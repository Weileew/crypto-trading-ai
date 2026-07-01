## Paper Trading Optimization Philosophy

**Paper trading is a laboratory, not a portfolio.** The goal is to generate enough closed signals to tune the strategy. Never reduce signal volume during a losing streak — that starves the optimization engine.

| State | Signal Volume | M2M | Why |
|---|---|---|---|
| 🔶 COLD | **Maximize** | every 15m | More data → faster strategy tuning |
| ✅ NORMAL | Standard (3 runs/day) | every 30m | Steady state |
| 🟢 HOT | Standard | every 30m | Capture momentum |

**Only pause signals during CRITICAL drawdown** (≥10% in paper, or any real-money drawdown). In all other states, keep signals flowing. See `references/signal-optimization.md` for the full bottleneck analysis and parameter tuning guide.

## Paper Trading Pipeline

The paper trading system has **two data directories** that must stay in sync:

| Directory | Purpose |
|-----------|---------|
| `/home/ubuntu/crypto-trading-ai/trading-advisor/reports/paper_trading/` | Canonical verified data (audited, reconciled) |
| `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/` | Cron M2M runtime data (read by `paper-trading-m2m` every 10m) |

**After any manual reconciliation** (see `references/paper-trading-reconciliation.md`), always sync:
```bash
cp /home/ubuntu/crypto-trading-ai/trading-advisor/reports/paper_trading/*.json \
   /home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/
```
The `crypto-backup-refresh` cron (every 6h) handles this automatically, but manual verification should sync immediately.

## Files
- `reports/paper_trading/portfolio.json` — current positions, cash balance, equity
- `reports/paper_trading/ledger.json` — trade history log
- `reports/paper_trading/summary_YYYY-MM-DD.md` — daily summaries

## Reconciliation Workflow
See `references/paper-trading-reconciliation.md` for the complete step-by-step procedure to reconcile `portfolio.json`, `ledger.json`, and `journal.db` when discrepancies are discovered. This workflow was applied during the 2026-06-28 audit.

## Schema

### Position object (portfolio.json → positions → symbol)

```json
{
  "symbol": "btc",
  "name": "Bitcoin (BTC)",
  "bias": "bullish",
  "entry_price": 0.367899,
  "quantity": 100.0,
  "allocated": 36.79,
  "opened_at": "2026-06-27T...",
  "stop": 0.355000,
  "target": 0.396000,
  "status": "open",
  "current_price": 0.366644,
  "pnl_usd": -0.13,
  "pnl_pct": -0.34,
  "strategy_id": "tok-v2-20260627",
  "strategy_snapshot": { "screening": {...}, "risk": {...} },
  "highest_price": 0.372000,
  "lowest_price": null,
  "trailing_stop": 0.367500,
  "trailing_activated": true,
  "trailing_activation_pct": 2.0,
  "trailing_distance_pct": 1.5
}
```

### Trailing stop fields
- `bias`: "bullish" | "bearish" — determines which direction to trail
- `highest_price`: peak price since entry (bullish positions only, null for bearish)
- `lowest_price`: trough price since entry (bearish only, null for bullish)
- `trailing_stop`: active trailing stop level, or `null` before activation
- `trailing_activated`: `true` once profit exceeds `trailing_activation_pct`
- `trailing_activation_pct`: per-position profit threshold to arm trail (from strategy snapshot)
- `trailing_distance_pct`: per-position trail distance below/above peak/trough

### Schema gotcha: paper_executor bypasses paper_trader.open_position()

`paper_executor.open_trades()` writes directly to `portfolio.json` with its own dict schema, rather than calling `paper_trader.open_position()`. When adding new position fields (e.g. trailing stop fields), they MUST be added to BOTH `paper_trader.open_position()` AND `paper_executor.open_trades()` in the same patch. If only one is updated, positions opened via the executor will lack the new fields and the M2M update loop will operate with defaults instead.

## M2M Update Flow

