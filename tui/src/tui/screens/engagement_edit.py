"""Create / rename engagement modals."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static


class EngagementCreateModal(ModalScreen[tuple[str, str] | None]):
    """Collect engagement id + display name."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container", classes="form-modal"):
            yield Label("Create engagement", id="modal-title")
            yield Label("Id (slug, e.g. northwind-fy2025)")
            yield Input(placeholder="engagement-id", id="eng-id-input")
            yield Label("Display name")
            yield Input(placeholder="Northwind FY2025", id="eng-name-input")
            yield Static("Enter submit  ·  Esc cancel", id="modal-help")

    def on_mount(self) -> None:
        self.query_one("#eng-id-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "eng-id-input":
            self.query_one("#eng-name-input", Input).focus()
            return
        self._submit()

    def _submit(self) -> None:
        engagement_id = self.query_one("#eng-id-input", Input).value.strip()
        name = self.query_one("#eng-name-input", Input).value.strip()
        if not engagement_id or not name:
            self.notify("Id and name are required.", severity="warning", timeout=3)
            return
        self.dismiss((engagement_id, name))

    def action_cancel(self) -> None:
        self.dismiss(None)


class EngagementRenameModal(ModalScreen[str | None]):
    """Collect a new display name for an engagement."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, current_name: str, engagement_id: str) -> None:
        super().__init__()
        self._current_name = current_name
        self._engagement_id = engagement_id

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container", classes="form-modal"):
            yield Label(f"Rename {self._engagement_id}", id="modal-title")
            yield Label("Display name")
            yield Input(value=self._current_name, id="eng-name-input")
            yield Static("Enter submit  ·  Esc cancel", id="modal-help")

    def on_mount(self) -> None:
        name_input = self.query_one("#eng-name-input", Input)
        name_input.focus()
        name_input.cursor_position = len(name_input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        _ = event
        name = self.query_one("#eng-name-input", Input).value.strip()
        if not name:
            self.notify("Name is required.", severity="warning", timeout=3)
            return
        self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
