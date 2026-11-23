"""Rename passages table and indexes to chunks.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("passages", "chunks")
    op.execute("ALTER INDEX IF EXISTS ix_passages_document_id RENAME TO ix_chunks_document_id")
    op.execute(
        "ALTER INDEX IF EXISTS ix_passages_document_version RENAME TO ix_chunks_document_version"
    )
    op.execute("ALTER INDEX IF EXISTS ix_passages_search_vector RENAME TO ix_chunks_search_vector")


def downgrade() -> None:
    op.execute("ALTER INDEX IF EXISTS ix_chunks_search_vector RENAME TO ix_passages_search_vector")
    op.execute(
        "ALTER INDEX IF EXISTS ix_chunks_document_version RENAME TO ix_passages_document_version"
    )
    op.execute("ALTER INDEX IF EXISTS ix_chunks_document_id RENAME TO ix_passages_document_id")
    op.rename_table("chunks", "passages")
