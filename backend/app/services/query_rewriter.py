"""Small, deterministic conversation-aware query rewriting helpers.

The rewrite happens before retrieval so follow-up questions can use the same
catalog and vector indexes as a standalone question.  The original question
is still kept for the final answer prompt, together with the conversation
context, so the model can preserve the visitor's wording.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_FOLLOW_UP_MARKERS = (
    "它",
    "这件文物",
    "这个文物",
    "该文物",
    "这件",
    "这个",
    "刚才",
    "前面",
    "上一个",
    "上一件",
    "那件",
)

_QUESTION_PREFIXES = (
    "介绍",
    "讲讲",
    "说说",
    "关于",
    "查询",
    "查一下",
    "看看",
    "请介绍",
    "请讲讲",
    "请问",
)


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    standalone_query: str
    used_history: bool = False
    subject: str | None = None


def _clean_subject(value: str) -> str:
    value = re.sub(r"[\s，。！？?！：:；;、]+$", "", value.strip())
    value = re.sub(r"^(?:请问|请|帮我|我想|能否|可以)\s*", "", value)
    value = re.sub(r"(?:的)?(?:介绍|资料|信息|图片|照片|视频|音频|语音|是什么|怎么样|有哪些).*$", "", value)
    value = re.sub(r"的(?:年代|材质|用途|尺寸|来历|历史|背景|故事|图片|照片|视频|音频).*$", "", value)
    return value.strip(" \t\"'“”‘’《》()（）[]【】")


def _subject_from_message(message: str) -> str | None:
    """Extract the likely object from a recent visitor question/answer."""

    text = str(message or "").strip()
    if not text:
        return None
    quoted = re.search(r"[“‘\"《【]([^”’\"》】]{2,40})[”’\"》】]", text)
    if quoted:
        candidate = _clean_subject(quoted.group(1))
        if candidate:
            return candidate
    for prefix in _QUESTION_PREFIXES:
        if text.startswith(prefix):
            candidate = _clean_subject(text[len(prefix) :])
            if 2 <= len(candidate) <= 40:
                return candidate
    match = re.search(r"(?:关于|介绍|讲讲|说说|查询|查看)\s*([^，。！？?]{2,40})", text)
    if match:
        candidate = _clean_subject(match.group(1))
        if candidate:
            return candidate
    return None


def _latest_subject(history: list[dict[str, Any]]) -> str | None:
    for message in reversed(history):
        subject = _subject_from_message(str(message.get("content") or ""))
        if subject:
            return subject
    return None


def _is_follow_up(query: str) -> bool:
    text = query.strip()
    if any(marker in text for marker in _FOLLOW_UP_MARKERS):
        return True
    # Short elliptical questions commonly omit the subject, while a short
    # named-artifact query such as “西兰卡普” must remain untouched.
    return bool(
        re.match(
            r"^(?:还有|是否|有没有|有无|能否|可以|能|什么|哪个|哪种|多少|如何|怎么|为什么|图片|照片|视频|音频|语音)",
            text,
        )
    )


def rewrite_query(query: str, history: list[dict[str, Any]] | None = None) -> QueryRewriteResult:
    """Resolve simple Chinese anaphora using the most recent conversation.

    This intentionally does not call an LLM.  It is deterministic, cheap, and
    keeps retrieval usable when model calls are disabled.  The final model
    prompt still receives the full recent context for more complex follow-ups.
    """

    original = (query or "").strip()
    messages = history or []
    if not original or not messages or not _is_follow_up(original):
        return QueryRewriteResult(original, original)
    subject = _latest_subject(messages)
    if not subject or subject in original:
        return QueryRewriteResult(original, original)
    standalone = original
    for marker in _FOLLOW_UP_MARKERS:
        standalone = standalone.replace(marker, subject, 1)
        if standalone != original:
            break
    if standalone == original:
        standalone = f"{subject}：{original}"
    return QueryRewriteResult(original, standalone, True, subject)


def format_conversation_context(
    history: list[dict[str, Any]] | None,
    *,
    max_messages: int = 10,
    max_chars: int = 12000,
) -> str:
    """Format recent messages for a prompt without treating them as evidence."""

    selected = (history or [])[-max_messages:]
    lines: list[str] = []
    for message in selected:
        role = "访客" if message.get("role") == "user" else "讲解员"
        content = re.sub(r"\s+", " ", str(message.get("content") or "")).strip()
        if not content:
            continue
        lines.append(f"{role}：{content[:1200]}")
    context = "\n".join(lines)
    return context[-max_chars:]
