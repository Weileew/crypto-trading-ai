# Trading-Advisor Quick Reference (2026-07-01)

## High-Impact Free Tools (Installed & Verified)

| Tool | Version | Purpose |
|------|---------|---------|
| **polars** | 1.42.1 | 10-50× faster DataFrames in `free_data.py`, `briefing.py` |
| **duckdb** | 1.5.4 | Analytical SQL on `journal.db` |
| **vectorbt** | 1.0.0 | Vectorized backtesting in `signal_validator.py` |
| **empyrical** | 0.5.12 | Industry-standard Sharpe, DD, Calmar, Sortino, Omega |
| **optuna** | 4.9.0 | Walk-forward optimization in `parameter_optimizer.py`, `portfolio_engine.py` |
| **pandas-ta-classic** | 0.6.52 | 193 pure-Python indicators (RSI, MACD, Supertrend) |

## Integration Quick Reference

```python
# free_data.py
df = free_data.markets_to_polars(markets)
scored = free_data.compute_candidate_scores_polars(df)
perf = free_data.get_regime_performance()  # DuckDB query

# briefing.py
if len(markets) >= 400:
    df = free_data.markets_to_polars(markets)
    scored = free_data.compute_candidate_scores_polars(df)

# signal_validator.py
bt = signal_validator.backtest(candles, date, entry, stop, target)
summary = signal_validator.summarize(signals)  # includes empyrical metrics

# portfolio_engine.py
perf = portfolio_engine.journal_performance(days=30)  # includes empyrical
optuna_result = portfolio_engine.optimize_portfolio_params(n_trials=50)

# parameter_optimizer.py
optuna_result = parameter_optimizer.optimize_with_optuna(coins, n_trials=50)
```

## Reference Files (in references/)

| File | Content |
|------|---------|
| `signal-quality.md` | Signal pipeline: scaled volatility gate, loss penalty, win momentum, regime gating |
| `paper-trading-data-model.md` | Paper trading data integrity: trade_id lifecycle, open/close pairing |
| `research-calibrations.md` | Volatility-regime bias, liquidity-adjusted sizing |
| `high-impact-tools-integration.md` | Polars, DuckDB, VectorBT, Empyrical, Optuna integration patterns |
| `vectorbt-empyrical-optuna-patterns.md` | VectorBT backtest, Empyrical metrics, Optuna optimization patterns |
| `free-data-integration-notes.md` | Free data sources validation |
| `tokocrypto.md` | TokoCrypto API integration |
| `trap-filters.md` | Falling-knife, pump, manipulation detection methodology |
| `paper-trading.md` | Paper trading pipeline |
| `investigate-m2m-output.md` | Cross-referencing notification → journal.db → ledger.json → portfolio.json |
| `paper-trading-m2m-script.md` | Cron script behavior, deliverable format, verification commands |
| `paper-trading-reconciliation.md` | Reconciling portfolio.json, ledger.json, journal.db |
| `strategy-provenance.md` | Strategy_id format, position enrichment, strategy-grouped P&L |
| `log_sheet.md` | Trade log template |
| `compact-briefing-template.md` | Compact briefing format |
| `cron-schedule.md` | Cron schedule |
| `coin-aliases.md` | coin_aliases.json + resolve_coin_id() + smart CG search |
| `dynamic-risk.md` | Dynamic risk & trailing stops formula |
| `portfolio-engine-and-derivatives.md` | Portfolio engine + derivatives deep-dive |
| `audit-checklist.md` | Use before any non-trivial patch |
| `audit-2026-06-28.md` | Full audit: fetch_markets, parser/format mismatch, validation loop, ledger schema drift |
| `orchestrator-setup.md` | Deployment, cron, symlinks, smoke test cleanup |
| `elementree-len-gotcha.md` | Python XML debugging trap |
| `ad-hoc-verification.md` | Self-cleaning tempfile verification template |
| `cg-rate-limit.md` | `_get_cg()` — 6s spacing, daily counter |
| `briefing-quality-audit.md` | Three-dimension audit methodology |
| `cron-manager.md` | `strategy/cron_manager.py` — CG budget, collision scan, auto-optimize |
| `smoke-test.md` | `scripts/smoke_test.py` — gates each parser, fetcher, entrypoint |
| `paper-trading-m2m-script.md` | M2M update script: `~/.hermes/scripts/paper-m2m-update.sh` |