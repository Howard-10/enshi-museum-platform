"""Candidate generation for the human evidence-review workflow.

Candidates are deliberately stored as ``needs_review``. This module never
promotes a Word document, alias, or media relationship to usable evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import (
    Artifact,
    ArtifactAlias,
    ArtifactDocumentLink,
    Document,
    DocumentEvidenceReview,
)

REVIEW_NEEDS = "needs_review"
APPROVED = "approved"
_PUNCTUATION = re.compile(r"[\s\-—_（）()【】\[\]、，,。．·]+")


def normalized_name(value: str) -> str:
    return _PUNCTUATION.sub("", value).strip()


@dataclass(frozen=True)
class CandidateSummary:
    documents_scanned: int
    artifact_alias_candidates: int
    document_link_candidates: int


def _document_match_reasons(
    document: Document, artifact: Artifact, aliases: list[str]
) -> list[str]:
    haystacks = {
        "title": document.title,
        "source_filename": document.source_filename,
        "body": document.full_text,
    }
    reasons: list[str] = []
    for term in [artifact.name, *aliases]:
        if len(term) < 2:
            continue
        for place, text in haystacks.items():
            if term in text:
                reasons.append(f"{place}:{term}")
    return reasons


def _confidence(reasons: list[str], artifact_name: str) -> int:
    if f"title:{artifact_name}" in reasons or f"source_filename:{artifact_name}" in reasons:
        return 95
    if any(reason.startswith(("title:", "source_filename:")) for reason in reasons):
        return 80
    if any(reason.startswith("body:") for reason in reasons):
        return 60
    return 0


async def generate_review_candidates(session: AsyncSession) -> CandidateSummary:
    """Create idempotent candidates for all imported Word documents and catalog artifacts."""

    artifacts = list((await session.scalars(select(Artifact).order_by(Artifact.name))).all())
    documents = list((await session.scalars(select(Document).order_by(Document.title))).all())
    existing_aliases = {
        (str(item.artifact_id), item.alias)
        for item in (await session.scalars(select(ArtifactAlias))).all()
    }
    existing_links = {
        (str(item.artifact_id), str(item.document_id))
        for item in (await session.scalars(select(ArtifactDocumentLink))).all()
    }
    reviewed_document_ids = {
        item.document_id for item in (await session.scalars(select(DocumentEvidenceReview))).all()
    }
    alias_count = 0
    link_count = 0
    aliases_by_artifact: dict[str, list[str]] = {}
    for artifact in artifacts:
        candidate = normalized_name(artifact.name)
        aliases_by_artifact[str(artifact.id)] = [candidate] if candidate != artifact.name else []
        if (
            candidate
            and candidate != artifact.name
            and (str(artifact.id), candidate) not in existing_aliases
        ):
            session.add(
                ArtifactAlias(
                    artifact_id=artifact.id,
                    alias=candidate,
                    source_reference="auto:normalized_catalog_name",
                    review_status=REVIEW_NEEDS,
                    review_note="自动候选：仅移除名称中的空白和标点；需人工确认后才能用于检索。",
                )
            )
            alias_count += 1
    await session.flush()

    approved_or_candidate_aliases = list((await session.scalars(select(ArtifactAlias))).all())
    for item in approved_or_candidate_aliases:
        aliases_by_artifact.setdefault(str(item.artifact_id), []).append(item.alias)

    for document in documents:
        if document.id not in reviewed_document_ids:
            session.add(
                DocumentEvidenceReview(
                    document_id=document.id,
                    review_status=REVIEW_NEEDS,
                    review_note="待审核：已生成候选关联；无候选时也需要确认其是否属于背景资料。",
                )
            )
        for artifact in artifacts:
            artifact_aliases = aliases_by_artifact.get(str(artifact.id), [])
            reasons = _document_match_reasons(document, artifact, artifact_aliases)
            if not reasons or (str(artifact.id), str(document.id)) in existing_links:
                continue
            session.add(
                ArtifactDocumentLink(
                    artifact_id=artifact.id,
                    document_id=document.id,
                    match_reasons=reasons,
                    confidence=_confidence(reasons, artifact.name),
                    review_status=REVIEW_NEEDS,
                    review_note="自动候选，尚未审核；不得作为馆藏事实证据。",
                )
            )
            link_count += 1
    await session.commit()
    return CandidateSummary(
        documents_scanned=len(documents),
        artifact_alias_candidates=alias_count,
        document_link_candidates=link_count,
    )


async def review_coverage(session: AsyncSession) -> dict[str, int]:
    """Return a read-only review dashboard for Phase 0 acceptance."""

    documents = await session.scalar(select(func.count()).select_from(Document))
    reviewed_documents = await session.scalar(
        select(func.count()).select_from(DocumentEvidenceReview)
    )
    links = list((await session.scalars(select(ArtifactDocumentLink))).all())
    aliases = list((await session.scalars(select(ArtifactAlias))).all())
    return {
        "documents": documents or 0,
        "documents_with_review_status": reviewed_documents or 0,
        "document_links_approved": sum(item.review_status == APPROVED for item in links),
        "document_links_needs_review": sum(item.review_status == REVIEW_NEEDS for item in links),
        "aliases_approved": sum(item.review_status == APPROVED for item in aliases),
        "aliases_needs_review": sum(item.review_status == REVIEW_NEEDS for item in aliases),
    }
