"""Persistence operations for traceable spreadsheet catalog rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import Artifact, ArtifactCatalogRecord


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_source_row(
        self,
        *,
        source_sha256: str,
        sheet_name: str,
        row_number: int,
    ) -> ArtifactCatalogRecord | None:
        return await self.session.scalar(
            select(ArtifactCatalogRecord).where(
                ArtifactCatalogRecord.source_sha256 == source_sha256,
                ArtifactCatalogRecord.sheet_name == sheet_name,
                ArtifactCatalogRecord.row_number == row_number,
            )
        )

    async def get_or_create_artifact(
        self,
        *,
        name: str | None,
        era: str | None,
    ) -> tuple[Artifact | None, bool, bool]:
        """Return an artifact plus whether it was created or enriched."""

        if not name:
            return None, False, False
        artifact = await self.session.scalar(select(Artifact).where(Artifact.name == name))
        if artifact is None:
            artifact = Artifact(name=name, era=era)
            self.session.add(artifact)
            await self.session.flush()
            return artifact, True, False
        if era and artifact.era is None:
            artifact.era = era
            return artifact, False, True
        return artifact, False, False

    def add_record(
        self,
        *,
        artifact: Artifact | None,
        source_sha256: str,
        source_uri: str,
        sheet_name: str,
        row_number: int,
        record_kind: str,
        era: str | None,
        location: str | None,
        material: str | None,
        content_fingerprint: str,
        raw_data: dict[str, Any],
    ) -> ArtifactCatalogRecord:
        record = ArtifactCatalogRecord(
            artifact=artifact,
            source_sha256=source_sha256,
            source_uri=source_uri,
            sheet_name=sheet_name,
            row_number=row_number,
            record_kind=record_kind,
            era=era,
            location=location,
            material=material,
            content_fingerprint=content_fingerprint,
            raw_data=raw_data,
        )
        self.session.add(record)
        return record
