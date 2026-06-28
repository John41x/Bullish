"""Core execution pipeline: parse → risk → broker."""

from __future__ import annotations

import time
from typing import Optional

from src.broker.base import BrokerAdapter
from src.journal.slippage import SlippageJournal, SlippageRecord
from src.logging_setup import get_logger
from src.models.trade_intent import TradeIntent
from src.pipeline.parser import AlertParser, ParseError
from src.risk.guards import RiskEngine

logger = get_logger("executor")


class Executor:
    def __init__(
        self,
        broker: BrokerAdapter,
        parser: Optional[AlertParser] = None,
        risk: Optional[RiskEngine] = None,
    ) -> None:
        self.broker = broker
        self.parser = parser or AlertParser()
        self.risk = risk or RiskEngine()
        self.journal = SlippageJournal()
        self.local_positions: dict[str, int] = {}

    async def process_alert(self, text: str, metadata: Optional[dict] = None) -> None:
        t0 = time.perf_counter()
        meta = metadata or {}
        logger.info("processing_alert", source=meta.get("source"), preview=text[:80])

        try:
            intent = self.parser.parse(text)
        except ParseError as exc:
            logger.warning("parse_failed", error=str(exc))
            return

        quote = None
        if intent.is_entry:
            try:
                quote = await self.broker.get_quote(intent.occ_symbol())
            except Exception as exc:
                logger.warning("quote_failed", error=str(exc))

        decision = self.risk.evaluate(intent, quote=quote)
        if not decision.approved:
            logger.warning("risk_rejected", reason=decision.reason, symbol=intent.symbol)
            return

        try:
            await self.broker.preview_order(intent)
        except Exception as exc:
            logger.warning("preview_failed", error=str(exc))

        order = await self.broker.place_order(intent)
        self.risk.record_fill(intent.quantity)

        fill = await self.broker.poll_fill(order.order_id)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "order_complete",
            order_id=order.order_id,
            status=fill.status,
            fill_price=fill.fill_price,
            latency_ms=round(elapsed_ms, 1),
        )

        if fill.fill_price and intent.limit_price:
            self.journal.record(
                SlippageRecord.from_fill(
                    occ_symbol=intent.occ_symbol(),
                    symbol=intent.symbol,
                    alert_price=intent.limit_price,
                    fill_price=fill.fill_price,
                    order_id=order.order_id,
                    status=fill.status,
                    template_name=intent.template_name,
                )
            )

        if fill.status == "filled" and intent.is_entry:
            await self._attach_protective_stop(intent, fill.fill_price)

        occ = intent.occ_symbol()
        qty_delta = intent.quantity if intent.is_entry else -intent.quantity
        self.local_positions[occ] = self.local_positions.get(occ, 0) + qty_delta

    async def _attach_protective_stop(self, intent: TradeIntent, fill_price: Optional[float]) -> None:
        if not fill_price or not intent.is_entry:
            return
        stop_price = round(fill_price * 0.85, 2)
        try:
            stop = await self.broker.attach_stop_loss(
                intent.occ_symbol(),
                intent.quantity,
                stop_price,
            )
            logger.info("stop_attached", order_id=stop.order_id, stop_price=stop_price)
        except Exception as exc:
            logger.error("stop_attach_failed", error=str(exc))
