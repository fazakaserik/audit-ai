"""Provider error mapping for context overflow vs generic unavailable."""

from __future__ import annotations

from backend.domain.errors import ContextTooLargeError, ModelUnavailableError
from backend.infrastructure.llm.provider_errors import map_provider_chat_error


def test_map_context_overflow_to_context_too_large() -> None:
    err = map_provider_chat_error(
        "Ollama chat request failed",
        RuntimeError("prompt too long for context window (n_ctx)"),
    )
    assert isinstance(err, ContextTooLargeError)
    assert "context window" in err.message.lower()
    assert "OLLAMA_NUM_CTX" in err.message


def test_map_oom_to_model_unavailable_with_hint() -> None:
    err = map_provider_chat_error(
        "Ollama chat request failed",
        RuntimeError("CUDA error: out of memory"),
    )
    assert isinstance(err, ModelUnavailableError)
    assert "out of memory" in err.message.lower()


def test_map_generic_provider_error_includes_detail() -> None:
    err = map_provider_chat_error(
        "Ollama chat request failed",
        RuntimeError("connection reset by peer"),
    )
    assert isinstance(err, ModelUnavailableError)
    assert "connection reset by peer" in err.message
