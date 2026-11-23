"""Startup banner for the AIditor CLI (Claude Code–style)."""

from __future__ import annotations

from rich.console import Console

from cli import __version__

# Block-letter wordmark for "AIditor"
_WORDMARK = (
    r"  █████╗ ██╗██████╗ ██╗████████╗ ██████╗ ██████╗ ",
    r" ██╔══██╗██║██╔══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗",
    r" ███████║██║██║  ██║██║   ██║   ██║   ██║██████╔╝",
    r" ██╔══██║██║██║  ██║██║   ██║   ██║   ██║██╔══██╗",
    r" ██║  ██║██║██████╔╝██║   ██║   ╚██████╔╝██║  ██║",
    r" ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
)

# Cyan → teal → green gradient across lines (Rich markup colors).
_LINE_COLORS = (
    "bright_cyan",
    "cyan",
    "dark_cyan",
    "#2E8B57",
    "green",
    "bright_green",
)


def print_banner(console: Console) -> None:
    """Print the colored AIditor wordmark and a short tagline."""
    console.print()
    for line, color in zip(_WORDMARK, _LINE_COLORS, strict=True):
        console.print(f"[{color}]{line}[/{color}]")
    console.print()
    console.print(
        f"[bold]AIditor[/bold] [dim]v{__version__}[/dim] — interactive mode"
    )
    console.print()
