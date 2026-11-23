"""Interactive REPL for audit-ai."""

from __future__ import annotations

import time
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx
import questionary
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.status import Status
from rich.text import Text

from backend.application.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    DocumentResponse,
    EngagementResponse,
    LlmUsageResponse,
    SessionSummaryResponse,
    UploadSummaryResponse,
)
from backend.domain.engagement import EngagementId
from backend.domain.errors import ErrorCode
from cli.client import AuditApiClient, CliApiError, unwrap_answer, unwrap_insufficient
from cli.render import (
    ToolProgressView,
    render_ask_response,
    render_document_bytes,
    render_error,
    render_progress_stage,
    render_session_detail,
    render_session_summaries,
    render_speaker,
    render_thinking_delta,
    render_thinking_done,
    render_upload_status,
    stage_label,
)

HELP_TEXT = """Slash commands:
  /engagement     Switch engagement (clears session)
  /new            Start a new session on the next question
  /sessions       List recent sessions
  /resume [id]    Resume a session (picker if no id)
  /documents [folder]  Browse documents (picker; optional start folder)
  /uploads [id]   List uploads or show one upload's details
  /upload <path> <folder>  Upload to the active engagement under <folder>
  /open <n>       Open citation [n] from the last answer
  /help           Show this help
  /quit           Exit
"""

_NEW_SESSION = object()
_PARENT_DIR = object()


class ReplState:
    def __init__(self) -> None:
        self.engagement_id: EngagementId | None = None
        self.session_id: UUID | None = None
        self.last_answer: AskResponse | None = None
        self.last_citations: tuple[CitationResponse, ...] = ()
        self.last_usage: LlmUsageResponse | None = None
        self.session_total_tokens: int = 0

    def clear_usage(self) -> None:
        self.last_usage = None
        self.session_total_tokens = 0

    def apply_usage_from_answer(self, response: AskResponse) -> None:
        self.last_usage = response.usage
        self.session_total_tokens = response.session_total_tokens


