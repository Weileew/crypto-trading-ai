---
name: trading-advisor
description: "Crypto market analysis and trading advisory skill for Hermes Agent. Generates swing/day trading briefings with multi-source free data, detailed reasoning, risk controls, and delivery via cron."
version: 0.3.0
author: user
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cryptocurrency, trading, crypto]
---

# Crypto Trading Advisor

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
- Detailed analysis output only when explicitly requested; otherwise keep concise and actionable.

## Skill Links
- Free sources: `references/data-sources.md`
- New free integrations: `references/free-data-integration-notes.md` (DeFiLlama, DEX Screener, stablecoin flows)
- TokoCrypto: `references/tokocrypto.md`
- Trade log template: `references/log_sheet.md`
- Compact briefing format: `references/compact-briefing-template.md`
- Cron schedule: `references/cron-schedule.md`
- Data source migration guide: see `data-source-testing` skill (general workflow for replacing dead APIs)
- Audit checklist: `references/audit-checklist.md` (use before any non-trivial patch)
- Orchestrator setup: `references/orchestrator-setup.md` (deployment, cron, symlinks, smoke test cleanup)
- ElementTree `__len__` gotcha: `references/elementree-len-gotcha.md` (Python XML debugging trap)
- Smoke test: `scripts/smoke_test.py` (run after every change; gates each parser, fetcher, and entrypoint)
- Scripts: `scripts/free_data.py`, `scripts/briefing.py`, `scripts/trade_plan.py`, `scripts/paper_trader.py`, `scripts/market_snapshot.py`, `scripts/pre_market_snapshot.sh`, `scripts/daily_loop.py`, `scripts/paper_executor.py`, `scripts/health_heartbeat.py`, `scripts/strategy_journal.py`, `scripts/market_news.py`, `scripts/orchestrator.py`

## Research Enrichment
Research papers are sourced from **OpenAlex** (free scholarly API, no auth) via `scripts/collect_papers_openalex.py` in the `crypto-research` skill. A daily cron job (`research-playbook-enrichment`) at 05:30 fetches new papers before the morning briefing. Currently **116 papers** (76 Tier A peer-reviewed + 31 Tier B preprint + 9 Tier C). Updated count as of 2026-06-27 enrichment run (+5 new papers). Use `best_paper_for()` in `briefing.py` (reads consolidated digest) or `scripts/query_papers.py` for manual search.

## Workflow
1. Identify user request type: watchlist, coin deep-dive, briefing, or sanity check.
2. Run the appropriate script from workdir `~/.hermes/skills/trading-advisor` as needed.
3. Consult `crypto-research/references/research-digest.md` via `best_paper_for()` in `briefing.py` for relevant research before making strategy claims. The consolidated digest is a single file (O(1) read) grouping all validated papers by topic. Local corpus only first; use web search only when zero matches are found and label it external evidence.
4. Gather free market data (3-phase screening pipeline in `briefing.py` `fetch_markets()`):
   - **Phase 1 — Pagination**: Fetch CoinGecko `/coins/markets` pages 1–2 (500 coins by mcap ranking). This covers ~198 of the 437 active Binance USDT pairs (top ~45%).
   - **Phase 2 — USDT Gate**: Keep only symbols that trade as active Binance USDT pairs via `GET /api/v3/exchangeInfo` (437 pairs as of mid-2026). Discards everything else.
   - **Phase 3 — Batch Fallback**: For the ~239 Binance USDT pairs NOT in the paginated top 500, resolve their CoinGecko IDs via `/coins/list` and batch-fetch price data via `/simple/price` (chunks of 150 IDs, 1–2 API calls). These fallback coins get conservative scoring (no `market_cap_change_percentage_24h` — score = `abs(p)` only).
   - **Coverage**: 97% of all Binance USDT pairs (424–426 of 437). ~11 symbols have no CoinGecko entry at all and are silently skipped.
   - Additional fetches:
     - Macro/sentiment: Fear & Greed, BTC dominance
     - Sector/defi signals: DeFiLlama protocols by TVL, yield pools, stablecoin circulation delta
     - DEX activity: DEX Screener search for txn/volume/price-change context
     - On-chain: Glassnode free endpoint data, CryptoQuant free signals, or Santiment general alerts
     - News: `scripts/market_news.py --compact` fetches from CoinTelegraph + CoinDesk RSS + Fear & Greed (free, no API key)
     - Technicals: indicator-calculation from OHLCV via helper scripts
     - Exchange liquidity: TokoCrypto manual snapshot only when coin is listed there (see `references/tokocrypto.md`). TokoCrypto auto-screening is NOT supported.
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
14. USDT-only screening: before candidate scoring, gate market lists with Binance `exchangeInfo` `USDT` trading pairs. This filters stablecoins, wash-USDT proxy tokens, and non-USDT pairs with one stable pass and should be the default scan rule.

