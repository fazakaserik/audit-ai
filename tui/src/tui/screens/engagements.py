"""Engagement picker screen with create / rename / delete."""

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
from tui.screens.confirm import ConfirmModal
from tui.screens.engagement_edit import EngagementCreateModal, EngagementRenameModal
from tui.widgets.option_helpers import (
    begin_picker_load,
    finish_picker_load,
    show_picker_empty,
    show_picker_error,
)


class EngagementsScreen(ChromeScreen):
    """Select an engagement to work in, or manage engagements."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "create_engagement", "New"),
        Binding("r", "rename_engagement", "Rename"),
        Binding("d", "delete_engagement", "Delete"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._names_by_id: dict[str, str] = {}

    def compose_main(self) -> ComposeResult:
        yield Label(
            "Enter open  ·  n new  ·  r rename  ·  d delete  ·  q quit",
            id="picker-help",
        )
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
                "No engagements yet. Press n to create one.",
            )
            return
        options: list[Option] = []
        for item in page.items:
            self._names_by_id[str(item.id)] = item.name
            options.append(Option(engagement_label(item), id=f"eng:{item.id}"))
        finish_picker_load(option_list, options)

    def _highlighted_engagement(self) -> tuple[EngagementId, str] | None:
        option_list = self.query_one("#picker-list", OptionList)
        index = option_list.highlighted
        if index is None:
            return None
        option = option_list.get_option_at_index(index)
        option_id = option.id
        if option_id is None or not option_id.startswith("eng:"):
            return None
        engagement_id: EngagementId = option_id.removeprefix("eng:")
        name = self._names_by_id.get(str(engagement_id), str(engagement_id))
        return engagement_id, name

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or not option_id.startswith("eng:"):
            return
        engagement_id: EngagementId = option_id.removeprefix("eng:")
        name = self._names_by_id.get(str(engagement_id), str(engagement_id))
        self.aiditor.select_engagement(engagement_id, name)

    def action_create_engagement(self) -> None:
        self.app.push_screen(EngagementCreateModal(), self._on_create_result)

    def _on_create_result(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        engagement_id, name = result
        try:
            created = self.aiditor.api_client.create_engagement(
                engagement_id=engagement_id,
                name=name,
            )
        except CliApiError as exc:
            self.notify(exc.detail, title="Create failed", severity="error", timeout=5)
            return
        self.notify(f"Created {created.name}", title="Engagement", timeout=3)
        self._load()

    def action_rename_engagement(self) -> None:
        selected = self._highlighted_engagement()
        if selected is None:
            self.notify("Select an engagement first.", severity="warning", timeout=3)
            return
        engagement_id, name = selected
        self.app.push_screen(
            EngagementRenameModal(current_name=name, engagement_id=str(engagement_id)),
            lambda new_name: self._on_rename_result(engagement_id, new_name),
        )

    def _on_rename_result(
        self,
        engagement_id: EngagementId,
        new_name: str | None,
    ) -> None:
        if new_name is None:
            return
        try:
            updated = self.aiditor.api_client.update_engagement(
                engagement_id,
                name=new_name,
            )
        except CliApiError as exc:
            self.notify(exc.detail, title="Rename failed", severity="error", timeout=5)
            return
        if self.aiditor.state.engagement_id == engagement_id:
            self.aiditor.state.engagement_name = updated.name
            self.aiditor.refresh_status()
        self.notify(f"Renamed to {updated.name}", title="Engagement", timeout=3)
        self._load()

    def action_delete_engagement(self) -> None:
        selected = self._highlighted_engagement()
        if selected is None:
            self.notify("Select an engagement first.", severity="warning", timeout=3)
            return
        engagement_id, name = selected
        message = (
            f"Delete engagement '{name}' ({engagement_id})?\n"
            "This removes documents, uploads, and sessions."
        )
        self.app.push_screen(
            ConfirmModal(message, title="Delete engagement"),
            lambda confirmed: self._on_delete_confirmed(engagement_id, name, confirmed),
        )

    def _on_delete_confirmed(
        self,
        engagement_id: EngagementId,
        name: str,
        confirmed: bool | None,
    ) -> None:
        if not confirmed:
            return
        try:
            self.aiditor.api_client.delete_engagement(engagement_id)
        except CliApiError as exc:
            self.notify(exc.detail, title="Delete failed", severity="error", timeout=5)
            return
        if self.aiditor.state.engagement_id == engagement_id:
            self.aiditor.state.clear_engagement()
            self.aiditor.refresh_status()
        self.notify(f"Deleted {name}", title="Engagement", timeout=3)
        self._load()
