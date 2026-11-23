"""Postgres document repository adapter."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.document import (
    Document,
    DocumentPath,
    FolderPath,
    child_folder_name,
    normalize_list_prefix,
    relative_segments,
    within_depth,
)
from backend.domain.engagement import EngagementId
from backend.infrastructure.postgres.models import DocumentRow
from backend.infrastructure.postgres.repositories._mappers import document_from_row


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
        return document_from_row(row)

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
        return document_from_row(row)

    async def delete_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> bool:
        result = await self._session.execute(
            delete(DocumentRow).where(
                DocumentRow.engagement_id == engagement_id,
                DocumentRow.path == path,
            )
        )
        await self._session.flush()
        return bool(result.rowcount)

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
        return [document_from_row(row) for row in rows], tuple(sorted(folders)), total
