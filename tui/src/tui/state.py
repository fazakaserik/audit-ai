"""Shared mutable state for the AIditor TUI."""

from __future__ import annotations

from uuid import UUID

from backend.application.api.contracts.v1.responses import (
    AskResponse,
    CitationResponse,
    LlmUsageResponse,
)
from backend.domain.engagement import EngagementId
from cli.client import unwrap_answer, unwrap_insufficient


class AppState:
    """Engagement/session context shared across screens."""

    def __init__(self) -> None:
        self.engagement_id: EngagementId | None = None
        self.engagement_name: str | None = None
        self.session_id: UUID | None = None
        self.session_title: str | None = None
        self.last_answer: AskResponse | None = None
        self.last_citations: tuple[CitationResponse, ...] = ()
        self.last_usage: LlmUsageResponse | None = None
        self.session_total_tokens: int = 0

    def clear_usage(self) -> None:
        self.last_usage = None
        self.session_total_tokens = 0

    def clear_session(self) -> None:
        self.session_id = None
        self.session_title = None
        self.last_answer = None
        self.last_citations = ()
        self.clear_usage()

    def set_engagement(self, engagement_id: EngagementId, name: str) -> None:
        self.engagement_id = engagement_id
        self.engagement_name = name
        self.clear_session()

    def apply_usage_from_answer(self, response: AskResponse) -> None:
        self.last_usage = response.usage
        self.session_total_tokens = response.session_total_tokens

    def collect_citations(self, response: AskResponse) -> tuple[CitationResponse, ...]:
        answered = unwrap_answer(response)
        if answered is not None:
            return answered.citations
        insufficient = unwrap_insufficient(response)
        if insufficient is not None:
            return insufficient.partial_citations
        return ()


def format_token_count(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def format_engagement_label(state: AppState) -> str:
    if state.engagement_name and state.engagement_id:
        return f"{state.engagement_name} ({state.engagement_id})"
    if state.engagement_id:
        return str(state.engagement_id)
    return "no engagement"


def format_session_label(state: AppState) -> str:
    if state.session_title:
        return state.session_title
    if state.session_id:
        return str(state.session_id)
    return "new session"


def format_token_stats(state: AppState) -> str:
    """Classic toolbar: ctx · last · session token counts."""
    usage = state.last_usage
    ctx = format_token_count(usage.prompt_tokens if usage is not None else None)
    last = format_token_count(usage.total_tokens if usage is not None else None)
    session = (
        format_token_count(state.session_total_tokens)
        if usage is not None or state.session_total_tokens > 0
        else "—"
    )
    return f"ctx {ctx} · last {last} · session {session}"


def format_status_bar(state: AppState) -> str:
    """Bottom bar: session on the left, token stats on the right."""
    return f" {format_session_label(state)}  ·  {format_token_stats(state)} "


def format_compact_header(state: AppState) -> str:
    """Top compact bar: engagement + token stats (replaces AIditor title in chat)."""
    return f" {format_engagement_label(state)}  ·  {format_token_stats(state)} "
