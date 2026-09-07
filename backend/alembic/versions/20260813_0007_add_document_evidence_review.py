"""Require a review state for every imported Word document.

Revision ID: 20260813_0007
Revises: 20260813_0006
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260813_0007"
down_revision = "20260813_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_evidence_reviews",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_document_evidence_reviews_review_status",
        "document_evidence_reviews",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_evidence_reviews_review_status", table_name="document_evidence_reviews"
    )
    op.drop_table("document_evidence_reviews")
