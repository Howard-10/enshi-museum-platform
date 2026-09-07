"""Persistence operations for MinIO-backed media metadata."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import Artifact, ArtifactMediaLink, MediaAsset


class MediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_sha256(self, sha256: str) -> MediaAsset | None:
        return await self.session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))

    async def get_or_create_artifact(self, name: str | None) -> Artifact | None:
        if not name:
            return None
        artifact = await self.session.scalar(select(Artifact).where(Artifact.name == name))
        if artifact is None:
            artifact = Artifact(name=name)
            self.session.add(artifact)
            await self.session.flush()
        return artifact

    async def create_media_asset(
        self,
        *,
        artifact_name: str | None,
        object_key: str,
        original_filename: str,
        media_type: str,
        mime_type: str,
        byte_size: int,
        sha256: str,
        metadata: dict[str, Any],
    ) -> MediaAsset:
        artifact = await self.get_or_create_artifact(artifact_name)
        asset = MediaAsset(
            artifact=artifact,
            object_key=object_key,
            original_filename=original_filename,
            media_type=media_type,
            mime_type=mime_type,
            byte_size=byte_size,
            sha256=sha256,
            metadata_json=metadata,
        )
        self.session.add(asset)
        if artifact is not None:
            self.session.add(
                ArtifactMediaLink(
                    artifact=artifact,
                    media_asset=asset,
                    source_reference=metadata.get("source_relative_path"),
                    association_confidence=metadata.get("association_confidence", "unassigned"),
                    metadata_json=metadata,
                )
            )
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def ensure_artifact_link(
        self,
        *,
        asset: MediaAsset,
        artifact_name: str | None,
        metadata: dict[str, Any],
    ) -> bool:
        """Attach an existing deduplicated object to another artifact if needed."""

        artifact = await self.get_or_create_artifact(artifact_name)
        if artifact is None:
            return False
        existing = await self.session.scalar(
            select(ArtifactMediaLink).where(
                ArtifactMediaLink.artifact_id == artifact.id,
                ArtifactMediaLink.media_asset_id == asset.id,
            )
        )
        if existing is not None:
            return False
        self.session.add(
            ArtifactMediaLink(
                artifact=artifact,
                media_asset=asset,
                source_reference=metadata.get("source_relative_path"),
                association_confidence=metadata.get("association_confidence", "unassigned"),
                metadata_json=metadata,
            )
        )
        await self.session.commit()
        return True
