# Investigating M2M Output Accuracy

When the M2M cron delivers a closed-trades notification, cross-reference it against the three sources of truth to validate accuracy.

## Source Hierarchy

```
journal.db (signals + outcomes tables)   ← SOURCE OF TRUTH for live trades
ledger.json (trades array)               ← historical record
portfolio.json (positions dict)          ← current open positions (ephemeral)
```

- **journal.db** is authoritative for any trade that went through the formal signal pipeline
- **ledger.json** is the comprehensive record but can carry orphaned/legacy entries
- **portfolio.json** only shows *currently open* positions; once a position closes it drops out

## Investigation Steps

### 1. Identify signal IDs from journal.db

```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -c "
import sqlite3
conn = sqlite3.connect('strategy/journal.db')
conn.row_factory = sqlite3.Row
# all signals with their outcomes (LEFT JOIN)
cur = conn.execute('''
  SELECT s.id, s.symbol, s.entry_price, s.source, s.notes,
         o.outcome, o.exit_price, o.pnl_pct, o.exit_reason
  FROM signals s
  LEFT JOIN outcomes o ON o.signal_id = s.id
  ORDER BY s.id
''')
for r in cur.fetchall():
    print(dict(r))
"
```

### 2. Check ledger.json for any trade not in journal

Each trade in `reports/paper_trading/ledger.json` has fields: `trade_id`, `symbol`, `entry_price`, `status` ("opened" or "closed"), `exit_price`, `pnl`, `validation_status`.

- **Trades in journal + ledger with exit data** → fully tracked, outcome is real
- **Trades in ledger but NOT in journal** → legacy orphan. Exit=N/A, PnL=N/A. These were opened before journal tracking existed or never synced. Labelled `legacy_archived` in M2M output.
- **Trades in ledger as "opened" but no longer in portfolio** → already swept by M2M, archived

### 3. Verify portfolio.json has no stale orphans

```bash
python3 -c "
import json
p = json.load(open('reports/paper_trading/portfolio.json'))
print('Positions:', list(p.get('positions', {}).keys()))
print('Cash:', p.get('cash'))
print('Equity:', float(p.get('cash', 0)) + sum(
    pos.get('quantity', 0) * pos.get('current_price', 0)
    for pos in p.get('positions', {}).values()
))
"
```

An empty `positions: {}` with old trades in ledger is normal after M2M cleanup.

### 4. Interpret the notification labels

| M2M label | Meaning |
|---|---|
| `hit_stop` | Stop-loss triggered — exit price and PnL from journal. Real outcome. |
| `hit_target` | Take-profit hit — exit price from journal. Real outcome. |
| `trailing_stop` | Trailing stop activated and triggered — exit price from journal. Real outcome. |
| `legacy_archived` | Trade existed in ledger but never in journal. Exit=N/A, PnL=N/A. Cleanup action, not a real close. |
| `Journal: synced N` | N = number of trades that had journal outcomes recorded this tick (matches journal.db rows added). |

### 5. Full trace example

Given M2M output:
```
| 2026-06-27 11:29 | SKYAI | entry=0.367899 | exit=0.348422 | -5.29% | hit_stop |
```

Trace:
1. ✅ journal.db signal id=21, SKYAI @ 0.367899, outcome=hit_stop, exit=0.348422, pnl=-5.29% — matches
2. ✅ ledger.json has trade for SKYAI with `status: "opened"` (ledger is historical, won't show close — that's normal)
3. ✅ portfolio.json no longer has SKYAI (removed on M2M close). Cash adjusted.

Given M2M output:
```
| 2026-06-27 11:49 | VELVET | entry=0.709546 | exit=N/A | N/A | legacy_archived |
```

Trace:
1. ❌ No matching signal in journal.db for VELVET @ 0.709546
2. ✅ ledger.json has trade `trade_c453e07e46` (VELVET, 0.709546, "opened", validation_status="pending")
3. ✅ portfolio.json no longer has VELVET (cleanup)
→ Honest `legacy_archived` — system correctly flagged lack of data

