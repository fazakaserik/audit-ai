"""Modal upload list / detail."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast
from uuid import UUID

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from cli.client import CliApiError
from tui.chat_render import error_panel
from tui.labels import upload_label
from tui.widgets.option_helpers import (
    begin_picker_load,
    finish_picker_load,
    show_picker_empty,
    show_picker_error,
)

if TYPE_CHECKING:
    from tui.app import AiditorApp


class UploadsModal(ModalScreen[None]):
    """List uploads or show one upload's details."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    def __init__(self, upload_id: UUID | None = None) -> None:
        super().__init__()
        self._upload_id = upload_id

    @property
    def aiditor(self) -> AiditorApp:
        return cast(AiditorApp, self.app)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("Uploads", id="modal-title")
            yield OptionList(id="modal-list")
            yield Static("", id="modal-detail")
            yield Static("Enter details  ·  Esc close", id="modal-help")

    def on_mount(self) -> None:
        if self._upload_id is not None:
            self._show_detail(self._upload_id)
        else:
            self._load_list()

    def _load_list(self) -> None:
        option_list = self.query_one("#modal-list", OptionList)
        begin_picker_load(option_list)
        option_list.display = True
        self.query_one("#modal-detail", Static).update("")
        self.query_one("#modal-title", Label).update("Uploads")
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            option_list.add_option(Option("No engagement selected.", disabled=True))
            return
        try:
            page = self.aiditor.api_client.list_uploads(engagement_id, limit=50, offset=0)
        except CliApiError as exc:
            show_picker_error(option_list, f"Error: {exc.detail}")
            return
        if not page.items:
            show_picker_empty(option_list, "No uploads yet.")
            return
        options = [Option(upload_label(item), id=f"up:{item.id}") for item in page.items]
        finish_picker_load(option_list, options)

    def _show_detail(self, upload_id: UUID) -> None:
        option_list = self.query_one("#modal-list", OptionList)
        option_list.display = False
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            return
        detail = self.query_one("#modal-detail", Static)
        self.query_one("#modal-title", Label).update(f"Upload {upload_id}")
        try:
            upload = self.aiditor.api_client.get_upload_status(engagement_id, upload_id)
        except CliApiError as exc:
            detail.update(error_panel(exc))
            return
        lines = [
            Text(
                f"Upload {upload.id} — {upload.status.value} (folder: {upload.target_folder})",
                style="bold",
            )
        ]
        if upload.completed_at is not None:
            lines.append(Text(f"completed_at: {upload.completed_at.isoformat()}", style="dim"))
        for item in upload.items:
            reason = f" — {item.reason}" if item.reason else ""
            lines.append(Text(f"  {item.document_path}: {item.status.value}{reason}"))
        detail.update(Group(*lines))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or not option_id.startswith("up:"):
            return
        self._show_detail(UUID(option_id.removeprefix("up:")))

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
