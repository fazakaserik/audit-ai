"""Chat prompt input with numpad-slash support."""

from __future__ import annotations

from textual import events
from textual.widgets import Input

# Numpad / Unicode division slash variants some hosts emit instead of ASCII "/".
_SLASH_CHARS = frozenset(
    {
        "/",
        "\u2215",  # DIVISION SLASH
        "\u2044",  # FRACTION SLASH
        "\uff0f",  # FULLWIDTH SOLIDUS
    }
)


class ChatInput(Input):
    """Input that accepts keypad divide as ASCII slash."""

    def check_consume_key(self, key: str, character: str | None) -> bool:
        if character in _SLASH_CHARS:
            return True
        if character is None and ("divide" in key or key in {"slash", "solidus"}):
            return True
        return super().check_consume_key(key, character)

    async def _on_key(self, event: events.Key) -> None:
        if event.character in _SLASH_CHARS - {"/"}:
            self.insert_text_at_cursor("/")
            event.prevent_default()
            event.stop()
            return
        if event.character is None and ("divide" in event.key or event.key in {"slash", "solidus"}):
            self.insert_text_at_cursor("/")
            event.prevent_default()
            event.stop()
            return
        await super()._on_key(event)
