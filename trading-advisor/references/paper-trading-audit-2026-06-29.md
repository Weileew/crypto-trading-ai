# Paper Trading Audit & Reconciliation — 2026-06-29

Findings from the paper trading system audit conducted on 2026-06-29 (see `audit_2026-06-29.md` in paper_trading/).

## Issues Discovered

### 1. Orphaned Positions in Ledger (Fixed)
Two positions existed in `ledger.json` but were never synced to the active M2M pipeline:
- **RE (RE)**: 310.28 units @ $0.616837 entry — marked `orphaned` / `legacy_archived`
- **SYN (Synapse)**: 449.38 units @ $0.416721 entry — marked `orphaned` / `legacy_archived`

These were from a stale `portfolio.json` that was never synced. The paper_trader.py `--update --summary` now shows them as `legacy_archived` with no PnL impact.

### 2. Duplicate Journal Entries
Signal validator produced duplicate journal entries for the same trades at different timestamps (e.g., SYN closed 4 times between 00:24 and 02:58 on 2026-06-29). The journal deduplication logic needs review.

### 3. Legacy qty=1 Trades
Early trades (VELVET, SKYAI, MAGMA from 2026-06-26/27) recorded with `qty=1` instead of proper position sizing. These are marked `legacy_archived` and excluded from performance metrics.

## Current Clean State (2026-06-30)

- **Portfolio**: $9,367.25 cash, 0 positions
- **Ledger**: 8 trades total (4 legacy archived, 2 orphaned archived, 2 real)
- **Journal**: 23 closed trades (includes duplicates)
- **Signal Performance**: 7 signals, 5 validated (40% win rate, PF 0.81)

## Action Items

1. [ ] Add deduplication to `signal_validator.py` journal writes (key: symbol + exit_date + exit_reason)
2. [ ] Review `paper_trader.py` sync logic to prevent stale portfolio.json drift
3. [ ] Consider purging legacy_archived trades from ledger.json for cleaner reporting
4. [ ] Update calibration: profit factor 0.81 → investigate trap-filter scores / correlation_threshold

## Files Referenced
- `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/audit_2026-06-29.md`
- `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/ledger.json`
- `/home/ubuntu/.hermes/skills/trading-advisor/reports/paper_trading/portfolio.json`
- `/home/ubuntu/.hermes/skills/trading-advisor/reports/signal_performance.json`