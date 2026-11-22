"""Map domain errors to RFC 9457 Problem Details."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from domain.common import RequestId
from domain.errors import DomainError, ErrorCode
from domain.errors import ValidationError as DomainValidationError
from domain.problem import FieldError, ProblemDetails

_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSAFE_UPLOAD: 400,
    ErrorCode.MODEL_TIMEOUT: 504,
    ErrorCode.MODEL_UNAVAILABLE: 502,
    ErrorCode.DEPENDENCY_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


def http_status_for(code: ErrorCode) -> int:
    """Map a domain error code to an HTTP status."""
    return _STATUS.get(code, 500)

_TITLE: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "Validation Error",
    ErrorCode.NOT_FOUND: "Not Found",
    ErrorCode.CONFLICT: "Conflict",
    ErrorCode.PAYLOAD_TOO_LARGE: "Payload Too Large",
    ErrorCode.UNSAFE_UPLOAD: "Unsafe Upload",
    ErrorCode.MODEL_TIMEOUT: "Model Timeout",
    ErrorCode.MODEL_UNAVAILABLE: "Model Unavailable",
    ErrorCode.DEPENDENCY_UNAVAILABLE: "Dependency Unavailable",
    ErrorCode.INTERNAL_ERROR: "Internal Error",
}


def _request_id(request: Request) -> RequestId:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, uuid.UUID):
        return RequestId(rid)
    return RequestId(uuid.uuid4())


def _problem_response(problem: ProblemDetails) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        code = exc.code
        field_errors: list[FieldError] = []
        if isinstance(exc, DomainValidationError):
            field_errors = [FieldError(field=f, message=m) for f, m in exc.field_errors]
        problem = ProblemDetails.of(
            code=code,
            title=_TITLE[code],
            status=_STATUS[code],
            detail=exc.message,
            request_id=_request_id(request),
            errors=field_errors or None,
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            FieldError(
                field=".".join(str(p) for p in err.get("loc", ())),
                message=str(err.get("msg", "invalid")),
            )
            for err in exc.errors()
        ]
        problem = ProblemDetails.of(
            code=ErrorCode.VALIDATION_ERROR,
            title=_TITLE[ErrorCode.VALIDATION_ERROR],
            status=422,
            detail="Request validation failed",
            request_id=_request_id(request),
            errors=errors,
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, _exc: Exception) -> JSONResponse:
        problem = ProblemDetails.of(
            code=ErrorCode.INTERNAL_ERROR,
            title=_TITLE[ErrorCode.INTERNAL_ERROR],
            status=500,
            detail="An unexpected error occurred",
            request_id=_request_id(request),
            instance=str(request.url.path),
        )
        return _problem_response(problem)
