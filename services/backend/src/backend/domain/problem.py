"""RFC 9457 Problem Details model (shared error envelope)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.common import RequestId
from backend.domain.errors import ErrorCode


class FieldError(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    field: Annotated[str, Field(min_length=1)]
    message: Annotated[str, Field(min_length=1)]


class ProblemDetails(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    type: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, Field(min_length=1)]
    code: ErrorCode
    request_id: RequestId
    instance: str | None = None
    errors: tuple[FieldError, ...] = ()

    @classmethod
    def of(
        cls,
        *,
        code: ErrorCode,
        title: str,
        status: int,
        detail: str,
        request_id: RequestId | None = None,
        errors: list[FieldError] | None = None,
        instance: str | None = None,
    ) -> ProblemDetails:
        rid = request_id if request_id is not None else RequestId(uuid.uuid4())
        return cls(
            type=f"https://audit-ai.local/problems/{code.value}",
            title=title,
            status=status,
            detail=detail,
            code=code,
            request_id=rid,
            instance=instance,
            errors=tuple(errors or ()),
        )
