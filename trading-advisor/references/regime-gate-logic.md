# Regime Gate Logic (Fear & Greed Index)

This reference documents the hard regime gate in `briefing.py::simple_rules()` that blocks ALL signals when F&G is in extreme territory.

## Hard Gate (lines 626-639 in briefing.py)

```python
# Market regime gating: adjust scoring by fear & greed
_fng_val = int(_fng_r.get('value', 50))
if _fng_val <= 15:
    return []  # Extreme Fear: skip all signals (dead cat bounce risk)
elif _fng_val >= 85:
    return []  # Extreme Greed: skip all signals (pump risk)
elif _fng_val <= 35:
    _regime_mult = 0.75  # Fear: penalize scores
elif _fng_val >= 65:
    _regime_mult = 1.15  # Greed: boost scores
```

## Behavior Summary

| F&G Range | Regime | Action | Score Mult |
|-----------|--------|--------|------------|
| 0–15 | Extreme Fear | **HARD BLOCK** (return `[]`) | — |
| 16–35 | Fear | Score ×0.75 | 0.75 |
| 36–64 | Neutral | Baseline | 1.0 |
| 65–84 | Greed | Score ×1.15 | 1.15 |
| 85–100 | Extreme Greed | **HARD BLOCK** (return `[]`) | — |

## Practical Impact (from 2026-06-30 session)

- **Current F&G = 12** → Hard block, zero signals emitted
- Funnel before gate: 424 coins → 171 ≥$50M mcap → 65 ≥3% move
- If F&G were 16–35 (Fear): those 65 would be scored with ×0.75 penalty
- If F&G were 36–64 (Neutral): baseline scoring, more signals pass 25 threshold
- If F&G were 65–84 (Greed): ×1.15 boost, more momentum plays qualify

## Score Thresholds (from params.json / calibrations)

| Tier | Market Cap | Min 24h Move | Notes |
|------|------------|--------------|-------|
| Mega-cap | >$50B | ≥0.5% | BTC, ETH, SOL, BNB |
| Large-cap | >$10B | ≥1.0% | ADA, AVAX, DOT, LINK |
| Mid-cap | >$1B | ≥2.0% | |
| Small-cap | >$100M | ≥3.0% | Adaptive via `params.json` |
| Micro-cap | $50M–$100M | ≥4.0% | High bar = manipulation filter |

**Pass threshold: score ≥ 25** (from `screening.score_threshold` in params.json)

## Key Scoring Components

1. **Core**: `abs(24h_change) + max(0, mcap_change_24h) * 0.08`
2. **Regime mult**: ×0.75 / 1.0 / 1.15
3. **Strategy routing**:
   - Mean-reversion (>4% move): vol premium up to 1.5×
   - Momentum (trending + TokoCrypto vol >$1M): 1.2× boost + mcap bonus
4. **Liquidity**: TokoCrypto spread <5bps +5pts; >20bps −10pts; volume bonuses
4. **Win momentum**: +3pts for recent winners (30-day lookback)
5. **Loss penalty**: −min(2×|loss|, 30) × recency decay (caps 40pts, 14-day half-life)
6. **Trap filters** (subtract points):
   - Falling knife (<−12%): −15
   - Slipping (<−8%): −8
   - Thin pump (>18% on low vol): −15
   - Low-vol pump (>12%): −10
   - Manipulation risk (>15% on <$1M vol): −12
   - Mcap divergence (>10% move, <2% mcap change): −8
   - Overextended (>25%): −10
   - Fake volume (vol/mcap <0.5%): −18
   - Wash trading (vol/mcap >200%): −8

## Workaround for Testing/Simulation

To see what signals WOULD appear if not for the regime gate, temporarily comment out or modify lines 626-631 in `briefing.py`:

```python
# Temporarily disable hard gate for simulation:
# if _fng_val <= 15: return []
# elif _fng_val >= 85: return []
```

Then re-run `python3 scripts/briefing.py --compact` to see candidates.