"""Windows UserNotificationListener extractor (run inside Windows VM).

Requires optional dependency: pip install -e ".[windows]"

Usage:
    python -m src.extractor.win_listener --forward-url http://192.168.1.10:8765/alert
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx

from src.logging_setup import get_logger, setup_logging

logger = get_logger("extractor.win_listener")

DISCORD_APPS = {"Discord", "Discord Canary", "Discord PTB"}
BROWSER_APPS = {"Microsoft Edge", "Google Chrome", "Brave", "Firefox"}


def _extract_text_from_notification(notif: Any) -> tuple[str, str, str]:
    """Extract title, body, app name from a Windows toast notification."""
    app_name = notif.app_info.display_name if notif.app_info else ""
    title = ""
    body = ""
    try:
        bindings = notif.notification.visual.bindings
        for binding in bindings:
            for element in binding.get_text_elements():
                text = element.text or ""
                if not title:
                    title = text
                elif not body:
                    body = text
                else:
                    body = f"{body} {text}"
    except Exception:
        pass
    combined = f"{title} {body}".strip()
    return app_name, title, combined


async def _forward_alert(
    *,
    forward_url: str,
    secret: str,
    text: str,
    app_name: str,
    title: str,
) -> None:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Alert-Secret"] = secret
    payload = {
        "text": text,
        "app_name": app_name,
        "title": title,
        "source": "win_listener",
        "timestamp": time.time(),
    }
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(forward_url, json=payload, headers=headers)
        response.raise_for_status()
    logger.info("alert_forwarded", app=app_name, preview=text[:80])


async def monitor_loop(*, forward_url: str, secret: str, poll_interval: float) -> None:
    try:
        from winrt.windows.ui.notifications import NotificationKinds
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
    except ImportError as exc:
        logger.error("winrt_not_installed", hint='pip install -e ".[windows]"')
        raise SystemExit(1) from exc

    listener = UserNotificationListener.get_current()
    status = await listener.request_access_async()
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        logger.error("notification_access_denied", status=str(status))
        raise SystemExit(1)

    seen_ids: set[int] = set()
    logger.info("win_listener_started", forward_url=forward_url)

    while True:
        notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
        for notif in notifications:
            notif_id = id(notif)
            if notif_id in seen_ids:
                continue
            app_name, title, text = _extract_text_from_notification(notif)
            if not text:
                continue
            is_discord = any(name in app_name for name in DISCORD_APPS)
            is_browser = any(name in app_name for name in BROWSER_APPS)
            if not (is_discord or is_browser):
                continue
            seen_ids.add(notif_id)
            try:
                await _forward_alert(
                    forward_url=forward_url,
                    secret=secret,
                    text=text,
                    app_name=app_name,
                    title=title,
                )
            except Exception as exc:
                logger.error("forward_failed", error=str(exc))
        if len(seen_ids) > 1000:
            seen_ids.clear()
        await asyncio.sleep(poll_interval)


async def _amain() -> None:
    parser = argparse.ArgumentParser(description="Windows notification listener for Auto Trader")
    parser.add_argument(
        "--forward-url",
        required=True,
        help="Mac executor alert bridge URL, e.g. http://192.168.1.10:8765/alert",
    )
    parser.add_argument("--secret", default="", help="X-Alert-Secret header value")
    parser.add_argument("--poll-interval", type=float, default=0.25, help="Poll interval seconds")
    args = parser.parse_args()
    setup_logging()
    await monitor_loop(
        forward_url=args.forward_url,
        secret=args.secret,
        poll_interval=args.poll_interval,
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
