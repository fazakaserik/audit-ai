"""Offline CLI render helpers for dim stage/source lines."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

from rich.console import Console

from backend.application.api.contracts.v1.responses import TurnResponse
from cli.render import (
    ToolProgressView,
    render_persisted_thinking,
    render_progress_stage,
    render_thinking_delta,
    render_thinking_done,
    render_turn,
)


def test_tool_progress_view_search_tree() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    tools = ToolProgressView()
    render_progress_stage(console, "think")
    tools.on_tool_call(
        console,
        name="search_relevant_chunks",
        arguments=json.dumps(
            {
                "query": ("company pay beer orange juice cheese reimbursement expense policy"),
            }
        ),
    )
    tools.on_sources(
        [
            {"path": "policies/expense-policy.md", "score": 0.66},
            {"path": "policies/expense-policy.md", "score": 0.53},
            {"path": "contracts/contoso-msa.md", "score": 0.51},
            {"path": "contracts/contoso-msa.md", "score": 0.50},
            {"path": "finance/q1-summary.md", "score": 0.49},
            {"path": "contracts/contoso-msa.md", "score": 0.47},
            {"path": "policies/expense-policy.md", "score": 0.47},
            {"path": "policies/expense-policy.md", "score": 0.47},
        ]
    )
    tools.on_tool_result(
        console,
        name="search_relevant_chunks",
        summary="search_relevant_chunks(query='…') → 8 hits",
    )
    render_thinking_done(console, 20.4)
    text = buffer.getvalue()
    assert "Thinking…" in text
    assert "▸ Search" in text
    assert "company pay beer" in text
    assert "8 hits · 3 docs" in text
    assert "· policies/expense-policy.md  0.66" in text
    assert "· contracts/contoso-msa.md  0.51" in text
    assert "· finance/q1-summary.md  0.49" in text
    assert "Tool →" not in text
    assert "Tool ←" not in text
    assert "Sources:" not in text
    thought_line = next(line for line in text.splitlines() if "Thought for" in line)
    assert thought_line.startswith("Thought for 20.4 seconds")


def test_tool_progress_view_read_without_sources() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    tools = ToolProgressView()
    tools.on_tool_call(
        console,
        name="read_document",
        arguments='{"path":"policies/expense-policy.md"}',
    )
    tools.on_tool_result(
        console,
        name="read_document",
        summary="read_document(path='policies/expense-policy.md') → evidence[2]",
    )
    text = buffer.getvalue()
    assert "▸ Read  policies/expense-policy.md" in text
    assert "  evidence[2]" in text


def test_tool_progress_view_caps_extra_docs() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    tools = ToolProgressView()
    tools.on_tool_call(console, name="search_relevant_chunks", arguments='{"query":"x"}')
    tools.on_sources(
        [{"path": f"docs/file-{index}.md", "score": 1.0 - (index * 0.01)} for index in range(8)]
    )
    tools.on_tool_result(console, name="search_relevant_chunks", summary="→ 8 hits")
    text = buffer.getvalue()
    assert "8 hits · 8 docs" in text
    assert "· +3 more" in text


def test_render_thinking_delta_prints_plain_lines() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=80, color_system=None)
    at_start = render_thinking_delta(console, "line one\n", at_line_start=True)
    assert at_start is True
    render_thinking_delta(console, "line two", at_line_start=at_start)
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert lines[0] == "line one"
    assert lines[1] == "line two"


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
    assert thought_line.startswith("Thought for 2.5 seconds")

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
                    "chunk_id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "document_path": "policies/expense-policy.md",
                    "snippet": "USD 75 per day",
                    "score": 0.9,
                }
            ],
            "session_id": session_id,
            "turn_id": turn_id,
            "request_id": str(uuid4()),
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "session_total_tokens": 120,
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
