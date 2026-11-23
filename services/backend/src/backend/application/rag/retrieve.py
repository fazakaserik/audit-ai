"""Hybrid vector/FTS retrieval over engagement chunks."""

from __future__ import annotations

from backend.application.dto import (
    RetrievalScope,
    ScoredChunk,
)
from backend.application.llm.embedder import Embedder
from backend.application.storage.vector_index import VectorIndex
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId


async def retrieve_relevant_chunks(
    *,
    query: str,
    engagement_id: EngagementId,
    folder_prefix: FolderPath | None,
    embedder: Embedder,
    vector_index: VectorIndex,
    top_k: int,
    min_score: float,
) -> list[ScoredChunk]:
    """Embed `query` and return scored chunks in engagement (optional folder) scope."""
    embedded = await embedder.embed((query,))
    scope = RetrievalScope(
        engagement_id=engagement_id,
        folder_prefix=folder_prefix,
        top_k=top_k,
    )
    return await vector_index.search(
        query,
        embedded.vectors[0],
        scope,
        embedding_model=embedder.model_name,
        min_score=min_score,
    )
