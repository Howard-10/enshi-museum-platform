"""add traceable artifact catalog records

Revision ID: 20260812_0003
Revises: 20260812_0002
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260812_0003"
down_revision = "20260812_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_catalog_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_uri", sa.String(length=1000), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("record_kind", sa.String(length=30), nullable=False, server_default="artifact"),
        sa.Column("era", sa.String(length=100), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("material", sa.String(length=100), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "source_sha256", "sheet_name", "row_number", name="uq_catalog_source_sheet_row"
        ),
    )
    op.create_index(
        "ix_artifact_catalog_records_artifact_id", "artifact_catalog_records", ["artifact_id"]
    )
    op.create_index(
        "ix_catalog_records_source", "artifact_catalog_records", ["source_sha256", "sheet_name"]
    )
    op.create_index(
        "ix_catalog_records_fingerprint", "artifact_catalog_records", ["content_fingerprint"]
    )
    op.create_index(
        "ix_artifact_catalog_records_record_kind", "artifact_catalog_records", ["record_kind"]
    )
    op.create_index("ix_artifact_catalog_records_era", "artifact_catalog_records", ["era"])
    op.create_index(
        "ix_artifact_catalog_records_location", "artifact_catalog_records", ["location"]
    )
    op.create_index(
        "ix_artifact_catalog_records_material", "artifact_catalog_records", ["material"]
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_catalog_records_material", table_name="artifact_catalog_records")
    op.drop_index("ix_artifact_catalog_records_location", table_name="artifact_catalog_records")
    op.drop_index("ix_artifact_catalog_records_era", table_name="artifact_catalog_records")
    op.drop_index("ix_artifact_catalog_records_record_kind", table_name="artifact_catalog_records")
    op.drop_index("ix_catalog_records_fingerprint", table_name="artifact_catalog_records")
    op.drop_index("ix_catalog_records_source", table_name="artifact_catalog_records")
    op.drop_index("ix_artifact_catalog_records_artifact_id", table_name="artifact_catalog_records")
    op.drop_table("artifact_catalog_records")
