"""Duplicate alert suppression."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class DedupCache:
    ttl_seconds: int = 30
    _seen: dict[str, float] = field(default_factory=dict)

    def _key(self, text: str) -> str:
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def is_duplicate(self, text: str) -> bool:
        now = time.monotonic()
        self._purge(now)
        key = self._key(text)
        if key in self._seen:
            return True
        self._seen[key] = now
        return False

    def _purge(self, now: float) -> None:
        expired = [k for k, ts in self._seen.items() if now - ts > self.ttl_seconds]
        for key in expired:
            del self._seen[key]
