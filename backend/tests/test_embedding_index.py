from app.services.embedding_index import IndexPlan, text_sha256


def test_embedding_text_hash_is_stable_and_sensitive_to_content() -> None:
    assert text_sha256("museum source") == text_sha256("museum source")
    assert text_sha256("museum source") != text_sha256("museum source changed")


def test_index_plan_exposes_a_safe_dry_run_summary() -> None:
    plan = IndexPlan(
        eligible_chunks=20,
        stale_chunks=17,
        already_current_chunks=3,
        model="embedding-test",
        dimensions=1024,
    )

    assert plan.eligible_chunks == plan.stale_chunks + plan.already_current_chunks
