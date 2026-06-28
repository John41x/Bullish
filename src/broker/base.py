"""Broker adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from src.models.trade_intent import TradeIntent


@dataclass
class OrderResult:
    order_id: str
    status: str
    fill_price: Optional[float] = None
    raw: Optional[dict[str, Any]] = None


@dataclass
class QuoteResult:
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]

    @property
    def mid(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.last


class BrokerAdapter(ABC):
    @abstractmethod
    async def preview_order(self, intent: TradeIntent) -> dict[str, Any]:
        ...

    @abstractmethod
    async def place_order(self, intent: TradeIntent) -> OrderResult:
        ...

    @abstractmethod
    async def get_quote(self, occ_symbol: str) -> QuoteResult:
        ...

    @abstractmethod
    async def get_open_positions(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def flatten_all(self) -> list[OrderResult]:
        ...

    @abstractmethod
    async def attach_stop_loss(
        self,
        occ_symbol: str,
        quantity: int,
        stop_price: float,
    ) -> OrderResult:
        ...
