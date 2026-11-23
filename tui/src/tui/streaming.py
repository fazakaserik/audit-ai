"""Stream ask responses into chat UI callbacks."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from rich.console import RenderableType

from backend.application.api.contracts.v1.responses import AskResponse
from backend.domain.engagement import EngagementId
from cli.ask_stream import AskStreamHandlers, consume_ask_stream
from cli.client import AuditApiClient, CliApiError
from cli.formatting.tool_progress import ToolProgressCorrelator
from tui.chat_render import ask_response_renderable
from tui.state import AppState


@dataclass(frozen=True)
class ThinkingStarted:
    """Open an expanded Thought process collapsible and stream into it."""


@dataclass(frozen=True)
class ThinkingAppend:
    """Append text (tool lines or thought deltas) into the live collapsible."""

    text: str


@dataclass(frozen=True)
class ThinkingFinished:
    """Collapse the live section and set the final duration title."""

    duration_seconds: float


@dataclass
class _WorkPhase:
    """Track wall-clock for the tools + thinking phase."""

    started_at: float = field(default_factory=time.monotonic)
    opened: bool = False
    saw_content: bool = False

    def duration_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)


def run_ask_stream(
    client: AuditApiClient,
    state: AppState,
    *,
    engagement_id: EngagementId,
    question: str,
    session_id: UUID | None,
    write: Callable[[RenderableType | ThinkingStarted | ThinkingAppend | ThinkingFinished], None],
) -> AskResponse | None:
    """Blocking stream consumer for use inside a Textual worker thread."""
    tools = ToolProgressCorrelator()
    phase: _WorkPhase | None = None
    need_tool_gap = False

    def ensure_phase() -> _WorkPhase:
        nonlocal phase
        if phase is None:
            phase = _WorkPhase()
        if not phase.opened:
            write(ThinkingStarted())
            phase.opened = True
        return phase

    def append(text: str) -> None:
        nonlocal need_tool_gap
        work = ensure_phase()
        work.saw_content = True
        write(ThinkingAppend(text=text))
        need_tool_gap = False

    def close_phase() -> None:
        nonlocal phase, need_tool_gap
        if phase is None:
            return
        write(ThinkingFinished(duration_seconds=phase.duration_seconds()))
        phase = None
        need_tool_gap = False

    def on_work_stage() -> None:
        ensure_phase()

    def on_tool_call(line: str) -> None:
        nonlocal need_tool_gap
        ensure_phase()
        if need_tool_gap:
            append("\n")
        append(line + "\n")

    def on_tool_result_lines(lines: list[str]) -> None:
        nonlocal need_tool_gap
        ensure_phase()
        for line in lines:
            append(line + "\n")
        need_tool_gap = True

    def on_thinking_delta(text: str) -> None:
        nonlocal need_tool_gap
        if need_tool_gap:
            append("\n")
            need_tool_gap = False
        append(text)

    def on_thinking_done(_duration: float) -> None:
        nonlocal need_tool_gap
        ensure_phase()
        need_tool_gap = True

    handlers = AskStreamHandlers(
        on_work_stage=on_work_stage,
        on_tool_call=on_tool_call,
        on_tool_result_lines=on_tool_result_lines,
        on_thinking_delta=on_thinking_delta,
        on_thinking_done=on_thinking_done,
        on_before_final=close_phase,
    )

    try:
        response = consume_ask_stream(
            client.ask_stream(
                engagement_id,
                question=question,
                session_id=session_id,
            ),
            handlers=handlers,
            tools=tools,
        )
    except CliApiError:
        raise

    if response is None:
        return None

    state.session_id = response.session_id
    state.last_answer = response
    state.last_citations = state.collect_citations(response)
    state.apply_usage_from_answer(response)
    write(ask_response_renderable(response))
    return response
