from __future__ import annotations

import threading
import time
from typing import Generic, TypeVar


T = TypeVar("T")


class MemoryCache(Generic[T]):
    """Very small in-memory cache with a single TTL value."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        """Return the cached value if it still exists and is fresh."""
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None

            expires_at, value = item
            if expires_at <= time.time():
                self._items.pop(key, None)
                return None

            return value

    def set(self, key: str, value: T) -> None:
        """Store a value until the configured TTL expires."""
        with self._lock:
            expires_at = time.time() + self.ttl_seconds
            self._items[key] = (expires_at, value)
