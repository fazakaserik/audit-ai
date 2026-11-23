"""Rich renderables for the chat log (TUI-owned; not CLI stdout)."""

from __future__ import annotations

from typing import Literal, Protocol, assert_never

from rich.console import RenderableType
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
from tui.render_text import markdown_to_text

ToolProgressBuffer = ToolProgressCorrelator


def speaker_label(role: Literal["you", "agent"]) -> Text:
    match role:
        case "you":
            return Text("You", style="bold cyan")
        case "agent":
            return Text("Agent", style="bold green")
        case _:
            assert_never(role)


def error_panel(error: CliApiError) -> Text:
    body = Text()
    body.append("API error\n", style="bold red")
    body.append("\n".join(format_error_lines(error)), style="red")
    return body


def citations_text(citations: tuple[CitationResponse, ...]) -> Text | None:
    if not citations:
        return None
    body = Text()
    body.append("Citations\n", style="bold cyan")
    for index, citation in enumerate(citations):
        if index:
            body.append("\n\n")
        body.append_text(format_citation_line(citation))
    return body


def insufficient_text(
    *,
    questions: tuple[SuggestedClientQuestionResponse, ...],
) -> Text:
    body = Text(INSUFFICIENT_ANSWER_LEAD)
    if questions:
        body.append("\n")
        for index, item in enumerate(questions, start=1):
            body.append(f"\nQ{index}: {item.question}")
    return body


def ask_response_renderable(response: AskResponse) -> Text:
    """Answer body as Text so the TUI mouse-selection offsets work."""
    answered = unwrap_answer(response)
    if answered is not None:
        body = markdown_to_text(answered.answer)
        citations = citations_text(answered.citations)
        if citations is not None:
            body.append("\n\n")
            body.append_text(citations)
        return body

    insufficient = unwrap_insufficient(response)
    if insufficient is not None:
        body = insufficient_text(questions=insufficient.suggested_client_questions)
        citations = citations_text(insufficient.partial_citations)
        if citations is not None:
            body.append("\n\n")
            body.append_text(citations)
        return body

    return Text("(empty response)", style="dim")


def document_body_text(content: bytes) -> Text:
    """Decode document bytes into selectable Text (markdown when it looks like MD)."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return Text(f"(binary content, {len(content)} bytes)", style="dim")
    if text.strip().startswith(("#", "-", "*")) or "\n##" in text:
        return markdown_to_text(text)
    return Text(text)


def document_bytes_renderable(document_path: str, content: bytes) -> Text:
    header = Text(f"Document: {document_path}\n", style="bold")
    header.append_text(document_body_text(content))
    return header


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
