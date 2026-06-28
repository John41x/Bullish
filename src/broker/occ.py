"""OCC option symbol utilities."""

from __future__ import annotations

from datetime import date


def build_occ_symbol(*, symbol: str, expiry: date, right: str, strike: float) -> str:
    """Build OCC option symbol, e.g. SPY251017C00450000."""
    root = symbol.upper().ljust(6)[:6]
    yymmdd = expiry.strftime("%y%m%d")
    cp = right.upper()[0]
    strike_int = int(round(strike * 1000))
    return f"{root.strip()}{yymmdd}{cp}{strike_int:08d}"


def parse_occ_symbol(occ: str) -> dict[str, str | float | date]:
    """Parse OCC symbol into components."""
    root = occ[:6].strip()
    yymmdd = occ[6:12]
    cp = occ[12]
    strike_raw = int(occ[13:21])
    expiry = date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    return {
        "symbol": root,
        "expiry": expiry,
        "right": cp,
        "strike": strike_raw / 1000.0,
    }
