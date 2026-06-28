"""Integration tests for alert bridge."""

from __future__ import annotations

import asyncio

import pytest
from aiohttp import ClientSession

from src.extractor.bridge import AlertBridge


@pytest.mark.asyncio
async def test_alert_bridge_accepts_post() -> None:
    bridge = AlertBridge(host="127.0.0.1", port=18765, secret="test-secret")
    await bridge.start()

    async def consume_one():
        text, meta = await asyncio.wait_for(bridge.alerts().__anext__(), timeout=2)
        return text, meta

    consumer = asyncio.create_task(consume_one())
    await asyncio.sleep(0.1)

    async with ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:18765/alert",
            json={"text": "BTO SPY 450C 10/18 @ 2.50", "app_name": "Discord"},
            headers={"X-Alert-Secret": "test-secret"},
        ) as resp:
            assert resp.status == 202

    text, meta = await consumer
    assert "BTO SPY" in text
    assert meta["app_name"] == "Discord"
    await bridge.stop()
