"""Modal document browser."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from cli.client import CliApiError
from tui.chat_render import document_bytes_renderable
from tui.screens.chat import ChatScreen
from tui.widgets.option_helpers import (
    begin_picker_load,
    finish_picker_load,
    show_picker_error,
)

if TYPE_CHECKING:
    from tui.app import AiditorApp

_PARENT = "parent-dir"


class DocumentsModal(ModalScreen[None]):
    """Browse folders and open a document into the chat log when possible."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    def __init__(self, start_folder: str = "") -> None:
        super().__init__()
        self._current = start_folder.strip().strip("/")

    @property
    def aiditor(self) -> AiditorApp:
        return cast(AiditorApp, self.app)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("Documents", id="modal-title")
            yield OptionList(id="modal-list")
            yield Static("Enter open  ·  Esc close", id="modal-help")

    def on_mount(self) -> None:
        self._load()

    def _join(self, child: str) -> str:
        if not self._current:
            return child
        return f"{self._current.rstrip('/')}/{child}"

    def _parent_folder(self) -> str:
        if not self._current or "/" not in self._current:
            return ""
        return self._current.rsplit("/", 1)[0]

    def _basename(self, path: str) -> str:
        if self._current and path.startswith(self._current.rstrip("/") + "/"):
            return path[len(self._current.rstrip("/")) + 1 :]
        return path.rsplit("/", 1)[-1]

    def _load(self) -> None:
        option_list = self.query_one("#modal-list", OptionList)
        begin_picker_load(option_list)
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            option_list.add_option(Option("No engagement selected.", disabled=True))
            return
        location = self._current if self._current else "/"
        self.query_one("#modal-title", Label).update(f"Browse {location}")
        try:
            listing = self.aiditor.api_client.list_documents(
                engagement_id,
                prefix=self._current or None,
                depth=1,
                limit=200,
                offset=0,
            )
        except CliApiError as exc:
            show_picker_error(option_list, f"Error: {exc.detail}")
            return
        options: list[Option] = []
        if self._current:
            options.append(Option("..", id=_PARENT))
        for folder in listing.folders:
            options.append(Option(f"[{folder}]", id=f"dir:{folder}"))
        for doc in listing.items:
            name = self._basename(doc.path)
            options.append(
                Option(
                    f"{name}  ({doc.size_bytes} bytes, {doc.content_type.value})",
                    id=f"doc:{doc.path}",
                )
            )
        if not options:
            options.append(Option("(empty)", disabled=True))
        finish_picker_load(option_list, options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None:
            return
        if option_id == _PARENT:
            self._current = self._parent_folder()
            self._load()
            return
        if option_id.startswith("dir:"):
            self._current = self._join(option_id.removeprefix("dir:"))
            self._load()
            return
        if option_id.startswith("doc:"):
            self._open_document(option_id.removeprefix("doc:"))

    def _open_document(self, path: str) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            return
        try:
            content = self.aiditor.api_client.get_document_content(engagement_id, path)
        except CliApiError as exc:
            self.aiditor.notify(str(exc.detail), severity="error")
            return
        renderable = document_bytes_renderable(path, content)
        self.dismiss(None)
        active = self.aiditor.screen
        if isinstance(active, ChatScreen):
            active.write_renderable(renderable)
        else:
            self.aiditor.notify(f"Opened {path}", severity="information")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
