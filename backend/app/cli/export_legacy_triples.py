"""Export old Chroma triples for human review without modifying the old index."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

TRIPLE_SQL = """
SELECT subject.id, subject.string_value, relation.string_value, object.string_value, source.string_value
FROM embedding_metadata AS subject
JOIN embedding_metadata AS relation ON relation.id = subject.id AND relation.key = 'relation'
JOIN embedding_metadata AS object ON object.id = subject.id AND object.key = 'object'
LEFT JOIN embedding_metadata AS source ON source.id = subject.id AND source.key = 'source'
WHERE subject.key = 'subject'
ORDER BY subject.id
"""


def load_triples(chroma_db: Path) -> list[tuple[int, str, str, str, str | None]]:
    connection = sqlite3.connect(f"file:{chroma_db.resolve()}?mode=ro", uri=True)
    try:
        return list(connection.execute(TRIPLE_SQL))
    finally:
        connection.close()


def build_rows(records: list[tuple[int, str, str, str, str | None]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[tuple[int, str | None]]] = defaultdict(list)
    for record_id, subject, relation, object_, source in records:
        grouped[(subject, relation, object_)].append((record_id, source))

    rows: list[dict[str, object]] = []
    for (subject, relation, object_), items in sorted(grouped.items()):
        sources = sorted({source for _, source in items if source})
        source_missing = any(not source for _, source in items)
        raw_count = len(items)
        high_risk = source_missing or raw_count > 1
        rows.append(
            {
                "subject": subject,
                "relation": relation,
                "object": object_,
                "source_files": "; ".join(sources),
                "raw_record_count": raw_count,
                "is_duplicate": raw_count > 1,
                "source_missing": source_missing,
                "risk_level": "high" if high_risk else "normal",
                "review_status": "pending",
                "review_note": "",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export old triples into a pending human-review CSV."
    )
    parser.add_argument("chroma_db", type=Path, help="Old Chroma sqlite database; opened read-only")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    if not args.chroma_db.is_file():
        raise SystemExit(f"Old Chroma database not found: {args.chroma_db}")

    records = load_triples(args.chroma_db)
    rows = build_rows(records)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_chroma_db": str(args.chroma_db.resolve()),
        "access_mode": "read_only",
        "raw_records": len(records),
        "unique_triples": len(rows),
        "duplicate_records": len(records) - len(rows),
        "triples_with_missing_source": sum(bool(row["source_missing"]) for row in rows),
        "high_risk_triples": sum(row["risk_level"] == "high" for row in rows),
        "review_status": "pending",
        "not_imported_into_platform": True,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
