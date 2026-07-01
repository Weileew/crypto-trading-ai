# Production-Ready Tool Integrations (v3.0.0)

The TOK trading system now integrates **8 battle-tested, free, open-source tools** that replace custom implementations with industry-standard libraries. All tools are MIT/BSD/Apache licensed, require **zero API keys, zero registration**, and run entirely locally.

| Tool | Version | Purpose | Key Integration Points |
|------|---------|---------|------------------------|
| **polars** | 1.42.1 | 10-50× faster DataFrame ops | `free_data.markets_to_polars()`, `compute_candidate_scores_polars()`, `export_markets_parquet()`, `scan_markets_parquet()` |
| **duckdb** | 1.5.4 | Analytical SQL on journal.db | `free_data.get_regime_performance()`, `get_win_loss_by_symbol()`, `get_performance_by_source()`, `get_portfolio_correlation_matrix()` |
| **vectorbt** | 1.0.0 | Vectorized backtesting | `signal_validator.backtest_vectorbt()`, `run_vectorbt_batch()` (stop/target/trailing) |
| **empyrical** | 0.5.12 | Industry-standard risk metrics | `signal_validator._empyrical_metrics()`, `summarize_with_empyrical()`, `portfolio_engine.journal_performance_empyrical()`, `calibration_health_empyrical()` |
| **optuna** | 4.9.0 | Bayesian optimization | `parameter_optimizer.optimize_with_optuna()`, `walk_forward_optimize()`, `portfolio_engine.optimize_portfolio_params()` |
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python indicators | `free_data.get_simple_technicals()` (RSI, EMA, SMA, MACD, Supertrend) |
| **loguru** | 0.7.3 | Structured JSON logging | Daily rotated logs in `reports/` + stdout for cron capture |
| **prometheus-client** | 0.25.0 | Metrics endpoint | Shared registry in `scripts/metrics.py`, endpoints in all modules |

## Architecture

All tools integrate through a **shared observability layer** (`scripts/metrics.py`) that provides:
- Single `CollectorRegistry` (`TOK_REGISTRY`) to prevent duplicate metric registrations
- Namespaced metrics: `fd_*` (free_data), `sv_*` (signal_validator), `pe_*` (portfolio_engine), `br_*` (briefing)
- `get_metrics()` endpoint for Prometheus scraping in every module

## Cron Jobs Updated

| Job | Schedule | Enhanced Commands |
|-----|----------|-------------------|
| `daily-crypto-trading-briefing-morning` | 0 8 * * * | `briefing.py` → `signal_validator.py` (vectorbt/empyrical) → `portfolio_engine.py` |
| `daily-crypto-trading-briefing-afternoon` | 0 14 * * * | Same as morning |
| `orchestrator-nightly` | 0 4 * * * | Full cycle + `portfolio_engine.py --optimize` + metrics |
| `parameter-optimizer-weekly` | 0 6 * * 1 | `parameter_optimizer.py` + `portfolio_engine.py --optimize` |

## Test Coverage

29 integration tests in `tests/` covering all new tool integrations:
```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -m pytest tests/ -v  # 29 passed
```

All tests verify:
- Polars vectorized scoring vs pandas baseline
- DuckDB analytical queries against journal.db
- vectorbt backtest with stop/target/trailing
- empyrical Sharpe, MaxDD, Calmar, Sortino, Omega
- Optuna walk-forward with actual trade replay
- pandas-ta RSI/EMA/SMA/MACD/Supertrend