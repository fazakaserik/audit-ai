"""OpenAI ChatModel adapter (structured outputs via chat.completions.parse)."""

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
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.application.ports import ChatMessage, StructuredResult, ThinkingCallbacks
from domain.errors import ModelTimeoutError, ModelUnavailableError
from domain.session import LlmUsage

TModel = TypeVar("TModel", bound=BaseModel)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    return False


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
                raise ModelUnavailableError("OpenAI chat request failed") from exc

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
        vendor_messages = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=cast(Any, vendor_messages),
            response_format=schema,
            timeout=self._timeout_seconds,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            refusal = completion.choices[0].message.refusal
            detail = refusal if isinstance(refusal, str) and refusal else "empty structured output"
            raise ModelUnavailableError(f"OpenAI chat returned no parsed content: {detail}")
        usage_raw = completion.usage
        usage = LlmUsage.from_counts(
            prompt_tokens=getattr(usage_raw, "prompt_tokens", None) if usage_raw else None,
            completion_tokens=getattr(usage_raw, "completion_tokens", None) if usage_raw else None,
            total_tokens=getattr(usage_raw, "total_tokens", None) if usage_raw else None,
        )
        return StructuredResult(value=parsed, usage=usage)
