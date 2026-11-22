"""Offline CLI render helpers for dim stage/source lines."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from cli.render import (
    render_progress_sources,
    render_progress_stage,
    render_thinking_delta,
    render_thinking_done,
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
