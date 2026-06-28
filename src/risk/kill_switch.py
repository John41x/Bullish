"""Telegram-based kill switch."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import httpx

from src.broker.base import BrokerAdapter
from src.config import get_settings
from src.logging_setup import get_logger

logger = get_logger("risk.kill_switch")


class KillSwitch:
    def __init__(
        self,
        broker: BrokerAdapter,
        *,
        on_halt: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
    ) -> None:
        self.broker = broker
        self.on_halt = on_halt
        self.on_resume = on_resume
        self.settings = get_settings()
        self._offset = 0
        self._running = False

    @property
    def enabled(self) -> bool:
        ks = self.settings.kill_switch
        return ks.enabled and bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def start_polling(self) -> None:
        if not self.enabled:
            logger.info("kill_switch_disabled")
            return
        self._running = True
        logger.info("kill_switch_polling_started")
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("kill_switch_poll_error", error=str(exc))
            await asyncio.sleep(2)

    def stop(self) -> None:
        self._running = False

    async def _poll_once(self) -> None:
        token = self.settings.telegram_bot_token
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"offset": self._offset, "timeout": 5})
            response.raise_for_status()
            data = response.json()
        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            message = update.get("message", {})
            text = (message.get("text") or "").strip().lower()
            chat_id = str(message.get("chat", {}).get("id", ""))
            if chat_id != self.settings.telegram_chat_id:
                continue
            if text in {"/halt", "/stop", "halt", "stop"}:
                await self.execute_halt()
            elif text in {"/resume", "resume"}:
                if self.on_resume:
                    self.on_resume()
                await self._notify("Auto Trader RESUMED.")

    async def execute_halt(self) -> None:
        logger.warning("kill_switch_triggered")
        if self.on_halt:
            self.on_halt()
        if self.settings.kill_switch.flatten_on_halt:
            results = await self.broker.flatten_all()
            logger.warning("kill_switch_flattened", count=len(results))
        await self._notify("Auto Trader HALTED. Positions flattened.")

    async def _notify(self, text: str) -> None:
        if not self.enabled:
            return
        token = self.settings.telegram_bot_token
        chat_id = self.settings.telegram_chat_id
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": text})
