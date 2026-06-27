---
name: trading-advisor
description: "Crypto market analysis and trading advisory skill for Hermes Agent. Generates swing/day trading briefings with multi-source free data, detailed reasoning, risk controls, and delivery via cron."
version: 0.7.0
author: user
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cryptocurrency, trading, crypto]
---

# Crypto Trading Advisor (TOK)

**TOK** — Welly's trading system alias. "run TOK" = the full trading-advisor pipeline (briefing.py, orchestrator.py, paper validation).

For swing/day trading in spot markets across all liquid coins, using only free data sources plus TokoCrypto liquidity where available.
Reasoning must be detailed and explicit. All inputs are read-only: no trade execution, no withdrawal, no signing.

Goal: produce a decision-quality daily briefing and on-demand market analysis that is far more rigorous than a casual call.

## Persona
Friendly, helpful, fun, dependable crypto trading buddy. Still a disciplined swing/day spot trader, but explain things clearly and keep it light. Stated risk coercion:
- PRIMARY: never get wiped
- SECONDARY: capture genuinely good setups
- NEVER: random coins at random time, impulse trades, copycat signals
- STYLE: keep explanations approachable and confidence-calibrated, not robotic.

## User Profile
- Risk style: balanced
- Timeframes: swing and day
- Assets: spot only, liquid non-stablecoins with meaningful movement; avoid low-volatility or dominated stablecoin proxies.

## Risk Guardrails (must be followed in every response)
1. ALWAYS lead each analysis with a plain-language risk disclosure.
2. NEVER mention leverage.
3. Prefer preparation instead of action.
4. Separate alpha finding from trade plan. Alpha finding focuses on opportunity; trade plan focuses on entry, stop-loss, target, convergence/divergence.
5. Bias toward setups with at least 2 independent signals agreeing.
6. Lower position size when only one signal or if confidence is "suspicious".
7. Treat low-liquidity, low-market-cap coins as higher probability of manipulation. Clearly mark "noise risk".
8. Always give explicit probability levels and why.
9. Use numeric thresholds plus exceptions. Only override when the argument is specific and well-structured.

## Conventions
- Default output: compact briefing format unless user asks for detailed analysis.
- Compact briefing rules: under 300 words, max 2 trade ideas, explicit bias/entry/stop/target.
- Visuals: compact briefing can optionally use ASCII visuals (BTC dominance bar, risk icon, confidence bar) when `--visuals` is passed. Keep visuals purely additive; do not replace core slot fields.
- Orchestrator status: use `--orchestrator` to append a compact block showing current strategy params, trailing performance (win rate, profit factor), and open signal count from the strategy journal. Both compact and full briefing modes support this flag.
- Enhanced mode: `briefing.py --enhanced` appends a compact regime block from DeFiLlama + DEX Screener + stablecoin flow data. Keep it additive and short; if any data source fails, emit a single degraded note rather than failing the whole briefing.
- Probabilities: use expected value framing when possible (not just win rate).
- Unit: prefer USD and percent, not shorthands like "1R".
- Accuracy: prefer confidence intervals when available, not point estimates.
- Explicit reasoning: show why each signal fits the current regime, not just a label.
- Regime awareness: macro first (trend, volatility, liquidity), then sector, then coin.
- Macro context banner: when Fear & Greed < 20, the compact briefing auto-appends `⚠️ Macro risk: Extreme Fear — even quality signals carry elevated macro risk. Size down, tighten stops.` below the Market Regime section. When F&G < 30 (but ≥20), a milder `⚡ Macro note: Fear — conservatism warranted.` banner appears. This is hardcoded in `render_compact_briefing()`.
- Bias-aware stop/target: since June 2026, targets and stops are **dynamic per coin** — scaled by volatility (abs(24h%)) and conviction (score). Bullish = target above entry, stop below; bearish = target below, stop above. Each target/stop label in the compact briefing shows the actual percentage used. Range: target 5–15%, stop 2–8%. R/R ratio improves with score (1.8x at score 25 → 4.1x at score 45 on same volatility). Multi-stage trailing stop locks in gains with configurable stages (default: +2%/1% → +6%/2% → +12%/3%), adjustable in `params.json` `dynamic_risk.trailing_stages`.
- Target philosophy: **realistic but don't leave profit on the table**. The dynamic formula caps targets at 15% (no chasing impossible rallies) but the multi-stage trailing stop (see below) locks in extra gains if the price runs beyond the initial target. The target is the primary profit-taking level; the trailing stop is the bonus.
- Multi-stage trailing stop: replaces single-stage (activate at +2%, trail 1.5%) with 3 stages that tighten early and loosen after bigger gains:
  | Profit | Trail distance | Behaviour |
  |---|---|---|
  | ≥ +2% | 1.0% | Tight — locks in early gains fast |
  | ≥ +6% | 2.0% | Medium — lets strong moves breathe |
  | ≥ +12% | 3.0% | Wide — maximises blow-off runs |
  The trail level ratchets up (or down for bearish) on each new peak. Stages are configurable via `strategy/params.json` `dynamic_risk.trailing_stages` — see `references/dynamic-risk.md`.
- Detailed analysis output only when explicitly requested; otherwise keep concise and actionable.

## Skill Links
- Free sources: `references/data-sources.md`
- New free integrations: `references/free-data-integration-notes.md` (DeFiLlama, DEX Screener, stablecoin flows)
- TokoCrypto: `references/tokocrypto.md`
- Trap filters: `references/trap-filters.md` (methodology for falling-knife, pump, manipulation detection)
- Paper trading pipeline: `references/paper-trading.md` (M2M bugs, `_safe_float`, key-mismatch fix, portfolio schema, **output format UX**, **HTML dashboard image delivery**)
- Strategy provenance: `references/strategy-provenance.md` (strategy_id format, position enrichment, strategy-grouped P&L, orchestator integration)
- Trade log template: `references/log_sheet.md`
- Compact briefing format: `references/compact-briefing-template.md`
- Cron schedule: `references/cron-schedule.md`
- Dynamic risk & trailing stops: `references/dynamic-risk.md` (formula, trailing stop mechanics, paper trading integration, params schema)
- Data source migration guide: see `data-source-testing` skill (general workflow for replacing dead APIs)
- Audit checklist: `references/audit-checklist.md` (use before any non-trivial patch)
- Orchestrator setup: `references/orchestrator-setup.md` (deployment, cron, symlinks, smoke test cleanup)
- ElementTree `__len__` gotcha: `references/elementree-len-gotcha.md` (Python XML debugging trap)
- Smoke test: `scripts/smoke_test.py` (run after every change; gates each parser, fetcher, and entrypoint)
- M2M update script: `~/.hermes/scripts/paper-m2m-update.sh` — no_agent cron script that runs `paper_trader.py --update --summary` every 10 minutes. Silent when no positions are closed; delivers to origin only on events (position closed, error). See `references/cron-schedule.md`.
- Scripts: `scripts/free_data.py`, `scripts/briefing.py`, `scripts/trade_plan.py`, `scripts/paper_trader.py`, `scripts/market_snapshot.py`, `scripts/pre_market_snapshot.sh`, `scripts/daily_loop.py`, `scripts/paper_executor.py`, `scripts/health_heartbeat.py`, `scripts/strategy_journal.py`, `scripts/market_news.py`, `scripts/orchestrator.py`

