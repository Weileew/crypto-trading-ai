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
cronjob action=create name=orchestrator-nightly schedule="0 4 * * *" \
  prompt="Run the full crypto trading orchestrator cycle." \
  script=orchestrator.py \
  workdir=/home/ubuntu/.hermes/skills/trading-advisor/scripts \
  no_agent=true \
  skills='["trading-advisor"]' \
  deliver=origin

# Update maintenance to avoid collision
cronjob action=update job_id=ADVISOR_MAINTENANCE_ID schedule="0 2 * * *"
```

## Symlink (required for no_agent script execution)
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
