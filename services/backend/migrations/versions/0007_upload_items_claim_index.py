"""Cover claim_next ORDER BY created_at in upload_items status index.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_upload_items_status_next_attempt", table_name="upload_items")
    op.create_index(
        "ix_upload_items_status_next_attempt",
        "upload_items",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_upload_items_status_next_attempt", table_name="upload_items")
    op.create_index(
        "ix_upload_items_status_next_attempt",
        "upload_items",
        ["status", "next_attempt_at"],
        unique=False,
    )
