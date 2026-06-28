# Windows VM Setup

Run Discord desktop inside a Windows 11 VM with desktop notifications enabled.

## Steps

1. Install Python 3.11+ in the VM
2. Clone/copy this project into the VM
3. `pip install -e ".[windows]"`
4. Enable notification access when Windows prompts
5. In Discord: Server Settings → Notifications → enable for VIP channels
6. Start the listener:

```powershell
python -m src.extractor.win_listener `
  --forward-url http://<MAC_LAN_IP>:8765/alert `
  --secret <ALERT_BRIDGE_SECRET>
```

7. On Mac, start executor: `python -m src.main`

## Verify

```bash
curl http://localhost:8765/health
```

Post a test alert:

```bash
curl -X POST http://localhost:8765/alert \
  -H "Content-Type: application/json" \
  -H "X-Alert-Secret: your-secret" \
  -d '{"text":"BTO SPY 450C 10/18 @ 2.50","app_name":"Discord"}'
```
