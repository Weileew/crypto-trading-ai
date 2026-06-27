# Dynamic Risk: Target/Stop Formula & Trailing Stops

## Dynamic Target/Stop Formula

In `render_compact_briefing()` in `briefing.py`, target and stop percentages are computed per-candidate using volatility and score:

```python
vol = abs(c.get("change_24h", 3.0))       # volatility proxy (24h move)
score = c.get("score", 25)                 # screening score
base_target = 8.0                          # from params.json dynamic_risk.base_target_pct
base_stop = 3.5                            # from params.json dynamic_risk.base_stop_pct
vol_factor = max(0.5, vol / 3.0)           # 1.0x at 3% vol
score_rr = max(0.8, min(1.5, (score - 15) / 20))  # 1.0x at score=35
target_pct = min(15.0, max(5.0, base_target * vol_factor * score_rr))
stop_tighten = max(0, (score - 25) * 0.03)           # tighter stop for high score
stop_pct = min(8.0, max(2.0, base_stop * (vol_factor ** 0.5) - stop_tighten))
```

The R/R ratio improves with score — from ~1.8x at score 25 to ~4.1x at score 45 on same 3% volatility.

### Example outputs

| Scenario | Target | Stop | R/R |
|---|---|---|---|
| Low vol (1.5%), avg score 25 | 5.0% | 2.5% | 2.0x |
| Normal (3%), avg score 25 | 6.4% | 3.5% | 1.8x |
| Normal (3%), high score 45 | 12.0% | 2.9% | 4.1x |
| High vol (8%), avg score 25 | 15.0% | 5.7% | 2.6x |
| High vol (8%), high score 45 | 15.0% | 5.1% | 2.9x |
| Extreme (12%), avg score 25 | 15.0% | 7.0% | 2.1x |

Clipping: `target_pct` is clamped to [5, 15], `stop_pct` to [2, 8]. These bounds are in `params.json dynamic_risk`.

## Multi-Stage Trailing Stop Mechanics

Replaced the old single-stage (activate 2%, trail 1.5%) with a configurable multi-stage system. The trail reads `trailing_stages` from `params.json dynamic_risk` live on each M2M tick via `_trail_params()` in `paper_trader.py`. The same stages are mirrored in `signal_validator.backtest()` via `_trail_for_profit()`, which also reads `params.json`.

### Default stages

| Profit | Trail distance | Behaviour |
|---|---|---|
| ≥ +2% | 1.0% | Tight — locks in early gains fast |
| ≥ +6% | 2.0% | Medium — lets strong moves breathe |
| ≥ +12% | 3.0% | Wide — maximises blow-off runs |

These are set in `params.json`:
```json
"trailing_stages": [[2.0, 1.0], [6.0, 2.0], [12.0, 3.0]]
```

To tune, edit `params.json` — no code changes needed. Add stages, remove stages, change thresholds. `_trail_params()` reads them dynamically each tick.

### Activation (bullish)
1. Track `highest_price = max(current_price, highest_price)` on every M2M tick
2. When `profit_pct >= 2%`, arm the trail: `trailing_stop = highest_price * (1 - distance/100)`
3. Distance depends on peak profit stage (tightens, not loosens with higher peaks)
4. Once armed, tighten the stop on new highs using the stage distance for the peak profit
5. If `current_price <= trailing_stop`: close with `reason: "trailing_stop"`

### Activation (bearish — mirrored)
1. Track `lowest_price = min(current_price, lowest_price)`
2. When profit (price dropping) >= 2%, arm trail above the lowest price
3. Tighten on new lows, close if price >= trailing_stop

### Example
- Entry: $100. Price hits $103 (+3%). Stage 1 activates.
  - Trail at $103 × (1 − 0.01) = $101.97
- Price reaches $108 (+8%). Stage 2: trail distance = 2.0%.
  - Trail tightens: $108 × (1 − 0.02) = $105.84
- Price peaks at $115 (+15%), then reverses.
  - Stage 3: trail distance = 3.0%. Trail = $115 × 0.97 = $111.55
  - Price drops to $110 < $111.55 → **close at $111.55, profit locked: +11.6%**

Without trailing: $100 → $115 → $100 (back to entry, no profit).
With trailing: $100 → $115 → trailed at $111.55 → **+11.6% locked**.

### Pre-computed lock-in amounts (bullish, default stages)

| Peak spike | Stage | Trail distance | Profit locked |
|---|---|---|---|
| +4% | 1 (2%/1%) | 1.0% | +2.97% |
| +8% | 2 (6%/2%) | 2.0% | +5.84% |
| +15% | 3 (12%/3%) | 3.0% | +11.55% |
| +20% | 3 (12%/3%) | 3.0% | +16.40% |

### Backward compatibility

The old `params.json dynamic_risk` fields `trailing_activation_pct` and `trailing_distance_pct` are no longer used. All trailing logic uses the configurable multi-stage system.

## Position Schema

Every open position stores these trailing-related fields (set in `open_position()` in `paper_trader.py`):
- `bias`: "bullish" | "bearish"
- `highest_price`: peak price since entry (bullish)
- `lowest_price`: trough price since entry (bearish)
- `trailing_stop`: current trailing stop level (or None before activation)
- `trailing_activated`: boolean — has trail been armed?

These MUST also be present when opening positions via `paper_executor.open_trades()` (it writes directly to `portfolio.json` with its own dict).
These MUST be included in `_normalize_position()` in `paper_trader.py` — any new field added to the position schema that does NOT appear in `_normalize_position()` will be silently stripped on every portfolio load, breaking persistence.

## Backtest Trailing Stop

`signal_validator.backtest()` mirrors the live logic:
- Uses candle `close` to check activation threshold (conservative: close must be above activation level)
- Uses candle `low` to check if the trailing stop was breached
- Reads the same multi-stage params from `params.json` (not hardcoded) via `_trail_params_path`
- Returns `exit_reason: "trailing_stop"` when trail is breached

The `summarize()` function includes `trailing_stop_rate` alongside `target_hit_rate` and `stop_hit_rate`.

## Journal Sync

When `paper_trader.update_mark_to_market()` closes a position via trailing stop, `_sync_closed_to_journal()` runs immediately after to match the closed position against open signals in the strategy journal and close them with outcome `trailing_stop`. This prevents the journal from holding "open" signal entries for positions that were trail-closed earlier. The sync is called from `main()` after every `update_mark_to_market()` call.

## M2M Frequency Is Critical

Trailing stops only activate during `paper_trader.update_mark_to_market()` calls. The no_agent cron `paper-trading-m2m` runs every **10 minutes** — minimum viable frequency for trailing stops to be reliable. A 30-minute gap meant a spike-reversal at crypto speed could slip between checks.

Each M2M tick costs 1 CG `/simple/price` call for all open positions (~3-5 seconds). At ~144 calls/day this is well within CG free tier limits.

The shell script (`~/.hermes/scripts/paper-m2m-update.sh`) only delivers output when a position was closed (`Journal: synced N`). Ticks with no changes produce no output → cron delivers nothing → Telegram stays quiet.
