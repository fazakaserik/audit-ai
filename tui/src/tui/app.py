"""Aiditor Textual application shell."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from uuid import UUID

from rich.text import Text
from textual.app import App
from textual.binding import Binding, BindingType
from textual.css.query import NoMatches

from backend.domain.engagement import EngagementId
from cli.client import AuditApiClient, CliApiError
from tui.chat_render import error_panel, upload_status_panel
from tui.connecting import wait_for_api
from tui.screens.base import ChromeScreen
from tui.screens.chat import ChatScreen
from tui.screens.connecting import ConnectingScreen
from tui.screens.documents import DocumentsModal
from tui.screens.engagements import EngagementsScreen
from tui.screens.sessions import SessionsScreen
from tui.screens.uploads import UploadsModal
from tui.state import AppState
from tui.textual_typing import switch_screen
from tui.widgets.brand_header import BrandHeader
from tui.widgets.status_bar import StatusBar


class AiditorApp(App[None]):
    """Fullscreen AIditor client: sticky chrome + screen stack."""

    CSS_PATH = "styles.tcss"
    TITLE = "AIditor"
    ALLOW_SELECT = True
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+e", "switch_engagement", "Engagement", show=True),
        # Prefer copy-over-quit when text is selected (Textual's default ctrl+c quits).
        Binding("ctrl+c", "copy_selected", "Copy", show=False, priority=True),
    ]

    def action_copy_selected(self) -> None:
        selected = self.screen.get_selected_text()
        if selected:
            self.copy_to_clipboard(selected)
            self.notify("Copied", timeout=1.5)
            return
        self.exit()

    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self._client: AuditApiClient | None = None

    @property
    def api_client(self) -> AuditApiClient:
        if self._client is None:
            msg = "API client is not open"
            raise RuntimeError(msg)
        return self._client

    def on_mount(self) -> None:
        self._client = AuditApiClient.from_env()
        self.push_screen(ConnectingScreen())

    def on_unmount(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def refresh_status(self) -> None:
        try:
            bar = self.screen.query_one("#status-bar", StatusBar)
        except NoMatches:
            pass
        else:
            bar.refresh_from_state()
        try:
            header = self.screen.query_one("#brand-header", BrandHeader)
        except NoMatches:
            pass
        else:
            header.refresh_from_state()

    def set_header_compact(self, compact: bool) -> None:
        try:
            header = self.screen.query_one("#brand-header", BrandHeader)
        except NoMatches:
            return
        header.compact = compact
        header.refresh_from_state()

    def open_engagements(self) -> None:
        self.state.clear_session()
        self._switch(EngagementsScreen())

    def open_sessions(self) -> None:
        if self.state.engagement_id is None:
            self.open_engagements()
            return
        self._switch(SessionsScreen())

    def open_chat(self, *, resume_session_id: UUID | None = None) -> None:
        self._switch(ChatScreen(resume_session_id=resume_session_id))

    def _switch(self, screen: ChromeScreen) -> None:
        """Typed wrapper around Textual switch_screen."""
        switch_screen(self, screen)

    def select_engagement(self, engagement_id: EngagementId, name: str) -> None:
        self.state.set_engagement(engagement_id, name)
        self.open_sessions()

    def start_new_session(self) -> None:
        self.state.clear_session()
        self.open_chat()

    def resume_session(self, session_id: UUID) -> None:
        self.open_chat(resume_session_id=session_id)

    def action_switch_engagement(self) -> None:
        self.open_engagements()

    def try_connect(self) -> bool:
        return wait_for_api(self.api_client)

    def show_documents_modal(self, start_folder: str = "") -> None:
        if self.state.engagement_id is None:
            return
        self.push_screen(DocumentsModal(start_folder=start_folder))

    def show_uploads_modal(self, upload_id: UUID | None = None) -> None:
        if self.state.engagement_id is None:
            return
        self.push_screen(UploadsModal(upload_id=upload_id))

    def upload_path(self, raw_path: str, folder: str) -> object:
        """Upload and wait; return a Rich renderable describing the result."""
        if self.state.engagement_id is None:
            return Text("No engagement selected.", style="red")

        cleaned = raw_path.strip().strip("\"'")
        path = Path(cleaned).expanduser()
        try:
            accepted = self.api_client.upload_path(self.state.engagement_id, path, folder=folder)
            final = self.api_client.wait_upload(self.state.engagement_id, accepted.upload_id)
        except CliApiError as exc:
            return error_panel(exc)
        except (FileNotFoundError, ValueError, OSError) as exc:
            return Text(str(exc), style="red")

        return upload_status_panel(final)
