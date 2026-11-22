"""Request-id middleware."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.logging import bind_context, clear_context
from domain.common import RequestId


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get("x-request-id")
        try:
            request_id = RequestId(uuid.UUID(raw) if raw else uuid.uuid4())
        except ValueError:
            request_id = RequestId(uuid.uuid4())
        request.state.request_id = request_id
        clear_context()
        bind_context(request_id=request_id)
        response = await call_next(request)
        response.headers["x-request-id"] = str(request_id)
        clear_context()
        return response
