# Trading Advisor Audit Checklist

Use this whenever the user asks for an audit, asks "is the advisor healthy?", or before a non-trivial patch. Each section is a self-contained check that produces evidence (not just a green checkmark).

## 1. Inventory

```bash
ls -la ~/.hermes/skills/trading-advisor/scripts/
wc -l ~/.hermes/skills/trading-advisor/scripts/*.py
```

Anything >300 LOC, or anything with multiple top-level responsibilities, is a refactor candidate.

## 2. Compile sweep

```bash
for f in ~/.hermes/skills/trading-advisor/scripts/*.py; do
  python3 -m py_compile "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```

A pass here is necessary but not sufficient.

## 3. Behavioral smoke test

```bash
python3 ~/.hermes/skills/trading-advisor/scripts/smoke_test.py
```

This script imports each module and runs a deterministic check: parser against the most recent real briefing, `--save-only` for `briefing.py`, fixture-level call for `signal_validator.backtest`, etc. Always run it after any change.

## 4. Parser consistency

Real briefings live in `reports/daily_briefing_*.md`. Run each parser against the same file:

```python
import sys; sys.path.insert(0, "~/.hermes/skills/trading-advisor/scripts")
from paper_trader import parse_briefing_recommendations
from paper_executor import parse_recommendations
from signal_validator import parse_buy_recommendations
# ... open the most recent briefing, run all three, diff the results
```

If any parser returns 0 while another returns N, that's the bug. They must agree on which symbols and which biases qualify as actionable trades.

## 5. Cron hygiene

```bash
hermes cron list  # or the agent's equivalent cronjob tool
```

Things to flag:
- Literal-date one-shots (`15 14 27 6 *`) — these fire once and never again.
- Schedule collisions: list each job's hours-of-day and check pairwise for shared hours.
- Jobs whose `next_run_at` is in the past.

## 6. Data-source dependency check

Run each external call against the real endpoint with a 5s timeout. Blocked or failing:

- `api.coincap.io` is DNS-blocked on some networks — do not use it as a primary source. CoinGecko `/simple/price` is the replacement.
- `api.binance.com` is generally reliable. Prefer `/api/v3/exchangeInfo` for the USDT pair gate and `/api/v3/klines` for candles.
- `api.coingecko.com` enforces 5–15 req/min on the free tier. Throttle or backoff is required.

## 7. Output schema drift

Read the most recent `reports/paper_trading/portfolio.json` and `ledger.json`. Look for fields used by old code paths:

- `qty` vs `quantity`
- `avg_entry` vs `entry_price`
- `stop_loss` vs `stop`
- `take_profit` vs `target`

Any position that uses the older schema will render `None` cells in `paper_trader.format_summary`. Normalize on read.

## 8. Validation loop health

Open `reports/signal_performance.json` and look at:

- `summary.pending_validation_count` — if > 0 for multiple consecutive runs, the candle-fetch path is broken.
- `summary.validated_count` — if 0 over multiple days, your signal coverage is too narrow (or rate-limited).

The fix is usually a stale-after-N-days timeout: drop the signal from `signals` after 5 days of `pending_validation`, write that decision into `adjustment_log.json` via `scripts/improve.py`, and surface the timeout to the next briefing.

## Severity ladder

Tag findings as Critical / High / Medium / Low:

- **Critical**: silently wrong output, loss of capital in paper trading, validation loop broken.
- **High**: schema drift, parser divergence, runtime crash in a script the cron invokes.
- **Medium**: degraded behavior under failure (silent zero where the user expected a banner), doc/code drift.
- **Low**: code quality, dupes between parsers, lint, telemetry gaps.

## Output format

Deliver findings as a Markdown table (severity / area / issue) followed by a numbered task list. Each task is one atomic change with a validation step. Don't merge multiple changes into one task — the audit table tells you the priority; the task list is the contract.