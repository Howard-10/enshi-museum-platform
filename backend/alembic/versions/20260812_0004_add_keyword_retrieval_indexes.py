"""add keyword retrieval indexes

Revision ID: 20260812_0004
Revises: 20260812_0003
Create Date: 2026-08-12
"""

from alembic import op

revision = "20260812_0004"
down_revision = "20260812_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_document_chunks_content_trgm "
        "ON document_chunks USING gin (content gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_documents_title_trgm ON documents USING gin (title gin_trgm_ops)")
    op.execute("CREATE INDEX ix_artifacts_name_trgm ON artifacts USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_artifacts_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_trgm")
