"""Document listing and download commands."""

from __future__ import annotations

import typer

from backend.domain.engagement import EngagementId
from cli.client import CliApiError
from cli.commands._common import client, console, exit_api_error
from cli.render import render_document_bytes, render_document_listing

app = typer.Typer(help="Engagement documents")


@app.command("list")
def documents_list(
    engagement: str = typer.Option(..., "--engagement"),
    prefix: str | None = typer.Option(None, "--prefix", help="Folder to list under"),
    depth: int | None = typer.Option(None, "--depth", min=1, help="Max path depth under prefix"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List documents and child folders."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            listing = api.list_documents(
                engagement_id,
                prefix=prefix,
                depth=depth,
                limit=limit,
                offset=offset,
            )
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_document_listing(console, listing, prefix=prefix or "")


@app.command("get")
def documents_get(
    engagement: str = typer.Option(..., "--engagement"),
    path: str = typer.Option(..., "--path", help="Document path"),
) -> None:
    """Download and print a document."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            content = api.get_document_content(engagement_id, path)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_document_bytes(console, path, content)


@app.command("delete")
def documents_delete(
    engagement: str = typer.Option(..., "--engagement"),
    path: str = typer.Option(..., "--path", help="Document path"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Delete a document and its indexed chunks."""
    engagement_id: EngagementId = engagement
    if not yes and not typer.confirm(f"Delete document {path}?"):
        raise typer.Abort()
    with client() as api:
        try:
            api.delete_document(engagement_id, path)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            console.print(f"Deleted document {path}")
