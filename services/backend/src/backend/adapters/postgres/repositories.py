"""Postgres repository adapters mapping ORM rows to frozen domain models."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.adapters.postgres.models import (
    DocumentRow,
    EngagementRow,
    SessionRow,
    SessionTurnRow,
    TurnCitationRow,
    TurnSuggestedQuestionRow,
    UploadItemRow,
    UploadRow,
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
from domain.chunk import ChunkId
from domain.document import ContentType, Document, DocumentId, DocumentPath, FolderPath
from domain.document.paths import (
    child_folder_name,
    normalize_list_prefix,
    relative_segments,
    within_depth,
)
from domain.engagement import Engagement, EngagementId
from domain.errors import ConflictError, NotFoundError
from domain.session import LlmUsage, Session, SessionId, Turn, TurnId
from domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemId,
    UploadItemStatus,
    UploadStatus,
)


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


def _citation_from_row(row: TurnCitationRow) -> Citation:
    return Citation(
        marker=row.marker,
        chunk_id=ChunkId(row.chunk_id),
        document_id=DocumentId(row.document_id),
        document_path=row.document_path,
        page=row.page,
        heading_path=tuple(row.heading_path or ()),
        snippet=row.snippet,
        score=row.score,
    )


def _citation_row(
    *,
    turn_id: UUID,
    kind: str,
    citation: Citation,
) -> TurnCitationRow:
    return TurnCitationRow(
        id=uuid4(),
        turn_id=turn_id,
        kind=kind,
        marker=citation.marker,
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        document_path=citation.document_path,
        page=citation.page,
        heading_path=list(citation.heading_path),
        snippet=citation.snippet,
        score=citation.score,
    )


def _answer_from_turn_row(row: SessionTurnRow) -> Answer:
    status = row.answer_status
    if status == AnswerStatus.ANSWERED:
        citations = tuple(
            _citation_from_row(item)
            for item in sorted(row.citations, key=lambda c: c.marker)
            if item.kind == "answer"
        )
        text = row.answer_text or ""
        return Answered(text=text, citations=citations)
    if status == AnswerStatus.INSUFFICIENT_EVIDENCE:
        partial = tuple(
            _citation_from_row(item)
            for item in sorted(row.citations, key=lambda c: c.marker)
            if item.kind == "partial"
        )
        suggestions = tuple(
            SuggestedClientQuestion(question=item.question, rationale=item.rationale)
            for item in sorted(row.suggested_questions, key=lambda s: s.ordinal)
        )
        reason_raw = row.insufficient_reason or InsufficientReason.MODEL_JUDGED_INSUFFICIENT.value
        if reason_raw == "no_relevant_passages":
            reason_raw = InsufficientReason.NO_RELEVANT_CHUNKS.value
        return InsufficientEvidence(
            reason=InsufficientReason(reason_raw),
            partial_citations=partial,
            suggested_client_questions=suggestions,
        )
    msg = f"unknown answer status: {status}"
    raise ValueError(msg)


def _upload_from_row(row: UploadRow) -> Upload:
    return Upload(
        id=UploadId(row.id),
        engagement_id=row.engagement_id,
        target_folder=row.target_folder,
        status=UploadStatus(row.status),
        completed_at=_aware(row.completed_at) if row.completed_at is not None else None,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _upload_item_from_row(row: UploadItemRow) -> UploadItem:
    return UploadItem(
        id=UploadItemId(row.id),
        upload_id=UploadId(row.upload_id),
        document_path=row.document_path,
        status=UploadItemStatus(row.status),
        reason=row.reason,
        attempts=row.attempts,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _usage_from_turn_row(row: SessionTurnRow) -> LlmUsage | None:
    if (
        row.usage_prompt_tokens is None
        and row.usage_completion_tokens is None
        and row.usage_total_tokens is None
    ):
        return None
    return LlmUsage(
        prompt_tokens=row.usage_prompt_tokens or 0,
        completion_tokens=row.usage_completion_tokens or 0,
        total_tokens=row.usage_total_tokens or 0,
    )


def _turn_from_row(row: SessionTurnRow) -> Turn:
    return Turn(
        id=TurnId(row.id),
        session_id=SessionId(row.session_id),
        ordinal=row.ordinal,
        question=Question(
            text=row.question_text,
            folder_scope=row.question_folder_scope,
            auditor_role=row.question_auditor_role,
            topic=row.question_topic,
        ),
        standalone_question=row.standalone_question,
        answer=_answer_from_turn_row(row),
        created_at=_aware(row.created_at),
        thinking_text=row.thinking_text,
        thinking_seconds=row.thinking_seconds,
        usage=_usage_from_turn_row(row),
    )


def _populate_answer_rows(row: SessionTurnRow, answer: Answer) -> None:
    match answer:
        case Answered():
            row.answer_status = AnswerStatus.ANSWERED.value
            row.answer_text = answer.text
            row.insufficient_reason = None
            row.citations = [
                _citation_row(turn_id=row.id, kind="answer", citation=citation)
                for citation in answer.citations
            ]
            row.suggested_questions = []
        case InsufficientEvidence():
            row.answer_status = AnswerStatus.INSUFFICIENT_EVIDENCE.value
            row.answer_text = None
            row.insufficient_reason = answer.reason.value
            row.citations = [
                _citation_row(turn_id=row.id, kind="partial", citation=citation)
                for citation in answer.partial_citations
            ]
            row.suggested_questions = [
                TurnSuggestedQuestionRow(
                    id=uuid4(),
                    turn_id=row.id,
                    ordinal=index,
                    question=item.question,
                    rationale=item.rationale,
                )
                for index, item in enumerate(answer.suggested_client_questions)
            ]


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
        depth: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], tuple[str, ...], int]:
        base = normalize_list_prefix(prefix)
        filters = [DocumentRow.engagement_id == engagement_id]
        if base:
            filters.append(DocumentRow.path.like(f"{base}/%"))

        path_stmt = select(DocumentRow.path).where(*filters).order_by(DocumentRow.path.asc())
        paths = list((await self._session.execute(path_stmt)).scalars().all())

        folders: set[str] = set()
        matching_paths: list[str] = []
        for path in paths:
            segments = relative_segments(path, base)
            if segments is None:
                continue
            folder = child_folder_name(segments)
            if folder is not None:
                folders.add(folder)
            if within_depth(segments, depth):
                matching_paths.append(path)

        total = len(matching_paths)
        page_paths = matching_paths[offset : offset + limit]
        if not page_paths:
            return [], tuple(sorted(folders)), total

        stmt = (
            select(DocumentRow)
            .where(
                DocumentRow.engagement_id == engagement_id,
                DocumentRow.path.in_(page_paths),
            )
            .order_by(DocumentRow.path.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_document_from_row(row) for row in rows], tuple(sorted(folders)), total


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
        usage = turn.usage
        row = SessionTurnRow(
            id=turn.id,
            session_id=turn.session_id,
            ordinal=turn.ordinal,
            question_text=turn.question.text,
            question_folder_scope=turn.question.folder_scope,
            question_auditor_role=turn.question.auditor_role,
            question_topic=turn.question.topic,
            standalone_question=turn.standalone_question,
            answer_status=turn.answer.status.value,
            answer_text=None,
            insufficient_reason=None,
            thinking_text=turn.thinking_text,
            thinking_seconds=turn.thinking_seconds,
            usage_prompt_tokens=usage.prompt_tokens if usage is not None else None,
            usage_completion_tokens=usage.completion_tokens if usage is not None else None,
            usage_total_tokens=usage.total_tokens if usage is not None else None,
            created_at=turn.created_at,
            citations=[],
            suggested_questions=[],
        )
        _populate_answer_rows(row, turn.answer)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(
            row,
            attribute_names=["citations", "suggested_questions"],
        )
        return _turn_from_row(row)

    async def list_turns(self, session_id: SessionId) -> list[Turn]:
        stmt = (
            select(SessionTurnRow)
            .where(SessionTurnRow.session_id == session_id)
            .options(
                selectinload(SessionTurnRow.citations),
                selectinload(SessionTurnRow.suggested_questions),
            )
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


class PostgresUploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, upload: Upload, items: Sequence[UploadItem]) -> Upload:
        now = datetime.now(UTC)
        self._session.add(
            UploadRow(
                id=upload.id,
                engagement_id=upload.engagement_id,
                target_folder=upload.target_folder,
                status=upload.status.value,
                completed_at=upload.completed_at,
                created_at=upload.created_at,
                updated_at=upload.updated_at,
            )
        )
        for item in items:
            self._session.add(
                UploadItemRow(
                    id=item.id,
                    upload_id=item.upload_id,
                    document_path=item.document_path,
                    status=item.status.value,
                    reason=item.reason,
                    attempts=item.attempts,
                    locked_until=None,
                    locked_by=None,
                    next_attempt_at=None,
                    raw_storage_key=item.document_path,
                    created_at=item.created_at,
                    updated_at=item.updated_at if item.updated_at else now,
                )
            )
        await self._session.flush()
        return upload

    async def get(
        self,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> tuple[Upload, list[UploadItem]] | None:
        stmt = select(UploadRow).where(
            UploadRow.id == upload_id,
            UploadRow.engagement_id == engagement_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        items_stmt = (
            select(UploadItemRow)
            .where(UploadItemRow.upload_id == upload_id)
            .order_by(UploadItemRow.created_at.asc())
        )
        item_rows = (await self._session.execute(items_stmt)).scalars().all()
        return _upload_from_row(row), [_upload_item_from_row(r) for r in item_rows]

    async def get_by_id(self, upload_id: UploadId) -> Upload | None:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            return None
        return _upload_from_row(row)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Upload], int]:
        filters = [UploadRow.engagement_id == engagement_id]
        total_stmt = select(func.count()).select_from(UploadRow).where(*filters)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(UploadRow)
            .where(*filters)
            .order_by(UploadRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_upload_from_row(row) for row in rows], total

    async def mark_processing(self, upload_id: UploadId) -> None:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            return
        if row.status == UploadStatus.QUEUED.value:
            now = datetime.now(UTC)
            row.status = UploadStatus.PROCESSING.value
            row.updated_at = now
            await self._session.flush()

    async def refresh_status(self, upload_id: UploadId) -> Upload:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            raise NotFoundError(f"upload not found: {upload_id}")

        items_stmt = select(UploadItemRow).where(UploadItemRow.upload_id == upload_id)
        item_rows = (await self._session.execute(items_stmt)).scalars().all()
        statuses = {UploadItemStatus(r.status) for r in item_rows}
        terminal = {
            UploadItemStatus.INDEXED,
            UploadItemStatus.SKIPPED,
            UploadItemStatus.NOT_SEARCHABLE,
            UploadItemStatus.FAILED,
        }
        now = datetime.now(UTC)
        if statuses and statuses <= terminal:
            row.status = UploadStatus.COMPLETED.value
            row.completed_at = now
        elif UploadItemStatus.PROCESSING in statuses or any(s in terminal for s in statuses):
            row.status = UploadStatus.PROCESSING.value
        else:
            row.status = UploadStatus.QUEUED.value
        row.updated_at = now
        await self._session.flush()
        return _upload_from_row(row)
