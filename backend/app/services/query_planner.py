"""Deterministic visitor-query planning used before retrieval.

The planner deliberately does not invent facts or identifiers. It only
extracts the requested task shape so catalog, document, and media retrieval
can run independently and the answer composer can preserve mixed requests.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

MEDIA_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "image": ("图片", "照片", "配图", "原图", "图像", "展示图片"),
    "audio": ("音频", "语音", "录音", "听听", "听一下", "播放讲解", "声音"),
    "video": ("视频", "录像", "短片", "视频介绍", "看视频"),
}
MEDIA_GENERIC_WORDS = ("媒体", "多媒体", "相关资料", "素材")
DESCRIPTION_WORDS = (
    "介绍",
    "是什么",
    "历史",
    "背景",
    "用途",
    "意义",
    "故事",
    "详情",
    "讲讲",
    "说说",
    "资料",
)
SUBJECT_PREFIXES = ("关于", "介绍", "讲讲", "说说", "查询", "查看", "了解")
_QUOTED_SUBJECT = re.compile(r"[“‘\"《【]([^”’\"》】]{2,80})[”’\"》】]")
_PUNCTUATION = re.compile(r"[，。！？?；;：:、\s]+")


@dataclass(frozen=True)
class MediaRequest:
    required: bool = False
    types: tuple[str, ...] = ()
    min_results: int = 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    retrieval_query: str
    intent: str
    tasks: tuple[str, ...] = ()
    subject_hint: str | None = None
    active_artifact_id: str | None = None
    active_artifact_name: str | None = None
    media_request: MediaRequest = field(default_factory=MediaRequest)
    needs_clarification: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tasks"] = list(self.tasks)
        data["media_request"] = self.media_request.as_dict()
        data["media_request"]["types"] = list(self.media_request.types)
        return data


def media_types_for_query(query: str) -> tuple[str, ...]:
    """Return all requested media types in stable visitor-facing order."""

    found: list[str] = []
    for media_type in ("image", "audio", "video"):
        if any(alias in query for alias in MEDIA_TYPE_ALIASES[media_type]):
            found.append(media_type)
    if not found and any(word in query for word in MEDIA_GENERIC_WORDS):
        return ("image", "audio", "video")
    return tuple(found)


def has_media_request(query: str) -> bool:
    return bool(media_types_for_query(query)) or any(
        word in query for word in MEDIA_GENERIC_WORDS
    )


def _active_artifact_from_history(
    history: list[dict[str, Any]] | None,
) -> tuple[str | None, str | None]:
    for message in reversed(history or []):
        metadata = message.get("metadata") or {}
        artifact_id = metadata.get("active_artifact_id")
        artifact_name = metadata.get("active_artifact_name")
        if artifact_id and artifact_name:
            return str(artifact_id), str(artifact_name)
    return None, None


def _clean_subject(value: str) -> str:
    value = _PUNCTUATION.sub(" ", value)
    for word in (
        *DESCRIPTION_WORDS,
        *MEDIA_GENERIC_WORDS,
        "请",
        "帮我",
        "给我",
        "我想",
        "播放",
        "看看",
        "看一下",
        "听一下",
    ):
        value = value.replace(word, " ")
    for aliases in MEDIA_TYPE_ALIASES.values():
        for alias in aliases:
            value = value.replace(alias, " ")
    value = value.strip(" \t\"'“”‘’《》()（）[]【】")
    if value.endswith("的"):
        value = value[:-1].strip()
    if value in {"相关", "这个", "它", "这件", "文物", "相关资料"}:
        return ""
    return value


def subject_hint_for_query(query: str) -> str | None:
    quoted = _QUOTED_SUBJECT.search(query)
    if quoted:
        subject = _clean_subject(quoted.group(1))
        return subject if len(subject) >= 2 else None
    for prefix in SUBJECT_PREFIXES:
        if prefix in query:
            tail = query.split(prefix, 1)[1]
            tail = re.split(r"[，,。；;]|再给我|并给我|然后给我", tail, maxsplit=1)[0]
            subject = _clean_subject(tail)
            if 2 <= len(subject) <= 80:
                return subject
    # For a named object followed by a request suffix, retain the subject
    # before the first media/delivery phrase.
    base = re.sub(r"^(?:请播放|请|帮我|给我|我想|播放|看看|看一下|听一下)", "", query)
    markers = (*MEDIA_GENERIC_WORDS, "图片", "照片", "视频", "音频", "语音", "播放", "听听")
    positions = [(base.find(marker), marker) for marker in markers if base.find(marker) >= 0]
    subject = base[: min(positions)[0]] if positions else base
    subject = _clean_subject(subject)
    if subject in {"", "它的", "这件的", "这个的", "相关"}:
        return None
    return subject if 2 <= len(subject) <= 80 else None


def plan_query(
    query: str,
    history: list[dict[str, Any]] | None = None,
) -> QueryPlan:
    original = (query or "").strip()
    media_types = media_types_for_query(original)
    media_required = has_media_request(original)
    subject = subject_hint_for_query(original)
    active_id, active_name = _active_artifact_from_history(history)
    if active_name and media_required and (
        not subject or active_name in subject or any(marker in subject for marker in ("它", "这件", "刚才"))
    ):
        subject = active_name
    tasks: list[str] = []
    if any(word in original for word in DESCRIPTION_WORDS) or not media_required:
        tasks.append("artifact_description")
    if media_required:
        tasks.append("media_request")
    if not tasks:
        tasks.append("artifact_description")
    if len(tasks) > 1:
        intent = "mixed"
    elif tasks[0] == "media_request":
        intent = "media"
    else:
        intent = "knowledge"
    needs_clarification = media_required and not subject and not active_name
    return QueryPlan(
        original_query=original,
        retrieval_query=subject if media_required and subject else original,
        intent=intent,
        tasks=tuple(tasks),
        subject_hint=subject,
        active_artifact_id=active_id if subject else None,
        active_artifact_name=active_name if subject else None,
        media_request=MediaRequest(
            required=media_required,
            types=media_types,
            min_results=1,
        ),
        needs_clarification=needs_clarification,
    )
