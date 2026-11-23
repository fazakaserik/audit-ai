"""Typer CLI entry for aiditor (non-interactive)."""

from __future__ import annotations

from pathlib import Path

import typer

from cli import __version__
from cli.commands import documents, engagements, sessions, uploads

app = typer.Typer(
    name="aiditor",
    help=(
        "AIditor non-interactive terminal client. "
        "For the fullscreen interactive UI, run: aiditor-tui"
    ),
    no_args_is_help=True,
)

app.add_typer(engagements.app, name="engagements")
app.add_typer(uploads.app, name="uploads")
app.add_typer(sessions.app, name="sessions")
app.add_typer(documents.app, name="documents")


@app.callback()
def main() -> None:
    """Non-interactive terminal client for the AIditor API."""


@app.command("version")
def version() -> None:
    """Print CLI version."""
    typer.echo(f"aiditor {__version__}")


@app.command("upload")
def upload(
    path: Path = typer.Argument(..., help="File, directory, or .zip"),
    engagement: str = typer.Option(..., "--engagement", help="Engagement id"),
    folder: str = typer.Option(..., "--folder", help="Target folder prefix"),
    wait: bool = typer.Option(False, "--wait", help="Poll until upload completes or fails"),
) -> None:
    """Upload files to an engagement folder."""
    uploads.upload_path_command(path, engagement, folder, wait)


if __name__ == "__main__":
    app()
