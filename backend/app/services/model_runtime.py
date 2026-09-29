"""Runtime state for external chat generation.

Configuration readiness only says that a provider *could* be called. This
module records what actually happened so a broken provider does not add a
retry storm to every visitor request.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatRuntimeSnapshot:
    failure_count: int
    last_error: str | None
    circuit_open: bool
    retry_after_seconds: int


class ChatGenerationRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failure_count = 0
        self._last_error: str | None = None
        self._open_until = 0.0

    def allow(self, *, threshold: int, cooldown_seconds: int) -> bool:
        """Return whether a provider call is currently allowed."""

        now = time.monotonic()
        with self._lock:
            if self._open_until and now < self._open_until:
                return False
            if self._open_until:
                # A cooldown expiry is a single fresh probe, not a permanent
                # ban. Keep the last error for observability until success.
                self._open_until = 0.0
            return True

    def record_failure(self, error_type: str, *, threshold: int, cooldown_seconds: int) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_error = error_type
            if self._failure_count >= max(1, threshold):
                self._open_until = time.monotonic() + max(1, cooldown_seconds)

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._last_error = None
            self._open_until = 0.0

    def snapshot(self) -> ChatRuntimeSnapshot:
        now = time.monotonic()
        with self._lock:
            retry_after = max(0, int(self._open_until - now + 0.999)) if self._open_until else 0
            return ChatRuntimeSnapshot(
                failure_count=self._failure_count,
                last_error=self._last_error,
                circuit_open=bool(self._open_until and now < self._open_until),
                retry_after_seconds=retry_after,
            )


chat_generation_runtime = ChatGenerationRuntime()
