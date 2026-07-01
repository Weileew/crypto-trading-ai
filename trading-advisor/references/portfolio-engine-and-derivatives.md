# Portfolio Engine & Derivatives Integration

Three new pipeline layers built in June 2026: portfolio-level risk management,
derivatives data signals, and a calibrations feedback loop.

## Layer 10: Portfolio Engine (`strategy/portfolio_engine.py`)

Three public functions exposed to the briefing pipeline:

### `portfolio_penalty(proposed_symbol, score) → (multiplier, reasons)`

Called per candidate in `simple_rules()` after trap filters. Multiplier is 0.0–1.0:

| Condition | Multiplier | Source |
|-----------|-----------|--------|
| Open positions ≥ concurrency_max (default 3) | 0.0 (gate) | research-calibrations.json → portfolio.concurrency_max |
| Drawdown ≥ drawdown_limit_pct (default 10%) | 0.0 (gate) | research-calibrations.json → portfolio.drawdown_limit_pct |
| 0% < drawdown < limit | 1.0 → 0.5 linearly | drawdown_pct / limit × reduction_pct |
| Proposed coin, r ≥ 0.70 with open position | Score × 0.50 | Correlation Pearson on 30d daily returns |
| No open positions, no drawdown | 1.0 | Default — no penalty |

### `calibration_health() → (lines[], score)`

Reads strategy journal DB, compares empirical performance against research calibrations.
Returns a markdown block and 0.0–1.0 score for the orchestrator digest.

### `suggest_adjustments() → list[str]`

Returns actionable tuning suggestions when empirical data diverges from calibrations.
Requires ≥5 closed signals in the journal to produce suggestions.

### Data Sources

- **Portfolio state**: `reports/paper_trading/portfolio.json` (open positions, cash)
- **Trade history**: `reports/paper_trading/ledger.json` (closed P&L)
- **Journal performance**: `strategy/journal.db` → `performance` table (win rate, PF, avg PnL)
- **Correlation**: CoinGecko OHLC (`/coins/{id}/ohlc`, 30d) — rate-limited at 6s, cached per-symbol

### Lazy Loading

`_lazy_load_portfolio_engine()` in `briefing.py` imports the module on first use. No disk/API activity at `briefing.py` import time.

## Layer 11: Derivatives Data (free_data.py)

Three Binance Futures public endpoints (no auth, no API key):

| Function | Endpoint | Returns |
|----------|----------|---------|
| `fetch_funding_rate(symbol, limit)` | `fapi.binance.com/fapi/v1/fundingRate` | Rate per 8h, annualized |
| `fetch_open_interest(symbol)` | `fapi.binance.com/fapi/v1/openInterest` | Current OI in contracts |
| `fetch_long_short_ratio(symbol, period, limit)` | `fapi.binance.com/futures/data/topLongShortPositionRatio` | Top trader L/S ratio |

### `interpret_funding_rate(rate_str) → (signal, icon, annualized_pct)`

| Rate (8h) | Signal | Icon | Annualized |
|-----------|--------|------|------------|
| > 0.001 | extreme positive | ⚠️ | > 164% |
| > 0.0001 | positive | 🟢 | > 55% |
| -0.0001 to 0.0001 | neutral | 🟡 | ±5% |
| < -0.0001 | negative | 🔴 | < -55% |
| < -0.001 | extreme negative | ⚠️ | < -219% |

### `fetch_derivatives_summary(symbol) → dict`

Bundles all three fetches + interpreted signals. Cached at module level in `briefing.py` via `_fetch_derivatives_once()`, so one Binance call per briefing run.

## Layer 12: Funding-Aware Score Adjustment (`briefing.py`)

`_funding_score_adjustment() → (points, reason)` — called once per `simple_rules()` run,
applied additively to every candidate's score:

