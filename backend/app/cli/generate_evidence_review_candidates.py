"""Generate human-review candidates without changing any source data."""

import asyncio
import json

from app.db.session import SessionLocal
from app.services.evidence_review import generate_review_candidates, review_coverage


async def main() -> None:
    async with SessionLocal() as session:
        generated = await generate_review_candidates(session)
        coverage = await review_coverage(session)
    print(
        json.dumps(
            {"generated": generated.__dict__, "coverage": coverage}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
