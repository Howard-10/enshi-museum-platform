from uuid import UUID

from pydantic import BaseModel


class KnowledgeSeedFile(BaseModel):
    relative_path: str
    kind: str
    artifact: str | None = None
    copied: bool


class KnowledgeSeedResponse(BaseModel):
    seed_name: str
    description: str
    total_files: int
    copied_files: int
    files: list[KnowledgeSeedFile]


class ArtifactCatalogItem(BaseModel):
    id: UUID
    name: str
    era: str | None = None
    location: str | None = None
    material: str | None = None
    source_rows: int


class ArtifactCatalogResponse(BaseModel):
    total: int
    items: list[ArtifactCatalogItem]


class PopularArtifactItem(BaseModel):
    id: UUID
    name: str
    era: str | None = None
    location: str | None = None
    material: str | None = None
    source_rows: int
    view_count: int


class PopularArtifactResponse(BaseModel):
    total: int
    has_visit_data: bool
    items: list[PopularArtifactItem]


class ArtifactVisitResponse(BaseModel):
    artifact_id: UUID
    view_count: int


class KeywordDocumentMatch(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    excerpt: str
    # Keyword scores are integers; hybrid/vector scores are normalized floats.
    score: float


class KeywordArtifactMatch(BaseModel):
    id: UUID
    name: str
    era: str | None = None
    location: str | None = None
    material: str | None = None
    score: int


class KeywordSearchResponse(BaseModel):
    mode: str
    query: str
    artifacts: list[KeywordArtifactMatch]
    documents: list[KeywordDocumentMatch]