## Scripts
- `scripts/signal_validator.py` — backtests recent briefings against market data and writes `reports/signal_performance.json`. Preferred candle source: CoinGecko `market_chart`; fallback: Binance klines. Run after briefings to accumulate signal-quality stats; pair with `scripts/improve.py` for the learning loop. Uses `ALIAS` table plus CoinGecko `search` fallback for unknown tickers, capped at 90 days for resolved ids and 30 days for unresolved ones.
- `scripts/improve.py` — continuous maintenance/improvement pass for the advisor.
- `scripts/paper_trader.py` — paper-trading ledger; does not automatically open trades from briefings unless invoked.
- `scripts/briefing.py` — briefing generator. Key functions:
  - `fetch_markets()` — 3-phase screening (pagination, USDT gate, batch fallback), returns ~424 candidates covering 97% of Binance USDT pairs
  - `_fetch_coingecko_page()` — single CG page fetch (250 coins by mcap)
  - `_fetch_coingecko_coin_list()` — returns `{SYMBOL: id}` map for all 17K+ CG coins
  - `_get_cg()` — CG-specific GET with 6s rate limiter + 4×2x backoff retries
  - `simple_rules()` — gates stablecoins, mcap<25M, |24h|<2%, score<20; returns top 15
  - `render_compact_briefing()` / `render_briefing()` — output formatters
- `scripts/free_data.py` — centralized free-data fetcher; owns the retry + rate-limit logic used by other scripts.
- `scripts/trade_plan.py` — trade-plan builder.
- `scripts/market_snapshot.py` / `scripts/pre_market_snapshot.sh` — snapshot helpers.
- `scripts/paper_executor.py` — parse today's briefing and open paper trades directly into ledger/portfolio, then refresh M2M via `paper_trader.py --update --summary`. Uses `RISK_PER_TRADE = 0.02` (2% of cash per trade) — never hardcodes `qty = 1.0`.
- `scripts/health_heartbeat.py` — generates `reports/health.json` with last-run timestamp and script sizes/mod-times. Run or cron after briefings to track system health.
- `scripts/strategy_journal.py` — persistent SQLite journal recording every signal, outcome, param change, and performance snapshot. This is the long-term memory for the orchestrator. CLI: `python3 scripts/strategy_journal.py signals|performance|params-history|adapt|record-signal|close-signal`.
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

Adjustable parameters persisted in JSON, auto-updated by the orchestrator:

```json
{
  "screening": {
    "min_mcap": 25000000,
    "min_24h_change_pct": 2.0,
    "score_threshold": 20.0,
    "score_mcap_boost_weight": 0.05
  },
  "risk": {
    "risk_per_trade_pct": 2.0,
    "stop_loss_pct": 3.5,
    "target_pct": 8.0
  },
  "adaptation": {
    "enabled": true,
    "min_signals_before_adjust": 20,
    "win_rate_target": 0.55,
    "win_rate_minimum": 0.40,
    "max_consecutive_losses": 5,
    "tighten_multiplier": 1.3,
    "loosen_multiplier": 0.85
  }
}
```

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

| Job | Schedule | Purpose |
|---|---|---|
| `orchestrator-nightly` | `0 4 * * *` | Full 6-phase cycle (news → briefing → journal → validate → performance → adapt) |
| `daily-crypto-trading-briefing-morning` | `0 8 * * *` | Morning briefing only (lighter, faster) |
| `daily-crypto-trading-briefing-afternoon` | `0 14 * * *` | Afternoon briefing only |

> **Note**: Signal validation is handled by the orchestrator's Phase 4 (nightly) and signal_validator.py (manual/on-demand). A standalone validation cron is NOT created because it would add unnecessary CG API load on the free tier.
>
> **⚠️ 2026-06-27 FIX**: The orchestrator-nightly cron was running in `no_agent=True` mode with `script: orchestrator.py`. Since `__file__` for symlinks resolves to the symlink path (not the resolved target), `SKILL_DIR` resolved to `~/.hermes/` instead of `~/.hermes/skills/trading-advisor/`. This caused all internal imports (strategy_journal, briefing, market_news) to look in `~/.hermes/scripts/` and fail with `FileNotFoundError`. Fixed: switched to prompt-driven mode (the agent runs `python3 scripts/orchestrator.py` from the skill workdir). See `scripts/orchestrator.py` line 29 for `SKILL_DIR` resolution.

