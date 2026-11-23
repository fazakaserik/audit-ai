"""Human-readable duration formatting."""

from __future__ import annotations

from datetime import datetime


def format_duration_ms(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "—"
    if duration_ms < 1000:
        return f"{duration_ms}ms"
    seconds = duration_ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    if minutes < 60:
        return f"{minutes}m {rem:.0f}s"
    hours = minutes // 60
    rem_m = minutes % 60
    return f"{hours}h {rem_m}m"


def format_elapsed(
    started: datetime | None,
    finished: datetime | None,
    *,
    now: datetime | None = None,
) -> str:
    if started is None:
        return "—"
    end = finished if finished is not None else now
    if end is None:
        return "—"
    ms = max(0, int((end - started).total_seconds() * 1000))
    return format_duration_ms(ms)
