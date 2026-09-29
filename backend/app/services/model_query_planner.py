"""Optional model-assisted query planning.

The model receives no catalog evidence and cannot approve facts. Its only job
is to extract a subject/task shape when deterministic planning is ambiguous;
the regular retrieval and evidence gate remain authoritative.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import Settings, settings
from app.services.model_clients import create_chat_client
from app.services.model_readiness import get_model_readiness
from app.services.model_runtime import chat_generation_runtime
from app.services.query_planner import QueryPlan


class ModelQueryPlan(BaseModel):
    subject_hint: str | None = Field(default=None, max_length=80)
    tasks: list[Literal["artifact_description", "media_request"]] = Field(default_factory=list)
    media_types: list[Literal["image", "audio", "video"]] = Field(default_factory=list)


async def enrich_query_plan(
    plan: QueryPlan,
    *,
    history: list[dict[str, Any]] | None = None,
    config: Settings = settings,
) -> tuple[QueryPlan, str | None]:
    """Use a model only for ambiguous extraction, never for evidence."""

    if not config.query_planner_model_enabled or plan.subject_hint or not get_model_readiness(config).chat_generation_enabled:
        return plan, None
    if not chat_generation_runtime.allow(
        threshold=config.chat_failure_threshold,
        cooldown_seconds=config.chat_circuit_cooldown_seconds,
    ):
        return plan, "query_planner_circuit_open"
    prompt = (
        "你只负责解析游客问题，不回答事实。输出 JSON：subject_hint（文物或资料名称，无法确定则 null）、"
        "tasks（artifact_description 和/或 media_request）、media_types（image/audio/video）。"
        "不要编造名称，不要把历史事实写进输出。\n"
        f"问题：{plan.original_query}\n"
        f"最近上下文：{history or []}"
    )
    try:
        structured = create_chat_client(config).with_structured_output(ModelQueryPlan)
        result = await structured.ainvoke(prompt)
        parsed = result if isinstance(result, ModelQueryPlan) else ModelQueryPlan.model_validate(result)
    except Exception as error:  # noqa: BLE001 -- planner must degrade to deterministic parsing.
        chat_generation_runtime.record_failure(
            type(error).__name__,
            threshold=config.chat_failure_threshold,
            cooldown_seconds=config.chat_circuit_cooldown_seconds,
        )
        return plan, f"query_planner_error:{type(error).__name__}"
    chat_generation_runtime.record_success()
    subject = (parsed.subject_hint or "").strip() or plan.subject_hint
    media_types = tuple(
        dict.fromkeys((*plan.media_request.types, *parsed.media_types))
    )
    parsed_tasks = [
        task
        for task in parsed.tasks
        if task != "media_request" or plan.media_request.required
    ]
    tasks = tuple(dict.fromkeys((*plan.tasks, *parsed_tasks)))
    if not tasks:
        tasks = plan.tasks
    intent = "mixed" if len(tasks) > 1 else "media" if tasks == ("media_request",) else "knowledge"
    from dataclasses import replace

    updated = replace(
        plan,
        retrieval_query=subject if plan.media_request.required and subject else plan.retrieval_query,
        intent=intent,
        tasks=tasks,
        subject_hint=subject,
        media_request=replace(plan.media_request, required=plan.media_request.required, types=media_types),
        needs_clarification=plan.media_request.required and not subject and not plan.active_artifact_name,
    )
    return updated, "query_planner_model_used"
