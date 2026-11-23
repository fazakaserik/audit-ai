"""Static that supports mouse text selection for any Rich renderable."""

from __future__ import annotations

from typing import Any

from rich.console import RenderableType
from textual.selection import Selection
from textual.widgets import Static

from tui.render_text import renderable_to_text


class SelectableStatic(Static):
    """Static that stores ``Text`` so Textual can mouse-select and copy.

    Textual only attaches selection ``offset`` meta for ``Text`` / ``Content``.
    Rich Markdown/Group/Panel omit that meta, so selection never starts.
    """

    ALLOW_SELECT = True

    def __init__(
        self,
        renderable: RenderableType = "",
        *,
        markup: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(renderable_to_text(renderable), markup=markup, **kwargs)

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        extracted = super().get_selection(selection)
        if extracted is not None:
            return extracted
        if self.size.height <= 0:
            return None
        lines = [self.render_line(y).text for y in range(self.size.height)]
        text = "\n".join(lines)
        if not text.strip():
            return None
        return selection.extract(text), "\n"
