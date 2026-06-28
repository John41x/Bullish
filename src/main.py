"""Auto Trader supervisor entrypoint."""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from src.broker.tradier import TradierClient
from src.config import get_settings
from src.executor import Executor
from src.extractor.bridge import AlertBridge
from src.logging_setup import get_logger, setup_logging
from src.reliability import HeartbeatMonitor, PositionReconciler, Watchdog
from src.risk.guards import RiskEngine
from src.risk.kill_switch import KillSwitch

logger = get_logger("main")


async def run_supervisor() -> None:
    load_dotenv()
    setup_logging()
    settings = get_settings()

    if not settings.tradier_api_key or not settings.tradier_account_id:
        logger.error("missing_tradier_credentials", hint="Set TRADIER_API_KEY and TRADIER_ACCOUNT_ID in .env")
        sys.exit(1)

    broker = TradierClient()
    risk = RiskEngine()
    executor = Executor(broker=broker, risk=risk)
    bridge = AlertBridge()
    heartbeat = HeartbeatMonitor()
    reconciler = PositionReconciler(broker, executor.local_positions)
    watchdog = Watchdog()

    kill_switch = KillSwitch(broker, on_halt=risk.halt, on_resume=risk.resume)

    await bridge.start()

    async def alert_loop() -> None:
        async for text, metadata in bridge.alerts():
            heartbeat.record_alert()
            await executor.process_alert(text, metadata)

    tasks = [
        asyncio.create_task(watchdog.supervise("alert_loop", alert_loop)),
        asyncio.create_task(watchdog.supervise("kill_switch", kill_switch.start_polling)),
        asyncio.create_task(watchdog.supervise("heartbeat", heartbeat.run)),
        asyncio.create_task(watchdog.supervise("reconciliation", reconciler.run)),
    ]

    mode = "live_pilot" if settings.live_pilot.enabled else "sandbox"
    logger.info(
        "auto_trader_started",
        mode=mode,
        broker=settings.broker.base_url,
        bridge_port=settings.alert_bridge.port,
    )

    try:
        await asyncio.gather(*tasks)
    finally:
        kill_switch.stop()
        await bridge.stop()
        await broker.close()


def main() -> None:
    asyncio.run(run_supervisor())


if __name__ == "__main__":
    main()
