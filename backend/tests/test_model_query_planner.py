import pytest

from app.core.config import Settings
from app.services.model_query_planner import enrich_query_plan
from app.services.query_planner import plan_query


@pytest.mark.asyncio
async def test_model_query_planner_is_opt_in_and_does_not_call_provider_by_default() -> None:
    plan = plan_query("介绍一件文物")
    updated, reason = await enrich_query_plan(
        plan,
        config=Settings(query_planner_model_enabled=False),
    )

    assert updated == plan
    assert reason is None
