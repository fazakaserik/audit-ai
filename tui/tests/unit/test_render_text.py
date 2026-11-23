"""Renderable → Text conversion keeps agent answers mouse-selectable."""

from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text

from tui.render_text import markdown_to_text, renderable_to_text


def test_markdown_to_text_preserves_plain_words() -> None:
    text = markdown_to_text("Payment terms are **Net-30**.")
    assert "Net-30" in text.plain
    assert "Payment terms" in text.plain


def test_renderable_to_text_flattens_group() -> None:
    grouped = Group(Markdown("Hello **world**"), Text("\ntail"))
    text = renderable_to_text(grouped, width=80)
    assert isinstance(text, Text)
    assert "Hello" in text.plain
    assert "world" in text.plain
    assert "tail" in text.plain


def test_renderable_to_text_passthrough_text() -> None:
    original = Text("already text", style="bold")
    assert renderable_to_text(original) is original