## Research Enrichment
Research papers are sourced from **OpenAlex** (free scholarly API, no auth) via `scripts/collect_papers_openalex.py` in the `crypto-research` skill. A daily cron job (`research-playbook-enrichment`) at 05:30 fetches new papers before the morning briefing. Currently **116 papers** (76 Tier A peer-reviewed + 31 Tier B preprint + 9 Tier C). Updated count as of 2026-06-27 enrichment run (+5 new papers). Use `best_paper_for()` in `briefing.py` (reads consolidated digest) or `scripts/query_papers.py` for manual search.

## Workflow
1. Identify user request type: watchlist, coin deep-dive, briefing, or sanity check.
2. Run the appropriate script from workdir `~/.hermes/skills/trading-advisor` as needed.
3. Consult `crypto-research/references/research-digest.md` via `best_paper_for()` in `briefing.py` for relevant research before making strategy claims. The consolidated digest is a single file (O(1) read) grouping all validated papers by topic. Local corpus only first; use web search only when zero matches are found and label it external evidence.
4. Gather free market data (3-phase screening pipeline in `briefing.py` `fetch_markets()`):
   - **Phase 1 — Pagination**: Fetch CoinGecko `/coins/markets` pages 1–2 (500 coins by mcap ranking). This covers ~198 of the 437 active TokoCrypto USDT pairs (top ~45%).
   - **Phase 2 — USDT Gate**: Gate by TokoCrypto USDT pairs via `https://www.tokocrypto.site/api/v3/exchangeInfo` (437 USDT pairs). Discards everything not tradeable on TokoCrypto.
   - **Phase 3 — Batch Fallback**: For the ~239 TokoCrypto USDT pairs NOT in the paginated top 500, resolve their CoinGecko IDs via `/coins/list` and batch-fetch price data via `/simple/price` (chunks of 150 IDs, 1–2 API calls). These fallback coins get conservative scoring (no `market_cap_change_percentage_24h` — score = `abs(p)` only).
   - **Phase 4 — TokoCrypto Ticker Enrichment**: Fetch 24hr tickers for all TokoCrypto USDT pairs (single call). Merges exchange-specific volume, bid/ask, and price change into each candidate for liquidity-aware scoring.
   - **Coverage**: 97% of all TokoCrypto USDT pairs (424–426 of 437). ~11 symbols have no CoinGecko entry at all and are silently skipped.
   - Additional fetches:
     - Macro/sentiment: Fear & Greed, BTC dominance
     - Sector/defi signals: DeFiLlama protocols by TVL, yield pools, stablecoin circulation delta
     - DEX activity: DEX Screener search for txn/volume/price-change context
     - On-chain: Glassnode free endpoint data, CryptoQuant free signals, or Santiment general alerts
     - News: `scripts/market_news.py --compact` fetches from CoinTelegraph + CoinDesk RSS + Fear & Greed (free, no API key)
     - Technicals: indicator-calculation from OHLCV via helper scripts
     - Exchange liquidity: 
       - **TokoCrypto** — primary pair gate (437 USDT pairs via public API, no auth). 24hr ticker data merged into all candidates; orderbook depth/spread fetched for top picks. See `references/tokocrypto.md`. Auto-screening IS now integrated — replaces the old Binance USDT gate.
5. Build a “macro -> sector -> coin” thesis and summarize it clearly.
6. Summarize all signals into a Daily Briefing using `references/compact-briefing-template.md`.
7. End with a standby plan if no trade tonight:
   - preconditions for the next setup
   - watch levels
   - invalidation
8. Conclude with action list of what needs to be checked next, by time and asset.
9. For manual runs, prefer the script path: run `scripts/briefing.py --compact --save-only` from the skill directory.
10. Paper trading: keep reports separate. Do not embed the full paper-trading table inside the briefing; refer users to `scripts/paper_trader.py --summary` instead.
11. After every briefing, optionally run `scripts/paper_trader.py --paper-open --briefing <latest>` so positions accumulate for validation loops.
12. Backtest/recent signals: run `scripts/signal_validator.py` to produce `reports/signal_performance.json`. Feed this into `scripts/improve.py` for accuracy feedback. Default choice for validator is CoinGecko `market_chart` (more reliable than `/ohlc` for some symbols on the free tier).
13. Rate limits: CoinGecko free tier enforces 5–15 req/min. The scripts now use inter-call delay + exponential backoff. If `/ohlc` returns 429, fall back to `market_chart` or wait for the limit reset.
14. USDT-only screening: before candidate scoring, gate market lists with TokoCrypto `exchangeInfo` `USDT` trading pairs via `tokocrypto.site` (public, no key). This filters stablecoins, wash-USDT proxy tokens, and non-USDT pairs with one stable pass and should be the default scan rule.