### Orchestrator Pitfalls
- **CG rate limits apply**: a full orchestrator run makes 7+ CG API calls (2 pages + 1 list + 1–2 simple/price + 1 global + 1 simple/price for validation). At 6s spacing, that's ~55–70s wall time. Do not schedule the orchestrator and a briefing cron within 5 minutes of each other.
- **News source fragility**: RSS feeds (CoinTelegraph, CoinDesk) may occasionally be unreachable. The fallback source (Fear & Greed only) always works. If both RSS feeds fail, the news section shows Fear & Greed only.
- **Journal DB growth**: `signals` and `outcomes` tables grow by ~2–4 rows/day. At this rate the DB stays under 10MB for years. No maintenance needed.
- **Smoke test signal cleanup**: `probe_strategy_journal()` in smoke_test.py creates and then immediately deletes a real signal in the DB. No manual cleanup needed. If the smoke test is interrupted mid-probe, run `DELETE FROM signals WHERE source='smoke_test'` (with foreign_keys=OFF) to clean up.
- **Performance with 0 signals**: `compute_performance()` handles zero-signal cases with `division by zero` guard (returns 0.0 for win rate, empty best/worst symbols). `adapt_params()` returns `insufficient_data` when `closed_signals < min_signals_before_adjust`.
- **`no_agent` cron + symlink `__file__`**: When a script in `~/.hermes/scripts/` (a symlink) runs in `no_agent=True` mode, Python's `__file__` resolves to the symlink path, NOT the resolved target. This means `os.path.dirname(__file__)` = `~/.hermes/scripts/` and `SKILL_DIR` = `~/.hermes/`. The orchestrator must NOT use `no_agent` mode — it needs a regular prompt-driven cron with `workdir` set to the skill directory so the agent runs `python3 scripts/orchestrator.py` from the correct location.
- **`Element.__len__` gotcha**: `xml.etree.ElementTree.Element.__len__()` returns child count, not text length. For text-only elements like `<title>text</title>`, `bool(element)` is `False` — never use `element or fallback`. See `references/elementree-len-gotcha.md` for detection, fix, and verification script.

## Briefing Format Contract
Current compact briefings use bullet blocks under `## Opportunities` (not always numbered). Each item has:
- `Name (symbol)` on its own line
- `- Bias: ...`
- `- Entry: ...`
- `- Stop: ...`
- `- Target: ...`
- `- Liquidity: ...`
- `- Research: [🟢 peer-reviewed] "Paper Title" (doi:...)` — auto-populated from `research-digest.md`, Tier A only when available
`signal_validator.py`'s parser must tolerate both numbered items (`1. Name`) and plain header lines with parentheses. Bias variants accepted: `buy bias`, `bullish`, `long`, `accumulate`, `buy`.

## Rate Limits & Resilience
- CoinGecko free tier enforces **~10 req/min** (effectively 1 call per 6s); bursts >5 calls in 30s trigger 429 that persists even with exponential backoff.
- `scripts/briefing.py` has a **CG-specific rate limiter** (`_get_cg()`) with 6s minimum spacing between calls, plus 4 retries at 2× backoff. This is separate from the generic `_RATE_DELAY_SECS` in `free_data.py` (which only enforces 0.55s spacing and is NOT suitable for CoinGecko). All CoinGecko calls in `briefing.py` must use `_get_cg()`, never bare `_get()`.
- The CG rate limiter initializes with a stagger (`_CG_LAST_CALL = time.time() - 5.5s`) so the first call doesn't fire instantly. A `_CG_LAST_CALL = 0.0` initialization causes the first call to skip the wait (time difference = ~1.7B, always > 6s).
- Total CG calls per briefing run: **5** (2 markets pages + 1 coin list + 1–2 simple/price batches). Total wall time: ~60–75s from rate-limit waiting.
- `scripts/free_data.py` centralizes generic inter-call throttle + backoff for non-CG endpoints (DeFiLlama, DEX Screener, Fear&Greed, CoinCap). These have less aggressive rate limits.
- When CoinGecko is rate-limited, prefer `market_chart` over `/ohlc` for recovery because it returns data for more symbols on the public tier.
- Binance `GET /api/v3/klines` is useful as a CoinGecko fallback for liquid USDT pairs.
- CoinCap `api.coincap.io` may be DNS-blocked on some environments; do not depend on it as the primary cache path.
- **Dead source = find a replacement, don't fix it**. When a free API becomes unreliable, use the `data-source-testing` skill's systematic workflow: test 2-3 alternatives with curl, verify output quality and rate limits, then migrate. This applies to any data source in the skill, not just crypto APIs.

