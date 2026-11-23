"""Shared chrome for every AIditor screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from tui.widgets.brand_header import BrandHeader
from tui.widgets.status_bar import StatusBar

if TYPE_CHECKING:
    from tui.app import AiditorApp


class ChromeScreen(Screen[None]):
    """Screen with sticky brand header, status bar, and key footer."""

    @property
    def aiditor(self) -> AiditorApp:
        # Quoted: AiditorApp is TYPE_CHECKING-only (avoids import cycle with app.py).
        return cast("AiditorApp", self.app)

    def compose(self) -> ComposeResult:
        yield BrandHeader(self.aiditor.state, id="brand-header")
        yield from self.compose_main()
        yield StatusBar(self.aiditor.state, id="status-bar")
        yield Footer()

    def compose_main(self) -> ComposeResult:
        yield from ()

    def on_screen_resume(self) -> None:
        self.aiditor.refresh_status()
