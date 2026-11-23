"""Add thinking fields to session turns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_turns", sa.Column("thinking_text", sa.Text(), nullable=True))
    op.add_column("session_turns", sa.Column("thinking_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("session_turns", "thinking_seconds")
    op.drop_column("session_turns", "thinking_text")
