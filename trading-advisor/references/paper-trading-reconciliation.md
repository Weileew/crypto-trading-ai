# Paper Trading Reconciliation Workflow

Complete step-by-step procedure for reconciling `portfolio.json`, `ledger.json`, and `journal.db` when discrepancies are discovered. Used during the 2026-06-28 audit session.

## Overview

Three data sources must agree:
- **portfolio.json** — active positions with trailing stop state, current prices, running P&L
- **ledger.json** — trade history log (legacy + new schema mixed)
- **journal.db** — append-only SQLite audit trail (signals, outcomes, params history) — **source of truth**

## Reconciliation Procedure

### Step 1: Load and Inspect All Three Sources

```bash
# Portfolio (active positions with trailing stop state)
cat trading-advisor/reports/paper_trading/portfolio.json

# Ledger (trade history with legacy/new mixed schema)
cat trading-advisor/reports/paper_trading/ledger.json

# Journal DB (source of truth for closed trades)
cd trading-advisor && python3 -c "
import sqlite3
conn = sqlite3.connect('strategy/journal.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT s.symbol, s.entry_price, o.exit_price, o.pnl_pct, o.outcome, o.exit_reason, o.closed_at
    FROM outcomes o JOIN signals s ON s.id=o.signal_id
    ORDER BY o.closed_at
''')
for row in cursor.fetchall():
    print(f'{row[0]}: signal_entry={row[1]} exit={row[2]} pnl={row[3]}% outcome={row[4]} reason={row[5]} at={row[6]}')
"
```

### Step 2: Dedup Journal Outcomes

Journal may have duplicate outcomes from repeated backtest runs (e.g., VELVET/MAGMA validated 3×). Create a deduped map keyed by `(symbol, signal_entry, exit_price)`:

```python
seen = set()
deduped = []
for outcome in outcomes:
    key = (outcome['symbol'].upper(), round(outcome['signal_entry'], 6), round(outcome['exit_price'], 6))
    if key not in seen:
        seen.add(key)
        deduped.append(outcome)
```

### Step 3: Match Ledger Trades to Journal Outcomes (One-to-One)

Each ledger trade should match **at most one** journal outcome. Use entry price proximity (±5%) as the matching key:

```python
used_outcomes = set()
for trade in ledger['trades']:
    sym = trade['symbol'].upper()
    entry = trade.get('entry_price') or trade.get('avg_entry')
    for i, outcome in enumerate(deduped):
        if i in used_outcomes:
            continue
        if outcome['symbol'].upper() == sym and entry and abs(entry - outcome['signal_entry']) / max(entry, 1) < 0.05:
            # MATCH: Update ledger trade with journal outcome
            trade['status'] = 'closed'
            trade['closed_at'] = outcome['closed_at']
            trade['exit_price'] = outcome['exit_price']
            trade['pnl'] = outcome['pnl_pct']
            qty = trade.get('qty', trade.get('quantity', 0))
            trade['pnl_usd'] = round(qty * outcome['exit_price'] - qty * entry, 2)
            trade['pnl_pct'] = outcome['pnl_pct']
            trade['exit_reason'] = outcome['exit_reason']
            used_outcomes.add(i)
            break
    else:
        # NO MATCH: trade is still open or missing from journal
        print(f'NO MATCH for {sym} entry={entry}')
```

### Step 4: Fix Portfolio ↔ Ledger Sync

**Case A: Ledger has OPEN trade but Portfolio missing position**
- Happened with VELVET trade_c453e07e46 (entry 0.709546 from 2026-06-27 briefing)
- Fix: Reconstruct position in portfolio.json from ledger trade, recalculate cash

**Case B: Portfolio has position but Ledger incorrectly shows CLOSED**
- Happened with RE trade_197f0ed43e — ledger matched to journal signal with DIFFERENT entry (0.626174 vs 0.616837)
- Fix: Revert ledger trade to OPEN (null out closed_at, exit_price, pnl, exit_reason)

