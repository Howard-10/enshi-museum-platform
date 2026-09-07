"""Pure parent/child text splitting for Chinese museum source materials.

This module has no database, model provider, or filesystem dependency so it can
be tested independently and replaced later if a domain-specific splitter wins
in evaluation.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    parent_size: int = 1_500
    parent_overlap: int = 160
    child_size: int = 420
    child_overlap: int = 60


@dataclass(frozen=True)
class ChildChunk:
    sequence: int
    content: str


@dataclass(frozen=True)
class ParentChunk:
    sequence: int
    content: str
    children: list[ChildChunk]


def normalize_text(text: str) -> str:
    """Normalize Word extraction noise without changing the factual content."""

    text = text.replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _preferred_boundary(text: str, start: int, limit: int) -> int:
    """Choose the last natural Chinese/paragraph boundary before `limit`."""

    if limit >= len(text):
        return len(text)
    minimum = start + max(1, (limit - start) // 2)
    candidates = [
        text.rfind("\n\n", minimum, limit),
        text.rfind("\n", minimum, limit),
        max(text.rfind(mark, minimum, limit) for mark in "。！？；"),
        text.rfind("，", minimum, limit),
    ]
    boundary = max(candidates)
    return boundary + 1 if boundary >= minimum else limit


def _split(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk overlap must be non-negative and smaller than chunk size")

    clean = normalize_text(text)
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = _preferred_boundary(clean, start, min(start + size, len(clean)))
        content = clean[start:end].strip()
        if content:
            chunks.append(content)
        if end >= len(clean):
            break
        next_start = max(end - overlap, start + 1)
        # Trim leading whitespace but guarantee forward progress.
        while next_start < len(clean) and clean[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


class ParentChildChunker:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def split(self, text: str) -> list[ParentChunk]:
        parents = _split(text, self.config.parent_size, self.config.parent_overlap)
        child_sequence = 0
        output: list[ParentChunk] = []
        for parent_sequence, parent_content in enumerate(parents):
            child_contents = _split(
                parent_content,
                self.config.child_size,
                self.config.child_overlap,
            )
            children = []
            for child_content in child_contents:
                children.append(ChildChunk(sequence=child_sequence, content=child_content))
                child_sequence += 1
            output.append(
                ParentChunk(
                    sequence=parent_sequence,
                    content=parent_content,
                    children=children,
                )
            )
        return output
