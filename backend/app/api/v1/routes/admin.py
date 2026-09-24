"""Local management-console APIs.

This is intentionally a small local-admin MVP. It protects every route with a
single token from ``ADMIN_API_TOKEN`` and records every write. Production use
should replace this dependency with the museum's approved SSO or user system.
"""

from __future__ import annotations

import hashlib
import secrets
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.core import (
    AdminAuditLog,
    Artifact,
    ArtifactCatalogRecord,
    ArtifactMediaLink,
    Document,
    DocumentEvidenceReview,
    MediaAsset,
)
from app.db.session import get_db_session
from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.schemas.admin import (
    AdminArtifactRead,
    AdminArtifactUpdate,
    AdminAuditRead,
    AdminDocumentRead,
    AdminDocumentReviewUpdate,
    AdminMediaLinkCreate,
    AdminMediaLinkRead,
    AdminMediaRead,
    AdminSummary,
)
from app.services.document_chunker import ParentChildChunker, blocks_to_text, parse_docx_blocks
from app.services.media_ingestion import MEDIA_DETAILS, build_object_key
from app.services.minio_storage import MinioStorage

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
bearer = HTTPBearer(auto_error=False)
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_MEDIA_BYTES = 200 * 1024 * 1024


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if not settings.admin_api_token:
        raise HTTPException(status_code=503, detail="管理端尚未配置 ADMIN_API_TOKEN")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="请输入管理端令牌")
    if not secrets.compare_digest(credentials.credentials, settings.admin_api_token):
        raise HTTPException(status_code=403, detail="管理端令牌无效")
    return "local_admin"


AdminActor = Annotated[str, Depends(require_admin)]


async def count_rows(session: AsyncSession, model: type, *conditions: object) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int((await session.scalar(statement)) or 0)


def snapshot_artifact(artifact: Artifact, record: ArtifactCatalogRecord | None) -> dict:
    return {
        "id": str(artifact.id),
        "name": artifact.name,
        "aliases": artifact.aliases or [],
        "era": artifact.era,
        "category": artifact.category,
        "description": artifact.description,
        "location": record.location if record else None,
        "material": record.material if record else None,
    }


def snapshot_document(document: Document, review: DocumentEvidenceReview | None) -> dict:
    return {
        "id": str(document.id),
        "title": document.title,
        "source_filename": document.source_filename,
        "import_status": document.import_status,
        "review_status": review.review_status if review else "needs_review",
        "review_note": review.review_note if review else None,
    }


def snapshot_media(asset: MediaAsset) -> dict:
    return {
        "id": str(asset.id),
        "original_filename": asset.original_filename,
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "byte_size": asset.byte_size,
        "sha256": asset.sha256,
        "object_key": asset.object_key,
    }


def add_audit(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: str | None,
    before: dict | None,
    after: dict | None,
) -> None:
    session.add(
        AdminAuditLog(
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_json=before or {},
            after_json=after or {},
        )
    )


def artifact_read(artifact: Artifact) -> AdminArtifactRead:
    record = next(iter(artifact.catalog_records), None)
    return AdminArtifactRead(
        id=artifact.id,
        name=artifact.name,
        aliases=artifact.aliases or [],
        era=artifact.era,
        category=artifact.category,
        description=artifact.description,
        location=record.location if record else None,
        material=record.material if record else None,
        document_count=len(artifact.document_links) + len(artifact.documents),
        media_count=len(artifact.media_links),
    )


def media_read(asset: MediaAsset) -> AdminMediaRead:
    return AdminMediaRead(
        id=asset.id,
        original_filename=asset.original_filename,
        media_type=asset.media_type,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        links=[
            AdminMediaLinkRead(
                artifact_id=link.artifact_id,
                artifact_name=link.artifact.name,
                review_status=link.review_status,
                association_confidence=link.association_confidence,
            )
            for link in asset.artifact_links
        ],
    )


@router.get("/summary", response_model=AdminSummary)
async def get_admin_summary(session: DbSession, _: AdminActor) -> AdminSummary:
    return AdminSummary(
        artifacts=await count_rows(session, Artifact),
        documents=await count_rows(session, Document),
        media_assets=await count_rows(session, MediaAsset),
        approved_documents=await count_rows(
            session, DocumentEvidenceReview, DocumentEvidenceReview.review_status == "approved"
        ),
        documents_needing_review=await count_rows(
            session,
            DocumentEvidenceReview,
            DocumentEvidenceReview.review_status == "needs_review",
        ),
        media_links_needing_review=await count_rows(
            session,
            ArtifactMediaLink,
            ArtifactMediaLink.review_status == "needs_review",
        ),
    )


