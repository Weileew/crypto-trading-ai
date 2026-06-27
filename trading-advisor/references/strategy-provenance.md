# Strategy Provenance for Portfolio Positions

## Why

Every open position in the paper portfolio must know **which strategy version created it**. Without this, when strategy parameters change (via auto-adaptation or manual tuning), old positions lose their provenance — you can't tell whether a win/loss came from a tight-screening v2 signal or a loose-screening v1 signal.

The strategy provenance system solves this by:
- Assigning a deterministic **strategy ID** at position-open time
- Snapshoting the **exact params** that screened the signal
- Displaying **strategy-grouped P&L** in the portfolio summary

## Strategy ID Format

```
tok-v{version}-{date}
```

Where:
- `{version}` = `params.json` → `version` (integer, currently `2`)
- `{date}` = `YYYYMMDD` at position-open time (UTC)

Example: `tok-v2-20260627`

This is **deterministic** — all positions opened on the same day with the same version share an ID. When `adapt_params()` bumps the version (e.g., v2 → v3), new positions get `tok-v3-YYYYMMDD`.

## Functions

### `paper_trader.py:_current_strategy_identity()`

Reads `strategy/params.json` and returns:

```python
{
  "strategy_id": "tok-v2-20260627",
  "strategy_snapshot": {
    "screening": {"min_mcap": 50000000, "min_24h_change_pct": 3.0, "score_threshold": 25.0, ...},
    "risk": {"risk_per_trade_pct": 2.0, "stop_loss_pct": 3.5, "target_pct": 8.0, ...}
  }
}
```

Falls back to `{"strategy_id": "legacy", "strategy_snapshot": {}}` if `params.json` is missing or unreadable.

### `strategy_journal.py:current_strategy_identity()`

Identical logic, but uses `strategy_journal`'s own `load_params()` (reads the same `params.json` file). Exists so the orchestrator can capture strategy identity when recording signals without importing from `paper_trader.py`.

## Position Enrichment

Every position opened via `open_position()` now includes two extra fields:

```json
{
  "symbol": "syrup",
  "entry_price": 0.144208,
  "strategy_id": "tok-v2-20260627",
  "strategy_snapshot": {
    "screening": {"min_mcap": 50000000, "min_24h_change_pct": 3.0, "score_threshold": 25.0},
    "risk": {"risk_per_trade_pct": 2.0, "stop_loss_pct": 3.5, "target_pct": 8.0}
  },
  ...
}
```

`strategy_snapshot` is the **immutable copy** of the active params at entry time. Even if `params.json` changes later (via auto-adaptation), the position still knows what thresholds it passed through to open.

## Strategy-Grouped P&L in Portfolio Summary

The `format_summary()` output now groups positions by strategy:

```
| Strategy | Positions | P&L |
| --- | --- | --- |
| tok-v2-20260627 | 1 | +$0.50 |
| legacy | 1 | -$0.01 |
```

```
| Symbol | Strategy | Entry | Current | P&L | P&L % |
| --- | --- | --- | --- | --- | --- |
| SYRUP | tok-v2-20260627 | 0.1442 | 0.1444 | +0.50 | +0.1% |
| SKYAI | legacy | 0.3679 | 0.3633 | -0.01 | -2.7% |
```

## Backward Compatibility

- Positions without `strategy_id` → automatically read as `"legacy"` via `_normalize_position()`
- Positions without `strategy_snapshot` → automatically read as `{}` (empty snapshot)
- The `legacy` fallback is a catch-all for positions opened before this system existed
- No schema migration needed — the fields are additive

## Orchestrator Integration

When the orchestrator records signals in `phase_journal_signals()`, it calls `journal.current_strategy_identity()` and embeds the strategy ID in the signal's `notes` field:

```
notes="strategy=tok-v2-20260627 | score=26.1 | 24h=+21.2%"
```

This means every signal in the SQLite journal is traceable back to the strategy version that generated it.

## Evolution Path

With strategy IDs in every position, you can later:

1. **Compare strategy performance**: "Did v2 (tight screening, score>=25) outperform v1 (loose, score>=20)?"
2. **A/B test strategies**: Run two param sets simultaneously on different allocations, compare strategy-grouped P&L
3. **Auto-close stale strategies**: "Close all v1 positions — they're using outdated thresholds that performed worse"
4. **Strategy-bucketed reports**: Show win rate / profit factor / average P&L per strategy version

## Pitfalls

- **Strategy ID is date-anchored**: `tok-v2-20260627` identifies the strategy at position-open time. If params change the next day, both `tok-v2-20260627` and `tok-v3-20260628` positions coexist. This is correct — each remembers its own screening context.
- **Snapshot vs live params**: `strategy_snapshot` is an immutable copy. Do NOT update it on M2M — the whole point is that it captures entry conditions. Live params are always read from `strategy/params.json`.
- **Legacy positions show no snapshot**: Positions with `strategy_id: "legacy"` have `strategy_snapshot: {}`. Code that reads `strategy_snapshot` must handle missing fields gracefully (`.get("screening", {})`, not `["screening"]`).
- **Both identity functions must stay in sync**: `_current_strategy_identity()` in `paper_trader.py` and `current_strategy_identity()` in `strategy_journal.py` read the same `params.json`. If you change the strategy ID format, patch BOTH files.
