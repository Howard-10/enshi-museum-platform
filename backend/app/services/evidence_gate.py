"""Deterministic authority and sufficiency checks; this is never delegated to a model."""

from __future__ import annotations

from typing import Any

CATALOG_FIELD_WORDS = (
    "年代",
    "时代",
    "地点",
    "出土",
    "材质",
    "材料",
    "编号",
    "馆藏",
    "哪里",
)
BACKGROUND_WORDS = (
    "历史",
    "背景",
    "用途",
    "民俗",
    "文化",
    "意义",
    "介绍",
    "是什么",
    "关系",
    "三交",
    "交往",
    "交流",
    "交融",
)
MEDIA_WORDS = ("图片", "视频", "音频")


def _compact(value: str) -> str:
    """Normalize visitor wording for exact catalog-name checks."""

    return "".join(
        character
        for character in value
        if character.isalnum() or "\u4e00" <= character <= "\u9fff"
    )


def evidence_gate(query: str, retrieval: dict[str, Any]) -> dict[str, Any]:
    """Classify evidence with P1 catalog facts before any document-derived claim."""

    artifacts = retrieval.get("artifacts", [])
    citations = retrieval.get("citations", [])
    media = retrieval.get("media", [])
    is_media = any(word in query for word in MEDIA_WORDS)
    is_catalog_field = any(word in query for word in CATALOG_FIELD_WORDS)
    is_background = any(word in query for word in BACKGROUND_WORDS)

    if is_media:
        if media and retrieval.get("media_review_status") in {"approved", "legacy_verified"}:
            return {
                "evidence_status": "sufficient",
                "reason_codes": ["verified_media_link", "minio_object_present"],
            }
        if media:
            return {
                "evidence_status": "insufficient",
                "reason_codes": ["media_link_needs_review"],
            }
        return {"evidence_status": "insufficient", "reason_codes": ["no_verified_media_evidence"]}
    # An exact catalog-name request must stay grounded in the P1 catalog even
    # when the visitor says “介绍”. Background documents may mention similar
    # objects and should not be allowed to overturn the catalog identity.
    compact_query = _compact(query)
    exact_catalog_match = any(
        artifact.get("name")
        and _compact(str(artifact["name"])) in compact_query
        for artifact in artifacts
    )
    if exact_catalog_match and retrieval.get("catalog_citations"):
        if is_background and citations and retrieval.get("has_approved_document_link"):
            return {
                "evidence_status": "sufficient",
                "reason_codes": [
                    "exact_catalog_artifact",
                    "p1_catalog_record",
                    "approved_background_link",
                ],
                "citation_scope": "catalog_with_background",
            }
        return {
            "evidence_status": "sufficient",
            "reason_codes": ["exact_catalog_artifact", "p1_catalog_record"],
            "citation_scope": "catalog_only",
        }
    # P1 catalog fields are directly traceable to the imported structured
    # catalog and do not depend on a Word-to-artifact association. Background
    # claims still require a separately approved Word relationship.
    # Fuzzy artifact hits alone are not evidence for an unrelated question.
    # They are common for short or broad queries, so only a catalog-field
    # request may use them without an exact catalog-name match.
    if artifacts and is_catalog_field:
        if retrieval.get("catalog_citations"):
            return {
                "evidence_status": "sufficient",
                "reason_codes": ["catalog_field_present", "p1_catalog_record"],
                "citation_scope": "catalog_only",
            }
        if retrieval.get("has_approved_document_link"):
            return {
                "evidence_status": "sufficient",
                "reason_codes": ["catalog_field_present", "approved_document_link"],
                "citation_scope": "all_internal",
            }
        return {
            "evidence_status": "insufficient",
            "reason_codes": ["catalog_field_present", "document_link_needs_review"],
        }
    if is_background and citations and (
        retrieval.get("has_approved_document_link", False)
        or retrieval.get("has_approved_document_review", False)
    ):
        return {
            "evidence_status": "sufficient",
            "reason_codes": ["approved_document_link"],
            "citation_scope": "approved_documents",
        }
    if retrieval.get("conflicting_internal_evidence", False):
        return {"evidence_status": "conflicting", "reason_codes": ["conflicting_internal_evidence"]}
    return {"evidence_status": "insufficient", "reason_codes": ["no_verified_evidence"]}
