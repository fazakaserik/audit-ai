"""LangGraph state for the ask / RAG workflow."""

from __future__ import annotations

from typing import TypedDict

from backend.application.ports import ScoredPassage
from backend.rag.prompts import AnswerGenerationResult
from domain.answer import Answer, Citation, InsufficientReason, Question
from domain.document import FolderPath
from domain.engagement import EngagementId
from domain.session import Turn


class AskState(TypedDict, total=False):
    engagement_id: EngagementId
    question: Question
    folder_scope: FolderPath | None
    prior_turns: tuple[Turn, ...]
    standalone_question: str
    scored_passages: list[ScoredPassage]
    generation: AnswerGenerationResult | None
    insufficient_reason: InsufficientReason | None
    partial_citations: tuple[Citation, ...]
    answer: Answer | None