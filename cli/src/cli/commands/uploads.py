"""Upload commands."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from rich.status import Status

from backend.domain.engagement import EngagementId
from cli.client import CliApiError
from cli.commands._common import client, console, exit_api_error
from cli.render import render_upload_status, render_upload_summaries

app = typer.Typer(help="Upload jobs")


@app.command("list")
def uploads_list(
    engagement: str = typer.Option(..., "--engagement"),
    limit: int = typer.Option(50, min=1, max=200),
    offset: int = typer.Option(0, min=0),
) -> None:
    """List upload jobs for an engagement."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            page = api.list_uploads(engagement_id, limit=limit, offset=offset)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_upload_summaries(console, page.items)


@app.command("status")
def uploads_status(
    engagement: str = typer.Option(..., "--engagement"),
    upload: UUID = typer.Option(..., "--upload"),
) -> None:
    """Show upload processing status."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            result = api.get_upload_status(engagement_id, upload)
        except CliApiError as exc:
            exit_api_error(exc)
        else:
            render_upload_status(console, result)


def upload_path_command(
    path: Path,
    engagement: str,
    folder: str,
    wait: bool,
) -> None:
    """Upload files to an engagement folder (top-level `aiditor upload`)."""
    engagement_id: EngagementId = engagement
    with client() as api:
        try:
            accepted = api.upload_path(engagement_id, path, folder=folder)
        except CliApiError as exc:
            exit_api_error(exc)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        else:
            console.print(f"Upload queued: {accepted.upload_id}")
            if not wait:
                return
            try:
                with Status("Waiting for upload…", console=console):
                    final = api.wait_upload(engagement_id, accepted.upload_id)
            except CliApiError as exc:
                exit_api_error(exc)
            else:
                render_upload_status(console, final)
                if final.status.value == "failed":
                    raise typer.Exit(code=1)
