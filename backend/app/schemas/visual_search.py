from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat import Citation, MediaItem


class VisualIdentification(BaseModel):
    """The constrained result returned by the configured vision model."""

    artifact_name: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    visual_note: str = ""


class RecognizedArtifact(BaseModel):
    id: UUID
    name: str
    era: str | None = None
    location: str | None = None
    material: str | None = None


class VisualMatch(BaseModel):
    artifact: str
    source: str
    score: float = Field(ge=0, le=1)
    backend: str


class VisualSearchResponse(BaseModel):
    recognized_artifact: RecognizedArtifact | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    visual_note: str = ""
    answer: str
    notice: str | None = None
    citations: list[Citation] = []
    media: list[MediaItem] = []
    visual_matches: list[VisualMatch] = []
