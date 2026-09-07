"""Print Phase 0 evidence-review coverage without changing data."""

import asyncio
import json

from app.db.session import SessionLocal
from app.services.evidence_review import review_coverage


async def main() -> None:
    async with SessionLocal() as session:
        print(json.dumps(await review_coverage(session), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
