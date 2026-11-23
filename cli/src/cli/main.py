"""Typer CLI entry for aiditor."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from rich.console import Console
from rich.status import Status

from backend.domain.engagement import EngagementId
from cli import __version__
from cli.client import AuditApiClient, CliApiError
from cli.render import (
    render_document_bytes,
    render_document_listing,
    render_engagement,
    render_engagements,
    render_error,
    render_session_detail,
    render_session_summaries,
    render_upload_status,
    render_upload_summaries,
)
from cli.repl import run_repl

console = Console()

app = typer.Typer(
    name="aiditor",
    help="AIditor terminal client",
    no_args_is_help=False,
)

engagements_app = typer.Typer(help="Manage engagements")
uploads_app = typer.Typer(help="Upload jobs")
sessions_app = typer.Typer(help="Chat sessions")
documents_app = typer.Typer(help="Engagement documents")

app.add_typer(engagements_app, name="engagements")
app.add_typer(uploads_app, name="uploads")
app.add_typer(sessions_app, name="sessions")
app.add_typer(documents_app, name="documents")


def _client() -> AuditApiClient:
    return AuditApiClient.from_env()


def _exit_api_error(exc: CliApiError) -> None:
    render_error(console, exc)
    raise typer.Exit(code=1) from exc


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Interactive terminal client for the AIditor API."""
    if ctx.invoked_subcommand is None:
        run_repl()
        raise typer.Exit()


@app.command("version")
def version() -> None:
    """Print CLI version."""
    typer.echo(f"aiditor {__version__}")


@engagements_app.command("list")
def engagements_list(
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List engagements."""
    with _client() as client:
        try:
            page = client.list_engagements(limit=limit, offset=offset)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_engagements(console, page.items)


@engagements_app.command("show")
def engagements_show(
    id: str = typer.Option(..., "--id", help="Engagement id"),
) -> None:
    """Show one engagement."""
    engagement_id: EngagementId = id
    with _client() as client:
        try:
            engagement = client.get_engagement(engagement_id)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_engagement(console, engagement)


@engagements_app.command("create")
def engagements_create(
    id: str = typer.Option(..., "--id", help="Engagement slug"),
    name: str = typer.Option(..., "--name", help="Display name"),
) -> None:
    """Create an engagement."""
    engagement_id: EngagementId = id
    with _client() as client:
        try:
            created = client.create_engagement(engagement_id=engagement_id, name=name)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            console.print(f"Created engagement {created.id} ({created.name})")


@app.command("upload")
def upload(
    path: Path = typer.Argument(..., help="File, directory, or .zip"),
    engagement: str = typer.Option(..., "--engagement", help="Engagement id"),
    folder: str = typer.Option(..., "--folder", help="Target folder prefix"),
    wait: bool = typer.Option(False, "--wait", help="Poll until upload completes or fails"),
) -> None:
    """Upload files to an engagement folder."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            accepted = client.upload_path(engagement_id, path, folder=folder)
        except CliApiError as exc:
            _exit_api_error(exc)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        else:
            console.print(f"Upload queued: {accepted.upload_id}")
            if not wait:
                return
            try:
                with Status("Waiting for upload…", console=console):
                    final = client.wait_upload(engagement_id, accepted.upload_id)
            except CliApiError as exc:
                _exit_api_error(exc)
            else:
                render_upload_status(console, final)
                if final.status.value == "failed":
                    raise typer.Exit(code=1)


@uploads_app.command("list")
def uploads_list(
    engagement: str = typer.Option(..., "--engagement"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List upload jobs for an engagement."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            page = client.list_uploads(engagement_id, limit=limit, offset=offset)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_upload_summaries(console, page.items)


@uploads_app.command("status")
def uploads_status(
    engagement: str = typer.Option(..., "--engagement"),
    upload: UUID = typer.Option(..., "--upload"),
) -> None:
    """Show upload processing status."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            result = client.get_upload_status(engagement_id, upload)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_upload_status(console, result)


@documents_app.command("list")
def documents_list(
    engagement: str = typer.Option(..., "--engagement"),
    prefix: str | None = typer.Option(None, "--prefix", help="Folder to list under"),
    depth: int | None = typer.Option(None, "--depth", min=1, help="Max path depth under prefix"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List documents and child folders."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            listing = client.list_documents(
                engagement_id,
                prefix=prefix,
                depth=depth,
                limit=limit,
                offset=offset,
            )
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_document_listing(console, listing, prefix=prefix or "")


@documents_app.command("get")
def documents_get(
    engagement: str = typer.Option(..., "--engagement"),
    path: str = typer.Option(..., "--path", help="Document path"),
) -> None:
    """Download and print a document."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            content = client.get_document_content(engagement_id, path)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_document_bytes(console, path, content)


@sessions_app.command("list")
def sessions_list(
    engagement: str = typer.Option(..., "--engagement"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List sessions for an engagement."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            page = client.list_sessions(engagement_id, limit=limit, offset=offset)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_session_summaries(console, page.items)


@sessions_app.command("show")
def sessions_show(
    engagement: str = typer.Option(..., "--engagement"),
    session: UUID = typer.Option(..., "--session"),
) -> None:
    """Show a session and its turns."""
    engagement_id: EngagementId = engagement
    with _client() as client:
        try:
            detail = client.get_session(engagement_id, session)
        except CliApiError as exc:
            _exit_api_error(exc)
        else:
            render_session_detail(console, detail)


if __name__ == "__main__":
    app()
