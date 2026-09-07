"""Track explicit artifact guide visits for popularity recommendations.

Revision ID: 20260824_0009
Revises: 20260813_0008
"""

import sqlalchemy as sa

from alembic import op

revision = "20260824_0009"
down_revision = "20260813_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "view_count")
