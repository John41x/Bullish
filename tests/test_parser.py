"""Parser and risk unit tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.broker.base import QuoteResult
from src.models.trade_intent import OptionRight, OrderAction
from src.pipeline.parser import AlertParser, ParseError
from src.risk.guards import RiskEngine

FIXTURES = Path(__file__).parent / "fixtures" / "alerts.json"


@pytest.fixture
def parser() -> AlertParser:
    return AlertParser()


def test_parse_standard_bto(parser: AlertParser) -> None:
    intent = parser.parse("BTO SPY 450C 10/18 @ 2.50")
    assert intent.action == OrderAction.BUY_TO_OPEN
    assert intent.symbol == "SPY"
    assert intent.strike == 450.0
    assert intent.right == OptionRight.CALL
    assert intent.limit_price == 2.50
    assert intent.template_name == "standard_bto"


def test_parse_spaced_right(parser: AlertParser) -> None:
    intent = parser.parse("BTO SPY 450 C 10/18 @ 2.50")
    assert intent.strike == 450.0
    assert intent.template_name == "spaced_alert"


def test_parse_discord_prefix(parser: AlertParser) -> None:
    intent = parser.parse("Discord: trader-vip BTO AAPL 220C 12/20 @ 3.10")
    assert intent.symbol == "AAPL"
    assert intent.template_name == "discord_notification"


def test_parse_exit(parser: AlertParser) -> None:
    intent = parser.parse("STC SPY 450C 10/18 @ 3.00")
    assert intent.action == OrderAction.STC
    assert intent.is_exit


def test_parse_with_quantity(parser: AlertParser) -> None:
    intent = parser.parse("BTO QQQ 380P 11/15 @ 1.25 x 2")
    assert intent.quantity == 2
    assert intent.right == OptionRight.PUT


def test_parse_failure(parser: AlertParser) -> None:
    with pytest.raises(ParseError):
        parser.parse("Just chatting about markets today")


def test_fixture_replay_success_rate(parser: AlertParser) -> None:
    alerts = json.loads(FIXTURES.read_text())
    parseable = [a for a in alerts if a.get("expect") == "parse"]
    successes = sum(1 for a in parseable if _try_parse(parser, a["text"]))
    rate = successes / len(parseable)
    assert rate >= 0.95, f"Parse rate {rate:.1%} below 95%"


def _try_parse(parser: AlertParser, text: str) -> bool:
    try:
        parser.parse(text)
        return True
    except ParseError:
        return False


def test_occ_symbol() -> None:
    parser = AlertParser()
    intent = parser.parse("BTO SPY 450C 10/18 @ 2.50")
    occ = intent.occ_symbol()
    assert occ.startswith("SPY")
    assert "C" in occ


def test_slippage_guard_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.models.trade_intent import TradeIntent
    from src.risk import guards

    monkeypatch.setattr(guards, "_within_trading_hours", lambda *args, **kwargs: True)

    engine = RiskEngine()
    engine.halted = False
    intent = TradeIntent(
        action=OrderAction.BUY_TO_OPEN,
        symbol="SPY",
        strike=450,
        right=OptionRight.CALL,
        expiry=date(2025, 10, 18),
        limit_price=2.50,
        raw_text="unique-alert-1",
    )
    quote = QuoteResult(symbol="x", bid=2.70, ask=2.80, last=2.75)
    decision = engine.evaluate(intent, quote=quote)
    assert not decision.approved
    assert "slippage" in decision.reason


def test_duplicate_suppression(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.models.trade_intent import TradeIntent
    from src.risk import guards

    monkeypatch.setattr(guards, "_within_trading_hours", lambda *args, **kwargs: True)

    engine = RiskEngine()
    intent = TradeIntent(
        action=OrderAction.BUY_TO_OPEN,
        symbol="SPY",
        strike=450,
        right=OptionRight.CALL,
        expiry=date(2025, 10, 18),
        limit_price=2.50,
        raw_text="duplicate-test-alert",
    )
    first = engine.evaluate(intent)
    second = engine.evaluate(intent)
    assert first.approved
    assert not second.approved
    assert second.reason == "duplicate_alert"


@pytest.mark.asyncio
async def test_executor_parse_only_no_broker_call() -> None:
    from src.executor import Executor

    broker = MagicMock()
    broker.get_quote = AsyncMock(return_value=QuoteResult("x", 2.4, 2.5, 2.45))
    broker.preview_order = AsyncMock()
    broker.place_order = AsyncMock()
    broker.poll_fill = AsyncMock()
    executor = Executor(broker=broker)
    await executor.process_alert("not a valid alert")
    broker.place_order.assert_not_called()