## Scripts
- `scripts/signal_validator.py` — backtests recent briefings against market data and writes `reports/signal_performance.json`. Preferred candle source: CoinGecko `market_chart`; fallback: Binance klines. Run after briefings to accumulate signal-quality stats; pair with `scripts/improve.py` for the learning loop. Uses `ALIAS` table plus CoinGecko `search` fallback for unknown tickers, capped at 90 days for resolved ids and 30 days for unresolved ones.
- `scripts/improve.py` — continuous maintenance/improvement pass for the advisor.
- `scripts/paper_trader.py` — paper-trading ledger; does not automatically open trades from briefings unless invoked. Every position now tracks `strategy_id` (e.g. `tok-v2-20260627`) and `strategy_snapshot` (immutable copy of screening params at entry). Portfolio summary groups P&L by strategy. See `references/strategy-provenance.md`. Key functions:
- `scripts/briefing.py` — briefing generator. Key functions:
  - `fetch_markets()` — 4-phase screening (pagination, TokoCrypto USDT gate, batch fallback, ticker enrichment), returns ~424 candidates covering 97% of TokoCrypto USDT pairs
  - `_fetch_coingecko_page()` — single CG page fetch (250 coins by mcap)
  - `_fetch_coingecko_coin_list()` — returns `{SYMBOL: id}` map for all 17K+ CG coins
  - `_get_cg()` — CG-specific GET with 6s rate limiter + 4×2x backoff retries
  - `simple_rules()` — gates stablecoins, mcap<50M, |24h|<3%, score<25; volume bonus capped at +10;
    TokoCrypto liquidity scoring: spread <5 bps = +5, 5-10 bps = neutral, 10-20 bps = -5, >20 bps = -10;
    TokoCrypto quote_volume >$1M = +3, >$100K = +1; no ticker data = -5 (unknown liquidity).
    Volume/mcap quality: if |p| > 8% and volume/mcap ratio < 0.5% → fake_volume (-18);
    if volume/mcap ratio > 200% → abnormal_volume (-8).
    Trading trap filters (applied sequentially, all penalty-only):
      • falling_knife (< -12%) = -15, slipping (< -8%) = -8
      • thin_pump (>18% with <$100K toko_vol or <$2M CG vol) = -15
      • manipulation_risk (|p|>15% with <$1M CG vol) = -12
      • mcap_divergence (|p|>10% with |mc|<2%) = -8
      • overextended (|p|>25%) = -10
    See `references/trap-filters.md` for methodology and tuning guidance.
  - `render_compact_briefing()` / `render_briefing()` — output formatters
- `scripts/free_data.py` — centralized free-data fetcher; owns the retry + rate-limit logic used by other scripts. Key TokoCrypto functions:
  - `fetch_tokocrypto_usdt_pairs()` — returns set of 437 TRADING USDT base assets (single `exchangeInfo` call to `.site`)
  - `fetch_tokocrypto_tickers()` — returns ALL 3,600+ tickers in one call; `build_tokocrypto_ticker_map()` converts to `{SYMBOL: {last, vol, bid/ask}}` lookup, filtered to USDT pairs only (~675 entries)
  - `fetch_tokocrypto_depth(symbol, limit)` — orderbook bids/asks; `compute_tokocrypto_depth_metrics()` returns spread_bps, depth within 1%, bid/ask depth in USD
  - `fetch_tokocrypto_klines(symbol, interval, limit)` — OHLCV candles (identical format to Binance klines)
  - `fetch_tokocrypto_book_ticker(symbol)` — lightweight bid/ask only (no orderbook depth)
- `scripts/trade_plan.py` — trade-plan builder.
- `scripts/market_snapshot.py` / `scripts/pre_market_snapshot.sh` — snapshot helpers.
- `scripts/paper_executor.py` — parse today's briefing and open paper trades directly into ledger/portfolio, then refresh M2M via `paper_trader.py --update --summary`. Uses `RISK_PER_TRADE = 0.02` (2% of cash per trade) — never hardcodes `qty = 1.0`.
- `scripts/audit_equity.py` — equity post-mortem and audit replay. Reconstructs closed trades, open positions, and equity from the ledger, portfolio, and strategy journal. Run after any drawdown or missed close to get a reproducible review report.
- `scripts/health_heartbeat.py` — generates `reports/health.json` with last-run timestamp and script sizes/mod-times. Run or cron after briefings to track system health.
- `scripts/strategy_journal.py` — persistent SQLite journal recording every signal, outcome, param change, and performance snapshot. This is the long-term memory for the orchestrator. Exposes `current_strategy_identity()` which returns `{strategy_id, strategy_snapshot}` from `strategy/params.json` — used by the orchestrator to tag signals with the active strategy version. CLI: `python3 scripts/strategy_journal.py signals|performance|params-history|adapt|record-signal|close-signal`.
- `scripts/market_news.py` — free news monitor fetching headlines from CoinTelegraph + CoinDesk RSS + Fear & Greed. Headlines classified as bullish/bearish/neutral. Usage: `--cache` for journal storage, `--compact` for embedding.
- `scripts/orchestrator.py` — central coordinator running the full 6-phase pipeline (news → briefing → journal → validate → performance → adapt). Runs nightly at 04:00 UTC. CLI: `--quick` skips news/validation, `--dry-run` for testing.

## Signal Validation Loop
1. Generate a briefing.
2. Run `scripts/signal_validator.py` to backtest its recommendations against candles.
3. Review `reports/signal_performance.json` for win rate, target/stop hit rate, avg R-multiple, and best/worst signals.
4. Stale `pending_validation` lifecycle: `signal_validator.py` automatically prunes `pending_validation` signals older than `pending_validation_stale_days` (default 90). The `pruned_stale_count` field in the output shows how many were dropped. This prevents the backlog from accumulating indefinitely.
5. Feed the result into `scripts/improve.py` to update heuristics.
6. Repeat across enough signals to reach statistically meaningful sample size before changing confidence thresholds.
7. `signal_validator.py` now also writes validated outcomes to the **strategy journal** (`strategy/journal.db`) via `_write_to_journal()`. It matches signals by symbol + entry price within 5% tolerance; unmatched signals get recorded as new journal entries then immediately closed with their outcome.

## Orchestrator Mode

The orchestrator (`scripts/orchestrator.py`) is the **central coordinator** that transforms the advisor from a passive briefing generator into an active, learning system. It runs as a nightly cron job and ties together the full pipeline:

### Orchestrator Pipeline (6 phases)

```
Phase 1 — News Monitor    fetch & cache market headlines from CoinTelegraph, CoinDesk RSS, Fear & Greed
Phase 2 — Briefing         run briefing with current strategy params (screens ~424 coins)
Phase 3 — Journal          record new signals in strategy journal
Phase 4 — Validation       check open signals against live prices → auto-close hit targets/stops
Phase 5 — Performance      compute trailing 30d win rate, profit factor, avg PnL
Phase 6 — Adaptation       auto-tighten thresholds on loss streaks, loosen on sustained wins
```

