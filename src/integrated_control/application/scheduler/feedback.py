"""Continuous-failure tolerance for observations, never for replaying commands."""
from copy import deepcopy
from dataclasses import dataclass, replace
import math
from threading import RLock
import time
from typing import Callable

from integrated_control.domain.models import DeviceState


@dataclass(frozen=True)
class FeedbackPolicy:
    """Configure grace periods and cached-feedback age limits for device observations."""
    continuous_failure_timeout_s: float = 3.0
    max_cached_age_s: float = 3.0

    def __post_init__(self) -> None:
        """Validate and normalize the initialized feedback policy fields."""
        if not math.isfinite(self.continuous_failure_timeout_s) or self.continuous_failure_timeout_s <= 0:
            raise ValueError("Continuous failure timeout must be positive and finite")
        if not math.isfinite(self.max_cached_age_s) or self.max_cached_age_s < 0:
            raise ValueError("Cache age must be nonnegative and finite")


class FeedbackTolerance:
    """Track communication gaps and decide when cached device feedback becomes invalid."""
    def __init__(self, policy: FeedbackPolicy | None = None, *,
                 clock: Callable[[], float] = time.monotonic) -> None:
        """Initialize feedback tolerance dependencies and internal state."""
        self.policy = policy or FeedbackPolicy()
        self._clock = clock
        self._last: DeviceState | None = None
        self._failure_started: float | None = None
        self._lock = RLock()

    def observe(self, state: DeviceState) -> DeviceState:
        """Publish received observations; omitted values do not invalidate them.

        Call only when a real observation is acquired, not whenever get_state()
        returns cached driver data. Explicit faults bypass communication grace."""
        with self._lock:
            now = self._clock()
            if self._last is not None and self._last.device_id != state.device_id:
                raise ValueError("One tolerance monitor per device")
            observed = replace(deepcopy(state), updated_at=now)
            self._last = observed
            self._failure_started = None
            return deepcopy(observed)

    def communication_failed(self, device_id: str, message: str) -> DeviceState:
        """Record a communication gap and return cached or invalid state according to feedback tolerance."""
        with self._lock:
            now = self._clock()
            if self._last is not None and self._last.device_id != device_id:
                raise ValueError("One tolerance monitor per device")
            if self._failure_started is None:
                self._failure_started = now
            cached = self._last
            if (cached is not None and cached.valid and cached.updated_at is not None
                    and now - self._failure_started < self.policy.continuous_failure_timeout_s
                    and now - cached.updated_at <= self.policy.max_cached_age_s):
                # Keep original timestamp: a failed poll is not a fresh reading.
                return deepcopy(cached)
            if cached is None:
                return DeviceState(device_id, "OFFLINE", "UNKNOWN", fault=message, valid=False)
            return replace(deepcopy(cached), valid=False,
                           fault=cached.fault or f"Feedback unavailable: {message}")
