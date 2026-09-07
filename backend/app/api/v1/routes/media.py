"""Read-only media lookup endpoints for the frontend and LangGraph tools."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.core import Artifact, ArtifactMediaLink, MediaAsset
from app.db.session import get_db_session
from app.schemas.media import MediaAssetRead, MediaDownloadUrl
from app.services.minio_storage import MinioStorage

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def to_media_read(asset: MediaAsset, *, artifact_name: str | None = None) -> MediaAssetRead:
    return MediaAssetRead(
        id=asset.id,
        artifact_name=artifact_name or (asset.artifact.name if asset.artifact else None),
        original_filename=asset.original_filename,
        media_type=asset.media_type,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        association_confidence=asset.metadata_json.get("association_confidence"),
    )


@router.get("", response_model=list[MediaAssetRead])
async def list_media_assets(
    session: DbSession,
    artifact: str | None = Query(default=None, description="Exact artifact name"),
    media_type: str | None = Query(default=None, pattern="^(audio|image|video)$"),
    reviewed_only: bool = Query(default=True, description="Only return approved or legacy-verified media"),
) -> list[MediaAssetRead]:
    statement = (
        select(MediaAsset)
        .options(selectinload(MediaAsset.artifact))
        .order_by(MediaAsset.created_at)
    )
    if artifact:
        statement = (
            select(MediaAsset, Artifact.name)
            .join(ArtifactMediaLink, ArtifactMediaLink.media_asset_id == MediaAsset.id)
            .join(Artifact, Artifact.id == ArtifactMediaLink.artifact_id)
            .options(selectinload(MediaAsset.artifact))
            .where(Artifact.name == artifact)
            .order_by(MediaAsset.created_at)
            .distinct()
        )
    if reviewed_only:
        if artifact:
            statement = statement.where(ArtifactMediaLink.review_status.in_(("approved", "legacy_verified")))
        else:
            statement = (
                statement
                .join(ArtifactMediaLink, ArtifactMediaLink.media_asset_id == MediaAsset.id)
                .where(ArtifactMediaLink.review_status.in_(("approved", "legacy_verified")))
                .distinct()
            )
    if media_type:
        statement = statement.where(MediaAsset.media_type == media_type)
    if artifact:
        rows = (await session.execute(statement)).all()
        return [to_media_read(asset, artifact_name=linked_name) for asset, linked_name in rows]
    assets = (await session.scalars(statement)).all()
    return [to_media_read(asset) for asset in assets]


@router.get("/{media_asset_id}/download-url", response_model=MediaDownloadUrl)
async def get_media_download_url(
    media_asset_id: UUID,
    session: DbSession,
) -> MediaDownloadUrl:
    asset = await session.scalar(
        select(MediaAsset)
        .options(selectinload(MediaAsset.artifact))
        .where(MediaAsset.id == media_asset_id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")

    expires_seconds = 600
    return MediaDownloadUrl(
        media_asset_id=asset.id,
        url=MinioStorage().presigned_download_url(asset.object_key, expires_seconds),
        expires_in_seconds=expires_seconds,
    )
