"""Keep pre-existing media mappings visible but distinguish them from reviewed evidence.

Revision ID: 20260813_0008
Revises: 20260813_0007
"""

from alembic import op

revision = "20260813_0008"
down_revision = "20260813_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE artifact_media_links SET review_status = 'legacy_verified' "
        "WHERE review_status = 'needs_review'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE artifact_media_links SET review_status = 'needs_review' "
        "WHERE review_status = 'legacy_verified'"
    )
