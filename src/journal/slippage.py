"""Slippage journaling for live pilot analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import get_settings


@dataclass
class SlippageRecord:
    timestamp: str
    symbol: str
    occ_symbol: str
    alert_price: float
    fill_price: Optional[float]
    slippage_pct: Optional[float]
    order_id: str
    status: str
    template_name: Optional[str] = None

    @classmethod
    def from_fill(
        cls,
        *,
        occ_symbol: str,
        symbol: str,
        alert_price: float,
        fill_price: Optional[float],
        order_id: str,
        status: str,
        template_name: Optional[str],
    ) -> SlippageRecord:
        slippage = None
        if fill_price is not None and alert_price:
            slippage = ((fill_price - alert_price) / alert_price) * 100
        return cls(
            timestamp=datetime.utcnow().isoformat(),
            symbol=symbol,
            occ_symbol=occ_symbol,
            alert_price=alert_price,
            fill_price=fill_price,
            slippage_pct=slippage,
            order_id=order_id,
            status=status,
            template_name=template_name,
        )


class SlippageJournal:
    def __init__(self, path: Optional[Path] = None) -> None:
        settings = get_settings()
        self.enabled = settings.slippage_journal.enabled
        self.path = path or Path(settings.slippage_journal.journal_path)
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: SlippageRecord) -> None:
        if not self.enabled:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry)) + "\n")

    def summary(self) -> dict:
        if not self.path.exists():
            return {"count": 0, "median_slippage_pct": None}
        records = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        slippages = [r["slippage_pct"] for r in records if r.get("slippage_pct") is not None]
        slippages.sort()
        median = slippages[len(slippages) // 2] if slippages else None
        return {"count": len(records), "median_slippage_pct": median}
