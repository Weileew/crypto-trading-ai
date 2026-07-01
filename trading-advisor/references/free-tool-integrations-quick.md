# TOK Free Tool Integrations - Quick Reference

## 7 Tools Integrated (All Free, No Registration)

| Tool | Version | Use Case |
|------|---------|----------|
| **polars** | 1.42.1 | 10-50× faster 500-coin scans |
| **duckdb** | 1.5.4 | Analytical SQL on journal.db |
| **vectorbt** | 1.0.0 | Vectorized backtesting |
| **empyrical** | 0.5.12 | Sharpe, MaxDD, Calmar, Sortino, Omega |
| **optuna** | 4.9.0 | Bayesian parameter optimization |
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python indicators |
| **ruff/mypy/pre-commit** | Latest | Lint, type-check, git hooks |

## Key Integration Points

### free_data.py
- `get_simple_technicals()` → pandas-ta-classic RSI/EMA/SMA
- `markets_to_polars()` + `compute_candidate_scores_polars()` → 10-50× faster scoring
- `export_markets_parquet()` / `scan_markets_parquet()` → lazy Parquet I/O
- `get_regime_performance()`, `get_win_loss_by_symbol()`, `get_performance_by_source()` → DuckDB analytics
- `get_portfolio_correlation_matrix()` → correlation via DuckDB+Polars

### signal_validator.py
- `backtest_vectorbt()` → vectorbt Portfolio.from_signals with sl_stop/tp_stop/sl_trail
- `_empyrical_metrics()` → industry-standard risk metrics
- `summarize_with_empyrical()` → enhanced signal summary
- `run_vectorbt_batch()` → batch backtest multiple signals

### briefing.py
- `_regime_bias()` → enhanced with DuckDB empirical regime performance

### portfolio_engine.py
- `journal_performance_empyrical()` → journal perf with empyrical metrics
- `calibration_health_empyrical()` → health check with Sharpe/Calmar/Sortino/Omega/VaR
- `get_correlation_matrix()` → correlation via free_data
- `optimize_portfolio_params()` → Optuna optimization of concurrency/DD/correlation params
- `suggest_params_file_updates()` → generates params.json suggestions

### parameter_optimizer.py
- `optimize_with_optuna()` → Bayesian optimization of screening thresholds
- `walk_forward_optimize()` → rolling train/test validation
- `save/load_optuna_study()` → study persistence

## Config Files Created
- `requirements-tok.txt` — pip deps with comments
- `pyproject.toml` — ruff, mypy, pytest, pre-commit config
- `.pre-commit-config.yaml` — git hooks

## Common Fixes
- DuckDB timestamp: `epoch(CAST(REPLACE(closed_at, 'T', ' ') AS TIMESTAMP)) * 1000`
- vectorbt v1.0: `sl_stop` (not `sl_stop`), `tp_stop`, `sl_trail` (not `trailing_stop`)
- Optuna: add `_noise` trial for smooth surface