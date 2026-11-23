"""Unit tests for TUI status / header chrome formatting."""

from __future__ import annotations

from uuid import uuid4

from backend.application.api.contracts.v1.responses import (
    AnsweredResponse,
    CitationResponse,
    LlmUsageResponse,
)
from backend.domain.common import RequestId
from tui.state import (
    AppState,
    format_compact_header,
    format_status_bar,
    format_token_count,
    format_token_stats,
)


def test_format_token_count_empty_and_thousands() -> None:
    assert format_token_count(None) == "—"
    assert format_token_count(0) == "0"
    assert format_token_count(12410) == "12,410"


def test_token_stats_and_chrome_labels() -> None:
    state = AppState()
    assert format_token_stats(state) == "ctx — · last — · session —"
    assert "no engagement" in format_compact_header(state)
    assert "new session" in format_status_bar(state)

    state.set_engagement("northwind-fy2025", "Northwind FY2025")
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
    state.session_id = response.session_id
    state.session_title = "Payment terms"
    state.apply_usage_from_answer(response)

    tokens = format_token_stats(state)
    assert tokens == "ctx 100 · last 120 · session 250"

    header = format_compact_header(state)
    assert "Northwind FY2025" in header
    assert "ctx 100" in header
    assert "last 120" in header
    assert "session 250" in header

    bottom = format_status_bar(state)
    assert "Payment terms" in bottom
    assert "ctx 100" in bottom
    assert "last 120" in bottom
    assert "session 250" in bottom
