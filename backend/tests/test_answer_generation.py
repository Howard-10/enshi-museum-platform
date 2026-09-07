from app.services.answer_generation import clean_user_facing_text


def test_clean_user_facing_text_hides_internal_prompt_fields() -> None:
    value = "馆内未收藏相关文物，INTERNAL_EVIDENCE 中没有相关内容，USER_QUERY 已处理。"

    assert clean_user_facing_text(value) == "馆内未收藏相关文物，馆内资料中没有相关内容，你的问题已处理。"


def test_clean_user_facing_text_preserves_normal_text() -> None:
    value = "这是一段正常的馆藏介绍。"

    assert clean_user_facing_text(value) == value
