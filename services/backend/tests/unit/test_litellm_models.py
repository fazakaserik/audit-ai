"""LiteLLM model-id helpers."""

from __future__ import annotations

import pytest

from backend.infrastructure.llm.litellm_models import (
    require_litellm_model_id,
    runtime_chat_model,
)


def test_runtime_chat_model_rewrites_openai_to_responses() -> None:
    assert runtime_chat_model("openai/gpt-6-luna") == "openai/responses/gpt-6-luna"


def test_runtime_chat_model_keeps_responses_prefix() -> None:
    assert (
        runtime_chat_model("openai/responses/gpt-6-luna") == "openai/responses/gpt-6-luna"
    )


def test_runtime_chat_model_leaves_ollama() -> None:
    assert runtime_chat_model("ollama_chat/qwen3.5:4b") == "ollama_chat/qwen3.5:4b"


def test_require_litellm_model_id_rejects_bare_name() -> None:
    with pytest.raises(ValueError, match="provider/model"):
        require_litellm_model_id("gpt-6-luna", field_name="LLM_MODEL")
