"""Application settings (flat environment variables)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.infrastructure.llm.litellm_models import (
    is_ollama_provider,
    provider_segment,
    require_litellm_model_id,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    llm_model: str = "ollama_chat/qwen3.5:4b"
    llm_api_key: SecretStr | None = None
    llm_api_base: str | None = "http://127.0.0.1:11434"

    embedding_model: str = "ollama/nomic-embed-text"
    embedding_api_key: SecretStr | None = None
    embedding_api_base: str | None = None
    embedding_dimensions: int | None = Field(default=None, ge=1, le=16_384)

    # Applied only when LLM_MODEL uses an ollama / ollama_chat prefix.
    ollama_num_ctx: int = Field(default=32_768, ge=2_048, le=262_144)

    database_url: str = "postgresql+asyncpg://audit:audit@localhost:5432/audit"
    document_storage_path: Path = Path("./data/storage")

    model_timeout_seconds: float = Field(default=120.0, gt=0)
    retrieval_top_k: int = Field(default=8, ge=1, le=50)
    relevance_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    max_concurrent_model_calls: int = Field(default=2, ge=1, le=64)
    agent_max_tool_rounds: int = Field(default=6, ge=1, le=20)
    agent_max_check_restarts: int = Field(default=2, ge=0, le=10)
    agent_read_max_chars: int = Field(default=12_000, ge=500, le=200_000)
    agent_search_snippet_chars: int = Field(default=2_000, ge=240, le=20_000)
    session_context_turns: int = Field(default=5, ge=1, le=50)
    agent_evidence_max_chars: int = Field(default=24_000, ge=2_000, le=200_000)

    upload_max_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    upload_max_files: int = Field(default=200, ge=1)
    upload_max_file_bytes: int = Field(default=20 * 1024 * 1024, ge=1)

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    enable_api_docs: bool = False

    log_level: str = "INFO"
    log_json: bool = True

    @field_validator("llm_api_base", "embedding_api_base", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_litellm_models_and_keys(self) -> Settings:
        require_litellm_model_id(self.llm_model, field_name="LLM_MODEL")
        require_litellm_model_id(self.embedding_model, field_name="EMBEDDING_MODEL")

        chat_key = _secret_or_none(self.llm_api_key)
        embed_key = _secret_or_none(self.embedding_api_key) or chat_key

        chat_provider = provider_segment(self.llm_model)
        if not is_ollama_provider(chat_provider) and not chat_key:
            msg = "LLM_API_KEY is required when LLM_MODEL is not an ollama / ollama_chat model"
            raise ValueError(msg)

        embed_provider = provider_segment(self.embedding_model)
        if not is_ollama_provider(embed_provider) and not embed_key:
            msg = (
                "EMBEDDING_API_KEY or LLM_API_KEY is required when EMBEDDING_MODEL "
                "is not an ollama / ollama_chat model"
            )
            raise ValueError(msg)
        return self


def _secret_or_none(value: SecretStr | None) -> str | None:
    if value is None:
        return None
    text = value.get_secret_value()
    return text if text else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
