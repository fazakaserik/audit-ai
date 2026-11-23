"""Document list, download, and upload routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile, status
from fastapi.responses import Response

from backend.application.api.contracts.v1.mapping import document_to_response
from backend.application.api.contracts.v1.responses import (
    DocumentListingResponse,
    UploadAcceptedResponse,
)
from backend.application.api.dependencies import get_bound, get_container
from backend.application.get_document import get_document
from backend.application.list_documents import list_documents
from backend.application.upload_documents import IncomingUploadFile, upload_documents
from backend.bootstrap import Container, SessionBound
from backend.domain.common import RequestId
from backend.domain.document import DocumentPath, FolderPath
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
    folder_prefix = FolderPath(prefix) if prefix is not None and prefix != "" else None
    result = await list_documents(
        bound.engagements,
        bound.documents,
        engagement_id=engagement_id,
        prefix=folder_prefix,
        depth=depth,
        limit=limit,
        offset=offset,
    )
    responses = tuple(document_to_response(doc) for doc in result.items)
    return DocumentListingResponse(
        items=responses,
        folders=result.folders,
        total=result.total,
        limit=limit,
        offset=offset,
    )


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
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    """Return the raw bytes for one document."""
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
    summary="Upload documents",
)
async def post_documents_upload(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement that will receive the files"),
    ],
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
    container: Annotated[Container, Depends(get_container)],
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

    result = await upload_documents(
        engagements=bound.engagements,
        uploads=bound.uploads,
        storage=container.document_storage,
        jobs=bound.jobs,
        archives=container.archive_extractor,
        settings=container.settings,
        engagement_id=engagement_id,
        target_folder=folder,
        files=incoming,
    )
    raw_rid = getattr(request.state, "request_id", None)
    request_id = RequestId(raw_rid) if isinstance(raw_rid, uuid.UUID) else RequestId(uuid.uuid4())
    return UploadAcceptedResponse(upload_id=result.upload.id, request_id=request_id)
