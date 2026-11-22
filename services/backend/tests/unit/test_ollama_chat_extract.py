"""Unit tests for Ollama structured payload extraction (thinking fallback)."""

from __future__ import annotations

import pytest

from backend.adapters.ollama_chat import _extract_json_text
from domain.errors import ModelUnavailableError


def test_extract_prefers_content() -> None:
    text = _extract_json_text(
        content='{"sufficient": true, "answer_text": "ok", "markers_used": [1]}',
        thinking='{"sufficient": false}',
    )
    assert '"sufficient": true' in text


def test_extract_falls_back_to_thinking_json() -> None:
    text = _extract_json_text(
        content="",
        thinking='{"sufficient": false, "answer_text": "", "markers_used": []}',
    )
    assert '"sufficient": false' in text


def test_extract_json_embedded_in_thinking_prose() -> None:
    thinking = (
        "Reasoning steps...\n"
        'Final: {"sufficient": true, "answer_text": "Meal limit is 75 USD [1]", '
        '"markers_used": [1]}\n'
        "done"
    )
    text = _extract_json_text(content=None, thinking=thinking)
    assert '"answer_text"' in text


def test_extract_raises_when_no_json() -> None:
    with pytest.raises(ModelUnavailableError, match="empty content"):
        _extract_json_text(content="", thinking="no json here")
