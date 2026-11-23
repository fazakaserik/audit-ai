"""Sticky brand header with AIditor wordmark or live engagement/token chrome."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from tui import __version__
from tui.state import AppState, format_compact_header, format_token_stats

_WORDMARK = (
    r"  █████╗ ██╗██████╗ ██╗████████╗ ██████╗ ██████╗ ",
    r" ██╔══██╗██║██╔══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗",
    r" ███████║██║██║  ██║██║   ██║   ██║   ██║██████╔╝",
    r" ██╔══██║██║██║  ██║██║   ██║   ██║   ██║██╔══██╗",
    r" ██║  ██║██║██████╔╝██║   ██║   ╚██████╔╝██║  ██║",
    r" ╚═╝  ╚═╝╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
)

_LINE_COLORS = (
    "bright_cyan",
    "cyan",
    "dark_cyan",
    "#2E8B57",
    "green",
    "bright_green",
)


class BrandHeader(Static):
    """Docked header: full ASCII wordmark, or compact engagement + tokens."""

    compact: reactive[bool] = reactive(False, layout=True)

    def __init__(
        self,
        state: AppState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._state = state

    def on_mount(self) -> None:
        self.refresh_from_state()

    def watch_compact(self, compact: bool) -> None:
        self.set_class(compact, "compact")
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        if self.compact:
            line = Text()
            line.append(format_compact_header(self._state).rstrip(), style="bold")
            self.update(line)
            return

        body = Text()
        for index, (row, color) in enumerate(zip(_WORDMARK, _LINE_COLORS, strict=True)):
            if index:
                body.append("\n")
            body.append(row, style=color)
        body.append("\n\n")
        body.append("AIditor", style="bold")
        body.append(f"  v{__version__}", style="dim")
        body.append("  — interactive mode", style="dim")
        if self._state.engagement_id is not None:
            body.append("\n")
            body.append(format_compact_header(self._state).strip(), style="dim")
        elif format_token_stats(self._state) != "ctx — · last — · session —":
            body.append("\n")
            body.append(format_token_stats(self._state), style="dim")
        self.update(body)
