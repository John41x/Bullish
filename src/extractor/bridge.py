"""HTTP alert bridge: receives notifications from Windows VM listener."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Optional

from aiohttp import web

from src.config import get_settings
from src.logging_setup import get_logger

logger = get_logger("extractor.bridge")

AlertHandler = Callable[[str, dict], asyncio.Future | None]


@dataclass
class AlertBridge:
    host: str = ""
    port: int = 8765
    secret: str = ""
    _queue: asyncio.Queue[tuple[str, dict]] = field(default_factory=asyncio.Queue)
    _app: Optional[web.Application] = None
    _runner: Optional[web.AppRunner] = None

    def __post_init__(self) -> None:
        settings = get_settings()
        self.host = self.host or settings.alert_bridge.host
        self.port = self.port or settings.alert_bridge.port
        self.secret = self.secret or settings.alert_bridge_secret

    async def _handle_alert(self, request: web.Request) -> web.Response:
        if self.secret:
            auth = request.headers.get("X-Alert-Secret", "")
            if auth != self.secret:
                return web.Response(status=401, text="unauthorized")

        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {"text": await request.text()}

        text = body.get("text") or body.get("message") or ""
        metadata = {
            "app_name": body.get("app_name", ""),
            "title": body.get("title", ""),
            "source": body.get("source", "bridge"),
        }
        if not text.strip():
            return web.Response(status=400, text="missing text")

        await self._queue.put((text, metadata))
        logger.info("alert_received", app=metadata.get("app_name"), preview=text[:80])
        return web.Response(status=202, text="accepted")

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "queue_size": self._queue.qsize()})

    async def start(self) -> None:
        self._app = web.Application()
        self._app.router.add_post("/alert", self._handle_alert)
        self._app.router.add_get("/health", self._handle_health)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info("alert_bridge_started", host=self.host, port=self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def alerts(self) -> AsyncIterator[tuple[str, dict]]:
        while True:
            yield await self._queue.get()
