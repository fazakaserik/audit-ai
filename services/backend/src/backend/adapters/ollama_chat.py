"""Ollama ChatModel adapter (structured JSON + tool turns)."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Sequence
from typing import Any, TypeVar, cast

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.application.ports import (
    ChatMessage,
    IncompleteStructuredOutputError,
    StructuredResult,
    ThinkingCallbacks,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from domain.errors import ModelTimeoutError, ModelUnavailableError
from domain.session import LlmUsage


def _usage_from_ollama(response: object) -> LlmUsage:
    prompt = getattr(response, "prompt_eval_count", None)
    completion = getattr(response, "eval_count", None)
    return LlmUsage.from_counts(prompt_tokens=prompt, completion_tokens=completion)


TModel = TypeVar("TModel", bound=BaseModel)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
# Thinking models can loop forever on "decline" decisions; bound wall-clock + size.
_THINKING_BUDGET_SECONDS = 45.0
_THINKING_BUDGET_CHARS = 12_000


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    return bool(isinstance(exc, ResponseError) and (exc.status_code >= 500 or exc.status_code == 429))


def _extract_json_text(*, content: str | None, thinking: str | None) -> str:
    """Prefer message content; fall back to JSON embedded in thinking (Qwen-style)."""
    for candidate in (content, thinking):
        if candidate is None:
            continue
        text = candidate.strip()
        if not text:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_OBJECT_RE.search(text)
            if match is None:
                continue
            text = match.group(0)
            try:
                json.loads(text)
            except json.JSONDecodeError:
                continue
        return text
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


def _to_ollama_tools(tools: Sequence[ToolSpec]) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


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
        supports_thinking: bool | None = None,
    ) -> None:
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncClient(host=base_url, timeout=timeout_seconds)
        self._supports_thinking = supports_thinking if supports_thinking is not None else False
        self._thinking_probed = supports_thinking is not None

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

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
            except (ConnectionError, ResponseError, ValidationError) as exc:
                raise ModelUnavailableError("Ollama chat request failed") from exc

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
                raise ModelUnavailableError("Ollama chat request failed") from exc

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
            usage = LlmUsage()
            budget_exhausted = False
            stream = await self._client.chat(  # pyright: ignore[reportUnknownMemberType] — ollama SDK overload
                model=self._model,
                messages=cast(Any, vendor_messages),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
                format=cast(Any, format_schema),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
                think=True,
                stream=True,
                options={"temperature": 0},
            )
            async for chunk in stream:
                if getattr(chunk, "done", False):
                    usage = _usage_from_ollama(chunk)
                message = chunk.message
                delta_thinking = getattr(message, "thinking", None)
                if isinstance(delta_thinking, str) and delta_thinking:
                    thinking_parts.append(delta_thinking)
                    thinking_chars += len(delta_thinking)
                    await thinking.on_delta(delta_thinking)
                delta_content = message.content
                if isinstance(delta_content, str) and delta_content:
                    content_parts.append(delta_content)
                elapsed = time.perf_counter() - started
                if (
                    thinking_chars >= _THINKING_BUDGET_CHARS or elapsed >= _THINKING_BUDGET_SECONDS
                ) and not content_parts:
                    budget_exhausted = True
                    break
            thinking.on_seconds(time.perf_counter() - started)
            if budget_exhausted and not content_parts:
                raise IncompleteStructuredOutputError(
                    "Ollama thinking exceeded budget without structured output"
                )
            try:
                payload = _extract_json_text(
                    content="".join(content_parts) or None,
                    thinking="".join(thinking_parts) or None,
                )
            except ModelUnavailableError as exc:
                raise IncompleteStructuredOutputError(str(exc)) from exc
            return StructuredResult(value=schema.model_validate_json(payload), usage=usage)

        response = await self._client.chat(  # pyright: ignore[reportUnknownMemberType] — ollama SDK overload
            model=self._model,
            messages=cast(Any, vendor_messages),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            format=cast(Any, format_schema),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            think=use_think,
            options={"temperature": 0},
        )
        payload = _extract_json_text(
            content=response.message.content,
            thinking=getattr(response.message, "thinking", None),
        )
        return StructuredResult(
            value=schema.model_validate_json(payload),
            usage=_usage_from_ollama(response),
        )

    async def _tool_turn_without_thinking(
        self,
        vendor_messages: list[dict[str, object]],
        ollama_tools: list[dict[str, object]],
    ) -> ToolTurnResult:
        response = await self._client.chat(  # pyright: ignore[reportUnknownMemberType] — ollama SDK overload
            model=self._model,
            messages=cast(Any, vendor_messages),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            tools=cast(Any, ollama_tools),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            think=False,
            options={"temperature": 0},
        )
        content = response.message.content if isinstance(response.message.content, str) else None
        return ToolTurnResult(
            content=content,
            tool_calls=_parse_tool_calls(getattr(response.message, "tool_calls", None)),
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
        ollama_tools = _to_ollama_tools(tools)
        use_think = self._supports_thinking and thinking is not None

        if not use_think or thinking is None:
            return await self._tool_turn_without_thinking(vendor_messages, ollama_tools)

        started = time.perf_counter()
        content_parts: list[str] = []
        thinking_chars = 0
        usage = LlmUsage()
        raw_calls: object | None = None
        stream = await self._client.chat(  # pyright: ignore[reportUnknownMemberType] — ollama SDK overload
            model=self._model,
            messages=cast(Any, vendor_messages),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            tools=cast(Any, ollama_tools),  # pyright: ignore[reportExplicitAny, reportAny] — ollama SDK
            think=True,
            stream=True,
            options={"temperature": 0},
        )
        async for chunk in stream:
            if getattr(chunk, "done", False):
                usage = _usage_from_ollama(chunk)
            message = chunk.message
            chunk_calls = getattr(message, "tool_calls", None)
            if chunk_calls:
                raw_calls = chunk_calls
            delta_thinking = getattr(message, "thinking", None)
            if isinstance(delta_thinking, str) and delta_thinking:
                thinking_chars += len(delta_thinking)
                await thinking.on_delta(delta_thinking)
            delta_content = message.content
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
