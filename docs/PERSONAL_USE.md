# Personal Use Guardrails

Complete this checklist before running Auto Trader with live capital.

## Legal and regulatory

- [ ] I am the sole user and operator of this software.
- [ ] I will not charge others for access, signal replication, or trade execution.
- [ ] I will not redistribute VIP alert content to third parties.
- [ ] I understand this is **not** registered investment advice or portfolio management.
- [ ] I have reviewed my signal provider's Terms of Service regarding automation.

## Technical scope

- [ ] API keys are stored locally (`.env` or OS keychain), never in git.
- [ ] Execution runs on infrastructure I control (Mac + optional Windows VM).
- [ ] No cloud webhook relays carry raw VIP alert text.
- [ ] Kill switch is configured and tested in sandbox before live trading.

## VIP provider ToS risk acceptance

OS notification scraping does **not** touch Discord/X APIs, but providers may
still prohibit automated use of their alerts. Consequences may include:

- Permanent Discord/X account ban
- Loss of paid VIP subscription without refund
- Civil claims for contract breach (especially if commercialized)

**By using this software you accept these risks.**

## Pre-live checklist

- [ ] Parser replay tests pass at ≥95% on your alert fixtures
- [ ] Tradier sandbox round-trip verified
- [ ] Slippage guard rejects quotes >3% from alert price
- [ ] Local stop-loss / take-profit attached after every entry
- [ ] Kill switch flattens sandbox positions on command
- [ ] Windows VM listener captures Discord toasts reliably during RTH

## What this software does NOT do

- Multi-user SaaS or client credential vault
- Discord/Twitter self-bots or headless scraping
- Performance marketing or subscription billing
- Guaranteed fill at alert price
