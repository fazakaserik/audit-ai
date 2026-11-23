"""Convert Rich renderables to Text so Textual can attach selection offsets."""

from __future__ import annotations

from rich.console import Console, RenderableType
from rich.markdown import Markdown
from rich.text import Text

# Wide enough that Markdown layout uses structural newlines only; Static wraps.
_MARKDOWN_CONSOLE_WIDTH = 10_000


def markdown_to_text(source: str) -> Text:
    """Render Markdown to a single Text (keeps bold/lists; selectable in Textual)."""
    return renderable_to_text(Markdown(source), width=_MARKDOWN_CONSOLE_WIDTH)


def renderable_to_text(renderable: RenderableType, *, width: int = 80) -> Text:
    """Flatten any Rich renderable to Text.

    Textual only injects selection ``offset`` meta for ``Text`` / ``Content``
    visuals. Rich ``Markdown``, ``Group``, and ``Panel`` omit that meta, so
    mouse selection cannot start inside those Static widgets.
    """
    if isinstance(renderable, str):
        return Text(renderable)
    if isinstance(renderable, Text):
        return renderable
    console = Console(
        width=max(width, 1),
        force_terminal=True,
        highlight=False,
        color_system="standard",
    )
    out = Text()
    for segment in console.render(renderable):
        out.append(segment.text, style=segment.style)
    return out
