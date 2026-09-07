"""Extract safely mapped Excel cell images, upload them to MinIO and register links."""

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
from app.services.media_ingestion import build_object_key
from app.services.minio_storage import MinioStorage
from app.services.xlsx_embedded_images import read_embedded_images


def find_workbooks(knowledge_root: Path) -> list[Path]:
    return sorted(
        path
        for path in knowledge_root.rglob("*.xlsx")
        if path.is_file() and not path.name.startswith("~$")
    )


async def import_image(
    *,
    image: Any,
    storage: MinioStorage,
    dry_run: bool,
) -> dict[str, Any]:
    sha256 = image.sha256
    suffix = Path(image.image_part).suffix
    object_key = build_object_key(media_type="image", sha256=sha256, suffix=suffix)
    metadata = {
        "source_kind": "xlsx_embedded_image",
        "source_relative_path": image.workbook_relative_path,
        "source_reference": image.source_reference,
        "source_sheet": image.sheet_name,
        "source_cell": image.cell_coordinate,
        "source_image_part": image.image_part,
        "association_confidence": "xlsx_row",
    }
    record = {
        "source_reference": image.source_reference,
        "artifact_name": image.artifact_name,
        "sha256": sha256,
        "object_key": object_key,
        "mime_type": image.mime_type,
        "byte_size": len(image.data),
    }

    async with SessionLocal() as session:
        repository = MediaRepository(session)
        existing = await repository.get_by_sha256(sha256)
        if existing is not None:
            if dry_run:
                return {
                    **record,
                    "status": "dry_run_existing_object",
                    "media_asset_id": str(existing.id),
                }
            linked = await repository.ensure_artifact_link(
                asset=existing,
                artifact_name=image.artifact_name,
                metadata=metadata,
            )
            return {
                **record,
                "status": "linked_existing_object" if linked else "skipped_database_duplicate",
                "media_asset_id": str(existing.id),
            }

        if dry_run:
            return {**record, "status": "dry_run"}

        uploaded = storage.upload_bytes_if_missing(
            data=image.data,
            object_key=object_key,
            mime_type=image.mime_type,
        )
        asset = await repository.create_media_asset(
            artifact_name=image.artifact_name,
            object_key=object_key,
            original_filename=f"{Path(image.workbook_relative_path).name}:{image.image_part}",
            media_type="image",
            mime_type=image.mime_type,
            byte_size=len(image.data),
            sha256=sha256,
            metadata=metadata,
        )
        return {
            **record,
            "status": "uploaded" if uploaded else "registered_existing_object",
            "media_asset_id": str(asset.id),
        }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract mapped XLSX images and import them into MinIO."
    )
    parser.add_argument("knowledge_root", type=Path)
    parser.add_argument(
        "--workbook-contains", help="Only process workbooks whose path contains this text."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    knowledge_root = args.knowledge_root.resolve()
    workbooks = find_workbooks(knowledge_root)
    if args.workbook_contains:
        workbooks = [path for path in workbooks if args.workbook_contains in str(path)]
    if not workbooks:
        raise SystemExit("No matching workbooks found.")

    storage = MinioStorage()
    if not args.dry_run:
        storage.ensure_bucket()

    records: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for workbook_path in workbooks:
        images, workbook_issues = read_embedded_images(workbook_path, knowledge_root)
        issues.extend(issue.__dict__ for issue in workbook_issues)
        for image in images:
            record = await import_image(image=image, storage=storage, dry_run=args.dry_run)
            records.append(record)
            print(f"{record['status']}: {record['source_reference']}")

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "dry_run": args.dry_run,
        "summary": {
            "workbooks": len(workbooks),
            "images_seen": len(records),
            "issues": len(issues),
            **dict(Counter(record["status"] for record in records)),
        },
        "records": records,
        "issues": issues,
    }
    write_report(args.report, report)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
