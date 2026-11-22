"""Document list, download, and upload routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import Response

from backend.api.contracts.v1.mapping import document_to_response
from backend.api.contracts.v1.page import Page
from backend.api.contracts.v1.responses import DocumentResponse, UploadAcceptedResponse
from backend.api.dependencies import get_bound, get_container
from backend.application.get_document import get_document
from backend.application.list_documents import list_documents
from backend.application.upload_documents import IncomingUploadFile, upload_documents
from backend.bootstrap import Container, SessionBound
from domain.common import RequestId
from domain.document import DocumentPath, FolderPath
from domain.engagement import EngagementId
from domain.errors import ValidationError

router = APIRouter(prefix="/api/v1/engagements", tags=["documents", "uploads"])


@router.get("/{engagement_id}/documents", response_model=Page[DocumentResponse])
async def get_documents_list(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
    prefix: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Page[DocumentResponse]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    folder_prefix = FolderPath(prefix) if prefix is not None and prefix != "" else None
    result = await list_documents(
        bound.engagements,
        bound.documents,
        engagement_id=engagement_id,
        prefix=folder_prefix,
        limit=limit,
        offset=offset,
    )
    responses = tuple(document_to_response(doc) for doc in result.items)
    return Page(items=responses, total=result.total, limit=limit, offset=offset)


@router.get("/{engagement_id}/documents/{document_path:path}")
async def get_document_content(
    engagement_id: EngagementId,
    document_path: DocumentPath,
    bound: Annotated[SessionBound, Depends(get_bound)],
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    result = await get_document(
        bound.engagements,
        bound.documents,
        container.document_storage,
        engagement_id=engagement_id,
        path=document_path,
    )
    return Response(content=result.data, media_type=result.media_type)


@router.post(
    "/{engagement_id}/documents",
    response_model=UploadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_documents_upload(
    engagement_id: EngagementId,
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
    container: Annotated[Container, Depends(get_container)],
    folder: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
) -> UploadAcceptedResponse:
    if not files:
        raise ValidationError("upload must include at least one file")

    incoming: list[IncomingUploadFile] = []
    for upload in files:
        payload = await upload.read()
        filename = upload.filename or "upload.bin"
        incoming.append(IncomingUploadFile(filename=filename, data=payload))

    result = await upload_documents(
        engagements=bound.engagements,
        uploads=bound.uploads,
        storage=container.document_storage,
        jobs=bound.jobs,
        settings=container.settings,
        engagement_id=engagement_id,
        target_folder=folder,
        files=incoming,
    )
    raw_rid = getattr(request.state, "request_id", None)
    request_id = (
        RequestId(raw_rid) if isinstance(raw_rid, uuid.UUID) else RequestId(uuid.uuid4())
    )
    return UploadAcceptedResponse(upload_id=result.upload.id, request_id=request_id)