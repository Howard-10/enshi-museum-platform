from app.cli.evaluate_retrieval import EvaluationCase, evaluate_result


def test_evaluation_requires_the_expected_artifact_and_media_type() -> None:
    case = EvaluationCase(
        case_id="case",
        query="西瓜碑音频",
        expected_artifact="西瓜碑",
        expected_media_type="audio",
        minimum_citations=1,
    )
    result = evaluate_result(
        case,
        {
            "artifacts": [{"name": "西瓜碑"}],
            "media": [{"type": "audio"}],
            "citations": [{"title": "来源"}],
            "answer_scope": "internal_only",
        },
    )

    assert result["passed"] is True


def test_evaluation_fails_when_the_expected_artifact_is_missing() -> None:
    case = EvaluationCase(case_id="case", query="问题", expected_artifact="西瓜碑")
    result = evaluate_result(
        case,
        {"artifacts": [], "media": [], "citations": [], "answer_scope": "internal_only"},
    )

    assert result["passed"] is False
