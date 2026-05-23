"""Document ingestion + management endpoints."""

from __future__ import annotations

import mimetypes
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Document, DocumentStatus
from app.db.session import get_session
from app.schemas.document import DocumentOut, UploadAccepted
from app.services.ingestion import index_document

router = APIRouter(prefix="/documents", tags=["documents"])

_ALLOWED_EXTENSIONS = (".pdf", ".txt", ".md", ".markdown")


def _resolve_content_type(file: UploadFile) -> str:
    if file.content_type and file.content_type != "application/octet-stream":
        return file.content_type
    guessed, _ = mimetypes.guess_type(file.filename or "")
    return guessed or "application/octet-stream"


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=UploadAccepted)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadAccepted:
    """Accept a file, persist its metadata, and index it in the background."""
    filename = file.filename or "upload"
    if not filename.lower().endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    data = await file.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty.")
    if size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )

    doc = Document(
        filename=filename,
        content_type=_resolve_content_type(file),
        size_bytes=size,
        status=DocumentStatus.PENDING,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Hand the bytes to the background task; the request returns immediately.
    background_tasks.add_task(index_document, doc.id, filename, doc.content_type, data)
    return UploadAccepted(document=DocumentOut.model_validate(doc))


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: AsyncSession = Depends(get_session)) -> list[Document]:
    rows = await session.execute(select(Document).order_by(Document.created_at.desc()))
    return list(rows.scalars().all())


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return doc


@router.delete(
    "/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_document(
    document_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    await session.delete(doc)  # chunks cascade
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
