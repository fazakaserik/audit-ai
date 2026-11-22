"""Rich rendering for CLI output."""

from __future__ import annotations

from typing import Literal, assert_never

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    DocumentListingResponse,
    DocumentResponse,
    EngagementResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SuggestedClientQuestionResponse,
    TurnResponse,
    UploadResponse,
    UploadSummaryResponse,
)
from cli.client import CliApiError, unwrap_answer, unwrap_insufficient


def render_error(console: Console, error: CliApiError) -> None:
    lines = [
        f"[bold red]Error[/bold red] ({error.status})",
        f"code: {error.code.value}",
        f"detail: {error.detail}",
    ]
    if error.request_id is not None:
        lines.append(f"request_id: {error.request_id}")
    console.print(Panel("\n".join(lines), title="API error", border_style="red"))


def _format_citation_line(citation: CitationResponse) -> Text:
    location = citation.document_path
    if citation.page is not None:
        location = f"{location} (p. {citation.page})"
    if citation.heading_path:
        location = f"{location} — {' / '.join(citation.heading_path)}"
    line = Text()
    line.append(f"[{citation.marker}] {location}\n", style="bold")
    line.append(citation.snippet, style="dim")
    return line


def render_citations(console: Console, citations: tuple[CitationResponse, ...]) -> None:
    if not citations:
        return
    body = Text()
    for index, citation in enumerate(citations):
        if index:
            body.append("\n\n")
        body.append_text(_format_citation_line(citation))
    console.print(Panel(body, title="Citations", border_style="cyan"))


def render_insufficient(
    console: Console,
    *,
    questions: tuple[SuggestedClientQuestionResponse, ...],
) -> None:
    console.print("I have insufficient information to answer confidently.")
    if not questions:
        return
    console.print()
    console.print("May I ask you to give me more details about:")
    for item in questions:
        console.print(f"- {item.question}")


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


_STAGE_LABELS: dict[str, str] = {
    "condense": "Condense question…",
    "retrieve": "Retrieve passages…",
    "grade": "Grade evidence…",
    "generate": "Generate answer…",
    "suggest": "Suggest client questions…",
    "finalize": "Finalize answer…",
}


def stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, stage)


def render_progress_stage(console: Console, stage: str) -> None:
    console.print(Text(stage_label(stage), style="dim"))


def render_progress_sources(console: Console, sources: list[dict[str, object]]) -> None:
    if not sources:
        console.print(Text("Sources: (none)", style="dim"))
        return
    parts: list[str] = []
    for item in sources:
        path = str(item.get("path", ""))
        score = item.get("score")
        if isinstance(score, (int, float)):
            parts.append(f"{path} ({score:.2f})")
        else:
            parts.append(path)
    console.print(Text("Sources: " + ", ".join(parts), style="dim"))


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
        )
        if insufficient.partial_citations:
            render_citations(console, insufficient.partial_citations)
        console.print(Text(f"session_id: {insufficient.session_id}", style="dim"))


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
        table.add_row(f"[{folder}]", "folder", "", "")
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


def render_documents(console: Console, documents: tuple[DocumentResponse, ...]) -> None:
    table = Table(title="Documents")
    table.add_column("Path", style="cyan")
    table.add_column("Type")
    table.add_column("Bytes", justify="right")
    for item in documents:
        table.add_row(item.path, item.content_type.value, str(item.size_bytes))
    console.print(table)


def render_upload_summaries(
    console: Console,
    uploads: tuple[UploadSummaryResponse, ...],
) -> None:
    table = Table(title="Uploads")
    table.add_column("Upload ID", style="cyan")
    table.add_column("Folder")
    table.add_column("Status")
    table.add_column("Created")
    for item in uploads:
        table.add_row(
            str(item.id),
            item.target_folder,
            item.status.value,
            item.created_at.isoformat(),
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
        console.print(
            Text(
                "No saved thought process in this session "
                "(only asks made after thinking-persist store it — ask again to capture).",
                style="dim italic",
            )
        )
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


def render_upload_status(console: Console, upload: UploadResponse) -> None:
    console.print(
        Text(
            f"Upload {upload.id} — {upload.status.value} (folder: {upload.target_folder})",
            style="bold",
        )
    )
    if upload.completed_at is not None:
        console.print(Text(f"completed_at: {upload.completed_at.isoformat()}", style="dim"))
    if not upload.items:
        return
    table = Table(title="Items")
    table.add_column("Path")
    table.add_column("Status")
    table.add_column("Reason")
    for item in upload.items:
        table.add_row(item.document_path, item.status.value, item.reason or "")
    console.print(table)


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
