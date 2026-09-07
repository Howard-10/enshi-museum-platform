"""Database-backed keyword retrieval used until an embedding model is configured.

This service deliberately returns evidence, not generated claims. Its output is
also the keyword half of the later hybrid (keyword + vector) RAG pipeline.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.core import (
    Artifact,
    ArtifactAlias,
    ArtifactCatalogRecord,
    ArtifactDocumentLink,
    ArtifactMediaLink,
    Document,
    DocumentChunk,
    DocumentEvidenceReview,
    MediaAsset,
)
from app.services.minio_storage import MinioStorage

MAX_QUERY_TERMS = 24
MAX_DOCUMENT_CANDIDATES = 80
MAX_DOCUMENT_RESULTS = 6
MAX_ARTIFACT_RESULTS = 5
MAX_MEDIA_RESULTS_PER_TYPE = 12

# Curated visitor-language hints for the structured catalog. These are kept
# separate from approved aliases because they describe a concept (for example,
# “读书高中” → “状元”), not an alternate artifact name.
CATALOG_CONCEPT_HINTS: dict[str, tuple[str, ...]] = {
    "香炉": ("炉",),
    "瓷瓶": ("瓶",),
    "读书": ("状元",),
    "高中": ("状元",),
    "诰命": ("诰命",),
    "人物": ("人物",),
    "土司印": ("长官司印", "司印"),
}

REQUEST_NOISE = re.compile(
    r"请问|请|帮我|介绍一下|介绍|讲讲|说说|告诉我|有哪些|有什么|是什么|怎么样|如何|的|吗|呢"
)
NON_WORD = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")


@dataclass(frozen=True)
class ArtifactMatch:
    id: str
    name: str
    era: str | None
    location: str | None
    material: str | None
    score: int
    catalog_record_id: str | None = None
    catalog_source_uri: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "era": self.era,
            "location": self.location,
            "material": self.material,
            "score": self.score,
            "catalog_record_id": self.catalog_record_id,
            "catalog_source_uri": self.catalog_source_uri,
        }


def extract_search_terms(query: str) -> list[str]:
    """Build conservative Chinese-friendly literal terms for PostgreSQL ILIKE."""

    compact = NON_WORD.sub("", query).strip()
    if not compact:
        return []
    cleaned = REQUEST_NOISE.sub(" ", compact)
    fragments = [part.strip() for part in cleaned.split() if len(part.strip()) >= 2]

    # Keep the complete query and cleaned phrases first for exact matches, then
    # add two-character windows before longer windows. This prevents the term
    # budget from dropping a meaningful word near the end of a long Chinese
    # question (for example “诰命” in a descriptive query).
    terms: list[str] = [compact, *fragments]
    for fragment in fragments:
        terms.extend(
            fragment[start : start + 2] for start in range(len(fragment) - 1)
        )
    for fragment in fragments:
        max_size = min(6, len(fragment))
        for size in range(3, max_size + 1):
            terms.extend(
                fragment[start : start + size] for start in range(len(fragment) - size + 1)
            )

    unique: list[str] = []
    for term in terms:
        if term not in unique:
            unique.append(term)
        if len(unique) == MAX_QUERY_TERMS:
            break
    return unique


def score_text(text: str, terms: Iterable[str]) -> int:
    return sum(len(term) * 10 for term in terms if term in text)


def name_overlap_score(name: str, query: str) -> int:
    """Score meaningful two-character name fragments found in a natural query."""

    compact_query = NON_WORD.sub("", query)
    fragments = {name[index : index + 2] for index in range(len(name) - 1)}
    matched = {fragment for fragment in fragments if fragment in compact_query}
    # One common fragment is too weak; two or more fragments are a useful,
    # deterministic signal for descriptive questions such as “凤凰和八卦铜镜”.
    return len(matched) * 20 if len(matched) >= 2 else 0


def catalog_concept_score(name: str, query: str) -> int:
    """Score a small set of curated natural-language catalog concepts."""

    return sum(
        120 if len(hint) >= 2 else 45
        for phrase, hints in CATALOG_CONCEPT_HINTS.items()
        if phrase in query
        for hint in hints
        if hint in name
    )


def catalog_metadata_score(value: str | None, query: str) -> int:
    """Give structured catalog filters priority in descriptive questions."""

    if not value:
        return 0
    compact_query = NON_WORD.sub("", query)
    parts = [part for part in re.split(r"[、,，/及]", value) if part]
    return 70 if any(part in compact_query or f"{part}代" in compact_query for part in parts) else 0


def excerpt_for(text: str, terms: Iterable[str], *, max_length: int = 220) -> str:
    start = next((text.find(term) for term in terms if text.find(term) >= 0), 0)
    left = max(0, start - 50)
    right = min(len(text), left + max_length)
    prefix = "…" if left else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{text[left:right].strip()}{suffix}"


class KeywordRetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        *,
        include_media: bool,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        terms = extract_search_terms(query)
        artifacts = await self._find_artifacts(terms, query)
        document_matches = await self._find_document_matches(terms, artifacts)
        media, media_review_status = (
            await self._find_media(artifacts, media_type=media_type)
            if include_media
            else ([], None)
        )
        approved_links = await self._approved_document_link_ids(document_matches, artifacts)
        approved_document_reviews = await self._approved_document_review_ids(document_matches)
        citations = [
            {
                "source_type": "internal",
                "id": item["chunk_id"],
                "document_id": item["document_id"],
                "chunk_id": item["chunk_id"],
                "title": item["title"],
                "url": None,
                "excerpt": item["excerpt"],
            }
            for item in document_matches
        ]
        # For an exact artifact-name request, keep only the longest exact
        # catalog match. Shorter names such as “铜镜” are related candidates,
        # not evidence for the specific object “凤凰八卦铜镜”.
        compact_query = NON_WORD.sub("", query)
        exact_matches = [
            artifact
            for artifact in artifacts
            if artifact.catalog_record_id
            and artifact.name
            and NON_WORD.sub("", artifact.name) in compact_query
        ]
        exact_name_length = max(
            (len(NON_WORD.sub("", artifact.name)) for artifact in exact_matches),
            default=0,
        )
        catalog_artifacts = (
            [
                artifact
                for artifact in exact_matches
                if len(NON_WORD.sub("", artifact.name)) == exact_name_length
            ]
            if exact_name_length
            else [artifact for artifact in artifacts if artifact.catalog_record_id]
        )
        catalog_citations = [
            {
                "source_type": "internal",
                "id": f"catalog:{artifact.id}",
                "document_id": None,
                "chunk_id": None,
                "title": f"{artifact.name}（标准目录）",
                "url": artifact.catalog_source_uri,
                "excerpt": "；".join(
                    value
                    for value in (
                        f"名称：{artifact.name}",
                        f"年代：{artifact.era}" if artifact.era else None,
                        f"地点：{artifact.location}" if artifact.location else None,
                        f"材质：{artifact.material}" if artifact.material else None,
                    )
                    if value
                ),
                "authority_level": "P1_catalog",
            }
            for artifact in catalog_artifacts
        ]
        return {
            "mode": "keyword",
            "query_terms": terms,
            "artifacts": [artifact.as_dict() for artifact in artifacts],
            "document_matches": document_matches,
            "citations": citations,
            "catalog_citations": catalog_citations,
            "media": media,
            "has_approved_document_link": bool(approved_links),
            "approved_document_link_ids": approved_links,
            "has_approved_document_review": bool(approved_document_reviews),
            "approved_document_review_ids": approved_document_reviews,
            "media_review_status": media_review_status,
        }

    async def _find_artifacts(self, terms: list[str], query: str) -> list[ArtifactMatch]:
        catalog_rows = (
            await self.session.scalars(
                select(ArtifactCatalogRecord)
                .join(Artifact, Artifact.id == ArtifactCatalogRecord.artifact_id)
                .options(joinedload(ArtifactCatalogRecord.artifact))
                .where(ArtifactCatalogRecord.record_kind == "artifact")
                .where(ArtifactCatalogRecord.artifact_id.is_not(None))
                .order_by(Artifact.name, ArtifactCatalogRecord.row_number)
            )
        ).all()
        catalog_by_artifact_id: dict[str, ArtifactCatalogRecord] = {}
        for row in catalog_rows:
            artifact = row.artifact
            if artifact is None:
                continue
            catalog_by_artifact_id.setdefault(str(artifact.id), row)
        all_artifacts = (await self.session.scalars(select(Artifact).order_by(Artifact.name))).all()
        approved_aliases = (
            await self.session.execute(
                select(ArtifactAlias.artifact_id, ArtifactAlias.alias).where(
                    ArtifactAlias.review_status == "approved"
                )
            )
        ).all()
        aliases_by_artifact: dict[str, list[str]] = {}
        for artifact_id, alias in approved_aliases:
            aliases_by_artifact.setdefault(str(artifact_id), []).append(alias)

        best: dict[str, ArtifactMatch] = {}
        for artifact in all_artifacts:
            row = catalog_by_artifact_id.get(str(artifact.id))
            base_score = max(
                score_text(artifact.name, terms),
                name_overlap_score(artifact.name, query),
                *(
                    score_text(alias, terms)
                    for alias in aliases_by_artifact.get(str(artifact.id), [])
                ),
                score_text((artifact.era or ""), terms),
                score_text((row.location or "") if row else "", terms),
                score_text((row.material or "") if row else "", terms),
            )
            metadata_score = sum(
                catalog_metadata_score(value, query)
                for value in (
                    row.era if row else None,
                    row.location if row else None,
                    row.material if row else None,
                )
            )
            score = base_score + metadata_score + catalog_concept_score(artifact.name, query)
            if not score:
                continue
            match = ArtifactMatch(
                id=str(artifact.id),
                name=artifact.name,
                era=(row.era if row else None) or artifact.era,
                location=row.location if row else None,
                material=row.material if row else None,
                score=score,
                catalog_record_id=str(row.id) if row else None,
                catalog_source_uri=row.source_uri if row else None,
            )
            prior = best.get(match.id)
            if prior is None or match.score > prior.score:
                best[match.id] = match
        return sorted(best.values(), key=lambda item: (-item.score, item.name))[
            :MAX_ARTIFACT_RESULTS
        ]

    async def _find_document_matches(
        self,
        terms: list[str],
        artifacts: list[ArtifactMatch],
    ) -> list[dict[str, Any]]:
        document_terms = list(terms)
        document_terms.extend(
            artifact.name for artifact in artifacts if artifact.name not in document_terms
        )
        if not document_terms:
            return []
        # Broader 2–6 character terms are useful for text recall, but title
        # candidates are collected as documents first so one large document
        # cannot use all SQL result slots before another matching title appears.
        title_terms = list(document_terms)
        title_conditions = [Document.title.ilike(f"%{term}%") for term in title_terms]
        title_documents = (
            await self.session.scalars(
                select(Document).where(or_(*title_conditions)).order_by(Document.title)
            )
        ).all()
        title_documents = sorted(
            title_documents,
            key=lambda document: (
                -score_text(document.title, title_terms),
                document.title,
            ),
        )
        title_document_ids = [document.id for document in title_documents[:12]]
        title_priority_ids = {str(document.id) for document in title_documents[:12]}
        title_statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.chunk_level == "child",
                Document.id.in_(title_document_ids),
            )
        )
        if title_document_ids:
            title_statement = title_statement.limit(MAX_DOCUMENT_CANDIDATES)
        content_conditions = [DocumentChunk.content.ilike(f"%{term}%") for term in document_terms]
        content_statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.chunk_level == "child")
            .where(or_(*content_conditions))
            .limit(MAX_DOCUMENT_CANDIDATES)
        )
        title_rows = []
        if title_document_ids:
            title_rows = (
                await self.session.execute(
                    title_statement.order_by(DocumentChunk.sequence).limit(24)
                )
            ).all()
        candidate_rows = [*title_rows, *(await self.session.execute(content_statement)).all()]
        rows = list(
            {str(chunk.id): (chunk, document) for chunk, document in candidate_rows}.values()
        )

        def rank_score(pair: tuple[DocumentChunk, Document]) -> int:
            chunk, document = pair
            content_score = score_text(chunk.content, document_terms)
            title_score = score_text(document.title, title_terms)
            exact_title_bonus = max(
                (len(term) * 1_000 for term in title_terms if term in document.title),
                default=0,
            )
            title_priority_bonus = 1_000_000 if str(document.id) in title_priority_ids else 0
            return content_score + (title_score * 40) + exact_title_bonus + title_priority_bonus

        ranked = sorted(
            rows,
            key=lambda pair: (
                -rank_score(pair),
                pair[1].title,
                pair[0].sequence,
            ),
        )
        results: list[dict[str, Any]] = []
        seen_documents: set[str] = set()
        for chunk, document in ranked:
            document_id = str(document.id)
            if document_id in seen_documents:
                continue
            seen_documents.add(document_id)
            results.append(
                {
                    "document_id": document_id,
                    "chunk_id": str(chunk.id),
                    "title": document.title,
                    "excerpt": excerpt_for(chunk.content, document_terms),
                    "score": rank_score((chunk, document)),
                }
            )
            if len(results) == MAX_DOCUMENT_RESULTS:
                break
        return results

    async def _find_media(
        self,
        artifacts: list[ArtifactMatch],
        *,
        media_type: str | None = None,
    ) -> tuple[list[dict[str, str]], str | None]:
        if not artifacts:
            return [], None
        artifact_ids = [UUID(artifact.id) for artifact in artifacts]
        statement = (
            select(MediaAsset)
            .join(ArtifactMediaLink, ArtifactMediaLink.media_asset_id == MediaAsset.id)
            .where(ArtifactMediaLink.artifact_id.in_(artifact_ids))
            .where(ArtifactMediaLink.review_status.in_(("approved", "legacy_verified")))
            .order_by(MediaAsset.media_type, MediaAsset.original_filename)
            .distinct()
        )
        if media_type:
            statement = statement.where(MediaAsset.media_type == media_type).limit(
                MAX_MEDIA_RESULTS_PER_TYPE
            )
        else:
            # Keep all three media types visible for a general media request.
            # A single global limit used to hide videos behind many audio files.
            statement = statement.limit(MAX_MEDIA_RESULTS_PER_TYPE * 3)
        rows = (await self.session.execute(statement)).scalars().all()
        storage = MinioStorage()
        items = [
            {
                "id": str(asset.id),
                "type": asset.media_type,
                "url": storage.presigned_download_url(asset.object_key, expires_seconds=600),
            }
            for asset in rows
        ]
        statuses = {
            link.review_status
            for link in (
                await self.session.scalars(
                    select(ArtifactMediaLink).where(
                        ArtifactMediaLink.artifact_id.in_(artifact_ids),
                        ArtifactMediaLink.review_status.in_(("approved", "legacy_verified")),
                    )
                )
            ).all()
        }
        return items, "approved" if statuses == {"approved"} else "legacy_verified"

    async def _approved_document_link_ids(
        self, documents: list[dict[str, Any]], artifacts: list[ArtifactMatch]
    ) -> list[str]:
        if not documents or not artifacts:
            return []
        rows = (
            await self.session.scalars(
                select(ArtifactDocumentLink).where(
                    ArtifactDocumentLink.document_id.in_(
                        [UUID(item["document_id"]) for item in documents]
                    ),
                    ArtifactDocumentLink.artifact_id.in_([UUID(item.id) for item in artifacts]),
                    ArtifactDocumentLink.review_status == "approved",
                )
            )
        ).all()
        return [str(row.id) for row in rows]

    async def _approved_document_review_ids(
        self, documents: list[dict[str, Any]]
    ) -> list[str]:
        """Return approved source documents, including background-only Word files."""

        if not documents:
            return []
        rows = (
            await self.session.scalars(
                select(DocumentEvidenceReview).where(
                    DocumentEvidenceReview.document_id.in_(
                        [UUID(item["document_id"]) for item in documents]
                    ),
                    DocumentEvidenceReview.review_status == "approved",
                )
            )
        ).all()
        return [str(row.document_id) for row in rows]
