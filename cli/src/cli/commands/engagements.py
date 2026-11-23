"""Engagement management commands."""

from __future__ import annotations

import typer

from backend.domain.engagement import EngagementId
from cli.client import CliApiError
from cli.commands._common import client, console, exit_api_error
from cli.render import render_engagement, render_engagements

app = typer.Typer(help="Manage engagements")


@app.command("list")
def engagements_list(
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List engagements."""
    with client() as api:
        try:
            page = api.list_engagements(limit=limit, offset=offset)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_engagements(console, page.items)


@app.command("show")
def engagements_show(
    id: str = typer.Option(..., "--id", help="Engagement id"),
) -> None:
    """Show one engagement."""
    engagement_id: EngagementId = id
    with client() as api:
        try:
            engagement = api.get_engagement(engagement_id)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_engagement(console, engagement)


@app.command("create")
def engagements_create(
    id: str = typer.Option(..., "--id", help="Engagement slug"),
    name: str = typer.Option(..., "--name", help="Display name"),
) -> None:
    """Create an engagement."""
    engagement_id: EngagementId = id
    with client() as api:
        try:
            created = api.create_engagement(engagement_id=engagement_id, name=name)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            console.print(f"Created engagement {created.id} ({created.name})")


@app.command("rename")
def engagements_rename(
    id: str = typer.Option(..., "--id", help="Engagement id"),
    name: str = typer.Option(..., "--name", help="New display name"),
) -> None:
    """Rename an engagement (id stays the same)."""
    engagement_id: EngagementId = id
    with client() as api:
        try:
            updated = api.update_engagement(engagement_id, name=name)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            console.print(f"Renamed engagement {updated.id} -> {updated.name}")


@app.command("delete")
def engagements_delete(
    id: str = typer.Option(..., "--id", help="Engagement id"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Delete an engagement and all related documents, uploads, and sessions."""
    engagement_id: EngagementId = id
    if not yes and not typer.confirm(f"Delete engagement {engagement_id} and all its data?"):
        raise typer.Abort()
    with client() as api:
        try:
            api.delete_engagement(engagement_id)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            console.print(f"Deleted engagement {engagement_id}")
