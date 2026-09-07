"""Add guarded vector-index metadata and web-search audit records.

Revision ID: 20260812_0005
Revises: 20260812_0004
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260812_0005"
down_revision = "20260812_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_chunks", sa.Column("embedding_model", sa.String(length=255), nullable=True)
    )
    op.add_column("document_chunks", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedding_text_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("document_chunks", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.create_index(
        "ix_document_chunks_embedding_fingerprint",
        "document_chunks",
        ["embedding_model", "embedding_dimensions", "embedding_text_sha256"],
    )

    op.create_table(
        "web_search_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("result_domains", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_web_search_audits_created_at", "web_search_audits", ["created_at"])
    op.create_index(
        "ix_web_search_audits_provider_status", "web_search_audits", ["provider", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_web_search_audits_provider_status", table_name="web_search_audits")
    op.drop_index("ix_web_search_audits_created_at", table_name="web_search_audits")
    op.drop_table("web_search_audits")
    op.drop_index("ix_document_chunks_embedding_fingerprint", table_name="document_chunks")
    op.drop_column("document_chunks", "embedding_error")
    op.drop_column("document_chunks", "embedding_indexed_at")
    op.drop_column("document_chunks", "embedding_text_sha256")
    op.drop_column("document_chunks", "embedding_dimensions")
    op.drop_column("document_chunks", "embedding_model")
