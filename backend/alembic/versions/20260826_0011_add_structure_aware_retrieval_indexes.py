"""add indexes used by heading-aware retrieval

Revision ID: 20260826_0011
Revises: 20260825_0010
"""

from alembic import op

revision = "20260826_0011"
down_revision = "20260825_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Metadata keeps the parser version and heading path without forcing a
    # destructive migration of the existing chunk rows.  This index makes
    # heading-path filters usable once the v2 importer is backfilled.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_metadata_gin "
        "ON document_chunks USING gin (metadata_json jsonb_path_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_media_assets_filename_trgm "
        "ON media_assets USING gin (original_filename gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_media_assets_object_key_trgm "
        "ON media_assets USING gin (object_key gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_media_assets_object_key_trgm")
    op.execute("DROP INDEX IF EXISTS ix_media_assets_filename_trgm")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_metadata_gin")
