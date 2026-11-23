"""Modal upload list / detail with live status."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, ClassVar, cast
from uuid import UUID

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static
from textual.widgets.data_table import CellDoesNotExist

from backend.application.api.contracts.v1.responses import (
    UploadResponse,
    UploadSummaryResponse,
)
from backend.domain.common import utc_now
from backend.domain.upload import UploadStatus
from cli.client import UPLOAD_POLL_INTERVAL_SECONDS, CliApiError
from cli.formatting.duration import format_elapsed
from cli.render import upload_status_renderable, upload_status_text
from tui.chat_render import error_panel

if TYPE_CHECKING:
    from textual.timer import Timer

    from tui.app import AiditorApp

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_ACTIVE_UPLOAD = frozenset({UploadStatus.QUEUED, UploadStatus.PROCESSING})


class UploadsModal(ModalScreen[None]):
    """List uploads in a table, or show one upload's per-file metrics."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back/Close"),
        Binding("enter", "open_selected", "Details", show=False),
    ]

    def __init__(self, upload_id: UUID | None = None) -> None:
        super().__init__()
        self._upload_id = upload_id
        self._opened_with_id = upload_id is not None
        self._summaries: list[UploadSummaryResponse] = []
        self._detail: UploadResponse | None = None
        self._spinner_index = 0
        self._poll_timer: Timer | None = None
        self._spin_timer: Timer | None = None

    @property
    def aiditor(self) -> AiditorApp:
        return cast("AiditorApp", self.app)

    @property
    def _spinner(self) -> str:
        return _SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("Uploads", id="modal-title")
            yield DataTable(id="uploads-table", cursor_type="row", zebra_stripes=True)
            with VerticalScroll(id="modal-detail-scroll"):
                yield Static("", id="modal-detail")
            yield Static("↑↓ select  ·  Enter details  ·  Esc close", id="modal-help")

    def on_mount(self) -> None:
        table = self.query_one("#uploads-table", DataTable)
        table.add_column("Status", key="status", width=14)
        table.add_column("Folder", key="folder")
        table.add_column("Created", key="created", width=20)
        table.add_column("Duration", key="duration", width=10)
        table.add_column("Upload ID", key="id", width=36)

        detail_scroll = self.query_one("#modal-detail-scroll", VerticalScroll)
        if self._upload_id is not None:
            table.display = False
            detail_scroll.display = True
            self._show_detail(self._upload_id)
        else:
            detail_scroll.display = False
            self._load_list()

        self._spin_timer = self.set_interval(0.12, self._tick_spinner)
        self._poll_timer = self.set_interval(UPLOAD_POLL_INTERVAL_SECONDS, self._poll_refresh)

    def on_unmount(self) -> None:
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def _load_list(self) -> None:
        table = self.query_one("#uploads-table", DataTable)
        detail = self.query_one("#modal-detail", Static)
        detail_scroll = self.query_one("#modal-detail-scroll", VerticalScroll)
        table.display = True
        detail_scroll.display = False
        detail.update("")
        self.query_one("#modal-title", Label).update("Uploads")
        self.query_one("#modal-help", Static).update("↑↓ select  ·  Enter details  ·  Esc close")
        self._detail = None
        self._upload_id = None

        engagement_id = self.aiditor.state.engagement_id
        table.clear()
        if engagement_id is None:
            self._summaries = []
            table.add_row(Text("No engagement selected.", style="dim"))
            return
        try:
            page = self.aiditor.api_client.list_uploads(engagement_id, limit=50, offset=0)
        except CliApiError as exc:
            self._summaries = []
            table.add_row(Text(f"Error: {exc.detail}", style="red"))
            return
        self._summaries = list(page.items)
        if not self._summaries:
            table.add_row(Text("No uploads yet.", style="dim"))
            return
        self._fill_table_rows()
        table.focus()

    def _fill_table_rows(self) -> None:
        table = self.query_one("#uploads-table", DataTable)
        table.clear()
        now = utc_now()
        for item in self._summaries:
            table.add_row(
                upload_status_text(item.status, spinner=self._spinner),
                item.target_folder,
                item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                format_elapsed(item.created_at, item.completed_at, now=now),
                str(item.id),
                key=str(item.id),
            )

    def _show_detail(self, upload_id: UUID) -> None:
        table = self.query_one("#uploads-table", DataTable)
        detail_scroll = self.query_one("#modal-detail-scroll", VerticalScroll)
        detail = self.query_one("#modal-detail", Static)
        table.display = False
        detail_scroll.display = True
        self._upload_id = upload_id
        self.query_one("#modal-title", Label).update(f"Upload {upload_id}")
        help_bits = "Esc back" if not self._opened_with_id else "Esc close"
        self.query_one("#modal-help", Static).update(help_bits)

        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            detail.update(Text("No engagement selected.", style="dim"))
            return
        try:
            upload = self.aiditor.api_client.get_upload_status(engagement_id, upload_id)
        except CliApiError as exc:
            self._detail = None
            detail.update(error_panel(exc))
            return
        self._detail = upload
        detail.update(upload_status_renderable(upload, spinner=self._spinner, now=utc_now()))
        detail_scroll.focus()

    def _tick_spinner(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(_SPINNER_FRAMES)
        if self._detail is not None and self._detail.status in _ACTIVE_UPLOAD:
            self.query_one("#modal-detail", Static).update(
                upload_status_renderable(self._detail, spinner=self._spinner, now=utc_now())
            )
            return
        if self._upload_id is not None:
            return
        if not any(item.status in _ACTIVE_UPLOAD for item in self._summaries):
            return
        table = self.query_one("#uploads-table", DataTable)
        now = utc_now()
        for item in self._summaries:
            if item.status not in _ACTIVE_UPLOAD:
                continue
            key = str(item.id)
            try:
                table.update_cell(
                    key,
                    "status",
                    upload_status_text(item.status, spinner=self._spinner),
                )
                table.update_cell(
                    key,
                    "duration",
                    format_elapsed(item.created_at, item.completed_at, now=now),
                )
            except CellDoesNotExist:
                return

    def _poll_refresh(self) -> None:
        if self._upload_id is not None:
            if self._detail is None or self._detail.status in _ACTIVE_UPLOAD:
                self._show_detail(self._upload_id)
            return
        if any(item.status in _ACTIVE_UPLOAD for item in self._summaries):
            self._reload_summaries_in_place()

    def _reload_summaries_in_place(self) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            return
        table = self.query_one("#uploads-table", DataTable)
        cursor_key: str | None = None
        if table.row_count > 0 and table.cursor_row is not None:
            try:
                raw_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            except CellDoesNotExist:
                raw_key = None
            if raw_key is not None:
                cursor_key = str(raw_key)
        try:
            page = self.aiditor.api_client.list_uploads(engagement_id, limit=50, offset=0)
        except CliApiError:
            return
        self._summaries = list(page.items)
        if not self._summaries:
            table.clear()
            table.add_row(Text("No uploads yet.", style="dim"))
            return
        self._fill_table_rows()
        if cursor_key is not None:
            with contextlib.suppress(CellDoesNotExist):
                table.cursor_coordinate = table.get_cell_coordinate(cursor_key, "status")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._upload_id is not None:
            return
        row_key = event.row_key.value
        if row_key is None:
            return
        try:
            upload_id = UUID(str(row_key))
        except ValueError:
            return
        self._show_detail(upload_id)

    def action_open_selected(self) -> None:
        if self._upload_id is not None:
            return
        table = self.query_one("#uploads-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            if row_key is None:
                return
            upload_id = UUID(str(row_key))
        except (CellDoesNotExist, ValueError):
            return
        self._show_detail(upload_id)

    def action_go_back(self) -> None:
        if self._upload_id is not None and not self._opened_with_id:
            self._load_list()
            return
        self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
