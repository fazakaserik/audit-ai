"""Shared human-readable labels for pickers."""

from __future__ import annotations

from rich.text import Text

from backend.application.api.contracts.v1.responses import (
    EngagementResponse,
    SessionSummaryResponse,
    UploadSummaryResponse,
)


def engagement_label(item: EngagementResponse) -> Text:
    # Use Text so bracketed counts are not parsed as Rich markup.
    return Text(f"{item.name}  ({item.id})  · {item.document_count} docs")


def session_label(item: SessionSummaryResponse) -> Text:
    stamp = item.updated_at.strftime("%Y-%m-%d %H:%M")
    return Text(f"{stamp}  {item.title}  ({item.turn_count} turns)  {item.id}")


def upload_label(item: UploadSummaryResponse) -> Text:
    return Text(
        f"{item.target_folder}  ({item.id})  · {item.status.value}, {item.created_at.isoformat()}"
    )
