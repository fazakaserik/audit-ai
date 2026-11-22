"""Typer CLI entry (stub until US7)."""

from __future__ import annotations

import typer

app = typer.Typer(name="audit-ai", help="Audit Assistant terminal client", no_args_is_help=True)


@app.command("version")
def version() -> None:
    """Print CLI version."""
    typer.echo("audit-ai 0.1.0")


if __name__ == "__main__":
    app()