@router.get("/artifacts", response_model=list[AdminArtifactRead])
async def list_admin_artifacts(
    session: DbSession,
    _: AdminActor,
    query: str | None = Query(default=None, max_length=100),
) -> list[AdminArtifactRead]:
    statement = (
        select(Artifact)
        .options(
            selectinload(Artifact.catalog_records),
            selectinload(Artifact.documents),
            selectinload(Artifact.document_links),
            selectinload(Artifact.media_links),
        )
        .order_by(Artifact.name)
    )
    if query:
        statement = statement.where(Artifact.name.ilike(f"%{query.strip()}%"))
    return [artifact_read(item) for item in (await session.scalars(statement)).all()]


@router.patch("/artifacts/{artifact_id}", response_model=AdminArtifactRead)
async def update_admin_artifact(
    artifact_id: UUID,
    payload: AdminArtifactUpdate,
    session: DbSession,
    actor: AdminActor,
) -> AdminArtifactRead:
    artifact = await session.scalar(
        select(Artifact)
        .options(
            selectinload(Artifact.catalog_records),
            selectinload(Artifact.documents),
            selectinload(Artifact.document_links),
            selectinload(Artifact.media_links),
        )
        .where(Artifact.id == artifact_id)
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="文物不存在")
    if "name" in payload.model_fields_set and payload.name != artifact.name:
        duplicate = await session.scalar(select(Artifact).where(Artifact.name == payload.name))
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="文物名称已存在")
    record = next(iter(artifact.catalog_records), None)
    before = snapshot_artifact(artifact, record)
    for field in ("name", "era", "category", "description"):
        if field in payload.model_fields_set:
            setattr(artifact, field, getattr(payload, field))
    if record is not None:
        for field in ("era", "location", "material"):
            if field in payload.model_fields_set and field != "era":
                setattr(record, field, getattr(payload, field))
        if "era" in payload.model_fields_set:
            record.era = payload.era
    await session.flush()
    after = snapshot_artifact(artifact, record)
    add_audit(
        session,
        actor=actor,
        action="update",
        object_type="artifact",
        object_id=str(artifact.id),
        before=before,
        after=after,
    )
    await session.commit()
    return artifact_read(artifact)


@router.get("/documents", response_model=list[AdminDocumentRead])
async def list_admin_documents(
    session: DbSession,
    _: AdminActor,
    query: str | None = Query(default=None, max_length=100),
) -> list[AdminDocumentRead]:
    statement = (
        select(Document)
        .options(selectinload(Document.artifact), selectinload(Document.evidence_review), selectinload(Document.chunks))
        .order_by(Document.created_at.desc())
    )
    if query:
        text = f"%{query.strip()}%"
        statement = statement.where(or_(Document.title.ilike(text), Document.source_filename.ilike(text)))
    documents = (await session.scalars(statement)).all()
    return [
        AdminDocumentRead(
            id=document.id,
            title=document.title,
            source_filename=document.source_filename,
            mime_type=document.mime_type,
            import_status=document.import_status,
            review_status=document.evidence_review.review_status if document.evidence_review else "needs_review",
            review_note=document.evidence_review.review_note if document.evidence_review else None,
            artifact_id=document.artifact_id,
            artifact_name=document.artifact.name if document.artifact else None,
            chunk_count=len(document.chunks),
        )
        for document in documents
    ]


