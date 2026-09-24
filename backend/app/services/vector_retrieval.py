"""Profile-isolated vector retrieval used only after Phase 3 is explicitly enabled."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.db.models.core import Document, DocumentChunk, EmbeddingProfile
from app.services.embedding_index import production_table_for, validate_embedding
from app.services.keyword_retrieval import excerpt_for, extract_search_terms
from app.services.model_clients import embed_retrieval_query

VECTOR_TOP_K = 20


async def vector_search(
    session: AsyncSession, query: str, *, config: Settings = settings, limit: int = VECTOR_TOP_K
) -> list[dict[str, Any]]:
    """Return child candidates from one active profile; never joins semantic spaces."""

    profile_id = config.embedding_profile_id or "school_embed_v1"
    profile = await session.get(EmbeddingProfile, profile_id)
    if profile is None or profile.status != "active" or not profile.production_table:
        raise RuntimeError("No active embedding profile is available")
    if profile.production_table != production_table_for(profile.id):
        raise RuntimeError("Embedding profile production table does not match the profile identity")
    query_vector = validate_embedding(await embed_retrieval_query(query, config), profile.dimension)
    vector_literal = "[" + ",".join(str(value) for value in query_vector) + "]"
    rows = (
        (
            await session.execute(
                text(
                    f"SELECT chunk_id, embedding <=> CAST(:query AS vector) AS distance "
                    f"FROM {profile.production_table} WHERE embedding_profile_id = :profile "
                    "AND index_status = 'success' ORDER BY embedding <=> CAST(:query AS vector) LIMIT :limit"
                ),
                {"query": vector_literal, "profile": profile.id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    chunk_ids = [row["chunk_id"] for row in rows]
    if not chunk_ids:
        return []
    items = (
        await session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(chunk_ids))
        )
    ).all()
    by_chunk_id = {str(chunk.id): (chunk, document) for chunk, document in items}
    terms = extract_search_terms(query)
    matches: list[dict[str, Any]] = []
    for row in rows:
        chunk, document = by_chunk_id[str(row["chunk_id"])]
        matches.append(
            {
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
                "title": document.title,
                "excerpt": excerpt_for(chunk.content, terms),
                "section_path": (chunk.metadata_json or {}).get("heading_path", []),
                "block_type": (chunk.metadata_json or {}).get("block_type", "paragraph"),
                "source_filename": (chunk.metadata_json or {}).get("source_filename"),
                "score": 1.0 - float(row["distance"]),
                "vector_distance": float(row["distance"]),
            }
        )
    return matches
