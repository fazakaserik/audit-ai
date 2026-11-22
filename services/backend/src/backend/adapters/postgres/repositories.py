"""Postgres repository adapters mapping ORM rows to frozen domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import assert_never
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.adapters.postgres.models import (
    DocumentRow,
    EngagementRow,
    SessionRow,
    SessionTurnRow,
)
from domain.answer import (
    Answer,
    Answered,
    AnswerStatus,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    Question,
    SuggestedClientQuestion,
)
from domain.document import ContentType, Document, DocumentId, DocumentPath, FolderPath
from domain.engagement import Engagement, EngagementId
from domain.errors import ConflictError, NotFoundError
from domain.passage import PassageId
from domain.session import Session, SessionId, Turn, TurnId


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _engagement_from_row(row: EngagementRow) -> Engagement:
    return Engagement(
        id=row.id,
        name=row.name,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _document_from_row(row: DocumentRow) -> Document:
    return Document(
        id=DocumentId(row.id),
        engagement_id=row.engagement_id,
        path=row.path,
        content_type=ContentType(row.content_type),
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        version=row.version,
        searchable=row.searchable,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _session_from_row(row: SessionRow) -> Session:
    return Session(
        id=SessionId(row.id),
        engagement_id=row.engagement_id,
        title=row.title,
        turn_count=row.turn_count,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _citation_from_dict(raw: dict[str, object]) -> Citation:
    page_raw = raw.get("page")
    page = int(page_raw) if isinstance(page_raw, int) else None
    heading_raw = raw.get("heading_path", ())
    if isinstance(heading_raw, list):
        heading_path = tuple(str(item) for item in heading_raw)
    elif isinstance(heading_raw, tuple):
        heading_path = tuple(str(item) for item in heading_raw)
    else:
        heading_path = ()
    return Citation(
        marker=int(raw["marker"]),  # type: ignore[arg-type]
        passage_id=PassageId(UUID(str(raw["passage_id"]))),
        document_id=DocumentId(UUID(str(raw["document_id"]))),
        document_path=str(raw["document_path"]),
        page=page,
        heading_path=heading_path,
        snippet=str(raw["snippet"]),
        score=float(raw["score"]),  # type: ignore[arg-type]
    )


def _answer_from_dict(raw: dict[str, object]) -> Answer:
    status = str(raw["status"])
    if status == AnswerStatus.ANSWERED:
        citations_raw = raw.get("citations", [])
        if not isinstance(citations_raw, list):
            citations_raw = []
        citations = tuple(
            _citation_from_dict(item) for item in citations_raw if isinstance(item, dict)
        )
        return Answered(text=str(raw["text"]), citations=citations)
    if status == AnswerStatus.INSUFFICIENT_EVIDENCE:
        partial_raw = raw.get("partial_citations", [])
        if not isinstance(partial_raw, list):
            partial_raw = []
        suggestions_raw = raw.get("suggested_client_questions", [])
        if not isinstance(suggestions_raw, list):
            suggestions_raw = []
        suggestions: list[SuggestedClientQuestion] = []
        for item in suggestions_raw:
            if isinstance(item, dict):
                suggestions.append(
                    SuggestedClientQuestion(
                        question=str(item["question"]),
                        rationale=str(item["rationale"]),
                    )
                )
        return InsufficientEvidence(
            reason=InsufficientReason(str(raw["reason"])),
            partial_citations=tuple(
                _citation_from_dict(item) for item in partial_raw if isinstance(item, dict)
            ),
            suggested_client_questions=tuple(suggestions),
        )
    msg = f"unknown answer status: {status}"
    raise ValueError(msg)


def _turn_from_row(row: SessionTurnRow) -> Turn:
    question_data = row.question
    return Turn(
        id=TurnId(row.id),
        session_id=SessionId(row.session_id),
        ordinal=row.ordinal,
        question=Question.model_validate(question_data),
        standalone_question=row.standalone_question,
        answer=_answer_from_dict(row.answer),
        created_at=_aware(row.created_at),
    )


def _answer_to_dict(answer: Answer) -> dict[str, object]:
    match answer:
        case Answered():
            return answer.model_dump(mode="json")
        case InsufficientEvidence():
            return answer.model_dump(mode="json")
        case _ as unreachable:
            assert_never(unreachable)


class PostgresEngagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, engagement: Engagement) -> Engagement:
        row = EngagementRow(
            id=engagement.id,
            name=engagement.name,
            created_at=engagement.created_at,
            updated_at=engagement.updated_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(f"engagement already exists: {engagement.id}") from exc
        return _engagement_from_row(row)

    async def get(self, engagement_id: EngagementId) -> Engagement | None:
        row = await self._session.get(EngagementRow, engagement_id)
        if row is None:
            return None
        return _engagement_from_row(row)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]:
        total_stmt = select(func.count()).select_from(EngagementRow)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(EngagementRow)
            .order_by(EngagementRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_engagement_from_row(row) for row in rows], total

    async def count_documents(self, engagement_id: EngagementId) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentRow)
            .where(DocumentRow.engagement_id == engagement_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())


class PostgresDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, document: Document) -> Document:
        stmt = (
            pg_insert(DocumentRow)
            .values(
                id=document.id,
                engagement_id=document.engagement_id,
                path=document.path,
                content_type=document.content_type.value,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                version=document.version,
                searchable=document.searchable,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            .on_conflict_do_update(
                constraint="uq_documents_engagement_path",
                set_={
                    "content_type": document.content_type.value,
                    "size_bytes": document.size_bytes,
                    "sha256": document.sha256,
                    "version": document.version,
                    "searchable": document.searchable,
                    "updated_at": document.updated_at,
                },
            )
            .returning(DocumentRow)
        )
        row = (await self._session.execute(stmt)).scalar_one()
        await self._session.flush()
        return _document_from_row(row)

    async def get_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> Document | None:
        stmt = select(DocumentRow).where(
            DocumentRow.engagement_id == engagement_id,
            DocumentRow.path == path,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _document_from_row(row)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        prefix: FolderPath | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        filters = [DocumentRow.engagement_id == engagement_id]
        if prefix is not None and prefix != "":
            filters.append(DocumentRow.path.like(f"{prefix}%"))

        total_stmt = select(func.count()).select_from(DocumentRow).where(*filters)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(DocumentRow)
            .where(*filters)
            .order_by(DocumentRow.path.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_document_from_row(row) for row in rows], total


class PostgresSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: Session) -> Session:
        row = SessionRow(
            id=session.id,
            engagement_id=session.engagement_id,
            title=session.title,
            turn_count=session.turn_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _session_from_row(row)

    async def get(
        self,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> Session | None:
        stmt = select(SessionRow).where(
            SessionRow.id == session_id,
            SessionRow.engagement_id == engagement_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _session_from_row(row)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Session], int]:
        filters = [SessionRow.engagement_id == engagement_id]
        total_stmt = select(func.count()).select_from(SessionRow).where(*filters)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(SessionRow)
            .where(*filters)
            .order_by(SessionRow.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_session_from_row(row) for row in rows], total

    async def add_turn(self, turn: Turn) -> Turn:
        row = SessionTurnRow(
            id=turn.id,
            session_id=turn.session_id,
            ordinal=turn.ordinal,
            question=turn.question.model_dump(mode="json"),
            standalone_question=turn.standalone_question,
            answer=_answer_to_dict(turn.answer),
            created_at=turn.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _turn_from_row(row)

    async def list_turns(self, session_id: SessionId) -> list[Turn]:
        stmt = (
            select(SessionTurnRow)
            .where(SessionTurnRow.session_id == session_id)
            .order_by(SessionTurnRow.ordinal.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_turn_from_row(row) for row in rows]

    async def bump_turn_count(
        self,
        session_id: SessionId,
        *,
        title: str | None = None,
    ) -> Session:
        row = await self._session.get(SessionRow, session_id)
        if row is None:
            raise NotFoundError(f"session not found: {session_id}")
        row.turn_count += 1
        row.updated_at = datetime.now(UTC)
        if title is not None:
            row.title = title
        await self._session.flush()
        return _session_from_row(row)