def _format_token_count(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def _token_toolbar(state: ReplState) -> HTML:
    usage = state.last_usage
    ctx = _format_token_count(usage.prompt_tokens if usage is not None else None)
    last = _format_token_count(usage.total_tokens if usage is not None else None)
    session = (
        _format_token_count(state.session_total_tokens)
        if usage is not None or state.session_total_tokens > 0
        else "—"
    )
    return HTML(
        f"<style bg='ansibrightblack' fg='ansiwhite'>"
        f" ctx <b>{ctx}</b> · last <b>{last}</b> · session <b>{session}</b> "
        f"</style>"
    )


def _collect_citations(response: AskResponse) -> tuple[CitationResponse, ...]:
    answered = unwrap_answer(response)
    if answered is not None:
        return answered.citations
    insufficient = unwrap_insufficient(response)
    if insufficient is not None:
        return insufficient.partial_citations
    return ()


def _select_choice(message: str, choices: list[questionary.Choice]) -> object | None:
    """Arrow-key radiolist. Returns None if cancelled (Ctrl+C / Esc)."""
    return questionary.select(message, choices=choices).ask()


def _engagement_label(item: EngagementResponse) -> str:
    return f"{item.name}  ({item.id})  [{item.document_count} docs]"


def _session_label(item: SessionSummaryResponse) -> str:
    # Put updated_at first so the newest sessions are easy to spot in the picker.
    stamp = item.updated_at.strftime("%Y-%m-%d %H:%M")
    return f"[{stamp}] {item.title}  ({item.turn_count} turns)  {item.id}"


def _select_engagement(client: AuditApiClient, console: Console) -> EngagementId:
    page = client.list_engagements(limit=200, offset=0)
    if not page.items:
        console.print("No engagements yet. Create one on the server, then restart /engagement.")
        raise SystemExit(1)
    choices = [
        questionary.Choice(title=_engagement_label(item), value=item.id) for item in page.items
    ]
    selected = _select_choice("Select engagement:", choices)
    if selected is None:
        raise SystemExit(0)
    return cast(EngagementId, selected)


def _load_session(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    state: ReplState,
    session_uuid: UUID,
) -> None:
    detail = client.get_session(engagement_id, session_uuid)
    state.session_id = detail.id
    if detail.turns:
        last = detail.turns[-1].answer
        state.last_answer = last
        state.last_citations = _collect_citations(last)
        state.apply_usage_from_answer(last)
    else:
        state.last_answer = None
        state.last_citations = ()
        state.clear_usage()
    render_session_detail(console, detail)


def _pick_initial_session(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    state: ReplState,
) -> None:
    page = client.list_sessions(engagement_id, limit=20, offset=0)
    if not page.items:
        console.print("No prior sessions — the first question will start a new one.")
        return

    choices: list[questionary.Choice] = [
        questionary.Choice(title="Start new session", value=_NEW_SESSION),
        *(questionary.Choice(title=_session_label(item), value=item.id) for item in page.items),
    ]
    selected = _select_choice("Resume or start new?", choices)
    if selected is None or selected is _NEW_SESSION:
        return
    _load_session(client, console, engagement_id, state, cast(UUID, selected))


def _resume_session_picker(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    state: ReplState,
) -> None:
    page = client.list_sessions(engagement_id, limit=50, offset=0)
    if not page.items:
        console.print("No sessions to resume.")
        return
    choices = [questionary.Choice(title=_session_label(item), value=item.id) for item in page.items]
    selected = _select_choice("Resume session:", choices)
    if selected is None:
        return
    _load_session(client, console, engagement_id, state, cast(UUID, selected))


def _find_citation(state: ReplState, marker: int) -> CitationResponse | None:
    for citation in state.last_citations:
        if citation.marker == marker:
            return citation
    return None


def _join_prefix(prefix: str, child: str) -> str:
    if not prefix:
        return child
    return f"{prefix.rstrip('/')}/{child}"


def _parent_prefix(prefix: str) -> str:
    if not prefix or "/" not in prefix:
        return ""
    return prefix.rsplit("/", 1)[0]


def _document_basename(path: str, prefix: str) -> str:
    if prefix and path.startswith(prefix.rstrip("/") + "/"):
        return path[len(prefix.rstrip("/")) + 1 :]
    return path.rsplit("/", 1)[-1]


def _browse_documents(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    start_folder: str,
) -> None:
    current = start_folder.strip().strip("/")
    while True:
        try:
            listing = client.list_documents(
                engagement_id,
                prefix=current or None,
                depth=1,
                limit=200,
                offset=0,
            )
        except CliApiError as exc:
            render_error(console, exc)
            return

        location = current if current else "/"
        choices: list[questionary.Choice] = []
        if current:
            choices.append(questionary.Choice(title="..", value=_PARENT_DIR))
        for folder in listing.folders:
            choices.append(questionary.Choice(title=f"[{folder}]", value=("dir", folder)))
        for doc in listing.items:
            name = _document_basename(doc.path, current)
            choices.append(
                questionary.Choice(
                    title=f"{name}  ({doc.size_bytes} bytes, {doc.content_type.value})",
                    value=("doc", doc),
                )
            )
        if not choices:
            console.print(f"[dim]No folders or documents under {location}.[/dim]")
            return

        selected = _select_choice(f"Browse {location}:", choices)
        if selected is None:
            return
        if selected is _PARENT_DIR:
            current = _parent_prefix(current)
            continue
        kind, payload = cast(tuple[str, str | DocumentResponse], selected)
        if kind == "dir":
            current = _join_prefix(current, cast(str, payload))
            continue
        document = cast(DocumentResponse, payload)
        try:
            content = client.get_document_content(engagement_id, document.path)
        except CliApiError as exc:
            render_error(console, exc)
            return
        render_document_bytes(console, document.path, content)
        return


def _upload_label(item: UploadSummaryResponse) -> str:
    return (
        f"{item.target_folder}  ({item.id})  [{item.status.value}, {item.created_at.isoformat()}]"
    )


def _show_upload_details(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    upload_id: UUID,
) -> None:
    try:
        detail = client.get_upload_status(engagement_id, upload_id)
    except CliApiError as exc:
        render_error(console, exc)
    else:
        render_upload_status(console, detail)


def _uploads_picker(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
) -> None:
    try:
        page = client.list_uploads(engagement_id, limit=50, offset=0)
    except CliApiError as exc:
        render_error(console, exc)
        return
    if not page.items:
        console.print("No uploads yet.")
        return
    choices = [questionary.Choice(title=_upload_label(item), value=item.id) for item in page.items]
    selected = _select_choice("Select upload:", choices)
    if selected is None:
        return
    _show_upload_details(client, console, engagement_id, cast(UUID, selected))


def _upload_to_engagement(
    client: AuditApiClient,
    console: Console,
    engagement_id: EngagementId,
    raw_path: str,
    folder: str,
) -> None:
    cleaned = raw_path.strip().strip("\"'")
    path = Path(cleaned).expanduser()
    try:
        with Status(f"Uploading {path}…", console=console):
            accepted = client.upload_path(engagement_id, path, folder=folder)
        console.print(f"Upload queued: {accepted.upload_id} → folder [cyan]{folder}[/cyan]")
        with Status("Waiting for upload…", console=console):
            final = client.wait_upload(engagement_id, accepted.upload_id)
    except CliApiError as exc:
        render_error(console, exc)
    except (FileNotFoundError, ValueError, OSError) as exc:
        console.print(f"[red]{exc}[/red]")
    else:
        render_upload_status(console, final)


def _handle_slash(
    line: str,
    *,
    client: AuditApiClient,
    console: Console,
    state: ReplState,
) -> bool:
    """Return False to exit REPL."""
    parts = line.split()
    command = parts[0].lower()
    args = parts[1:]
    remainder = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) == 2 else ""

    match command:
        case "/quit" | "/exit":
            return False
        case "/help":
            console.print(HELP_TEXT)
        case "/new":
            state.session_id = None
            state.clear_usage()
            console.print("Next question starts a new session.")
        case "/engagement":
            selected = _select_engagement(client, console)
            state.engagement_id = selected
            state.session_id = None
            state.last_answer = None
            state.last_citations = ()
            state.clear_usage()
            console.print(f"Active engagement: {state.engagement_id}")
        case "/sessions":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            else:
                page = client.list_sessions(state.engagement_id, limit=50, offset=0)
                render_session_summaries(console, page.items)
        case "/resume":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            elif len(args) == 0:
                _resume_session_picker(client, console, state.engagement_id, state)
            elif len(args) == 1:
                try:
                    session_uuid = UUID(args[0])
                except ValueError:
                    console.print("[red]Invalid session id.[/red]")
                else:
                    _load_session(client, console, state.engagement_id, state, session_uuid)
            else:
                console.print("[red]Usage: /resume [session_id][/red]")
        case "/documents":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            else:
                start_folder = remainder.strip().strip("\"'")
                _browse_documents(client, console, state.engagement_id, start_folder)
        case "/uploads":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            elif len(args) == 0:
                _uploads_picker(client, console, state.engagement_id)
            elif len(args) == 1:
                try:
                    upload_uuid = UUID(args[0])
                except ValueError:
                    console.print("[red]Invalid upload id.[/red]")
                else:
                    _show_upload_details(client, console, state.engagement_id, upload_uuid)
            else:
                console.print("[red]Usage: /uploads [upload_id][/red]")
        case "/upload":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            else:
                upload_parts = remainder.rsplit(maxsplit=1)
                if len(upload_parts) != 2 or not upload_parts[0] or not upload_parts[1]:
                    console.print("[red]Usage: /upload <path> <folder>[/red]")
                else:
                    raw_path, folder = upload_parts
                    _upload_to_engagement(client, console, state.engagement_id, raw_path, folder)
        case "/open":
            if state.engagement_id is None:
                console.print("[red]No engagement selected.[/red]")
            elif len(args) != 1 or not args[0].isdigit():
                console.print("[red]Usage: /open <citation marker n>[/red]")
            else:
                marker = int(args[0])
                citation = _find_citation(state, marker)
                if citation is None:
                    console.print(f"[red]No citation [{marker}] in the last answer.[/red]")
                else:
                    try:
                        content = client.get_document_content(
                            state.engagement_id, citation.document_path
                        )
                        render_document_bytes(console, citation.document_path, content)
                    except CliApiError as exc:
                        render_error(console, exc)
        case _:
            console.print(f"[red]Unknown command: {command}[/red]. Type /help.")
    return True


