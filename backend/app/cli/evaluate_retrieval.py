"""Evaluate the offline evidence flow without calling models or web search."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db.session import SessionLocal
from app.graphs.chat_graph import chat_graph
from app.services.rag_pipeline import RagPipeline


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    query: str
    expected_artifact: str | None = None
    category: str = "exact_artifact"
    priority: str = "normal"
    expected_document_title: str | None = None
    expected_media_type: str | None = None
    minimum_citations: int = 0
    minimum_documents: int | None = None
    should_refuse: bool = False
    reference_answer: str | None = None


def load_cases(path: Path) -> list[EvaluationCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_cases, list):
        raise TypeError("Evaluation file must contain a JSON list")
    return [
        EvaluationCase(
            case_id=item["id"],
            category=item["category"],
            priority=item["priority"],
            query=item["query"],
            expected_artifact=item.get("expected_artifact") or None,
            expected_document_title=item.get("expected_document_title") or None,
            expected_media_type=item.get("expected_media_type"),
            minimum_citations=item.get("minimum_citations", item.get("minimum_documents", 0)),
            should_refuse=bool(item.get("should_refuse", False)),
            reference_answer=item.get("reference_answer"),
        )
        for item in raw_cases
    ]


def evaluate_result(case: EvaluationCase, result: dict[str, Any]) -> dict[str, Any]:
    artifact_names = [artifact["name"] for artifact in result["artifacts"]]
    citation_titles = [citation["title"] for citation in result["citations"]]
    media_types = sorted({item["type"] for item in result["media"]})
    artifact_rank = (
        artifact_names.index(case.expected_artifact) + 1
        if case.expected_artifact in artifact_names
        else None
    )
    artifact_passed = case.expected_artifact is None or artifact_rank is not None
    document_passed = case.expected_document_title is None or any(
        case.expected_document_title in title for title in citation_titles
    )
    media_passed = case.expected_media_type is None or case.expected_media_type in media_types
    citation_count = len(result.get("citations", result.get("document_matches", [])))
    minimum_citations = (
        case.minimum_documents if case.minimum_documents is not None else case.minimum_citations
    )
    citations_passed = citation_count >= minimum_citations
    refusal_passed = not case.should_refuse or result["answer_scope"] == "insufficient_evidence"
    return {
        "id": case.case_id,
        "category": case.category,
        "priority": case.priority,
        "query": case.query,
        "expected_artifact": case.expected_artifact,
        "found_artifacts": artifact_names,
        "artifact_rank": artifact_rank,
        "expected_document_title": case.expected_document_title,
        "citation_titles": citation_titles,
        "expected_media_type": case.expected_media_type,
        "found_media_types": media_types,
        "minimum_citations": case.minimum_citations,
        "found_citations": citation_count,
        "retrieval_mode": result.get("retrieval_mode", "keyword_rag"),
        "answer_scope": result.get("answer_scope", "internal_only"),
        "should_refuse": case.should_refuse,
        "checks": {
            "artifact": artifact_passed,
            "document": document_passed,
            "media": media_passed,
            "citations": citations_passed,
            "refusal": refusal_passed,
        },
        "passed": all(
            (artifact_passed, document_passed, media_passed, citations_passed, refusal_passed)
        ),
    }


async def evaluate(cases: list[EvaluationCase]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    async with SessionLocal() as session:
        pipeline = RagPipeline(session)
        for case in cases:
            retrieval = await pipeline.search(
                case.query, include_media=case.expected_media_type is not None
            )
            result = chat_graph.invoke(
                {
                    "session_id": "offline-evaluation",
                    "user_query": case.query,
                    "intent": "",
                    "answer": "",
                    "citations": retrieval["citations"],
                    "media": retrieval["media"],
                    "retrieval": retrieval,
                    "answer_scope": "insufficient_evidence",
                    "notice": None,
                    "evidence_status": "sufficient" if not case.should_refuse else "insufficient",
                    "reason_codes": ["offline_retrieval_evaluation"],
                }
            )
            results.append(
                evaluate_result(
                    case,
                    {
                        "artifacts": retrieval["artifacts"],
                        "citations": result["citations"],
                        "media": result["media"],
                        "answer_scope": result["answer_scope"],
                        "retrieval_mode": retrieval["mode"],
                    },
                )
            )
    artifact_cases = [item for item in results if item["expected_artifact"]]
    media_cases = [item for item in results if item["expected_media_type"]]
    refusal_cases = [item for item in results if item["should_refuse"]]
    high_priority = [item for item in results if item["priority"] == "high"]
    semantic_cases = [item for item in results if item["category"].startswith("semantic_")]
    retrieval_modes = {item["retrieval_mode"] for item in results}

    def pass_rate(items: list[dict[str, Any]]) -> float | None:
        if not items:
            return None
        return round(sum(bool(item["passed"]) for item in items) / len(items), 4)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": retrieval_modes.pop() if len(retrieval_modes) == 1 else "mixed_retrieval",
        "external_model_calls": sum(
            item["retrieval_mode"] == "hybrid_rag" for item in results
        ),
        "web_search_calls": 0,
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "metrics": {
            "artifact_cases": len(artifact_cases),
            "hit_at_1": round(
                sum(item["artifact_rank"] == 1 for item in artifact_cases) / len(artifact_cases),
                4,
            )
            if artifact_cases
            else None,
            "hit_at_3": round(
                sum(
                    item["artifact_rank"] is not None and item["artifact_rank"] <= 3
                    for item in artifact_cases
                )
                / len(artifact_cases),
                4,
            )
            if artifact_cases
            else None,
            "hit_at_5": round(
                sum(
                    item["artifact_rank"] is not None and item["artifact_rank"] <= 5
                    for item in artifact_cases
                )
                / len(artifact_cases),
                4,
            )
            if artifact_cases
            else None,
            "media_hit_rate": round(
                sum(item["checks"]["media"] for item in media_cases) / len(media_cases),
                4,
            )
            if media_cases
            else None,
            "refusal_correct_rate": round(
                sum(item["checks"]["refusal"] for item in refusal_cases) / len(refusal_cases),
                4,
            )
            if refusal_cases
            else None,
            "high_priority_pass_rate": pass_rate(high_priority),
            "semantic_cases": len(semantic_cases),
        },
        "results": results,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local retrieval without model APIs.")
    parser.add_argument(
        "cases", type=Path, nargs="+", help="One or more JSON evaluation case files"
    )
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Write and print an evaluation report without returning a non-zero exit code.",
    )
    args = parser.parse_args()

    cases = [case for path in args.cases for case in load_cases(path)]
    report = await evaluate(cases)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["failed"] and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
