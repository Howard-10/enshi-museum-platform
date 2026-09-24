"""Persistence operations for imported source documents."""

import hashlib
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import Artifact, Document, DocumentChunk
from app.services.document_chunker import DocumentBlock, ParentChildChunker, blocks_to_text


class DuplicateDocumentError(RuntimeError):
    pass


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_artifact(self, name: str | None) -> Artifact | None:
        if not name:
            return None
        artifact = await self.session.scalar(select(Artifact).where(Artifact.name == name))
        if artifact is None:
            artifact = Artifact(name=name)
            self.session.add(artifact)
            await self.session.flush()
        return artifact

    async def remove_existing_by_sha256(self, sha256: str) -> bool:
        """Remove one prior import for an explicit, operator-run reindex."""

        existing = await self.session.scalar(select(Document).where(Document.sha256 == sha256))
        if existing is None:
            return False
        await self.session.delete(existing)
        await self.session.commit()
        return True

    async def rebuild_chunks(
        self,
        document: Document,
        *,
        blocks: list[DocumentBlock],
        chunker: ParentChildChunker,
    ) -> int:
        """Replace only a document's chunks while preserving its identity and reviews."""

        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        document.full_text = blocks_to_text(blocks)
        parent_chunks = chunker.split_blocks(blocks)
        for parent_payload in parent_chunks:
            metadata = {
                "source_filename": document.source_filename,
                "chunking_version": "v2_heading_aware",
                **parent_payload.metadata,
            }
            parent = DocumentChunk(
                document_id=document.id,
                chunk_level="parent",
                sequence=parent_payload.sequence,
                content=parent_payload.content,
                char_count=len(parent_payload.content),
                metadata_json=metadata,
            )
            self.session.add(parent)
            await self.session.flush()
            for child_payload in parent_payload.children:
                self.session.add(
                    DocumentChunk(
                        document_id=document.id,
                        parent_chunk_id=parent.id,
                        chunk_level="child",
                        sequence=child_payload.sequence,
                        content=child_payload.content,
                        char_count=len(child_payload.content),
                        metadata_json={**metadata, **child_payload.metadata},
                    )
                )
        await self.session.flush()
        return sum(len(parent.children) for parent in parent_chunks)

    async def import_word_text(
        self,
        *,
        source_path: Path,
        text: str,
        artifact_name: str | None,
        chunker: ParentChildChunker,
        blocks: list[DocumentBlock] | None = None,
    ) -> Document:
        source_bytes = source_path.read_bytes()
        sha256 = hashlib.sha256(source_bytes).hexdigest()
        existing = await self.session.scalar(select(Document).where(Document.sha256 == sha256))
        if existing is not None:
            raise DuplicateDocumentError(f"文件已导入：{source_path.name} ({existing.id})")

        artifact = await self.get_or_create_artifact(artifact_name)
        structured_blocks = blocks or []
        normalized_text = blocks_to_text(structured_blocks) if structured_blocks else text
        document = Document(
            artifact=artifact,
            title=source_path.stem,
            source_filename=source_path.name,
            source_uri=f"imports/{source_path.name}",
            sha256=sha256,
            full_text=normalized_text,
        )
        self.session.add(document)

        parent_chunks = chunker.split_blocks(structured_blocks) if structured_blocks else chunker.split(text)
        for parent_payload in parent_chunks:
            parent_metadata = {
                "source_filename": source_path.name,
                "chunking_version": "v2_heading_aware" if structured_blocks else "v1_text",
                **parent_payload.metadata,
            }
            parent = DocumentChunk(
                document=document,
                chunk_level="parent",
                sequence=parent_payload.sequence,
                content=parent_payload.content,
                char_count=len(parent_payload.content),
                metadata_json=parent_metadata,
            )
            self.session.add(parent)
            for child_payload in parent_payload.children:
                child = DocumentChunk(
                    document=document,
                    parent=parent,
                    chunk_level="child",
                    sequence=child_payload.sequence,
                    content=child_payload.content,
                    char_count=len(child_payload.content),
                    metadata_json={**parent_metadata, **child_payload.metadata},
                )
                self.session.add(child)

        await self.session.commit()
        await self.session.refresh(document)
        return document
