"""Engagement picker screen."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from backend.domain.engagement import EngagementId
from cli.client import CliApiError
from tui.labels import engagement_label
from tui.screens.base import ChromeScreen
from tui.widgets.option_helpers import highlight_first_enabled


class EngagementsScreen(ChromeScreen):
    """Select an engagement to work in."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Quit"),
    ]

    def compose_main(self) -> ComposeResult:
        yield Label("Select engagement", id="picker-help")
        yield OptionList(id="picker-list")

    def on_mount(self) -> None:
        self.aiditor.set_header_compact(False)
        self.aiditor.refresh_status()
        self._load()

    def _load(self) -> None:
        option_list = self.query_one("#picker-list", OptionList)
        option_list.clear_options()
        try:
            page = self.aiditor.api_client.list_engagements(limit=200, offset=0)
        except CliApiError as exc:
            option_list.add_option(Option(f"Error: {exc.detail}", id="error", disabled=True))
            return
        if not page.items:
            option_list.add_option(
                Option("No engagements yet. Create one via aiditor, then restart.", disabled=True)
            )
            return
        for item in page.items:
            option_list.add_option(Option(engagement_label(item), id=f"eng:{item.id}"))
        highlight_first_enabled(option_list)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or not option_id.startswith("eng:"):
            return
        engagement_id: EngagementId = option_id.removeprefix("eng:")
        # Recover display name from the option prompt text before the id paren.
        prompt = str(event.option.prompt)
        name = prompt.split("  (", 1)[0].strip() or engagement_id
        self.aiditor.select_engagement(engagement_id, name)
