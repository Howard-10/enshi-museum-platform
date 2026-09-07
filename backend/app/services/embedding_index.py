"""Staged, resumable embedding work with a profile-specific production store.

No function in this module constructs a provider client unless both the global
and indexing switches are explicitly enabled.  The pilot writes JSON staging
records first; production ``vector(N)`` tables are created only after the
returned dimension has been confirmed.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from openai import APIError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.core import (
    Document,
    DocumentChunk,
    EmbeddingPilotItem,
    EmbeddingPilotRun,
    EmbeddingProfile,
)
from app.services.model_clients import create_embedding_client
from app.services.model_readiness import (
    get_model_readiness,
    require_external_model_calls,
)

BATCH_SIZE = 20
MAX_RETRIES = 2
_PROFILE_TABLE = re.compile(r"^embedding_vectors_[a-z0-9_]+$")


@dataclass(frozen=True)
class IndexPlan:
    eligible_chunks: int
    stale_chunks: int
    already_current_chunks: int
    model: str | None
    dimensions: int | None


@dataclass(frozen=True)
class EmbeddingSource:
    """The exact text supplied to an embedding provider for one child chunk."""

    chunk: DocumentChunk
    document_title: str

    def text_for_template(self, template: str) -> str:
        if template == "content_only_v1":
            return self.chunk.content.strip()
        if template == "title_and_content_v2":
            return f"文档标题：{self.document_title.strip()}\n正文：{self.chunk.content.strip()}"
        raise ValueError(f"Unsupported EMBEDDING_TEXT_TEMPLATE: {template}")


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def profile_id_for(config: Settings) -> str:
    """Use a deliberate env value if supplied; otherwise a safe provisional ID."""

    return getattr(config, "embedding_profile_id", None) or "school_embed_v1"


def production_table_for(profile_id: str) -> str:
    suffix = re.sub(r"[^a-z0-9]+", "_", profile_id.lower()).strip("_")
    return f"embedding_vectors_{suffix.removeprefix('school_embed_') or 'v1'}"


def validate_embedding(vector: Iterable[float], expected_dimension: int) -> list[float]:
    values = list(vector)
    if len(values) != expected_dimension:
        raise ValueError("Embedding response dimensions did not match EMBEDDING_DIMENSIONS")
    if not values or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Embedding response contains non-finite values")
    if not any(float(value) != 0.0 for value in values):
        raise ValueError("Embedding response is an all-zero vector")
    return [float(value) for value in values]


async def load_child_chunks(
    session: AsyncSession, *, limit: int | None = None, catalog_only: bool = False
) -> list[EmbeddingSource]:
    statement = (
        select(DocumentChunk, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.chunk_level == "child")
        .order_by(DocumentChunk.document_id, DocumentChunk.sequence)
    )
    if catalog_only:
        statement = statement.where(Document.artifact_id.is_not(None))
    if limit is not None:
        statement = statement.limit(limit)
    return [EmbeddingSource(chunk=chunk, document_title=title) for chunk, title in (await session.execute(statement)).all()]


def source_text(source: EmbeddingSource, config: Settings) -> str:
    """Keep stored hashes and provider requests tied to the same text template."""

    return source.text_for_template(config.embedding_text_template)


async def get_or_create_profile(session: AsyncSession, *, config: Settings) -> EmbeddingProfile:
    if not config.embedding_model or not config.embedding_dimensions:
        raise ValueError("EMBEDDING_MODEL and EMBEDDING_DIMENSIONS are required for a profile")
    profile_id = profile_id_for(config)
    profile = await session.get(EmbeddingProfile, profile_id)
    if profile is None:
        profile = EmbeddingProfile(
            id=profile_id,
            provider="openai_compatible",
            model=config.embedding_model,
            dimension=config.embedding_dimensions,
            adapter_version=f"openai_compatible_{config.embedding_text_template}",
            status="staging",
        )
        session.add(profile)
        await session.flush()
    elif (profile.model, profile.dimension, profile.adapter_version) != (
        config.embedding_model,
        config.embedding_dimensions,
        f"openai_compatible_{config.embedding_text_template}",
    ):
        raise ValueError(
            "Embedding profile is immutable; create a new EMBEDDING_PROFILE_ID for a changed model, dimension, or text template"
        )
    return profile


async def build_index_plan(
    session: AsyncSession,
    *,
    config: Settings,
    limit: int | None = None,
    catalog_only: bool = False,
) -> IndexPlan:
    chunks = await load_child_chunks(session, limit=limit, catalog_only=catalog_only)
    profile = await session.get(EmbeddingProfile, config.embedding_profile_id or "")
    current_hashes: dict[uuid.UUID, str] = {}
    if profile and profile.production_table and _PROFILE_TABLE.fullmatch(profile.production_table):
        rows = await session.execute(
            text(
                f"SELECT chunk_id, text_sha256 FROM {profile.production_table} "
                "WHERE embedding_profile_id = :profile AND index_status = 'success'"
            ),
            {"profile": profile.id},
        )
        current_hashes = {row.chunk_id: row.text_sha256 for row in rows.mappings()}
    already_current = sum(
        1
        for source in chunks
        if current_hashes.get(source.chunk.id) == text_sha256(source_text(source, config))
    )
    return IndexPlan(
        eligible_chunks=len(chunks),
        stale_chunks=len(chunks) - already_current,
        already_current_chunks=already_current,
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
    )


async def create_pilot_run(
    session: AsyncSession, *, config: Settings, limit: int = BATCH_SIZE
) -> EmbeddingPilotRun:
    profile = await get_or_create_profile(session, config=config)
    chunks = await load_child_chunks(session, limit=limit)
    run = EmbeddingPilotRun(
        embedding_profile_id=profile.id,
        requested_count=len(chunks),
        estimated_full_request_count=await _child_chunk_count(session),
        status="pending",
    )
    session.add(run)
    await session.flush()
    for source in chunks:
        session.add(
            EmbeddingPilotItem(
                run_id=run.id,
                chunk_id=source.chunk.id,
                text_sha256=text_sha256(source_text(source, config)),
                embedding_profile_id=profile.id,
                status="pending",
            )
        )
    await session.commit()
    return run


async def run_pilot(
    session: AsyncSession, *, run_id: uuid.UUID, config: Settings
) -> dict[str, int | str]:
    """Run an explicit pilot; successful same hash/profile items remain skipped."""

    require_external_model_calls(config)
    if not config.embedding_indexing_enabled:
        raise RuntimeError(
            "Embedding indexing is disabled. Set EMBEDDING_INDEXING_ENABLED=true after approval."
        )
    readiness = get_model_readiness(config)
    if not readiness.embedding_indexing_ready:
        raise ValueError(
            f"Embedding configuration is incomplete: {', '.join(readiness.missing_embedding_fields)}"
        )
    run = await session.get(EmbeddingPilotRun, run_id)
    if run is None:
        raise ValueError("Unknown embedding pilot run")
    profile = await session.get(EmbeddingProfile, run.embedding_profile_id)
    if profile is None:
        raise ValueError("Pilot profile no longer exists")
    items = list(
        (
            await session.scalars(
                select(EmbeddingPilotItem)
                .where(EmbeddingPilotItem.run_id == run.id)
                .order_by(EmbeddingPilotItem.created_at)
            )
        ).all()
    )
    sources = {source.chunk.id: source for source in await load_child_chunks(session)}
    client = create_embedding_client(config)
    indexed = failed = skipped = 0
    for item in items:
        if (
            item.status == "success"
            and item.text_sha256
            and item.embedding_profile_id == profile.id
        ):
            item.status = "skipped"
            skipped += 1
            continue
        source = sources.get(item.chunk_id)
        if source is None:
            item.status, item.error_type = "failed", "ChunkNotFound"
            failed += 1
            continue
        item.status, item.request_attempts = "running", item.request_attempts + 1
        started = time.perf_counter()
        try:
            vector = validate_embedding(
                (await client.aembed_documents([source_text(source, config)]))[0], profile.dimension
            )
            item.vector_json = vector
            item.returned_dimensions = len(vector)
            item.latency_ms = round((time.perf_counter() - started) * 1000)
            item.status, item.error_type = "success", None
            indexed += 1
        except (APIError, httpx.HTTPError, OSError, RuntimeError, ValueError, IndexError) as error:
            item.latency_ms = round((time.perf_counter() - started) * 1000)
            item.status, item.error_type = "failed", type(error).__name__
            failed += 1
    run.status = "success" if failed == 0 and indexed + skipped == len(items) else "failed"
    await session.commit()
    return {"run_id": str(run.id), "indexed": indexed, "failed": failed, "skipped": skipped}


async def provision_production_table(session: AsyncSession, *, profile_id: str) -> str:
    """Create an empty fixed-dimension table after a successful pilot; no API call occurs."""

    profile = await session.get(EmbeddingProfile, profile_id)
    if profile is None or profile.status not in {"pilot_passed", "active"}:
        raise ValueError("Only a pilot-passed embedding profile may get a production table")
    table = profile.production_table or production_table_for(profile.id)
    if not _PROFILE_TABLE.fullmatch(table):
        raise ValueError("Unsafe production vector table name")
    await session.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "chunk_id uuid NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE, "
            "embedding_profile_id varchar(100) NOT NULL REFERENCES embedding_profiles(id), "
            "text_sha256 varchar(64) NOT NULL, embedding vector("
            + str(profile.dimension)
            + ") NULL, "
            "index_status varchar(30) NOT NULL DEFAULT 'pending', indexed_at timestamptz NULL, "
            "error_type varchar(255) NULL, attempts integer NOT NULL DEFAULT 0, "
            "PRIMARY KEY (chunk_id, embedding_profile_id)"
            ")"
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_success ON {table} (chunk_id) "
            "WHERE index_status = 'success'"
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_embedding_hnsw ON {table} "
            "USING hnsw (embedding vector_cosine_ops) "
            "WHERE index_status = 'success'"
        )
    )
    profile.production_table = table
    profile.status = "active"
    await session.commit()
    return table


async def index_child_chunks(
    session: AsyncSession,
    *,
    config: Settings,
    limit: int | None = None,
    catalog_only: bool = False,
    batch_size: int = BATCH_SIZE,
    max_batches: int | None = None,
) -> dict[str, int]:
    """Index changed chunks into the active profile table in resumable batches of at most 20."""

    require_external_model_calls(config)
    if not config.embedding_indexing_enabled:
        raise RuntimeError("Embedding indexing is disabled")
    profile = await get_or_create_profile(session, config=config)
    if profile.status != "active" or not profile.production_table:
        raise ValueError("Run and approve a pilot before full production indexing")
    if batch_size != BATCH_SIZE:
        raise ValueError("Production batch size is fixed at 20 for auditable recovery")
    if max_batches is not None and max_batches < 1:
        raise ValueError("max_batches must be at least 1 when provided")
    table = profile.production_table
    if not _PROFILE_TABLE.fullmatch(table):
        raise ValueError("Unsafe production vector table name")
    chunks = await load_child_chunks(session, limit=limit, catalog_only=catalog_only)
    client = create_embedding_client(config)
    indexed = failed = skipped = request_batches = 0
    stopped_on_provider_error = False
    for start in range(0, len(chunks), BATCH_SIZE):
        candidates: list[tuple[EmbeddingSource, str, int]] = []
        for source in chunks[start : start + BATCH_SIZE]:
            chunk = source.chunk
            digest = text_sha256(source_text(source, config))
            prior = await session.execute(
                text(
                    f"SELECT text_sha256, index_status, attempts FROM {table} WHERE chunk_id = :chunk AND embedding_profile_id = :profile"
                ),
                {"chunk": chunk.id, "profile": profile.id},
            )
            row = prior.mappings().first()
            if row and row["text_sha256"] == digest and row["index_status"] == "success":
                skipped += 1
                continue
            attempts = int(row["attempts"]) if row else 0
            if attempts >= MAX_RETRIES and row and row["index_status"] == "failed":
                failed += 1
                continue
            candidates.append((source, digest, attempts + 1))

        if not candidates:
            await session.commit()
            continue
        if max_batches is not None and request_batches >= max_batches:
            break

        pending: list[tuple[EmbeddingSource, str]] = []
        for source, digest, next_attempt in candidates:
            chunk = source.chunk
            await session.execute(
                text(
                    f"INSERT INTO {table} (chunk_id, embedding_profile_id, text_sha256, index_status, attempts) "
                    "VALUES (:chunk, :profile, :digest, 'running', :attempts) "
                    "ON CONFLICT (chunk_id, embedding_profile_id) DO UPDATE SET text_sha256 = EXCLUDED.text_sha256, index_status = 'running', attempts = EXCLUDED.attempts"
                ),
                {
                    "chunk": chunk.id,
                    "profile": profile.id,
                    "digest": digest,
                    "attempts": next_attempt,
                },
            )
            pending.append((source, digest))

        request_batches += 1
        try:
            response_vectors = await client.aembed_documents(
                [source_text(source, config) for source, _ in pending]
            )
            if len(response_vectors) != len(pending):
                raise ValueError("Embedding response count does not match request count")

            for (source, _), raw_vector in zip(pending, response_vectors, strict=True):
                chunk = source.chunk
                vector = validate_embedding(raw_vector, profile.dimension)
                vector_text = "[" + ",".join(str(value) for value in vector) + "]"
                await session.execute(
                    text(
                        f"UPDATE {table} SET embedding = CAST(:embedding AS vector), index_status = 'success', indexed_at = :indexed, error_type = NULL WHERE chunk_id = :chunk AND embedding_profile_id = :profile"
                    ),
                    {
                        "embedding": vector_text,
                        "indexed": datetime.now(UTC),
                        "chunk": chunk.id,
                        "profile": profile.id,
                    },
                )
                indexed += 1
        except (APIError, httpx.HTTPError, OSError, RuntimeError, ValueError, IndexError) as error:
            for source, _ in pending:
                chunk = source.chunk
                await session.execute(
                    text(
                        f"UPDATE {table} SET index_status = 'failed', error_type = :error WHERE chunk_id = :chunk AND embedding_profile_id = :profile"
                    ),
                    {"error": type(error).__name__, "chunk": chunk.id, "profile": profile.id},
                )
                failed += 1
            # A provider or network failure commonly affects the whole batch
            # (for example, exhausted quota). Persist this batch and stop so
            # the worker does not send hundreds of known-failing requests.
            stopped_on_provider_error = True
        await session.commit()
        if stopped_on_provider_error:
            break
    return {
        "indexed": indexed,
        "failed": failed,
        "skipped": skipped,
        "request_batches": request_batches,
        "stopped_on_provider_error": int(stopped_on_provider_error),
    }


async def _child_chunk_count(session: AsyncSession) -> int:
    return len(await load_child_chunks(session))
