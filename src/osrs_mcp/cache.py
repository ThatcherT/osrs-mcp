import time
from typing import Any


class TTLCache:
    """Simple TTL dictionary cache."""

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        if key in self._store:
            expires, value = self._store[key]
            if time.time() < expires:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (expires, value)

    def clear(self) -> None:
        self._store.clear()


cache = TTLCache(default_ttl=300)
