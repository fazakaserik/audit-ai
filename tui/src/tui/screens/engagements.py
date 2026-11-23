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
from tui.widgets.option_helpers import (
    begin_picker_load,
    finish_picker_load,
    show_picker_empty,
    show_picker_error,
)


class EngagementsScreen(ChromeScreen):
    """Select an engagement to work in."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._names_by_id: dict[str, str] = {}

    def compose_main(self) -> ComposeResult:
        yield Label("Select engagement", id="picker-help")
        yield OptionList(id="picker-list")

    def on_mount(self) -> None:
        self.aiditor.set_header_compact(False)
        self.aiditor.refresh_status()
        self._load()

    def _load(self) -> None:
        option_list = self.query_one("#picker-list", OptionList)
        begin_picker_load(option_list)
        self._names_by_id = {}
        try:
            page = self.aiditor.api_client.list_engagements(limit=200, offset=0)
        except CliApiError as exc:
            show_picker_error(option_list, f"Error: {exc.detail}")
            return
        if not page.items:
            show_picker_empty(
                option_list,
                "No engagements yet. Create one via aiditor, then restart.",
            )
            return
        options: list[Option] = []
        for item in page.items:
            self._names_by_id[str(item.id)] = item.name
            options.append(Option(engagement_label(item), id=f"eng:{item.id}"))
        finish_picker_load(option_list, options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or not option_id.startswith("eng:"):
            return
        engagement_id: EngagementId = option_id.removeprefix("eng:")
        name = self._names_by_id.get(str(engagement_id), str(engagement_id))
        self.aiditor.select_engagement(engagement_id, name)
