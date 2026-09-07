"""Redis-cached and PostgreSQL-backed conversation memory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import from_url
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.core import Conversation, ConversationMessage
from app.services.answer_generation import clean_user_facing_text

RECENT_MESSAGE_LIMIT = 20
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


def cache_key(session_id: str) -> str:
    return f"conversation:recent:{session_id}"


def serialize_message(message: ConversationMessage) -> dict[str, Any]:
    created_at = message.created_at or datetime.now(UTC)
    return {
        "id": str(message.id),
        "sequence": message.sequence,
        "role": message.role,
        "content": clean_user_facing_text(message.content) or "",
        "citations": message.citations_json,
        "media": message.media_json,
        "created_at": created_at.isoformat(),
    }


class ConversationMemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def remember_exchange(
        self,
        *,
        session_id: str,
        user_content: str,
        assistant_content: str,
        citations: list[dict[str, Any]],
        media: list[dict[str, Any]],
    ) -> None:
        conversation = await self._get_or_create_conversation(session_id)
        current_sequence = await self.session.scalar(
            select(func.max(ConversationMessage.sequence)).where(
                ConversationMessage.conversation_id == conversation.id
            )
        )
        next_sequence = (current_sequence or 0) + 1
        user_message = ConversationMessage(
            conversation=conversation,
            sequence=next_sequence,
            role="user",
            content=user_content,
        )
        assistant_message = ConversationMessage(
            conversation=conversation,
            sequence=next_sequence + 1,
            role="assistant",
            content=assistant_content,
            citations_json=citations,
            media_json=media,
        )
        self.session.add_all((user_message, assistant_message))
        await self.session.commit()
        await self.session.refresh(user_message)
        await self.session.refresh(assistant_message)
        await self._cache_recent(session_id, await self._load_database_recent(session_id))

    async def recent_messages(self, session_id: str) -> tuple[str, list[dict[str, Any]]]:
        cached = await self._load_cached_recent(session_id)
        if cached is not None:
            return "redis", cached
        messages = await self._load_database_recent(session_id)
        await self._cache_recent(session_id, messages)
        return "postgresql", messages

    async def _get_or_create_conversation(self, session_id: str) -> Conversation:
        conversation = await self.session.scalar(
            select(Conversation).where(Conversation.session_key == session_id)
        )
        if conversation is None:
            conversation = Conversation(session_key=session_id)
            self.session.add(conversation)
            await self.session.flush()
        return conversation

    async def _load_database_recent(self, session_id: str) -> list[dict[str, Any]]:
        conversation = await self.session.scalar(
            select(Conversation).where(Conversation.session_key == session_id)
        )
        if conversation is None:
            return []
        messages = (
            await self.session.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.sequence.desc())
                .limit(RECENT_MESSAGE_LIMIT)
            )
        ).all()
        return [serialize_message(message) for message in reversed(messages)]

    async def _load_cached_recent(self, session_id: str) -> list[dict[str, Any]] | None:
        client = from_url(settings.redis_url, decode_responses=True)
        try:
            values = await client.lrange(cache_key(session_id), 0, -1)
            if not values:
                return None
            messages = [json.loads(value) for value in values]
            for message in messages:
                if message.get("role") == "assistant":
                    message["content"] = clean_user_facing_text(message.get("content")) or ""
            return messages
        except (RedisError, OSError, ValueError, json.JSONDecodeError):
            return None
        finally:
            await client.aclose()

    async def _cache_recent(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        client = from_url(settings.redis_url, decode_responses=True)
        try:
            key = cache_key(session_id)
            await client.delete(key)
            if messages:
                await client.rpush(
                    key, *(json.dumps(message, ensure_ascii=False) for message in messages)
                )
                await client.expire(key, CACHE_TTL_SECONDS)
        except (RedisError, OSError):
            pass
        finally:
            await client.aclose()
