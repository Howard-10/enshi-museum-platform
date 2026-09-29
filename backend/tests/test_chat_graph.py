from app.graphs.chat_graph import _local_answer, _primary_artifact, chat_graph, classify_intent


def test_primary_artifact_prefers_specific_descriptive_match_over_generic_suffix() -> None:
    artifacts = [
        {"name": "铜镜", "score": 90},
        {"name": "凤凰八卦铜镜", "score": 340},
    ]

    selected = _primary_artifact("一面有凤凰和八卦纹样的明代铜镜是什么", artifacts)

    assert selected is not None
    assert selected["name"] == "凤凰八卦铜镜"


def test_primary_artifact_does_not_invent_a_single_winner_for_broad_queries() -> None:
    artifacts = [
        {"name": "唐崖长官司印", "score": 230},
        {"name": "永宁卫前千户所百户印", "score": 230},
    ]

    assert _primary_artifact("明代咸丰的青铜印有哪些", artifacts) is None


def test_local_answer_lists_multiple_catalog_matches_for_broad_query() -> None:
    artifacts = [
        {"name": "唐崖长官司印", "score": 230, "era": "明代", "material": "青铜"},
        {"name": "永宁卫前千户所百户印", "score": 230, "era": "明代", "material": "青铜"},
    ]

    answer = _local_answer("明代咸丰的青铜印有哪些", artifacts, [])

    assert "唐崖长官司印" in answer
    assert "永宁卫前千户所百户印" in answer
    assert "馆内目录中找到 2 项相关文物" in answer


def test_classify_intent_recognizes_audio_requests() -> None:
    state = {
        "session_id": "test",
        "user_query": "请播放西瓜碑语音介绍",
        "intent": "",
        "answer": "",
        "citations": [],
        "media": [],
        "retrieval": {"artifacts": [], "citations": [], "media": []},
        "answer_scope": "",
        "notice": None,
        "evidence_status": "",
        "reason_codes": [],
    }

    assert classify_intent(state)["intent"] == "media"


def test_mixed_query_keeps_the_catalog_answer_and_media_payload() -> None:
    state = {
        "session_id": "test",
        "user_query": "介绍凤凰八卦铜镜，再给我图片",
        "intent": "",
        "answer": "",
        "citations": [],
        "media": [{"id": "m1", "type": "image", "url": "https://example.test/m1"}],
        "retrieval": {
            "artifacts": [{"name": "凤凰八卦铜镜", "score": 600, "era": "明代"}],
            "citations": [],
            "media": [{"id": "m1", "type": "image", "url": "https://example.test/m1"}],
        },
        "answer_scope": "",
        "notice": None,
        "evidence_status": "sufficient",
        "reason_codes": [],
        "query_plan": {
            "intent": "mixed",
            "tasks": ["artifact_description", "media_request"],
            "needs_clarification": False,
        },
    }

    result = chat_graph.invoke(state)

    assert result["media"] == state["media"]
    assert "凤凰八卦铜镜" in result["answer"]


def test_media_query_without_subject_requests_clarification() -> None:
    state = {
        "session_id": "test",
        "user_query": "给我看看相关媒体",
        "intent": "",
        "answer": "",
        "citations": [],
        "media": [],
        "retrieval": {"artifacts": [], "citations": [], "media": []},
        "answer_scope": "",
        "notice": None,
        "evidence_status": "insufficient",
        "reason_codes": [],
        "query_plan": {"intent": "media", "needs_clarification": True},
    }

    result = chat_graph.invoke(state)

    assert "具体是哪件文物" in result["answer"]


def test_local_answer_uses_approved_background_excerpt_when_available() -> None:
    artifacts = [{"name": "西瓜碑", "score": 600, "era": "唐代", "location": "恩施"}]
    citations = [
        {
            "source_type": "internal",
            "title": "西瓜碑文物资料",
            "excerpt": "资料记载，西瓜碑是唐代石碑，具有重要历史价值。",
        }
    ]

    answer = _local_answer("介绍一下西瓜碑的历史背景", artifacts, citations)

    assert "已审核资料补充" in answer
    assert "具有重要历史价值" in answer
