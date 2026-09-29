from app.services.keyword_retrieval import name_overlap_score


def test_fuzzy_catalog_name_signal_survives_a_small_typo() -> None:
    assert name_overlap_score("凤凰八卦铜镜", "凤凰八卦铜竟") > 0


def test_fuzzy_catalog_name_does_not_promote_a_generic_long_question() -> None:
    assert name_overlap_score("凤凰八卦铜镜", "请介绍一件明代青铜器的历史背景") == 0
