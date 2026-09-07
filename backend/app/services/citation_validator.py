"""Last deterministic guard before a generated answer may reach a visitor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SOURCE_ID = re.compile(r"^SRC_[A-Z0-9_]+$")


@dataclass(frozen=True)
class CitationValidation:
    valid: bool
    reason_code: str | None = None


class CitationValidator:
    def validate(
        self, generated: dict[str, Any], allowed_source_ids: set[str]
    ) -> CitationValidation:
        citations = generated.get("internal_citations", [])
        answer = (generated.get("internal_answer") or "").strip()
        if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations):
            return CitationValidation(False, "citation_format_invalid")
        if len(citations) != len(set(citations)):
            return CitationValidation(False, "citation_duplicate")
        if any(
            not SOURCE_ID.fullmatch(item) or item not in allowed_source_ids for item in citations
        ):
            return CitationValidation(False, "citation_unknown")
        if answer and not citations:
            return CitationValidation(False, "internal_answer_without_citation")
        return CitationValidation(True)