```bash
# Cron job configuration
# ~/.hermes/scripts/paper-m2m-update.sh runs every 10m (no_agent mode)
# Calls: python3 scripts/paper_trader.py --update --summary
```

See `references/paper-trading-m2m-script.md` for complete cron script documentation including behavior, deliverable format, common issues, and verification commands.

```mermaid
flowchart TD
    A[cron (every 10m, no_agent=True)] --> B[~/.hermes/scripts/paper-m2m-update.sh]
    B --> C[python3 scripts/paper_trader.py --update --summary]
    C --> D[load_portfolio()]
    C --> E[update_mark_to_market(portfolio)]
    E --> F[current_price_map() — 1 CG /simple/price call]
    F --> G{For each position}
    G --> H[fixed stop check → close("stop-loss")]
    G --> I[fixed target check → close("target-hit")]
    G --> J[trailing stop check]
    J --> K[track highest_price/lowest_price]
    J --> L[activate at profit >= threshold]
    J --> M[tighten trail on new highs]
    J --> N[price < trail → close("trailing_stop")]
    E --> O[save_portfolio()]
    E --> P[save_ledger()]
    E --> Q[format_summary() — output with Trail column]
```

## Output Format (preferred UX)

The paper trading summary uses an emoji-dashboard layout for Telegram delivery:

```
📊 **Paper Trading**
💵 Cash: $9024.24  ·  💰 Equity: $9553.81  ·  📉 Return: -4.46%  ·  🎯 2 open  ·  💰 Start: $10000
📁 *legacy*: 🟢 2 · $+29.24
```

- **Summary bar** → single compact line with emoji indicators (📉📈 for return direction, 🎯 for open count, 💰💵 for cash/equity). Avoid stacked metric tables — one line is scannable, four rows is not.
- **Strategy P&L line** → per-strategy with 🟢/🔴/⚪ prefix so you can spot which strategy is performing at a glance.
- **Open positions table** → 4 columns only: `Symbol | Entry → Current | P&L | Trail`. The Strategy column is redundant (shown in summary). Entry→Current is rendered as `{entry} → **{current}**` to visualise price movement.
- **Closed trades table** → 5 columns: `Date | Symbol | Exit | P&L | Reason`. P&L gets a 🟢/🔴/⚪ prefix.
- **P&L emojis**: 🟢 positive, 🔴 negative, ⚪ flat/zero.
- **Trailing stop**: 🔒 $price when active, blank otherwise.
- **Section headers** → bold with emoji: `**🟢 Open Positions**`, `**📋 Recently Closed**`.
- **No raw dollar/P&L column split** — the P&L column shows the emoji + percentage; the dollar value is absorbed into the summary bar.

### HTML Dashboard Image Delivery

Telegram tables have alignment issues with multi-column data. For the M2M cron, an alternative delivery method generates an HTML dashboard and serves it as a screenshot image:

1. Run `python3 scripts/paper_trader.py --update --summary` to get current state
2. Read `portfolio.json`, `ledger.json`, and `journal.db` outcomes
3. Generate a self-contained dark-mode HTML dashboard (at `reports/paper_trading_dashboard.html`)
4. Start a local HTTP server on 127.0.0.1:8899
5. Use `browser_navigate` + `browser_vision` to screenshot
6. Deliver the image via `MEDIA:<path>` in the cron response

The HTML dashboard includes:
- 4 summary cards (Equity, Cash, Return, Open count) with red/amber/green coloring
- 6 metrics cards (Win Rate, Profit Factor, Avg P&L, Avg Win, Avg Loss, Total Signals)
- Full closed trades table from journal outcomes (not ledger)
- Best/worst/streak footer bar

## Bug History

### Bug 1: current_price_map key mismatch (2026-06-27)
Keys returned as lowercase CG IDs but looked up by uppercase portfolio symbols → all positions showed 0% P&L.
**Fix**: reverse-map via `cgid_to_orig`.

### Bug 2: float("?") crash (2026-06-27)
`update_mark_to_market()` called `float(pos["stop"])` on strings like `"?"` → ValueError crashed the entire M2M loop.
**Fix**: `_safe_float()` helper + `try/except continue`.