```python
# Add missing position to portfolio
position = {
    'symbol': trade['symbol'],
    'name': trade['name'],
    'quantity': trade.get('qty', trade.get('quantity', 1.0)),
    'entry_price': trade['entry_price'],
    'allocated': round(trade.get('qty', trade.get('quantity', 1.0)) * trade['entry_price'], 2),
    'current_price': trade['entry_price'],
    'stop': trade.get('stop_loss', trade.get('stop')),
    'target': trade.get('take_profit', trade.get('target')),
    'pnl_usd': 0.0,
    'pnl_pct': 0.0,
    'status': 'open',
    'trade_id': trade['trade_id'],
    'opened_at': trade['opened_at'],
    'strategy_id': 'legacy',
    'strategy_snapshot': {},
    'bias': 'bullish',
    'highest_price': trade['entry_price'],
    'lowest_price': None,
    'trailing_stop': None,
    'trailing_activated': False
}
portfolio['positions'][trade['symbol']] = position
portfolio['cash'] = round(portfolio['cash'] - position['allocated'], 2)
```

### Step 5: Run M2M Update to Validate

```bash
cd /home/ubuntu/crypto-trading-ai && python3 trading-advisor/scripts/paper_trader.py --update --summary
```

Verify:
- Open positions match between portfolio and ledger (both OPEN)
- Closed trades in ledger match journal outcomes exactly
- P&L calculations are consistent (position quantity × price diff = ledger pnl_usd)

### Step 6: Final Verification Commands

```bash
# 1. Check portfolio positions
python3 -c "
import json
with open('trading-advisor/reports/paper_trading/portfolio.json') as f:
    p = json.load(f)
for sym, pos in p['positions'].items():
    print(f'{sym}: entry={pos[\"entry_price\"]} current={pos[\"current_price\"]} qty={pos[\"quantity\"]} pnl={pos[\"pnl_pct\"]}%')
"

# 2. Check ledger trades
python3 -c "
import json
with open('trading-advisor/reports/paper_trading/ledger.json') as f:
    l = json.load(f)
for t in l['trades']:
    print(f'{t[\"symbol\"]}: status={t[\"status\"]} entry={t[\"entry_price\"]} exit={t.get(\"exit_price\")}')
"

# 3. Run summary
cd /home/ubuntu/crypto-trading-ai && python3 trading-advisor/scripts/paper_trader.py --update --summary
```

### Cash Reconciliation Diagnostic

When the portfolio shows an unexplained cash gap (e.g., starting $10,000 → cash $9,367 while closed-trade PnL sums to only +$1.07), run this trace:

```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -c "
import json

# Load portfolio and ledger
with open('reports/paper_trading/portfolio.json') as f:
    pf = json.load(f)
with open('reports/paper_trading/ledger.json') as f:
    lg = json.load(f)

start = pf.get('starting_capital', 10000.0)
cash = pf.get('cash', 0.0)
print(f'Starting capital: \${start:.2f}')
print(f'Current cash:     \${cash:.2f}')
print(f'Gap:              \${cash - start:+.2f}')
print()

# Trace closed trades
total_realized = 0.0
for t in lg['trades']:
    if t.get('status') in ('closed',) or t.get('closed_at'):
        pnl = t.get('pnl_usd') or 0
        total_realized += pnl
        sym = t.get('symbol', '?')
        qty = t.get('qty') or t.get('quantity') or 1.0
        alloc = t.get('entry_price', 0) * qty
        print(f'  CLOSED {sym}: alloc=\${alloc:.2f}  pnl=\${pnl:+.2f}')

print(f'Sum of realized PnL: \${total_realized:+.2f}')
print(f'Expected cash:       \${start + total_realized:.2f}')
print(f'Phantom loss:        \${cash - (start + total_realized):+.2f}')
print()

# Check open trades in ledger (allocated but not in portfolio)
for t in lg['trades']:
    if t.get('status') == 'opened':
        sym = t.get('symbol', '?')
        qty = t.get('qty') or t.get('quantity') or 0
        entry = t.get('entry_price') or 0
        alloc = qty * entry
        print(f'  OPEN {sym}: qty={qty:.2f} entry=\${entry:.6f} alloc=\${alloc:.2f}')
print()

# Check if open trades exist in portfolio
positions = pf.get('positions', {})
ledger_open = [t for t in lg['trades'] if t.get('status') == 'opened']
for t in ledger_open:
    sym = t.get('symbol', '').upper()
    if sym not in positions:
        print(f'  ⚠️  {sym} is OPEN in ledger but MISSING from portfolio (phantom position)')
"
```

