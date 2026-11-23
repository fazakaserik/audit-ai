"""Session picker screen."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from cli.client import CliApiError
from tui.labels import session_label
from tui.screens.base import ChromeScreen
from tui.widgets.option_helpers import highlight_first_enabled

_NEW_SESSION_ID = "new-session"


class SessionsScreen(ChromeScreen):
    """Start a new session or resume an existing one."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back_engagement", "Engagement"),
        Binding("ctrl+e", "back_engagement", "Engagement"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose_main(self) -> ComposeResult:
        yield Label("Resume or start new session  ·  Esc engagement", id="picker-help")
        yield OptionList(id="picker-list")

    def on_mount(self) -> None:
        self.aiditor.set_header_compact(False)
        self.aiditor.refresh_status()
        self._load()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self.aiditor.set_header_compact(False)
        self._load()

    def _load(self) -> None:
        option_list = self.query_one("#picker-list", OptionList)
        option_list.clear_options()
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            option_list.add_option(Option("No engagement selected.", disabled=True))
            return
        option_list.add_option(Option("Start new session", id=_NEW_SESSION_ID))
        try:
            page = self.aiditor.api_client.list_sessions(engagement_id, limit=50, offset=0)
        except CliApiError as exc:
            option_list.add_option(Option(f"Error: {exc.detail}", disabled=True))
            return
        if not page.items:
            option_list.add_option(
                Option("No prior sessions — choose Start new session.", disabled=True)
            )
            return
        for item in page.items:
            option_list.add_option(Option(session_label(item), id=f"sess:{item.id}"))
        highlight_first_enabled(option_list)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None:
            return
        if option_id == _NEW_SESSION_ID:
            self.aiditor.start_new_session()
            return
        if option_id.startswith("sess:"):
            session_id = UUID(option_id.removeprefix("sess:"))
            self.aiditor.resume_session(session_id)

    def action_back_engagement(self) -> None:
        self.aiditor.open_engagements()
