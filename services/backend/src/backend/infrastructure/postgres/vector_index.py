"""Hybrid vector + FTS index with reciprocal rank fusion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from backend.application.dto import (
    RetrievalScope,
    ScoredChunk,
)
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.document import DocumentId, DocumentPath
from backend.domain.engagement import EngagementId
from backend.infrastructure.postgres.models import ChunkRow, DocumentRow

_RRF_K = 60


def _chunk_from_row(row: ChunkRow) -> Chunk:
    heading = tuple(row.heading_path) if row.heading_path else ()
    return Chunk(
        id=ChunkId(row.id),
        document_id=DocumentId(row.document_id),
        document_version=row.document_version,
        ordinal=row.ordinal,
        page=row.page,
        heading_path=heading,
        text=row.text,
        token_count=row.token_count,
        created_at=row.created_at,
    )


def _rrf_merge(
    vector_ids: Sequence[UUID],
    fts_ids: Sequence[UUID],
    *,
    k: int = _RRF_K,
) -> list[UUID]:
    scores: dict[UUID, float] = {}
    for rank, chunk_id in enumerate(vector_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    for rank, chunk_id in enumerate(fts_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)


def _scoped_chunk_filters(
    scope: RetrievalScope,
    *,
    embedding_model: str,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        DocumentRow.engagement_id == scope.engagement_id,
        DocumentRow.version == ChunkRow.document_version,
        DocumentRow.searchable.is_(True),
        ChunkRow.embedding_model == embedding_model,
        ChunkRow.embedding.is_not(None),
    ]
    if scope.folder_prefix is not None and scope.folder_prefix != "":
        filters.append(DocumentRow.path.like(f"{scope.folder_prefix}%"))
    return filters


class PostgresVectorIndex:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_chunks(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
        document_path: DocumentPath,
        document_version: int,
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
        embedding_model: str,
    ) -> None:
        if len(chunks) != len(embeddings):
            msg = "chunks and embeddings must have the same length"
            raise ValueError(msg)

        doc_stmt = select(DocumentRow.id).where(
            DocumentRow.id == document_id,
            DocumentRow.engagement_id == engagement_id,
            DocumentRow.path == document_path,
        )
        found = (await self._session.execute(doc_stmt)).scalar_one_or_none()
        if found is None:
            msg = (
                f"document {document_id} not found in engagement {engagement_id} "
                f"at path {document_path}"
            )
            raise ValueError(msg)

        await self._session.execute(delete(ChunkRow).where(ChunkRow.document_id == document_id))

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.document_id != document_id:
                msg = "chunk.document_id must match document_id"
                raise ValueError(msg)
            if chunk.document_version != document_version:
                msg = "chunk.document_version must match document_version"
                raise ValueError(msg)
            self._session.add(
                ChunkRow(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    document_version=chunk.document_version,
                    ordinal=chunk.ordinal,
                    page=chunk.page,
                    heading_path=list(chunk.heading_path),
                    text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=list(embedding),
                    embedding_model=embedding_model,
                    created_at=chunk.created_at,
                )
            )
        await self._session.flush()

    async def list_document_chunks(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
    ) -> list[ScoredChunk]:
        stmt = (
            select(ChunkRow, DocumentRow.path)
            .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
            .where(
                DocumentRow.engagement_id == engagement_id,
                DocumentRow.id == document_id,
                DocumentRow.version == ChunkRow.document_version,
            )
            .order_by(ChunkRow.ordinal.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ScoredChunk(
                chunk=_chunk_from_row(row),
                document_path=path,
                score=1.0,
            )
            for row, path in (db_row.tuple() for db_row in rows)
        ]

    async def search(
        self,
        query: str,
        query_embedding: Sequence[float],
        scope: RetrievalScope,
        *,
        embedding_model: str,
        min_score: float,
    ) -> list[ScoredChunk]:
        filters = _scoped_chunk_filters(scope, embedding_model=embedding_model)
        embedding_list = list(query_embedding)
        distance = ChunkRow.embedding.cosine_distance(embedding_list)
        similarity = (1.0 - distance).label("similarity")
        candidate_limit = max(scope.top_k * 4, scope.top_k)

        vector_stmt = (
            select(ChunkRow, DocumentRow.path, similarity)
            .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
            .where(*filters)
            .order_by(distance.asc())
            .limit(candidate_limit)
        )
        vector_rows = (await self._session.execute(vector_stmt)).all()

        vector_survivors: list[tuple[ChunkRow, str, float]] = []
        for db_row in vector_rows:
            row, path, score_raw = db_row.tuple()
            score = float(score_raw)
            if score >= min_score:
                vector_survivors.append((row, path, score))

        # FTS runs over the full engagement scope (not only vector survivors) so
        # exact names/ids (e.g. auditor firm on a signature page) can enter RRF
        # even when their embedding score is weak or outside the vector shortlist.
        fts_hits = await self._fts_hits(
            query=query,
            scope=scope,
            embedding_model=embedding_model,
            limit=candidate_limit,
        )

        if not vector_survivors and not fts_hits:
            return []

        vector_ranked_ids = [row.id for row, _, _ in vector_survivors]
        score_by_id = {row.id: score for row, _, score in vector_survivors}
        path_by_id = {row.id: path for row, path, _ in vector_survivors}
        row_by_id = {row.id: row for row, _, _ in vector_survivors}

        fts_ranked_ids: list[UUID] = []
        for row, path in fts_hits:
            fts_ranked_ids.append(row.id)
            if row.id not in row_by_id:
                row_by_id[row.id] = row
                path_by_id[row.id] = path
                # Nominal score for FTS-only hits (vector score unavailable).
                score_by_id[row.id] = min_score

        if vector_ranked_ids:
            fused_ids = _rrf_merge(vector_ranked_ids, fts_ranked_ids)[: scope.top_k]
        else:
            fused_ids = fts_ranked_ids[: scope.top_k]

        return [
            ScoredChunk(
                chunk=_chunk_from_row(row_by_id[chunk_id]),
                document_path=path_by_id[chunk_id],
                score=score_by_id[chunk_id],
            )
            for chunk_id in fused_ids
        ]

    async def _fts_hits(
        self,
        *,
        query: str,
        scope: RetrievalScope,
        embedding_model: str,
        limit: int,
    ) -> list[tuple[ChunkRow, str]]:
        if not query.strip():
            return []

        filters = _scoped_chunk_filters(scope, embedding_model=embedding_model)
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(ChunkRow.search_vector, ts_query)

        stmt = (
            select(ChunkRow, DocumentRow.path)
            .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
            .where(
                *filters,
                ChunkRow.search_vector.op("@@")(ts_query),
            )
            .order_by(rank.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row, path) for row, path in (db_row.tuple() for db_row in rows)]
