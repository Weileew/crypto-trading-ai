# Signal Generation Optimization

## Key Principle: Paper Trading = Maximize Signal Volume

**This is not real money.** Paper trading has zero capital-at-risk. The entire point is to generate enough closed signals to tune the strategy parameters for profitability. Every signal you skip is a lost optimization cycle.

### State-Based Optimization Philosophy

| State | Signal Volume | M2M Frequency | Rationale |
|---|---|---|---|
| 🔴 CRITICAL (dd ≤ -10%) | Pause signal gen | every 15m | Capital preservation — recovery mode |
| 🔶 COLD (wr <25% / streak ≤ -5) | **MAXIMIZE** | every 15m | More data = faster tuning. Paper mode: cold means the strategy needs MORE data to debug |
| ✅ NORMAL (wr 25-55%) | Standard (3 runs/day) | every 30m | Maintain signal flow at normal rate |
| 🟢 HOT (wr ≥55% / pf ≥1.5) | Standard | every 30m | Capture momentum; don't add noise to a working strategy |

**CRITICAL is the only state where signals decrease.** All other states maintain or increase signal volume. In COLD, the instinct is to reduce signals (real-money capital preservation mindset) — but in paper trading, cold means the strategy is broken and needs more data to diagnose the problem.

## Current Signal Pipeline Bottleneck

As of 2026-06-29, the signal generation pipeline has these limits:

### Throughput

| Stage | Capacity | Constraint |
|---|---|---|
| `fetch_markets()` | ~500 coins scanned | 2 CG calls |
| `simple_rules()` filter | ~5-15 viable candidates | mcap≥$50M, abs(24h chg)≥3%, score calc |
| `max_opportunities: 2` | **only top 2 → signals** | **PRIMARY BOTTLENECK** |
| `score_threshold: 25.0` | filters out scores below 25 | **SECONDARY BOTTLENECK** |
| Signal runs/day | 3 (04:00, 08:00, 14:00) | Fixed by cron schedule |

**Result:** 0-6 signals/day. At 3 runs with 2 opportunities, the system has only generated 23 total signals across its entire lifetime.

### CG Headroom

| Metric | Value |
|---|---|
| Used/day | ~116 calls (M2M 96 + orchestrator 8 + briefings 12) |
| Free tier | 14,400 calls/day |
| **Available** | **14,284 calls/day (99.2% unused)** |

The CG budget is essentially not a constraint. Adding screening passes or increasing opportunities costs near-zero CG.

## Optimization Levers

### 1. `max_opportunities` (params.json → screening)

Currently `2`. Increasing to `4-5` gives 2-2.5× more signals per run at zero CG cost. The `simple_rules()` scoring loop already evaluates all candidates — the only thing changing is how many of the top scorers get recorded as signals.

**Risk:** More open positions means more CG calls per M2M tick (1 CG/position for price). At 5 open positions, M2M still costs 1 CG call (single `/simple/price` batch). No meaningful increase.

### 2. `score_threshold` (params.json → screening)

Currently `25.0`. Scores are driven by: price momentum (abs 24h), mcap flow, TokoCrypto volume bonus (+10 max), spread bonus (±5), liquidity penalty (-5), trap filter penalties (-8 to -15). Dropping to `18.0-20.0` catches borderline candidates that still have spread+volume bonuses. The volume bonus (+10) and spread bonus (+5) naturally reward high-quality setups.

### 3. Additional screening passes

Add 1-2 `--quick` orchestrator runs per day (e.g., 12:00, 18:00). These skip news, validation, and performance — just `fetch_markets() → simple_rules() → record signals`. Cost: 2 CG calls each. Catches midday breakouts and late-day setups the fixed 08:00/14:00 runs miss.

Implementation: either `cronjob(action='create', ...)` calling `python3 scripts/orchestrator.py --quick` or a dedicated `python3 scripts/briefing.py --scout-only` script.

### 4. `min_24h_change_pct` (params.json → screening)

Currently `3.0%`. Lowering to `2.0%` catches early-stage movers before they hit 3%. May increase noise but paper trading absorbs this cost freely. Pairs well with a lower score threshold.

## Expected Impact

| Change | Signals/day | Time to 100 closed signals |
|---|---|---|
| Baseline (2 opps, thresh 25, 3 runs) | ~2-3 | **5-8 weeks** |
| + max_opportunities=5 | ~5-8 | **2-3 weeks** |
| + threshold=18 | ~8-12 | **~10 days** |
| + 2 extra screening runs | ~12-18 | **~1 week** |

100 closed signals is the rough threshold for statistically meaningful win-rate measurement (±10% margin at 95% confidence). Below this, a 40% WR could mean anything from 30-50%.

## Verification

Run this after any parameter change to verify signal throughput:

```bash
cd ~/.hermes/skills/trading-advisor
python3 -c "
import sqlite3
db = sqlite3.connect('strategy/journal.db')
total = db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
open_s = db.execute(\"SELECT COUNT(*) FROM signals WHERE state='open'\").fetchone()[0]
closed = db.execute(\"SELECT COUNT(*) FROM signals WHERE state='closed'\").fetchone()[0]
pending = db.execute(\"SELECT COUNT(*) FROM signals WHERE state='pending'\").fetchone()[0]
print(f'Total signals: {total} | Open: {open_s} | Closed: {closed} | Pending: {pending}')
print(f'Win rate: {db.execute(\"SELECT win_rate FROM performance ORDER BY id DESC LIMIT 1\").fetchone()[0]:.1%}')
"
```

## Cron Manager Integration

The cron manager at `strategy/cron_manager.py` includes performance awareness via `--performance` / `-p` flag. Run it to check current state and get schedule recommendations:

```bash
cd ~/.hermes/skills/trading-advisor
python3 strategy/cron_manager.py --performance
```

The manager reads the strategy journal, signal performance, and portfolio to classify the system state and suggest appropriate schedule changes. Use `cronjob action=update` to apply the recommended schedule changes.
