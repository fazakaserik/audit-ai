"""Ollama ChatModel adapter (structured JSON via format=schema)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, TypeVar, cast

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.application.ports import ChatMessage
from domain.errors import ModelTimeoutError, ModelUnavailableError

TModel = TypeVar("TModel", bound=BaseModel)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, ResponseError) and (exc.status_code >= 500 or exc.status_code == 429):
        return True
    return False


class OllamaChatModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
    ) -> None:
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncClient(host=base_url, timeout=timeout_seconds)

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
    ) -> TModel:
        async with self._semaphore:
            try:
                return await self._generate_structured_once(messages, schema)
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Ollama chat request timed out") from exc
            except (ConnectionError, ResponseError, ValidationError) as exc:
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
    ) -> TModel:
        vendor_messages = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        format_schema: dict[str, Any] = schema.model_json_schema()
        response = await self._client.chat(
            model=self._model,
            messages=cast(Any, vendor_messages),
            format=format_schema,
            options={"temperature": 0},
        )
        content = response.message.content
        if not content:
            raise ModelUnavailableError("Ollama chat returned empty content")
        return schema.model_validate_json(content)
