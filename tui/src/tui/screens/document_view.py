"""Full-screen document viewer (Esc returns to the previous screen)."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.chat_render import document_body_text
from tui.widgets.selectable import SelectableStatic


class DocumentViewScreen(Screen[None]):
    """Inspect a document full-screen, then Esc/q back — like leaving vim."""

    ALLOW_SELECT = True
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close", show=True),
        Binding("q", "close", "Close", show=False),
        Binding("ctrl+c", "copy_selected", "Copy", show=False),
    ]

    def __init__(self, path: str, content: bytes) -> None:
        super().__init__()
        self._path = path
        self._content = content

    def compose(self) -> ComposeResult:
        yield Static(Text(self._path, style="bold"), id="doc-view-title")
        with VerticalScroll(id="doc-view-body"):
            yield SelectableStatic(
                document_body_text(self._content),
                id="doc-view-content",
                markup=False,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#doc-view-body", VerticalScroll).focus()

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_copy_selected(self) -> None:
        selected = self.get_selected_text()
        if selected:
            self.app.copy_to_clipboard(selected)
            self.notify("Copied", timeout=1.5)
