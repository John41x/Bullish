#!/usr/bin/env python3
"""Replay alert fixtures through the parser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.parser import AlertParser, ParseError


def main() -> None:
    fixtures_path = ROOT / "tests" / "fixtures" / "alerts.json"
    alerts = json.loads(fixtures_path.read_text())
    parser = AlertParser()

    ok = 0
    fail = 0
    for item in alerts:
        text = item["text"]
        expect = item.get("expect", "parse")
        try:
            intent = parser.parse(text)
            if expect == "fail":
                fail += 1
                print(f"UNEXPECTED OK {text[:60]}")
            else:
                ok += 1
                print(f"OK  [{intent.template_name}] {text[:60]}")
        except ParseError as exc:
            if expect == "fail":
                ok += 1
                print(f"OK  (expected fail) {text[:60]}")
            else:
                fail += 1
                print(f"FAIL {text[:60]}")
                print(f"     {exc}")

    total = ok + fail
    parse_expected = sum(1 for a in alerts if a.get("expect") == "parse")
    rate = ok / total if total else 0
    print(f"\nResults {ok}/{total} checks passed")
    print(f"Parse success on expected alerts: {parse_expected} templates")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
