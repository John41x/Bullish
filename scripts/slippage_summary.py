#!/usr/bin/env python3
"""Summarize slippage journal for live pilot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.journal.slippage import SlippageJournal


def main() -> None:
    journal = SlippageJournal()
    summary = journal.summary()
    print(json.dumps(summary, indent=2))
    if journal.path.exists():
        print(f"\nJournal: {journal.path}")
        with journal.path.open() as handle:
            for line in handle:
                print(line.rstrip())


if __name__ == "__main__":
    main()
