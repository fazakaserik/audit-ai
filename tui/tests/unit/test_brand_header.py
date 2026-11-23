"""Unit tests for brand header content."""

from __future__ import annotations

from tui import __version__
from tui.widgets import brand_header


def test_wordmark_constant_present() -> None:
    assert len(brand_header._WORDMARK) == len(brand_header._LINE_COLORS)
    assert any("█████" in line for line in brand_header._WORDMARK)
    assert __version__
