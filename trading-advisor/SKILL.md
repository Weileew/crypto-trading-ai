---
name: trading-advisor
description: "Crypto market analysis and trading advisory skill for Hermes Agent. Generates swing/day trading briefings with multi-source free data, detailed reasoning, risk controls, and delivery via cron."
version: 3.1.0
author: user
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cryptocurrency, trading, crypto]
---

# Crypto Trading Advisor (TOK)

**TOK** — Welly's trading system alias. "run TOK" = the full trading-advisor pipeline (briefing.py, orchestrator.py, paper validation).

For swing/day trading in spot markets across all liquid coins, using only free data sources plus TokoCrypto liquidity where available.
Reasoning must be detailed and explicit. All inputs are read-only: no trade execution, no withdrawal, no signing.

Goal: produce a decision-quality daily briefing and on-demand market analysis that is far more rigorous than a casual call.

## Reference Documents
- `references/signal-quality.md` — Signal pipeline: scaled volatility gate, loss penalty, win momentum, regime gating
- `references/paper-trading-data-model.md` — Paper trading data integrity: dedup guards, open/close lifecycle, path divergence
- `references/cron-schedule.md` — All active cron jobs, removed jobs, state-based schedule map, adding new jobs
- `references/cron-optimization.md` — Complete case study: converting LLM-driven briefing crons to 6x/day no_agent script with --paper-open auto-execution
