"""Structure-aware parsing and parent/child splitting for Word sources."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W = lambda name: f"{W_NS}{name}"


@dataclass(frozen=True)
class ChunkingConfig:
    parent_size: int = 1_500
    parent_overlap: int = 0
    child_size: int = 420
    child_overlap: int = 60


@dataclass(frozen=True)
class DocumentBlock:
    sequence: int
    content: str
    block_type: str = "paragraph"
    heading_level: int | None = None
    heading_path: tuple[str, ...] = ()
    source_start: int | None = None
    source_end: int | None = None


@dataclass(frozen=True)
class ChildChunk:
    sequence: int
    content: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParentChunk:
    sequence: int
    content: str
    children: list[ChildChunk]
    metadata: dict[str, object] = field(default_factory=dict)


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _local_name(element: ET.Element, name: str) -> str:
    return element.attrib.get(W(name), "")


def _paragraph_text(paragraph: ET.Element) -> str:
    pieces: list[str] = []
    for child in paragraph.iter():
        if child.tag == W("t"):
            pieces.append(child.text or "")
        elif child.tag == W("tab"):
            pieces.append("\t")
        elif child.tag in {W("br"), W("cr")}:
            pieces.append("\n")
    return normalize_text("".join(pieces))


def _style_names(zf: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except (KeyError, ET.ParseError):
        return {}
    names: dict[str, str] = {}
    for style in root.findall(f"{W_NS}style"):
        style_id = _local_name(style, "styleId")
        name_node = style.find(f"{W_NS}name")
        if style_id and name_node is not None:
            names[style_id] = _local_name(name_node, "val")
    return names


def _heading_level(paragraph: ET.Element, style_names: dict[str, str], text: str) -> int | None:
    ppr = paragraph.find(f"{W_NS}pPr")
    style_id = ""
    if ppr is not None:
        style = ppr.find(f"{W_NS}pStyle")
        if style is not None:
            style_id = _local_name(style, "val")
        outline = ppr.find(f"{W_NS}outlineLvl")
        if outline is not None:
            try:
                return int(_local_name(outline, "val")) + 1
            except ValueError:
                pass
    style_name = style_names.get(style_id, style_id).lower()
    match = re.search(r"(?:heading|标题)\s*([1-9])", style_name)
    if match:
        return int(match.group(1))
    patterns = (
        r"^第\s*[一二三四五六七八九十百千万0-9]+\s*[章节篇部卷]",
        r"^[一二三四五六七八九十百千万]+[、.．]\s*",
        r"^\d+(?:\.\d+){0,3}[、.．)]\s*",
    )
    if any(re.match(pattern, text) for pattern in patterns):
        if text.startswith("第"):
            return 1
        numeric = re.match(r"^(\d+(?:\.\d+)*)", text)
        if numeric:
            return min(4, numeric.group(1).count(".") + 1)
        return 2
    return None


def _is_list(paragraph: ET.Element) -> bool:
    ppr = paragraph.find(f"{W_NS}pPr")
    return ppr is not None and ppr.find(f"{W_NS}numPr") is not None


def _table_text(table: ET.Element) -> str:
    rows: list[str] = []
    for row in table.findall(f"{W_NS}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{W_NS}tc"):
            text = " ".join(
                value for value in (_paragraph_text(p) for p in cell.findall(f"{W_NS}p")) if value
            )
            if text:
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def parse_docx_blocks(source_path: Path) -> list[DocumentBlock]:
    """Parse paragraphs and tables while preserving their original order."""

    with zipfile.ZipFile(source_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        style_names = _style_names(archive)
    body = root.find(f"{W_NS}body")
    if body is None:
        return []
    blocks: list[DocumentBlock] = []
    offset = 0
    for element in body:
        if element.tag == W("p"):
            content = _paragraph_text(element)
            if not content:
                continue
            level = _heading_level(element, style_names, content)
            block_type = "heading" if level is not None else ("list" if _is_list(element) else "paragraph")
        elif element.tag == W("tbl"):
            content = _table_text(element)
            if not content:
                continue
            level = None
            block_type = "table"
        else:
            continue
        start = offset
        offset += len(content) + 1
        blocks.append(
            DocumentBlock(
                sequence=len(blocks),
                content=content,
                block_type=block_type,
                heading_level=level,
                source_start=start,
                source_end=offset,
            )
        )
    return blocks


def blocks_to_text(blocks: list[DocumentBlock]) -> str:
    return normalize_text("\n\n".join(block.content for block in blocks))


def _preferred_boundary(text: str, start: int, limit: int) -> int:
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
        while next_start < len(clean) and clean[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


class ParentChildChunker:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def split(self, text: str) -> list[ParentChunk]:
        """Legacy plain-text fallback used by non-DOCX callers."""

        parents = _split(text, self.config.parent_size, self.config.parent_overlap)
        return self._build_parents(
            [(content, {"block_type": "paragraph", "heading_path": []}) for content in parents]
        )

    def split_blocks(self, blocks: list[DocumentBlock]) -> list[ParentChunk]:
        """Split by heading sections first, then natural text boundaries."""

        if not blocks:
            return []
        sections: list[tuple[str, dict[str, object]]] = []
        path: list[str] = []
        current_lines: list[str] = []
        current_meta: dict[str, object] = {"block_type": "paragraph", "heading_path": []}

        def flush() -> None:
            if current_lines:
                sections.append(("\n\n".join(current_lines), dict(current_meta)))
                current_lines.clear()

        for block in blocks:
            if block.heading_level is not None:
                flush()
                level = max(1, block.heading_level)
                path[:] = path[: level - 1]
                path.append(block.content)
                current_meta = {
                    "block_type": "section",
                    "heading_level": level,
                    "heading_text": block.content,
                    "heading_path": list(path),
                    "source_start": block.source_start,
                    "source_end": block.source_end,
                }
                current_lines.append(block.content)
                continue
            if not current_lines:
                current_meta = {
                    "block_type": block.block_type,
                    "heading_path": list(path),
                    "source_start": block.source_start,
                    "source_end": block.source_end,
                }
            else:
                current_meta["source_end"] = block.source_end
            current_lines.append(block.content)
        flush()

        parent_inputs: list[tuple[str, dict[str, object]]] = []
        for text, metadata in sections:
            for section_part in _split(text, self.config.parent_size, 0):
                parent_inputs.append((section_part, metadata))
        return self._build_parents(parent_inputs)

    def _build_parents(self, parents: list[tuple[str, dict[str, object]]]) -> list[ParentChunk]:
        child_sequence = 0
        output: list[ParentChunk] = []
        for parent_sequence, (parent_content, metadata) in enumerate(parents):
            children: list[ChildChunk] = []
            for child_content in _split(parent_content, self.config.child_size, self.config.child_overlap):
                children.append(
                    ChildChunk(sequence=child_sequence, content=child_content, metadata=dict(metadata))
                )
                child_sequence += 1
            output.append(
                ParentChunk(
                    sequence=parent_sequence,
                    content=parent_content,
                    children=children,
                    metadata=dict(metadata),
                )
            )
        return output
