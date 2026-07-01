# External Critic Assessment (2026-07-01)

## Summary
A detailed external review of the TOK briefing system. The critic is **largely correct about what the briefing *shows*** but **underestimates what the system *does***. The architecture has sophisticated risk controls, regime detection, and validation — they just don't surface in the daily output.

## Claim-by-Claim Verdict

| Claim | Verdict | Evidence |
|-------|---------|----------|
| **1. F&G as "primary filter / crutch"** | Partially True | `simple_rules()` (briefing.py L598-L636) hard-gates at F&G ≤15/≥85 *before* any scoring. But `_regime_bias()` (L1060-L1096) uses research-calibrated volatility thresholds (1.5%/3%) for strategy routing. Derivatives data (funding/L-S/OI) feeds `_funding_score_adjustment()` (L534-L579). The crutch is the hard gate; the real regime logic exists but runs later. |
| **2. "No Opportunity" = binary lazy output** | True | `render_compact_briefing()` L1525-L1532: `"🤷 No high-confidence setup today. all screened below thresholds"`. `_funnel_summary()` shows `195 → 424 → 12` but **no threshold distance for top near-miss**. The requested metric (`XRP missed by 4.2% on RVol`) is **not implemented**. |
| **3. News section = "digital newspaper fluff"** | True | `_news_compact_block()` (L977-L1013) fetches 4 headlines, classifies sentiment, prints them. **Zero NLP scoring feeds into weights, scores, or execution logic.** `sentiment` calibrations exist in `research-calibrations.json` (L23-L28) but aren't wired to news. |
| **4. Pipeline status = misleading ✅ on 33% WR** | True | `signal_performance.json`: 5 signals, 40% WR, PF=0.58 (avg R=0.235). `_orchestrator_block()` shows WR/PF but the **compact briefing (default) hides this**. No VaR, expectancy, Sharpe, Sortino, or avg win/loss in main output. The ✅ icon on "Signal validation" is misleading without context. |

## What the System Actually Has (That the Critic Missed)

| Capability | Location | Status |
|------------|----------|--------|
| Scaled volatility gates by mcap tier (0.5%→4%) | `simple_rules()` L670-L681 | ✅ Active |
| Decaying loss penalties (14-day, cap 40) | `get_loss_penalties()` + `simple_rules()` L682-L738 | ✅ Active |
| Win momentum boost (+3 for 30d winners) | `simple_rules()` L730-L732 | ✅ Active |
| Portfolio engine: drawdown gate, correlation penalty, concurrency cap | `portfolio_engine.py` L240-L335 | ✅ Active |
| Regime-aware max stops (5% extreme fear → 8% neutral) | `_regime_max_stop()` L581-L595 | ✅ Active |
| Volatility-based regime bias (mean-rev vs momentum) | `_regime_bias()` L1060-L1096 | ✅ Active (research-calibrated) |
| Derivatives: funding rate, OI, L/S ratio | `fetch_derivatives_summary()` L680-L740 | ✅ Active, feeds scoring |
| VectorBT + Empyrical backtesting | `signal_validator.py` L542-L665 | ✅ Available |
| Strategy journal with auto-adaptation | `strategy_journal.py` L561-L635 | ✅ Active (win-rate → param adjustment) |
| Paper trading with multi-stage trailing stops | `paper_trader.py` L394-L464 | ✅ Active |

## The Real Gap: Output ≠ Intelligence

The system **computes** regime, distance, risk, expectancy — but the **briefing renders** "No picks today" + 4 headlines + ✅ icons.

The critic's three demanded questions **can be answered from existing data** but aren't surfaced:

| Question | Data Exists? | Where |
|----------|--------------|-------|
| **Regime: mean-rev or momentum?** | ✅ | `_regime_bias(change_24h)` → uses 1.5%/3% vol thresholds from `research-calibrations.json` |
| **Distance: how close was top candidate?** | ❌ | `_funnel_summary()` counts stages but doesn't compute `min(score - threshold)` for near-misses |
| **Risk: VaR if deploying 10%?** | ⚠️ Partial | Portfolio engine has drawdown/exposure/correlation, but no VaR output. Empyrical can compute VaR/CVaR (signal_validator.py L628-L629) but not in briefing. |

## Priority Fixes (Highest ROI First)

1. **Add Threshold Distance Metric** (Critic #2) — 30 min
   - In `_funnel_summary()`: track top 3 candidates by raw score, show `score - threshold` and which gate they failed
   - Output: `📈 195 scanned → 424 ≥$50M → 12 ≥3% → 2 scored≥25 | Near-miss: XRP 23.8 (-1.2 vs threshold)`

2. **VaR / Expectancy in Briefing** (Critic #4) — 45 min
   - Use `empyrical.value_at_risk()` on validated signal returns (already in `summarize_with_empyrical()`)
   - Add to compact briefing: `VaR(95%): -X% | Expectancy: +Y% | Avg Win: +Z% | Avg Loss: -W%`

3. **Regime Banner** (Critic #1/4) — 20 min
   - Show `_regime_bias()` result prominently: `📊 Regime: mean-reversion (BTC 24h vol 4.2% > 3% threshold)` or `momentum (vol 1.1% < 1.5%)`

3. **Kill or Wire News Sentiment** (Critic #3) — 15 min
   - Either: remove news block entirely, OR pipe headlines → VADER/FinBERT → sentiment score → feed into `_regime_bias` or scoring