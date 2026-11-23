"""Citation line formatting."""

from __future__ import annotations

from rich.text import Text

from backend.application.api.contracts.v1.responses import CitationResponse


def format_citation_line(citation: CitationResponse) -> Text:
    location = citation.document_path
    if citation.page is not None:
        location = f"{location} (p. {citation.page})"
    if citation.heading_path:
        location = f"{location} — {' / '.join(citation.heading_path)}"
    line = Text()
    line.append(f"[{citation.marker}] {location}\n", style="bold")
    line.append(citation.snippet, style="dim")
    return line
