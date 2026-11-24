"""LiteLLM ChatModel adapter (structured outputs + tool turns)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, TypeVar, cast

import httpx
import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.application.dto import (
    ChatMessage,
    IncompleteStructuredOutputError,
    StructuredResult,
    ThinkingCallbacks,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from backend.domain.errors import ModelTimeoutError, ModelUnavailableError
from backend.domain.session import LlmUsage
from backend.infrastructure.llm.json_extract import extract_json_text
from backend.infrastructure.llm.litellm_models import (
    bare_model_name,
    is_ollama_model,
    runtime_chat_model,
)
from backend.infrastructure.llm.provider_errors import (
    is_context_overflow_message,
    map_provider_chat_error,
)
from backend.infrastructure.llm.retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.infrastructure.llm.strict_schema import openai_strict_json_schema
from backend.infrastructure.llm.tools import to_vendor_function_tools

TModel = TypeVar("TModel", bound=BaseModel)

# UI budget for streamed thinking; structured streams are not aborted early
# (cutting mid-think drops the final JSON and forced insufficient_evidence).
_THINKING_BUDGET_SECONDS = 45.0
_THINKING_BUDGET_CHARS = 12_000

litellm.drop_params = True


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (Timeout, APIConnectionError, RateLimitError, ServiceUnavailableError)):
        return True
    if isinstance(exc, APIError):
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            if is_context_overflow_message(str(exc)):
                return False
            return status >= 500 or status == 429
    return bool(isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)))


def _usage_from_litellm(usage_raw: object | None) -> LlmUsage:
    if usage_raw is None:
        return LlmUsage()
    prompt = getattr(usage_raw, "prompt_tokens", None)
    if prompt is None:
        prompt = getattr(usage_raw, "input_tokens", None)
    completion = getattr(usage_raw, "completion_tokens", None)
    if completion is None:
        completion = getattr(usage_raw, "output_tokens", None)
    total = getattr(usage_raw, "total_tokens", None)
    return LlmUsage.from_counts(
        prompt_tokens=prompt if isinstance(prompt, int) else None,
        completion_tokens=completion if isinstance(completion, int) else None,
        total_tokens=total if isinstance(total, int) else None,
    )


def _to_litellm_messages(messages: Sequence[ChatMessage]) -> list[dict[str, object]]:
    vendor: list[dict[str, object]] = []
    for message in messages:
        item: dict[str, object] = {"role": message.role}
        if message.content is not None:
            item["content"] = message.content
        elif message.role != "assistant" or not message.tool_calls:
            item["content"] = ""
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        if message.tool_call_id is not None:
            item["tool_call_id"] = message.tool_call_id
        if message.name is not None:
            item["name"] = message.name
        vendor.append(item)
    return vendor


def _json_schema_response_format(schema: type[BaseModel]) -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": openai_strict_json_schema(schema),
            "strict": True,
        },
    }


def _mapping_get(obj: object, key: str) -> object | None:
    if isinstance(obj, Mapping):
        return cast(Mapping[str, object], obj).get(key)
    return getattr(obj, key, None)


def _parse_tool_calls(raw_calls: object) -> tuple[ToolCall, ...]:
    if not isinstance(raw_calls, (list, tuple)):
        return ()
    items = list(cast(Sequence[object], raw_calls))
    parsed: list[ToolCall] = []
    for index, call in enumerate(items):
        function = _mapping_get(call, "function")
        call_id = _mapping_get(call, "id")
        if function is None:
            continue
        name = _mapping_get(function, "name")
        arguments = _mapping_get(function, "arguments")
        if not isinstance(name, str):
            continue
        if isinstance(arguments, dict):
            arguments_text = json.dumps(cast(dict[str, object], arguments))
        elif isinstance(arguments, str):
            arguments_text = arguments
        else:
            arguments_text = "{}"
        tool_id = call_id if isinstance(call_id, str) and call_id else f"call_{index}"
        parsed.append(ToolCall(id=tool_id, name=name, arguments=arguments_text))
    return tuple(parsed)


def _accumulate_tool_call_deltas(
    buckets: dict[int, dict[str, object]],
    chunk_calls: object,
) -> None:
    """Merge streamed tool-call fragments by ``index`` (OpenAI-style) into ``buckets``."""
    if not isinstance(chunk_calls, (list, tuple)):
        return
    for offset, item in enumerate(cast(Sequence[object], chunk_calls)):
        index_raw = _mapping_get(item, "index")
        index = index_raw if isinstance(index_raw, int) else offset
        slot = buckets.setdefault(index, {"function": {}})
        call_id = _mapping_get(item, "id")
        if isinstance(call_id, str) and call_id:
            slot["id"] = call_id
        function = _mapping_get(item, "function")
        if function is None:
            continue
        dest = cast(dict[str, object], slot.setdefault("function", {}))
        name = _mapping_get(function, "name")
        if isinstance(name, str) and name:
            dest["name"] = name
        arguments = _mapping_get(function, "arguments")
        if isinstance(arguments, str):
            dest["arguments"] = str(dest.get("arguments") or "") + arguments
        elif isinstance(arguments, dict):
            dest["arguments"] = arguments


def _message_field(message: object | None, name: str) -> object | None:
    if message is None:
        return None
    return _mapping_get(message, name)


class LiteLLMChatModel:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        api_base: str | None,
        timeout_seconds: float,
        max_concurrent_calls: int,
        num_ctx: int = 32_768,
        supports_thinking: bool | None = None,
    ) -> None:
        self._configured_model = model
        self._runtime_model = runtime_chat_model(model)
        self._api_key = api_key
        self._api_base = api_base
        self._timeout_seconds = timeout_seconds
        self._num_ctx = num_ctx
        self._is_ollama = is_ollama_model(model)
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        if supports_thinking is not None:
            self._supports_thinking = supports_thinking
            self._thinking_probed = True
        else:
            self._supports_thinking = False
            self._thinking_probed = not self._is_ollama

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

    def _base_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "model": self._runtime_model,
            "timeout": self._timeout_seconds,
            "num_retries": 0,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._is_ollama:
            kwargs["num_ctx"] = self._num_ctx
            kwargs["temperature"] = 0
        return kwargs

    async def _ensure_thinking_capability(self) -> None:
        if self._thinking_probed:
            return
        self._thinking_probed = True
        if not self._is_ollama or not self._api_base:
            self._supports_thinking = False
            return
        try:
            async with httpx.AsyncClient(base_url=self._api_base, timeout=10.0) as client:
                response = await client.post(
                    "/api/show",
                    json={"name": bare_model_name(self._configured_model)},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            self._supports_thinking = False
            return
        caps = payload.get("capabilities") if isinstance(payload, dict) else None
        self._supports_thinking = isinstance(caps, list) and "thinking" in caps

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        async with self._semaphore:
            try:
                return await self._generate_structured_once(messages, schema, thinking=thinking)
            except Timeout as exc:
                raise ModelTimeoutError("Chat request timed out") from exc
            except ValidationError as exc:
                raise map_provider_chat_error(
                    "Chat returned invalid structured output",
                    exc,
                ) from exc
            except (APIConnectionError, RateLimitError, ServiceUnavailableError, APIError) as exc:
                raise map_provider_chat_error("Chat request failed", exc) from exc
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Chat request timed out") from exc
            except ConnectionError as exc:
                raise map_provider_chat_error("Chat request failed", exc) from exc

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult:
        async with self._semaphore:
            try:
                return await self._complete_tool_turn_once(messages, tools, thinking=thinking)
            except Timeout as exc:
                raise ModelTimeoutError("Chat request timed out") from exc
            except (APIConnectionError, RateLimitError, ServiceUnavailableError, APIError) as exc:
                raise map_provider_chat_error("Chat request failed", exc) from exc
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Chat request timed out") from exc
            except ConnectionError as exc:
                raise map_provider_chat_error("Chat request failed", exc) from exc

    async def _acompletion(self, **kwargs: object) -> object:
        cleaned = {key: value for key, value in kwargs.items() if value is not None}
        return await litellm.acompletion(**cast(Any, cleaned))

    async def _generate_structured_without_thinking(
        self,
        vendor_messages: list[dict[str, object]],
        schema: type[TModel],
    ) -> StructuredResult[TModel]:
        response = await self._acompletion(
            **self._base_kwargs(),
            messages=vendor_messages,
            response_format=_json_schema_response_format(schema),
            reasoning_effort="none" if self._is_ollama else None,
        )
        choice = _mapping_get(response, "choices")
        first = choice[0] if isinstance(choice, list) and choice else None
        message = _mapping_get(first, "message") if first is not None else None
        content = _message_field(message, "content")
        thinking_text = _message_field(message, "reasoning_content")
        content_text = content if isinstance(content, str) else None
        thinking_str = thinking_text if isinstance(thinking_text, str) else None
        try:
            payload = extract_json_text(content=content_text, thinking=thinking_str)
            return StructuredResult(
                value=schema.model_validate_json(payload),
                usage=_usage_from_litellm(_mapping_get(response, "usage")),
            )
        except (ModelUnavailableError, ValidationError) as exc:
            raise IncompleteStructuredOutputError(str(exc)) from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _generate_structured_once(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None,
    ) -> StructuredResult[TModel]:
        await self._ensure_thinking_capability()
        vendor_messages = _to_litellm_messages(messages)
        use_think = self._supports_thinking and thinking is not None

        if not use_think or thinking is None:
            return await self._generate_structured_without_thinking(vendor_messages, schema)

        started = time.perf_counter()
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        thinking_chars = 0
        emit_thinking = True
        usage = LlmUsage()
        stream = cast(
            AsyncIterator[object],
            await self._acompletion(
                **self._base_kwargs(),
                messages=vendor_messages,
                response_format=_json_schema_response_format(schema),
                stream=True,
                reasoning_effort="low",
            ),
        )
        async for chunk in stream:
            choice_list = _mapping_get(chunk, "choices")
            first = choice_list[0] if isinstance(choice_list, list) and choice_list else None
            delta = _mapping_get(first, "delta") if first is not None else None
            finish = _mapping_get(first, "finish_reason") if first is not None else None
            if finish is not None:
                usage = _usage_from_litellm(_mapping_get(chunk, "usage"))
            delta_thinking = _message_field(delta, "reasoning_content")
            if isinstance(delta_thinking, str) and delta_thinking:
                thinking_parts.append(delta_thinking)
                thinking_chars += len(delta_thinking)
                if emit_thinking:
                    await thinking.on_delta(delta_thinking)
            delta_content = _message_field(delta, "content")
            if isinstance(delta_content, str) and delta_content:
                content_parts.append(delta_content)
            elapsed = time.perf_counter() - started
            if emit_thinking and (
                thinking_chars >= _THINKING_BUDGET_CHARS or elapsed >= _THINKING_BUDGET_SECONDS
            ):
                emit_thinking = False
        thinking.on_seconds(time.perf_counter() - started)
        try:
            payload = extract_json_text(
                content="".join(content_parts) or None,
                thinking="".join(thinking_parts) or None,
            )
            return StructuredResult(
                value=schema.model_validate_json(payload),
                usage=usage,
            )
        except (ModelUnavailableError, ValidationError):
            cold = await self._generate_structured_without_thinking(vendor_messages, schema)
            return StructuredResult(value=cold.value, usage=usage + cold.usage)

    async def _tool_turn_without_thinking(
        self,
        vendor_messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ToolTurnResult:
        response = await self._acompletion(
            **self._base_kwargs(),
            messages=vendor_messages,
            tools=tools,
            reasoning_effort="none" if self._is_ollama else None,
        )
        choice_list = _mapping_get(response, "choices")
        first = choice_list[0] if isinstance(choice_list, list) and choice_list else None
        message = _mapping_get(first, "message") if first is not None else None
        content = _message_field(message, "content")
        content_text = content if isinstance(content, str) else None
        return ToolTurnResult(
            content=content_text,
            tool_calls=_parse_tool_calls(_message_field(message, "tool_calls")),
            usage=_usage_from_litellm(_mapping_get(response, "usage")),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _complete_tool_turn_once(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None,
    ) -> ToolTurnResult:
        await self._ensure_thinking_capability()
        vendor_messages = _to_litellm_messages(messages)
        vendor_tools = to_vendor_function_tools(tools)
        use_think = self._supports_thinking and thinking is not None

        if not use_think or thinking is None:
            return await self._tool_turn_without_thinking(vendor_messages, vendor_tools)

        started = time.perf_counter()
        content_parts: list[str] = []
        thinking_chars = 0
        emit_thinking = True
        usage = LlmUsage()
        tool_call_buckets: dict[int, dict[str, object]] = {}
        stream = cast(
            AsyncIterator[object],
            await self._acompletion(
                **self._base_kwargs(),
                messages=vendor_messages,
                tools=vendor_tools,
                stream=True,
                reasoning_effort="low",
            ),
        )
        async for chunk in stream:
            choice_list = _mapping_get(chunk, "choices")
            first = choice_list[0] if isinstance(choice_list, list) and choice_list else None
            delta = _mapping_get(first, "delta") if first is not None else None
            finish = _mapping_get(first, "finish_reason") if first is not None else None
            if finish is not None:
                usage = _usage_from_litellm(_mapping_get(chunk, "usage"))
            chunk_calls = _message_field(delta, "tool_calls")
            if chunk_calls is not None:
                _accumulate_tool_call_deltas(tool_call_buckets, chunk_calls)
            delta_thinking = _message_field(delta, "reasoning_content")
            if isinstance(delta_thinking, str) and delta_thinking:
                thinking_chars += len(delta_thinking)
                if emit_thinking:
                    await thinking.on_delta(delta_thinking)
            delta_content = _message_field(delta, "content")
            if isinstance(delta_content, str) and delta_content:
                content_parts.append(delta_content)
            elapsed = time.perf_counter() - started
            if emit_thinking and (
                thinking_chars >= _THINKING_BUDGET_CHARS or elapsed >= _THINKING_BUDGET_SECONDS
            ):
                # Stop emitting thinking, but keep reading until finish_reason so late
                # tool_calls deltas are not dropped (same pattern as structured generate).
                emit_thinking = False
        thinking.on_seconds(time.perf_counter() - started)
        merged_calls = [tool_call_buckets[key] for key in sorted(tool_call_buckets)]
        tool_calls = _parse_tool_calls(merged_calls)
        content = "".join(content_parts) or None
        if tool_calls:
            return ToolTurnResult(content=content, tool_calls=tool_calls, usage=usage)

        cold = await self._tool_turn_without_thinking(vendor_messages, vendor_tools)
        return ToolTurnResult(
            content=cold.content if cold.content is not None else content,
            tool_calls=cold.tool_calls,
            usage=usage + cold.usage,
        )