### Bug 3: _safe_price parser failure (2026-06-27)
`_safe_price("0.3973 (+8%)")` returned None because `float()` can't parse parenthetical annotations.
**Fix**: strip `(...)` suffix and `near`/`~` prefixes before `float()`.

### Bug 4: Paper_executor schema drift (2026-06-27)
`paper_executor.open_trades()` wrote positions with `stop_loss`/`take_profit` keys while `paper_trader.update_mark_to_market()` read `stop`/`target` keys → trailing stop and fixed stop both silently skipped.
**Fix**: Unify to `stop`/`target` keys. Normalization in `_normalize_position()` handles both old and new keys.

### Bug 5: M2M closed positions not persisted (2026-06-27 — precise root cause)

`paper_trader.py --update` computed closed positions in memory via `update_mark_to_market()` but **never** called `save_portfolio()` or `save_ledger()`. The `--update` branch in `main()` had:
- `update_mark_to_market(portfolio)` — modifies dict in memory
- `_sync_closed_to_journal(closed)` — writes to journal.db
- No save calls — portfolio.json and ledger.json unchanged on disk

Result: every M2M cron tick re-closed the same positions (portfolio still had them on next load) and re-synced to journal, inflating journal.db with duplicates.

**Fix**: `save_portfolio(portfolio)` and `save_ledger(ledger)` are now called immediately after the update block, before any conditional early-return.

### Bug 6: `--update` fell through to default path (2026-06-27)

When running `python3 scripts/paper_trader.py --update` (no `--summary`), the `--update` block had no `return`. Execution fell through to the default path, which ran `update_mark_to_market()` a second time — double M2M on the same tick.

**Fix**: early-return after the update block when neither `--summary` nor `--paper-open` is set:
```python
if args.summary:
    print(format_summary(portfolio, ledger))
    return
if not args.paper_open:
    return
```

### Bug 7: Closed trades table header/column mismatch in `format_summary()` (2026-06-27)

The `Recent closed trades` Markdown table had:
- Header: `| Recent closed trades |` (single pseudo-column)
- Divisor: `| --- | --- |` (2-column separator)
- Data rows: 5+ columns with raw `entry=xxx` strings from legacy ledger entries

Telegram mangled this into unreadable output.

**Fix**: proper 6-column table:
```
| Closed At | Symbol | Exit | P&L ($) | P&L % | Reason |
| --- | --- | --- | --- | --- | --- |
```
Exit price and reason are explicit columns. P&L% suppressed when empty.  
**Rule**: every `format_summary()` table must have header column count === divisor column count === every data row column count.

### Bug 8: Closed trades table blank when ledger has no closed entries (2026-06-27)

`format_summary()` rendered nothing under `Recent closed trades` if `ledger.json` had no closed entries, even though `journal.db` outcomes existed. That hid post-close audit evidence.

**Fix**: add a journal fallback in `paper_trader.py --summary` that injects recent `outcomes` joined with `signals.symbol` into the same `Recent closed trades` table.

### Reconciliation rule

- Prefer `journal.db` outcomes when `ledger.json` and `portfolio.json` disagree.
- `journal.db` is append-only and auditable by signal ID; use it as the source of truth for closed trades.
- Reproducible audit commands: `python3 scripts/paper_trader.py --update --summary` and `python3 scripts/audit_equity.py`.

## Current Audit State (2026-06-28 — this session)

**Portfolio Status:**
- Starting capital: $10,000
- Cash: $9,380.63
- Equity: $9,577.09
- Return: -4.23%
- Open positions: 1 (RE, legacy strategy, +2.64%, trailing stop armed at $0.6235)

**Ledger State:**
- 5 open trades recorded (VELVET×2, MAGMA, SKYAI, RE) — mixed legacy/new schema
- Legacy trades use `qty`, `stop_loss`, `take_profit` keys
- Recent RE trade uses correct `stop`/`target` keys
- No closed trades in ledger (all show `"status": "opened"`)

