"""Rebuild existing Word document chunks without changing document identities."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.db.models.core import Document
from app.db.session import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.document_chunker import ParentChildChunker, parse_docx_blocks


async def main() -> None:
    parser = argparse.ArgumentParser(description="用标题感知解析重建已有 Word 文档分块")
    parser.add_argument("source", type=Path, help="包含原始 .docx 文件的目录")
    args = parser.parse_args()
    files_by_sha256 = {
        hashlib.sha256(path.read_bytes()).hexdigest(): path
        for path in args.source.rglob("*.docx")
        if not path.name.startswith("~$")
    }
    updated = 0
    skipped = 0
    async with SessionLocal() as session:
        documents = (await session.scalars(select(Document).order_by(Document.source_filename))).all()
        repository = DocumentRepository(session)
        for document in documents:
            source_path = files_by_sha256.get(document.sha256)
            if source_path is None:
                skipped += 1
                continue
            blocks = parse_docx_blocks(source_path)
            if not blocks:
                skipped += 1
                continue
            child_count = await repository.rebuild_chunks(
                document,
                blocks=blocks,
                chunker=ParentChildChunker(),
            )
            updated += 1
            print(f"[ok] {document.source_filename}: {child_count} 个子分块")
        await session.commit()
    print(f"[done] 重建 {updated} 份文档，跳过 {skipped} 份")


if __name__ == "__main__":
    asyncio.run(main())
