"""add artifact media links

Revision ID: 20260812_0002
Revises: 20260811_0001
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260812_0002"
down_revision = "20260811_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "artifact_media_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column(
            "association_confidence",
            sa.String(length=30),
            nullable=False,
            server_default="unassigned",
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("artifact_id", "media_asset_id", name="uq_artifact_media_link"),
    )
    op.create_index("ix_artifact_media_links_artifact_id", "artifact_media_links", ["artifact_id"])
    op.create_index(
        "ix_artifact_media_links_media_asset_id", "artifact_media_links", ["media_asset_id"]
    )
    op.execute(
        """
        INSERT INTO artifact_media_links (
            id, artifact_id, media_asset_id, source_reference,
            association_confidence, metadata_json, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), artifact_id, id,
            metadata_json->>'source_relative_path',
            COALESCE(metadata_json->>'association_confidence', 'unassigned'),
            metadata_json, created_at, updated_at
        FROM media_assets
        WHERE artifact_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_media_links_media_asset_id", table_name="artifact_media_links")
    op.drop_index("ix_artifact_media_links_artifact_id", table_name="artifact_media_links")
    op.drop_table("artifact_media_links")
