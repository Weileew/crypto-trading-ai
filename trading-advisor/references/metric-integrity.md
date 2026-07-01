# Metric Integrity — Live vs Backtest Separation

## The Bug (discovered 2026-06-30)

`strategy_journal.compute_performance()` joined ALL outcome sources without filtering. This caused `signal_validator` backtest results — a deliberate quality filter where most signals are expected to fail — to be counted as "trading losses" in the live performance metrics.

### Symptoms

| Metric | Before (polluted) | After (live-only) | Impact |
|---|---|---|---|
| Profit Factor | 0.88 | 2.15 | Misleading "losses" → PF below 1.0 |
| Win Rate | 42.9% | 75.0% | 15 validator stops overwhelmed 3 live wins |
| Closed trades | 28 | 4 | 24 validator outcomes blended into the count |
| Best symbol | SYN | SYRUP | Validator's SYN timeout inflated best-symbol avg |
| Worst symbol | S | SKYAI | S had 5 backtest_stop outcomes at -8% each |

### Root Cause

`compute_performance()` query (lines 430-436 in strategy_journal.py):

```sql
SELECT ... FROM outcomes o
JOIN signals s ON s.id = o.signal_id
WHERE s.generated_at >= ?
```

No `WHERE s.source != 'signal_validator'` filter. All sources were mixed.

The `signal_validator` produces **24 outcomes per batch** (5 tokens × multiple param versions) where ~15/24 are `backtest_stop` — this is the validator *doing its job*, not trading losses. But the performance engine counted them as losses.

### The Fix

1. **`compute_performance()`** — Added `exclude_sources=['signal_validator']` as a default parameter. Both the main data query and the streak query now include `AND s.source NOT IN (...)`.

2. **`portfolio_engine.journal_performance()`** — Added `WHERE s.source NOT IN ('signal_validator')` to the raw outcomes query that computes stop/target/trailing hit rates.

3. **Snapshot cleanup** — Deleted 68 polluted performance snapshots from `performance` table.

### The Principle

**Live trading metrics must only include live trading data.** The signal_validator is a pre-trade quality gate — its job is to produce high fail rates on bad signals. Including its outputs in the performance table is like counting rejected applications as "failed hires."

### Sources That Should Be Excluded From Live Metrics

| Source | Purpose | Should Count As Live? |
|---|---|---|
| `paper_trader` | Actual paper trades (live) | ✅ Yes |
| `briefing` | Signals recorded during briefing | ✅ Yes (but rare - usually consensus signals) |
| `signal_validator` | Backtest quality gate | ❌ No — designed to fail bad signals |
| `smoke_test` | Test signals (cleaned up immediately) | ❌ No — ephemeral test data |

### Verification

```bash
# Check performance shows only live trades
cd ~/.hermes/skills/trading-advisor
python3 scripts/strategy_journal.py performance trailing_30d

# Expected: PF > 1.0 if live trading is positive, small signal count
# Check: closed_signals should match only paper_trader outcomes

# Check portfolio engine sees clean data
python3 -c "
import sys; sys.path.insert(0, 'strategy')
from portfolio_engine import journal_performance
r = journal_performance()
print(f'WR={r[\"win_rate\"]} PF={r[\"profit_factor\"]} closed={r[\"closed\"]}')
print(f'stop_hit_rate={r[\"stop_hit_rate\"]}% target_hit_rate={r[\"target_hit_rate\"]}%')
"
```

### Pitfalls

- **Sample size shock**: After the fix, closed_signals drops dramatically (e.g. 28→4). The system now has <5 closed trades, which triggers `insufficient_data` in `adapt_params()` and the calibration health "not enough data" penalty. This is *correct* — don't auto-tune on 4 trades.

- **`portfolio_engine.journal_performance()` reads two sources**: (1) the latest pre-computed snapshot from the `performance` table, and (2) its own raw outcomes query for stop/target/trailing rates. Both must be filtered independently.

- **Streak calculation was also polluted**: The streak query (lines 481-488) had the same missing filter. With validator data, the streak showed -10 (15 validator stops in a row). Without it, the live streak resets to 0 or positive.

- **Signal_validator data is NOT useless**: Exclude it from live metrics, but keep it for signal-quality analysis — tracking what % of signals pass/fail validation is a key system health metric. It just doesn't belong in the P&L column.