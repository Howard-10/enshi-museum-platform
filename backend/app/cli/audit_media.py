"""Create an auditable report for PostgreSQL media rows, MinIO objects and sources."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.core import MediaAsset
from app.db.session import SessionLocal
from app.services.media_ingestion import sha256_file
from app.services.minio_storage import MinioStorage


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit media source files, database rows and MinIO objects."
    )
    parser.add_argument("knowledge_root", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    knowledge_root = args.knowledge_root.resolve()
    if not knowledge_root.is_dir():
        raise SystemExit(f"Knowledge root not found: {knowledge_root}")

    async with SessionLocal() as session:
        assets = (
            await session.scalars(
                select(MediaAsset)
                .options(selectinload(MediaAsset.artifact))
                .order_by(MediaAsset.object_key)
            )
        ).all()

    storage = MinioStorage()
    objects = {
        item.object_name: item.size
        for item in storage.client.list_objects(storage.bucket, prefix="media/", recursive=True)
    }

    records: list[dict[str, Any]] = []
    for asset in assets:
        source_relative_path = asset.metadata_json.get("source_relative_path")
        source_kind = asset.metadata_json.get("source_kind", "file")
        source_path = knowledge_root / source_relative_path if source_relative_path else None
        source_exists = bool(source_path and source_path.is_file())
        source_hash_matches: bool | None
        if source_kind == "xlsx_embedded_image":
            # The workbook exists at source_path, while the imported object is one
            # specific embedded image part; its own hash is checked by the XLSX
            # importer and its audit report rather than against the whole workbook.
            source_hash_matches = None
        else:
            source_hash_matches = (
                sha256_file(source_path) == asset.sha256
                if source_exists and source_path is not None
                else False
            )
        object_size = objects.get(asset.object_key)
        records.append(
            {
                "media_asset_id": str(asset.id),
                "source_relative_path": source_relative_path,
                "source_kind": source_kind,
                "source_reference": asset.metadata_json.get("source_reference"),
                "original_filename": asset.original_filename,
                "media_type": asset.media_type,
                "artifact_name": asset.artifact.name if asset.artifact else None,
                "association_confidence": asset.metadata_json.get("association_confidence"),
                "sha256": asset.sha256,
                "object_key": asset.object_key,
                "database_byte_size": asset.byte_size,
                "source_exists": source_exists,
                "source_hash_matches": source_hash_matches,
                "minio_object_exists": object_size is not None,
                "minio_object_size": object_size,
                "minio_size_matches": object_size == asset.byte_size,
            }
        )

    expected_keys = {asset.object_key for asset in assets}
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "database_assets": len(assets),
        "minio_objects": len(objects),
        "source_missing": sum(not record["source_exists"] for record in records),
        "source_hash_mismatches": sum(record["source_hash_matches"] is False for record in records),
        "minio_missing": sum(not record["minio_object_exists"] for record in records),
        "minio_size_mismatches": sum(not record["minio_size_matches"] for record in records),
        "unexpected_minio_objects": len(set(objects) - expected_keys),
        "by_media_type": dict(Counter(asset.media_type for asset in assets)),
        "by_association_confidence": dict(
            Counter(record["association_confidence"] or "missing" for record in records)
        ),
    }
    report = {"summary": summary, "records": records}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
