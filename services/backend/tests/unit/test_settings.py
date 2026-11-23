"""Settings validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import Settings
from backend.domain.providers import LlmProvider


def test_openai_without_key_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider=LlmProvider.OPENAI, openai_api_key=None)
