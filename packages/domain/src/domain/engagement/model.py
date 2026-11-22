"""Engagement entity and id."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from domain.common import MODEL_CONFIG
from domain.engagement.validators import validate_engagement_id

EngagementId = Annotated[str, AfterValidator(validate_engagement_id)]


class Engagement(BaseModel):
    model_config = MODEL_CONFIG

    id: EngagementId
    name: Annotated[str, Field(min_length=1, max_length=200)]
    created_at: datetime
    updated_at: datetime
