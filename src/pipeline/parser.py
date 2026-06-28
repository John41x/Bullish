"""Regex-first alert parser."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

from src.config import ROOT, get_settings
from src.models.trade_intent import OptionRight, OrderAction, TradeIntent


class ParseError(Exception):
    """Alert text could not be parsed into a TradeIntent."""


class AlertParser:
    def __init__(self, templates_path: Optional[Path] = None) -> None:
        settings = get_settings()
        path = templates_path or (ROOT / settings.parser.templates_file)
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        self.templates: list[tuple[str, re.Pattern[str], dict]] = []
        for item in data.get("templates", []):
            name = item["name"]
            # YAML folded strings may insert newlines; remove them only (keep intentional spaces).
            pattern_str = item["pattern"].replace("\n", "")
            pattern = re.compile(pattern_str)
            meta = {
                "default_action": item.get("default_action"),
                "infer_expiry": item.get("infer_expiry"),
            }
            self.templates.append((name, pattern, meta))
        self.default_quantity = settings.parser.default_quantity

    def parse(self, text: str) -> TradeIntent:
        cleaned = " ".join(text.split())
        for name, pattern, meta in self.templates:
            match = pattern.search(cleaned)
            if not match:
                continue
            groups = match.groupdict()
            try:
                action_raw = groups.get("action") or meta.get("default_action")
                if not action_raw:
                    raise KeyError("action")
                expiry_raw = groups.get("expiry")
                if expiry_raw:
                    expiry = _parse_expiry(expiry_raw)
                elif meta.get("infer_expiry") == "today":
                    expiry = datetime.now().date()
                else:
                    raise KeyError("expiry")
                right = groups["right"].upper()[0]
                return TradeIntent(
                    action=OrderAction(action_raw.upper()),
                    symbol=groups["symbol"],
                    strike=float(groups["strike"]),
                    right=OptionRight(right),
                    expiry=expiry,
                    limit_price=float(groups["price"]) if groups.get("price") else None,
                    quantity=int(groups["quantity"]) if groups.get("quantity") else self.default_quantity,
                    raw_text=text,
                    template_name=name,
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise ParseError(f"Template {name} matched but validation failed: {exc}") from exc
        raise ParseError(f"No template matched alert: {cleaned[:120]}")


def _parse_expiry(raw: str) -> date:
    """Parse MM/DD, MM/DD/YY, or MM/DD/YYYY."""
    parts = raw.split("/")
    if len(parts) == 2:
        month, day = int(parts[0]), int(parts[1])
        year = _infer_year(month, day)
    elif len(parts) == 3:
        month, day = int(parts[0]), int(parts[1])
        year_part = int(parts[2])
        year = year_part if year_part > 100 else 2000 + year_part
    else:
        raise ValueError(f"Invalid expiry format: {raw}")
    return date(year, month, day)


def _infer_year(month: int, day: int) -> int:
    today = datetime.now().date()
    candidate = date(today.year, month, day)
    if candidate < today:
        return today.year + 1
    return today.year
