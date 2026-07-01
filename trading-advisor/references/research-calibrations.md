# Research Calibrations (`strategy/research-calibrations.json`)

A JSON file at `strategy/research-calibrations.json` stores calibration constants extracted from the paper corpus. The orchestrator reads it at briefing time via `_load_calibrations()`. This decouples research thresholds from code — edit the JSON to tune without touching `.py` files.

## Volatility-Regime Bias Detection

`_regime_bias(change_24h)` returns the strategy mode (`"momentum"` or `"mean-reversion"`) based on 24h volatility vs calibrated thresholds:

| Volatility (abs change_24h) | Mode | Trade Thesis |
|---|---|---|
| < 1.5% | momentum | Trending — momentum + cap flow aligned |
| 1.5% – 3.0% | momentum | Trending — momentum + cap flow aligned |
| > 3.0% | mean-reversion | High-vol — targeting snap-back with tight stop |

The bias line in the briefing becomes `"mean-reversion - bullish"` when volatility is high, or `"bullish"` (default) for low/mid vol. The Why: line switches between `"trending — momentum + cap flow aligned"` and `"high-vol regime — targeting snap-back with tight stop"`.

**Enhanced with DuckDB regime performance**: When volatility is in neutral range (1.5-3.0%), `_regime_bias()` now queries `journal.db` via DuckDB through `free_data.get_regime_performance()` to find the historically best-performing regime and uses it as a tiebreaker. This makes regime selection data-driven rather than purely threshold-based.

## Liquidity-Adjusted Position Sizing

`_liquidity_multiplier(c)` returns 0.5–1.0 multiplier based on TokoCrypto depth/spread data:

| Condition | Multiplier | Rationale |
|---|---|---|
| Ideal spread (<3bps), deep book (>$50K) | 1.0 | Full size — ideal liquidity |
| Edge spread (7bps), adequate depth | ~0.71 | 29% cut — spread 4bps above ideal |
| Thin depth ($25K), good spread | ~0.86 | 14% cut — below confidence threshold |
| Bad both (15bps, $10K) | 0.50 | Max cut — research-calibrated max penalty |
| No depth data available | 1.0 | Can't penalise without data |

Formula: `spread_penalty = min(max_penalty, excess / spread_range * max_penalty)` where excess = spread - ideal_bps. `depth_penalty = 0.20 * (1.0 - depth / min_depth)` when depth < $50K. Total penalty capped at 0.50.

The renderer shows `- Sizing: 85% multiplier (spread-adjusted)` when multiplier < 1.0.