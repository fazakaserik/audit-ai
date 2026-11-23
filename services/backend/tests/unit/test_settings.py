"""Settings validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import Settings
from backend.domain.providers import LlmProvider


def test_openai_without_key_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider=LlmProvider.OPENAI, openai_api_key=None)


def test_ollama_qwen_defaults() -> None:
    settings = Settings()
    assert settings.llm_provider == LlmProvider.OLLAMA
    assert settings.llm_model == "qwen3.5:4b"
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.log_level == "INFO"
    assert settings.log_json is True
