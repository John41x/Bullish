"""Reliability: heartbeat, reconciliation, watchdog."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from src.broker.base import BrokerAdapter
from src.config import get_settings
from src.logging_setup import get_logger

logger = get_logger("reliability")


class HeartbeatMonitor:
    def __init__(self) -> None:
        self.last_alert_at: float = time.monotonic()
        self.settings = get_settings()

    def record_alert(self) -> None:
        self.last_alert_at = time.monotonic()

    async def run(self) -> None:
        interval = self.settings.reliability.heartbeat_interval_seconds
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - self.last_alert_at
            logger.info("heartbeat", seconds_since_last_alert=round(elapsed, 1))
            if self.settings.telegram_bot_token and elapsed > interval * 3:
                await _telegram_notify(f"Auto Trader: no alerts for {int(elapsed)}s during session")


class PositionReconciler:
    def __init__(self, broker: BrokerAdapter, local_state: dict) -> None:
        self.broker = broker
        self.local_state = local_state
        self.settings = get_settings()

    async def run(self) -> None:
        interval = self.settings.reliability.reconciliation_interval_seconds
        while True:
            await asyncio.sleep(interval)
            try:
                broker_positions = await self.broker.get_open_positions()
                broker_symbols = {p.get("symbol") for p in broker_positions}
                local_symbols = set(self.local_state.keys())
                drift = broker_symbols.symmetric_difference(local_symbols)
                if drift:
                    logger.warning("position_drift", drift=list(drift))
            except Exception as exc:
                logger.error("reconciliation_failed", error=str(exc))


async def _telegram_notify(text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": text})


class Watchdog:
    """Restart supervisor tasks on failure."""

    def __init__(self, delay: Optional[float] = None) -> None:
        self.delay = delay or get_settings().reliability.watchdog_restart_delay_seconds

    async def supervise(self, name: str, coro_factory) -> None:
        while True:
            try:
                await coro_factory()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("watchdog_restart", task=name, error=str(exc))
                await asyncio.sleep(self.delay)
