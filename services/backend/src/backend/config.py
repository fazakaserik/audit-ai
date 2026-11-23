"""Application settings (flat environment variables)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.domain.providers import LlmProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    llm_provider: LlmProvider = LlmProvider.OLLAMA
    llm_model: str = "qwen3.5:4b"
    embedding_provider: LlmProvider = LlmProvider.OLLAMA
    embedding_model: str = "nomic-embed-text"

    openai_api_key: SecretStr | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"

    database_url: str = "postgresql+asyncpg://audit:audit@localhost:5432/audit"
    document_storage_path: Path = Path("./data/storage")

    model_timeout_seconds: float = Field(default=120.0, gt=0)
    retrieval_top_k: int = Field(default=8, ge=1, le=50)
    relevance_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    max_concurrent_model_calls: int = Field(default=2, ge=1, le=64)
    agent_max_tool_rounds: int = Field(default=6, ge=1, le=20)
    agent_read_max_chars: int = Field(default=12_000, ge=500, le=200_000)

    upload_max_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    upload_max_files: int = Field(default=200, ge=1)
    upload_max_file_bytes: int = Field(default=20 * 1024 * 1024, ge=1)

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    enable_api_docs: bool = False

    log_level: str = "INFO"
    log_json: bool = True

    @model_validator(mode="after")
    def require_openai_key_when_needed(self) -> Settings:
        needs_openai = (
            self.llm_provider == LlmProvider.OPENAI or self.embedding_provider == LlmProvider.OPENAI
        )
        if needs_openai and (
            self.openai_api_key is None or not self.openai_api_key.get_secret_value()
        ):
            msg = "OPENAI_API_KEY is required when LLM_PROVIDER or EMBEDDING_PROVIDER is openai"
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
