"""Offline CLI render helpers for dim stage/source lines."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

from rich.console import Console

from backend.api.contracts.v1.responses import TurnResponse
from cli.render import (
    render_persisted_thinking,
    render_progress_sources,
    render_progress_stage,
    render_thinking_delta,
    render_thinking_done,
    render_turn,
)


def test_render_progress_stage_and_sources_dim() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    render_progress_stage(console, "retrieve")
    render_progress_sources(
        console,
        [{"path": "policies/expense-policy.md", "score": 0.81}],
    )
    render_thinking_done(console, 20.4)
    text = buffer.getvalue()
    assert "Retrieve passages…" in text
    assert "Sources: policies/expense-policy.md (0.81)" in text
    thought_line = next(line for line in text.splitlines() if "Thought for" in line)
    assert thought_line.startswith(" ")
    assert thought_line.lstrip().startswith("Thought for 20.4 seconds")


def test_render_thinking_delta_tabs_each_line() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    at_start = render_thinking_delta(console, "line one\n", at_line_start=True)
    assert at_start is True
    render_thinking_delta(console, "line two", at_line_start=at_start)
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert all(line.startswith(" ") for line in lines)
    assert lines[0].lstrip() == "line one"
    assert lines[1].lstrip() == "line two"


def test_render_persisted_thinking_and_turn_replay() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    render_persisted_thinking(
        console,
        thinking_text="Checking policy…",
        thinking_seconds=2.5,
    )
    text = buffer.getvalue()
    assert "Thought process" in text
    assert "Checking policy…" in text
    thought_line = next(line for line in text.splitlines() if "Thought for" in line)
    assert thought_line.lstrip().startswith("Thought for 2.5 seconds")

    session_id = str(uuid4())
    turn_id = str(uuid4())
    payload = {
        "id": turn_id,
        "ordinal": 0,
        "question": "Are there meal limits?",
        "folder_scope": None,
        "auditor_role": None,
        "topic": None,
        "standalone_question": "Are there meal limits?",
        "answer": {
            "status": "answered",
            "answer": "Meal limit is 75 USD [1].",
            "citations": [
                {
                    "marker": 1,
                    "passage_id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "document_path": "policies/expense-policy.md",
                    "snippet": "USD 75 per day",
                    "score": 0.9,
                }
            ],
            "session_id": session_id,
            "turn_id": turn_id,
            "request_id": str(uuid4()),
        },
        "created_at": datetime.now(UTC).isoformat(),
        "thinking_text": "Checking policy…",
        "thinking_seconds": 2.5,
    }
    turn = TurnResponse.model_validate_json(json.dumps(payload))
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    render_turn(console, turn)
    replay = buffer.getvalue()
    assert "Are there meal limits?" in replay
    assert "Checking policy…" in replay
    assert "Thought for 2.5 seconds" in replay
    assert "Meal limit is 75 USD" in replay
