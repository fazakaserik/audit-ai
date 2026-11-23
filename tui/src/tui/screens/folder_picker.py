"""Modal folder picker for choosing an upload target."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from cli.client import CliApiError
from tui.widgets.option_helpers import (
    begin_picker_load,
    finish_picker_load,
    show_picker_error,
)

if TYPE_CHECKING:
    from tui.app import AiditorApp

_USE_CURRENT = "use-current"
_PARENT = "parent-dir"


class FolderPickerModal(ModalScreen[str | None]):
    """Browse folders; Enter on the first option uses the current folder."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, start_folder: str = "") -> None:
        super().__init__()
        self._current = start_folder.strip().strip("/")

    @property
    def aiditor(self) -> AiditorApp:
        return cast("AiditorApp", self.app)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("Select upload folder", id="modal-title")
            yield OptionList(id="modal-list")
            yield Input(
                placeholder="Or type a folder path and press Enter",
                id="folder-input",
            )
            yield Static(
                "Enter use / open  ·  Esc cancel",
                id="modal-help",
            )

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

    def _location_label(self) -> str:
        return self._current if self._current else "/"

    def _load(self) -> None:
        option_list = self.query_one("#modal-list", OptionList)
        begin_picker_load(option_list)
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            option_list.add_option(Option("No engagement selected.", disabled=True))
            return
        location = self._location_label()
        self.query_one("#modal-title", Label).update(f"Select upload folder — {location}")
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
        options: list[Option] = [
            Option(
                Text(f"Use this folder ({location})", style="bold"),
                id=_USE_CURRENT,
            )
        ]
        if self._current:
            options.append(Option(Text(".."), id=_PARENT))
        for folder in listing.folders:
            options.append(Option(Text(f"{folder}/"), id=f"dir:{folder}"))
        finish_picker_load(option_list, options)
        folder_input = self.query_one("#folder-input", Input)
        folder_input.value = self._current
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None:
            return
        if option_id == _USE_CURRENT:
            self.dismiss(self._current)
            return
        if option_id == _PARENT:
            self._current = self._parent_folder()
            self._load()
            return
        if option_id.startswith("dir:"):
            self._current = self._join(option_id.removeprefix("dir:"))
            self._load()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        folder = event.value.strip().strip("/").replace("\\", "/")
        self.dismiss(folder)

    def action_cancel(self) -> None:
        self.dismiss(None)