### 6. Cash Reconciliation Trace (for phantom losses)

When the M2M report shows a return like "-6.33%" but the sum of all closed-trade PnL is tiny (+$1.07), run a cash reconciliation:

```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -c "
import json

with open('reports/paper_trading/portfolio.json') as f:
    pf = json.load(f)
with open('reports/paper_trading/ledger.json') as f:
    lg = json.load(f)

start = pf.get('starting_capital', 10000.0)
cash = pf.get('cash', 0.0)
print(f'Starting capital: \${start:.2f}')
print(f'Current cash:     \${cash:.2f}')
print(f'Total gap:        \${cash - start:+.2f}')
print()

total_r = 0.0
for t in lg['trades']:
    if t.get('status') in ('closed',) or t.get('closed_at'):
        pnl = t.get('pnl_usd') or 0
        total_r += pnl
        sym = t['symbol']
        qty = t.get('qty') or t.get('quantity') or 1.0
        entry = t.get('entry_price', 0)
        print(f'  CLOSED {sym}  qty={qty:.2f}  entry=\${entry:.6f}  pnl=\${pnl:+.2f}')

print()
print(f'Realized PnL sum:  \${total_r:+.2f}')
print(f'Expected cash:     \${start + total_r:.2f}')
print(f'PHANTOM LOSS:      \${cash - (start + total_r):+.2f}')
# If phantom loss is large (hundreds of $), the portfolio deducted
# 5% allocations (~$500) for trades but the ledger recorded them with qty=1.0
"
```

Common finding: ledger shows `qty=1.0` allocations ($0.37–$0.72) but portfolio cash dropped by $600+. The actual portfolio deducted 5% allocations per trade, not recorded in the ledger. The ledger is the record of intent, not actual cash flow.

Also check for orphaned open trades in the ledger that never made it to the portfolio:

```bash
python3 -c "
import json
with open('reports/paper_trading/portfolio.json') as f:
    pf = json.load(f)
with open('reports/paper_trading/ledger.json') as f:
    lg = json.load(f)

positions = pf.get('positions', {})
for t in lg['trades']:
    if t.get('status') == 'opened':
        sym = t.get('symbol', '?')
        if sym.upper() not in positions:
            qty = t.get('qty') or t.get('quantity') or 0
            entry = t.get('entry_price', 0)
            alloc = qty * entry
            print(f'⚠️  {sym} OPEN in ledger, MISSING from portfolio (alloc=\${alloc:.2f})')
"
```

This detects the "position opened by briefing but overwritten by M2M before persist" pattern.

## Phantom / Duplicate Signal Detection

A phantom duplicate is a signal+outcome pair in `journal.db` for a position that is still **open** in `portfolio.json`. These occur when a trailing stop or other close fires and syncs to the journal, but a bug re-opens the same position before the next M2M tick.

**Detection:**

```bash
cd ~/.hermes/skills/trading-advisor
python3 -c "
import json, sqlite3
# Group signals by symbol+entry to find duplicates
db = sqlite3.connect('strategy/journal.db')
cur = db.execute('''
  SELECT symbol, entry_price, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
  FROM signals
  GROUP BY symbol, entry_price
  HAVING cnt > 1
  ORDER BY cnt DESC
''')
dupes = cur.fetchall()
if dupes:
    print('DUPLICATE SIGNALS:')
    for d in dupes:
        print(f'  {d[0]} @ {d[1]} — {d[2]} copies (ids: {d[3]})')
else:
    print('No duplicate signals')

# Cross-check: signals closed in journal but position open in portfolio
with open('reports/paper_trading/portfolio.json') as f:
    p = json.load(f)
open_syms = list(p.get('positions', {}).keys())
if open_syms:
    placeholders = ','.join(['?'] * len(open_syms))
    cur = db.execute(
        f'SELECT s.id, s.symbol, s.entry_price FROM signals s JOIN outcomes o ON s.id = o.signal_id WHERE s.symbol IN ({placeholders})',
        open_syms
    )
    phantom = cur.fetchall()
    if phantom:
        print(f'PHANTOM (closed in journal, open in portfolio):')
        for e in phantom:
            print(f'  sig={e[0]} {e[1]} @ {e[2]}')
db.close()
"
```

