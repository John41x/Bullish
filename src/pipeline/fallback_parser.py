"""Optional local SLM fallback parser (v2, offline only).

Not wired into the hot path by default. Regex failures are logged and skipped
to preserve latency budget (<500 ms total).
"""

from __future__ import annotations

from typing import Optional

from src.models.trade_intent import TradeIntent
from src.pipeline.parser import ParseError


class FallbackParser:
    """Placeholder for future local SLM integration with hard timeout."""

    def __init__(self, timeout_ms: int = 200) -> None:
        self.timeout_ms = timeout_ms

    async def parse(self, text: str) -> Optional[TradeIntent]:
        raise ParseError("Local SLM fallback not configured; skipping trade")
