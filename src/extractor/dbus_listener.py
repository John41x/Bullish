"""Linux D-Bus notification listener (run inside Linux VM).

Requires: pip install -e ".[linux]"

Usage:
    python -m src.extractor.dbus_listener \
      --forward-url http://192.168.64.1:8765/alert \
      --secret your-bridge-secret
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx

from src.logging_setup import get_logger, setup_logging

logger = get_logger("extractor.dbus_listener")

DISCORD_APP_NAMES = {"discord", "discord-canary", "discord-ptb", "discord-development"}
BROWSER_APP_NAMES = {"firefox", "google-chrome", "chromium", "chromium-browser", "brave-browser"}

NOTIFY_MATCH = (
    "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
)


def _is_target_app(app_name: str) -> bool:
    normalized = app_name.lower().replace(" ", "-")
    if normalized in DISCORD_APP_NAMES or "discord" in normalized:
        return True
    return normalized in BROWSER_APP_NAMES


async def monitor_dbus(*, forward_url: str, secret: str) -> None:
    try:
        from dbus_next.aio import MessageBus
        from dbus_next.constants import BusType, MessageType
    except ImportError as exc:
        logger.error("dbus_next_not_installed", hint='pip install -e ".[linux]"')
        raise SystemExit(1) from exc

    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    await bus.call(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "AddMatch",
        NOTIFY_MATCH,
    )

    seen: dict[str, float] = {}
    dedup_ttl = 30.0

    def _make_handler():
        async def handler(message) -> None:
            if message.message_type != MessageType.METHOD_CALL:
                return
            if message.interface != "org.freedesktop.Notifications":
                return
            if message.member != "Notify":
                return
            if len(message.body) < 4:
                return

            app_name = str(message.body[0] or "")
            summary = str(message.body[2] or "")
            body = str(message.body[3] or "")
            text = f"{summary} {body}".strip()
            if not text or not _is_target_app(app_name):
                return

            now = time.monotonic()
            key = f"{app_name}:{text.lower()}"
            if key in seen and now - seen[key] < dedup_ttl:
                return
            seen[key] = now

            try:
                await _forward(forward_url, secret, text, app_name, summary)
            except Exception as exc:
                logger.error("forward_failed", error=str(exc))

        return handler

    bus.add_message_handler(_make_handler())
    logger.info("dbus_listener_started", forward_url=forward_url, match=NOTIFY_MATCH)
    await asyncio.Future()


async def _forward(forward_url: str, secret: str, text: str, app_name: str, title: str) -> None:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Alert-Secret"] = secret
    payload = {"text": text, "app_name": app_name, "title": title, "source": "dbus_listener"}
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(forward_url, json=payload, headers=headers)
        response.raise_for_status()
    logger.info("alert_forwarded", app=app_name, preview=text[:80])


def main() -> None:
    parser = argparse.ArgumentParser(description="Linux D-Bus notification forwarder for Auto Trader")
    parser.add_argument(
        "--forward-url",
        required=True,
        help="Mac executor URL, e.g. http://192.168.64.1:8765/alert",
    )
    parser.add_argument("--secret", default="", help="Must match ALERT_BRIDGE_SECRET in Mac .env")
    args = parser.parse_args()
    setup_logging()
    asyncio.run(monitor_dbus(forward_url=args.forward_url, secret=args.secret))


if __name__ == "__main__":
    main()
