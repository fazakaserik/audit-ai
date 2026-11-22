"""OpenAI Embedder adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._embedding_dims import dimensions_for
from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from domain.errors import ModelTimeoutError, ModelUnavailableError


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    return False


class OpenAIEmbedder:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
    ) -> None:
        self._model = model
        self._dimensions = dimensions_for(model)
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncOpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=timeout_seconds,
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        async with self._semaphore:
            try:
                return await self._embed_once(texts)
            except APITimeoutError as exc:
                raise ModelTimeoutError("OpenAI embedding request timed out") from exc
            except (
                APIConnectionError,
                RateLimitError,
                InternalServerError,
                APIStatusError,
            ) as exc:
                raise ModelUnavailableError("OpenAI embedding request failed") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _embed_once(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=cast(Any, list(texts)),
            timeout=self._timeout_seconds,
        )
        vectors: list[list[float]] = []
        for item in response.data:
            vectors.append([float(value) for value in item.embedding])
        return vectors
