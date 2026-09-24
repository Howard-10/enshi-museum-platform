"""Offline-safe retrieval orchestration with future vector/RRF extension points."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from openai import APIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import Artifact, Document, DocumentChunk
from app.services.keyword_retrieval import KeywordRetrievalService, extract_search_terms, score_text
from app.services.model_readiness import get_model_readiness
from app.services.vector_retrieval import vector_search

RRF_K = 60
_REQUEST_WORDS = ("请问", "请", "帮我", "介绍一下", "介绍", "讲讲", "说说", "是什么", "有哪些")
_MEDIA_WORDS = ("图片", "照片", "音频", "语音", "视频", "播放", "看看", "听听")


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    *,
    k: int = RRF_K,
) -> dict[str, float]:
    """Fuse ranked IDs using RRF; source names are kept for future tracing."""

    scores: dict[str, float] = {}
    for ranked_ids in rankings.values():
        for rank, item_id in enumerate(ranked_ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def deterministic_rerank(
    query: str, matches: list[dict[str, Any]], fusion_scores: Mapping[str, float]
) -> list[dict[str, Any]]:
    """A local lexical fallback until a configured reranker becomes available."""

    terms = extract_search_terms(query)
    return sorted(
        matches,
        key=lambda item: (
            -(
                fusion_scores.get(item["chunk_id"], 0.0) * 10_000
                + score_text(item["excerpt"], terms)
                + score_text(" ".join(item.get("section_path", [])), terms) * 3
            ),
            item["title"],
        ),
    )


def _compact_query(value: str) -> str:
    compact = "".join(character for character in value if character.isalnum() or "\u4e00" <= character <= "\u9fff")
    for word in [*_REQUEST_WORDS, *_MEDIA_WORDS, "的", "吗", "呢", "什么", "一下"]:
        compact = compact.replace(word, "")
    return compact


def keyword_guard_reason(keyword_result: Mapping[str, Any], query: str) -> str | None:
    """Keep high-confidence local keyword evidence ahead of partial vector coverage.

    The current v2 profile is a catalog-only pilot. Exact artifact and exact
    source-title requests must therefore remain keyword-first until all Word
    sources have been indexed and the full evaluation passes.
    """

    compact_query = _compact_query(query)
    if len(compact_query) < 2:
        return None
    for artifact in keyword_result["artifacts"]:
        name = _compact_query(str(artifact["name"]))
        # Two-character artifact names (for example 玉玦、银狮) are exact only
        # when the cleaned request itself equals the name. Longer names may
        # safely appear inside a natural-language or media request.
        is_short_exact_name = len(name) == 2 and compact_query == name
        is_long_name_in_request = len(name) >= 3 and name in compact_query
        if is_short_exact_name or is_long_name_in_request:
            return "exact_catalog_artifact"
    for document in keyword_result["document_matches"]:
        title = _compact_query(str(document["title"]))
        if len(title) >= 4 and (title in compact_query or compact_query in title):
            return "exact_document_title"
    return None


class RagPipeline:
    """One retrieval entry point for keyword-only and later hybrid RAG modes.

    No provider client is constructed in keyword mode, so calling this pipeline
    cannot call a real model API while external calls are disabled.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        *,
        include_media: bool,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        keyword_result = await KeywordRetrievalService(self.session).search(
            query,
            include_media=include_media,
            media_type=media_type,
        )
        keyword_documents = keyword_result["document_matches"][:20]
        # Keyword service already returns one best child per source document.
        # Keep its existing source-level semantics; parent restoration is
        # applied only to vector child candidates when hybrid mode is enabled.
        rankings: dict[str, Sequence[str]] = {
            "keyword": [item["chunk_id"] for item in keyword_documents],
        }
        vector_documents: list[dict[str, Any]] = []
        readiness = get_model_readiness()
        vector_error: str | None = None
        guard_reason = keyword_guard_reason(keyword_result, query)
        vector_attempted = False
        if readiness.vector_search_enabled and guard_reason is None:
            vector_attempted = True
            try:
                vector_documents = await vector_search(self.session, query, limit=20)
                rankings["vector"] = [item["chunk_id"] for item in vector_documents]
            except (APIError, RuntimeError, ValueError, OSError) as error:
                # A vector outage is a retrieval degradation, not a visitor-facing failure.
                vector_error = type(error).__name__
        fusion_scores = reciprocal_rank_fusion(rankings)
        candidates = {item["chunk_id"]: item for item in [*keyword_documents, *vector_documents]}
        ranked_children = deterministic_rerank(query, list(candidates.values()), fusion_scores)[:12]
        documents = (
            await self._aggregate_parent_evidence(ranked_children, query)
            if vector_documents
            else ranked_children[:6]
        )
        keyword_result["document_matches"] = documents
        keyword_result["citations"] = [
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
            for item in documents
        ]
        if vector_attempted and not vector_error:
            keyword_result["mode"] = "hybrid_rag"
        elif vector_error:
            keyword_result["mode"] = "keyword_rag"
        elif guard_reason:
            keyword_result["mode"] = "keyword_guarded"
        else:
            keyword_result["mode"] = f"{readiness.retrieval_mode}_rag"
        keyword_result["retrieval_trace"] = {
            "sources": list(rankings),
            "rrf_k": RRF_K,
            "reranker": "deterministic_lexical"
            if not readiness.reranker_enabled
            else "pending_external",
            "external_model_calls_enabled": readiness.external_calls_enabled,
            "vector_error": vector_error,
            "vector_guard": guard_reason,
            "vector_attempted": vector_attempted,
            "degradation": "keyword_fallback" if vector_error else None,
        }
        keyword_result["artifacts"] = await self._artifacts_for_evidence(
            documents,
            keyword_result["artifacts"],
        )
        return keyword_result

    async def _artifacts_for_evidence(
        self,
        documents: list[dict[str, Any]],
        keyword_artifacts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Make artifact reporting follow final evidence, not only keyword matching."""

        document_ids = [UUID(item["document_id"]) for item in documents]
        if not document_ids:
            return keyword_artifacts
        rows = (
            await self.session.execute(
                select(Document.id, Artifact)
                .join(Artifact, Artifact.id == Document.artifact_id)
                .where(Document.id.in_(document_ids))
            )
        ).all()
        by_document = {
            str(document_id): {
                "id": str(artifact.id),
                "name": artifact.name,
                "era": artifact.era,
                "location": None,
                "material": None,
                "score": 0,
            }
            for document_id, artifact in rows
        }
        merged_by_id: dict[str, dict[str, Any]] = {}
        for item in documents:
            artifact = by_document.get(item["document_id"])
            if artifact:
                merged_by_id[artifact["id"]] = artifact
        for artifact in keyword_artifacts:
            current = merged_by_id.get(artifact["id"])
            # Catalog matching carries a meaningful score; vector document
            # ownership is only a fallback signal and currently has score 0.
            if current is None or artifact.get("score", 0) > current.get("score", 0):
                merged_by_id[artifact["id"]] = artifact
        return sorted(merged_by_id.values(), key=lambda item: (-item.get("score", 0), item["name"]))

    async def _aggregate_parent_evidence(
        self, ranked_children: list[dict[str, Any]], query: str
    ) -> list[dict[str, Any]]:
        """Deduplicate retrieved children and restore 3–5 readable parent chunks."""

        if not ranked_children:
            return []
        child_ids = [UUID(item["chunk_id"]) for item in ranked_children]
        rows = (
            await self.session.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.id.in_(child_ids))
            )
        ).all()
        source = {str(chunk.id): (chunk, document) for chunk, document in rows}
        selected: list[dict[str, Any]] = []
        seen_parents: set[str] = set()
        seen_sections: set[tuple[str, str]] = set()
        for match in ranked_children:
            chunk, document = source.get(match["chunk_id"], (None, None))
            if chunk is None or document is None:
                continue
            parent_key = str(chunk.parent_chunk_id or chunk.id)
            section_path = tuple(str(item) for item in (chunk.metadata_json or {}).get("heading_path", []))
            section_key = (str(document.id), " > ".join(section_path))
            if parent_key in seen_parents or (section_path and section_key in seen_sections):
                continue
            seen_parents.add(parent_key)
            if section_path:
                seen_sections.add(section_key)
            selected.append({**match, "parent_chunk_id": parent_key})
            if len(selected) == 5:
                break
        return selected
