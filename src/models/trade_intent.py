"""Normalized trade intent parsed from alert text."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class OrderAction(str, Enum):
    BUY_TO_OPEN = "BTO"
    SELL_TO_OPEN = "STO"
    BUY_TO_CLOSE = "BTC"
    STC = "STC"


class OptionRight(str, Enum):
    CALL = "C"
    PUT = "P"


class TradeIntent(BaseModel):
    """Structured execution payload derived from a VIP alert."""

    action: OrderAction
    symbol: str = Field(min_length=1, max_length=5)
    strike: float = Field(gt=0)
    right: OptionRight
    expiry: date
    limit_price: Optional[float] = Field(default=None, gt=0)
    quantity: int = Field(default=1, ge=1)
    raw_text: str = ""
    template_name: Optional[str] = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()

    @property
    def is_entry(self) -> bool:
        return self.action in (OrderAction.BUY_TO_OPEN, OrderAction.SELL_TO_OPEN)

    @property
    def is_exit(self) -> bool:
        return self.action in (OrderAction.BUY_TO_CLOSE, OrderAction.STC)

    @property
    def broker_side(self) -> str:
        mapping = {
            OrderAction.BUY_TO_OPEN: "buy_to_open",
            OrderAction.SELL_TO_OPEN: "sell_to_open",
            OrderAction.BUY_TO_CLOSE: "buy_to_close",
            OrderAction.STC: "sell_to_close",
        }
        return mapping[self.action]

    def occ_symbol(self) -> str:
        """Build OCC option symbol (Tradier format)."""
        from src.broker.occ import build_occ_symbol

        return build_occ_symbol(
            symbol=self.symbol,
            expiry=self.expiry,
            right=self.right.value,
            strike=self.strike,
        )
