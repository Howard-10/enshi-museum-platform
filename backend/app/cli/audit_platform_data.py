"""Write a local, read-only data audit for the demonstration handoff."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.db.models.core import (
    Artifact,
    ArtifactMediaLink,
    Document,
    DocumentChunk,
    MediaAsset,
)
from app.db.session import SessionLocal


async def build_report() -> dict[str, object]:
    async with SessionLocal() as session:
        document_count = await session.scalar(select(func.count()).select_from(Document))
        child_chunks = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_level == "child")
        )
        parent_chunks = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_level == "parent")
        )
        artifacts = (await session.scalars(select(Artifact).order_by(Artifact.name))).all()
        media = (await session.scalars(select(MediaAsset))).all()
        media_links = await session.scalar(select(func.count()).select_from(ArtifactMediaLink))
        media_without_artifact = await session.scalar(
            select(func.count()).select_from(MediaAsset).where(MediaAsset.artifact_id.is_(None))
        )
        chunk_without_parent = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_level == "child", DocumentChunk.parent_chunk_id.is_(None))
        )
        media_hashes = [item.sha256 for item in media]
        media_types = Counter(item.media_type for item in media)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "local_audit_no_model_or_web_calls",
        "external_model_calls": 0,
        "web_search_calls": 0,
        "documents": document_count or 0,
        "child_chunks": child_chunks or 0,
        "parent_chunks": parent_chunks or 0,
        "catalog_artifacts": len(artifacts),
        "media_assets": len(media),
        "media_links": media_links or 0,
        "media_without_primary_artifact": media_without_artifact or 0,
        "child_chunks_without_parent": chunk_without_parent or 0,
        "duplicate_media_hash_rows": len(media_hashes) - len(set(media_hashes)),
        "media_by_type": dict(sorted(media_types.items())),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Audit imported platform data without mutation.")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = await build_report()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
