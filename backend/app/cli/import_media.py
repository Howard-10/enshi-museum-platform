"""Upload knowledge-base media to MinIO and register metadata in PostgreSQL.

Example:
    python -m app.cli.import_media "E:\\恩施知识库" --types audio image video
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db.session import SessionLocal
from app.repositories.media_repository import MediaRepository
from app.services.media_ingestion import (
    MEDIA_DETAILS,
    build_object_key,
    describe_media,
    sha256_file,
)
from app.services.minio_storage import MinioStorage


def find_media_files(knowledge_root: Path, allowed_types: set[str]) -> list[Path]:
    return sorted(
        path
        for path in knowledge_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in MEDIA_DETAILS
        and MEDIA_DETAILS[path.suffix.lower()][0] in allowed_types
    )


async def import_file(
    *,
    path: Path,
    knowledge_root: Path,
    storage: MinioStorage,
    dry_run: bool,
) -> dict[str, Any]:
    descriptor = describe_media(path, knowledge_root)
    sha256 = sha256_file(path)
    object_key = build_object_key(
        media_type=descriptor.media_type,
        sha256=sha256,
        suffix=path.suffix,
    )
    record = {
        "source_relative_path": descriptor.source_relative_path,
        "original_filename": path.name,
        "sha256": sha256,
        "object_key": object_key,
        "media_type": descriptor.media_type,
        "mime_type": descriptor.mime_type,
        "byte_size": path.stat().st_size,
        "artifact_name": descriptor.artifact_name,
        "artifact_hint": descriptor.artifact_hint,
        "association_confidence": descriptor.association_confidence,
    }

    async with SessionLocal() as session:
        repository = MediaRepository(session)
        existing = await repository.get_by_sha256(sha256)
        if existing is not None:
            metadata = {
                "source_relative_path": descriptor.source_relative_path,
                "source_category": descriptor.source_category,
                "artifact_hint": descriptor.artifact_hint,
                "association_confidence": descriptor.association_confidence,
            }
            linked = await repository.ensure_artifact_link(
                asset=existing,
                artifact_name=descriptor.artifact_name,
                metadata=metadata,
            )
            status = "linked_existing_object" if linked else "skipped_database_duplicate"
            return {**record, "status": status, "media_asset_id": str(existing.id)}

        if not dry_run:
            uploaded = storage.upload_if_missing(
                source_path=path,
                object_key=object_key,
                mime_type=descriptor.mime_type,
            )
            metadata = {
                "source_relative_path": descriptor.source_relative_path,
                "source_category": descriptor.source_category,
                "artifact_hint": descriptor.artifact_hint,
                "association_confidence": descriptor.association_confidence,
            }
            asset = await repository.create_media_asset(
                artifact_name=descriptor.artifact_name,
                object_key=object_key,
                original_filename=path.name,
                media_type=descriptor.media_type,
                mime_type=descriptor.mime_type,
                byte_size=path.stat().st_size,
                sha256=sha256,
                metadata=metadata,
            )
            return {
                **record,
                "status": "uploaded" if uploaded else "registered_existing_object",
                "media_asset_id": str(asset.id),
            }

    return {**record, "status": "dry_run"}


def write_report(path: Path, records: list[dict[str, Any]], dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    statuses = Counter(record["status"] for record in records)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "dry_run": dry_run,
        "summary": dict(statuses),
        "records": records,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload media to MinIO with SHA-256 deduplication."
    )
    parser.add_argument("knowledge_root", type=Path)
    parser.add_argument(
        "--types",
        nargs="+",
        choices=["audio", "image", "video"],
        default=["audio", "image", "video"],
    )
    parser.add_argument("--limit", type=int, default=None, help="For a small verification batch.")
    parser.add_argument(
        "--min-size-mb",
        type=float,
        default=None,
        help="Only import files at or above this size; useful for separately handling large videos.",
    )
    parser.add_argument(
        "--source-categories",
        nargs="+",
        help="Only import selected top-level folders under the knowledge root.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, help="Optional UTF-8 JSON audit report path.")
    args = parser.parse_args()

    knowledge_root = args.knowledge_root.resolve()
    if not knowledge_root.is_dir():
        raise SystemExit(f"Knowledge root not found: {knowledge_root}")

    files = find_media_files(knowledge_root, set(args.types))
    if args.source_categories:
        categories = set(args.source_categories)
        files = [path for path in files if path.relative_to(knowledge_root).parts[0] in categories]
    if args.min_size_mb is not None:
        min_bytes = int(args.min_size_mb * 1024 * 1024)
        files = [path for path in files if path.stat().st_size >= min_bytes]
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No supported media files found for the selected types.")

    storage = MinioStorage()
    if not args.dry_run:
        storage.ensure_bucket()

    records: list[dict[str, Any]] = []
    for index, path in enumerate(files, start=1):
        record = await import_file(
            path=path,
            knowledge_root=knowledge_root,
            storage=storage,
            dry_run=args.dry_run,
        )
        records.append(record)
        print(f"[{index}/{len(files)}] {record['status']}: {record['source_relative_path']}")

    if args.report:
        write_report(args.report, records, args.dry_run)
        print(f"Report: {args.report}")

    print(json.dumps(dict(Counter(record["status"] for record in records)), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
