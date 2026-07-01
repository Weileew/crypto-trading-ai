# High-Impact Free Tools for TOK Development

**All tools: free, open source (MIT/BSD/Apache), no registration, no API keys.**

## Core Data & Backtest Stack (Highest ROI for TOK)

| Tool | Version | Purpose | TOK Integration |
|------|---------|---------|-----------------|
| **polars** | 1.42.1 | 10-50× faster DataFrames, lazy eval, streaming | `free_data.py` market scans, `paper_trader.py`, `signal_validator.py` |
| **duckdb** | 1.5.4 | In-process analytical SQL on `journal.db`, `portfolio.json` | Regime analysis, win/loss by symbol, performance by source |
| **vectorbt** | 1.0.0 | Vectorized backtesting on NumPy | Replace custom backtest loops in `signal_validator.py` |
| **empyrical** | 0.5.12 | Industry-standard risk/performance metrics (Quantopian lineage) | Sharpe, DD, Calmar, Sortino, Omega in `signal_validator.py` |
| **optuna** | 4.9.0 | Hyperparameter optimization (TPE/CMA-ES samplers) | Walk-forward optimize vol gates, penalty weights, regime thresholds |

## Technical Indicators

| Tool | Version | Purpose |
|------|---------|---------|
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python indicators, no C deps (`df.ta.rsi()`, `df.ta.macd()`, `df.ta.supertrend()`) |

## Dev Hygiene (Catch Bugs Before Cron Runs)

| Tool | Version | Purpose |
|------|---------|---------|
| **ruff** | 0.15.20 | Lint + format 100× faster than flake8/black |
| **mypy** | 2.1.0 | Static type checking |
| **pre-commit** | 4.6.0 | Git hooks: ruff check --fix, mypy, pytest -q |
| **pytest + xdist** | 9.1.1 + 3.8.0 | Parallel test runs |
| **debugpy** | 1.8.21 | VS Code remote debug: `python -m debugpy --listen 5678 -m paper_trader` |

## Observability (Optional)

| Tool | Version | Purpose |
|------|---------|---------|
| **loguru** | 0.7.3 | Structured JSON logs for cron jobs |
| **rich** | 13.7.1 | Pretty terminal dashboards |
| **prometheus-client** | 0.25.0 | `/metrics` endpoint for local Grafana |

---

## Files Created: 2026-07-01
 Status: Installed in Hermes venv, integrated into TOK modules