"""Interactive REPL for audit-ai."""

from __future__ import annotations

from uuid import UUID

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status

from backend.api.contracts.v1.responses import AskResponse, CitationResponse
from cli.client import AuditApiClient, CliApiError, unwrap_answer, unwrap_insufficient
from cli.render import (
    render_ask_response,
    render_document_bytes,
    render_engagements,
    render_error,
    render_session_detail,
    render_session_summaries,
)
from domain.engagement import EngagementId

HELP_TEXT = """Slash commands:
  /engagement     Switch engagement (clears session)
  /new            Start a new session on the next question
  /sessions       List recent sessions
  /resume <id>    Load a session and show its turns
  /open <n>       Open citation [n] from the last answer
  /help           Show this help
  /quit           Exit
"""


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


def _select_engagement(client: AuditApiClient, console: Console) -> EngagementId:
    page = client.list_engagements(limit=200, offset=0)
    if not page.items:
        console.print("No engagements yet. Create one on the server, then restart /engagement.")
        raise SystemExit(1)
    render_engagements(console, page.items)
    while True:
        choice = console.input("Engagement id (or number 1..n): ").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(page.items):
                return page.items[index].id
        for item in page.items:
            if item.id == choice:
                return item.id
        console.print("[red]Invalid choice.[/red]")


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
    render_session_summaries(console, page.items)
    choice = console.input("Resume session id (empty for new): ").strip()
    if not choice:
        return
    try:
        session_uuid = UUID(choice)
    except ValueError:
        console.print("[red]Invalid session id.[/red]")
        return
    detail = client.get_session(engagement_id, session_uuid)
    state.session_id = detail.id
    render_session_detail(console, detail)


def _find_citation(state: ReplState, marker: int) -> CitationResponse | None:
    for citation in state.last_citations:
        if citation.marker == marker:
            return citation
    return None


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

    match command:
        case "/quit" | "/exit":
            return False
        case "/help":
            console.print(Markdown(HELP_TEXT))
        case "/new":
            state.session_id = None
            console.print("Next question starts a new session.")
        case "/engagement":
            state.engagement_id = _select_engagement(client, console)
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
            elif len(args) != 1:
                console.print("[red]Usage: /resume <session_id>[/red]")
            else:
                try:
                    session_uuid = UUID(args[0])
                except ValueError:
                    console.print("[red]Invalid session id.[/red]")
                else:
                    detail = client.get_session(state.engagement_id, session_uuid)
                    state.session_id = detail.id
                    if detail.turns:
                        state.last_answer = detail.turns[-1].answer
                        state.last_citations = _collect_citations(state.last_answer)
                    render_session_detail(console, detail)
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
    render_ask_response(console, response)


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