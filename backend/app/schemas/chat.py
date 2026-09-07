from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_type: Literal["internal", "external"] = "internal"
    id: str
    chunk_id: str | None = None
    title: str
    document_id: str | None = None
    url: str | None = None
    excerpt: str | None = None


class MediaItem(BaseModel):
    id: str
    type: str
    url: str


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4_000)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    intent: str
    answer_scope: Literal[
        "internal_only",
        "internal_plus_general",
        "external_search",
        "insufficient_evidence",
    ]
    unverified_extension: str | None = None
    evidence_status: Literal["sufficient", "insufficient", "conflicting"] = "insufficient"
    reason_codes: list[str] = []
    notice: str | None = None
    citations: list[Citation] = []
    media: list[MediaItem] = []
