"""Unit tests for REPL token toolbar formatting."""

from __future__ import annotations

from uuid import uuid4

from backend.application.api.contracts.v1.responses import (
    AnsweredResponse,
    CitationResponse,
    LlmUsageResponse,
)
from backend.domain.common import RequestId
from cli.repl import ReplState, _format_token_count, _token_toolbar


def test_format_token_count_empty_and_thousands() -> None:
    assert _format_token_count(None) == "—"
    assert _format_token_count(0) == "0"
    assert _format_token_count(12410) == "12,410"


def test_token_toolbar_placeholder_then_populated() -> None:
    state = ReplState()
    empty = str(_token_toolbar(state))
    assert "ctx" in empty
    assert "—" in empty

    response = AnsweredResponse(
        status="answered",
        answer="ok [1]",
        citations=(
            CitationResponse(
                marker=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_path="docs/a.md",
                page=1,
                heading_path=(),
                snippet="snippet",
                score=0.9,
            ),
        ),
        session_id=uuid4(),
        turn_id=uuid4(),
        request_id=RequestId(uuid4()),
        usage=LlmUsageResponse(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        session_total_tokens=250,
    )
    state.apply_usage_from_answer(response)
    filled = str(_token_toolbar(state))
    assert "100" in filled
    assert "120" in filled
    assert "250" in filled