### Orchestrator CLI
```bash
python3 scripts/orchestrator.py                    # full nightly run
python3 scripts/orchestrator.py --quick            # skip news + validation
python3 scripts/orchestrator.py --dry-run          # print but don't save anything
python3 scripts/orchestrator.py --out path.md      # custom output path
```

Output is written to `reports/orchestrator_digest_YYYY-MM-DD.md` with sections for strategy params, market news, opportunities, signal validation, and trailing performance.

### Strategy Journal (`scripts/strategy_journal.py`)

A persistent SQLite database at `strategy/journal.db` that records every signal, outcome, parameter change, and performance snapshot. This is the **long-term memory** of the trading advisor.

**Tables:**
- **`signals`** — Every signal generated with symbol, bias, entry/target/stop prices, score, batch ID
- **`outcomes`** — Signal closure outcomes (hit_target, hit_stop, expired) with PnL%, duration, exit reason
- **`params_history`** — Every parameter adjustment with trigger reason (manual, loss_streak, win_rate_above_target, init)
- **`performance`** — Computed metrics snapshots (win rate, profit factor, avg PnL, best/worst symbols)
- **`news_cache`** — Cached market headlines with sentiment classification

**CLI commands:**
```bash
python3 scripts/strategy_journal.py signals                     # list recent signals
python3 scripts/strategy_journal.py performance                 # trailing performance report
python3 scripts/strategy_journal.py performance trailing_30d    # 30-day window
python3 scripts/strategy_journal.py params-history              # parameter change log
python3 scripts/strategy_journal.py adapt                       # run parameter adjustment
python3 scripts/strategy_journal.py record-signal --symbol BTC --bias bullish --entry 50000
python3 scripts/strategy_journal.py close-signal --id 5 --outcome hit_target --exit 52000
```

### Market News Monitor (`scripts/market_news.py`)

Fetches free market news from multiple sources:
- **CoinTelegraph RSS** — real-time crypto news feed
- **CoinDesk RSS** — major crypto news outlet
- **Fear & Greed Index** — via alternative.me free API
- Headlines classified as bullish/bearish/neutral by keyword matching

Sources are deduplicated by headline text and cached in the strategy journal.

```bash
python3 scripts/market_news.py                  # print headlines
python3 scripts/market_news.py --cache          # fetch and store in journal
python3 scripts/market_news.py --compact        # one-liner for embedding in briefings
```

### Strategy Parameters (`strategy/params.json`)

Adjustable parameters persisted in JSON, auto-updated by the orchestrator.

**Version 4** (2026-06-27) adds the `dynamic_risk` block with per-candidate target/stop scaling and configurable trailing stop stages:

```json
{
  "version": 3,
  "description": "Live strategy parameters — dynamic target/stop with trailing stop lock-in",
  "screening": {
    "min_mcap": 50000000,
    "min_24h_change_pct": 3.0,
    "score_threshold": 25.0,
    "max_opportunities": 2
  },
  "risk": {
    "risk_per_trade_pct": 2.0,
    "stop_loss_pct": 3.5,
    "target_pct": 8.0
  },
  "dynamic_risk": {
    "enabled": true,
    "base_target_pct": 8.0,
    "base_stop_pct": 3.5,
    "min_target_pct": 5.0,
    "max_target_pct": 15.0,
    "min_stop_pct": 2.0,
    "max_stop_pct": 8.0
  },
  "adaptation": {
    "enabled": true,
    "min_signals_before_adjust": 20,
    "win_rate_target": 0.55
  }
}
```

`min_target_pct` and `max_target_pct` are hard-clamps — the briefing never produces a target outside this range, no matter how extreme the volatility or score. See `references/dynamic-risk.md` for the full formula and rationale.

### Auto-Adaptation Rules

The orchestrator adjusts strategy parameters based on trailing 30-day performance:

| Condition | Action |
|---|---|
| **Win rate < 40%** (≥20 signals) | Tighten: multiply min_24h_change and score_threshold by 1.3× |
| **Win rate > 55%** (≥20 signals) | Loosen: multiply thresholds by 0.85× |
| **≥5 consecutive losses** | Tighten aggressively (same multiplier, loss_streak trigger) |
| **Within range or insufficient data** | No change, log reason |

Parameter values are clamped: `min_24h_change` ∈ [1.0%, 15.0%], `score_threshold` ∈ [10, 80].

### Orchestrator Cron Schedule

The orchestrator runs on a different cadence than the briefing cron to avoid resource contention:

| Job | Schedule | Purpose | Cost |
|---|---|---|---|
| `paper-trading-m2m` | `every 10m` | M2M update + trailing stop check via `paper_trader.py --update --summary`. **no_agent=True** — zero LLM tokens, delivers to origin only on events (position closed). | 1 CG call |
| `orchestrator-nightly` | `0 4 * * *` | Full 6-phase cycle (news → briefing → journal → validate → performance → adapt) | LLM |
| `daily-crypto-trading-briefing-morning` | `0 8 * * *` | Morning briefing only (lighter, faster) | LLM |
| `daily-crypto-trading-briefing-afternoon` | `0 14 * * *` | Afternoon briefing only | LLM |

> **Note**: Signal validation is handled by the orchestrator's Phase 4 (nightly) and signal_validator.py (manual/on-demand). A standalone validation cron is NOT created because it would add unnecessary CG API load on the free tier.
>
> **Lightweight cron pattern**: Jobs that only run a self-contained script (no LLM reasoning needed) should use `no_agent=True` with a `script` parameter. Example — `paper-trading-m2m` runs `paper_trader.py --update --summary` every 10 min with zero tokens burned. The script lives at `~/.hermes/scripts/paper-m2m-update.sh` and the cron is created with `no_agent=True, script='paper-m2m-update.sh', schedule='every 10m', deliver='origin'`. The script only outputs on position closes or errors; otherwise cron delivers nothing. This is the right pattern for any cron that just calls `python3 some_script.py` and conditionally delivers its output.
>
> **⚠️ 2026-06-27 FIX**: The orchestrator-nightly cron was running in `no_agent=True` mode with `script: orchestrator.py`. Since `__file__` for symlinks resolves to the symlink path (not the resolved target), `SKILL_DIR` resolved to `~/.hermes/` instead of `~/.hermes/skills/trading-advisor/`. This caused all internal imports (strategy_journal, briefing, market_news) to look in `~/.hermes/scripts/` and fail with `FileNotFoundError`. Fixed: switched to prompt-driven mode (the agent runs `python3 scripts/orchestrator.py` from the skill workdir). See `scripts/orchestrator.py` line 29 for `SKILL_DIR` resolution. Rule: `no_agent=True` works for scripts that don't need `__file__`-based path resolution. If a script computes paths via `__file__`, use prompt-driven mode with `workdir`.

