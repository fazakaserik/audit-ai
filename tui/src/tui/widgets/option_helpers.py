"""Shared OptionList helpers."""

from __future__ import annotations

from textual.widgets import OptionList


def highlight_first_enabled(option_list: OptionList) -> None:
    """Highlight the first enabled option so Enter works without pressing Down first."""
    for index in range(option_list.option_count):
        option = option_list.get_option_at_index(index)
        if not option.disabled:
            option_list.highlighted = index
            return
    option_list.highlighted = None
