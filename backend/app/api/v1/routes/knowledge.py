from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.core import Artifact, ArtifactCatalogRecord
from app.db.session import get_db_session
from app.schemas.knowledge import (
    ArtifactCatalogItem,
    ArtifactCatalogResponse,
    ArtifactVisitResponse,
    KeywordArtifactMatch,
    KeywordDocumentMatch,
    KeywordSearchResponse,
    KnowledgeSeedResponse,
    PopularArtifactItem,
    PopularArtifactResponse,
)
from app.services.rag_pipeline import RagPipeline
from app.services.seed_knowledge_service import get_knowledge_seed

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/seed", response_model=KnowledgeSeedResponse)
async def get_seed_knowledge_base() -> KnowledgeSeedResponse:
    """Preview the copied Word documents before they are ingested into PostgreSQL."""

    return get_knowledge_seed()


@router.get("/catalog", response_model=ArtifactCatalogResponse)
async def get_artifact_catalog(
    session: DbSession,
    query: str | None = Query(default=None, min_length=1, max_length=100),
    era: str | None = Query(default=None, min_length=1, max_length=100),
    location: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=48, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ArtifactCatalogResponse:
    """List standardized artifacts backed by traceable Excel catalog rows."""

    statement = (
        select(ArtifactCatalogRecord)
        .join(Artifact, Artifact.id == ArtifactCatalogRecord.artifact_id)
        .options(joinedload(ArtifactCatalogRecord.artifact))
        .where(ArtifactCatalogRecord.record_kind == "artifact")
        .where(ArtifactCatalogRecord.artifact_id.is_not(None))
        .order_by(Artifact.name, ArtifactCatalogRecord.row_number)
    )
    if query:
        statement = statement.where(Artifact.name.ilike(f"%{query.strip()}%"))
    if era:
        statement = statement.where(ArtifactCatalogRecord.era == era.strip())
    if location:
        statement = statement.where(ArtifactCatalogRecord.location == location.strip())

    rows = (await session.scalars(statement)).all()
    catalog: dict[str, ArtifactCatalogItem] = {}
    for record in rows:
        artifact = record.artifact
        if artifact is None:
            continue
        key = str(artifact.id)
        existing = catalog.get(key)
        if existing is None:
            catalog[key] = ArtifactCatalogItem(
                id=artifact.id,
                name=artifact.name,
                era=record.era or artifact.era,
                location=record.location,
                material=record.material,
                source_rows=1,
            )
        else:
            catalog[key] = existing.model_copy(update={"source_rows": existing.source_rows + 1})

    items = list(catalog.values())
    return ArtifactCatalogResponse(total=len(items), items=items[offset : offset + limit])


@router.get("/popular", response_model=PopularArtifactResponse)
async def get_popular_artifacts(
    session: DbSession,
    limit: int = Query(default=6, ge=1, le=12),
) -> PopularArtifactResponse:
    """Return catalog artifacts ordered by explicit guide visits."""

    statement = (
        select(
            Artifact.id,
            Artifact.name,
            Artifact.era,
            Artifact.view_count,
            func.max(ArtifactCatalogRecord.era).label("catalog_era"),
            func.max(ArtifactCatalogRecord.location).label("location"),
            func.max(ArtifactCatalogRecord.material).label("material"),
            func.count(ArtifactCatalogRecord.id).label("source_rows"),
        )
        .join(ArtifactCatalogRecord, ArtifactCatalogRecord.artifact_id == Artifact.id)
        .where(ArtifactCatalogRecord.record_kind == "artifact")
        .group_by(Artifact.id, Artifact.name, Artifact.era, Artifact.view_count)
        .order_by(Artifact.view_count.desc(), Artifact.name)
        .limit(limit)
    )
    rows = (await session.execute(statement)).mappings().all()
    items = [
        PopularArtifactItem(
            id=row["id"],
            name=row["name"],
            era=row["catalog_era"] or row["era"],
            location=row["location"],
            material=row["material"],
            source_rows=row["source_rows"],
            view_count=row["view_count"],
        )
        for row in rows
    ]
    return PopularArtifactResponse(
        total=len(items),
        has_visit_data=any(item.view_count > 0 for item in items),
        items=items,
    )


@router.post("/artifacts/{artifact_id}/visit", response_model=ArtifactVisitResponse)
async def record_artifact_visit(artifact_id: str, session: DbSession) -> ArtifactVisitResponse:
    """Count an explicit request to open a catalog artifact's guide."""

    exists = await session.scalar(select(Artifact.id).where(Artifact.id == artifact_id))
    if exists is None:
        raise HTTPException(status_code=404, detail="文物不存在。")
    await session.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id)
        .values(view_count=Artifact.view_count + 1)
    )
    await session.commit()
    view_count = await session.scalar(select(Artifact.view_count).where(Artifact.id == artifact_id))
    return ArtifactVisitResponse(artifact_id=exists, view_count=view_count or 0)


@router.get("/search", response_model=KeywordSearchResponse)
async def search_knowledge(
    session: DbSession,
    query: str = Query(min_length=2, max_length=200),
) -> KeywordSearchResponse:
    """Return keyword-search evidence while vector retrieval is not configured."""

    result = await RagPipeline(session).search(query, include_media=False)
    artifacts = [KeywordArtifactMatch(**item) for item in result["artifacts"]]
    documents = [KeywordDocumentMatch(**item) for item in result["document_matches"]]
    return KeywordSearchResponse(
        mode=result["mode"], query=query, artifacts=artifacts, documents=documents
    )
