"""Unit tests for structured payload extraction (thinking fallback)."""

from __future__ import annotations

import pytest

from backend.domain.errors import ModelUnavailableError
from backend.infrastructure.llm.json_extract import extract_json_text


def test_extract_prefers_content() -> None:
    text = extract_json_text(
        content='{"can_answer": true, "answer_text": "ok", "markers_used": [1]}',
        thinking='{"can_answer": false}',
    )
    assert '"can_answer": true' in text


def test_extract_falls_back_to_thinking_json() -> None:
    text = extract_json_text(
        content="",
        thinking='{"can_answer": false, "answer_text": "", "markers_used": []}',
    )
    assert '"can_answer": false' in text


def test_extract_json_embedded_in_thinking_prose() -> None:
    thinking = (
        "Reasoning steps...\n"
        'Final: {"can_answer": true, "answer_text": "Meal limit is 75 USD [1]", '
        '"markers_used": [1]}\n'
        "done"
    )
    text = extract_json_text(content=None, thinking=thinking)
    assert '"answer_text"' in text


def test_extract_prefers_last_json_object_in_prose() -> None:
    thinking = (
        'Earlier draft {"can_answer": false, "answer_text": ""}\n'
        'Final {"can_answer": true, "answer_text": "ok", "markers_used": [1]}'
    )
    text = extract_json_text(content=None, thinking=thinking)
    assert '"can_answer": true' in text


def test_extract_raises_when_no_json() -> None:
    with pytest.raises(ModelUnavailableError, match="empty content"):
        extract_json_text(content="", thinking="no json here")