@router.patch("/documents/{document_id}/review", response_model=AdminDocumentRead)
async def review_admin_document(
    document_id: UUID,
    payload: AdminDocumentReviewUpdate,
    session: DbSession,
    actor: AdminActor,
) -> AdminDocumentRead:
    document = await session.scalar(
        select(Document)
        .options(selectinload(Document.artifact), selectinload(Document.evidence_review), selectinload(Document.chunks))
        .where(Document.id == document_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    review = document.evidence_review
    before = snapshot_document(document, review)
    if review is None:
        review = DocumentEvidenceReview(document_id=document.id)
        session.add(review)
    review.review_status = payload.review_status
    review.review_note = payload.review_note
    await session.flush()
    after = snapshot_document(document, review)
    add_audit(session, actor=actor, action="review", object_type="document", object_id=str(document.id), before=before, after=after)
    await session.commit()
    return AdminDocumentRead(
        id=document.id,
        title=document.title,
        source_filename=document.source_filename,
        mime_type=document.mime_type,
        import_status=document.import_status,
        review_status=review.review_status,
        review_note=review.review_note,
        artifact_id=document.artifact_id,
        artifact_name=document.artifact.name if document.artifact else None,
        chunk_count=len(document.chunks),
    )


@router.post("/documents/upload", response_model=AdminDocumentRead, status_code=201)
async def upload_admin_document(
    session: DbSession,
    actor: AdminActor,
    file: UploadFile = File(...),
    artifact_id: UUID | None = Form(default=None),
) -> AdminDocumentRead:
    filename = file.filename or "upload.docx"
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="当前只支持上传 .docx 文档")
    data = await file.read()
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 25 MB")
    artifact_name: str | None = None
    if artifact_id is not None:
        artifact = await session.scalar(select(Artifact).where(Artifact.id == artifact_id))
        if artifact is None:
            raise HTTPException(status_code=404, detail="关联文物不存在")
        artifact_name = artifact.name
    with tempfile.TemporaryDirectory(prefix="enshi-admin-doc-") as temp_dir:
        source_path = Path(temp_dir) / Path(filename).name
        source_path.write_bytes(data)
        blocks = parse_docx_blocks(source_path)
        text = blocks_to_text(blocks)
        if not text:
            raise HTTPException(status_code=400, detail="文档没有可读取的正文")
        try:
            document = await DocumentRepository(session).import_word_text(
                source_path=source_path,
                text=text,
                artifact_name=artifact_name,
                chunker=ParentChildChunker(),
                blocks=blocks,
            )
        except DuplicateDocumentError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
    review = DocumentEvidenceReview(document_id=document.id, review_status="needs_review")
    session.add(review)
    add_audit(
        session,
        actor=actor,
        action="upload",
        object_type="document",
        object_id=str(document.id),
        before=None,
        after=snapshot_document(document, review),
    )
    await session.commit()
    await session.refresh(document, attribute_names=["artifact", "chunks", "evidence_review"])
    return AdminDocumentRead(
        id=document.id,
        title=document.title,
        source_filename=document.source_filename,
        mime_type=document.mime_type,
        import_status=document.import_status,
        review_status=review.review_status,
        review_note=review.review_note,
        artifact_id=document.artifact_id,
        artifact_name=artifact_name,
        chunk_count=len(document.chunks),
    )


@router.get("/media", response_model=list[AdminMediaRead])
async def list_admin_media(
    session: DbSession,
    _: AdminActor,
    query: str | None = Query(default=None, max_length=100),
    media_type: str | None = Query(default=None, pattern="^(audio|image|video)$"),
) -> list[AdminMediaRead]:
    statement = (
        select(MediaAsset)
        .options(selectinload(MediaAsset.artifact_links).selectinload(ArtifactMediaLink.artifact))
        .order_by(MediaAsset.created_at.desc())
    )
    if query:
        statement = statement.where(MediaAsset.original_filename.ilike(f"%{query.strip()}%"))
    if media_type:
        statement = statement.where(MediaAsset.media_type == media_type)
    return [media_read(item) for item in (await session.scalars(statement)).all()]


@router.post("/media/upload", response_model=AdminMediaRead, status_code=201)
async def upload_admin_media(
    session: DbSession,
    actor: AdminActor,
    file: UploadFile = File(...),
    artifact_id: UUID | None = Form(default=None),
) -> AdminMediaRead:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    details = MEDIA_DETAILS.get(suffix)
    if details is None:
        raise HTTPException(status_code=400, detail="不支持的媒体格式")
    data = await file.read()
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="媒体文件不能超过 200 MB")
    if artifact_id is not None and await session.scalar(select(Artifact.id).where(Artifact.id == artifact_id)) is None:
        raise HTTPException(status_code=404, detail="关联文物不存在")
    media_type, mime_type = details
    sha256 = hashlib.sha256(data).hexdigest()
    object_key = build_object_key(media_type=media_type, sha256=sha256, suffix=suffix)
    existing = await session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
    if existing is None:
        storage = MinioStorage()
        storage.ensure_bucket()
        storage.upload_bytes_if_missing(data=data, object_key=object_key, mime_type=mime_type)
        existing = MediaAsset(
            object_key=object_key,
            original_filename=Path(filename).name,
            media_type=media_type,
            mime_type=mime_type,
            byte_size=len(data),
            sha256=sha256,
            metadata_json={"source": "admin_upload"},
        )
        session.add(existing)
        await session.flush()
    if artifact_id is not None:
        link = await session.scalar(
            select(ArtifactMediaLink).where(
                ArtifactMediaLink.artifact_id == artifact_id,
                ArtifactMediaLink.media_asset_id == existing.id,
            )
        )
        if link is None:
            session.add(
                ArtifactMediaLink(
                    artifact_id=artifact_id,
                    media_asset_id=existing.id,
                    source_reference="admin_upload",
                    association_confidence="manual",
                    review_status="needs_review",
                    metadata_json={"source": "admin_upload"},
                )
            )
    add_audit(
        session,
        actor=actor,
        action="upload",
        object_type="media",
        object_id=str(existing.id),
        before=None,
        after=snapshot_media(existing),
    )
    await session.commit()
    asset = await session.scalar(
        select(MediaAsset)
        .options(selectinload(MediaAsset.artifact_links).selectinload(ArtifactMediaLink.artifact))
        .where(MediaAsset.id == existing.id)
    )
    assert asset is not None
    return media_read(asset)


