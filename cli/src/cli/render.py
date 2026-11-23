"""Rich rendering for CLI output."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, assert_never

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.application.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    DocumentListingResponse,
    EngagementResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SuggestedClientQuestionResponse,
    TurnResponse,
    UploadItemResponse,
    UploadResponse,
    UploadSummaryResponse,
)
from backend.domain.upload import UploadItemStatus, UploadStatus
from cli.client import CliApiError, unwrap_answer, unwrap_insufficient
from cli.formatting.citations import format_citation_line
from cli.formatting.copy import INSUFFICIENT_ANSWER_LEAD, NO_SAVED_THOUGHT_PROCESS
from cli.formatting.duration import format_duration_ms, format_elapsed
from cli.formatting.errors import format_error_lines
from cli.formatting.labels import stage_label
from cli.formatting.tool_progress import ToolProgressCorrelator
from cli.formatting.tools import source_progress_lines

_UPLOAD_STATUS_STYLE: dict[UploadStatus, str] = {
    UploadStatus.QUEUED: "cyan",
    UploadStatus.PROCESSING: "yellow",
    UploadStatus.COMPLETED: "green",
    UploadStatus.FAILED: "red",
}

_ITEM_STATUS_STYLE: dict[UploadItemStatus, str] = {
    UploadItemStatus.PENDING: "cyan",
    UploadItemStatus.PROCESSING: "yellow",
    UploadItemStatus.INDEXED: "green",
    UploadItemStatus.SKIPPED: "dim",
    UploadItemStatus.NOT_SEARCHABLE: "magenta",
    UploadItemStatus.FAILED: "red",
}


def upload_status_text(status: UploadStatus, *, spinner: str | None = None) -> Text:
    label = status.value
    if spinner and status in (UploadStatus.QUEUED, UploadStatus.PROCESSING):
        label = f"{spinner} {label}"
    return Text(label, style=_UPLOAD_STATUS_STYLE.get(status, ""))


def item_status_text(status: UploadItemStatus, *, spinner: str | None = None) -> Text:
    label = status.value
    if spinner and status in (UploadItemStatus.PENDING, UploadItemStatus.PROCESSING):
        label = f"{spinner} {label}"
    return Text(label, style=_ITEM_STATUS_STYLE.get(status, ""))


def _tokens_cell(item: UploadItemResponse) -> str:
    if item.embedding_total_tokens is None:
        return "—"
    return f"{item.embedding_total_tokens:,}"


def _chunks_cell(item: UploadItemResponse) -> str:
    if item.chunk_count is None:
        return "—"
    if item.chunk_token_sum is None:
        return str(item.chunk_count)
    return f"{item.chunk_count} ({item.chunk_token_sum:,} tok)"


def _item_duration_cell(item: UploadItemResponse, *, now: datetime | None) -> str:
    if item.processing_duration_ms is not None:
        return format_duration_ms(item.processing_duration_ms)
    if item.status in (UploadItemStatus.PENDING, UploadItemStatus.PROCESSING):
        return format_elapsed(item.processing_started_at, None, now=now)
    return "—"


def render_error(console: Console, error: CliApiError) -> None:
    console.print(
        Panel("\n".join(format_error_lines(error)), title="API error", border_style="red")
    )


def render_citations(console: Console, citations: tuple[CitationResponse, ...]) -> None:
    if not citations:
        return
    body = Text()
    for index, citation in enumerate(citations):
        if index:
            body.append("\n\n")
        body.append_text(format_citation_line(citation))
    console.print(Panel(body, title="Citations", border_style="cyan"))


def render_insufficient(
    console: Console,
    *,
    questions: tuple[SuggestedClientQuestionResponse, ...],
    uncertainties: tuple[str, ...] = (),
) -> None:
    _ = uncertainties  # kept on the API; questions carry the asks shown to the user
    console.print(INSUFFICIENT_ANSWER_LEAD)
    if not questions:
        return
    console.print()
    for index, item in enumerate(questions, start=1):
        console.print(f"Q{index}: {item.question}")


def render_speaker(console: Console, role: Literal["you", "agent"]) -> None:
    """Print a blank line then a bold colored speaker label."""
    console.print()
    match role:
        case "you":
            console.print(Text("You", style="bold cyan"))
        case "agent":
            console.print(Text("Agent", style="bold green"))
        case _:
            assert_never(role)


def render_user_message(console: Console, question: str) -> None:
    render_speaker(console, "you")
    console.print(question)


def render_progress_stage(console: Console, stage: str) -> None:
    console.print(Text(stage_label(stage), style="dim"))


class ToolProgressView:
    """CLI wrapper: print tool progress lines via Rich Console."""

    def __init__(self) -> None:
        self._correlator = ToolProgressCorrelator()

    def on_tool_call(self, console: Console, *, name: str, arguments: str) -> None:
        console.print(self._correlator.on_tool_call(name=name, arguments=arguments))

    def on_sources(self, sources: list[dict[str, object]]) -> None:
        self._correlator.on_sources(sources)

    def on_tool_result(self, console: Console, *, name: str, summary: str) -> None:
        for line in self._correlator.on_tool_result(name=name, summary=summary):
            console.print(line)


def render_progress_sources(console: Console, sources: list[dict[str, object]]) -> None:
    """Legacy one-shot source dump; prefer ToolProgressView during ask streams."""
    for line in source_progress_lines(sources):
        console.print(Text(line, style="dim"))


def render_thinking_delta(console: Console, text: str, *, at_line_start: bool) -> bool:
    """Print dim thinking text. Returns next at_line_start."""
    if not text:
        return at_line_start
    console.print(Text(text, style="dim"), end="")
    return text.endswith("\n")


def render_thinking_done(console: Console, duration_seconds: float) -> None:
    console.print()
    console.print(Text(f"Thought for {duration_seconds:.1f} seconds", style="dim"))


def render_persisted_thinking(
    console: Console,
    *,
    thinking_text: str | None,
    thinking_seconds: float | None,
) -> None:
    """Replay stored thinking as a stable dim block (not streamed end='')."""
    if not thinking_text and not thinking_seconds:
        return
    console.print(Text("Thought process", style="dim bold"))
    if thinking_text:
        console.print(Text(thinking_text, style="dim"))
    if thinking_seconds is not None and thinking_seconds > 0:
        console.print(Text(f"Thought for {thinking_seconds:.1f} seconds", style="dim"))


def render_ask_response(console: Console, response: AskResponse) -> None:
    answered = unwrap_answer(response)
    if answered is not None:
        console.print(Markdown(answered.answer))
        render_citations(console, answered.citations)
        return

    insufficient = unwrap_insufficient(response)
    if insufficient is not None:
        render_insufficient(
            console,
            questions=insufficient.suggested_client_questions,
            uncertainties=insufficient.uncertainties,
        )
        if insufficient.partial_citations:
            render_citations(console, insufficient.partial_citations)


def render_agent_message(
    console: Console,
    response: AskResponse,
    *,
    thinking_text: str | None = None,
    thinking_seconds: float | None = None,
) -> None:
    render_speaker(console, "agent")
    render_persisted_thinking(
        console,
        thinking_text=thinking_text,
        thinking_seconds=thinking_seconds,
    )
    render_ask_response(console, response)


def render_engagements(console: Console, engagements: tuple[EngagementResponse, ...]) -> None:
    table = Table(title="Engagements")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Documents", justify="right")
    table.add_column("Updated")
    for item in engagements:
        table.add_row(
            str(item.id),
            item.name,
            str(item.document_count),
            item.updated_at.isoformat(),
        )
    console.print(table)


def render_engagement(console: Console, engagement: EngagementResponse) -> None:
    console.print(
        Text(
            f"{engagement.id} — {engagement.name} ({engagement.document_count} docs)",
            style="bold",
        )
    )
    console.print(Text(f"created_at: {engagement.created_at.isoformat()}", style="dim"))
    console.print(Text(f"updated_at: {engagement.updated_at.isoformat()}", style="dim"))


def render_document_listing(
    console: Console,
    listing: DocumentListingResponse,
    *,
    prefix: str,
) -> None:
    location = prefix if prefix else "/"
    table = Table(title=f"Documents — {location}")
    table.add_column("Path", style="cyan")
    table.add_column("Type")
    table.add_column("Bytes", justify="right")
    table.add_column("Searchable")
    for folder in listing.folders:
        # Text: literal brackets; a bare "[name]" string is Rich markup and vanishes.
        table.add_row(Text(f"[{folder}]"), "folder", "", "")
    for item in listing.items:
        table.add_row(
            item.path,
            item.content_type.value,
            str(item.size_bytes),
            "yes" if item.searchable else "no",
        )
    console.print(table)
    console.print(
        Text(
            f"total documents: {listing.total} (showing {len(listing.items)})",
            style="dim",
        )
    )


def render_upload_summaries(
    console: Console,
    uploads: tuple[UploadSummaryResponse, ...],
) -> None:
    table = Table(title="Uploads")
    table.add_column("Status")
    table.add_column("Folder")
    table.add_column("Created")
    table.add_column("Duration", justify="right")
    table.add_column("Upload ID", style="cyan")
    for item in uploads:
        duration = format_elapsed(item.created_at, item.completed_at)
        table.add_row(
            upload_status_text(item.status),
            item.target_folder,
            item.created_at.isoformat(),
            duration,
            str(item.id),
        )
    console.print(table)


def render_session_summaries(
    console: Console,
    sessions: tuple[SessionSummaryResponse, ...],
) -> None:
    table = Table(title="Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Title")
    table.add_column("Turns", justify="right")
    table.add_column("Updated")
    for item in sessions:
        table.add_row(
            str(item.id),
            item.title,
            str(item.turn_count),
            item.updated_at.isoformat(),
        )
    console.print(table)


def render_session_detail(console: Console, session: SessionDetailResponse) -> None:
    console.print(
        Text(f"Session {session.id} — {session.title} ({session.turn_count} turns)", style="bold")
    )
    if session.turns and not any(
        turn.thinking_text or (turn.thinking_seconds is not None and turn.thinking_seconds > 0)
        for turn in session.turns
    ):
        console.print(Text(NO_SAVED_THOUGHT_PROCESS, style="dim italic"))
    for turn in session.turns:
        render_turn(console, turn)


def render_turn(console: Console, turn: TurnResponse) -> None:
    render_user_message(console, turn.question)
    render_agent_message(
        console,
        turn.answer,
        thinking_text=turn.thinking_text,
        thinking_seconds=turn.thinking_seconds,
    )


def upload_status_renderable(
    upload: UploadResponse,
    *,
    spinner: str | None = None,
    now: datetime | None = None,
) -> RenderableType:
    header = Text()
    header.append("Upload ", style="bold")
    header.append(str(upload.id), style="bold cyan")
    header.append(" — ", style="bold")
    header.append_text(upload_status_text(upload.status, spinner=spinner))
    header.append(f"  (folder: {upload.target_folder})", style="bold")

    parts: list[RenderableType] = [header]
    wall = format_elapsed(upload.created_at, upload.completed_at, now=now)
    if upload.completed_at is not None:
        parts.append(
            Text(
                f"completed_at: {upload.completed_at.isoformat()}  ·  wall time: {wall}",
                style="dim",
            )
        )
    elif wall != "—":
        parts.append(Text(f"elapsed: {wall}", style="dim"))

    item_durations = [i.processing_duration_ms for i in upload.items if i.processing_duration_ms]
    item_tokens = [i.embedding_total_tokens for i in upload.items if i.embedding_total_tokens]
    summary_bits: list[str] = [f"{len(upload.items)} file(s)"]
    if item_durations:
        summary_bits.append(f"process time Σ {format_duration_ms(sum(item_durations))}")
    if item_tokens:
        summary_bits.append(f"embed tokens Σ {sum(item_tokens):,}")
    parts.append(Text(" · ".join(summary_bits), style="dim"))

    if upload.items:
        table = Table(title="Items", expand=True)
        table.add_column("Path", overflow="fold")
        table.add_column("Status")
        table.add_column("Duration", justify="right")
        table.add_column("Embed tokens", justify="right")
        table.add_column("Chunks", justify="right")
        table.add_column("Reason", overflow="fold")
        for item in upload.items:
            table.add_row(
                item.document_path,
                item_status_text(item.status, spinner=spinner),
                _item_duration_cell(item, now=now),
                _tokens_cell(item),
                _chunks_cell(item),
                item.reason or "",
            )
        parts.append(table)
    return Group(*parts)


def render_upload_status(console: Console, upload: UploadResponse) -> None:
    console.print(upload_status_renderable(upload))


def render_document_bytes(console: Console, document_path: str, content: bytes) -> None:
    console.print(Text(f"Document: {document_path}", style="bold"))
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        console.print(Text(f"(binary content, {len(content)} bytes)", style="dim"))
        return
    if text.strip().startswith(("#", "-", "*")) or "\n##" in text:
        console.print(Markdown(text))
    else:
        console.print(text)
