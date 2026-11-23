"""API error line formatting."""

from __future__ import annotations

from cli.client import CliApiError


def format_error_lines(error: CliApiError) -> list[str]:
    lines = [
        f"[bold red]Error[/bold red] ({error.status})",
        f"code: {error.code.value}",
        f"detail: {error.detail}",
    ]
    if error.request_id is not None:
        lines.append(f"request_id: {error.request_id}")
    return lines
