"""Add per-item ingest timing and embedding token metrics.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "upload_items",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "upload_items",
        sa.Column("processing_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "upload_items",
        sa.Column("embedding_prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "upload_items",
        sa.Column("embedding_total_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "upload_items",
        sa.Column("chunk_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "upload_items",
        sa.Column("chunk_token_sum", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("upload_items", "chunk_token_sum")
    op.drop_column("upload_items", "chunk_count")
    op.drop_column("upload_items", "embedding_total_tokens")
    op.drop_column("upload_items", "embedding_prompt_tokens")
    op.drop_column("upload_items", "processing_finished_at")
    op.drop_column("upload_items", "processing_started_at")