**Cleanup** (verify IDs first, then run):

```bash
cd ~/.hermes/skills/trading-advisor
python3 -c "
import sqlite3
db = sqlite3.connect('strategy/journal.db')
db.execute('PRAGMA foreign_keys = OFF')
# DELETE outcomes first (FK to signals), then signals
# Replace with actual IDs from detection step
phantom_outcome_ids = [27, 28, 29, 30]
phantom_signal_ids = [29, 30, 31, 32]
if phantom_outcome_ids:
    db.execute(f'DELETE FROM outcomes WHERE id IN ({','.join(['?']*len(phantom_outcome_ids))})', phantom_outcome_ids)
if phantom_signal_ids:
    db.execute(f'DELETE FROM signals WHERE id IN ({','.join(['?']*len(phantom_signal_ids))})', phantom_signal_ids)
db.commit()
print(f'Cleaned {len(phantom_signal_ids)} signals + {len(phantom_outcome_ids)} outcomes')
db.close()
"
```

**Prevention:** `_sync_closed_to_journal()` in `paper_trader.py` calls `strategy_journal.signal_exists(symbol, entry_price)` before creating a standalone record. If a signal for this symbol+entry (±5%) already exists (open or closed), the standalone branch is skipped — the existing record is sufficient.

### Real-Time M2M Overwrite Awareness

When running M2M diagnostics, be aware that the M2M cron runs **every 15 minutes**. If your diagnostic spans multiple reads, the M2M can close positions and adjust cash between reads:

1. First read shows RE open, cash=$9,187.12
2. M2M runs (15m tick): closes RE via trailing stop, cash becomes $9,367.25
3. Second read shows no positions, cash=$9,367.25

**Rule of thumb**: If you're doing multi-step diagnostics, either pause the M2M cron first, or timestamp every read and note M2M run boundaries. Use `cronjob action='pause' job_id='91d6c930e1f3'` to pause the M2M during extended diagnostics.

### SQLite Tolerance Gotcha (`MAX(ABS)`)

When writing `ABS(s.entry_price - ?) / MAX(ABS(?), 1.0) < ?`, the `MAX()` evaluates on the **bound parameter**, not the stored column. For crypto prices < $1.0, `MAX(ABS(0.616837), 1.0)` = 1.0, making absolute tolerance $0.05 = ~8% of a $0.62 entry — too wide, can match genuinely different trades.

**Fix:** reference the *stored column*:
```sql
ABS(s.entry_price - ?) / MAX(ABS(s.entry_price), 0.001) < ?
```
The `0.001` floor keeps the tolerance percentage-based even for sub-penny prices.

### Common Pitfalls

- **Two trades same symbol, different prices**: M2M archives both independently (e.g. VELVET @ 0.7095 and VELVET @ 0.6058 are separate ledger entries, archived separately)
- **Exit=N/A ≠ error**: for `legacy_archived` records, it means the journal had no outcome data to report, not that the system failed to look
- **Cash changes between pre/post-close**: M2M updates cash incrementally. If RE was open at +$4 and the diagnostic showed cash=$9,380.63, a later RE close (trailing_stop +$2.30-ish) brings cash to ~$9,566. Cross-check with ledger's latest P&L
- **Journal sync count vs notification table**: "Journal: synced 1 closed position(s)" = 1 trade was newly recorded in journal this tick. The notification table may show 4 rows because 3 are legacy_archived (pre-existing ledger cleanups) and 1 is the new journal sync. These are both operational in the same report — the count only tracks journal-write events, not total rows printed.
- **Phantom cash loss from qty=1 trades**: If the M2M report says `-6.33% return` but closed trades sum to only +$1.07, the portfolio deducted 5% allocations (~$500 each) for early trades while the ledger recorded them at qty=1.0 (~$0.71). The cash balance is real; the ledger is under-reporting allocations. Reconcile by reconstructing real allocations from portfolio.json history.