| Condition | Adj | Reason |
|-----------|-----|--------|
| Funding extreme positive | -18 pts | squeeze risk — crowded longs |
| Funding positive | -5 pts | leverage elevated |
| L/S crowded long (>1.5) | -5 pts | additional penalty |
| Funding negative | +3 pts | shorts paying — reversal setup |
| Funding extreme negative | +8 pts | short squeeze setup |
| L/S crowded short (<0.67) | +5 pts | additional boost |
| Neutral funding + balanced L/S | 0 pts | no adjustment |

Points are additive, not multiplicative, so they directly shift the rank ordering.
A marginal 26-pt candidate drops to 8 in extreme funding — eliminated from top picks.
A 26-pt candidate rises to 34 in extreme negative — promoted for squeeze setups.

### Briefing Renderer Lines

All three layers produce visible lines in the compact briefing:

```
## Market Regime
- BTC funding: 🟡 neutral (5% annualized)
- BTC OI: $6,172,998,533
- Long/short: 1.23x (leaning long)

## Opportunities
1. Magma Finance (magma)
   - Score: 28.5
   - Portfolio: drawdown 4.4% → size 78%        (when penalty active)
   - Derivatives: funding positive — leverage elevated  (when adjustment active)
```

## Calibrations (`research-calibrations.json`)

New top-level keys added:

### `portfolio`
```json
{
  "concurrency_max": 3,
  "drawdown_limit_pct": 10.0,
  "drawdown_sizing_reduction_pct": 50.0,
  "max_exposure_pct": 20.0,
  "correlation_threshold": 0.70,
  "correlation_exposure_penalty": 0.50,
  "correlation_lookback_days": 30
}
```

### `derivatives`
```json
{
  "funding_extreme_positive": 0.001,
  "funding_positive": 0.0001,
  "funding_negative": -0.0001,
  "funding_extreme_negative": -0.001,
  "ls_crowded_long": 1.5,
  "ls_crowded_short": 0.67
}
```

## Pitfalls

- **Portfolio engine loads lazily**: `_lazy_load_portfolio_engine()` is a separate function. Do NOT import `strategy/portfolio_engine` at the top of `briefing.py` — it would create a circular import because `portfolio_engine.py` doesn't import from `briefing.py`, but the lazy pattern keeps file I/O off the import path.
- **Derivatives cache is process-scoped**: `_DERIVATIVES_CACHE` is set once per Python process. In cron runs this is fine; in long-running processes, clear it between briefing runs with `_DERIVATIVES_CACHE = None`.
- **Funding modifier is additive, not multiplicative**: It adds/subtracts points from the score, not multiplies. This means extreme funding can zero out marginal candidates but won't completely override strong ones (45-pt candidate → 27 pts even in extreme funding).
- **Correlation fetches are slow**: Each unique symbol pair triggers a CG OHLC call at 6s spacing. With 3 open positions + 3 candidates, that's up to 9 calls × 6s = 54s added to briefing runtime. The correlation branch is skipped entirely when there are no open positions (zero CG calls).
- **`portfolio_penalty(proposed=None)`**: pass `None` to get only the global (drawdown/concurrency) penalty without correlation checking. Used in contexts where per-symbol CG data isn't needed.
- **Paper executor bias format**: The compact briefing emits `"mean-reversion - bullish"` as the bias line. `paper_executor.py`'s `_canonical_bias()` now detects `"bullish"` / `"bearish"` as substrings — this must stay in sync with any future briefing format changes.

## Verification

```bash
# Test portfolio engine standalone
cd ~/.hermes/skills/trading-advisor
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from strategy.portfolio_engine import portfolio_penalty, calibration_health
mult, reasons = portfolio_penalty('magma', 30.0)
print(f'Penalty: {mult} — {\"; \".join(reasons)}')
lines, score = calibration_health()
print(f'Health: {score:.0%}')
"

# Test derivatives data
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from free_data import fetch_derivatives_summary
d = fetch_derivatives_summary('BTCUSDT')
print(f'{d[\"funding_icon\"]} {d[\"funding_signal\"]} ({d[\"annualized_pct\"]:.0f}%)')
"
```
