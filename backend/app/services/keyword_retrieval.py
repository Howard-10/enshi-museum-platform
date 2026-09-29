"""Database-backed keyword retrieval used until an embedding model is configured.

This service deliberately returns evidence, not generated claims. Its output is
also the keyword half of the later hybrid (keyword + vector) RAG pipeline.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
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
    r"请问|请|帮我|给我|我想|关于|查询|查一下|查看|介绍一下|介绍|讲讲|说说|告诉我|有哪些|有什么|是什么|怎么样|如何|的|吗|呢"
)
NON_WORD = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")
MEDIA_QUERY_WORDS = (
    "图片", "照片", "配图", "原图", "视频", "录像", "音频", "语音", "录音",
    "播放", "看看", "看一下", "听听", "听一下", "媒体", "多媒体", "相关资料",
)


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


def artifact_query_for_media(query: str) -> str:
    """Remove delivery words before resolving the requested artifact."""

    cleaned = query
    for word in MEDIA_QUERY_WORDS:
        cleaned = cleaned.replace(word, "")
    return REQUEST_NOISE.sub("", cleaned).strip()


def media_subject_for_query(query: str, media: list[dict[str, str]]) -> str | None:
    """Recover a display subject from a verified media filename."""

    subject = artifact_query_for_media(query)
    compact_subject = NON_WORD.sub("", subject)
    if len(compact_subject) < 2:
        return None
    for item in media:
        filename = NON_WORD.sub("", str(item.get("filename") or ""))
        if compact_subject in filename:
            return subject
    return None


def score_text(text: str, terms: Iterable[str]) -> int:
    return sum(len(term) * 10 for term in terms if term in text)


def name_overlap_score(name: str, query: str) -> int:
    """Score evidence that the *name* matches a descriptive question.

    The previous implementation gave every artifact with a matching era or
    material a larger score than a specifically-described artifact.  For
    example, ``明代铜镜`` could rank a generic copper vessel above
    ``凤凰八卦铜镜`` because the latter only received a small two-character
    overlap bonus.  Name n-grams are a stronger identity signal than catalog
    metadata, while a single generic n-gram (``铜镜``/``石碑``) remains weak.
    """

    compact_query = NON_WORD.sub("", query)
    compact_name = NON_WORD.sub("", name)
    if not compact_name or not compact_query:
        return 0
    if compact_name in compact_query and (
        compact_query == compact_name or len(compact_name) >= 3
    ):
        # Exact name mentions must dominate incidental metadata matches.
        # Longer names are more specific than generic suffixes such as
        # ``铜镜``.  This matters when a descriptive query contains both.
        return 5_000 + len(compact_name) * 1_500

    matched_2grams = {
        compact_name[index : index + 2]
        for index in range(len(compact_name) - 1)
        if compact_name[index : index + 2] in compact_query
    }
    matched_3grams = {
        compact_name[index : index + 3]
        for index in range(len(compact_name) - 2)
        if compact_name[index : index + 3] in compact_query
    }
    # Three-character overlaps are more discriminative than two-character
    # overlaps.  Keep a single generic overlap useful, but not decisive.
    overlap_score = len(matched_3grams) * 180 + len(matched_2grams) * 90
    # A small typo should not make a known catalog name disappear. Only use
    # fuzzy similarity for a short query fragment; long natural-language
    # questions are already handled by exact n-gram and metadata signals.
    fuzzy_score = 0
    query_fragments = [fragment for fragment in re.split(r"[\s，。！？?、]+", compact_query) if fragment]
    if len(compact_name) >= 3:
        similarity = max(
            (SequenceMatcher(None, compact_name, fragment).ratio() for fragment in query_fragments),
            default=0.0,
        )
        if similarity >= 0.72:
            fuzzy_score = int(similarity * 220)
    return overlap_score + fuzzy_score


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


def excerpt_for(text: str, terms: Iterable[str], *, max_length: int | None = None) -> str:
    """Return the evidence text without silently hiding source content.

    Retrieval callers use the complete child chunk by default so the visitor
    can read the full evidence shown in an answer or citation. A bounded
    excerpt remains available for future ranking-only callers by passing an
    explicit ``max_length``.
    """

    clean_text = text.strip()
    if max_length is None or len(clean_text) <= max_length:
        return clean_text
    start = next((clean_text.find(term) for term in terms if clean_text.find(term) >= 0), 0)
    left = max(0, start - 50)
    right = min(len(clean_text), left + max_length)
    return clean_text[left:right].strip()


class KeywordRetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        *,
        include_media: bool,
        media_type: str | None = None,
        media_types: list[str] | tuple[str, ...] | None = None,
        preferred_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        terms = extract_search_terms(query)
        artifact_query = artifact_query_for_media(query) if include_media else query
        if preferred_artifact_id:
            preferred_artifact = await self.session.scalar(
                select(Artifact).where(Artifact.id == UUID(preferred_artifact_id))
            )
            if preferred_artifact is not None:
                artifact_query = f"{preferred_artifact.name} {artifact_query}".strip()
                terms = [preferred_artifact.name, *terms]
        artifact_terms = extract_search_terms(artifact_query)
        artifacts = await self._find_artifacts(artifact_terms, artifact_query)
        document_matches = await self._find_document_matches(terms, artifacts)
        resolved_media_types = tuple(media_types or ((media_type,) if media_type else ()))
        media, media_review_status = (
            await self._find_media(query, artifacts, media_types=resolved_media_types)
            if include_media
            else ([], None)
        )
        artifact_items = [artifact.as_dict() for artifact in artifacts]
        media_subject = media_subject_for_query(query, media) if media else None
        if media_subject and not any(item["name"] == media_subject for item in artifact_items):
            # This is presentation metadata, not a catalog match. It lets the
            # visitor-facing response name the verified media subject instead
            # of exposing a generic import-folder artifact.
            artifact_items.insert(
                0,
                {
                    "id": f"media:{media[0]['id']}",
                    "name": media_subject,
                    "era": None,
                    "location": None,
                    "material": None,
                    "score": 4_000,
                    "catalog_record_id": None,
                    "catalog_source_uri": None,
                    "match_kind": "media_filename",
                },
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
                "section_path": item.get("section_path", []),
                "source_filename": item.get("source_filename"),
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
            "artifacts": artifact_items,
            "document_matches": document_matches,
            "citations": citations,
            "catalog_citations": catalog_citations,
            "media": media,
            "has_approved_document_link": bool(approved_links),
            "approved_document_link_ids": approved_links,
            "has_approved_document_review": bool(approved_document_reviews),
            "approved_document_review_ids": approved_document_reviews,
            "media_review_status": media_review_status,
            "media_types": list(resolved_media_types),
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
            name_score = name_overlap_score(artifact.name, query)
            compact_artifact_name = NON_WORD.sub("", artifact.name)
            compact_query = NON_WORD.sub("", query)
            exact_name_score = (
                5_000 + len(compact_artifact_name) * 1_500
                if compact_artifact_name in compact_query
                and (compact_query == compact_artifact_name or len(compact_artifact_name) >= 3)
                else 0
            )
            base_score = max(
                exact_name_score,
                name_score,
                score_text(artifact.name, terms),
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
        content_conditions = [
            expression.ilike(f"%{term}%")
            for term in document_terms
            for expression in (
                DocumentChunk.content,
                DocumentChunk.metadata_json["heading_path"].astext,
                DocumentChunk.metadata_json["heading_text"].astext,
            )
        ]
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
            metadata = chunk.metadata_json or {}
            heading_path = " > ".join(str(item) for item in metadata.get("heading_path", []))
            heading_score = score_text(heading_path, document_terms)
            title_score = score_text(document.title, title_terms)
            exact_title_bonus = max(
                (len(term) * 1_000 for term in title_terms if term in document.title),
                default=0,
            )
            title_priority_bonus = 1_000_000 if str(document.id) in title_priority_ids else 0
            return content_score + (heading_score * 90) + (title_score * 40) + exact_title_bonus + title_priority_bonus

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
        seen_sources: set[tuple[str, str]] = set()
        for chunk, document in ranked:
            document_id = str(document.id)
            if document_id in seen_documents:
                continue
            excerpt = excerpt_for(chunk.content, document_terms)
            source_key = (document.title.strip(), excerpt)
            if source_key in seen_sources:
                continue
            seen_documents.add(document_id)
            seen_sources.add(source_key)
            results.append(
                {
                    "document_id": document_id,
                    "chunk_id": str(chunk.id),
                    "title": document.title,
                    "excerpt": excerpt,
                    "section_path": (chunk.metadata_json or {}).get("heading_path", []),
                    "block_type": (chunk.metadata_json or {}).get("block_type", "paragraph"),
                    "source_filename": (chunk.metadata_json or {}).get("source_filename"),
                    "score": rank_score((chunk, document)),
                }
            )
            if len(results) == MAX_DOCUMENT_RESULTS:
                break
        return results

    async def _find_media(
        self,
        query: str,
        artifacts: list[ArtifactMatch],
        *,
        media_types: tuple[str, ...] = (),
    ) -> tuple[list[dict[str, Any]], str | None]:
        terms = extract_search_terms(query)
        artifact_ids = [UUID(artifact.id) for artifact in artifacts]
        statement = (
            select(MediaAsset)
            .outerjoin(ArtifactMediaLink, ArtifactMediaLink.media_asset_id == MediaAsset.id)
            .where(
                or_(
                    ArtifactMediaLink.artifact_id.in_(artifact_ids) if artifact_ids else False,
                    *[
                        expression.ilike(f"%{term}%")
                        for term in terms
                        for expression in (MediaAsset.original_filename, MediaAsset.object_key)
                    ],
                )
            )
            .where(
                or_(
                    ArtifactMediaLink.review_status.in_(("approved", "legacy_verified")),
                    MediaAsset.metadata_json["association_confidence"].astext.in_(("review", "folder")),
                )
            )
            .order_by(MediaAsset.media_type, MediaAsset.original_filename)
            .distinct()
        )
        if media_types:
            statement = statement.where(MediaAsset.media_type.in_(media_types)).limit(
                MAX_MEDIA_RESULTS_PER_TYPE * len(media_types)
            )
        else:
            statement = statement.limit(MAX_MEDIA_RESULTS_PER_TYPE * 3)
        rows = (await self.session.execute(statement)).scalars().all()
        compact_query = NON_WORD.sub("", query).lower()

        def score(asset: MediaAsset) -> int:
            filename = NON_WORD.sub("", asset.original_filename).lower()
            stem = NON_WORD.sub("", asset.original_filename.rsplit(".", 1)[0]).lower()
            value = 0
            if stem and stem == compact_query:
                value += 1_000
            if filename and filename in compact_query:
                value += 500
            value += sum(120 for term in terms if term.lower() in filename)
            if asset.artifact_id in artifact_ids:
                value += 300
            return value

        rows = sorted(rows, key=lambda asset: (-score(asset), asset.media_type, asset.original_filename))
        rows = [asset for asset in rows if score(asset) > 0]
        if media_types:
            grouped: dict[str, list[MediaAsset]] = {media_type: [] for media_type in media_types}
            for asset in rows:
                if asset.media_type in grouped and len(grouped[asset.media_type]) < MAX_MEDIA_RESULTS_PER_TYPE:
                    grouped[asset.media_type].append(asset)
            rows = [asset for media_type in media_types for asset in grouped[media_type]]
        else:
            rows = rows[: MAX_MEDIA_RESULTS_PER_TYPE * 3]
        link_statuses: dict[str, set[str]] = {}
        link_artifact_ids: dict[str, set[str]] = {}
        if rows:
            link_statement = select(ArtifactMediaLink).where(
                ArtifactMediaLink.media_asset_id.in_([asset.id for asset in rows])
            )
            if artifact_ids:
                link_statement = link_statement.where(
                    ArtifactMediaLink.artifact_id.in_(artifact_ids)
                )
            links = (await self.session.scalars(link_statement)).all()
            for link in links:
                link_statuses.setdefault(str(link.media_asset_id), set()).add(link.review_status)
                link_artifact_ids.setdefault(str(link.media_asset_id), set()).add(str(link.artifact_id))
        storage = MinioStorage()
        items = [
            {
                "id": str(asset.id),
                "type": asset.media_type,
                "url": storage.presigned_download_url(asset.object_key, expires_seconds=600),
                "filename": asset.original_filename,
                "match_reason": "artifact_link" if str(asset.id) in link_artifact_ids else "filename_match",
                "artifact_id": next(iter(link_artifact_ids.get(str(asset.id), set())), None)
                or (str(asset.artifact_id) if asset.artifact_id in artifact_ids else None),
                "evidence_status": (
                    "approved"
                    if "approved" in link_statuses.get(str(asset.id), set())
                    else "legacy_verified"
                    if "legacy_verified" in link_statuses.get(str(asset.id), set())
                    else "needs_review"
                ),
                "match_confidence": 1.0 if score(asset) >= 1_000 else 0.65,
            }
            for asset in rows
        ]
        statuses = {item["evidence_status"] for item in items}
        aggregate_status = (
            "approved"
            if statuses and statuses == {"approved"}
            else "legacy_verified"
            if statuses and statuses <= {"approved", "legacy_verified"}
            else "needs_review"
        )
        return items, aggregate_status if items else None

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
