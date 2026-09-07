from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminSummary(BaseModel):
    artifacts: int
    documents: int
    media_assets: int
    approved_documents: int
    documents_needing_review: int
    media_links_needing_review: int


class AdminArtifactRead(BaseModel):
    id: UUID
    name: str
    aliases: list[str]
    era: str | None
    category: str | None
    description: str | None
    location: str | None
    material: str | None
    document_count: int
    media_count: int


class AdminArtifactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    era: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    material: str | None = Field(default=None, max_length=100)


class AdminDocumentRead(BaseModel):
    id: UUID
    title: str
    source_filename: str
    mime_type: str
    import_status: str
    review_status: str
    review_note: str | None
    artifact_id: UUID | None
    artifact_name: str | None
    chunk_count: int


class AdminDocumentReviewUpdate(BaseModel):
    review_status: str = Field(pattern="^(approved|rejected|needs_review)$")
    review_note: str | None = None


class AdminMediaLinkRead(BaseModel):
    artifact_id: UUID
    artifact_name: str
    review_status: str
    association_confidence: str


class AdminMediaRead(BaseModel):
    id: UUID
    original_filename: str
    media_type: str
    mime_type: str
    byte_size: int
    sha256: str
    links: list[AdminMediaLinkRead]


class AdminMediaLinkCreate(BaseModel):
    artifact_id: UUID
    review_status: str = Field(default="needs_review", pattern="^(approved|rejected|needs_review)$")
    source_reference: str | None = None
    association_confidence: str = Field(default="manual", max_length=30)


class AdminAuditRead(BaseModel):
    id: UUID
    actor: str
    action: str
    object_type: str
    object_id: str | None
    before: dict
    after: dict
    created_at: datetime
