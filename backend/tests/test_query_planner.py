from app.services.query_planner import media_types_for_query, plan_query


def test_planner_keeps_description_and_multiple_media_tasks() -> None:
    plan = plan_query("介绍唐崖土司牌坊，再给我图片和视频")

    assert plan.intent == "mixed"
    assert plan.tasks == ("artifact_description", "media_request")
    assert plan.subject_hint == "唐崖土司牌坊"
    assert plan.media_request.types == ("image", "video")
    assert plan.media_request.required is True


def test_planner_extracts_subject_from_delivery_language() -> None:
    plan = plan_query("请播放西瓜碑音频")

    assert plan.intent == "media"
    assert plan.subject_hint == "西瓜碑"
    assert plan.media_request.types == ("audio",)


def test_planner_resolves_media_follow_up_from_active_artifact() -> None:
    plan = plan_query(
        "它的音频",
        history=[
            {
                "role": "assistant",
                "content": "介绍完成",
                "metadata": {
                    "active_artifact_id": "artifact-1",
                    "active_artifact_name": "西瓜碑",
                },
            }
        ],
    )

    assert plan.intent == "media"
    assert plan.subject_hint == "西瓜碑"
    assert plan.active_artifact_id == "artifact-1"
    assert plan.media_request.types == ("audio",)


def test_generic_media_request_needs_a_subject() -> None:
    plan = plan_query("给我看看相关媒体")

    assert plan.needs_clarification is True
    assert media_types_for_query("相关媒体") == ("image", "audio", "video")
