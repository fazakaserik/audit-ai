"""Initial schema with pgvector.

Revision ID: 0001
Revises:
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "engagements",
        sa.Column("id", sa.String(length=63), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id",
            sa.String(length=63),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_folder", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_uploads_engagement_id", "uploads", ["engagement_id"])

    op.create_table(
        "upload_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "upload_id", sa.Uuid(), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_path", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=200), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_storage_key", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_upload_items_upload_id", "upload_items", ["upload_id"])
    op.create_index(
        "ix_upload_items_status_next_attempt", "upload_items", ["status", "next_attempt_at"]
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id",
            sa.String(length=63),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("searchable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("engagement_id", "path", name="uq_documents_engagement_path"),
    )
    op.create_index("ix_documents_engagement_id", "documents", ["engagement_id"])

    op.create_table(
        "passages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_passages_document_id", "passages", ["document_id"])
    op.create_index("ix_passages_document_version", "passages", ["document_id", "document_version"])
    op.create_index(
        "ix_passages_search_vector", "passages", ["search_vector"], postgresql_using="gin"
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id",
            sa.String(length=63),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_engagement_id", "sessions", ["engagement_id"])
    op.create_index("ix_sessions_engagement_updated", "sessions", ["engagement_id", "updated_at"])

    op.create_table(
        "session_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("question", postgresql.JSONB(), nullable=False),
        sa.Column("standalone_question", sa.Text(), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "ordinal", name="uq_session_turns_session_ordinal"),
    )
    op.create_index("ix_session_turns_session_id", "session_turns", ["session_id"])


def downgrade() -> None:
    op.drop_table("session_turns")
    op.drop_table("sessions")
    op.drop_table("passages")
    op.drop_table("documents")
    op.drop_table("upload_items")
    op.drop_table("uploads")
    op.drop_table("engagements")
