"""Ask pipeline entrypoint: tool-calling agent → grounded answer or suggestions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.ports import (
    ChatModel,
    DocumentRepository,
    DocumentStorage,
    Embedder,
    EngagementRepository,
    VectorIndex,
)
from backend.application.rag.agent import AskAgentDeps, AskAgentResult, run_ask_agent
from backend.application.rag.progress import AskProgress
from backend.config import Settings
from backend.domain.answer import Question
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import Turn


@dataclass(frozen=True, slots=True)
class AskGraphDeps:
    """Deps for the ask graph; mirrors agent deps for call-site compatibility."""

    chat: ChatModel
    embedder: Embedder
    vector_index: VectorIndex
    engagements: EngagementRepository
    documents: DocumentRepository
    storage: DocumentStorage
    settings: Settings
    progress: AskProgress | None = None


AskGraphResult = AskAgentResult


async def run_ask_graph(
    *,
    engagement_id: EngagementId,
    question: Question,
    folder_scope: FolderPath | None,
    prior_turns: Sequence[Turn] = (),
    deps: AskGraphDeps,
    progress: AskProgress | None = None,
) -> AskAgentResult:
    progress_sink = progress if progress is not None else deps.progress
    agent_deps = AskAgentDeps(
        chat=deps.chat,
        embedder=deps.embedder,
        vector_index=deps.vector_index,
        engagements=deps.engagements,
        documents=deps.documents,
        storage=deps.storage,
        settings=deps.settings,
        progress=progress_sink,
    )
    return await run_ask_agent(
        engagement_id=engagement_id,
        question=question,
        folder_scope=folder_scope,
        prior_turns=prior_turns,
        deps=agent_deps,
    )
