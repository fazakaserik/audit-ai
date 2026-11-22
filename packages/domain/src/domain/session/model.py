"""Session and turn entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, NewType

from pydantic import BaseModel, Field

from domain.answer import Answer, Question
from domain.common import MODEL_CONFIG
from domain.engagement import EngagementId

SessionId = NewType("SessionId", uuid.UUID)
TurnId = NewType("TurnId", uuid.UUID)


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
