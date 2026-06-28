# Auto Trader

Personal, self-hosted execution assistant for converting VIP trading alerts into
brokerage orders. **Not a commercial product. Not investment advice.**

## Scope (personal use only)

This software is intended for **a single operator** using:

- One VIP Discord/X subscription (credentials stay on your machines)
- One brokerage account (API keys stored locally)
- Local infrastructure only (no signal redistribution to third parties)

Do **not** use this to operate a copy-trading service, rebroadcast alerts, or
manage client funds. Doing so may trigger RIA/BD registration requirements and
contract violations with signal providers.

## Risk disclosures

- **Platform ToS:** OS notification capture may still violate Discord/X or VIP
  provider terms. You accept account-ban and subscription-loss risk.
- **Execution risk:** Options are volatile. Slippage, partial fills, API outages,
  and missed exit alerts can cause losses.
- **No warranty:** Software is provided as-is. The author assumes all trading
  and legal risk.

See [docs/PERSONAL_USE.md](docs/PERSONAL_USE.md) for the full guardrail checklist.

## Architecture

```
VIP alert → OS notification → extractor → parser → risk engine → broker API
                                    ↑
                              kill switch (Telegram/SMS)
```

Recommended signal capture: **Linux VM** (Ubuntu + D-Bus listener) on 16 GB Macs, or
**Windows VM** with `UserNotificationListener`. macOS cannot read third-party
app notifications natively.

See [docs/LINUX_VM.md](docs/LINUX_VM.md) (Linux) or [docs/WINDOWS_VM.md](docs/WINDOWS_VM.md) (Windows).

Default broker path: **Tradier sandbox → Tradier live** (options).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp config/settings.example.yaml config/settings.yaml
cp .env.example .env
# Edit .env with TRADIER_API_KEY, TRADIER_ACCOUNT_ID

# Replay parser against fixtures
python scripts/replay_fixtures.py

# Run tests
pytest

# Start executor (Mac or VM)
python -m src.main
```

## Configuration

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Broker, risk limits, trading hours |
| `config/alert_templates.yaml` | Regex patterns per signal provider |
| `.env` | API keys (never commit) |

## Linux VM listener (recommended on 16 GB Mac)

On Ubuntu 24.04 in UTM with Discord notifications enabled:

```bash
pip install -e ".[linux]"
python -m src.extractor.dbus_listener \
  --forward-url http://<mac-ip>:8765/alert \
  --secret <ALERT_BRIDGE_SECRET>
```

Full guide: [docs/LINUX_VM.md](docs/LINUX_VM.md)

## Windows VM listener

On a Windows 11 VM with Discord notifications enabled:

```powershell
pip install -e ".[windows]"
python -m src.extractor.win_listener --forward-url http://<mac-ip>:8765/alert
```

## Kill switch

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. Send `/halt` to
flatten positions and disable execution.

## License

Private personal use. No redistribution.
