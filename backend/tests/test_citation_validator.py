from app.services.citation_validator import CitationValidator


def test_validator_rejects_unknown_or_duplicate_citations() -> None:
    validator = CitationValidator()
    assert not validator.validate(
        {"internal_answer": "馆藏事实", "internal_citations": ["SRC_001", "SRC_001"]},
        {"SRC_001"},
    ).valid
    assert not validator.validate(
        {"internal_answer": "馆藏事实", "internal_citations": ["SRC_999"]}, {"SRC_001"}
    ).valid


def test_validator_accepts_only_allowed_citations() -> None:
    result = CitationValidator().validate(
        {"internal_answer": "馆藏事实", "internal_citations": ["SRC_001"]}, {"SRC_001"}
    )
    assert result.valid
