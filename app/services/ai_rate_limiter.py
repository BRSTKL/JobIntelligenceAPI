from __future__ import annotations

import threading
import time
from collections.abc import Callable

from app.core.exceptions import RateLimitExceededError


class AIRateLimiter:
    """A tiny fixed-window rate limiter keyed by API key."""

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.time_provider = time_provider or time.time
        self._items: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def enforce(self, key: str) -> None:
        """Raise a rate-limit error when the key exceeds the configured allowance."""
        now = float(self.time_provider())
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = [timestamp for timestamp in self._items.get(key, []) if timestamp > cutoff]
            if len(timestamps) >= self.limit:
                raise RateLimitExceededError(
                    message="AI endpoint rate limit exceeded.",
                    details=[f"Limit: {self.limit} requests per {self.window_seconds} seconds."],
                )

            timestamps.append(now)
            self._items[key] = timestamps
