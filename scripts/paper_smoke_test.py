#!/usr/bin/env python3
"""Smoke test Tradier sandbox connectivity (requires .env credentials)."""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.broker.tradier import TradierClient
from src.config import get_settings
from src.models.trade_intent import OptionRight, OrderAction, TradeIntent


async def main() -> None:
    load_dotenv()
    settings = get_settings()
    if not settings.tradier_api_key:
        print("SKIP: TRADIER_API_KEY not set")
        return

    broker = TradierClient()
    t0 = time.perf_counter()

    intent = TradeIntent(
        action=OrderAction.BUY_TO_OPEN,
        symbol="SPY",
        strike=450,
        right=OptionRight.CALL,
        expiry=date(2025, 10, 17),
        limit_price=0.01,
        quantity=1,
        raw_text="smoke-test",
    )

    try:
        preview = await broker.preview_order(intent)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"Preview OK in {elapsed:.0f}ms")
        print(preview)
    except Exception as exc:
        print(f"Preview failed (expected if sandbox lacks symbol): {exc}")
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
