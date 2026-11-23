"""Tests for OptionList helpers."""

from __future__ import annotations

from typing import cast

from textual.widgets import OptionList

from tui.widgets.option_helpers import highlight_first_enabled


class _FakeOption:
    def __init__(self, *, disabled: bool = False, id: str | None = None) -> None:
        self.disabled = disabled
        self.id = id


class _FakeOptionList:
    def __init__(self, options: list[_FakeOption]) -> None:
        self._options = options
        self.highlighted: int | None = None

    @property
    def option_count(self) -> int:
        return len(self._options)

    def get_option_at_index(self, index: int) -> _FakeOption:
        return self._options[index]


def test_highlight_first_enabled_skips_disabled() -> None:
    option_list = _FakeOptionList(
        [
            _FakeOption(disabled=True, id="disabled"),
            _FakeOption(id="first"),
            _FakeOption(id="second"),
        ]
    )
    highlight_first_enabled(cast(OptionList, option_list))
    assert option_list.highlighted == 1
