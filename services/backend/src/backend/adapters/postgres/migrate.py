"""Apply Alembic migrations programmatically (e.g. API startup)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"
_SCRIPT_LOCATION = _BACKEND_ROOT / "migrations"


def upgrade_head(database_url: str) -> None:
    """Upgrade the database schema to the latest Alembic revision."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", database_url)
    # Prefer this over Settings() when env.py runs inside command.upgrade.
    cfg.attributes["database_url"] = database_url
    command.upgrade(cfg, "head")
