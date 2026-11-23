"""Rich renderables for the chat log (TUI-owned; not CLI stdout)."""

from __future__ import annotations

from typing import Literal, Protocol, assert_never

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from backend.application.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    SessionDetailResponse,
    SuggestedClientQuestionResponse,
    TurnResponse,
    UploadResponse,
)
from cli.client import CliApiError, unwrap_answer, unwrap_insufficient
from cli.formatting.citations import format_citation_line
from cli.formatting.copy import INSUFFICIENT_ANSWER_LEAD, NO_SAVED_THOUGHT_PROCESS
from cli.formatting.errors import format_error_lines
from cli.formatting.tool_progress import ToolProgressCorrelator
from cli.render import upload_status_renderable

ToolProgressBuffer = ToolProgressCorrelator


def speaker_label(role: Literal["you", "agent"]) -> Text:
    match role:
        case "you":
            return Text("You", style="bold cyan")
        case "agent":
            return Text("Agent", style="bold green")
        case _:
            assert_never(role)


def error_panel(error: CliApiError) -> Panel:
    return Panel("\n".join(format_error_lines(error)), title="API error", border_style="red")


def citations_panel(citations: tuple[CitationResponse, ...]) -> Panel | None:
    if not citations:
        return None
    body = Text()
    for index, citation in enumerate(citations):
        if index:
            body.append("\n\n")
        body.append_text(format_citation_line(citation))
    return Panel(body, title="Citations", border_style="cyan")


def insufficient_group(
    *,
    questions: tuple[SuggestedClientQuestionResponse, ...],
) -> Group:
    lines: list[Text | str] = [INSUFFICIENT_ANSWER_LEAD]
    if questions:
        lines.append("")
        for index, item in enumerate(questions, start=1):
            lines.append(f"Q{index}: {item.question}")
    return Group(*lines)


def ask_response_renderable(response: AskResponse) -> Group:
    answered = unwrap_answer(response)
    if answered is not None:
        parts: list[RenderableType] = [Markdown(answered.answer)]
        panel = citations_panel(answered.citations)
        if panel is not None:
            parts.append(panel)
        return Group(*parts)

    insufficient = unwrap_insufficient(response)
    if insufficient is not None:
        parts = [insufficient_group(questions=insufficient.suggested_client_questions)]
        if insufficient.partial_citations:
            panel = citations_panel(insufficient.partial_citations)
            if panel is not None:
                parts.append(panel)
        return Group(*parts)

    return Group(Text("(empty response)", style="dim"))


def document_bytes_renderable(document_path: str, content: bytes) -> Group:
    header = Text(f"Document: {document_path}", style="bold")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return Group(header, Text(f"(binary content, {len(content)} bytes)", style="dim"))
    if text.strip().startswith(("#", "-", "*")) or "\n##" in text:
        return Group(header, Markdown(text))
    return Group(header, text)


def upload_status_panel(upload: object) -> Panel:
    """Wrap shared upload renderable for chat log display."""
    if not isinstance(upload, UploadResponse):
        return Panel(str(upload), title="Upload", border_style="cyan")
    return Panel(upload_status_renderable(upload), title="Upload", border_style="cyan")


class SessionReplaySink(Protocol):
    def append_speaker(self, role: Literal["you", "agent"]) -> None: ...

    def mount_line(self, content: RenderableType) -> None: ...

    def mount_thinking(self, *, body: str, duration_seconds: float | None) -> None: ...


def _session_has_saved_thinking(detail: SessionDetailResponse) -> bool:
    return any(
        turn.thinking_text or (turn.thinking_seconds is not None and turn.thinking_seconds > 0)
        for turn in detail.turns
    )


def replay_session_detail(detail: SessionDetailResponse, sink: SessionReplaySink) -> None:
    """Single session replay path with collapsible thought-process widgets."""
    sink.mount_line(
        Text(
            f"Session {detail.id} — {detail.title} ({detail.turn_count} turns)",
            style="bold",
        )
    )
    if detail.turns and not _session_has_saved_thinking(detail):
        sink.mount_line(Text(NO_SAVED_THOUGHT_PROCESS, style="dim italic"))
    for turn in detail.turns:
        replay_turn(turn, sink)


def replay_turn(turn: TurnResponse, sink: SessionReplaySink) -> None:
    sink.append_speaker("you")
    sink.mount_line(turn.question)
    sink.append_speaker("agent")
    if turn.thinking_text or (turn.thinking_seconds is not None and turn.thinking_seconds > 0):
        sink.mount_thinking(
            body=turn.thinking_text or "(no details)",
            duration_seconds=turn.thinking_seconds,
        )
    sink.mount_line(ask_response_renderable(turn.answer))
