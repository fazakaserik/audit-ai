"""Ollama Embedder adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, cast

import httpx
from ollama import AsyncClient, ResponseError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._embedding_dims import dimensions_for
from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from domain.errors import ModelTimeoutError, ModelUnavailableError


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, ResponseError) and (exc.status_code >= 500 or exc.status_code == 429):
        return True
    return False


class OllamaEmbedder:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
    ) -> None:
        self._model = model
        self._dimensions = dimensions_for(model)
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncClient(host=base_url, timeout=timeout_seconds)

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
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Ollama embedding request timed out") from exc
            except (ConnectionError, ResponseError) as exc:
                raise ModelUnavailableError("Ollama embedding request failed") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _embed_once(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self._client.embed(
            model=self._model,
            input=cast(Any, list(texts)),
        )
        return [[float(value) for value in vector] for vector in response.embeddings]
