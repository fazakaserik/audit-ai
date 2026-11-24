"""Offline assertions for explicit Compose credentials (no silent password fallback)."""

from __future__ import annotations

from pathlib import Path

from backend.config import Settings

_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE = _ROOT / "deployment" / "docker-compose"


def test_compose_requires_explicit_postgres_password() -> None:
    text = (_COMPOSE / "compose.yaml").read_text(encoding="utf-8")
    assert "${POSTGRES_PASSWORD:-audit}" not in text
    assert "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}" in text


def test_settings_still_constructs_with_documented_local_defaults() -> None:
    settings = Settings()
    assert "audit" in settings.database_url
    assert settings.session_max_turns >= settings.session_context_turns
