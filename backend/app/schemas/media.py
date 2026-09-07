"""Response models for MinIO-backed media assets."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_name: str | None
    original_filename: str
    media_type: str
    mime_type: str
    byte_size: int
    association_confidence: str | None


class MediaDownloadUrl(BaseModel):
    media_asset_id: UUID
    url: str
    expires_in_seconds: int
