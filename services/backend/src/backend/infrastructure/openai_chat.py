"""OpenAI ChatModel adapter (structured outputs + tool turns)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, TypeVar, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ParsedChatCompletion
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.application.dto import (
    ChatMessage,
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

TModel = TypeVar("TModel", bound=BaseModel)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError):
        if is_context_overflow_message(str(exc)):
            return False
        return exc.status_code >= 500
    return False


def _usage_from_openai(usage_raw: object | None) -> LlmUsage:
    return LlmUsage.from_counts(
        prompt_tokens=getattr(usage_raw, "prompt_tokens", None) if usage_raw else None,
        completion_tokens=getattr(usage_raw, "completion_tokens", None) if usage_raw else None,
        total_tokens=getattr(usage_raw, "total_tokens", None) if usage_raw else None,
    )


def _to_openai_messages(messages: Sequence[ChatMessage]) -> list[dict[str, object]]:
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


class OpenAIChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
    ) -> None:
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncOpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=timeout_seconds,
        )

    @property
    def supports_thinking(self) -> bool:
        return False

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        _ = thinking
        async with self._semaphore:
            try:
                return await self._generate_structured_once(messages, schema)
            except APITimeoutError as exc:
                raise ModelTimeoutError("OpenAI chat request timed out") from exc
            except (
                APIConnectionError,
                RateLimitError,
                InternalServerError,
                APIStatusError,
            ) as exc:
                raise map_provider_chat_error("OpenAI chat request failed", exc) from exc

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult:
        _ = thinking
        async with self._semaphore:
            try:
                return await self._complete_tool_turn_once(messages, tools)
            except APITimeoutError as exc:
                raise ModelTimeoutError("OpenAI chat request timed out") from exc
            except (
                APIConnectionError,
                RateLimitError,
                InternalServerError,
                APIStatusError,
            ) as exc:
                raise map_provider_chat_error("OpenAI chat request failed", exc) from exc

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
    ) -> StructuredResult[TModel]:
        vendor_messages = _to_openai_messages(messages)
        completion_raw = await self._client.chat.completions.parse(
            model=self._model,
            messages=cast(Any, vendor_messages),
            response_format=schema,
            timeout=self._timeout_seconds,
        )
        completion = cast(ParsedChatCompletion[TModel], completion_raw)
        message = completion.choices[0].message
        parsed = message.parsed
        if parsed is None:
            refusal = message.refusal
            detail = refusal if isinstance(refusal, str) and refusal else "empty structured output"
            raise ModelUnavailableError(f"OpenAI chat returned no parsed content: {detail}")
        return StructuredResult(value=parsed, usage=_usage_from_openai(completion.usage))

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
    ) -> ToolTurnResult:
        completion_raw = await self._client.chat.completions.create(
            model=self._model,
            messages=cast(Any, _to_openai_messages(messages)),
            tools=cast(Any, to_vendor_function_tools(tools)),
            timeout=self._timeout_seconds,
        )
        completion = cast(ChatCompletion, completion_raw)
        message = completion.choices[0].message
        tool_calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            # OpenAI unions function + custom tool calls; only function tools are used.
            function = getattr(call, "function", None)
            call_id = getattr(call, "id", None)
            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", None)
            if isinstance(call_id, str) and isinstance(name, str) and isinstance(arguments, str):
                tool_calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
        content = message.content if isinstance(message.content, str) else None
        return ToolTurnResult(
            content=content,
            tool_calls=tuple(tool_calls),
            usage=_usage_from_openai(completion.usage),
        )
