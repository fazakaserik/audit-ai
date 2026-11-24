"""LiteLLM embedder passes dimensions and validates vector length."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.domain.errors import ModelUnavailableError
from backend.infrastructure.litellm_embed import LiteLLMEmbedder


def _embedder(*, dimensions: int | None) -> LiteLLMEmbedder:
    return LiteLLMEmbedder(
        model="openai/text-embedding-3-small",
        api_key="sk-test",
        api_base=None,
        timeout_seconds=30,
        max_concurrent_calls=1,
        dimensions_override=dimensions,
    )


@pytest.mark.asyncio
async def test_embed_passes_dimensions_and_accepts_matching_length() -> None:
    embedder = _embedder(dimensions=8)
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * 8)],
        usage=SimpleNamespace(prompt_tokens=1, total_tokens=1),
    )
    mock = AsyncMock(return_value=response)
    with patch("backend.infrastructure.litellm_embed.litellm.aembedding", new=mock):
        result = await embedder.embed(["hello"])
    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == 8
    assert mock.await_args.kwargs["dimensions"] == 8


@pytest.mark.asyncio
async def test_embed_rejects_mismatched_vector_length() -> None:
    embedder = _embedder(dimensions=8)
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * 4)],
        usage=None,
    )
    mock = AsyncMock(return_value=response)
    with (
        patch("backend.infrastructure.litellm_embed.litellm.aembedding", new=mock),
        pytest.raises(ModelUnavailableError, match="Embedding length"),
    ):
        await embedder.embed(["hello"])
