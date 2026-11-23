"""Shared helpers for Typer command modules."""

from __future__ import annotations

import typer
from rich.console import Console

from cli.client import AuditApiClient, CliApiError
from cli.render import render_error

console = Console()


def client() -> AuditApiClient:
    return AuditApiClient.from_env()


def exit_api_error(exc: CliApiError) -> None:
    render_error(console, exc)
    raise typer.Exit(code=1) from exc
