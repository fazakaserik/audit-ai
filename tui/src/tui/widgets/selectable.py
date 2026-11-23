"""Static that supports mouse text selection for any Rich renderable."""

from __future__ import annotations

from textual.selection import Selection
from textual.widgets import Static


class SelectableStatic(Static):
    """Like Static, but selection works for Markdown/Group/Panel content.

    Textual's default ``get_selection`` only extracts text when the visual is
    ``Text`` or ``Content``; Rich Markdown/Group return ``None`` and selection
    appears broken.
    """

    ALLOW_SELECT = True

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
