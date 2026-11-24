"""Offline assertions that Compose publish binds stay on loopback."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE = _ROOT / "deployment" / "docker-compose"


def test_default_compose_publishes_api_on_loopback() -> None:
    text = (_COMPOSE / "compose.yaml").read_text(encoding="utf-8")
    assert "127.0.0.1:8000:8000" in text
    assert '"8000:8000"' not in text
    assert "'8000:8000'" not in text
    assert "compose.lan.yaml" not in text


def test_dev_compose_publishes_db_and_ollama_on_loopback() -> None:
    text = (_COMPOSE / "compose.dev.yaml").read_text(encoding="utf-8")
    assert "127.0.0.1:5432:5432" in text
    assert "127.0.0.1:11434:11434" in text
    assert "compose.lan" not in text


def test_lan_overlay_not_shipped() -> None:
    assert not (_COMPOSE / "compose.lan.yaml").exists()
