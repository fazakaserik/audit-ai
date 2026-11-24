"""Optional live Ollama smoke (marker: integration)."""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel, ConfigDict

from backend.application.dto import ChatMessage
from backend.infrastructure.litellm_chat import LiteLLMChatModel
from backend.infrastructure.litellm_embed import LiteLLMEmbedder


class _Ping(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    ok: bool


@pytest.mark.integration
async def test_ollama_embed_and_chat() -> None:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to run")
    base = os.environ.get("LLM_API_BASE") or os.environ.get(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
    )
    model = os.environ.get("LLM_MODEL", "ollama_chat/qwen3.5:4b")
    embed_model = os.environ.get("EMBEDDING_MODEL", "ollama/nomic-embed-text")
    if "/" not in model:
        model = f"ollama_chat/{model}"
    if "/" not in embed_model:
        embed_model = f"ollama/{embed_model}"
    embedder = LiteLLMEmbedder(
        model=embed_model,
        api_key=None,
        api_base=base,
        timeout_seconds=120,
        max_concurrent_calls=1,
    )
    embedded = await embedder.embed(["ping"])
    assert embedded.vectors and len(embedded.vectors[0]) > 0
    chat = LiteLLMChatModel(
        model=model,
        api_key=None,
        api_base=base,
        timeout_seconds=120,
        max_concurrent_calls=1,
    )
    result = await chat.generate_structured(
        [ChatMessage(role="user", content='Reply with JSON {"ok": true}')],
        _Ping,
    )
    assert result.value.ok is True
