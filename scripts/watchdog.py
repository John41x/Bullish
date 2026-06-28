#!/usr/bin/env python3
"""Watchdog launcher for Auto Trader supervisor."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELAY = 5


def main() -> None:
    while True:
        print("Starting auto-trader supervisor...")
        proc = subprocess.run([sys.executable, "-m", "src.main"], cwd=ROOT)
        print(f"Supervisor exited with code {proc.returncode}, restarting in {DELAY}s")
        time.sleep(DELAY)


if __name__ == "__main__":
    main()
