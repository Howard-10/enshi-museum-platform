"""Read-only startup and model readiness information."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.core import (
    ArtifactCatalogRecord,
    ArtifactDocumentLink,
    Document,
    DocumentChunk,
    MediaAsset,
)
from app.db.session import get_db_session
from app.schemas.system import SystemReadinessResponse
from app.services.model_readiness import get_model_readiness

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/readiness", response_model=SystemReadinessResponse)
async def get_system_readiness(session: DbSession) -> SystemReadinessResponse:
    """Expose data and model readiness without returning any secret values."""

    readiness = get_model_readiness()
    documents = await session.scalar(select(func.count()).select_from(Document))
    child_chunks = await session.scalar(
        select(func.count()).select_from(DocumentChunk).where(DocumentChunk.chunk_level == "child")
    )
    catalog_artifacts = await session.scalar(
        select(func.count(func.distinct(ArtifactCatalogRecord.artifact_id))).where(
            ArtifactCatalogRecord.record_kind == "artifact"
        )
    )
    media_assets = await session.scalar(select(func.count()).select_from(MediaAsset))
    approved_document_links = await session.scalar(
        select(func.count())
        .select_from(ArtifactDocumentLink)
        .where(ArtifactDocumentLink.review_status == "approved")
    )
    return SystemReadinessResponse(
        retrieval_mode=readiness.retrieval_mode,
        external_model_calls_enabled=readiness.external_calls_enabled,
        vector_search_enabled=readiness.vector_search_enabled,
        chat_generation_enabled=readiness.chat_generation_enabled,
        reranker_enabled=readiness.reranker_enabled,
        web_search_enabled=settings.web_search_enabled,
        web_search_provider=settings.web_search_provider,
        web_search_monthly_request_limit=settings.web_search_monthly_request_limit,
        web_search_max_requests_per_answer=settings.web_search_max_requests_per_answer,
        web_search_allowed_domains=[
            domain.strip()
            for domain in settings.web_search_allowed_domains.split(",")
            if domain.strip()
        ],
        missing_embedding_fields=list(readiness.missing_embedding_fields),
        missing_chat_fields=list(readiness.missing_chat_fields),
        missing_reranker_fields=list(readiness.missing_reranker_fields),
        documents=documents or 0,
        child_chunks=child_chunks or 0,
        catalog_artifacts=catalog_artifacts or 0,
        media_assets=media_assets or 0,
        approved_document_links=approved_document_links or 0,
    )
