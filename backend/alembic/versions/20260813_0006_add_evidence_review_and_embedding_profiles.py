"""Add auditable evidence review and staged embedding index records.

Revision ID: 20260813_0006
Revises: 20260812_0005
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260813_0006"
down_revision = "20260812_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=False),
        sa.Column(
            "review_status", sa.String(length=30), nullable=False, server_default="needs_review"
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("artifact_id", "alias", name="uq_artifact_alias"),
    )
    op.create_index("ix_artifact_aliases_alias", "artifact_aliases", ["alias"])
    op.create_index("ix_artifact_aliases_artifact_id", "artifact_aliases", ["artifact_id"])
    op.create_index("ix_artifact_aliases_review_status", "artifact_aliases", ["review_status"])
    op.create_table(
        "artifact_document_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "review_status", sa.String(length=30), nullable=False, server_default="needs_review"
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("artifact_id", "document_id", name="uq_artifact_document_link"),
    )
    op.create_index(
        "ix_artifact_document_links_artifact_id", "artifact_document_links", ["artifact_id"]
    )
    op.create_index(
        "ix_artifact_document_links_document_id", "artifact_document_links", ["document_id"]
    )
    op.create_index(
        "ix_artifact_document_links_review_status", "artifact_document_links", ["review_status"]
    )
    op.create_table(
        "embedding_profiles",
        sa.Column("id", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("adapter_version", sa.String(length=100), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="staging"),
        sa.Column("production_table", sa.String(length=100), nullable=True, unique=True),
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
    op.create_index("ix_embedding_profiles_status", "embedding_profiles", ["status"])
    op.create_table(
        "embedding_pilot_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "embedding_profile_id",
            sa.String(length=100),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("estimated_full_request_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_embedding_pilot_runs_embedding_profile_id",
        "embedding_pilot_runs",
        ["embedding_profile_id"],
    )
    op.create_index("ix_embedding_pilot_runs_status", "embedding_pilot_runs", ["status"])
    op.create_table(
        "embedding_pilot_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("embedding_pilot_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "embedding_profile_id",
            sa.String(length=100),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("vector_json", postgresql.JSONB(), nullable=True),
        sa.Column("returned_dimensions", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("request_attempts", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("run_id", "chunk_id", name="uq_pilot_run_chunk"),
    )
    op.create_index("ix_embedding_pilot_items_chunk_id", "embedding_pilot_items", ["chunk_id"])
    op.create_index(
        "ix_embedding_pilot_items_embedding_profile_id",
        "embedding_pilot_items",
        ["embedding_profile_id"],
    )
    op.create_index("ix_embedding_pilot_items_run_id", "embedding_pilot_items", ["run_id"])
    op.create_index("ix_embedding_pilot_items_status", "embedding_pilot_items", ["status"])
    op.add_column(
        "artifact_media_links",
        sa.Column(
            "review_status", sa.String(length=30), nullable=False, server_default="legacy_verified"
        ),
    )
    op.create_index(
        "ix_artifact_media_links_review_status", "artifact_media_links", ["review_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_media_links_review_status", table_name="artifact_media_links")
    op.drop_column("artifact_media_links", "review_status")
    for table, names in (
        (
            "embedding_pilot_items",
            [
                "ix_embedding_pilot_items_status",
                "ix_embedding_pilot_items_run_id",
                "ix_embedding_pilot_items_embedding_profile_id",
                "ix_embedding_pilot_items_chunk_id",
            ],
        ),
        (
            "embedding_pilot_runs",
            ["ix_embedding_pilot_runs_status", "ix_embedding_pilot_runs_embedding_profile_id"],
        ),
        ("embedding_profiles", ["ix_embedding_profiles_status"]),
        (
            "artifact_document_links",
            [
                "ix_artifact_document_links_review_status",
                "ix_artifact_document_links_document_id",
                "ix_artifact_document_links_artifact_id",
            ],
        ),
        (
            "artifact_aliases",
            [
                "ix_artifact_aliases_review_status",
                "ix_artifact_aliases_artifact_id",
                "ix_artifact_aliases_alias",
            ],
        ),
    ):
        for name in names:
            op.drop_index(name, table_name=table)
        op.drop_table(table)
