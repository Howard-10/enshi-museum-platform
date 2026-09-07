"""Persistence operations for imported source documents."""

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.core import Artifact, Document, DocumentChunk
from app.services.document_chunker import ParentChildChunker


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

    async def import_word_text(
        self,
        *,
        source_path: Path,
        text: str,
        artifact_name: str | None,
        chunker: ParentChildChunker,
    ) -> Document:
        source_bytes = source_path.read_bytes()
        sha256 = hashlib.sha256(source_bytes).hexdigest()
        existing = await self.session.scalar(select(Document).where(Document.sha256 == sha256))
        if existing is not None:
            raise DuplicateDocumentError(f"文件已导入：{source_path.name} ({existing.id})")

        artifact = await self.get_or_create_artifact(artifact_name)
        document = Document(
            artifact=artifact,
            title=source_path.stem,
            source_filename=source_path.name,
            source_uri=f"imports/{source_path.name}",
            sha256=sha256,
            full_text=text,
        )
        self.session.add(document)

        for parent_payload in chunker.split(text):
            parent = DocumentChunk(
                document=document,
                chunk_level="parent",
                sequence=parent_payload.sequence,
                content=parent_payload.content,
                char_count=len(parent_payload.content),
                metadata_json={"source_filename": source_path.name},
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
                    metadata_json={"source_filename": source_path.name},
                )
                self.session.add(child)

        await self.session.commit()
        await self.session.refresh(document)
        return document