**Journal State (source of truth):**
- 9 closed trades recorded (outcomes table)
- Win rate: ~44% (4 wins, 5 losses from visible data)
- Exit reasons: `backtest_target` (3 VELVET), `backtest_stop` (3 MAGMA), `trailing_stop` (1 RE), `target-hit` (1 SYRUP), `stop-loss` (1 SKYAI)
- P&L range: -5.29% to +8.03%

**Key Observations:**
1. Ledger positions (5) ≠ Portfolio positions (1) — legacy positions in ledger were closed via journal but never removed from ledger.json
2. Portfolio only shows RE (new position from 2026-06-28 briefing) — older positions were closed by M2M but ledger not cleaned
3. Journal DB is accurate; ledger has stale "opened" status for closed positions
4. The -4.23% equity drawdown is primarily cash drag (only ~$191 deployed of $10k capital)

**Action Items:**
- Run `python3 scripts/audit_equity.py` for full reconciliation
- Consider purging stale ledger entries that have journal outcomes
- Monitor if portfolio concurrency limit (3) is blocking new entries


## Reconciliation Workflow (2026-06-28 — Complete Procedure)

This is the step-by-step workflow used to fully reconcile portfolio.json, ledger.json, and journal.db after discovering discrepancies.

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

### Critical Matching Rules

1. **One-to-one matching**: Each journal outcome matches at most one ledger trade. Use a `used_outcomes` set to prevent double-matching.
2. **±5% entry price tolerance**: Match on `abs(ledger_entry - journal_signal_entry) / max(ledger_entry, 1) < 0.05`
3. **Symbol case-insensitive**: Compare `.upper()` on both sides
4. **Revert incorrect matches**: If a ledger trade was matched to a journal outcome with a different entry price, revert to OPEN status
5. **Journal is source of truth**: When ledger and journal disagree, journal wins for closed trades

### Common Mismatch Patterns Seen

| Pattern | Detection | Fix |
|---------|-----------|-----|
| Briefing trade entry ≠ Backtest signal entry | Ledger entry price doesn't match any journal signal_entry ±5% | Keep as OPEN, add to portfolio if missing |
| Backtest validated 3× same signal | Journal has 3 outcomes with identical (symbol, signal_entry, exit_price) | Dedup journal outcomes before matching |
| Ledger has legacy schema (`qty`, `stop_loss`) | Keys differ from paper_trader schema (`quantity`, `stop`) | Use `.get('qty', trade.get('quantity'))` pattern |
| Portfolio missing position from ledger | `portfolio['positions']` empty but ledger has `status=opened` | Reconstruct from ledger, deduct from cash |
| **Two-directory drift** | Verified data in `/crypto-trading-ai/trading-advisor/reports/paper_trading/` differs from `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/` | After reconciliation, `cp` both portfolio.json and ledger.json to skill directory; M2M cron runs from skill directory |
| **Briefing trade hit target after backtest already closed it** | Journal shows backtest outcome (exit=0.6542) then later live M2M outcome (exit=1.78) for same symbol with DIFFERENT entry prices | Match by entry price proximity; briefing trade (0.709546) ≠ backtest signal (0.605781). Both can exist as separate trades |
| **Journal signal entry ≠ Ledger trade entry for same symbol** | RE: journal signal_entry=0.626174, ledger entry=0.616837 (different briefing runs) | Match by entry price ±5%; if no match, treat as separate independent trades |

### Automation Note

This reconciliation should be automated in `scripts/audit_equity.py`. The manual workflow above documents the exact logic that the audit script should implement for reproducible verification.

## Position Close Reasons

| reason | Trigger | Summary display |
|--------|---------|----------------|
| `stop-loss` | Price <= fixed stop | `🔴 stop` |
| `target-hit` | Price >= fixed target | `🟢 target` |
| `trailing_stop` | Price <= trailing stop level | `🟡 trail` |
| `manual` | User/api call | `manual` |
