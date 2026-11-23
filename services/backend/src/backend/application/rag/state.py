"""LangGraph state for the ask / RAG workflow."""

from __future__ import annotations

from typing import TypedDict

from backend.application.ports import ScoredChunk
from backend.application.rag.prompts import AnswerGenerationResult
from backend.domain.answer import Answer, Citation, InsufficientReason, Question
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage, Turn


class AskState(TypedDict, total=False):
    engagement_id: EngagementId
    question: Question
    folder_scope: FolderPath | None
    prior_turns: tuple[Turn, ...]
    standalone_question: str
    scored_chunks: list[ScoredChunk]
    generation: AnswerGenerationResult | None
    insufficient_reason: InsufficientReason | None
    partial_citations: tuple[Citation, ...]
    answer: Answer | None
    usage: LlmUsage
