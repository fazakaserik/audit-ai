"""Session and turn entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, NewType, Self

from pydantic import BaseModel, Field

from domain.answer import Answer, Question
from domain.common import MODEL_CONFIG
from domain.engagement import EngagementId

SessionId = NewType("SessionId", uuid.UUID)
TurnId = NewType("TurnId", uuid.UUID)


class LlmUsage(BaseModel):
    """Provider-reported token usage for one or more model calls."""

    model_config = MODEL_CONFIG

    prompt_tokens: Annotated[int, Field(ge=0)] = 0
    completion_tokens: Annotated[int, Field(ge=0)] = 0
    total_tokens: Annotated[int, Field(ge=0)] = 0

    def __add__(self, other: LlmUsage) -> LlmUsage:
        return LlmUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    @classmethod
    def from_counts(
        cls,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> Self:
        prompt = max(0, int(prompt_tokens or 0))
        completion = max(0, int(completion_tokens or 0))
        total = int(total_tokens) if total_tokens is not None else prompt + completion
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=max(0, total),
        )


class Session(BaseModel):
    model_config = MODEL_CONFIG

    id: SessionId
    engagement_id: EngagementId
    title: Annotated[str, Field(min_length=1, max_length=200)]
    turn_count: Annotated[int, Field(ge=0)]
    created_at: datetime
    updated_at: datetime


class Turn(BaseModel):
    model_config = MODEL_CONFIG

    id: TurnId
    session_id: SessionId
    ordinal: Annotated[int, Field(ge=0)]
    question: Question
    standalone_question: Annotated[str, Field(min_length=1)]
    answer: Answer
    created_at: datetime
    thinking_text: str | None = None
    thinking_seconds: float | None = None
    usage: LlmUsage | None = None
