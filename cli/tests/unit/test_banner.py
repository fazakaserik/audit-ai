"""Unit tests for the AIditor startup banner."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from cli.banner import print_banner


def test_print_banner_includes_product_name_and_version() -> None:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, color_system=None)
    print_banner(console)
    output = buffer.getvalue()
    assert "AIditor" in output
    assert "interactive mode" in output
    assert "v0.1.0" in output