def _ask_question(
    client: AuditApiClient,
    console: Console,
    state: ReplState,
    question: str,
) -> None:
    if state.engagement_id is None:
        console.print("[red]No engagement selected.[/red]")
        return
    render_speaker(console, "agent")
    response: AskResponse | None = None
    thinking_at_line_start = True
    saw_thinking = False
    tools = ToolProgressView()
    status = Status("Thinking…", console=console)
    status.start()
    try:
        for event in client.ask_stream(
            state.engagement_id,
            question=question,
            session_id=state.session_id,
        ):
            event_type = event.get("type")
            if event_type == "stage":
                stage = str(event.get("stage", ""))
                status.stop()
                if saw_thinking and not thinking_at_line_start:
                    console.print()
                    thinking_at_line_start = True
                render_progress_stage(console, stage)
                if not saw_thinking:
                    status.update(stage_label(stage))
                    status.start()
            elif event_type == "sources":
                sources = event.get("sources")
                if isinstance(sources, list):
                    tools.on_sources([item for item in sources if isinstance(item, dict)])
            elif event_type == "tool_call":
                status.stop()
                name = str(event.get("name", "tool"))
                arguments = str(event.get("arguments", ""))
                tools.on_tool_call(console, name=name, arguments=arguments)
                if not saw_thinking:
                    status.start()
            elif event_type == "tool_result":
                status.stop()
                name = str(event.get("name", "tool"))
                summary = str(event.get("summary", ""))
                tools.on_tool_result(console, name=name, summary=summary)
                if not saw_thinking:
                    status.start()
            elif event_type == "thinking_delta":
                text = event.get("text")
                if isinstance(text, str) and text:
                    if not saw_thinking:
                        status.stop()
                        console.print()
                        console.print(Text("Thought process", style="dim bold"))
                        saw_thinking = True
                    thinking_at_line_start = render_thinking_delta(
                        console,
                        text,
                        at_line_start=thinking_at_line_start,
                    )
            elif event_type == "thinking_done":
                status.stop()
                raw = event.get("duration_seconds", 0)
                duration = float(raw) if isinstance(raw, (int, float, str)) else 0.0
                render_thinking_done(console, duration)
                thinking_at_line_start = True
            elif event_type == "final":
                status.stop()
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
    except CliApiError as exc:
        status.stop()
        render_error(console, exc)
        return
    finally:
        status.stop()
    if response is None:
        console.print("[red]No answer received from stream.[/red]")
        return
    state.session_id = _session_from_response(response)
    state.last_answer = response
    state.last_citations = _collect_citations(response)
    state.apply_usage_from_answer(response)
    render_ask_response(console, response)


