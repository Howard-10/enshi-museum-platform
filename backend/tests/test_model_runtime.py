from app.services.model_runtime import ChatGenerationRuntime


def test_runtime_opens_after_threshold_and_reports_retry_window() -> None:
    runtime = ChatGenerationRuntime()

    assert runtime.allow(threshold=2, cooldown_seconds=60)
    runtime.record_failure("APIConnectionError", threshold=2, cooldown_seconds=60)
    assert runtime.allow(threshold=2, cooldown_seconds=60)
    runtime.record_failure("APIConnectionError", threshold=2, cooldown_seconds=60)

    snapshot = runtime.snapshot()
    assert snapshot.circuit_open is True
    assert snapshot.failure_count == 2
    assert snapshot.last_error == "APIConnectionError"
    assert snapshot.retry_after_seconds >= 1
    assert runtime.allow(threshold=2, cooldown_seconds=60) is False


def test_runtime_success_resets_degraded_state() -> None:
    runtime = ChatGenerationRuntime()
    runtime.record_failure("TimeoutError", threshold=3, cooldown_seconds=60)
    runtime.record_success()

    snapshot = runtime.snapshot()
    assert snapshot.failure_count == 0
    assert snapshot.last_error is None
    assert snapshot.circuit_open is False
