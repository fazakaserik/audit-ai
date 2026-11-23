"""Pure presentation helpers shared by CLI and TUI."""

from cli.formatting.citations import format_citation_line
from cli.formatting.copy import INSUFFICIENT_ANSWER_LEAD, NO_SAVED_THOUGHT_PROCESS
from cli.formatting.errors import format_error_lines
from cli.formatting.labels import stage_label, tool_label
from cli.formatting.tool_progress import ToolProgressCorrelator
from cli.formatting.tools import (
    SOURCE_PATHS_MAX,
    TOOL_DETAIL_MAX,
    dedupe_sources_by_path,
    parse_tool_args,
    short_tool_result,
    source_progress_lines,
    tool_detail,
    truncate,
)

__all__ = [
    "INSUFFICIENT_ANSWER_LEAD",
    "NO_SAVED_THOUGHT_PROCESS",
    "SOURCE_PATHS_MAX",
    "TOOL_DETAIL_MAX",
    "ToolProgressCorrelator",
    "dedupe_sources_by_path",
    "format_citation_line",
    "format_error_lines",
    "parse_tool_args",
    "short_tool_result",
    "source_progress_lines",
    "stage_label",
    "tool_detail",
    "tool_label",
    "truncate",
]
