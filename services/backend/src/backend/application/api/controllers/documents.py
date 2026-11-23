"""Document list, download, and upload controllers."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile, status
from fastapi.responses import Response

from backend.application.api.contracts.v1.mapping import (
    document_listing_to_response,
    upload_accepted_to_response,
)
from backend.application.api.contracts.v1.responses import (
    DocumentListingResponse,
    UploadAcceptedResponse,
)
from backend.application.api.dependencies import get_bound
from backend.application.services.documents import IncomingUploadFile
from backend.application.wiring import SessionBound
from backend.domain.common import RequestId
from backend.domain.document import DocumentPath, FolderPath, validate_folder_path
from backend.domain.engagement import EngagementId
from backend.domain.errors import ValidationError

router = APIRouter(prefix="/api/v1/engagements", tags=["documents", "uploads"])


@router.get(
    "/{engagement_id}/documents",
    response_model=DocumentListingResponse,
    summary="List documents and child folders",
)
async def get_documents_list(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement that owns the documents"),
    ],
    bound: Annotated[SessionBound, Depends(get_bound)],
    prefix: Annotated[
        str | None,
        Query(description="Folder to list under; omit or empty for the engagement root"),
    ] = None,
    depth: Annotated[
        int | None,
        Query(
            ge=1,
            description="How many path levels under prefix to return; omit for all levels",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Max documents to return"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of documents to skip"),
    ] = 0,
) -> DocumentListingResponse:
    """List documents under a folder prefix, optionally limited by depth.

    Also returns immediate child folder names so clients can browse the tree.
    """
    folder_prefix: FolderPath | None = (
        validate_folder_path(prefix) if prefix is not None and prefix != "" else None
    )
    listing = await bound.documents.list_documents(
        engagement_id=engagement_id,
        prefix=folder_prefix,
        depth=depth,
        limit=limit,
        offset=offset,
    )
    return document_listing_to_response(listing)


@router.get(
    "/{engagement_id}/documents/{document_path:path}",
    summary="Download a document",
)
async def get_document_content(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement that owns the document"),
    ],
    document_path: Annotated[
        DocumentPath,
        Path(description="Full relative document path"),
    ],
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> Response:
    """Return the raw bytes for one document."""
    content = await bound.documents.get_document_content(
        engagement_id=engagement_id,
        path=document_path,
    )
    return Response(content=content.data, media_type=content.media_type)


@router.post(
    "/{engagement_id}/documents",
    response_model=UploadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload documents",
)
async def post_documents_upload(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement that will receive the files"),
    ],
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
    folder: Annotated[
        str,
        Form(description="Target folder prefix where uploaded files are stored"),
    ],
    files: Annotated[
        list[UploadFile],
        File(description="One or more files, or a zip archive"),
    ],
) -> UploadAcceptedResponse:
    """Queue files for async ingest into an engagement folder."""
    if not files:
        raise ValidationError("upload must include at least one file")

    incoming: list[IncomingUploadFile] = []
    for upload in files:
        payload = await upload.read()
        filename = upload.filename or "upload.bin"
        incoming.append(IncomingUploadFile(filename=filename, data=payload))

    raw_rid = getattr(request.state, "request_id", None)
    request_id = RequestId(raw_rid) if isinstance(raw_rid, uuid.UUID) else RequestId(uuid.uuid4())
    accepted = await bound.documents.upload_documents(
        engagement_id=engagement_id,
        target_folder=folder,
        files=incoming,
    )
    return upload_accepted_to_response(accepted, request_id=request_id)
