"""API responses for persisted conversation memory."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationMessageRead(BaseModel):
    id: UUID
    sequence: int
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    media: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    session_id: str
    source: str
    messages: list[ConversationMessageRead]
