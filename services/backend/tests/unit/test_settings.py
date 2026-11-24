"""Settings validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_openai_without_key_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(
            llm_model="openai/gpt-6-luna",
            llm_api_key=None,
            llm_api_base=None,
            embedding_model="openai/text-embedding-3-small",
            embedding_api_key=None,
        )


def test_model_without_provider_prefix_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_model="qwen3.5:4b", embedding_model="ollama/nomic-embed-text")


def test_ollama_without_key_ok() -> None:
    settings = Settings(
        llm_model="ollama_chat/qwen3.5:4b",
        llm_api_key=None,
        llm_api_base="http://127.0.0.1:11434",
        embedding_model="ollama/nomic-embed-text",
        embedding_api_key=None,
    )
    assert settings.llm_model.startswith("ollama_chat/")


def test_embedding_key_falls_back_to_llm_key() -> None:
    settings = Settings(
        llm_model="openai/gpt-6-luna",
        llm_api_key="sk-test",
        llm_api_base=None,
        embedding_model="openai/text-embedding-3-small",
        embedding_api_key=None,
    )
    assert settings.llm_api_key is not None
