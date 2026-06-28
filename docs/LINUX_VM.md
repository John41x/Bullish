# Linux VM Setup (recommended for 16 GB Mac)

Run Discord desktop in an Ubuntu VM. A D-Bus listener captures toasts and forwards
them to the Auto Trader executor on your Mac.

```
Discord (Linux VM) → dbus_listener → HTTP POST → Mac executor → Tradier sandbox
```

## VM sizing (16 GB Mac host)

| Setting | Value |
|---------|-------|
| Hypervisor | [UTM](https://mac.getutm.app/) (free) |
| Guest OS | Ubuntu 24.04 Desktop (64-bit) |
| RAM | 4 GB |
| CPU | 2 cores |
| Disk | 32 GB |
| Network | Shared Network (NAT) |

## Part 1 — Mac setup (do this first)

```bash
cd "/Users/johnluke/Documents/Projects/Auto Trader"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp config/settings.example.yaml config/settings.yaml   # if not done
cp .env.example .env
```

Edit `.env`:

```bash
TRADIER_API_KEY=<sandbox token from web.tradier.com/user/api>
TRADIER_ACCOUNT_ID=<sandbox account id>
TRADIER_BASE_URL=https://sandbox.tradier.com/v1
ALERT_BRIDGE_SECRET=<pick-a-long-random-string>
```

Verify parser (no VM needed):

```bash
pytest
python scripts/replay_fixtures.py
```

### Preview without VM (Mac only)

Terminal 1 — start executor:

```bash
source .venv/bin/activate
python -m src.main
```

Terminal 2 — fake alert:

```bash
curl http://localhost:8765/health

curl -X POST http://localhost:8765/alert \
  -H "Content-Type: application/json" \
  -H "X-Alert-Secret: YOUR_SECRET" \
  -d '{"text":"BTO SPY 450C 10/18 @ 2.50","app_name":"Discord"}'
```

You should see JSON logs: parse → risk → Tradier preview/place (sandbox).

Find Mac IP for the VM (note for later):

```bash
# UTM shared network often uses 192.168.64.x — try:
ipconfig getifaddr en0
# or after VM is up:
ifconfig | grep "inet "
```

## Part 2 — Create Ubuntu VM in UTM

1. Download [Ubuntu 24.04 Desktop ISO](https://ubuntu.com/download/desktop).
2. UTM → **Create New Virtual Machine** → Virtualize → Linux → Ubuntu 64-bit.
3. RAM **4096 MB**, CPU **2**, storage **32 GB**.
4. Mount ISO, install Ubuntu (defaults are fine).
5. After install: UTM → VM Settings → Network → **Shared Network**.
6. Boot VM and run system updates:

```bash
sudo apt update && sudo apt upgrade -y
```

## Part 3 — Install software in the VM

```bash
sudo apt install -y python3 python3-pip python3-venv git curl

# Discord (.deb from discord.com or):
wget -O /tmp/discord.deb "https://discord.com/api/download?platform=linux&format=deb"
sudo apt install -y /tmp/discord.deb
```

Copy the project into the VM (shared folder, `git clone`, or zip).

```bash
cd ~/Auto\ Trader   # or your path
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[linux]"
```

## Part 4 — Discord notifications in VM

1. Log into Discord with your VIP account.
2. Ubuntu: **Settings → Notifications** → allow notifications.
3. Discord: **User Settings → Notifications** → enable desktop notifications.
4. VIP server: channel notification override → **All Messages** (for alert channels).

Test: send yourself a DM in Discord — you should see an Ubuntu toast.

## Part 5 — Run both sides

**Mac** (executor):

```bash
source .venv/bin/activate
python -m src.main
```

**Linux VM** (listener) — replace IP and secret:

```bash
source .venv/bin/activate
python -m src.extractor.dbus_listener \
  --forward-url http://192.168.64.1:8765/alert \
  --secret YOUR_SECRET
```

UTM shared network: Mac is often `192.168.64.1` from the guest. If that fails,
use your Mac's LAN IP from `ipconfig getifaddr en0`.

### Test D-Bus capture without a live VIP alert

In the VM, trigger a test notification:

```bash
notify-send "Discord" "BTO SPY 450C 10/18 @ 2.50"
```

Note: `notify-send` uses app name `notify-send`, not Discord — this tests Mac
executor only. For a Discord-like test, post in a Discord channel and watch the
listener logs.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| VM can't reach Mac | Try `192.168.64.1`, Mac LAN IP, disable Mac firewall for port 8765 |
| 401 on /alert | `ALERT_BRIDGE_SECRET` must match on Mac `.env` and `--secret` |
| No D-Bus events | Must be logged into Ubuntu desktop session (not SSH-only) |
| Listener silent | Confirm Discord toasts appear manually first |
| Tradier errors | Sandbox token + sandbox URL must pair; account ID from sandbox |

## Daily workflow

**Before market:** boot VM → Discord running → start Mac `main` → start `dbus_listener`  
**After market:** stop listener → stop executor → shut down VM (saves RAM on 16 GB Mac)
