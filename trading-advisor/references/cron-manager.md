## Cron Schedule Manager

**Module:** `strategy/cron_manager.py`

Central registry for all TOK cron jobs with CG call costs, schedules, collision detection, and **performance-aware holistic scheduling**.

### Commands

| Flag | Output |
|---|---|
| _(no args)_ | Full report: CG budget + collision scan |
| `--performance` / `-p` | TOK performance state + state-specific schedule suggestions (✅ already-applied confirmations) |
| `--budget` / `-b` | CG daily budget breakdown by job |
| `--check-collisions` / `-c` | Same-minute collision scan |
| `--schedule` / `-s` | 24h timeline showing all job firings |
| `--auto-optimize` / `-o` | Concrete schedule shift commands with `cronjob update` syntax |

### Job Registry

The `JOB_REGISTRY` list at module level defines all 12 cron jobs. Each entry:

```python
{
    "name": "paper-trading-m2m",
    "job_id": "91d6c930e1f3",
    "schedule_cron": "every 30m",
    "cg_calls_per_run": 1,       # 0 for non-CG jobs
    "runtime_s": 3,
    "offset_minutes": 20,        # fires at XX:20 and XX:50
    "no_agent": True,
    "description": "...",
}
```

Required fields: `name`, `schedule_cron`, `cg_calls_per_run`, `description`.
Use `offset_minutes` for "every N" schedules.

### Performance State Classification

`classify_performance()` reads from `journal.db` (win rate, profit factor, streak), `signal_performance.json` (pending/validated), `portfolio.json` (drawdown), and `params.json`.

Returns one of: `hot`, `normal`, `cold`, `critical`, `insufficient_data`.

Thresholds (configured in `PERF_THRESHOLDS`):
- `win_rate_good`: 0.40, `win_rate_hot`: 0.55, `win_rate_cold`: 0.25
- `profit_factor_good`: 1.0, `profit_factor_hot`: 1.5
- `max_consecutive_losses`: 5
- `drawdown_warn_pct`: -5.0%, `drawdown_critical_pct`: -10.0%
- `min_closed_signals`: 5

### Holistic State-Based Schedule Map

**Critical insight (June 2026)**: when the user says "proceed with recommendations", apply changes across **ALL** cron jobs, not just the performance-tagged ones (M2M, briefings). The cron manager manages all 12 jobs — orchestrator, auto-push, enrichment, backups all contribute to system load, CG budget, and noise floor.

| State | M2M | Briefings | Orchestrator | Auto-push | Rationale |
|---|---|---|---|---|---|
| 🔴 CRITICAL (dd ≤ -10%) | `every 15m` | **Pause both** | Keep at 04:00 or pause | `every 60m` | Capital preservation — no new signals, tightest trailing stops |
| 🔶 COLD (wr < 25% / streak ≤ -5) | **`every 15m`** | **1/day (morning only)** | 04:00 | `every 60m` | Loss mitigation — tighter stops, fewer loss-generating signals |
| ✅ NORMAL | `every 30m` | 2/day (08:00, 14:00) | 04:00 | `every 60m` | Standard operations |
| 🟢 HOT (wr ≥ 55% / pf ≥ 1.5) | `every 30m` | 2/day (+ weekend optional) | 04:00 | `every 60m` | Capture momentum — loosen, add optional window |

**Jobs that remain fixed** (no state dependency):
- `tok-daily-diagnostic` — always 07:00 (essential monitoring)
- `research-playbook-enrichment` — always 05:30 (0 CG calls)
- `advisor-continuous-improvement` — always 00:00/12:00 (0 CG calls — improvement is valuable during cold streaks)
- `parameter-optimizer-weekly` — always Mon 06:00 (especially important during cold streak to find better params)
- `crypto-backup-refresh` — always every 6h (0 CG calls)
- `cloud-backup-hermes` — always 03:00 (infrastructure)
- `discovery-engine-weekly` — always Sun 10:00 (0 CG calls)

### Applying Changes Holistically: Workflow

```bash
# 1. Check current performance state
python3 strategy/cron_manager.py --performance

# 2. If state suggests changes, apply them across ALL jobs:
#    - M2M frequency change
cronjob action=update job_id=91d6c930e1f3 schedule="every 15m"  # or "every 30m"
#    - Pause/resume afternoon briefing
cronjob action=pause job_id=ccc18cada9a7    # cold/critical
cronjob action=resume job_id=ccc18cada9a7   # normal/hot
#    - Orchestrator time (moved from 05:00 to 04:00 to decompress morning cluster)
cronjob action=update job_id=58e8183595d8 schedule="0 4 * * *"
#    - Auto-push frequency (every 15m → every 60m is the standard now)
cronjob action=update job_id=df36310d255c schedule="every 60m"

# 3. Verify the changes are correct
python3 strategy/cron_manager.py --schedule      # visual 24h timeline
python3 strategy/cron_manager.py --budget        # verify CG budget is safe
python3 strategy/cron_manager.py --check-collisions  # verify no CG collisions
python3 strategy/cron_manager.py --performance   # verify suggestions show ✅ confirmations
```

### Resume Procedure (When Performance Recovers)

When win rate recovers above 40% and loss streak breaks:

```bash
# 1. Resume afternoon briefing
cronjob action=resume job_id=ccc18cada9a7

# 2. Ease M2M back to every 30m
cronjob action=update job_id=91d6c930e1f3 schedule="every 30m"

# 3. Update JOB_REGISTRY in cron_manager.py to reflect normal state:
#    - paper-trading-m2m: schedule_cron="every 30m", schedule_label="every 30 min"
#    - daily-crypto-trading-briefing-afternoon: keep schedule, remove pause note

# 4. Update references/cron-schedule.md to show full 2-briefing schedule
```

The cron manager's `schedule_suggestions_for_performance()` checks the actual JOB_REGISTRY and shows ✅ confirmations when changes are already applied, preventing redundant suggestions.

### Current Schedule (COLD state, June 2026)

```
03:00  ┆ cloud-backup-hermes                  ⚪ backup
04:00  ┆ orchestrator-nightly                 💸 8 CG
05:30  ┆ research-playbook-enrichment         ⚪
06:00  ┆ parameter-optimizer-weekly (Mon)     💸 2 CG
07:00  ┆ tok-daily-diagnostic                 ⚪ monitoring
08:00  ┆ daily-crypto-trading-briefing-morning 💸 6 CG
14:00  ┆ daily-crypto-trading-briefing-afternoon 🟡 PAUSED
XX:05  ┆ paper-trading-m2m                    💸 1 CG ← every 15m
XX:20  ┆ paper-trading-m2m                    💸 1 CG
XX:35  ┆ paper-trading-m2m                    💸 1 CG
XX:50  ┆ paper-trading-m2m                    💸 1 CG
:00    ┆ auto-push-github                     ⚪ every 60m (was 15m)
00/12  ┆ advisor-continuous-improvement       ⚪
Sun 10 ┆ discovery-engine-weekly              ⚪
```

CG footprint: 116.3 calls/day = 0.81% of free tier.
Peak load: 8 CG calls at 04:00 (orchestrator alone — within 10 req/min limit).
