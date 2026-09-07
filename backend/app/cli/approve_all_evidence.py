"""Explicitly promote all current evidence-review candidates after user approval."""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import select

from app.db.models.core import ArtifactAlias, ArtifactDocumentLink, DocumentEvidenceReview
from app.db.session import SessionLocal


async def approve_all(*, apply: bool) -> dict[str, object]:
    async with SessionLocal() as session:
        document_reviews = list((await session.scalars(select(DocumentEvidenceReview))).all())
        document_links = list((await session.scalars(select(ArtifactDocumentLink))).all())
        aliases = list((await session.scalars(select(ArtifactAlias))).all())
        if apply:
            note = "用户确认批量通过；后续可按需抽查或回退。"
            for item in document_reviews:
                item.review_status = "approved"
                item.review_note = note
            for item in document_links:
                item.review_status = "approved"
                item.review_note = note
            for item in aliases:
                item.review_status = "approved"
                item.review_note = note
            await session.commit()
    return {
        "mode": "applied" if apply else "dry_run",
        "document_reviews": len(document_reviews),
        "document_links": len(document_links),
        "aliases": len(aliases),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve all current evidence-review candidates.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply the batch approval. Without this flag only a preview is printed.",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(approve_all(apply=args.yes)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
