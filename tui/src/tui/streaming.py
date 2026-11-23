"""Stream ask responses into chat UI callbacks."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, cast
from uuid import UUID

from rich.console import RenderableType

from backend.application.api.contracts.v1.responses import AskResponse
from backend.domain.engagement import EngagementId
from backend.domain.errors import ErrorCode
from cli.client import AuditApiClient, CliApiError
from tui.chat_render import ToolProgressBuffer, ask_response_renderable
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


class ChatSink(Protocol):
    def write(self, content: object) -> None: ...


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
    response: AskResponse | None = None
    tools = ToolProgressBuffer()
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

    try:
        for event in client.ask_stream(
            engagement_id,
            question=question,
            session_id=session_id,
        ):
            event_type = event.get("type")
            if event_type == "stage":
                stage = str(event.get("stage", ""))
                if stage in {"agent", "tool", "retrieve", "grade", "condense"}:
                    ensure_phase()
            elif event_type == "sources":
                sources = event.get("sources")
                if isinstance(sources, list):
                    typed_sources: list[dict[str, object]] = []
                    for raw_item in cast(list[object], sources):
                        if isinstance(raw_item, dict):
                            typed_sources.append(cast(dict[str, object], raw_item))
                    tools.on_sources(typed_sources)
            elif event_type == "tool_call":
                ensure_phase()
                # Separate tool block from prior thought text with a blank line.
                if need_tool_gap:
                    append("\n")
                name = str(event.get("name", "tool"))
                arguments = str(event.get("arguments", ""))
                line = tools.on_tool_call(name=name, arguments=arguments)
                append(line.plain + "\n")
            elif event_type == "tool_result":
                ensure_phase()
                name = str(event.get("name", "tool"))
                summary = str(event.get("summary", ""))
                for line in tools.on_tool_result(name=name, summary=summary):
                    append(line.plain + "\n")
                need_tool_gap = True
            elif event_type == "thinking_delta":
                text = event.get("text")
                if isinstance(text, str) and text:
                    if need_tool_gap:
                        append("\n")
                        need_tool_gap = False
                    append(text)
            elif event_type == "thinking_done":
                ensure_phase()
                need_tool_gap = True
            elif event_type == "final":
                close_phase()
                final = event.get("response")
                if isinstance(final, AskResponse):
                    response = final
                else:
                    raise CliApiError(
                        code=ErrorCode.INTERNAL_ERROR,
                        detail="stream final payload missing",
                        status=500,
                        request_id=None,
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
