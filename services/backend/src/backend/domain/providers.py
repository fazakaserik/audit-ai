"""LLM provider identifiers (config surface, not a feature entity)."""

from __future__ import annotations

from enum import StrEnum


class LlmProvider(StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
