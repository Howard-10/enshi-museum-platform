"""Run one guarded chat-generation check without changing application settings."""

from __future__ import annotations

import argparse
import asyncio
import json

from app.db.session import SessionLocal
from app.services.answer_generation import generate_grounded_answer
from app.services.answer_generation import GeneratedAnswer
from app.services.evidence_gate import evidence_gate
from app.services.model_clients import create_chat_client
from app.services.rag_pipeline import RagPipeline


async def main() -> None:
    parser = argparse.ArgumentParser(description="Verify one evidence-grounded chat reply.")
    parser.add_argument("query", help="Museum question to validate")
    parser.add_argument(
        "--provider-check",
        action="store_true",
        help="Verify only the configured chat provider and structured output, without museum data.",
    )
    args = parser.parse_args()

    if args.provider_check:
        result = await create_chat_client().with_structured_output(GeneratedAnswer).ainvoke(
            "请只按给定结构返回：internal_answer 写‘连通测试成功’，"
            "internal_citations 为空列表，unverified_extension 为 null。"
        )
        generated = (
            result.model_dump()
            if isinstance(result, GeneratedAnswer)
            else GeneratedAnswer.model_validate(result).model_dump()
        )
        print(
            json.dumps(
                {
                    "provider_check_passed": generated["internal_answer"] == "连通测试成功",
                    "model_response": generated,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    async with SessionLocal() as session:
        retrieval = await RagPipeline(session).search(args.query, include_media=False)
        gate = evidence_gate(args.query, retrieval)
        if gate.get("citation_scope") == "catalog_only":
            retrieval = {**retrieval, "citations": retrieval.get("catalog_citations", [])}
        generated, reason = (None, None)
        if gate["evidence_status"] == "sufficient":
            generated, reason = await generate_grounded_answer(args.query, retrieval)

    print(
        json.dumps(
            {
                "query": args.query,
                "retrieval_mode": retrieval["mode"],
                "evidence_status": gate["evidence_status"],
                "reason_codes": gate["reason_codes"],
                "generation_passed": generated is not None,
                "generation_reason": reason,
                "answer": generated["answer"] if generated else None,
                "citation_titles": [citation["title"] for citation in retrieval["citations"]],
                "citation_ids": [citation["id"] for citation in generated["citations"]]
                if generated
                else [],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
