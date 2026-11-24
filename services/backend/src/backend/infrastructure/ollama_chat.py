"""Ollama ChatModel adapter (structured JSON + tool turns)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import TypeVar, cast

import httpx
from ollama import AsyncClient, ResponseError
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
from backend.infrastructure.llm.provider_errors import (
    is_context_overflow_message,
    map_provider_chat_error,
)
from backend.infrastructure.llm.retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.infrastructure.llm.tools import to_vendor_function_tools
from backend.infrastructure.ollama_protocols import ollama_chat_client


def _usage_from_ollama(response: object) -> LlmUsage:
    prompt = getattr(response, "prompt_eval_count", None)
    completion = getattr(response, "eval_count", None)
    return LlmUsage.from_counts(prompt_tokens=prompt, completion_tokens=completion)


TModel = TypeVar("TModel", bound=BaseModel)

# UI budget for streamed thinking; the model stream itself is not aborted early
# (cutting mid-think drops the final JSON and forced insufficient_evidence).
_THINKING_BUDGET_SECONDS = 45.0
_THINKING_BUDGET_CHARS = 12_000


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, ResponseError):
        if is_context_overflow_message(str(exc)):
            return False
        return exc.status_code >= 500 or exc.status_code == 429
    return False


def _try_parse_json_object(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass
    # Prefer the last object — thinking prose often has braces before the payload.
    decoder = json.JSONDecoder()
    last: str | None = None
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(stripped, index)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            last = stripped[index:end]
    return last


def _extract_json_text(*, content: str | None, thinking: str | None) -> str:
    """Prefer message content; fall back to JSON embedded in thinking (Qwen-style)."""
    for candidate in (content, thinking):
        if candidate is None:
            continue
        parsed = _try_parse_json_object(candidate)
        if parsed is not None:
            return parsed
    raise ModelUnavailableError("Ollama chat returned empty content")


def _to_ollama_messages(messages: Sequence[ChatMessage]) -> list[dict[str, object]]:
    vendor: list[dict[str, object]] = []
    for message in messages:
        item: dict[str, object] = {"role": message.role}
        if message.content is not None:
            item["content"] = message.content
        elif message.role == "tool":
            item["content"] = ""
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.loads(call.arguments)
                        if call.arguments.strip().startswith("{")
                        else call.arguments,
                    },
                    "id": call.id,
                }
                for call in message.tool_calls
            ]
        if message.tool_call_id is not None:
            item["tool_call_id"] = message.tool_call_id
        if message.name is not None:
            item["name"] = message.name
        vendor.append(item)
    return vendor


def _optional_attr(instance: object, name: str) -> object | None:
    return cast(object | None, getattr(instance, name, None))


def _mapping_get(obj: object, key: str) -> object | None:
    if isinstance(obj, dict):
        typed = cast(dict[str, object], obj)
        return typed.get(key)
    return getattr(obj, key, None)


def _parse_tool_calls(raw_calls: object) -> tuple[ToolCall, ...]:
    """Best-effort parse of Ollama/OpenAI-shaped tool_calls payloads."""
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


class OllamaChatModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
        num_ctx: int = 32_768,
        supports_thinking: bool | None = None,
    ) -> None:
        self._model = model
        self._num_ctx = num_ctx
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncClient(host=base_url, timeout=timeout_seconds)
        self._supports_thinking = supports_thinking if supports_thinking is not None else False
        self._thinking_probed = supports_thinking is not None

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

    def _chat_options(self) -> dict[str, object]:
        return {"temperature": 0, "num_ctx": self._num_ctx}

    async def _ensure_thinking_capability(self) -> None:
        if self._thinking_probed:
            return
        self._thinking_probed = True
        try:
            shown = await self._client.show(self._model)
        except Exception:
            self._supports_thinking = False
            return
        caps = getattr(shown, "capabilities", None)
        if isinstance(caps, list):
            self._supports_thinking = "thinking" in caps
        else:
            self._supports_thinking = False

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
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Ollama chat request timed out") from exc
            except ValidationError as exc:
                raise map_provider_chat_error(
                    "Ollama chat returned invalid structured output",
                    exc,
                ) from exc
            except (ConnectionError, ResponseError) as exc:
                raise map_provider_chat_error("Ollama chat request failed", exc) from exc

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
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Ollama chat request timed out") from exc
            except (ConnectionError, ResponseError) as exc:
                raise map_provider_chat_error("Ollama chat request failed", exc) from exc

    async def _generate_structured_without_thinking(
        self,
        vendor_messages: list[dict[str, object]],
        format_schema: dict[str, object],
        schema: type[TModel],
    ) -> StructuredResult[TModel]:
        chat = ollama_chat_client(self._client)
        response = await chat.chat(
            model=self._model,
            messages=vendor_messages,
            format=format_schema,
            think=False,
            options=self._chat_options(),
        )
        response_obj = cast(object, response)
        response_message = getattr(response_obj, "message", None)
        raw_content = (
            getattr(response_message, "content", None) if response_message is not None else None
        )
        content = raw_content if isinstance(raw_content, str) else None
        raw_thinking = (
            getattr(response_message, "thinking", None) if response_message is not None else None
        )
        thinking_text = raw_thinking if isinstance(raw_thinking, str) else None
        try:
            payload = _extract_json_text(content=content, thinking=thinking_text)
            return StructuredResult(
                value=schema.model_validate_json(payload),
                usage=_usage_from_ollama(response),
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
        vendor_messages = _to_ollama_messages(messages)
        format_schema = cast(dict[str, object], schema.model_json_schema())
        use_think = self._supports_thinking

        if thinking is not None and use_think:
            started = time.perf_counter()
            content_parts: list[str] = []
            thinking_parts: list[str] = []
            thinking_chars = 0
            emit_thinking = True
            usage = LlmUsage()
            chat = ollama_chat_client(self._client)
            stream = cast(
                AsyncIterator[object],
                await chat.chat(
                    model=self._model,
                    messages=vendor_messages,
                    format=format_schema,
                    think=True,
                    stream=True,
                    options=self._chat_options(),
                ),
            )
            async for chunk in stream:
                if getattr(chunk, "done", False):
                    usage = _usage_from_ollama(chunk)
                message = getattr(chunk, "message", None)
                delta_thinking = getattr(message, "thinking", None)
                if isinstance(delta_thinking, str) and delta_thinking:
                    thinking_parts.append(delta_thinking)
                    thinking_chars += len(delta_thinking)
                    if emit_thinking:
                        await thinking.on_delta(delta_thinking)
                delta_content = getattr(message, "content", None)
                if isinstance(delta_content, str) and delta_content:
                    content_parts.append(delta_content)
                elapsed = time.perf_counter() - started
                # Stop UI deltas after budget, but keep reading so final JSON can arrive.
                if emit_thinking and (
                    thinking_chars >= _THINKING_BUDGET_CHARS or elapsed >= _THINKING_BUDGET_SECONDS
                ):
                    emit_thinking = False
            thinking.on_seconds(time.perf_counter() - started)
            try:
                payload = _extract_json_text(
                    content="".join(content_parts) or None,
                    thinking="".join(thinking_parts) or None,
                )
                return StructuredResult(
                    value=schema.model_validate_json(payload),
                    usage=usage,
                )
            except (ModelUnavailableError, ValidationError):
                # Thinking models often narrate the answer then emit empty/invalid JSON.
                # Retry cold (same pattern as tool turns).
                cold = await self._generate_structured_without_thinking(
                    vendor_messages,
                    format_schema,
                    schema,
                )
                return StructuredResult(value=cold.value, usage=usage + cold.usage)

        return await self._generate_structured_without_thinking(
            vendor_messages,
            format_schema,
            schema,
        )

    async def _tool_turn_without_thinking(
        self,
        vendor_messages: list[dict[str, object]],
        ollama_tools: list[dict[str, object]],
    ) -> ToolTurnResult:
        chat = ollama_chat_client(self._client)
        response = await chat.chat(
            model=self._model,
            messages=vendor_messages,
            tools=ollama_tools,
            think=False,
            options=self._chat_options(),
        )
        response_obj = cast(object, response)
        message_obj = getattr(response_obj, "message", None)
        raw_content = getattr(message_obj, "content", None) if message_obj is not None else None
        content = raw_content if isinstance(raw_content, str) else None
        raw_tool_calls = (
            getattr(message_obj, "tool_calls", None) if message_obj is not None else None
        )
        return ToolTurnResult(
            content=content,
            tool_calls=_parse_tool_calls(raw_tool_calls),
            usage=_usage_from_ollama(response),
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
        vendor_messages = _to_ollama_messages(messages)
        ollama_tools = to_vendor_function_tools(tools)
        use_think = self._supports_thinking and thinking is not None

        if not use_think or thinking is None:
            return await self._tool_turn_without_thinking(vendor_messages, ollama_tools)

        started = time.perf_counter()
        content_parts: list[str] = []
        thinking_chars = 0
        usage = LlmUsage()
        raw_calls: object | None = None
        chat = ollama_chat_client(self._client)
        stream = cast(
            AsyncIterator[object],
            await chat.chat(
                model=self._model,
                messages=vendor_messages,
                tools=ollama_tools,
                think=True,
                stream=True,
                options=self._chat_options(),
            ),
        )
        async for chunk in stream:
            if getattr(chunk, "done", False):
                usage = _usage_from_ollama(chunk)
            message = getattr(chunk, "message", None)
            chunk_calls = getattr(message, "tool_calls", None)
            if chunk_calls is not None:
                raw_calls = cast(object, chunk_calls)
            delta_thinking = getattr(message, "thinking", None)
            if isinstance(delta_thinking, str) and delta_thinking:
                thinking_chars += len(delta_thinking)
                await thinking.on_delta(delta_thinking)
            delta_content = getattr(message, "content", None)
            if isinstance(delta_content, str) and delta_content:
                content_parts.append(delta_content)
            elapsed = time.perf_counter() - started
            if thinking_chars >= _THINKING_BUDGET_CHARS or elapsed >= _THINKING_BUDGET_SECONDS:
                break
        thinking.on_seconds(time.perf_counter() - started)
        tool_calls = _parse_tool_calls(raw_calls)
        content = "".join(content_parts) or None
        if tool_calls:
            return ToolTurnResult(content=content, tool_calls=tool_calls, usage=usage)

        # Thinking models often narrate intended tool use without emitting tool_calls.
        # Retry once with thinking disabled so the tool loop can actually run.
        cold = await self._tool_turn_without_thinking(vendor_messages, ollama_tools)
        return ToolTurnResult(
            content=cold.content if cold.content is not None else content,
            tool_calls=cold.tool_calls,
            usage=usage + cold.usage,
        )