## Critical Matching Rules

1. **One-to-one matching**: Each journal outcome matches at most one ledger trade. Use a `used_outcomes` set to prevent double-matching.
2. **±5% entry price tolerance**: Match on `abs(ledger_entry - journal_signal_entry) / max(ledger_entry, 1) < 0.05`
3. **Symbol case-insensitive**: Compare `.upper()` on both sides
4. **Revert incorrect matches**: If a ledger trade was matched to a journal outcome with a different entry price, revert to OPEN status
5. **Journal is source of truth**: When ledger and journal disagree, journal wins for closed trades

## Common Mismatch Patterns Seen

| Pattern | Detection | Fix |
|---------|-----------|-----|
| Briefing trade entry ≠ Backtest signal entry | Ledger entry price doesn't match any journal signal_entry ±5% | Keep as OPEN, add to portfolio if missing |
| Backtest validated 3× same signal | Journal has 3 outcomes with identical (symbol, signal_entry, exit_price) | Dedup journal outcomes before matching |
| Ledger has legacy schema (`qty`, `stop_loss`) | Keys differ from paper_trader schema (`quantity`, `stop`) | Use `.get('qty', trade.get('quantity'))` pattern |
| Portfolio missing position from ledger | `portfolio['positions']` empty but ledger has `status=opened` | Reconstruct from ledger, deduct from cash |
| **Two-directory drift** | Verified data in `/crypto-trading-ai/trading-advisor/reports/paper_trading/` differs from `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/` | After reconciliation, `cp` both portfolio.json and ledger.json to skill directory; M2M cron runs from skill directory |
| **Briefing trade hit target after backtest already closed it** | Journal shows backtest outcome (exit=0.6542) then later live M2M outcome (exit=1.78) for same symbol with DIFFERENT entry prices | Match by entry price proximity; briefing trade (0.709546) ≠ backtest signal (0.605781). Both can exist as separate trades |
| **Journal signal entry ≠ Ledger trade entry for same symbol** | RE: journal signal_entry=0.626174, ledger entry=0.616837 (different briefing runs) | Match by entry price ±5%; if no match, treat as separate independent trades |
| **Phantom cash drain from small-ticket trades** | Ledger shows qty=1.0 trades (allocations $0.37–$0.72) but portfolio cash dropped $633+ from $10,000. Sum of closed-trade realized PnL is ~$1.07, not -$633. | Early trades may have been entered manually in ledger with qty=1 but the portfolio deducted larger allocations (~$500 each via 5% rule). The gap between ledger debits+credits and actual portfolio cash change is the phantom drain. Reconstruct real allocations from portfolio.json history or restore from backup. |
| **Position opened by briefing but never persisted to portfolio** | Ledger shows `status=opened` with proper 5%-allocation qty (e.g., SYN qty=449.38, entry=$0.416721, alloc=$187.27) but no matching entry in EITHER portfolio.json copy. | The position was created by `open_today_from_briefing()` but portfolio.json at that path was overwritten by a subsequent M2M run before the position was persisted. Check ledger for orphaned open trades, then either inject into portfolio or purge from ledger. |
| **M2M overwriting positions between diagnostic reads** | First `cat portfolio.json` shows position RE with cash=$9,187.12; second read moments later shows no positions and cash=$9,367.25 | The M2M cron (every 15m) ran between reads and closed the position. Check cron timestamps against your reads. Account for ongoing M2M activity during any multi-step diagnostic — data is live, not snapshotted. |

## Automation Note

This reconciliation should be automated in `scripts/audit_equity.py`. The manual workflow above documents the exact logic that the audit script should implement for reproducible verification.
