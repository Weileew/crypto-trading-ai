# High-Impact Free Tools Integration (2026-07-01)

All tools are free, open source (MIT/BSD/Apache), no registration, no API keys. Installed in the Hermes venv and integrated across the TOK codebase.

## Installed Tools

| Tool | Version | Purpose | Integrated In |
|------|---------|---------|---------------|
| **polars** | 1.42.1 | 10-50× faster DataFrames | `free_data.markets_to_polars()`, `compute_candidate_scores_polars()` |
| **duckdb** | 1.5.4 | Analytical SQL on `journal.db` | `free_data.get_regime_performance()`, `portfolio_engine.get_correlation_matrix()` |
| **vectorbt** | 1.0.0 | Vectorized backtesting | `signal_validator.backtest_vectorbt()` |
| **empyrical** | 0.5.12 | Industry-standard metrics | `signal_validator.summarize()`, `portfolio_engine.journal_performance()` |
| **optuna** | 4.9.0 | Hyperparameter optimization | `parameter_optimizer.optimize_with_optuna()`, `portfolio_engine.optimize_portfolio_params()` |
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python indicators | `free_data.get_simple_technicals()` |

## Integration Points

### `scripts/free_data.py`
```python
# DuckDB analytical queries
free_data.get_regime_performance()     # SELECT regime, AVG(pnl_pct) FROM jdb.outcomes ...
free_data.get_win_loss_by_symbol()     # Win/loss stats by symbol
free_data.get_performance_by_source()  # Performance by signal source

# Polars vectorized scoring
df = free_data.markets_to_polars(markets)
scored = free_data.compute_candidate_scores_polars(df)

# pandas-ta-classic indicators
indicators = free_data.get_simple_technicals(prices)
# Returns: rsi14, ema20, ema50, ema200, sma20
```

### `scripts/briefing.py`
```python
# Optional Polars-accelerated path in simple_rules() for 400+ markets
if len(markets) >= 400:
    df = free_data.markets_to_polars(markets)
    scored = free_data.compute_candidate_scores_polars(df)
    # Filter, apply portfolio/funding adjustments, return top 15

# DuckDB regime performance in _regime_bias()
perf = free_data.get_regime_performance()
# Uses best historical regime as tiebreaker for neutral volatility
```

### `scripts/signal_validator.py`
```python
# Vectorbt vectorized backtest
bt = signal_validator.backtest(candles, date, entry, stop, target, max_candles=30)
# Returns: exit_price, exit_reason, exit_date, entry_open, holding_candles

# Empyrical metrics in summarize()
summary = signal_validator.summarize(signals)
# Now includes: sharpe_ratio, max_drawdown, calmar_ratio, sortino_ratio, omega_ratio, annual_return, annual_volatility
```

### `strategy/portfolio_engine.py`
```python
# Empyrical metrics in journal_performance()
perf = portfolio_engine.journal_performance(days=30)
# Returns: win_rate, profit_factor, sharpe_ratio, max_drawdown, calmar_ratio, sortino_ratio, omega_ratio, annual_return, annual_volatility

# DuckDB correlation matrix
corr_matrix = portfolio_engine.get_correlation_matrix(days=30)

# Optuna portfolio parameter optimization
optuna_result = portfolio_engine.optimize_portfolio_params(n_trials=50)
# Returns: best_params (concurrency_max, drawdown_limit_pct, correlation_threshold, ...)
```

### `strategy/parameter_optimizer.py`
```python
# Optuna threshold optimization
optuna_result = parameter_optimizer.optimize_with_optuna(coins, n_trials=50)
# Optimizes: min_24h_change_pct, score_threshold
# Objective: win_rate * signal_bonus
```

## Files Created

| File | Purpose |
|------|---------|
| `requirements-tok.txt` | Complete dependency list with comments |
| `pyproject.toml` | Full project config (ruff, mypy, pytest, pre-commit) |
| `.pre-commit-config.yaml` | Git hooks configuration |

## Verification

All tools tested and working:
```python
import free_data, briefing, signal_validator, portfolio_engine, parameter_optimizer
import vectorbt, empyrical, optuna, polars, duckdb, pandas_ta_classic

# All imports succeed, all functions tested
```