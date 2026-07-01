# Trading Advisor Cron Job Status — 2026-06-30

Snapshot of all active cron jobs for the trading-advisor skill as of the scheduled cron run on 2026-06-30 05:00 WIB.

## Active Jobs (11 total)

| Job ID | Name | Schedule | Status | Last Run | Next Run | Notes |
|--------|------|----------|--------|----------|----------|-------|
| f0fc8b054fc8 | daily-crypto-trading-briefing-morning | 0 8 * * * | active | 2026-06-29T08:18:08 ✅ | 2026-06-30T08:00:00 | Skills: trading-advisor, workdir: skill dir |
| ccc18cada9a7 | daily-crypto-trading-briefing-afternoon | 0 14 * * * | active | 2026-06-29T14:02:13 ✅ | 2026-06-30T14:00:00 | Skills: trading-advisor, workdir: skill dir |
| 58e8183595d8 | orchestrator-nightly | 0 4 * * * | active | 2026-06-30T04:05:40 ✅ | 2026-07-01T04:00:00 | Skills: trading-advisor, workdir: skill dir |
| 91d6c930e1f3 | paper-trading-m2m | every 15m | active | 2026-06-30T04:48:45 ✅ | 2026-06-30T05:03:45 | Script: paper-m2m-update.sh, no-agent mode |
| b366c4096b1b | weekly-performance-review | 0 20 * * 0 | active | — | 2026-07-05T20:00:00 | Skills: trading-advisor |
| af1b44ab18eb | parameter-optimizer-weekly | 0 6 * * 1 | active | 2026-06-29T06:10:09 ✅ | 2026-07-06T06:00:00 | Deliver: local |

## Paper Trading State (as of 2026-06-30 05:00)

- **Starting Capital**: $9,367.25
- **Current Cash**: $9,367.25
- **Open Positions**: 0
- **Equity**: $9,367.25 (0.0% return)
- **Journal**: 23 closed trades, 43.5% win rate, profit factor 0.81 (negative expectancy)
- **Calibration Health**: 80% — profit factor 0.81 < 1.0 needs review

## Recent Briefings

- **2026-06-28**: Extreme Fear (F&G=18), 2 opportunities (SYN, S), 1 open position (RE -0.90%)
- **2026-06-29**: Extreme Fear (F&G=12), no high-confidence setups, no open positions
- **2026-06-30**: Just generated — Extreme Fear (F&G=12), no high-confidence setups

## Research Calibration Alerts

From orchestrator_digest_2026-06-29:
- Optimal `min_24h_change_pct=5%` (current=3%) — catches 49 of 59 big movers
- Optimal `score_threshold=10` (current=25) — FP rate 0% at 10
- L1 sector correlation_threshold=0.70 appropriate (83% directional alignment)
- **Action needed**: Profit factor 0.81 < 1.0 → review trap-filter scores or increase correlation_threshold in research-calibrations.json

## Cron Job Scripts

- `/home/ubuntu/.hermes/scripts/paper-m2m-update.sh` — Paper trading mark-to-market (runs every 15m)
- `/home/ubuntu/.hermes/skills/trading-advisor/scripts/briefing.py` — Daily briefing generator
- `/home/ubuntu/.hermes/skills/trading-advisor/scripts/orchestrator.py` — Full orchestrator pipeline