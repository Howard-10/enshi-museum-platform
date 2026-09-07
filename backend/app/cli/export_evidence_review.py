"""Export candidate evidence links for human review without changing review state."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.models.core import Artifact, ArtifactDocumentLink, Document, DocumentEvidenceReview
from app.db.session import SessionLocal


async def export_review(output: Path) -> dict[str, object]:
    async with SessionLocal() as session:
        link_rows = await session.execute(
            select(ArtifactDocumentLink, Artifact, Document)
            .join(Artifact, Artifact.id == ArtifactDocumentLink.artifact_id)
            .join(Document, Document.id == ArtifactDocumentLink.document_id)
            .order_by(ArtifactDocumentLink.review_status, Artifact.name, Document.title)
        )
        document_rows = await session.execute(
            select(Document, DocumentEvidenceReview)
            .outerjoin(DocumentEvidenceReview, DocumentEvidenceReview.document_id == Document.id)
            .order_by(Document.title)
        )

    links = [
        {
            "link_id": str(link.id),
            "artifact_name": artifact.name,
            "document_title": document.title,
            "source_filename": document.source_filename,
            "confidence": link.confidence,
            "match_reasons": "； ".join(link.match_reasons),
            "current_status": link.review_status,
            "current_note": link.review_note or "",
            "review_decision": "",
            "review_note": "",
        }
        for link, artifact, document in link_rows.all()
    ]
    documents = [
        {
            "document_id": str(document.id),
            "document_title": document.title,
            "source_filename": document.source_filename,
            "current_status": review.review_status if review else "missing",
            "current_note": review.review_note if review and review.review_note else "",
            "review_decision": "",
            "review_note": "",
        }
        for document, review in document_rows.all()
    ]
    payload = {"links": links, "documents": documents}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"output": str(output), "link_rows": len(links), "document_rows": len(documents)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export human-review evidence candidates.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(export_review(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
