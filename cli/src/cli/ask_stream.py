"""Shared ask-stream event consumer."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import cast

from backend.application.api.contracts.v1.responses import AskResponse
from backend.domain.errors import ErrorCode
from cli.client import CliApiError
from cli.formatting.tool_progress import ToolProgressCorrelator


def coerce_sources(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        return []
    typed: list[dict[str, object]] = []
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            typed.append(cast(dict[str, object], item))
    return typed


@dataclass
class AskStreamHandlers:
    """Callbacks while consuming SSE progress events."""

    on_stage: Callable[[str], None] | None = None
    on_sources: Callable[[list[dict[str, object]]], None] | None = None
    on_tool_call: Callable[[str], None] | None = None
    on_tool_result_lines: Callable[[list[str]], None] | None = None
    on_thinking_delta: Callable[[str], None] | None = None
    on_thinking_done: Callable[[float], None] | None = None
    on_before_final: Callable[[], None] | None = None
    work_stages: frozenset[str] = field(
        default_factory=lambda: frozenset({"agent", "tool", "retrieve", "grade", "condense"})
    )
    on_work_stage: Callable[[], None] | None = None


def consume_ask_stream(
    events: Iterable[dict[str, object]],
    *,
    handlers: AskStreamHandlers,
    tools: ToolProgressCorrelator | None = None,
) -> AskResponse | None:
    """Walk stream events; return final AskResponse when present."""
    response: AskResponse | None = None

    for event in events:
        event_type = event.get("type")
        if event_type == "stage":
            stage = str(event.get("stage", ""))
            if handlers.on_stage is not None:
                handlers.on_stage(stage)
            if stage in handlers.work_stages and handlers.on_work_stage is not None:
                handlers.on_work_stage()
        elif event_type == "sources":
            sources = coerce_sources(event.get("sources"))
            if tools is not None:
                tools.on_sources(sources)
            elif handlers.on_sources is not None:
                handlers.on_sources(sources)
        elif event_type == "tool_call":
            if handlers.on_work_stage is not None:
                handlers.on_work_stage()
            name = str(event.get("name", "tool"))
            arguments = str(event.get("arguments", ""))
            if tools is not None and handlers.on_tool_call is not None:
                line = tools.on_tool_call(name=name, arguments=arguments)
                handlers.on_tool_call(line.plain)
            elif handlers.on_tool_call is not None:
                handlers.on_tool_call(f"{name} {arguments}".strip())
        elif event_type == "tool_result":
            if handlers.on_work_stage is not None:
                handlers.on_work_stage()
            name = str(event.get("name", "tool"))
            summary = str(event.get("summary", ""))
            if tools is not None and handlers.on_tool_result_lines is not None:
                lines = [text.plain for text in tools.on_tool_result(name=name, summary=summary)]
                if lines:
                    handlers.on_tool_result_lines(lines)
            elif handlers.on_tool_result_lines is not None:
                short = summary.strip()
                if short:
                    handlers.on_tool_result_lines([short])
        elif event_type == "thinking_delta":
            text = event.get("text")
            if isinstance(text, str) and text and handlers.on_thinking_delta is not None:
                handlers.on_thinking_delta(text)
        elif event_type == "thinking_done":
            if handlers.on_work_stage is not None:
                handlers.on_work_stage()
            if handlers.on_thinking_done is not None:
                raw = event.get("duration_seconds", 0)
                duration = float(raw) if isinstance(raw, (int, float, str)) else 0.0
                handlers.on_thinking_done(duration)
        elif event_type == "final":
            if handlers.on_before_final is not None:
                handlers.on_before_final()
            final = event.get("response")
            if isinstance(final, AskResponse):
                response = final
            else:
                raise CliApiError(
                    code=ErrorCode.INTERNAL_ERROR,
                    detail="stream final payload missing",
                    status=500,
                    request_id=None,
                )

    return response
