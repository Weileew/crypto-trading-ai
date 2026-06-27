# Cron Schedule

## Active Jobs (as of June 2026)

| Job ID | Name | Schedule (UTC+7) | What it does | Cost |
|--------|------|-------------------|--------------|------|
| `df36310d255c` | auto-push-github | `every 15m` | Auto-push local file changes to GitHub via `auto-push-github.sh` | — |
| `49dfd654806a` | research-playbook-enrichment | `30 5 * * *` — daily 05:30 | Runs `collect_papers_openalex.py` to fetch new crypto-trading papers from OpenAlex | LLM |
| `f0fc8b054fc8` | daily-crypto-trading-briefing-morning | `0 8 * * *` — daily 08:00 | Generates morning compact briefing with `--compact --save-only --enhanced` | LLM |
| `ccc18cada9a7` | daily-crypto-trading-briefing-afternoon | `0 14 * * *` — daily 14:00 | Generates afternoon compact briefing with `--compact --save-only --enhanced` | LLM |
| `91d6c930e1f3` | paper-trading-m2m | `every 10m` | Updates paper trader mark-to-market + trailing stop checks via `paper_trader.py --update --summary`. **no_agent** — zero LLM tokens, silent when no events, delivers to origin on position closes/errors. | 1 CG call |
| `ec4094d8b22d` | advisor-continuous-improvement | `0 */12 * * *` — 12:00, 00:00 | Runs `improve.py` to update heuristics | LLM |
| `orchestrator-nightly` | orchestrator-nightly | `0 4 * * *` — daily 04:00 | Full orchestrator cycle: news → briefing → journal → validate → performance → adapt | LLM |

## Schedule Rules

- **Enrichment**: runs at 05:30 — before the morning briefing at 08:00 — so fresh research is available for citation.
- **Briefings**: exactly 2 per day (morning 08:00, afternoon 14:00). Never create a third.
- **Orchestrator**: 04:00 daily, after all CG rate-limit windows from the enrichment run (05:30+1h=06:30) have cooled. Runs 3h before morning briefing so its digest is available.
- **M2M**: every 10 min, no_agent mode — makes 1 CG `/simple/price` call per tick. Silent when no positions close; delivers to Telegram only on position-closed events or errors. 144 calls/day is well within CG free tier.
- **Improvement**: fires at noon/midnight; intentional overlap with morning briefing avoided by staggering.

## Removed Jobs

| Name | Schedule | Reason |
|------|----------|--------|
| `noon-sync-paper` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `midday-signal-validator` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `advisor-maintenance` (old 0330) | `30 3 * * *` | Moved to 02:00, then removed — now redundant after 10-min M2M cron |
| `paper-trading-m2m` (old) | `15 */6 * * *` | Replaced by no_agent 30-min version, then 10-min version with trailing stop + event-only notifications |

## Adding a New Cron Job

1. Pick a slot that doesn't collide with existing schedules (check table above).
2. Use `cronjob(action='create', name=..., schedule=..., prompt=..., skills=['trading-advisor'], workdir='~/.../trading-advisor')`.
3. Update this table.
