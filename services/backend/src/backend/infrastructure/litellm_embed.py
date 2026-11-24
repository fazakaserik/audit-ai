"""LiteLLM Embedder adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, cast

import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.application.dto import EmbedResult
from backend.domain.errors import ModelTimeoutError, ModelUnavailableError
from backend.domain.session import LlmUsage
from backend.infrastructure._embedding_dims import dimensions_for
from backend.infrastructure.llm.retry import MAX_ATTEMPTS, RETRY_WAIT

litellm.drop_params = True


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (Timeout, APIConnectionError, RateLimitError, ServiceUnavailableError)):
        return True
    if isinstance(exc, APIError):
        status = getattr(exc, "status_code", None)
        return isinstance(status, int) and (status >= 500 or status == 429)
    return False


def _usage_from_litellm(usage_raw: object | None) -> LlmUsage:
    if usage_raw is None:
        return LlmUsage()
    prompt = getattr(usage_raw, "prompt_tokens", None)
    if prompt is None:
        prompt = getattr(usage_raw, "input_tokens", None)
    total = getattr(usage_raw, "total_tokens", None)
    return LlmUsage.from_counts(
        prompt_tokens=prompt if isinstance(prompt, int) else None,
        total_tokens=total if isinstance(total, int) else None,
    )


class LiteLLMEmbedder:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        api_base: str | None,
        timeout_seconds: float,
        max_concurrent_calls: int,
        dimensions_override: int | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._timeout_seconds = timeout_seconds
        self._dimensions = dimensions_for(model, override=dimensions_override)
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)

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
            except Timeout as exc:
                raise ModelTimeoutError("Embedding request timed out") from exc
            except (APIConnectionError, RateLimitError, ServiceUnavailableError, APIError) as exc:
                raise ModelUnavailableError("Embedding request failed") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _embed_once(self, texts: Sequence[str]) -> EmbedResult:
        kwargs: dict[str, object] = {
            "model": self._model,
            "input": list(texts),
            "timeout": self._timeout_seconds,
            "num_retries": 0,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base
        response = await litellm.aembedding(**cast(Any, kwargs))
        data = getattr(response, "data", None)
        if not isinstance(data, list):
            raise ModelUnavailableError("Embedding response missing data")
        vectors: list[list[float]] = []
        for item in cast(list[object], data):
            if isinstance(item, Mapping):
                embedding = cast(Mapping[str, object], item).get("embedding")
            else:
                embedding = getattr(item, "embedding", None)
            if not isinstance(embedding, list):
                raise ModelUnavailableError("Embedding response missing vectors")
            row: list[float] = []
            for value in cast(list[object], embedding):
                if not isinstance(value, (int, float)):
                    raise ModelUnavailableError("Embedding response has non-numeric values")
                row.append(float(value))
            vectors.append(row)
        usage = _usage_from_litellm(getattr(response, "usage", None))
        return EmbedResult(vectors=vectors, usage=usage)
