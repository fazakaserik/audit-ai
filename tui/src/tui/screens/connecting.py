"""Startup screen: wait for API health."""

from __future__ import annotations

from typing import ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Label, LoadingIndicator, Static
from textual.worker import Worker, WorkerState

from tui.screens.base import ChromeScreen


class ConnectingScreen(ChromeScreen):
    """Show connection progress, then hand off to engagements."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Quit"),
    ]

    def compose_main(self) -> ComposeResult:
        with Vertical(id="connect-body"):
            yield Label("Connecting to API…", id="connect-label")
            yield LoadingIndicator()
            yield Static("", id="connect-error")

    def on_mount(self) -> None:
        self.aiditor.set_header_compact(False)
        self.run_worker(self._connect, exclusive=True, thread=True)

    def _connect(self) -> bool:
        return self.aiditor.try_connect()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state is not WorkerState.SUCCESS:
            return
        worker = event.worker  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        result = cast(bool | None, worker.result)
        ok = result is True
        if not ok:
            client = self.aiditor.api_client
            self.query_one("#connect-label", Label).update("Unable to reach API")
            self.query_one("#connect-error", Static).update(
                f"[red]No connection to API at {client.base_url}.[/red]\nPress q to quit."
            )
            return
        self.aiditor.open_engagements()
