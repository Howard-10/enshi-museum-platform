"""Import one or more Word documents into the new PostgreSQL schema.

Example:
    python -m app.cli.import_docx ..\\data\\raw --artifact "虎钮錞于"
"""

import argparse
import asyncio
import hashlib
from pathlib import Path

from app.db.session import SessionLocal
from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.services.document_chunker import ParentChildChunker, blocks_to_text, parse_docx_blocks


def find_docx_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() == ".docx" else []
    return sorted(path for path in source.rglob("*.docx") if not path.name.startswith("~$"))


def infer_artifact_name(path: Path, knowledge_root: Path) -> str | None:
    """Return the artifact folder for the standard period/artifact/text layout.

    New source packages use ``时期/文物/文物文字/文件.docx``.  Keeping the
    association at import time means documents and their corresponding audio
    share one Artifact record without relying on filename matching.
    """

    relative = path.resolve().relative_to(knowledge_root.resolve())
    if len(relative.parts) >= 4 and "文字" in relative.parts[2]:
        return relative.parts[1]
    return None


async def import_file(path: Path, artifact_name: str | None, *, replace_existing: bool = False) -> None:
    blocks = parse_docx_blocks(path)
    text = blocks_to_text(blocks)
    if not text:
        print(f"[skip] 未提取到文本：{path}")
        return

    async with SessionLocal() as session:
        repository = DocumentRepository(session)
        if replace_existing:
            await repository.remove_existing_by_sha256(hashlib.sha256(path.read_bytes()).hexdigest())
        try:
            document = await repository.import_word_text(
                source_path=path,
                text=text,
                artifact_name=artifact_name,
                chunker=ParentChildChunker(),
                blocks=blocks,
            )
        except DuplicateDocumentError as error:
            print(f"[skip] {error}")
            return
    print(f"[ok] {path.name} -> document_id={document.id}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="导入 Word 文档并生成父子 Chunk")
    parser.add_argument("source", type=Path, help="单个 .docx 文件或包含 .docx 的目录")
    parser.add_argument("--artifact", help="可选：关联的标准文物名称")
    parser.add_argument(
        "--infer-artifact-from-path",
        action="store_true",
        help="按“时期/文物/文字/文件.docx”目录结构自动关联文物",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="显式删除同 SHA-256 的旧分块并用标题感知解析重新导入",
    )
    args = parser.parse_args()

    files = find_docx_files(args.source)
    if not files:
        raise SystemExit("未找到可导入的 .docx 文件")
    print(f"[info] 待导入 {len(files)} 份 Word 文档")
    for path in files:
        artifact_name = args.artifact
        if args.infer_artifact_from_path:
            artifact_name = infer_artifact_name(path, args.source.resolve())
        await import_file(path, artifact_name, replace_existing=args.replace_existing)


if __name__ == "__main__":
    asyncio.run(main())
