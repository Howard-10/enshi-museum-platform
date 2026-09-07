from uuid import uuid4

from app.schemas.knowledge import KeywordDocumentMatch
from app.services.keyword_retrieval import catalog_concept_score, extract_search_terms


def test_keyword_document_match_accepts_hybrid_float_score() -> None:
    result = KeywordDocumentMatch(
        document_id=uuid4(),
        chunk_id=uuid4(),
        title="测试资料",
        excerpt="测试内容",
        score=0.625,
    )

    assert result.score == 0.625


def test_catalog_concepts_help_descriptive_queries() -> None:
    assert catalog_concept_score("状元及第镜", "记录读书高中寓意的明代铜镜") > 0
    assert "诰命" in extract_search_terms("鹤峰地区一块记载朝廷诰命的碑刻")
