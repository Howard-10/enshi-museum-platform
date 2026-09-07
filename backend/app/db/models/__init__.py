"""Import all models so Alembic can discover a complete metadata registry."""

from app.db.models.core import (  # noqa: F401
    AdminAuditLog,
    Artifact,
    ArtifactCatalogRecord,
    Conversation,
    ConversationMessage,
    Document,
    DocumentChunk,
    MediaAsset,
    User,
    WebSearchAudit,
)
