"""Interactive REPL for audit-ai."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import UUID

import questionary
from prompt_toolkit import PromptSession
from rich.console import Console
from rich.status import Status

from backend.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    EngagementResponse,
    SessionSummaryResponse,
)
from cli.client import AuditApiClient, CliApiError, unwrap_answer, unwrap_insufficient
from cli.render import (
    render_assistant_message,
    render_document_bytes,
    render_error,
    render_session_detail,
    render_session_summaries,
    render_upload_status,
    render_user_message,
)
from domain.engagement import EngagementId

HELP_TEXT = """Slash commands:
  /engagement     Switch engagement (clears session)
  /new            Start a new session on the next question
  /sessions       List recent sessions
  /resume [id]    Resume a session (picker if no id)
  /upload <path> <folder>  Upload to the active engagement under <folder>
  /open <n>       Open citation [n] from the last answer
  /help           Show this help
  /quit           Exit
"""

_NEW_SESSION = object()


class ReplState:
    def __init__(self) -> None:
        self.engagement_id: EngagementId | None = None
        self.session_id: UUID | None = None
        self.last_answer: AskResponse | None = None
        self.last_citations: tuple[CitationResponse, ...] = ()


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
    return f"{item.title}  ({item.id})  [{item.turn_count} turns, {item.updated_at.isoformat()}]"


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
        state.last_answer = detail.turns[-1].answer
        state.last_citations = _collect_citations(state.last_answer)
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
            console.print("Next question starts a new session.")
        case "/engagement":
            selected = _select_engagement(client, console)
            state.engagement_id = selected
            state.session_id = None
            state.last_answer = None
            state.last_citations = ()
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
    render_user_message(console, question)
    try:
        with Status("Thinking…", console=console):
            response = client.ask(
                state.engagement_id,
                question=question,
                session_id=state.session_id,
            )
    except CliApiError as exc:
        render_error(console, exc)
        return
    state.session_id = _session_from_response(response)
    state.last_answer = response
    state.last_citations = _collect_citations(response)
    render_assistant_message(console, response)


def _session_from_response(response: AskResponse) -> UUID:
    return response.session_id


def run_repl() -> None:
    console = Console()
    session: PromptSession[str] = PromptSession()
    state = ReplState()

    with AuditApiClient.from_env() as client:
        try:
            console.print("[bold]Audit Assistant[/bold] — interactive mode")
            state.engagement_id = _select_engagement(client, console)
            _pick_initial_session(client, console, state.engagement_id, state)

            while True:
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
