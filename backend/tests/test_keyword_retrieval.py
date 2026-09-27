from app.services.keyword_retrieval import excerpt_for, extract_search_terms, name_overlap_score


def test_extract_search_terms_keeps_artifact_name_from_a_natural_question() -> None:
    terms = extract_search_terms("请介绍一下西瓜碑的音频")

    assert "西瓜碑" in terms
    assert "音频" in terms


def test_descriptive_name_match_beats_generic_metadata_signal() -> None:
    query = "一面有凤凰和八卦纹样的明代铜镜是什么"

    assert name_overlap_score("凤凰八卦铜镜", query) > name_overlap_score("缠枝双龙瓶", query)


def test_exact_artifact_name_gets_a_dominant_identity_score() -> None:
    assert name_overlap_score("凤凰八卦铜镜", "请介绍凤凰八卦铜镜") > 10_000


def test_specific_name_outranks_a_generic_suffix_in_a_description() -> None:
    query = "一面有凤凰和八卦纹样的明代铜镜是什么"

    assert name_overlap_score("凤凰八卦铜镜", query) > name_overlap_score("铜镜", query)


def test_excerpt_centers_on_the_first_matching_term() -> None:
    excerpt = excerpt_for("前言" * 40 + "西瓜碑是重要文物。" + "后记" * 40, ["西瓜碑"])

    assert "西瓜碑是重要文物" in excerpt
    assert not excerpt.startswith("…")
    assert not excerpt.endswith("…")


def test_excerpt_can_be_bounded_only_when_requested() -> None:
    source = "前言" * 40 + "西瓜碑是重要文物。" + "后记" * 40

    excerpt = excerpt_for(source, ["西瓜碑"], max_length=40)

    assert len(excerpt) <= 40
    assert "…" not in excerpt
