from app.services.keyword_retrieval import excerpt_for, extract_search_terms


def test_extract_search_terms_keeps_artifact_name_from_a_natural_question() -> None:
    terms = extract_search_terms("请介绍一下西瓜碑的音频")

    assert "西瓜碑" in terms
    assert "音频" in terms


def test_excerpt_centers_on_the_first_matching_term() -> None:
    excerpt = excerpt_for("前言" * 40 + "西瓜碑是重要文物。" + "后记" * 40, ["西瓜碑"])

    assert "西瓜碑是重要文物" in excerpt
    assert excerpt.startswith("…")
