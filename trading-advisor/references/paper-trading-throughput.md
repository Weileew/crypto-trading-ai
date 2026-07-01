# Paper Trading Throughput Optimization

## The Core Constraint (User Preference)

> **One pipeline, one grand strategy.** Never introduce a secondary pipeline, relaxed filters, or alternative strategy to generate more signals. The goal is to test the *exact same strategy* at maximum frequency. Throughput improvements must be **operational** (cron scheduling, execution speed, capital recycling), not **algorithmic** (different looksbacks, different screening logic).

## Architecture Overview: 3 Jobs, 1 Pipeline

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Job A: Briefing    │────→│  Job B: M2M (15min)  │────→│  Job C: Summary (1/d)│
│  (4-6×/day)         │     │  (no_agent=True)     │     │  (LLM agent)         │
│                     │     │                      │     │                     │
│  brief → score →    │     │  update positions    │     │  read ledger.csv     │
│  rank → save →      │     │  check stops/targets │     │  compute P&L         │
│  --paper-open       │     │  check trailing      │     │  report to user      │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
         │                           │
         │ opens positions           │ closes positions (stop/target/trail)
         │ via --paper-open          │ frees capital
         ▼                           ▼
    portfolio.json ────────────── portfolio.json
```

## The Bottleneck Analysis

### 24h Lookback Limit

The pipeline screens using **24h price change** as its primary filter. This means:

- A coin that jumps 3% at 09:00 stays a candidate for ~24 hours
- Running the pipeline more often doesn't reveal *new* candidates faster — the same coins repeat
- **Benefit of higher frequency**: earlier capture of new moves (not more candidates per run)

### The Real Multiplier: Capital Recycling

With M2M running every 15 minutes, trades can close (stop/target/trail) and free capital between briefing runs. If `--paper-open` is wired, the next briefing run can **re-open the same symbol on the same day** because:

- `paper_trader.open_position()` checks if symbol is in `portfolio.positions` (current open positions only)
- Once a trade closes, it's removed from positions → symbol is available again
- Ledger dedup checks `(date, symbol)` with `status == "opened"` — closed trades don't block

**Example throughput (single coin, volatile day):**

| Time | Event | Cash | Positions |
|---|---|---|---|
| 06:00 | Brief → open RE @ $0.62 | $8,996 | RE |
| 11:00 | M2M: RE hits target @ $0.71 → **closed +14.5%** | $9,367 | — |
| 14:00 | Brief → open RE @ $0.65 (still a candidate) | $8,996 | RE |
| 18:00 | M2M: RE hits trailing stop @ $0.68 → **closed +4.6%** | $9,367 | — |
| Day total | **+$741 (+~19%) from one coin, two trades** | | |

vs without capital recycling: one trade, +$711 (+7.6%), rest of day idle.

### Rate Limit Feasibility

One briefing run makes **4-5 CoinGecko calls** at 6-second spacing (~25s total):

| Call | API | Rate-limited? |
|---|---|---|
| `_fetch_coingecko_page(1)` | CoinGecko | Yes (6s) |
| `_fetch_coingecko_page(2)` | CoinGecko | Yes (6s) |
| `_get_cg(coins/list)` | CoinGecko | Yes (6s, cached after first run) |
| `_get_cg(simple/price)` | CoinGecko | Yes (6s) |
| `_get_cg_global()` | CoinGecko | Yes (12s, separate budget) |
| `fetch_fear_greed()` | alternative.me | No |
| `fetch_coincap()` | coincap.io | No |

**Budget at various frequencies:**

| Frequency | CG calls/day | Free tier used | Headroom |
|---|---|---|---|
| 2× (current) | ~10 | 0.07% | 99.93% |
| 4× | ~20 | 0.14% | 99.86% |
| **6×** | **~30** | **0.21%** | **99.79%** |
| 12× (every 2h) | ~60 | 0.42% | 99.58% |

Free tier limit: ~14,400 calls/day (10 req/min × 1440 min). 6×/day uses 0.21%. There is effectively no rate-limit constraint.

### The LLM Middleman Latency (Critical)

The cron prompt currently runs as an **LLM agent that reads the skill → executes steps 1..4 sequentially**. For each tick:

1. LLM loads skill: ~2-5 seconds (token overhead)
2. LLM runs `briefing.py`: ~25 seconds
3. LLM reads output and **decides** to run paper_executor: ~3-10 seconds
4. LLM runs paper_executor: ~5 seconds
5. LLM formats delivery: ~5 seconds

Total overhead: **~40-50 seconds per run** — mostly LLM reasoning time that adds nothing.

### The Fix: `--paper-open` (already exists, not wired)

`briefing.py` has a `--paper-open` flag (line 2205) that:

1. Calls `paper_trader.open_today_from_briefing()` **inline** in the same process
2. Opens positions into `portfolio.json` + `ledger.json`
3. Uses live market price (not markdown-parsed price) via CoinGecko `simple/price`
4. Adjusts stop/target proportionally to live price
5. Respects all dedup rules (no duplicate opens)

**Current cron prompt** (wasteful):
```bash
python3 scripts/briefing.py --output reports/daily_briefing_$(date +%F).md
# LLM reads output, then separately decides to run paper_executor.py
```

**Optimal cron prompt** (single process):
```bash
python3 scripts/briefing.py --compact --save-only --paper-open --enhanced
```

The difference: paper execution happens at signal time (±2 seconds), not 5-15 minutes later. In crypto, a 10-minute delay on a volatile coin can lose 50-100bps of entry price.

## Implementation Notes

### Dedup Safety

`--paper-open` is safe to run every briefing tick because:

1. `paper_trader.open_position()` on line 296: `if symbol in portfolio.positions: return None`
2. `paper_executor.open_trades()` on line 226-233: checks `(date, symbol)` in ledger AND `portfolio_open_symbols`
3. Re-opening same symbol on same day is **allowed** if the first trade has already closed (capital recycled)

### M2M Must Keep Running

The M2M cron (`every 15m`, `no_agent=True`) is essential for throughput:

- It calls `update_mark_to_market()` which checks stops/targets/trails
- Without M2M, positions stay open indefinitely — no capital recycling
- With M2M, a trade hitting target at 11:00 is closed by 11:15, capital ready for 14:00 briefing

### No Changes to Briefing.py Required

Everything in this optimization is **operational** — cron scheduling and flag changes. The pipeline code (scoring, ranking, filters) is untouched. This satisfies the single-preference constraint entirely.

## Recommended Schedule

```
02:00  │ 06:00  │ 10:00  │ 14:00  │ 18:00  │ 22:00
```

6 runs/day. Each run: `briefing.py --compact --save-only --paper-open --enhanced`.

Why not more? Diminishing returns. With 24h lookback, 6×/day catches new moves at 4-hour granularity. Beyond that, the same candidates repeat without new signal. 6× is the sweet spot between coverage and redundancy.

## Key Trade-off Summary

| Approach | New trades/week | Code changes | Risk |
|---|---|---|---|
| 2×/day (current) | 0-4 | None | Baseline |
| 6×/day + `--paper-open` | 2-10 | Cron prompt only | Low (wired flag, tested dedup) |
| New pipeline (relaxed filters) | 8-20 | Requires new scoring | High (mixes strategies) |
| Shorter lookback (4h) | 10-25 | Requires new scoring | High (noisier signals) |

The recommended approach (6×/day + `--paper-open`) is the maximum throughput available from the **exact same pipeline**.
