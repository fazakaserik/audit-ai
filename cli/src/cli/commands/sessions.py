"""Session listing commands."""

from __future__ import annotations

from uuid import UUID

import typer

from backend.domain.engagement import EngagementId
from cli.client import CliApiError
from cli.commands._common import client, console, exit_api_error
from cli.render import render_session_detail, render_session_summaries

app = typer.Typer(help="Chat sessions")


@app.command("list")
def sessions_list(
    engagement: str = typer.Option(..., "--engagement"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List sessions for an engagement."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            page = api.list_sessions(engagement_id, limit=limit, offset=offset)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_session_summaries(console, page.items)


@app.command("show")
def sessions_show(
    engagement: str = typer.Option(..., "--engagement"),
    session: UUID = typer.Option(..., "--session"),
) -> None:
    """Show a session and its turns."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            detail = api.get_session(engagement_id, session)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_session_detail(console, detail)