### Orchestrator Pitfalls
- **CG rate limits apply**: a full orchestrator run makes 7+ CG API calls (2 pages + 1 list + 1–2 simple/price + 1 global + 1 simple/price for validation). At 6s spacing, that's ~55–70s wall time. Do not schedule the orchestrator and a briefing cron within 5 minutes of each other.
- **News source fragility**: RSS feeds (CoinTelegraph, CoinDesk) may occasionally be unreachable. The fallback source (Fear & Greed only) always works. If both RSS feeds fail, the news section shows Fear & Greed only.
- **Journal DB growth**: `signals` and `outcomes` tables grow by ~2–4 rows/day. At this rate the DB stays under 10MB for years. No maintenance needed.
- **Smoke test signal cleanup**: `probe_strategy_journal()` in smoke_test.py creates and then immediately deletes a real signal in the DB. No manual cleanup needed. If the smoke test is interrupted mid-probe, run `DELETE FROM signals WHERE source='smoke_test'` (with foreign_keys=OFF) to clean up.
- **Performance with 0 signals**: `compute_performance()` handles zero-signal cases with `division by zero` guard (returns 0.0 for win rate, empty best/worst symbols). `adapt_params()` returns `insufficient_data` when `closed_signals < min_signals_before_adjust`.
- **`no_agent` cron + symlink `__file__`**: When a script in `~/.hermes/scripts/` (a symlink) runs in `no_agent=True` mode, Python's `__file__` resolves to the symlink path, NOT the resolved target. This means `os.path.dirname(__file__)` = `~/.hermes/scripts/` and `SKILL_DIR` = `~/.hermes/`. The orchestrator must NOT use `no_agent` mode — it needs a regular prompt-driven cron with `workdir` set to the skill directory so the agent runs `python3 scripts/orchestrator.py` from the correct location.
- **`Element.__len__` gotcha**: `xml.etree.ElementTree.Element.__len__()` returns child count, not text length. For text-only elements like `<title>text</title>`, `bool(element)` is `False` — never use `element or fallback`. See `references/elementree-len-gotcha.md` for detection, fix, and verification script.

## Briefing Format Contract
Current compact briefings use bullet blocks under `## Opportunities`. Each item has:
- `Name (symbol)` on its own line
- `- Bias: bullish|bearish`
- `- Why: 24h=±X.XX%; momentum + cap flow aligned`
- `- Entry: near <price>`
- `- Stop: <price>`
- `- Target: <price> (+N%)` or `(-N%)` for bearish — N is dynamic per candidate (5–15%, shown in label)
- `- Confidence: medium ███████░░░░░`
- `- TokoCrypto · $<depth> depth · <spread> bps spread` — live orderbook depth from TokoCrypto
- `- ⚠️ <trap_flag> · ⚠️ <trap_flag>` — only shown when trap filters fire (see trap-filters.md)
- `- Research: [🟢 peer-reviewed] "Paper Title" (doi:...)` — auto-populated from `research-digest.md`, Tier A only when available
If TokoCrypto depth fetch fails, the line degrades gracefully to `TokoCrypto spread: X bps $vol vol`.
`signal_validator.py`'s parser must tolerate both numbered items (`1. Name`) and plain header lines with parentheses. Bias variants accepted: `buy bias`, `bullish`, `long`, `accumulate`, `buy`.

## Rate Limits & Resilience
- CoinGecko free tier enforces **~10 req/min** (effectively 1 call per 6s); bursts >5 calls in 30s trigger 429 that persists even with exponential backoff.
- `scripts/briefing.py` has a **CG-specific rate limiter** (`_get_cg()`) with 6s minimum spacing between calls, plus 4 retries at 2× backoff. This is separate from the generic `_RATE_DELAY_SECS` in `free_data.py` (which only enforces 0.55s spacing and is NOT suitable for CoinGecko). All CoinGecko calls in `briefing.py` must use `_get_cg()`, never bare `_get()`.
- The CG rate limiter initializes with a stagger (`_CG_LAST_CALL = time.time() - 5.5s`) so the first call doesn't fire instantly. A `_CG_LAST_CALL = 0.0` initialization causes the first call to skip the wait (time difference = ~1.7B, always > 6s).
- The **global endpoint** (`/api/v3/global` for BTC dominance) has its own rate limit budget (`_get_cg_global()`) with a 12s minimum interval and 3 retries at 3× backoff. This is necessary because the 5 market-data CG calls in `fetch_markets()` exhaust the free-tier rate budget, and a 6th consecutive CG call to `/global` gets 429'd even at 6s spacing. The separate budget ensures the global call waits long enough, but adds ~12s to total runtime.
- **BTC dominance fallback**: if `fetch_global()` returns `n/a` (rate-limited or failed), `_btc_dom_from_markets(markets)` computes an approximate BTC dominance from the paginated CoinGecko markets data (BTC mcap ÷ sum of all coin mcaps in pages 1-2). This is always a slight overestimate (top-500 market cap ≈ 90%+ of total market cap). The compact briefing falls back to this before displaying `n/a`.
- Total CG calls per briefing run: **6** (2 markets pages + 1 coin list + 1–2 simple/price batches + 1 global). CG-only wall time: ~75–85s from rate-limit waiting.
- **Total briefing runtime**: ~100–110s (5 CG calls + 1 TokoCrypto exchangeInfo + 1 TokoCrypto all-tickers + 2–5 TokoCrypto depth calls). The all-tickers endpoint returns ~3,600 items; allow ~2s for download/parse. Smoke test timeout must be **≥180s** to account for API variance and retries.
- `scripts/free_data.py` centralizes generic inter-call throttle + backoff for non-CG endpoints (DeFiLlama, DEX Screener, Fear&Greed, CoinCap). These have less aggressive rate limits.
- When CoinGecko is rate-limited, prefer `market_chart` over `/ohlc` for recovery because it returns data for more symbols on the public tier.
- Binance `GET /api/v3/klines` is useful as a CoinGecko fallback for liquid USDT pairs.
- CoinCap `api.coincap.io` may be DNS-blocked on some environments; do not depend on it as the primary cache path.
- **TokoCrypto domain distinction**: `www.tokocrypto.site` (public API, no auth) vs `www.tokocrypto.com` (requires API key for all endpoints). Always use `.site` for unauthenticated market data. The `.com` web UI is also geo-restricted; the `.site` API is globally accessible.
- **Dead source = find a replacement, don't fix it**. When a free API becomes unreliable, use the `data-source-testing` skill's systematic workflow: test 2-3 alternatives with curl, verify output quality and rate limits, then migrate. This applies to any crypto data source, not just crypto APIs.