def _session_from_response(response: AskResponse) -> UUID:
    return response.session_id


_CONNECT_BACKOFF_SECONDS = (1, 2, 3, 5, 10)


def _wait_for_api(client: AuditApiClient, console: Console) -> None:
    """Retry `/health/live` with backoff; exit cleanly if the API never comes up."""
    try:
        with Status("Connecting to API…", console=console) as status:
            for attempt, delay in enumerate((0, *_CONNECT_BACKOFF_SECONDS)):
                if delay:
                    status.update("Connecting...")
                    time.sleep(delay)
                try:
                    client.check_live()
                except CliApiError:
                    if attempt == len(_CONNECT_BACKOFF_SECONDS):
                        break
                    continue
                return
    except KeyboardInterrupt:
        console.print()
        raise SystemExit(130) from None

    console.print(f"[red]No connection to API at {client.base_url}.[/red]")
    raise SystemExit(1)


def run_repl() -> None:
    console = Console()
    state = ReplState()

    with AuditApiClient.from_env() as client:
        try:
            console.print("[bold]Audit Assistant[/bold] — interactive mode")
            _wait_for_api(client, console)
            session: PromptSession[str] = PromptSession(
                bottom_toolbar=lambda: _token_toolbar(state),
            )
            state.engagement_id = _select_engagement(client, console)
            _pick_initial_session(client, console, state.engagement_id, state)

            while True:
                render_speaker(console, "you")
                try:
                    line = session.prompt("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print()
                    break
                if not line:
                    continue
                if line.startswith("/"):
                    if not _handle_slash(line, client=client, console=console, state=state):
                        break
                else:
                    _ask_question(client, console, state, line)

        except CliApiError as exc:
            render_error(console, exc)
        except httpx.RequestError as exc:
            console.print(f"[red]No connection to API at {client.base_url}: {exc}[/red]")
            raise SystemExit(1) from None
