# Trading Trap Filters

Applied by `simple_rules()` in `briefing.py` after core scoring and liquidity assessment. All are **penalty-only** — they never increase a score, only reduce it. This prevents borderline candidates from slipping through on volatility alone.

## Filter Inventory

| # | Filter | Trigger | Penalty | Rationale |
|---|--------|---------|---------|-----------|
| 1 | **falling_knife** | p < -12% | -15 | Steep single-day drop with momentum against you. Buying this dip is catching a falling knife — the move often continues. |
| 2 | **slipping** | p < -8% | -8 | Moderate drop without clear support. Higher probability of continuation than reversal. |
| 3 | **thin_pump** | p > +18% AND (toko_vol < $100K OR CG_vol < $2M) | -15 | Pump without exchange volume to back it. Likely low-liquidity manipulation or a small wallet pumping into thin orderbook. |
| 4 | **low_vol_pump** | p > +12% AND toko_vol < $50K | -10 | Smaller pump on very thin TokoCrypto volume. Execution risk is high — you'd move the market entering or exiting. |
| 5 | **manipulation_risk** | \|p\| > 15% AND CG_vol < $1M | -12 | Any extreme move on tiny global volume. Price is not anchored by real demand. |
| 6 | **mcap_divergence** | \|p\| > 10% AND \|mc\| < 2% | -8 | Price is moving but market cap isn't following. Suggests low-float manipulation or stale pricing rather than genuine capital flow. |
| 7 | **overextended** | \|p\| > 25% | -10 | Extreme move in either direction. Even if genuine, the probability of a snap-back or exhaustion move is elevated. |
| 8 | **fake_volume** | \|p\| > 8% AND vol/mcap ratio < 0.005 | -18 | Classic manipulation: price moved >8% but daily trading volume is <0.5% of market cap. No real capital backing the move. |
| 8b | **fake_volume (weak)** | \|p\| > 5% AND vol/mcap ratio < 0.002 | -18 | Smaller price move on even thinner volume. Same manipulation signal at lower amplitude. |
| 9 | **abnormal_volume** | vol/mcap ratio > 2.0 | -8 | Daily volume exceeds 200% of market cap — possible wash trading, panic selling, or bot activity. Healthy ratio is 1-20%; >200% is suspicious. |

## Interaction with Core Scoring

The trap penalties stack with the existing liquidity scoring:

```
final_score = price_momentum_score     (abs(p) + mcap_flow * 0.08)
            + volume_bonus             (min(toko_vol/10M, 10))
            + spread_bonus_penalty     (+5 for <5bps, -5 for 10-20bps, -10 for >20bps)
            + volume_liquidity_bonus   (+3 for >$1M, +1 for >$100K)
            + no_ticker_penalty        (-5 if no bid/ask data)
            + ALL_TRAP_PENALTIES       (each trap that fires subtracts its value)
```

A single filter can cut ~15 points, which typically drops the candidate below the score_threshold (25). This is intentional — the trap filters are the last gate before a candidate makes it into the briefing.

## When to Tune

- If too many legitimate setups are being filtered, relax the trigger thresholds (e.g., falling_knife from -12% to -15%) or reduce penalty magnitudes.
- If suspicious candidates still appear, tighten triggers or increase penalties. The thresholds were tuned for a balanced swing/day profile during the June 2026 session.
- The `params.json` adaptation layer does NOT auto-adjust trap thresholds — they are hardcoded in `simple_rules()`. Manual adjustment only.
