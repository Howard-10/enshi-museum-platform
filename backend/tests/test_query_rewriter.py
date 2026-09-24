from app.services.query_rewriter import format_conversation_context, rewrite_query


def test_follow_up_question_is_rewritten_with_the_previous_artifact() -> None:
    history = [
        {"role": "user", "content": "介绍虎钮錞于"},
        {"role": "assistant", "content": "虎钮錞于是馆内目录收录的青铜器。"},
    ]

    rewritten = rewrite_query("它是什么材质？", history)

    assert rewritten.used_history is True
    assert rewritten.subject == "虎钮錞于"
    assert rewritten.standalone_query == "虎钮錞于是什么材质？"


def test_new_named_artifact_is_not_overwritten_by_old_context() -> None:
    history = [{"role": "user", "content": "介绍虎钮錞于"}]

    rewritten = rewrite_query("那西兰卡普呢？", history)

    assert rewritten.used_history is False
    assert "西兰卡普" in rewritten.standalone_query


def test_context_formatter_labels_history_as_conversation_not_evidence() -> None:
    context = format_conversation_context(
        [
            {"role": "user", "content": "介绍虎钮錞于"},
            {"role": "assistant", "content": "这是上一轮回答"},
        ]
    )

    assert "访客：介绍虎钮錞于" in context
    assert "讲解员：这是上一轮回答" in context
