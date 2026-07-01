# Paper Trading Data Model

## Open/Close Pairing Protocol

Every trade in the paper trading system must follow a strict **open→close lifecycle** with a persistent `trade_id` linking both states. This is the single most critical invariant for simulation accuracy.

### The Lifecycle

```
paper_executor / open_position()           M2M update_mark_to_market()
      │                                            │
      │  Creates ledger entry                      │
      │  with trade_id + status:"opened"           │
      │  Adds to portfolio[symbol]                 │
      │  with matching trade_id                    │
      ├─────────────────────►──────────────────────┤
      │                                            │
      │                              close_position():
      │                              1. Adds trade_id to closed dict
      │                              2. Deletes from portfolio[symbol]
      │                              3. Returns {trade_id, exit_price, pnl, ...}
      │                                            │
      │  _sync_closed_to_ledger():                 │
      │    Matches closed dict to ledger entry     │
      │    by trade_id                              │
      │    Updates: status="closed"                 │
      │              closed_at, exit_price,         │
      │              pnl_usd, pnl_pct, exit_reason  │
      │                                            │
      │  _sync_closed_to_journal():                 │
      │    Records outcome in signal DB             │
      │◄──────────────────────┘
```

### Critical Rules

1. **trade_id must survive the close.** `close_position()` originally dropped `trade_id` from its return dict — the ledger was permanently broken. Every close position dict must include `"trade_id": pos.get("trade_id")`.

2. **Ledger close sync is mandatory.** After `update_mark_to_market()` returns closed positions, `main()` must call `_sync_closed_to_ledger(ledger, closed)` before `save_ledger()`. This function matches by trade_id and sets `status: "closed"` with exit data. Without this, trades show as permanently open.

3. **Every open path must create a complete ledger entry.** Both `--paper-open` in `main()` and `open_today_from_briefing()` create ledger entries. They MUST include: `trade_id`, `status: "opened"`, `side`, `closed_at: None`, `exit_price: None`, `pnl_usd: None`, `pnl_pct: None`.

4. **Portfolio dict stops at one position per symbol.** The portfolio `positions` dict is keyed by symbol string. Opening a second position with the same symbol overwrites the first — cash is debited for the second, but the first's cash allocation is lost. **Dedup guards** in both `open_position()` (returns None) and `paper_executor.py` (checks portfolio keys) prevent this.

### Dedup Guard Implementation

**In `paper_trader.py`'s `open_position()` (line ~295):**
```python
if any(k.upper() == symbol.upper() for k in (portfolio.get("positions") or {})):
    return None  # Case-insensitive: 'syn' == 'SYN'
```
⚠️ **Case sensitivity pitfall**: The portfolio dict keys preserve the case used at open time (e.g. `"SYN"` vs `"syn"`). A simple `symbol in portfolio["positions"]` check would miss `"SYN"` when looking for `"syn"`, creating a **duplicate third position** for the same coin. Always normalize both sides to uppercase before comparison.

**In `paper_executor.py`'s `open_trades()` (line ~153-176):**
```python
# Check both ledger (same date+symbol) and portfolio (any open for symbol)
existing_keys = [...(date, symbol) from ledger if status=="opened"]
portfolio_open_symbols = {s.upper() for s in (portfolio.get("positions") or {})}
...
if (date, rec["symbol"]) in existing_keys: skip
if rec["symbol"].upper() in portfolio_open_symbols: skip  # cross-day dedup
```

### Field Name Schema

The portfolio and ledger use different field names depending on which script last wrote them. Normalization happens on each load.

| Logical Field | paper_executor writes | paper_trader canonical (after normalize) |
|---|---|---|
| Stop loss | `stop_loss` | `stop` |
| Take profit | `take_profit` | `target` |
| Quantity | `quantity` | `quantity` (or `qty` in legacy) |
| Trade ID | `trade_id` | `trade_id` |

**Normalization** in `_normalize_position()`: `pos.get("stop") or pos.get("stop_loss") or pos.get("Stop")` — uses OR-fallback on every load, so both schemas work.

### Path Divergence Prevention

Two codebases can write to different `portfolio.json` files:

| Path | Used By | Active? |
|---|---|---|
| `~/.hermes/skills/trading-advisor/reports/paper_trading/` | M2M cron, paper_executor (from .hermes workdir) | ✅ Active |
| `~/crypto-trading-ai/trading-advisor/reports/paper_trading/` | paper_executor (stale copy in parallel repo) | ❌ Stale — replace with symlink |

**Fix:** Replace the stale copy with a symlink to the active one:
```bash
rm -rf ~/crypto-trading-ai/trading-advisor/reports/paper_trading
ln -s ~/.hermes/skills/trading-advisor/reports/paper_trading \
  ~/crypto-trading-ai/trading-advisor/reports/paper_trading
```

### Simulation Accuracy Checklist

- [ ] Every open ledger entry has `trade_id` and `status: "opened"`
- [ ] Every closed ledger entry has `status: "closed"` with exit price and PnL
- [ ] Portfolio `positions` dict has no duplicate symbols
- [ ] `paper_executor.py` and `paper_trader.py` write to the same `portfolio.json` (symlink verified)
- [ ] Cash sanity: `starting_capital + realized_pnl + unrealized_pnl ≈ equity`
- [ ] M2M summary shows no orphaned trades
- [ ] `close_position()` return dict includes `trade_id`

### Historical Issues Found (2026-06-29)

1. **Ledger never marked trades closed** — `close_position()` dropped `trade_id`, `main()` never updated the ledger. All 6 historical trades showed `status: "opened"` in the ledger even though 4 were closed.
2. **Two code paths created ledger entries without trade_id** — `--paper-open` and `open_today_from_briefing()` used a minimal schema missing `trade_id`, `status`, `side`.
3. **Early trades (06-26/27) used qty=1.0 but real 5% cash allocation** — Ledger records show $0.37-0.72 allocations, but the portfolio actually deployed ~$500 per trade. The -$633 cash gap is unrecoverable legacy data.
4. **Dual portfolio files** — paper_executor in the stale `crypto-trading-ai` repo wrote to a different `portfolio.json` than the M2M cron read. RE and SYN positions were orphaned.
5. **Entry price used recommended briefing price, not live market** — If the market moved between the briefing and execution, stop/target levels were wrong. E.g. recommended entry $0.60, stop $0.57 (-5%). Market at $0.62 → real stop distance = -8%. Fixed by adding `fetch_live_prices()` in paper_executor that queries CoinGecko before opening and adjusts stop/target proportionally (`stop_new = stop_recommended × live_price / entry_recommended`).
6. **Save order: ledger first, portfolio second** — If crash between saves, ledger has phantom "opened" trade that permanently blocks re-opening that symbol on that date. Fixed: always save portfolio first, ledger second.
7. **M2M notification script bugs** — Hardcoded $10k starting capital (fixed: read from `p.get('starting_capital')`); backtest_stop display bug (fixed: restore "Backtest " prefix after regex strip); no field safety (fixed: all `.get(key, default)`); double-quote heredoc escaping (fixed: switched to `<< 'PYEOF'`).
