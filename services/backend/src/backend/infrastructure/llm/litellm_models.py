"""LiteLLM model-id helpers (provider/model parsing and OpenAI Responses rewrite)."""

from __future__ import annotations


def require_litellm_model_id(model: str, *, field_name: str) -> str:
    stripped = model.strip()
    if "/" not in stripped or stripped.startswith("/") or stripped.endswith("/"):
        msg = f"{field_name} must be a LiteLLM id of the form provider/model (got {model!r})"
        raise ValueError(msg)
    provider, name = stripped.split("/", 1)
    if not provider or not name:
        msg = f"{field_name} must be a LiteLLM id of the form provider/model (got {model!r})"
        raise ValueError(msg)
    return stripped


def provider_segment(model: str) -> str:
    return model.split("/", 1)[0]


def bare_model_name(model: str) -> str:
    """Strip the LiteLLM provider prefix (keeps nested paths like responses/gpt-6-luna)."""
    return model.split("/", 1)[1]


def is_ollama_provider(provider: str) -> bool:
    return provider in {"ollama", "ollama_chat"}


def is_ollama_model(model: str) -> bool:
    return is_ollama_provider(provider_segment(model))


def runtime_chat_model(model: str) -> str:
    """Rewrite openai/<name> to openai/responses/<name> for tool-capable Responses routing."""
    if model.startswith("openai/responses/"):
        return model
    if model.startswith("openai/"):
        return f"openai/responses/{model.removeprefix('openai/')}"
    return model
