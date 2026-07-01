# Pitfalls & Bug Fix History

## Paper Tracker Bugs (2026-06-27)
- **Key mismatch**: `current_price_map()` prices keyed by CG ID (`"velvet"`) but `update_mark_to_market()` looked up by portfolio symbol (`"VELVET"`) → 0% P&L. Fix: track `orig_to_cgid` mapping, return dict keyed by original input symbol.
- **Stop/target crash**: `float(pos["stop"])` on `"?"` (string for n/a) crashes entire M2M loop. Fix: `_safe_float()` helper + try/except per position.
- **Price parsing on compact briefing**: `_safe_price("0.3973 (+8%)")` returns None. All 3 parsers (`_safe_price`, `parse_price` in paper_executor/signal_validator) must strip `(…)` suffixes, trailing annotations, and prefixes (`near`, `~`, etc.).
- **Missing rate limiting**: paper_trader's own `_get()` had zero rate limiting / retries → silent 429s. Resolved by centralizing via `free_data._get_cg()`.

## CG Rate Limits
- **Global endpoint trap**: after `fetch_markets()` (5 CG calls), `/global` routinely 429s. Separate 12s budget (`_get_cg_global()`) + 3 retries + `_btc_dom_from_markets()` fallback. Allow ~90-110s total for briefing.
- **Central rate limiter**: all CG calls through `free_data._get_cg()` with 6s spacing, exponential backoff (3s×attempt on 429), daily counter at `reports/cg_call_count.json`.
- **Free tier**: ~14,400 calls/day, ~10 req/min, min 6s spacing. M2M at 15m = 96/day, orchestrator = 8/run, briefings = 6/run. Total: ~116/day (0.81% of tier).

## Coin Alias Resolution
- Shared JSON at `strategy/coin_aliases.json` (90+ entries) replaces duplicate dicts in signal_validator and paper_trader.
- All resolution goes through `free_data.resolve_coin_id()`: alias file lookup → smart CG search (scans 10 results for exact symbol match) → raw label.
- Avoids duplicate alias definitions diverging between scripts.

## Orchestrator Adaptation
- `adapt_params()` never fired initially because `compute_performance("trailing_30d")` saw <20 closed signals at orchestrator run time. The 19 duplicate signals from validator came after the run.
- Fixes applied (loss cooldown, classification, dedup) mean the next run will see correct 40.9% WR, +1 streak, and 22+ closed signals.

## Paper Trading Audit
- `journal.db` outcomes are source of truth over `ledger.json`.
- Review command: `python3 scripts/paper_trader.py --update --summary`
- Portfolio at `reports/paper_trading/portfolio.json`, journal at `strategy/journal.db`

## CLI Flags
- **`briefing.py` uses `--out` not `--output`**: argparse flag is `--out OUT` (short for output path). Attempting `--output` will error. Also accepts `--save-only` for auto-named files.
- **`signal_validator.py` has no `--days` CLI**: `main(days=30)` accepts `days` as a Python parameter but the CLI (`__main__` block) passes no args. To change lookback, modify the source or call `main(days=N)` from another script. Default is 30 days.

## Telegram / Delivery
- **TELEGEMINI_TELEGRAM_CHAT_ID must be set**: the user's Telegram delivery step references this env var. If unset, Telegram delivery fails silently. The cron job's automatic delivery mechanism handles output when Telegram is unavailable — do not attempt to send via API without a valid bot token and chat ID.

## Memecoins / Speculative Assets
- Never draw from sub-$1M speculative memecoins, token launches with no product, or obvious pump-and-dump patterns.
- Mark such coins "speculative - not recommended for balanced style".
- Other sub-$1M assets may be considered with genuine liquidity + clear thesis, with explicit elevated-risk disclosure.
