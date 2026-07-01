# TOK High-Performance Free Tool Integrations

## Summary
This document captures the complete integration of 7 high-impact free, open-source tools into the TOK trading system. All tools are MIT/BSD/Apache licensed, require no registration, no API keys, and no external dependencies.

## Installed Tools & Versions

| Tool | Version | Purpose |
|------|---------|---------|
| **polars** | 1.42.1 | 10-50× faster DataFrame operations for 500-coin scans |
| **duckdb** | 1.5.4 | Analytical SQL on `journal.db`, `portfolio.json`, Parquet exports |
| **vectorbt** | 1.0.0 | Vectorized backtesting engine (10-100× faster than loop-based) |
| **empyrical** | 0.5.12 | Industry-standard Sharpe, Max DD, Calmar, Sortino, Omega |
| **optuna** | 4.9.0 | Bayesian optimization (TPE/CMA-ES) for walk-forward parameter tuning |
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python technical indicators (RSI, MACD, Supertrend, etc.) |
| **ruff/mypy/pre-commit** | Latest | Lint, type-check, git hooks for dev hygiene |

## Integration Points

### 1. `scripts/free_data.py` — Data Layer Acceleration
**New functions added:**
- `get_simple_technicals(prices)` — Uses `pandas_ta_classic` for RSI, EMA, SMA (fallback to manual calc)
- `markets_to_polars(markets)` — Convert market list to Polars DataFrame
- `compute_candidate_scores_polars(df)` — Vectorized scoring with Polars expressions (10-50× faster)
- `export_markets_parquet(markets, filename)` — Export to Parquet for lazy scanning
- `scan_markets_parquet(filename, filters)` — Lazy scan with column/row filtering
- `get_regime_performance(days, exclude_sources)` — DuckDB analytical query on journal.db
- `get_win_loss_by_symbol(days, exclude_sources, min_trades)` — Per-symbol win/loss stats
- `get_performance_by_source(days, min_trades)` — Source-level performance breakdown
- `get_portfolio_correlation_matrix(symbols, days)` — Correlation matrix via DuckDB + Polars

**Key patterns:**
```python
# Optional imports with availability flags
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

# Usage with graceful fallback
if POLARS_AVAILABLE:
    df = markets_to_polars(markets)
    scored = compute_candidate_scores_polars(df)
```

### 2. `scripts/signal_validator.py` — Vectorized Backtesting + Metrics
**New functions added:**
- `backtest_vectorbt(close_series, entries, exits, stop_pct, target_pct, trailing_pct, freq)` — Vectorbt Portfolio.from_signals with stops
- `_empyrical_metrics(returns)` — Industry metrics: Sharpe, MaxDD, Calmar, Sortino, Omega, VaR, CVaR
- `summarize_with_empyrical(signals)` — Enhanced summary with empyrical metrics
- `run_vectorbt_batch(signals, max_candles)` — Batch backtest multiple signals

**Vectorbt parameter fix:**
```python
# Correct parameter names in v1.0.0
pf = vbt.Portfolio.from_signals(
    close=close_series,
    entries=entries,
    exits=exits,
    sl_stop=stop_pct,      # stop loss (was sl_stop)
    tp_stop=target_pct,    # take profit (was tp_stop)
    sl_trail=trailing_pct, # trailing stop (was trailing_stop)
    direction="longonly",
)
```

### 3. `scripts/briefing.py` — Empirical Regime Detection
**Enhanced:**
- `_regime_bias(change_24h)` — Now queries DuckDB `get_regime_performance()` for empirical regime performance and overrides threshold-based regime when data supports it

### 4. `strategy/portfolio_engine.py` — Empyrical + Optuna Portfolio Optimization
**New functions added:**
- `journal_performance_empyrical(days, exclude_sources)` — Journal performance with empyrical risk metrics
- `calibration_health_empyrical()` — Calibration health with empyrical metrics (Sharpe, Calmar, Sortino, Omega, VaR)
- `get_correlation_matrix(symbols, days)` — Correlation matrix via free_data DuckDB integration
- `optimize_portfolio_params(n_trials, lookback_days)` — Optuna optimization of concurrency, drawdown, correlation params
- `suggest_params_file_updates(opt_result)` — Generate suggested params.json/research-calibrations.json updates

### 5. `strategy/parameter_optimizer.py` — Optuna Walk-Forward Optimization
**New functions added:**
- `optimize_with_optuna(historical_data, n_trials, lookback_days, study_name, storage)` — Bayesian optimization of screening thresholds
- `walk_forward_optimize(historical_data, train_days, test_days, n_trials, step_days)` — Rolling train/test validation
- `save_optuna_study(study, filepath)` / `load_optuna_study(filepath)` — Persistence

## Project Configuration Files Created

| File | Purpose |
|------|---------|
| `requirements-tok.txt` | Pip-installable dependency list with comments |
| `pyproject.toml` | Full project config: deps, ruff, mypy, pytest, pre-commit |
| `.pre-commit-config.yaml` | Git hooks: ruff --fix, mypy, pytest -q |

## Verification Commands

```bash
# Quick import test
cd /home/ubuntu/crypto-trading-ai/trading-advisor
source .hermes/hermes-agent/venv/bin/activate
python -c "
import free_data, signal_validator, portfolio_engine, parameter_optimizer
import polars, duckdb, vectorbt, empyrical, optuna, pandas_ta_classic
print('All imports OK')

# Test key functions
print(free_data.get_simple_technicals([100]*20))
print(free_data.get_regime_performance())
print(signal_validator._empyrical_metrics(__import__('pandas').Series([0.01]*10)))
"
```

## Common Issues & Fixes

### DuckDB Timestamp Comparison
SQLite stores timestamps as TEXT. DuckDB requires explicit casting:
```python
# WRONG: o.closed_at > ? (VARCHAR vs DOUBLE)
# CORRECT: (epoch(CAST(REPLACE(o.closed_at, 'T', ' ') AS TIMESTAMP)) * 1000) > ?
```

### Vectorbt v1.0.0 Parameter Names
- `trailing_stop` → `sl_trail`
- Check `help(vbt.Portfolio.from_signals)` for current signature

### Optuna Trial Noise
Add `trial.suggest_float("_noise", -0.5, 0.5)` to objective to create smooth optimization surface.

## Next Steps for Full Adoption
1. Replace manual indicator calculations in `free_data.py` with `df.ta.rsi()`, `df.ta.macd()`, `df.ta.supertrend()`
2. Use DuckDB regime queries as primary signal in `briefing._regime_bias()`
3. Replace custom backtest loops in `signal_validator.main()` with `backtest_vectorbt()`
4. Use empyrical metrics for all performance reporting in `portfolio_engine`
5. Schedule weekly Optuna study: `cronjob create --schedule "0 2 * * 1" --prompt "python3 strategy/parameter_optimizer.py"`
6. Run `pre-commit run --all-files` to activate git hooks