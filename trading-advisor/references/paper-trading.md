# Paper Trading Pipeline

## Files
- `reports/paper_trading/portfolio.json` — current positions, cash balance, equity
- `reports/paper_trading/ledger.json` — trade history log
- `reports/paper_trading/summary_YYYY-MM-DD.md` — daily summaries

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

```
cron (every 30m, no_agent=True)
  └─ ~/.hermes/scripts/paper-m2m-update.sh
       └─ python3 scripts/paper_trader.py --update --summary
            ├─ load_portfolio()              # load from JSON
            ├─ update_mark_to_market(portfolio)
            │    ├─ current_price_map()      # 1 CG /simple/price call
            │    └─ for each position:
            │         ├─ fixed stop check   → close("stop-loss")
            │         ├─ fixed target check  → close("target-hit")
            │         ├─ trailing stop check:
            │         │    ├─ track highest_price
            │         │    ├─ activate at profit >= threshold
            │         │    ├─ tighten trail on new highs
            │         │    └─ price < trail  → close("trailing_stop")
            ├─ save_portfolio()              # persist closed positions
            ├─ save_ledger()                 # persist trade log
            └─ format_summary()              # output table with Trail column
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

## Position Close Reasons

| reason | Trigger | Summary display |
|--------|---------|----------------|
| `stop-loss` | Price <= fixed stop | `🔴 stop` |
| `target-hit` | Price >= fixed target | `🟢 target` |
| `trailing_stop` | Price <= trailing stop level | `🟡 trail` |
| `manual` | User/api call | `manual` |
