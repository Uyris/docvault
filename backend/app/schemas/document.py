"""Document API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error: str | None = None
    num_chunks: int
    num_chars: int
    created_at: datetime


class UploadAccepted(BaseModel):
    """Returned immediately on upload; indexing continues in the background."""

    document: DocumentOut
    message: str = "Upload accepted. Indexing runs in the background; poll the document status."