## Pitfalls
- **CG global endpoint rate limit trap**: after `fetch_markets()` makes 5 CG calls (2 pages + 1 list + 1-2 simple/price), the free-tier rate budget is nearly exhausted. The `/global` call that follows routinely returns 429 "Too Many Requests" even with 6s spacing. The fix (`_get_cg_global()`) uses a separate 12s min-interval budget plus 3 retries, but you must NOT rely on this being fast — allow ~90-110s total for a full briefing run. The `_btc_dom_from_markets()` fallback computes BTC dominance from paginated data when `/global` still fails.
- **Paper trader `current_price_map` key mismatch (2026-06-27 fix)**: `current_price_map()` was returning prices keyed by CoinGecko ID (lowercase `"velvet"`) but `update_mark_to_market()` looked them up by portfolio symbol (uppercase `"VELVET"`). Every lookup returned None → all positions showed 0% P&L forever. Fix: track `orig_to_cgid` mapping in `current_price_map()` and return dict keyed by the original input symbol. The reverse map `cgid_to_orig` converts CG IDs back to portfolio keys. Both `update_mark_to_market()` and `open_today()` now use consistent keys.
- **Paper trader stop/target crash trap**: `update_mark_to_market()` called `float(pos["stop"])` without validation. Old briefings stored stop/target as `"?"` (string for `"n/a"`). `float("?")` raises ValueError, crashing the entire M2M update loop partway through. The crash could silently drop unprocessed positions when `save_portfolio()` is not reached. Fix: use `_safe_float()` helper (returns None for non-float values) and wrap each position's processing in a `try/except continue` so one bad position doesn't kill the whole update.
- **Price parsing fails on compact briefing format annotations**: `_safe_price("0.3973 (+8%)")` returned `None` because `float("0.3973 (+8%)")` raises `ValueError`. The compact briefing emits targets as `"0.3973 (+8%)"` (human-readable `+8%` annotation) and entries as `"near 0.3679"`. When any new parser is added or an existing one is modified, all 3 price parsers (`_safe_price` in paper_trader.py, `parse_price` in paper_executor.py, `parse_price` in signal_validator.py) must apply the same normalization: strip parenthetical suffixes `(...)`, space-separated trailing annotations, and leading prefixes (`near`, `~`, `around`, `above`, `below`). If you change the briefing format's target/stop/entry line format, you must re-verify all 3 parsers against real output. See `references/paper-trading.md` Bug 4 for the exact fix.
- **Paper trader `_get` lacked rate limiting**: `paper_trader.py`'s own `_get()` had zero rate limiting and zero retries. Any call hitting CoinGecko after the briefing's budget was exhausted got 429'd silently, making M2M updates return empty price maps. Fix: added 3 retries with exponential backoff (2×, 4×, 6× seconds) for HTTP 429 + other errors.
- **`format_summary()` table column mismatch**: every Markdown table emitted by `format_summary()` must have identical column counts in header, separator, and every data row. The `Recent closed trades` block had a 1-column header and 2-column separator while data rows had 5 columns — Telegram mangled the output into unreadable prose. Always count pipes: `| a | b |` has 4 pipes (opening + 2 separators + closing) but 2 columns. See `references/paper-trading.md` Bug 7 for the full fix history.
- **M2M `--update` never saved to disk**: `paper_trader.py --update` computed closed positions in memory but never called `save_portfolio()` or `save_ledger()`. Every M2M cron tick re-closed the same positions and re-synced to journal. Fix: add `save_portfolio(portfolio); save_ledger(ledger)` inside the `--update` branch. See `references/paper-trading.md` Bug 5.
- **`--update` fall-through to default path**: when `--update` had no `return`, running `paper_trader.py --update` reached the default path and ran M2M a second time. Fix: early-return after the update block when neither `--summary` nor `--paper-open` is set.
- **Screening coverage ceiling**: original `fetch_markets()` with single CoinGecko page of 250 covers only 198/437 TokoCrypto USDT pairs (45%). The expanded 4-phase pipeline (2 pages + batch fallback via `/simple/price` + ticker enrichment) reaches ~424/437 (97%). If adding new screeners, always verify coverage against live TokoCrypto `exchangeInfo` on `tokocrypto.site`.
- **CG rate limiter initialization**: `_CG_LAST_CALL` must NOT start at `0.0`. With Unix timestamps ~1.7B, `time.time() - 0.0` is always > any wait interval, so the first call fires instantly. Use `_CG_LAST_CALL = time.time() - (interval - 0.5)` to stagger the first call by ~0.5s.
- **Phase 3 fallback uses conservative scoring**: `/simple/price` does NOT return `market_cap_change_percentage_24h`. Fallback coins get `score = abs(p)` only, without the mcap-change boost (`max(0, mc) * 0.05`). This means they're less likely to bubble past top-500 paginated coins. This is by design — only genuinely strong movers get through.
- **~11 TokoCrypto USDT pairs have no CoinGecko entry**: symbols like AIGENSYN, AMDB, BEAMX, BTTC, EUR, EWYB, INTCB, MSTRB, RONIN, BROCCOLI714 cannot be resolved even via `/coins/list`. They are silently skipped in Phase 3 with no coverage impact (they're typically extremely low-cap or defunct tokens).
- **`/simple/price` chunk size**: CG free tier accepts up to ~150 IDs per `/simple/price` call. With 228 missing symbols across 2 chunks, both succeed under the 6s rate limiter. A third chunk (for pagination failure fallback covering all 437 symbols) also works but adds ~30s.
- **Page failure handling**: if a CoinGecko page returns a 429 error dict (not a list), `_extract_market_items()` returns `[]`. The dedup merge code must handle non-list pages gracefully (`isinstance(p, list)` guard) rather than crashing. When both pages fail, Phase 3 still works and covers all symbols via `/simple/price`.
- USDT-only screening: default scan must use TokoCrypto USDT `exchangeInfo` as the pair gate before CoinGecko candidate scoring. This prevents stablecoins, non-TokoCrypto assets, and non-USDT pairs from appearing as actionable opportunities.
- Decoupled outputs: briefing and paper-trading reports must not merge into one markdown body. Appending repeated portfolio sections over days makes the briefing unreadable.
- `.bashrc` alias: after any `.bashrc` change, verify `alias crypto-brief-now` still exists before reporting manual-run support. If missing, restore it from `scripts/briefing.py`.
- `briefing.py` edit safety: this file is brittle under hand-edits; partial indentation patches can break `simple_rules()` and collapse opportunity output to stale noise. When changing logic, prefer small isolated patches that keep control flow and indentation consistent. If you introduce a syntax error, do not re-patch blindly—re-run the script to surface the exact traceback and match the offending block line-for-line.
- Two morning jobs: do not create two morning briefing crons. Keep exactly one morning job and one afternoon job unless user explicitly requests more.
- Schedule: two separate jobs because the scheduler doesn't support multiple times in one cron expression. Current jobs: `daily-crypto-trading-briefing-morning` at 08:00 and `daily-crypto-trading-briefing-afternoon` at 14:00 local time.
- Cron job overlap: when adding or auditing cron jobs, check for schedule collisions. Current nesting: enrichment at 05:30, morning briefing at 08:00, afternoon at 14:00. If adding a new job, pick a slot that leaves at least 30min between CG-heavy jobs (briefing, orchestrator, enrichment) to avoid rate-limit contention across cron processes.
- Cron literal-date one-shots: do not schedule a job with a fixed month/day like `15 14 27 6 *` unless the user explicitly wants a single fire. They will look scheduled but never run again.
- Orphan output directories: deleted cron jobs leave directories under `~/.hermes/cron/output/<job_id>/`. These are harmless but should be cleaned up during audits to keep the workspace tidy.
- Cron timezone drift: cron jobs created under one TZ show `next_run_at` in that TZ until the scheduler recomputes. If the afternoon briefing's `next_run_at` shows a different offset from morning (e.g., +08 vs +07), it still fires at the correct wall-clock time — the TZ display is stale, not the schedule. Verify by comparing `next_run_at` against the system time: `date +%z` on the host.
- Pre-requisites: internet access, Python requests available
- Output: structured briefing saved to `reports/daily_briefing_YYYY-MM-DD.md`
- Delivery: cron job returns briefing text. If user wants message delivery, configure cron deliver target herself.
- Quality gate before sending: verify numerical sanity, source consistency, no hallucinated futures.
- Paper-trade command fallback: if a cron or manual run reports `--paper-open` is not valid, use `scripts/paper_trader.py --paper-open --briefing <path>` instead. This preserves the existing behavior after CLI flattening.
- Paper trader doesn't auto-open: `scripts/paper_trader.py` doesn't read briefings automatically. If you want the ledger to grow, explicitly trigger it after briefings. Otherwise there is no trade data for the improvement loop to learn from.
- **TokoCrypto fallback to Binance**: if `tokocrypto.site` is unreachable or returns no pairs, `fetch_markets()` and `_usdt_pairs()` silently fall back to Binance `exchangeInfo`. Briefing still runs but gates by Binance pairs instead of TokoCrypto. Check for degraded mode if you see non-TokoCrypto pairs in output.
- **`_normalize_position()` strips unknown fields**: `_normalize_position()` in `paper_trader.py` constructs a NEW dict for every position during `load_portfolio()`. Any field NOT in the `out = {…}` block is silently dropped on every load-save cycle. This bit us with trailing stop fields (bias, highest_price, trailing_stop, trailing_activated) — they were set during M2M, saved to disk, then STRIPPED on the next load, causing the trailing stop to reset to entry every 30 minutes. **Rule**: whenever you add a field to `open_position()` or `paper_executor.open_trades()`, add it to `_normalize_position()` in the same patch. Same for `_migrate_legacy_schema()` if the new field has a legacy name variant.
- **M2M frequency is the trailing stop bottleneck**: trailing stops only activate during `paper_trader.update_mark_to_market()` calls. If M2M refreshes every 10 minutes, a spike-reversal pattern can still slip through between checks at crypto speed. The 10-min `paper-trading-m2m` no_agent cron is the floor; anything slower makes the trailing stop unreliable. When adding new cron jobs, never reduce M2M frequency below 10 min. Each M2M tick costs 1 CG `/simple/price` call for all open positions, well within the free tier at ~144 calls/day.
- **Backtest trailing stops use `close` for activation**: `signal_validator.py` backtest uses candle `close` to check if the trailing stop activation threshold (+2%) was hit, then checks if `low` breached the trail level. This is a deliberate conservative choice — if the close is below the trail signal but the low breached it, we still count it. If a candle's low triggered activation and the same candle's low then breached the trail, both happen in the same candle — the trailing stop exit fires.
- **Trailing stop → journal sync (FIXED 2026-06-27)**: when `paper_trader.update_mark_to_market()` closes a position via trailing stop, it removes the position from `portfolio.json` and writes to `ledger.json`. `_sync_closed_to_journal()` now runs after every M2M update — it matches the closed position (by symbol + entry ±5%) against open signals in the strategy journal and closes them with the correct outcome. Unmatched positions get a standalone record + close. This keeps the journal in sync without manual reconciliation.
- **Signal validator reads live trail params (FIXED 2026-06-27)**: `signal_validator.py` now reads `strategy/params.json` `dynamic_risk` block via `_trail_params_path` at backtest time, falling back to multi-stage defaults (2%/1% → 6%/2% → 12%/3%) if the file is missing. The same `_trail_for_profit()` helper mirrors the live `_trail_params()` in `paper_trader.py`. If `params.json` is tuned, the backtest matches live behaviour automatically.

## Development Workflow (audit → patch → verify)
This skill exists to deliver decision-quality briefings, not just to write code. Before any "I'll add a feature" change, run the audit loop:

1. **Inventory**: list every script under `scripts/` and check LOC. Anything >300 LOC or with multiple responsibilities is a refactor candidate.
2. **Compile all**: `for f in scripts/*.py; do python3 -m py_compile "$f"; done` — passing compile is necessary but not sufficient.
3. **Smoke test each script's primary entrypoint**: import each script and call its main function against the real APIs. `py_compile` passing ≠ runtime passing. (Use `scripts/smoke_test.py` in this skill.)
4. **Behavioral diff**: parse real briefing markdown with every parser in the skill (`paper_trader`, `paper_executor`, `signal_validator`). When one parser returns 0 and another returns N, the discrepancy is the bug.
5. **Cron hygiene**: `cronjob list` and check for literal-date one-shots, schedule collisions, and jobs whose `next_run_at` is in the past. Update `references/cron-schedule.md` with any new/modified jobs and removed entries.
6. **Document findings** as a numbered task list with severity tags before patching. Then patch in priority order, validating each step with the same smoke test before moving on.
7. **Post-patch hygiene**: After the last patch passes smoke test, re-run `scripts/health_heartbeat.py` (catches script-size/mod-time drift), and update `references/cron-schedule.md` if any cron jobs were added, removed, or had their schedule changed. Commit cron-schedule.md changes in the same patch batch so they ship together.

The smoke test script `scripts/smoke_test.py` automates steps 1–4.

## Pitfalls discovered during audit (June 2026)
- Parser divergence: each of `paper_trader.py`, `paper_executor.py`, and `signal_validator.py` has its own briefing parser. Bias whitelist, symbol extraction, and price parsing drift between them. Whenever you change one, re-run the others against the same briefing file and confirm zero diff.
- Whole-coin quantities: never default to `qty = 1.0`. A `BTC` "buy" signal with `qty=1.0` commits ~$60k of notional. Always size from `risk_per_trade` and `entry - stop`.
- Schema drift on the portfolio: older positions used `qty`/`avg_entry`; newer code uses `quantity`/`entry_price`. `format_summary` will render `None` rows for legacy positions. Normalize on read.
- M2M that depends on a blocked source: `current_price_map` calling CoinCap will silently produce 0% P&L forever in DNS-blocked environments. Always route M2M through a free source with a known-good fallback (CoinGecko `/simple/price`).
- Validation loop stalled on missing candles: when CoinGecko is rate-limited AND Binance has no kline pair for a token, signals sit in `pending_validation` indefinitely. Add a `pending_validation_count` ceiling and a stale-after-N-days timeout that drops the signal from `signal_performance.json`.
- Module-level `from free_data import …` in a sibling script: works only if both files share a directory and the importer's CWD is that directory. Move imports inside the function for cron-spawned scripts whose CWD is unpredictable.
- `render_briefing()` must accept and forward every keyword arg that `render_compact_briefing()` accepts. If you add `enhanced` to the compact renderer, add it to the wrapper too — otherwise `main()` passing `--enhanced` to `render_briefing()` crashes at runtime.
- CoinGecko ID alias tables (paper_trader.py `_SYM_TO_CG` and signal_validator.py `ALIAS`) must stay in sync. `paper_trader.py`'s `current_price_map()` uses `_SYM_TO_CG` to translate portfolio keys (uppercase symbols like `VELVET`) to CoinGecko internal IDs (`velvet`). If a token is added to one table but not the other, M2M price lookups silently return empty for that position while signal validation still works — or vice versa. When adding a new alias to either table, add it to both in the same patch.
- Research-digest is the single source of truth: do NOT fall back to querying individual paper markdown files. The digest already dedups, tiers, and groups. Calling `query_papers.py` at runtime wastes file I/O and may return stale results.
- Near-duplicate detection is O(n) across existing titles: avoid checking near-dupes on every single new paper during large batch runs. The collector does it correctly for daily runs (15-50 papers); for manual backfill, disable the near-dupe guard and run a dedup post-process instead.
- `best_paper_for()` in `briefing.py` returns `{"title": ..., "ref": ..., "tier": ...}` from the digest path or `{"title": ..., "path": ..., "tier": ...}` from the old `query_papers` path. `research_line()` handles both formats — when patching either function, keep format compatibility.

## Working style preferences
- The user repeatedly asks for "proceed as your next/best recommendation". Default to auto-execute when the work is mechanical (rename function, add field, swap dependency). Pause only when there is a meaningful trade-off to flag.
- The user values reproducible trades. After any meaningful change, provide a manual verification command in the reply: `python3 scripts/paper_trader.py --update --summary`. Don’t summarize "I made it reproducible" — show the command and, if possible, one line of real output so the user can see the closed trade table.
- Always show evidence of execution (command, exit code, sample output) — never summarize "I made the change". Briefings/audit reports are evidence-first, narrative-second.
- Don't bury `py_compile` results. Run it. Show pass/fail per file in the response.
- Target philosophy: **realistic but don't leave profit on the table**. The dynamic target formula caps at 15% (no chasing impossible rallies). The multi-stage trailing stop is the bonus mechanism — it locks in extra gains when the price runs beyond the initial target. The fixed target is the primary profit exit; the trailing stop is the upside kicker. When setting targets, prefer achievable levels over aggressive ones. When trailing, let the multi-stage logic handle the profit capture.
- **Paper trading output format**: the user prefers an emoji-dashboard layout with a compact summary bar, 🟢/🔴 P&L indicators, and clean 4-column open positions / 5-column closed trades tables. Do NOT use stacked metric tables or malformed Markdown headers. For Telegram delivery, the user also approves generating an HTML dashboard screenshot image as an alternative to Markdown tables. See `references/paper-trading.md` → Output Format section.

## Failure Modes
- API key missing / rate limited: degrade gracefully and label missing coverage. Prefer `market_chart` over `/ohlc` under rate pressure.
- Token symbol resolution: some symbols map to Binance pairs (`MAGMAUSDT`) but are NOT listed on Binance spot even if CoinGecko search finds them. Binance searchable != Binance tradeable. When klines return empty and CoinGecko free tier is also rate-limited, record the signal as `pending_validation` with `exit_reason: "no_data"` instead of silently dropping it. This is the preferred behavior over skipping, so the advisor can later update confidence once candle coverage arrives.
- Free source CORS or access blocked: use alternative mirror or forum summary with origin link.
- Speculative memecoins / pump-and-dump: never draw from sub-$1M speculative memecoins, token launches with no product, or obvious pump-and-dump patterns. Mark such coins “speculative - not recommended for balanced style”. Other sub-$1M assets may be considered if they have genuine liquidity and a clear thesis, but require explicit disclosure of the elevated risk.
- Mis-specified data: do not compute risk scores with incomplete data. Disclose incompleteness explicitly.
- Research-free claims: never invent a paper citation. If lookup failed, say `no matching source in current corpus`.

