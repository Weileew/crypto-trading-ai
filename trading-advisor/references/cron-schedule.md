# Cron Schedule

## Active Jobs (as of June 2026)

| Job ID | Name | Schedule (UTC+7) | What it does |
|--------|------|-------------------|--------------|
| `df36310d255c` | auto-push-github | `every 15m` | Auto-push local file changes to GitHub via `auto-push-github.sh` |
| `49dfd654806a` | research-playbook-enrichment | `30 5 * * *` — daily 05:30 | Runs `collect_papers_openalex.py` to fetch new crypto-trading papers from OpenAlex |
| `f0fc8b054fc8` | daily-crypto-trading-briefing-morning | `0 8 * * *` — daily 08:00 | Generates morning compact briefing with `--compact --save-only --enhanced` |
| `ccc18cada9a7` | daily-crypto-trading-briefing-afternoon | `0 14 * * *` — daily 14:00 | Generates afternoon compact briefing with `--compact --save-only --enhanced` |
| `8f85c4c753fe` | paper-trading-m2m | `15 */6 * * *` — 06:15, 12:15, 18:15, 00:15 | Updates paper trader mark-to-market via `paper_trader.py --update` |
| `ec4094d8b22d` | advisor-continuous-improvement | `0 */12 * * *` — 12:00, 00:00 | Runs `improve.py` to update heuristics |
| `5af24ee0c671` | advisor-maintenance | `0 2 * * *` — daily 02:00 | Daily maintenance pass (M2M + summary) |
| `orchestrator-nightly` | orchestrator-nightly | `0 4 * * *` — daily 04:00 | Full orchestrator cycle: news → briefing → journal → validate → performance → adapt |

## Schedule Rules

- **Enrichment**: runs at 05:30 — before the morning briefing at 08:00 — so fresh research is available for citation.
- **Briefings**: exactly 2 per day (morning 08:00, afternoon 14:00). Never create a third.
- **Orchestrator**: 04:00 daily, after all CG rate-limit windows from the enrichment run (05:30+1h=06:30) have cooled. Runs 3h before morning briefing so its digest is available.
- **Maintenance**: shifted to 02:00 to avoid collision with orchestrator (04:00) and enrichment (05:30).
- **M2M**: shifted 15 minutes past every 6h mark to avoid collision with improvement job.
- **Improvement**: fires at noon/midnight; intentional overlap with morning briefing avoided by staggering.

## Removed Jobs

| Name | Schedule | Reason |
|------|----------|--------|
| `noon-sync-paper` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `midday-signal-validator` | `15 14 27 6 *` | Literal June 27 2026 only — never runs again after that date |
| `advisor-maintenance` (old 0330) | `30 3 * * *` | Moved to 02:00 to avoid orchestrator collision |

## Adding a New Cron Job

1. Pick a slot that doesn't collide with existing schedules (check table above).
2. Use `cronjob(action='create', name=..., schedule=..., prompt=..., skills=['trading-advisor'], workdir='~/.../trading-advisor')`.
3. Update this table.
