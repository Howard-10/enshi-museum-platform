"""Compare a saved keyword report with a hybrid report, including semantic regressions."""

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rank(result: dict) -> int | None:
    return result.get("artifact_rank")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare keyword and hybrid retrieval reports.")
    parser.add_argument("keyword", type=Path)
    parser.add_argument("hybrid", type=Path)
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Print the comparison even when the acceptance threshold is not met.",
    )
    args = parser.parse_args()
    baseline = {item["id"]: item for item in load(args.keyword)["results"]}
    hybrid = {item["id"]: item for item in load(args.hybrid)["results"]}
    semantic_ids = [key for key, item in hybrid.items() if item["category"].startswith("semantic_")]
    improved = unchanged = degraded = 0
    high_priority_degraded: list[str] = []
    for case_id in semantic_ids:
        before, after = rank(baseline[case_id]), rank(hybrid[case_id])
        before_value, after_value = before or 999, after or 999
        if after_value < before_value:
            improved += 1
        elif after_value == before_value:
            unchanged += 1
        else:
            degraded += 1
            if hybrid[case_id]["priority"] == "high":
                high_priority_degraded.append(case_id)
    def hit3(report: dict[str, int | None], ids: list[str]) -> int:
        return sum((rank(report[item]) or 999) <= 3 for item in ids)
    output = {
        "semantic_cases": len(semantic_ids),
        "semantic_hit3_keyword": hit3(baseline, semantic_ids),
        "semantic_hit3_hybrid": hit3(hybrid, semantic_ids),
        "improved_count": improved,
        "unchanged_count": unchanged,
        "degraded_count": degraded,
        "high_priority_degraded": high_priority_degraded,
    }
    output["passed"] = (
        output["semantic_hit3_hybrid"] > output["semantic_hit3_keyword"]
        and not high_priority_degraded
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not output["passed"] and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
