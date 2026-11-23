"""Live + finished thought-process collapsible widgets."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Collapsible, Static


class LiveThoughtProcess(Collapsible):
    """Expanded while work streams in; collapsed when finished."""

    # Collapsible defaults to ALLOW_SELECT=False; allow selecting streamed text.
    ALLOW_SELECT = True

    def __init__(self) -> None:
        self._body = Static("", classes="thinking-body", markup=False)
        self._buffer = ""
        super().__init__(
            self._body,
            title="Thinking…",
            collapsed=False,
            classes="thinking-collapsible",
        )

    def reset(self) -> None:
        """Reuse this widget for a new stream."""
        self._buffer = ""
        self._body.update("")
        self.title = "Thinking…"
        self.collapsed = False

    def append_text(self, text: str) -> None:
        if not text:
            return
        self._buffer += text
        self._body.update(Text(self._buffer, style="dim"))

    def finish(self, *, duration_seconds: float) -> None:
        if not self._buffer.strip():
            self._buffer = "(no details)"
            self._body.update(Text(self._buffer, style="dim"))
        if duration_seconds > 0:
            self.title = f"Thought process ({duration_seconds:.1f}s)"
        else:
            self.title = "Thought process"
        self.collapsed = True


def make_thinking_collapsible(
    body: str,
    *,
    duration_seconds: float | None = None,
) -> Collapsible:
    """Collapsed summary for resumed sessions (already finished)."""
    if duration_seconds is not None and duration_seconds > 0:
        title = f"Thought process ({duration_seconds:.1f}s)"
    else:
        title = "Thought process"
    content = Static(Text(body, style="dim"), classes="thinking-body", markup=False)
    return Collapsible(
        content,
        title=title,
        collapsed=True,
        classes="thinking-collapsible",
    )
