"""Read-only preview for the first copied source-document batch.

This helps the UI show what can be imported before PostgreSQL is available.
It is intentionally not a retrieval system and does not read legacy indexes.
"""

import json
from pathlib import Path

from app.schemas.knowledge import KnowledgeSeedFile, KnowledgeSeedResponse

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PROJECT_ROOT / "data" / "knowledge_seed_manifest.json"
COPIED_ROOT = PROJECT_ROOT / "data" / "raw" / "seed-v1"


def get_knowledge_seed() -> KnowledgeSeedResponse:
    if not MANIFEST_PATH.is_file():
        return KnowledgeSeedResponse(
            seed_name="本地知识库",
            description="种子清单暂未挂载；馆藏目录仍可正常使用。",
            total_files=0,
            copied_files=0,
            files=[],
        )
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = [
        KnowledgeSeedFile(
            relative_path=item["relative_path"],
            kind=item["kind"],
            artifact=item.get("artifact"),
            copied=(COPIED_ROOT / item["relative_path"]).is_file(),
        )
        for item in raw["files"]
    ]
    return KnowledgeSeedResponse(
        seed_name=raw["seed_name"],
        description=raw["description"],
        total_files=len(files),
        copied_files=sum(item.copied for item in files),
        files=files,
    )
