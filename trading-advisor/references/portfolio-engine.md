# Portfolio Engine Architecture

`strategy/portfolio_engine.py` — correlation-aware sizing, drawdown limits, exposure gating, and calibration health feedback.

## Data Flow

```
portfolio.json ──→ load_portfolio()
ledger.json    ──→ load_ledger()
journal.db     ──→ journal_performance()
CoinGecko OHLC ──→ fetch_daily_returns() → _pearson()
research-calibrations.json ──→ _load_calibrations()
                                         ↓
                              portfolio_penalty(symbol, score) → (multiplier, reasons)
                              calibration_health() → (lines[], score)
                              suggest_adjustments() → [strings]
```

## Public API

### `portfolio_penalty(proposed_symbol=None, proposed_score=0.0)`
Returns `(multiplier 0.0-1.0, reasons[])`.
Checks in order: concurrency gate → drawdown gate → proportional drawdown penalty → correlation penalty.
If the concurrency or drawdown hard gate fires, returns `(0.0, [reason])` immediately.

### `journal_performance(days=30)`
Reads `strategy/journal.db` performance table (most recent snapshot) + raw outcomes table.
Returns dict with: win_rate, profit_factor, avg_pnl_pct, avg_win_pct, avg_loss_pct,
stop_hit_rate, target_hit_rate, trailing_stop_rate, expired_rate, total_closed.

### `calibration_health()`
Compares journal_performance() against research-calibrations.json thresholds across 6 dimensions.
Returns `(lines[], score)` — score is 0.0-1.0, lines is markdown-ready content.

### `suggest_adjustments()`
Returns action strings when empirical data diverges from calibrations.
Requires ≥5 closed trades; otherwise returns a single "insufficient data" message.

### `compute_drawdown(portfolio, ledger)`
Reads portfolio.json for cash + open positions, ledger for closed P&L.
Returns `(current_equity, peak_equity, drawdown_pct)`.

### `get_pair_correlation(sym_a, coin_id_a, sym_b, coin_id_b, days=30)`
Fetches CoinGecko OHLC, computes Pearson r. Rate-limited at 6s per call, cached per symbol.

## Integration Points

- `briefing.py simple_rules()`: lazy-loaded via `_lazy_load_portfolio_engine()`, called after trap filters and before score < 25 gate. Writes `portfolio_note` into candidate dict.
- `briefing.py render_compact_briefing()`: reads `candidate["portfolio_note"]` and shows `- Portfolio: <reason>` when the penalty is active.
- `orchestrator.py build_digest()`: calls `calibration_health()` and `suggest_adjustments()` after Phase 6, writes `## Research Calibration Health` block.

## Lazy-Load Pattern

```python
# In briefning.py — avoids circular imports and module-level CG calls
PORTFOLIO_ENGINE = None

def _lazy_load_portfolio_engine():
    global PORTFOLIO_ENGINE
    if PORTFOLIO_ENGINE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("portfolio_engine", _PORTFOLIO_ENGINE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        PORTFOLIO_ENGINE = mod
    return PORTFOLIO_ENGINE
```

## Calibration Parameters

All under `research-calibrations.json` → `"portfolio"`:

| Key | Default | Effect |
|---|---|---|
| `concurrency_max` | 3 | Hard gate — no new positions above this |
| `drawdown_limit_pct` | 10.0 | Hard gate — stops all trading at this drawdown |
| `drawdown_sizing_reduction_pct` | 50.0 | Max score reduction at drawdown limit (proportional scaling) |
| `max_exposure_pct` | 20.0 | Informational — not a hard gate |
| `correlation_threshold` | 0.70 | r ≥ this with any open position triggers penalty |
| `correlation_exposure_penalty` | 0.50 | Score × (1 - penalty) when correlation fired |
| `correlation_lookback_days` | 30 | OHLC window for correlation computation |

## Troubleshooting

- **`- Portfolio:` line never appears**: verify `_PORTFOLIO_ENGINE_PATH` resolves correctly. Run `python3 -c 'from scripts.briefing import _lazy_load_portfolio_engine; print(_lazy_load_portfolio_engine())'` from skill directory.
- **Drawdown is 0% with closed trades**: check if ledger trades have `pnl_usd` or `pnl` fields. Legacy-archived trades with null P&L don't contribute to drawdown.
- **Correlation never fires**: check if `portfolio.json` has open positions. With `"positions": {}`, the correlation branch is entirely skipped.
- **Calibration health score stuck at 0.9**: need ≥5 closed trades in the journal for full calibration validation. The `0.1` "insufficient data" penalty keeps it below 1.0.
