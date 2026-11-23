"""Bottom status bar: session label + classic token toolbar."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from tui.state import AppState, format_session_label, format_token_stats


class StatusBar(Static):
    """Docked one-line status chrome with ctx / last / session tokens."""

    def __init__(
        self,
        state: AppState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._state = state

    def on_mount(self) -> None:
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        line = Text()
        line.append(" ")
        line.append(format_session_label(self._state), style="bold")
        line.append("  ·  ", style="dim")
        line.append(format_token_stats(self._state))
        line.append(" ")
        self.update(line)
