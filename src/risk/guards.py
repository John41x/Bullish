"""Risk management guards."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from src.broker.base import QuoteResult
from src.config import get_settings
from src.models.trade_intent import TradeIntent
from src.pipeline.dedup import DedupCache


@dataclass
class RiskDecision:
    approved: bool
    reason: str = ""


@dataclass
class RiskEngine:
    dedup: DedupCache = field(default_factory=lambda: DedupCache(
        ttl_seconds=get_settings().risk.duplicate_suppression_seconds
    ))
    halted: bool = False
    daily_contracts: int = 0
    _daily_date: Optional[str] = None

    def reset_daily_if_needed(self) -> None:
        today = datetime.now().date().isoformat()
        if self._daily_date != today:
            self._daily_date = today
            self.daily_contracts = 0

    def halt(self) -> None:
        self.halted = True

    def resume(self) -> None:
        self.halted = False

    def evaluate(
        self,
        intent: TradeIntent,
        *,
        quote: Optional[QuoteResult] = None,
    ) -> RiskDecision:
        settings = get_settings()
        risk = settings.risk

        if self.halted:
            return RiskDecision(False, "kill_switch_active")

        if self.dedup.is_duplicate(intent.raw_text):
            return RiskDecision(False, "duplicate_alert")

        self.reset_daily_if_needed()
        if intent.quantity > risk.max_contracts_per_trade:
            return RiskDecision(False, "exceeds_max_contracts_per_trade")

        if self.daily_contracts + intent.quantity > risk.max_contracts_per_day:
            return RiskDecision(False, "exceeds_max_contracts_per_day")

        if settings.live_pilot.enabled and intent.quantity > settings.live_pilot.max_contracts:
            return RiskDecision(False, "live_pilot_contract_cap")

        if not _within_trading_hours(risk.trading_hours.start, risk.trading_hours.end, risk.trading_hours.timezone):
            return RiskDecision(False, "outside_trading_hours")

        if risk.require_limit_orders and intent.limit_price is None and intent.is_entry:
            return RiskDecision(False, "limit_price_required_for_entry")

        if intent.limit_price and intent.quantity * intent.limit_price * 100 > risk.max_notional_usd:
            return RiskDecision(False, "exceeds_max_notional")

        if quote and intent.limit_price and intent.is_entry:
            ask = quote.ask or quote.last
            if ask is not None:
                slippage_pct = ((ask - intent.limit_price) / intent.limit_price) * 100
                if slippage_pct > risk.max_slippage_pct:
                    return RiskDecision(
                        False,
                        f"slippage_exceeded:{slippage_pct:.2f}%>{risk.max_slippage_pct}%",
                    )

        return RiskDecision(True, "approved")

    def record_fill(self, quantity: int) -> None:
        self.reset_daily_if_needed()
        self.daily_contracts += quantity


def _within_trading_hours(start: str, end: str, tz_name: str) -> bool:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    start_h, start_m = map(int, start.split(":"))
    end_h, end_m = map(int, end.split(":"))
    start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return start_dt <= now <= end_dt
