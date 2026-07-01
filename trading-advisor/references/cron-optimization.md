# Cron Optimization: Trading Advisor Briefing

## The Conversion (2026-07-01)

Replaced 2 LLM-driven briefing cron jobs with 1 `no_agent=True` script job running 6×/day.

### Before

| Job | Schedule | Mode | Token cost/run | Daily cost |
|---|---|---|---|---|
| `daily-crypto-trading-briefing-morning` | 08:00 UTC+7 | LLM agent (trading-advisor skill) | ~20K tokens | 40K tokens |
| `daily-crypto-trading-briefing-afternoon` | 14:00 UTC+7 | LLM agent (trading-advisor skill) | ~20K tokens | |

**Prompt (same for both):**
```
Load trading-advisor skill. Execute these steps from workdir ...:
1. Generate daily briefing: python3 scripts/briefing.py --output reports/daily_briefing_$(date +%F).md
2. Run signal validation: python3 scripts/signal_validator.py --days 30
3. Run portfolio engine: python3 strategy/portfolio_engine.py
4. Send briefing via Telegram
```

**Problems:**
- Every tick loaded the 100KB trading-advisor SKILL.md as LLM context
- LLM had to reason about commands, read output, and format response — 30-60s latency
- Paper execution was a *separate LLM decision*, not automatic
- `--enhanced` flag already covered steps 2-3 (signal_validator + portfolio engine) — they were redundant
- 2×/day missed intraday moves and prevented capital recycling

### After

| Job | Schedule | Mode | Token cost/run | Daily cost |
|---|---|---|---|---|
| `tok-briefing` | 02/06/10/14/18/22 UTC+7 | `no_agent` script | **0** | **0** |

**Script (`~/.hermes/scripts/tok-briefing.sh`):**
```bash
#!/usr/bin/env bash
set -e
SKILL_DIR="/home/ubuntu/.hermes/skills/trading-advisor"
cd "$SKILL_DIR"
python3 scripts/briefing.py \
  --compact --save-only --paper-open --enhanced \
  >/dev/null 2>/dev/null
cat reports/daily_briefing_"$(date +%F)".md
```

**Key design decisions:**

1. **`>/dev/null 2>/dev/null`** — Suppresses noise lines ("Pulling free market data...", "Briefing written to...") from stdout. Only the cat'd markdown reaches Telegram.

2. **`--paper-open`** — Auto-executes paper trades inline during the briefing run via `paper_trader.open_today_from_briefing()`. No separate paper_executor.py step. No markdown parsing. No LLM decision gate.

3. **`--enhanced`** — Already includes empyrical metrics (VaR, Sharpe, Sortino, Calmar), portfolio status with DoD delta, and regime data. The external signal_validator.py and portfolio_engine.py calls are fully covered — removing them loses nothing.

4. **`set -e`** — Exits immediately on any failure. With `no_agent=True`, non-zero exit triggers an automatic error alert to Telegram.

**Cron creation:**
```bash
cronjob action=create \
  name=tok-briefing \
  schedule="0 2,6,10,14,18,22 * * *" \
  script=tok-briefing.sh \
  no_agent=true \
  deliver=origin
```

### What Changed vs What Stayed

| Component | Before | After | Change |
|---|---|---|---|
| `briefing.py` | Via LLM terminal command | Direct script call | No change to code |
| Paper execution | LLM decides to run `paper_executor.py` | `--paper-open` auto-executes | Inline, instant |
| `signal_validator.py` | LLM runs separately | Already in `--enhanced` block | Removed redundancy |
| `portfolio_engine.py` | LLM runs separately | Already in compact P&L block | Removed redundancy |
| Delivery formatting | LLM formats Telegram message | Script stdout → cron delivery | Fully automatic |
| M2M cron (every 15m) | Unchanged | Unchanged | Kept |
| Latency per run | ~30-60s (LLM) | ~108s (all API calls) | More time, $0 cost |

### Expected Throughput

| Metric | Before (2×/day, LLM-gated) | After (6×/day, auto-execute) |
|---|---|---|
| Runs/week | 14 | **42** (3× more) |
| Signal-to-execution latency | 5-15 min (LLM gate) | **<2 seconds** (in-process) |
| Paper trades/week | 0-2 | **2-8** |
| LLM token cost/month | ~1.2M tokens | **0** |
| Capital recycling | Rare (1×/candidate) | **2-3×/candidate** (close → re-open) |

### Capital Recycling Mechanism

The throughput multiplier isn't just more candidates — it's **re-entry after exit**:

1. **06:00**: RE opened at $0.62 (from briefing + --paper-open)
2. **09:00**: RE hits target at $0.71 → M2M closes it, +14.5%, capital freed
3. **10:00**: Same RE (still passing 24h filter, now at different price) re-opened
4. **15:00**: RE hits trailing stop → closed at +3%, freed again
5. **18:00**: New candidate entirely (breakout that happened during the day)

The dedup guard in `paper_trader.open_position()` only blocks symbols currently in `portfolio["positions"]`. Once a position closes (removed from positions dict), the next briefing run can re-open it at the new price. This is intentional — it allows the same coin to trade 2-3× per day rather than a single multi-day hold.

### Critical Bug Discovered During Validation

**Case-sensitive dedup in `paper_trader.py':296`:**

The briefing generates `syn` (lowercase) for the symbol, but the portfolio stored `SYN` (uppercase). The original check was `if symbol in portfolio["positions"]` which is case-sensitive. Result: `--paper-open` opened a **duplicate third position** (same coin, $449 allocation, different strategy_id).

**Fix:** Changed to case-insensitive comparison:
```python
if any(k.upper() == symbol.upper() for k in (portfolio.get("positions") or {})):
    return None
```

`paper_executor.py` was already correct — it used `.upper()` on both sides.

### Due Diligence Checklist (run before any cron conversion)

- [ ] Confirm the script output is Telegram-ready (no noise lines, clean markdown)
- [ ] Verify all flags cover the functionality of the old LLM steps
- [ ] Check stdout for hidden progress messages that would pollute delivery
- [ ] Verify exit behavior: set -e or explicit error handling
- [ ] Test dedup guards with mixed-case symbols
- [ ] Remove old cron job after new one is verified
- [ ] Update `cron-schedule.md` with new job and removed jobs
<br>Source: actual session transcript — the conversion was validated with 7 tests (API budget, output format, edge cases, M2M compat, capital recycling, bug fixing) before going live.
