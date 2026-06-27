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

### Bug 5: Trailing stop → journal gap (known, unfixed)
`update_mark_to_market()` closing via `trailing_stop` removes the position from portfolio.json but does not update the strategy journal. The journal signal stays "open" until manually reconciled. Orchestrator's `phase_validate_open` only checks fixed target/stop — trailing closures are invisible to the journal.
**Impact**: Journal win rate undercounts, open signal count overcounts.
**Workaround**: Run `strategy_journal.py close-signal` manually for trailed-out positions, or wait for a reconciliation fix.

## Position Close Reasons

| reason | Trigger | Summary display |
|--------|---------|----------------|
| `stop-loss` | Price <= fixed stop | `🔴 stop` |
| `target-hit` | Price >= fixed target | `🟢 target` |
| `trailing_stop` | Price <= trailing stop level | `🟡 trail` |
| `manual` | User/api call | `manual` |