@router.post("/media/{media_id}/links", response_model=AdminMediaRead)
async def link_admin_media(
    media_id: UUID,
    payload: AdminMediaLinkCreate,
    session: DbSession,
    actor: AdminActor,
) -> AdminMediaRead:
    asset = await session.scalar(select(MediaAsset).where(MediaAsset.id == media_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="媒体不存在")
    if await session.scalar(select(Artifact.id).where(Artifact.id == payload.artifact_id)) is None:
        raise HTTPException(status_code=404, detail="关联文物不存在")
    link = await session.scalar(
        select(ArtifactMediaLink).where(
            ArtifactMediaLink.media_asset_id == media_id,
            ArtifactMediaLink.artifact_id == payload.artifact_id,
        )
    )
    before = {
        "review_status": link.review_status,
        "association_confidence": link.association_confidence,
        "source_reference": link.source_reference,
    } if link else None
    if link is None:
        link = ArtifactMediaLink(media_asset_id=media_id, artifact_id=payload.artifact_id)
        session.add(link)
    link.review_status = payload.review_status
    link.association_confidence = payload.association_confidence
    link.source_reference = payload.source_reference
    await session.flush()
    after = {
        "review_status": link.review_status,
        "association_confidence": link.association_confidence,
        "source_reference": link.source_reference,
    }
    add_audit(session, actor=actor, action="link", object_type="media", object_id=str(media_id), before=before, after=after)
    await session.commit()
    asset = await session.scalar(
        select(MediaAsset)
        .options(selectinload(MediaAsset.artifact_links).selectinload(ArtifactMediaLink.artifact))
        .where(MediaAsset.id == media_id)
    )
    assert asset is not None
    return media_read(asset)


@router.delete("/media/{media_id}/links/{artifact_id}", status_code=204)
async def unlink_admin_media(
    media_id: UUID,
    artifact_id: UUID,
    session: DbSession,
    actor: AdminActor,
) -> None:
    link = await session.scalar(
        select(ArtifactMediaLink).where(
            ArtifactMediaLink.media_asset_id == media_id,
            ArtifactMediaLink.artifact_id == artifact_id,
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="媒体关联不存在")
    before = {
        "artifact_id": str(link.artifact_id),
        "media_asset_id": str(link.media_asset_id),
        "review_status": link.review_status,
    }
    await session.delete(link)
    add_audit(session, actor=actor, action="unlink", object_type="media_link", object_id=str(link.id), before=before, after=None)
    await session.commit()


@router.get("/audit", response_model=list[AdminAuditRead])
async def list_admin_audit(
    session: DbSession,
    _: AdminActor,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AdminAuditRead]:
    logs = (
        await session.scalars(
            select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
        )
    ).all()
    return [
        AdminAuditRead(
            id=item.id,
            actor=item.actor,
            action=item.action,
            object_type=item.object_type,
            object_id=item.object_id,
            before=item.before_json,
            after=item.after_json,
            created_at=item.created_at,
        )
        for item in logs
    ]
