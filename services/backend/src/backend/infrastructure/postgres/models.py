"""SQLAlchemy ORM tables for Postgres + pgvector."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for adapter ORM models."""


class EngagementRow(Base):
    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    documents: Mapped[list[DocumentRow]] = relationship(back_populates="engagement")
    uploads: Mapped[list[UploadRow]] = relationship(back_populates="engagement")
    sessions: Mapped[list[SessionRow]] = relationship(back_populates="engagement")


class UploadRow(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        String(63),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_folder: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engagement: Mapped[EngagementRow] = relationship(back_populates="uploads")
    items: Mapped[list[UploadItemRow]] = relationship(back_populates="upload")


class UploadItemRow(Base):
    __tablename__ = "upload_items"
    __table_args__: tuple[Index, ...] = (
        Index(
            "ix_upload_items_status_next_attempt",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_storage_key: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    embedding_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_token_sum: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    upload: Mapped[UploadRow] = relationship(back_populates="items")


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("engagement_id", "path", name="uq_documents_engagement_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        String(63),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engagement: Mapped[EngagementRow] = relationship(back_populates="documents")
    chunks: Mapped[list[ChunkRow]] = relationship(back_populates="document")


class ChunkRow(Base):
    __tablename__ = "chunks"
    __table_args__: tuple[Index, ...] = (
        Index("ix_chunks_document_version", "document_id", "document_version"),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default="{}",
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__: tuple[Index, ...] = (
        Index("ix_sessions_engagement_updated", "engagement_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        String(63),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engagement: Mapped[EngagementRow] = relationship(back_populates="sessions")
    turns: Mapped[list[SessionTurnRow]] = relationship(back_populates="session")


class SessionTurnRow(Base):
    __tablename__ = "session_turns"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("session_id", "ordinal", name="uq_session_turns_session_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_folder_scope: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    question_auditor_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    question_topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    standalone_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_status: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    insufficient_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thinking_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[SessionRow] = relationship(back_populates="turns")
    citations: Mapped[list[TurnCitationRow]] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
    )
    suggested_questions: Mapped[list[TurnSuggestedQuestionRow]] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
    )


class TurnCitationRow(Base):
    __tablename__ = "turn_citations"
    __table_args__: tuple[UniqueConstraint, Index] = (
        UniqueConstraint("turn_id", "kind", "marker", name="uq_turn_citations_turn_kind_marker"),
        Index("ix_turn_citations_turn_id", "turn_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("session_turns.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    marker: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default="{}",
    )
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    turn: Mapped[SessionTurnRow] = relationship(back_populates="citations")


class TurnSuggestedQuestionRow(Base):
    __tablename__ = "turn_suggested_questions"
    __table_args__: tuple[UniqueConstraint, Index] = (
        UniqueConstraint(
            "turn_id",
            "ordinal",
            name="uq_turn_suggested_questions_turn_ordinal",
        ),
        Index("ix_turn_suggested_questions_turn_id", "turn_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("session_turns.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    turn: Mapped[SessionTurnRow] = relationship(back_populates="suggested_questions")
