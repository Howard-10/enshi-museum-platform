"""Run the fixed 20-question chat answer evaluation set against the live API."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import httpx


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("评测集必须是非空数组。")
    return payload


def source_text(response: dict[str, Any]) -> str:
    parts: list[str] = [response.get("answer", "")]
    for citation in response.get("citations", []):
        parts.extend(
            [
                citation.get("id", ""),
                citation.get("title", ""),
                citation.get("excerpt", "") or "",
            ]
        )
    return " ".join(parts).lower()


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    citations = response.get("citations", [])
    expected_artifact = str(case.get("expected_artifact", "")).strip()
    expected_media = case.get("expected_media_type")
    response_text = source_text(response)
    artifact_passed = not expected_artifact or expected_artifact.lower() in response_text
    citation_passed = len(citations) >= int(case.get("minimum_citations", 0))
    media_types = [str(item.get("type", "")).lower() for item in response.get("media", [])]
    media_passed = expected_media is None or str(expected_media).lower() in media_types
    refused = response.get("answer_scope") == "insufficient_evidence" or response.get("evidence_status") == "insufficient"
    refusal_passed = refused if case.get("should_refuse", False) else not refused
    evidence_passed = (
        response.get("evidence_status") == "sufficient"
        if not case.get("should_refuse", False)
        else refused
    )
    generated = "回答仅基于本轮后端证据包生成。" in str(response.get("notice", ""))
    checks = {
        "artifact_or_source": artifact_passed,
        "minimum_citations": citation_passed,
        "media_type": media_passed,
        "evidence_status": evidence_passed,
        "refusal": refusal_passed,
    }
    return {
        "id": case["id"],
        "category": case["category"],
        "priority": case["priority"],
        "query": case["query"],
        "expected_artifact": expected_artifact,
        "expected_media_type": expected_media,
        "answer": response.get("answer"),
        "answer_scope": response.get("answer_scope"),
        "evidence_status": response.get("evidence_status"),
        "reason_codes": response.get("reason_codes", []),
        "notice": response.get("notice"),
        "citation_titles": [item.get("title") for item in citations],
        "citation_count": len(citations),
        "media_types": media_types,
        "model_generated": generated,
        "checks": checks,
        "automated_passed": all(checks.values()),
        "manual_review": {
            "citation_legality": None,
            "evidence_support": None,
            "museum_hallucination": None,
            "internal_general_separation": None,
            "usability": None,
        },
    }


async def request_answer(client: httpx.AsyncClient, url: str, case: dict[str, Any], run_id: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = await client.post(
                url,
                json={"session_id": f"chat-eval-{run_id}-{case['id']}", "message": case["query"]},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("聊天接口返回的不是 JSON 对象。")
            return payload
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < 3:
                await asyncio.sleep(1.5 * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("聊天接口请求失败。")


async def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.cases)
    if args.ids:
        requested = {item.strip() for item in args.ids.split(",") if item.strip()}
        cases = [case for case in cases if case.get("id") in requested]
    if args.limit:
        cases = cases[: args.limit]
    run_id = str(uuid.uuid4())
    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(args.timeout, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for case in cases:
            try:
                response = await request_answer(client, args.url, case, run_id)
                results.append(evaluate_case(case, response))
            except Exception as exc:  # noqa: BLE001 - preserve one failed case and continue the report
                results.append(
                    {
                        "id": case["id"],
                        "category": case["category"],
                        "priority": case["priority"],
                        "query": case["query"],
                        "answer": None,
                        "error": f"{type(exc).__name__}: {exc}",
                        "checks": {},
                        "automated_passed": False,
                        "manual_review": {},
                    }
                )

    passed = sum(1 for item in results if item["automated_passed"])
    generated = sum(1 for item in results if item.get("model_generated"))
    category_summary: dict[str, dict[str, int]] = {}
    for category in sorted({item["category"] for item in results}):
        category_items = [item for item in results if item["category"] == category]
        category_summary[category] = {
            "total": len(category_items),
            "passed": sum(1 for item in category_items if item["automated_passed"]),
        }
    report = {
        "report_version": "chat-answer-evaluation-v1",
        "run_id": run_id,
        "cases_file": str(args.cases),
        "chat_url": args.url,
        "total": len(results),
        "automated_passed": passed,
        "automated_failed": len(results) - passed,
        "model_generated": generated,
        "category_summary": category_summary,
        "reason_code_counts": dict(Counter(code for item in results for code in item.get("reason_codes", []))),
        "manual_review_required": True,
        "manual_review_fields": [
            "citation_legality",
            "evidence_support",
            "museum_hallucination",
            "internal_general_separation",
            "usability",
        ],
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="评测 20 条基于证据的聊天回答。")
    parser.add_argument("--cases", type=Path, default=Path("/app/evaluation/chat-evaluation-cases.json"))
    parser.add_argument("--report", type=Path, default=Path("/app/reports/chat-answer-evaluation.json"))
    parser.add_argument("--url", default="http://host.docker.internal:8000/api/v1/chat")
    parser.add_argument("--limit", type=int, default=0, help="只运行前 N 条，0 表示全部。")
    parser.add_argument("--ids", help="只运行指定题目 ID，多个 ID 用英文逗号分隔。")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    print(json.dumps({key: report[key] for key in ("run_id", "total", "automated_passed", "automated_failed", "model_generated", "category_summary")}, ensure_ascii=False, indent=2))
    if report["automated_failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
