"""Shared OptionList helpers."""

from __future__ import annotations

from textual.widgets import OptionList
from textual.widgets.option_list import Option


def highlight_first_enabled(option_list: OptionList) -> None:
    """Highlight the first enabled option so Enter works without pressing Down first."""
    for index in range(option_list.option_count):
        option = option_list.get_option_at_index(index)
        if not option.disabled:
            option_list.highlighted = index
            return
    option_list.highlighted = None


def begin_picker_load(option_list: OptionList) -> None:
    option_list.clear_options()


def finish_picker_load(option_list: OptionList, options: list[Option]) -> None:
    for item in options:
        option_list.add_option(item)
    highlight_first_enabled(option_list)
    option_list.focus()


def show_picker_error(option_list: OptionList, message: str) -> None:
    begin_picker_load(option_list)
    option_list.add_option(Option(message, id="error", disabled=True))


def show_picker_empty(option_list: OptionList, message: str) -> None:
    begin_picker_load(option_list)
    option_list.add_option(Option(message, disabled=True))
