"""Rich rendering for CLI output."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    EngagementResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SuggestedClientQuestionResponse,
    TurnResponse,
    UploadResponse,
)
from cli.client import CliApiError, unwrap_answer, unwrap_insufficient
from domain.answer import InsufficientReason


def render_error(console: Console, error: CliApiError) -> None:
    lines = [
        f"[bold red]Error[/bold red] ({error.status})",
        f"code: {error.code.value}",
        f"detail: {error.detail}",
    ]
    if error.request_id is not None:
        lines.append(f"request_id: {error.request_id}")
    console.print(Panel("\n".join(lines), title="API error", border_style="red"))


def _format_citation_line(citation: CitationResponse) -> str:
    location = citation.document_path
    if citation.page is not None:
        location = f"{location} (p. {citation.page})"
    if citation.heading_path:
        location = f"{location} — {' / '.join(citation.heading_path)}"
    return f"[{citation.marker}] {location}\n    {citation.snippet}"


def render_citations(console: Console, citations: tuple[CitationResponse, ...]) -> None:
    if not citations:
        return
    body = "\n\n".join(_format_citation_line(c) for c in citations)
    console.print(Panel(body, title="Citations", border_style="cyan"))


def _reason_label(reason: InsufficientReason) -> str:
    if reason is InsufficientReason.NO_RELEVANT_PASSAGES:
        return "No relevant passages were retrieved for this question."
    if reason is InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
        return "The model judged the retrieved evidence insufficient."
    msg = f"unexpected reason: {reason!r}"
    raise AssertionError(msg)


def render_suggestions(
    console: Console,
    questions: tuple[SuggestedClientQuestionResponse, ...],
) -> None:
    if not questions:
        return
    lines: list[str] = []
    for index, item in enumerate(questions, start=1):
        lines.append(f"{index}. {item.question}")
        lines.append(f"   {item.rationale}")
    console.print(Panel("\n".join(lines), title="Suggested client questions", border_style="yellow"))


def render_ask_response(console: Console, response: AskResponse) -> None:
    answered = unwrap_answer(response)
    if answered is not None:
        console.print(Markdown(answered.answer))
        render_citations(console, answered.citations)
        console.print(Text(f"session_id: {answered.session_id}", style="dim"))
        return

    insufficient = unwrap_insufficient(response)
    if insufficient is not None:
        console.print(
            Panel(
                _reason_label(insufficient.reason),
                title="Insufficient evidence",
                border_style="yellow",
            )
        )
        if insufficient.partial_citations:
            render_citations(console, insufficient.partial_citations)
        render_suggestions(console, insufficient.suggested_client_questions)
        console.print(Text(f"session_id: {insufficient.session_id}", style="dim"))


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
    for turn in session.turns:
        render_turn(console, turn)


def render_turn(console: Console, turn: TurnResponse) -> None:
    console.print(Text(f"\n— Turn {turn.ordinal + 1}: {turn.question}", style="bold blue"))
    render_ask_response(console, turn.answer)


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