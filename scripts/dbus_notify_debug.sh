#!/usr/bin/env python3
"""Print raw D-Bus notification events (run inside Ubuntu VM).

Usage:
    sudo apt install -y dbus-x11   # provides dbus-monitor
    ./scripts/dbus_notify_debug.sh

Then send a Discord DM or run:
    notify-send "Discord" "test alert BTO SPY 450C 10/18 @ 2.50"
"""

from __future__ import annotations

import subprocess
import sys

RULE = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"

print("Watching D-Bus Notify calls. Send a Discord message or notify-send test.")
print(f"Match rule: {RULE}\n")

try:
    subprocess.run(["dbus-monitor", f"interface='org.freedesktop.Notifications',member='Notify'"], check=False)
except FileNotFoundError:
    print("Install dbus-monitor: sudo apt install -y dbus-x11", file=sys.stderr)
    sys.exit(1)
