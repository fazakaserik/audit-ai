"""Rich renderables for the chat log (TUI-owned; not CLI stdout)."""

from __future__ import annotations

import json
import re
from typing import Literal, assert_never, cast

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


def speaker_label(role: Literal["you", "agent"]) -> Text:
    match role:
        case "you":
            return Text("You", style="bold cyan")
        case "agent":
            return Text("Agent", style="bold green")
        case _:
            assert_never(role)


def error_panel(error: CliApiError) -> Panel:
    lines = [
        f"[bold red]Error[/bold red] ({error.status})",
        f"code: {error.code.value}",
        f"detail: {error.detail}",
    ]
    if error.request_id is not None:
        lines.append(f"request_id: {error.request_id}")
    return Panel("\n".join(lines), title="API error", border_style="red")


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


def citations_panel(citations: tuple[CitationResponse, ...]) -> Panel | None:
    if not citations:
        return None
    body = Text()
    for index, citation in enumerate(citations):
        if index:
            body.append("\n\n")
        body.append_text(_format_citation_line(citation))
    return Panel(body, title="Citations", border_style="cyan")


def insufficient_group(
    *,
    questions: tuple[SuggestedClientQuestionResponse, ...],
) -> Group:
    lines: list[Text | str] = [
        (
            "I have insufficient information to answer confidently. "
            "Please answer my question below to proceed."
        )
    ]
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


def persisted_thinking(
    *,
    thinking_text: str | None,
    thinking_seconds: float | None,
) -> Group | None:
    if not thinking_text and not thinking_seconds:
        return None
    parts: list[Text] = [Text("Thought process", style="dim bold")]
    if thinking_text:
        parts.append(Text(thinking_text, style="dim"))
    if thinking_seconds is not None and thinking_seconds > 0:
        parts.append(Text(f"Thought for {thinking_seconds:.1f} seconds", style="dim"))
    return Group(*parts)


def turn_renderables(turn: TurnResponse) -> list[RenderableType]:
    items: list[RenderableType] = [
        speaker_label("you"),
        turn.question,
        speaker_label("agent"),
    ]
    thinking = persisted_thinking(
        thinking_text=turn.thinking_text,
        thinking_seconds=turn.thinking_seconds,
    )
    if thinking is not None:
        items.append(thinking)
    items.append(ask_response_renderable(turn.answer))
    return items


def session_replay_renderables(session: SessionDetailResponse) -> list[RenderableType]:
    items: list[RenderableType] = [
        Text(
            f"Session {session.id} — {session.title} ({session.turn_count} turns)",
            style="bold",
        )
    ]
    if session.turns and not any(
        turn.thinking_text or (turn.thinking_seconds is not None and turn.thinking_seconds > 0)
        for turn in session.turns
    ):
        items.append(
            Text(
                "No saved thought process in this session "
                "(only asks made after thinking-persist store it — ask again to capture).",
                style="dim italic",
            )
        )
    for turn in session.turns:
        items.extend(turn_renderables(turn))
    return items


def document_bytes_renderable(document_path: str, content: bytes) -> Group:
    header = Text(f"Document: {document_path}", style="bold")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return Group(header, Text(f"(binary content, {len(content)} bytes)", style="dim"))
    if text.strip().startswith(("#", "-", "*")) or "\n##" in text:
        return Group(header, Markdown(text))
    return Group(header, text)


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
        loaded = cast(object, json.loads(raw))
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, object], loaded)


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


class ToolProgressBuffer:
    """Correlate tool_call → sources → tool_result into compact Text lines."""

    def __init__(self) -> None:
        self._pending_sources: list[dict[str, object]] = []

    def on_tool_call(self, *, name: str, arguments: str) -> Text:
        self._pending_sources = []
        label = _TOOL_LABELS.get(name, name)
        detail = _tool_detail(name, arguments)
        line = f"▸ {label}" if not detail else f"▸ {label}  {detail}"
        return Text(line, style="dim")

    def on_sources(self, sources: list[dict[str, object]]) -> None:
        self._pending_sources = list(sources)

    def on_tool_result(self, *, name: str, summary: str) -> list[Text]:
        sources = self._pending_sources
        self._pending_sources = []
        lines: list[Text] = []
        if sources:
            unique = _dedupe_sources_by_path(sources)
            hits = len(sources)
            docs = len(unique)
            lines.append(Text(f"  {hits} hits · {docs} docs", style="dim"))
            shown = unique[:_SOURCE_PATHS_MAX]
            for path, score in shown:
                if score is None:
                    lines.append(Text(f"  · {path}", style="dim"))
                else:
                    lines.append(Text(f"  · {path}  {score:.2f}", style="dim"))
            remaining = len(unique) - len(shown)
            if remaining > 0:
                lines.append(Text(f"  · +{remaining} more", style="dim"))
            return lines
        short = _short_tool_result(name, summary)
        if short:
            lines.append(Text(f"  {short}", style="dim"))
        return lines
