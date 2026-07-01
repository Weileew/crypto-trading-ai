# Orchestrator Setup

Deployment sequence when setting up or re-deploying the orchestrator after a skill reset:

## Files
| Path | Purpose |
|---|---|
| `scripts/orchestrator.py` | Main coordinator — 6-phase pipeline |
| `scripts/strategy_journal.py` | SQLite journal DB |
| `scripts/market_news.py` | Free news fetcher (CoinTelegraph, CoinDesk RSS, Fear & Greed) |
| `strategy/params.json` | Adjustable strategy params |
| `strategy/journal.db` | (auto-created on first use) |

## Cron jobs

```bash
# Full nightly orchestrator (04:00 UTC)
# NOTE: Do NOT use no_agent=true for orchestrator.py — it uses __file__-based path resolution
# (SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) which breaks
# when run via no_agent cron because Python resolves __file__ to the symlink path
# (~/.hermes/scripts/orchestrator.py) instead of the actual skill directory.
# Use prompt-driven mode with workdir instead.
cronjob action=create name=orchestrator-nightly schedule="0 4 * * *" \
  prompt="Run the full crypto trading orchestrator cycle." \
  workdir=/home/ubuntu/.hermes/skills/trading-advisor \
  skills='["trading-advisor"]' \
  deliver=origin

# Update maintenance to avoid collision
cronjob action=update job_id=ADVISOR_MAINTENANCE_ID schedule="0 2 * * *"
```

## Symlink (required for no_agent script execution)
<!-- Note: orchestrator.py should NOT use this symlink/no_agent pattern.
     It's only needed for scripts that don't use __file__-based path resolution. -->
```bash
mkdir -p ~/.hermes/scripts
ln -sf /home/ubuntu/.hermes/skills/trading-advisor/scripts/orchestrator.py \
  ~/.hermes/scripts/orchestrator.py
```

## Smoke test cleanup

`probe_strategy_journal()` in smoke_test.py now auto-cleans its test signal after verification (PRAGMA foreign_keys=OFF, DELETE signal + outcome). No manual cleanup needed after a successful smoke test run. If the smoke test is interrupted mid-probe (Ctrl+C, crash), clean up with:

```bash
python3 -c "
import os, sys
sys.path.insert(0, 'scripts')
from strategy_journal import get_conn
conn = get_conn()
conn.execute('PRAGMA foreign_keys=OFF')
conn.execute(\"DELETE FROM outcomes WHERE exit_reason='smoke_test'\")
conn.execute(\"DELETE FROM signals WHERE source='smoke_test'\")
conn.commit()
conn.close()
"
```

## Rate-limit notes
- Full orchestrator: ~7 CG calls × 6s = ~55–70s wall time
- Must not overlap with enrichment (05:30) or briefings (08:00, 14:00) within a 5min window
- Current safe nesting: maintenance 02:00 → orchestrator 04:00 → enrichment 05:30 → briefing 08:00

## Known pitfalls
- **`__file__` resolution in `no_agent` cron**: When a script in `~/.hermes/scripts/` (a symlink) runs in `no_agent=True` mode, Python's `__file__` resolves to the symlink path, NOT the resolved target. This means `os.path.dirname(__file__)` = `~/.hermes/scripts/` and `SKILL_DIR` = `~/.hermes/`. The orchestrator must NOT use `no_agent` mode — it needs a regular prompt-driven cron with `workdir` set to the skill directory so the agent runs `python3 scripts/orchestrator.py` from the correct location.
- **Relative imports in cron context**: The orchestrator's `build_digest()` function attempts to import `strategy.portfolio_engine` for calibration health checks. This fails because the cron environment doesn't have the skill's `strategy/` directory in `sys.path`. The fix (applied in `scripts/orchestrator.py`) uses `importlib.util.spec_from_file_location()` with an absolute path based on `STRATEGY_DIR` (derived from `SKILL_DIR`), matching the pattern used in `briefing.py`'s `_lazy_load_portfolio_engine()`.
