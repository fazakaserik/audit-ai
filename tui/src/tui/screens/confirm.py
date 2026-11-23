"""Simple yes/no confirmation modal."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class ConfirmModal(ModalScreen[bool]):
    """Ask the user to confirm a destructive action."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Yes", show=False),
    ]

    def __init__(self, message: str, *, title: str = "Confirm") -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container", classes="confirm-modal"):
            yield Label(self._title, id="modal-title")
            yield Static(self._message, id="confirm-message")
            yield Static("Enter/Y confirm  ·  Esc/N cancel", id="modal-help")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
