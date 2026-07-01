# Market Regime & Parameter Optimizer Findings — 2026-06-30

Key findings from the orchestrator nightly runs (2026-06-27 through 2026-06-29) and parameter optimizer analysis.

## Persistent Extreme Fear Regime

**F&G Index**: 12-18 (Extreme Fear) for 3+ consecutive days
- **2026-06-27**: F&G=18, BTC dominance 66.05%
- **2026-06-28**: F&G=18, BTC dominance 55.71%
- **2026-06-29**: F&G=12, BTC dominance 55.61% (orchestrator) / 66.0% (briefing)

**Implications**:
- Macro risk elevated — even quality signals carry elevated risk
- Strategy correctly gating: "Extreme Fear = size down, tighten stops"
- Zero high-confidence setups on 2026-06-27, 2026-06-29 (only 2026-06-28 had 2 setups)

## Parameter Optimizer Recommendations (from 23 closed trades)

Based on analysis of 500 coins (2026-06-28):

| Parameter | Current | Optimal | Rationale |
|-----------|---------|---------|-----------|
| `min_24h_change_pct` | 3% | **5%** | Catches 49 of 59 big movers (83%) vs current threshold |
| `score_threshold` | 25 | **10** | FP rate 0% at 10; current 25 may be over-filtering |
| `correlation_threshold` | 0.70 | 0.70 (keep) | L1 sector: 7 coins, 83% directional alignment — appropriate |

**Critical Finding**: Profit factor 0.81 < 1.0 (negative expectancy)
- Win rate: 43.5% (below 50%)
- Stop hit rate: 54% (high)
- Avg PnL: -0.75%

**Recommended Action**: 
1. Raise `min_24h_change_pct` from 3% → 5% in strategy params
2. Lower `score_threshold` from 25 → 10
3. Review `research-calibrations.json` trap-filter scores
4. Consider increasing `correlation_threshold` if stop hit rate persists >50%

## BTC Dominance Data Discrepancy

**Orchestrator** (uses free_data.py): 55.61% on 2026-06-29
**Briefing** (uses different source): 66.0% on 2026-06-29

**Root Cause**: Different data sources/API endpoints for BTC dominance calculation.
-ness calculation.
- free_data.py uses CoinGecko global data
- briefing.py may use different endpoint or cached value

**Action**: Standardize on single BTC dominance source in both scripts.

## Strategy Performance by Regime

| Regime | Days | Setups | Win Rate | Notes |
|--------|------|--------|----------|-------|
| Extreme Fear | 3 | 2 (both 2026-06-28) | TBD | High stop hit rate expected |
| Neutral/Greedy | — | — | — | No data in current window |

## Files Updated
- `strategy/params.json` — should be updated with optimizer recommendations
- `strategy/research-calibrations.json` — trap-filter scores review needed
- `scripts/free_data.py` — verify BTC dominance source consistency