## Pitfalls
- **Screening coverage ceiling**: original `fetch_markets()` with single CoinGecko page of 250 covers only 198/437 Binance USDT pairs (45%). The expanded 3-phase pipeline (2 pages + batch fallback via `/simple/price`) reaches ~424/437 (97%). If adding new screeners, always verify coverage against live Binance `exchangeInfo`.
- **CG rate limiter initialization**: `_CG_LAST_CALL` must NOT start at `0.0`. With Unix timestamps ~1.7B, `time.time() - 0.0` is always > any wait interval, so the first call fires instantly. Use `_CG_LAST_CALL = time.time() - (interval - 0.5)` to stagger the first call by ~0.5s.
- **Phase 3 fallback uses conservative scoring**: `/simple/price` does NOT return `market_cap_change_percentage_24h`. Fallback coins get `score = abs(p)` only, without the mcap-change boost (`max(0, mc) * 0.05`). This means they're less likely to bubble past top-500 paginated coins. This is by design — only genuinely strong movers get through.
- **~11 Binance USDT pairs have no CoinGecko entry**: symbols like AIGENSYN, AMDB, BEAMX, BTTC, EUR, EWYB, INTCB, MSTRB, RONIN, BROCCOLI714 cannot be resolved even via `/coins/list`. They are silently skipped in Phase 3 with no coverage impact (they're typically extremely low-cap or defunct tokens).
- **`/simple/price` chunk size**: CG free tier accepts up to ~150 IDs per `/simple/price` call. With 228 missing symbols across 2 chunks, both succeed under the 6s rate limiter. A third chunk (for pagination failure fallback covering all 437 symbols) also works but adds ~30s.
- **Page failure handling**: if a CoinGecko page returns a 429 error dict (not a list), `_extract_market_items()` returns `[]`. The dedup merge code must handle non-list pages gracefully (`isinstance(p, list)` guard) rather than crashing. When both pages fail, Phase 3 still works and covers all symbols via `/simple/price`.
- USDT-only screening: default scan must use Binance USDT `exchangeInfo` as the pair gate before CoinGecko candidate scoring. This prevents stablecoins and non-USDT assets from appearing as actionable opportunities.
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
- Paper trader doesn't auto-open: `scripts/paper_trader.py` doesn’t read briefings automatically. If you want the ledger to grow, explicitly trigger it after briefings. Otherwise there is no trade data for the improvement loop to learn from.

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
- Always show evidence of execution (command, exit code, sample output) — never summarize "I made the change". Briefings/audit reports are evidence-first, narrative-second.
- Don't bury `py_compile` results. Run it. Show pass/fail per file in the response.

## Failure Modes
- API key missing / rate limited: degrade gracefully and label missing coverage. Prefer `market_chart` over `/ohlc` under rate pressure.
- Token symbol resolution: some symbols map to Binance pairs (`MAGMAUSDT`) but are NOT listed on Binance spot even if CoinGecko search finds them. Binance searchable != Binance tradeable. When klines return empty and CoinGecko free tier is also rate-limited, record the signal as `pending_validation` with `exit_reason: "no_data"` instead of silently dropping it. This is the preferred behavior over skipping, so the advisor can later update confidence once candle coverage arrives.
- Free source CORS or access blocked: use alternative mirror or forum summary with origin link.
- Speculative memecoins / pump-and-dump: never draw from sub-$1M speculative memecoins, token launches with no product, or obvious pump-and-dump patterns. Mark such coins “speculative - not recommended for balanced style”. Other sub-$1M assets may be considered if they have genuine liquidity and a clear thesis, but require explicit disclosure of the elevated risk.
- Mis-specified data: do not compute risk scores with incomplete data. Disclose incompleteness explicitly.
- Research-free claims: never invent a paper citation. If lookup failed, say `no matching source in current corpus`.

