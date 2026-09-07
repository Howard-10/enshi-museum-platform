"""Core domain models for the new platform.

The models deliberately contain no logic inherited from the former Streamlit
prototype.  PostgreSQL owns metadata and relationships; MinIO owns bytes.
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30), default="visitor", index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Artifact(TimestampMixin, Base):
    """A museum artifact or cultural subject used to relate documents and media."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    era: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    documents: Mapped[list["Document"]] = relationship(back_populates="artifact")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="artifact")
    media_links: Mapped[list["ArtifactMediaLink"]] = relationship(back_populates="artifact")
    catalog_records: Mapped[list["ArtifactCatalogRecord"]] = relationship(back_populates="artifact")
    alias_records: Mapped[list["ArtifactAlias"]] = relationship(back_populates="artifact")
    document_links: Mapped[list["ArtifactDocumentLink"]] = relationship(back_populates="artifact")


class Document(TimestampMixin, Base):
    """An imported source file plus its normalized full text."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("sha256", name="uq_documents_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), index=True)
    source_filename: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String(100),
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    sha256: Mapped[str] = mapped_column(String(64))
    full_text: Mapped[str] = mapped_column(Text)
    import_status: Mapped[str] = mapped_column(String(30), default="ready", index=True)

    artifact: Mapped[Artifact | None] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentChunk.document_id",
    )
    artifact_links: Mapped[list["ArtifactDocumentLink"]] = relationship(back_populates="document")
    evidence_review: Mapped["DocumentEvidenceReview | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )


class DocumentEvidenceReview(TimestampMixin, Base):
    """One required review state per imported Word, even when no artifact matches."""

    __tablename__ = "document_evidence_reviews"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    review_status: Mapped[str] = mapped_column(String(30), default="needs_review", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="evidence_review")


class ArtifactAlias(TimestampMixin, Base):
    """Auditable artifact name variant. Only approved aliases are searchable."""

    __tablename__ = "artifact_aliases"
    __table_args__ = (UniqueConstraint("artifact_id", "alias", name="uq_artifact_alias"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(255), index=True)
    source_reference: Mapped[str] = mapped_column(String(1_000))
    review_status: Mapped[str] = mapped_column(String(30), default="needs_review", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    artifact: Mapped[Artifact] = relationship(back_populates="alias_records")


class ArtifactDocumentLink(TimestampMixin, Base):
    """Human-audited relationship between a source Word document and an artifact."""

    __tablename__ = "artifact_document_links"
    __table_args__ = (
        UniqueConstraint("artifact_id", "document_id", name="uq_artifact_document_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    match_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[str] = mapped_column(String(30), default="needs_review", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    artifact: Mapped[Artifact] = relationship(back_populates="document_links")
    document: Mapped[Document] = relationship(back_populates="artifact_links")


class EmbeddingProfile(TimestampMixin, Base):
    """Immutable semantic-space identity. A changed provider version means a new profile."""

    __tablename__ = "embedding_profiles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(255))
    dimension: Mapped[int] = mapped_column(Integer)
    adapter_version: Mapped[str] = mapped_column(String(100), default="v1")
    status: Mapped[str] = mapped_column(String(30), default="staging", index=True)
    production_table: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)


class EmbeddingPilotRun(TimestampMixin, Base):
    __tablename__ = "embedding_pilot_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    embedding_profile_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_profiles.id"), index=True
    )
    requested_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    estimated_full_request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmbeddingPilotItem(TimestampMixin, Base):
    __tablename__ = "embedding_pilot_items"
    __table_args__ = (UniqueConstraint("run_id", "chunk_id", name="uq_pilot_run_chunk"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("embedding_pilot_runs.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    text_sha256: Mapped[str] = mapped_column(String(64))
    embedding_profile_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_profiles.id"), index=True
    )
    vector_json: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    returned_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_attempts: Mapped[int] = mapped_column(Integer, default=0)


class DocumentChunk(TimestampMixin, Base):
    """Parent/child chunks used by the retrieval pipeline.

    `chunk_level` is either `parent` or `child`. Child chunks are retrieved;
    their parent restores a larger, readable context for answer generation.
    `embedding` intentionally has no fixed dimension until the school confirms
    the selected embedding model.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_level", "sequence", name="uq_chunk_order"),
        Index("ix_chunk_document_level", "document_id", "chunk_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chunk_level: Mapped[str] = mapped_column(String(10), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks", foreign_keys=[document_id])
    parent: Mapped["DocumentChunk | None"] = relationship(
        remote_side="DocumentChunk.id", back_populates="children"
    )
    children: Mapped[list["DocumentChunk"]] = relationship(back_populates="parent")


class MediaAsset(TimestampMixin, Base):
    """Metadata for a file stored in MinIO, never a server filesystem path."""

    __tablename__ = "media_assets"
    __table_args__ = (UniqueConstraint("object_key", name="uq_media_object_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    object_key: Mapped[str] = mapped_column(String(1_000))
    original_filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(20), index=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    artifact: Mapped[Artifact | None] = relationship(back_populates="media_assets")
    artifact_links: Mapped[list["ArtifactMediaLink"]] = relationship(back_populates="media_asset")


class ArtifactMediaLink(TimestampMixin, Base):
    """Associates one deduplicated media object with one or more artifacts."""

    __tablename__ = "artifact_media_links"
    __table_args__ = (
        UniqueConstraint("artifact_id", "media_asset_id", name="uq_artifact_media_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    source_reference: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    association_confidence: Mapped[str] = mapped_column(String(30), default="unassigned")
    review_status: Mapped[str] = mapped_column(String(30), default="legacy_verified", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    artifact: Mapped[Artifact] = relationship(back_populates="media_links")
    media_asset: Mapped[MediaAsset] = relationship(back_populates="artifact_links")


class ArtifactCatalogRecord(TimestampMixin, Base):
    """One traceable row from a structured artifact catalog workbook.

    The source row is preserved even when it is an annotation or a duplicate
    candidate. The optional artifact relationship is the normalized identity
    used by the application.
    """

    __tablename__ = "artifact_catalog_records"
    __table_args__ = (
        UniqueConstraint(
            "source_sha256", "sheet_name", "row_number", name="uq_catalog_source_sheet_row"
        ),
        Index("ix_catalog_records_source", "source_sha256", "sheet_name"),
        Index("ix_catalog_records_fingerprint", "content_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_uri: Mapped[str] = mapped_column(String(1_000))
    sheet_name: Mapped[str] = mapped_column(String(255))
    row_number: Mapped[int] = mapped_column(Integer)
    record_kind: Mapped[str] = mapped_column(String(30), default="artifact", index=True)
    era: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    artifact: Mapped[Artifact | None] = relationship(back_populates="catalog_records")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(TimestampMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence", name="uq_message_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    media_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class WebSearchAudit(TimestampMixin, Base):
    """Operational metadata for approved external search, never including an API key."""

    __tablename__ = "web_search_audits"
    __table_args__ = (
        Index("ix_web_search_audits_created_at", "created_at"),
        Index("ix_web_search_audits_provider_status", "provider", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    query_sha256: Mapped[str] = mapped_column(String(64), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(50), default="tavily")
    status: Mapped[str] = mapped_column(String(30), index=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AdminAuditLog(TimestampMixin, Base):
    """Immutable record of a local management-console change."""

    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_logs_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(100), default="local_admin")
    action: Mapped[str] = mapped_column(String(50), index=True)
    object_type: Mapped[str] = mapped_column(String(50), index=True)
    object_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
