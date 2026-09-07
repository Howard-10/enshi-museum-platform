"""Pure helpers for describing local media before it is uploaded to MinIO."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

MEDIA_DETAILS: dict[str, tuple[str, str]] = {
    ".m4a": ("audio", "audio/mp4"),
    ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".webp": ("image", "image/webp"),
    ".mp4": ("video", "video/mp4"),
    ".mov": ("video", "video/quicktime"),
    ".avi": ("video", "video/x-msvideo"),
}


@dataclass(frozen=True)
class MediaDescriptor:
    """Stable metadata inferred from a canonical knowledge-base path."""

    media_type: str
    mime_type: str
    source_relative_path: str
    source_category: str
    artifact_name: str | None
    artifact_hint: str | None
    association_confidence: str


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    """Calculate a content hash without loading videos fully into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def build_object_key(*, media_type: str, sha256: str, suffix: str) -> str:
    """Return a deterministic, content-addressed MinIO object key."""

    return f"media/{media_type}/{sha256[:2]}/{sha256}{suffix.lower()}"


def describe_media(path: Path, knowledge_root: Path) -> MediaDescriptor:
    """Infer a cautious artifact association from the source folder structure.

    Files nested below a named artifact folder are marked ``folder`` confidence.
    Flat files in ``图生视频库`` are intentionally not linked to an artifact because
    a filename such as ``牌坊.mp4`` is too ambiguous to bind automatically.
    """

    suffix = path.suffix.lower()
    try:
        media_type, mime_type = MEDIA_DETAILS[suffix]
    except KeyError as error:
        raise ValueError(f"Unsupported media extension: {path.suffix}") from error

    relative = path.relative_to(knowledge_root)
    parts = relative.parts
    if not parts:
        raise ValueError(f"Media file is outside the knowledge root: {path}")

    source_category = parts[0]
    artifact_name: str | None = None
    artifact_hint: str | None = None
    confidence = "unassigned"

    if len(parts) >= 4 and ("音频" in parts[2] or "语音" in parts[2]):
        # Standard source package: 时期/文物/文物音频/文件.mp3.
        artifact_name = parts[1]
        artifact_hint = artifact_name
        confidence = "folder"
    elif source_category == "唐宋文物语音" and len(parts) >= 3:
        folder_name = parts[-2]
        artifact_name = folder_name.removesuffix("语音").strip() or folder_name
        artifact_hint = artifact_name
        confidence = "folder"
    elif source_category == "图生视频库":
        artifact_hint = path.stem
        confidence = "review"
    elif len(parts) >= 3:
        artifact_name = parts[-2]
        artifact_hint = artifact_name
        confidence = "folder"

    return MediaDescriptor(
        media_type=media_type,
        mime_type=mime_type,
        source_relative_path=relative.as_posix(),
        source_category=source_category,
        artifact_name=artifact_name,
        artifact_hint=artifact_hint,
        association_confidence=confidence,
    )
