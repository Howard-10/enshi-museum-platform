from app.graphs.chat_graph import _local_answer, _primary_artifact, classify_intent


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
