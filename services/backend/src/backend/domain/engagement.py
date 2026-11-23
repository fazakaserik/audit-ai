"""Engagement entity and id."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from backend.domain.common import MODEL_CONFIG

_ENGAGEMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


def validate_engagement_id(value: str) -> str:
    if not _ENGAGEMENT_ID_RE.fullmatch(value):
        msg = "engagement id must be 2-63 chars, start with a-z0-9, and contain only a-z0-9-"
        raise ValueError(msg)
    return value


EngagementId = Annotated[str, AfterValidator(validate_engagement_id)]


class Engagement(BaseModel):
    model_config = MODEL_CONFIG

    id: EngagementId
    name: Annotated[str, Field(min_length=1, max_length=200)]
    created_at: datetime
    updated_at: datetime
