"""Duration formatting helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cli.formatting.duration import format_duration_ms, format_elapsed


def test_format_duration_ms_scales() -> None:
    assert format_duration_ms(None) == "—"
    assert format_duration_ms(250) == "250ms"
    assert format_duration_ms(1500) == "1.5s"
    assert format_duration_ms(65_000) == "1m 5s"


def test_format_elapsed_uses_now_when_unfinished() -> None:
    started = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = started + timedelta(seconds=3)
    assert format_elapsed(started, None, now=now) == "3.0s"
    assert format_elapsed(started, None) == "—"
