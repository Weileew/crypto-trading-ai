# Cron Schedule

## Active Jobs (as of June 2026)

| Job ID | Name | Schedule (UTC+7) | What it does | Cost |
|--------|------|-------------------|--------------|------|
| `df36310d255c` | auto-push-github | `every 60m` | Auto-push local file changes to GitHub via `auto-push-github.sh`. Reduced from 15m to 60m during cold trading state. | — |
| `49dfd654806a` | research-playbook-enrichment | `30 5 * * *` — daily 05:30 | Runs `collect_papers_openalex.py` to fetch new crypto-trading papers from OpenAlex. Deliver: local (digest consumed by briefing citation pipeline). | LLM |
| `2c64dd10c714` | tok-briefing | `0 2,6,10,14,18,22 * * *` — 6×/day | Generates compact briefing with `--compact --save-only --paper-open --enhanced`. Auto-opens paper trades inline via `--paper-open` (no separate executor step). **no_agent** — zero LLM tokens, stdout delivered to Telegram. | 5 CG calls |
| `91d6c930e1f3` | paper-trading-m2m | `every 15m` | Updates paper trader mark-to-market + trailing stop checks via `paper_trader.py --update --summary`. **no_agent** — zero LLM tokens, silent when no events, delivers to origin on position closes/errors. Increased from 30m for tighter risk management during cold state. | 1 CG call |
| `58e8183595d8` | orchestrator-nightly | `0 4 * * *` — daily 04:00 | Full orchestrator cycle: news → briefing → journal → validate → performance → adapt → calibration health → dashboard. Moved from 05:00 to decompress morning CG cluster (04:00 is 90min from enrichment at 05:30). | LLM |
| `e2d7034a03f8` | discovery-engine-weekly | `0 10 * * 0` — weekly Sun 10:00 | Runs self-architect discovery engine | agent |
| `cd08dca87913` | crypto-backup-refresh | `0 */6 * * *` — every 6h | Syncs Hermes skills to `~/crypto-trading-ai` repo via `backup-crypto-repo.sh`. **no_agent** | — |
| `af1b44ab18eb` | parameter-optimizer-weekly | `0 6 * * 1` — weekly Mon 06:00 | Sweeps 500 CoinGecko coins for optimal `min_24h_change_pct` and `score_threshold`; writes `strategy/optimizer_report.json`. Deliver: local (orchestrator surfaces findings in nightly digest). | 2 CG calls |
| `b973000ea6fc` | cloud-backup-hermes | `0 3 * * *` — daily 03:00 | Hermes config + data backup via `cloud-backup.sh`. **no_agent** | — |
| `b366c4096b1b` | weekly-performance-review | `0 20 * * 0` — weekly Sun 20:00 | Reads journal.db for 7-day trend vs prior 7 days: win rate, best/worst trades, drawdown, F&G trend, optimizer findings. Compact bullet format, ~200 words. | LLM |

## Data Directory Sync
**Critical**: The M2M cron (`paper-trading-m2m`) runs from `/home/ubuntu/.hermes/skills/trading-advisor` workdir and reads/writes `reports/paper_trading/` **in the skill directory**. The canonical verified data lives in `/home/ubuntu/crypto-trading-ai/trading-advisor/reports/paper_trading/`. After any manual reconciliation (see `references/paper-trading-reconciliation.md`), **always sync both ways**:
```bash
cp /home/ubuntu/crypto-trading-ai/trading-advisor/reports/paper_trading/*.json \
   /home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/
```
The `crypto-backup-refresh` cron (every 6h) handles this automatically, but manual verification should sync immediately.

## Schedule Rules

- **No same-minute CG collisions**: Scheduled to avoid any two CG-carrying jobs firing in the same minute. Auto-push and backup have 0 CG calls and don't count.
- **Enrichment**: runs at 05:30 — before the morning briefing at 08:00 — so fresh research is available for citation.
- **Orchestrator**: 04:00 daily (moved from 05:00 to separate from enrichment at 05:30 and reduce morning CG cluster from 8 calls/min).
- **Briefings**: 6 per day (02/06/10/14/18/22 UTC+7). `no_agent` script — zero LLM token cost. `--paper-open` flag auto-executes paper trades inline during the briefing run, eliminating the separate paper_executor.py step. Each run overwrites the same `daily_briefing_DATE.md` file. Capital recycling: when M2M closes a position (stop/target/trail), the next briefing run can re-open it at the new price.
- **M2M**: every 15 min during cold state (96 CG calls/day), reverts to every 30 min in normal/hot state (48 CG calls/day). Uses `no_agent` mode — 1 CG `/simple/price` call per tick via `free_data._get_cg()`. Silent when no positions close; delivers to Telegram only on position-closed events or errors.
- **CG rate limits**: all CG calls across the system go through `free_data._get_cg()` with 6s spacing + daily counter at `reports/cg_call_count.json`. See `references/cg-rate-limit.md`.
- **Performance-aware scheduling**: Run `python3 strategy/cron_manager.py --performance` to check current trading state and get schedule recommendations. The `--auto-optimize` flag generates concrete `cronjob update` commands.

## State-Based Schedule Map

| Performance State | M2M | Briefings | Orchestrator | Auto-push | Rationale |
|---|---|---|---|---|---|---|
| 🔴 CRITICAL (dd ≤ -10%) | every 15m | Pause all | Pause | every 60m | Capital preservation |
| 🔶 COLD (wr <25% / streak ≤ -5) | every 15m | 6/day (no_agent) | 04:00 | every 60m | More runs = more paper trading data for faster strategy validation |
| ✅ NORMAL | every 30m | 6/day (no_agent) | 04:00 | every 60m | Standard operations, zero LLM cost for briefings |
| 🟢 HOT (wr ≥55% / pf ≥1.5) | every 30m | 6/day (no_agent) | 04:00 | every 60m | Capture momentum |

## Removed Jobs

| Name | Schedule | Reason |
|------|----------|--------|
| `noon-sync-paper` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `midday-signal-validator` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `advisor-maintenance` (old 0330) | `30 3 * * *` | Moved to 02:00, then removed — now redundant after 10-min M2M cron |
| `paper-trading-m2m` (old) | `15 */6 * * *` | Replaced by no_agent version, then 30-min -> 15-min with trailing stop + event-only notifications |
| `advisor-continuous-improvement` | `0 */12 * * *` | Removed 2026-06-29 — passive read-only analyzer, superseded by orchestrator calibration health |
| `daily-crypto-trading-briefing-morning` | `0 8 * * *` | Replaced by `tok-briefing` (6×/day no_agent script with --paper-open). Old job cost ~20K tokens/run via LLM agent. |
| `daily-crypto-trading-briefing-afternoon` | `0 14 * * *` | Replaced by `tok-briefing`. Identical pipeline, no LLM cost, auto-executes trades inline. |

## Adding a New Cron Job

1. Pick a slot that doesn't collide with existing schedules (check table above).
2. Use `cronjob(action='create', name=..., schedule=..., prompt=..., skills=['trading-advisor'], workdir='~/.../trading-advisor')`.
3. Update this table.
