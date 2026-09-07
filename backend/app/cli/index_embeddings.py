"""Plan or explicitly run vector indexing for changed child chunks."""

from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.embedding_index import (
    build_index_plan,
    create_pilot_run,
    index_child_chunks,
    provision_production_table,
    run_pilot,
)
from app.services.model_readiness import require_external_model_calls


async def main() -> None:
    parser = argparse.ArgumentParser(description="Plan or run approved embedding indexing.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Maximum child chunks to inspect or index."
    )
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of real 20-item embedding requests for this run.",
    )
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Index child chunks belonging to any catalog-linked artifact only.",
    )
    parser.add_argument("--pilot", action="store_true", help="Create a 20-item staging pilot.")
    parser.add_argument("--run-id", help="Run an existing pilot UUID after explicit approval.")
    parser.add_argument(
        "--provision-profile",
        help="Create the fixed vector(N) production table after pilot approval.",
    )
    parser.add_argument(
        "--approve-pilot",
        help="Mark a successful pilot profile as eligible for a production table.",
    )
    parser.add_argument("--yes", action="store_true", help="Acknowledge real embedding API calls.")
    args = parser.parse_args()

    async with SessionLocal() as session:
        plan = await build_index_plan(
            session,
            config=settings,
            limit=args.limit,
            catalog_only=args.catalog_only,
        )
        print(json.dumps({"mode": "plan", **plan.__dict__}, ensure_ascii=False, indent=2))
        if args.pilot:
            pilot = await create_pilot_run(session, config=settings, limit=20)
            print(
                json.dumps({"mode": "pilot_created", "run_id": str(pilot.id)}, ensure_ascii=False)
            )
            return
        if args.approve_pilot:
            from sqlalchemy import func, select

            from app.db.models.core import EmbeddingPilotItem, EmbeddingProfile

            profile = await session.get(EmbeddingProfile, args.approve_pilot)
            if profile is None:
                raise SystemExit("Unknown embedding profile")
            failed = await session.scalar(
                select(func.count())
                .select_from(EmbeddingPilotItem)
                .where(
                    EmbeddingPilotItem.embedding_profile_id == profile.id,
                    EmbeddingPilotItem.status == "failed",
                )
            )
            successful = await session.scalar(
                select(func.count())
                .select_from(EmbeddingPilotItem)
                .where(
                    EmbeddingPilotItem.embedding_profile_id == profile.id,
                    EmbeddingPilotItem.status.in_(("success", "skipped")),
                )
            )
            if failed or (successful or 0) < 20:
                raise SystemExit(
                    "Pilot is not eligible: need 20 successful/staged items and zero failures"
                )
            profile.status = "pilot_passed"
            await session.commit()
            print(
                json.dumps({"mode": "pilot_approved", "profile_id": profile.id}, ensure_ascii=False)
            )
            return
        if args.provision_profile:
            table = await provision_production_table(session, profile_id=args.provision_profile)
            print(
                json.dumps({"mode": "production_table_ready", "table": table}, ensure_ascii=False)
            )
            return
        if not args.yes:
            print("No model request was made. Re-run with --yes only after approval.")
            return
        require_external_model_calls(settings)
        if args.run_id:
            import uuid

            result = await run_pilot(session, run_id=uuid.UUID(args.run_id), config=settings)
            print(json.dumps({"mode": "pilot_ran", **result}, ensure_ascii=False, indent=2))
            return
        result = await index_child_chunks(
            session,
            config=settings,
            limit=args.limit,
            catalog_only=args.catalog_only,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
        )
        print(json.dumps({"mode": "indexed", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
