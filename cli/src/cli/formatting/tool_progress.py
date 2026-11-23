"""Correlate tool_call → sources → tool_result into compact lines."""

from __future__ import annotations

from rich.text import Text

from cli.formatting.tools import (
    SOURCE_PATHS_MAX,
    dedupe_sources_by_path,
    short_tool_result,
    source_progress_lines,
    tool_call_line,
)


class ToolProgressCorrelator:
    """Shared tool progress correlation for CLI stdout and TUI chat log."""

    def __init__(self) -> None:
        self._pending_sources: list[dict[str, object]] = []

    def on_tool_call(self, *, name: str, arguments: str) -> Text:
        self._pending_sources = []
        return Text(tool_call_line(name=name, arguments=arguments), style="dim")

    def on_sources(self, sources: list[dict[str, object]]) -> None:
        self._pending_sources = list(sources)

    def on_tool_result(self, *, name: str, summary: str) -> list[Text]:
        sources = self._pending_sources
        self._pending_sources = []
        lines: list[Text] = []
        if sources:
            unique = dedupe_sources_by_path(sources)
            hits = len(sources)
            docs = len(unique)
            lines.append(Text(f"  {hits} hits · {docs} docs", style="dim"))
            shown = unique[:SOURCE_PATHS_MAX]
            for path, score in shown:
                if score is None:
                    lines.append(Text(f"  · {path}", style="dim"))
                else:
                    lines.append(Text(f"  · {path}  {score:.2f}", style="dim"))
            remaining = len(unique) - len(shown)
            if remaining > 0:
                lines.append(Text(f"  · +{remaining} more", style="dim"))
            return lines
        short = short_tool_result(name, summary)
        if short:
            lines.append(Text(f"  {short}", style="dim"))
        return lines

    @staticmethod
    def sources_progress_texts(sources: list[dict[str, object]]) -> list[Text]:
        return [Text(line, style="dim") for line in source_progress_lines(sources)]
