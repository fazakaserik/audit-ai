"""Optional live Ollama smoke (marker: integration)."""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel, ConfigDict

from backend.application.ports import ChatMessage
from backend.infrastructure.ollama_chat import OllamaChatModel
from backend.infrastructure.ollama_embed import OllamaEmbedder


class _Ping(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    ok: bool


@pytest.mark.integration
async def test_ollama_embed_and_chat() -> None:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to run")
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.environ.get("LLM_MODEL", "qwen3.5:4b")
    embed_model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
    embedder = OllamaEmbedder(
        base_url=base,
        model=embed_model,
        timeout_seconds=120,
        max_concurrent_calls=1,
    )
    embedded = await embedder.embed(["ping"])
    assert embedded.vectors and len(embedded.vectors[0]) > 0
    chat = OllamaChatModel(
        base_url=base,
        model=model,
        timeout_seconds=120,
        max_concurrent_calls=1,
    )
    result = await chat.generate_structured(
        [ChatMessage(role="user", content='Reply with JSON {"ok": true}')],
        _Ping,
    )
    assert result.value.ok is True
