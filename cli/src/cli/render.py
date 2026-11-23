"""Rich rendering for CLI output."""

from __future__ import annotations

import json
import re
from typing import Literal, assert_never

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.application.api.contracts.v1.responses import (
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

_TOOL_LABELS: dict[str, str] = {
    "search_relevant_chunks": "Search",
    "read_document": "Read",
    "list_documents": "List",
}
_TOOL_DETAIL_MAX = 72
_SOURCE_PATHS_MAX = 5
_RESULT_ARROW_RE = re.compile(r"^.*→\s*")


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
    uncertainties: tuple[str, ...] = (),
) -> None:
    _ = uncertainties  # kept on the API; questions carry the asks shown to the user
    console.print(
        "I have insufficient information to answer confidently. "
        "Please answer my question below to proceed."
    )
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


_STAGE_LABELS: dict[str, str] = {
    "agent": "Agent thinking…",
    "tool": "Running tools…",
    "generate": "Generate answer…",
    "suggest": "Suggest client questions…",
    "finalize": "Finalize answer…",
    "condense": "Condense question…",
    "retrieve": "Retrieve chunks…",
    "grade": "Grade evidence…",
}


def stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, stage)


def render_progress_stage(console: Console, stage: str) -> None:
    console.print(Text(stage_label(stage), style="dim"))


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    return text[: max_len - 1].rstrip() + "…"


def _parse_tool_args(arguments: str) -> dict[str, object]:
    raw = arguments.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_detail(name: str, arguments: str) -> str:
    args = _parse_tool_args(arguments)
    if name == "search_relevant_chunks":
        query = args.get("query")
        if isinstance(query, str) and query.strip():
            return f"“{_truncate(query.strip(), _TOOL_DETAIL_MAX)}”"
    elif name == "read_document":
        path = args.get("path")
        if isinstance(path, str) and path.strip():
            return _truncate(path.strip(), _TOOL_DETAIL_MAX)
    elif name == "list_documents":
        prefix = args.get("prefix")
        if isinstance(prefix, str) and prefix.strip():
            return _truncate(prefix.strip(), _TOOL_DETAIL_MAX)
        return "/"
    if args:
        compact = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
        return _truncate(compact, _TOOL_DETAIL_MAX)
    stripped = arguments.strip()
    return _truncate(stripped, _TOOL_DETAIL_MAX) if stripped else ""


def _dedupe_sources_by_path(
    sources: list[dict[str, object]],
) -> list[tuple[str, float | None]]:
    best: dict[str, float | None] = {}
    order: list[str] = []
    for item in sources:
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        score_raw = item.get("score")
        score: float | None = float(score_raw) if isinstance(score_raw, (int, float)) else None
        if path not in best:
            order.append(path)
            best[path] = score
            continue
        previous = best[path]
        if score is not None and (previous is None or score > previous):
            best[path] = score
    ranked = [(path, best[path]) for path in order]
    ranked.sort(
        key=lambda row: (-row[1] if row[1] is not None else float("inf"), row[0]),
    )
    return ranked


def _short_tool_result(name: str, summary: str) -> str:
    text = summary.strip()
    if not text:
        return ""
    if text.startswith(name):
        text = _RESULT_ARROW_RE.sub("", text).strip()
    elif "→" in text:
        text = text.split("→", 1)[1].strip()
    return text


class ToolProgressView:
    """Correlate tool_call → sources → tool_result into one compact tree."""

    def __init__(self) -> None:
        self._pending_sources: list[dict[str, object]] = []

    def on_tool_call(self, console: Console, *, name: str, arguments: str) -> None:
        self._pending_sources = []
        label = _TOOL_LABELS.get(name, name)
        detail = _tool_detail(name, arguments)
        line = f"▸ {label}" if not detail else f"▸ {label}  {detail}"
        console.print(Text(line, style="dim"))

    def on_sources(self, sources: list[dict[str, object]]) -> None:
        self._pending_sources = list(sources)

    def on_tool_result(self, console: Console, *, name: str, summary: str) -> None:
        sources = self._pending_sources
        self._pending_sources = []
        if sources:
            unique = _dedupe_sources_by_path(sources)
            hits = len(sources)
            docs = len(unique)
            console.print(Text(f"  {hits} hits · {docs} docs", style="dim"))
            shown = unique[:_SOURCE_PATHS_MAX]
            for path, score in shown:
                if score is None:
                    console.print(Text(f"  · {path}", style="dim"))
                else:
                    console.print(Text(f"  · {path}  {score:.2f}", style="dim"))
            remaining = len(unique) - len(shown)
            if remaining > 0:
                console.print(Text(f"  · +{remaining} more", style="dim"))
            return
        short = _short_tool_result(name, summary)
        if short:
            console.print(Text(f"  {short}", style="dim"))


def render_progress_sources(console: Console, sources: list[dict[str, object]]) -> None:
    """Legacy one-shot source dump; prefer ToolProgressView during ask streams."""
    if not sources:
        console.print(Text("  (no sources)", style="dim"))
        return
    unique = _dedupe_sources_by_path(sources)
    shown = unique[:_SOURCE_PATHS_MAX]
    for path, score in shown:
        if score is None:
            console.print(Text(f"  · {path}", style="dim"))
        else:
            console.print(Text(f"  · {path}  {score:.2f}", style="dim"))
    remaining = len(unique) - len(shown)
    if remaining > 0:
        console.print(Text(f"  · +{remaining} more", style="dim"))


def render_progress_tool_call(console: Console, *, name: str, arguments: str) -> None:
    ToolProgressView().on_tool_call(console, name=name, arguments=arguments)


def render_progress_tool_result(console: Console, *, name: str, summary: str) -> None:
    ToolProgressView().on_tool_result(console, name=name, summary=summary)


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
