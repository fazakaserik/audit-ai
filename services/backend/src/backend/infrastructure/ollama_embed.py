"""Ollama Embedder adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, cast

import httpx
from ollama import AsyncClient, ResponseError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.application.ports import EmbedResult
from backend.domain.errors import ModelTimeoutError, ModelUnavailableError
from backend.domain.session import LlmUsage
from backend.infrastructure._embedding_dims import dimensions_for
from backend.infrastructure._retry import MAX_ATTEMPTS, RETRY_WAIT


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    return bool(
        isinstance(exc, ResponseError) and (exc.status_code >= 500 or exc.status_code == 429)
    )


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

    async def embed(self, texts: Sequence[str]) -> EmbedResult:
        if not texts:
            return EmbedResult(vectors=[], usage=LlmUsage())
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
    async def _embed_once(self, texts: Sequence[str]) -> EmbedResult:
        response = await self._client.embed(
            model=self._model,
            input=cast(Any, list(texts)),
        )
        vectors = [[float(value) for value in vector] for vector in response.embeddings]
        prompt = getattr(response, "prompt_eval_count", None)
        usage = LlmUsage.from_counts(prompt_tokens=prompt, total_tokens=prompt)
        return EmbedResult(vectors=vectors, usage=usage)
