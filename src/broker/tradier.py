"""Tradier brokerage REST adapter."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from src.broker.base import BrokerAdapter, OrderResult, QuoteResult
from src.config import get_settings
from src.logging_setup import get_logger
from src.models.trade_intent import TradeIntent

logger = get_logger("broker.tradier")


class TradierClient(BrokerAdapter):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.tradier_api_key
        self.account_id = account_id or settings.tradier_account_id
        self.base_url = (base_url or settings.broker.base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def _order_payload(self, intent: TradeIntent, *, preview: bool) -> dict[str, str]:
        payload: dict[str, str] = {
            "class": "option",
            "symbol": intent.symbol,
            "option_symbol": intent.occ_symbol(),
            "side": intent.broker_side,
            "quantity": str(intent.quantity),
            "type": "limit" if intent.limit_price else "market",
            "duration": "day",
            "preview": "true" if preview else "false",
        }
        if intent.limit_price is not None:
            payload["price"] = f"{intent.limit_price:.2f}"
        return payload

    async def preview_order(self, intent: TradeIntent) -> dict[str, Any]:
        path = f"/v1/accounts/{self.account_id}/orders"
        return await self._request(
            "POST",
            path,
            data=self._order_payload(intent, preview=True),
        )

    async def place_order(self, intent: TradeIntent) -> OrderResult:
        path = f"/v1/accounts/{self.account_id}/orders"
        data = await self._request(
            "POST",
            path,
            data=self._order_payload(intent, preview=False),
        )
        order = data.get("order", data)
        order_id = str(order.get("id", ""))
        status = str(order.get("status", "unknown"))
        logger.info("order_placed", order_id=order_id, status=status, occ=intent.occ_symbol())
        return OrderResult(order_id=order_id, status=status, raw=order)

    async def get_order(self, order_id: str) -> dict[str, Any]:
        path = f"/v1/accounts/{self.account_id}/orders/{order_id}"
        data = await self._request("GET", path)
        return data.get("order", data)

    async def poll_fill(self, order_id: str, *, max_attempts: int = 10, delay: float = 0.15) -> OrderResult:
        import asyncio

        for _ in range(max_attempts):
            order = await self.get_order(order_id)
            status = str(order.get("status", "")).lower()
            if status in {"filled", "partially_filled", "rejected", "canceled", "expired"}:
                avg = order.get("avg_fill_price") or order.get("price")
                fill_price = float(avg) if avg else None
                return OrderResult(
                    order_id=order_id,
                    status=status,
                    fill_price=fill_price,
                    raw=order,
                )
            await asyncio.sleep(delay)
        return OrderResult(order_id=order_id, status="timeout", raw={})

    async def get_quote(self, occ_symbol: str) -> QuoteResult:
        data = await self._request("GET", "/v1/markets/quotes", params={"symbols": occ_symbol})
        quotes = data.get("quotes", {}).get("quote", {})
        if isinstance(quotes, list):
            quotes = quotes[0] if quotes else {}
        return QuoteResult(
            symbol=occ_symbol,
            bid=_to_float(quotes.get("bid")),
            ask=_to_float(quotes.get("ask")),
            last=_to_float(quotes.get("last")),
        )

    async def get_open_positions(self) -> list[dict[str, Any]]:
        path = f"/v1/accounts/{self.account_id}/positions"
        data = await self._request("GET", path)
        positions = data.get("positions", {}).get("position", [])
        if isinstance(positions, dict):
            return [positions]
        return positions or []

    async def flatten_all(self) -> list[OrderResult]:
        from src.broker.occ import parse_occ_symbol

        results: list[OrderResult] = []
        for pos in await self.get_open_positions():
            qty = int(float(pos.get("quantity", 0)))
            if qty == 0:
                continue
            occ = str(pos.get("symbol", ""))
            parsed = parse_occ_symbol(occ)
            symbol = str(parsed["symbol"])
            side = "sell_to_close" if qty > 0 else "buy_to_close"
            payload = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": occ,
                "side": side,
                "quantity": str(abs(qty)),
                "type": "market",
                "duration": "day",
                "preview": "false",
            }
            path = f"/v1/accounts/{self.account_id}/orders"
            data = await self._request("POST", path, data=payload)
            order = data.get("order", data)
            results.append(
                OrderResult(
                    order_id=str(order.get("id", "")),
                    status=str(order.get("status", "unknown")),
                    raw=order,
                )
            )
        return results

    async def attach_stop_loss(
        self,
        occ_symbol: str,
        quantity: int,
        stop_price: float,
    ) -> OrderResult:
        """Attach a stop order to close a long option position."""
        symbol = occ_symbol[:6].strip()
        payload = {
            "class": "option",
            "symbol": symbol,
            "option_symbol": occ_symbol,
            "side": "sell_to_close",
            "quantity": str(quantity),
            "type": "stop",
            "stop": f"{stop_price:.2f}",
            "duration": "gtc",
            "preview": "false",
        }
        path = f"/v1/accounts/{self.account_id}/orders"
        data = await self._request("POST", path, data=payload)
        order = data.get("order", data)
        return OrderResult(
            order_id=str(order.get("id", "")),
            status=str(order.get("status", "unknown")),
            raw=order,
        )


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
