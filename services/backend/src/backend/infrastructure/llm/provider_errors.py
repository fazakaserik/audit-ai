"""Map vendor exceptions to typed domain model errors."""

from __future__ import annotations

from backend.domain.errors import ContextTooLargeError, DomainError, ModelUnavailableError

_CONTEXT_MARKERS = (
    "context length",
    "context window",
    "prompt too long",
    "exceeds context",
    "maximum context",
    "n_ctx",
    "num_ctx",
    "token limit",
    "too many tokens",
    "context_length_exceeded",
    "maximum context length",
    "input is too long",
)

_OOM_MARKERS = (
    "out of memory",
    "oom",
    "cuda error",
    "insufficient memory",
)


def _exc_text(exc: BaseException) -> str:
    return str(exc).strip()


def _short_detail(text: str, *, limit: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def is_context_overflow_message(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CONTEXT_MARKERS)


def is_oom_message(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _OOM_MARKERS)


def map_provider_chat_error(prefix: str, exc: BaseException) -> DomainError:
    """Convert a vendor chat failure into ContextTooLargeError or ModelUnavailableError."""
    detail = _exc_text(exc)
    if detail and is_context_overflow_message(detail):
        return ContextTooLargeError(
            "Prompt exceeds the model context window. "
            "Start a new session, shorten the question, or raise OLLAMA_NUM_CTX; "
            f"provider detail: {_short_detail(detail)}"
        )
    if detail and is_oom_message(detail):
        return ModelUnavailableError(
            "Model ran out of memory while handling the request "
            "(often a large prompt or concurrent asks). "
            f"Provider detail: {_short_detail(detail)}"
        )
    if detail:
        return ModelUnavailableError(f"{prefix}: {_short_detail(detail)}")
    return ModelUnavailableError(prefix)
