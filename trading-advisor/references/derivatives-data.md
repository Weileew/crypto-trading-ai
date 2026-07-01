# Derivatives Data Reference

## Data Sources

All data comes from **Binance Futures** (`fapi.binance.com`) — free public API, no auth required. No documented rate limit.

### Endpoints

| Endpoint | Returns | Example Response |
|---|---|---|
| `GET /fapi/v1/fundingRate?symbol=BTCUSDT&limit=1` | Current funding rate (per 8h) | `[{"fundingRate":"0.00004284","fundingTime":...,"markPrice":"60817.30"}]` |
| `GET /fapi/v1/openInterest?symbol=BTCUSDT` | Current open interest in contracts | `{"openInterest":"102847.354","time":...}` |
| `GET /futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=1h&limit=1` | Top trader L/S ratio | `[{"longShortRatio":"1.2256","longAccount":"0.5507","shortAccount":"0.4493"}]` |

### Usage in Code

```python
from free_data import fetch_derivatives_summary

summary = fetch_derivatives_summary("BTCUSDT")
# Returns dict with:
#   funding_rate: 4.258e-05
#   funding_signal: "neutral"
#   funding_icon: "🟡"
#   annualized_pct: 4.7
#   oi_btc: 102852.1
#   oi_usd: 6171166961.0
#   ls_ratio: 1.226
#   ls_signal: "leaning long"
```

### Standalone Functions

```python
from free_data import (
    fetch_funding_rate,        # rate per 8h as decimal string
    fetch_open_interest,        # OI in contracts
    fetch_long_short_ratio,     # list with ratio + long/short accounts %
    interpret_funding_rate,     # (signal, icon, annualized_pct)
)
```

## Calibration Thresholds

Stored in `strategy/research-calibrations.json` under `derivatives`:

```json
{
  "derivatives": {
    "funding_extreme_positive": 0.001,
    "funding_positive": 0.0001,
    "funding_negative": -0.0001,
    "funding_extreme_negative": -0.001,
    "ls_crowded_long": 1.5,
    "ls_crowded_short": 0.67
  }
}
```

| Threshold | Boundary | Signal | Interpretation |
|---|---|---|---|
| `funding_extreme_positive` | > 0.001 (>0.1%) | ⚠️ extreme positive | Crowded longs → squeeze risk |
| `funding_positive` | > 0.0001 (>0.01%) | 🟢 positive | Bullish sentiment |
| `funding_negative` | < -0.0001 (< -0.01%) | 🔴 negative | Bearish sentiment |
| `funding_extreme_negative` | < -0.001 (< -0.1%) | ⚠️ extreme negative | Crowded shorts → short-squeeze |
| Between ±0.0001 | — | 🟡 neutral | Normal funding |

Long/short ratio:
| Ratio | Signal | Interpretation |
|---|---|---|
| > 1.5 | crowded long | Top traders heavily long |
| 1.2 — 1.5 | leaning long | Mild bullish positioning |
| 0.8 — 1.2 | balanced | Neutral |
| 0.67 — 0.8 | leaning short | Mild bearish positioning |
| < 0.67 | crowded short | Top traders heavily short |

## Briefing Integration

In `render_compact_briefing()`, after the Market Regime section is built:

```python
try:
    from free_data import fetch_derivatives_summary
    _d = fetch_derivatives_summary("BTCUSDT")
    if _d.get("funding_rate") is not None:
        txt.append(f"- BTC funding: {_d['funding_icon']} {_d['funding_signal']} ({_d['annualized_pct']:.0f}% annualized)")
    if _d.get("oi_btc"):
        txt.append(f"- BTC OI: ${_d['oi_usd']:,.0f}")
    if _d.get("ls_ratio"):
        txt.append(f"- Long/short: {_d['ls_ratio']:.2f}x ({_d['ls_signal']})")
except Exception:
    pass  # non-fatal
```

Output in briefing:
```
- BTC funding: 🟡 neutral (5% annualized)
- BTC OI: $6,172,998,533
- Long/short: 1.23x (leaning long)
```

## Pitfalls

1. **Only BTC perpetual fetched by default**. The `fetch_derivatives_summary()` accepts any symbol parameter — ETHUSDT, SOLUSDT, etc. — but the briefing only fetches BTCUSDT. Extend by adding more symbols in `render_compact_briefing()`.

2. **Binance funding is per 8h**, not per 1h like some other exchanges. Annualized formula: `rate × 3 × 365 × 100 = annualized %`. This matches Binance's settlement schedule.

3. **L/S ratio is top 20% traders only**. The `topLongShortPositionRatio` endpoint reflects the largest traders by account value, not the entire exchange. Retail positioning may be very different.

4. **Funding rate ≠ spot price direction**. Funding rates predict squeeze/sell-off events, not immediate direction. A positive funding rate can persist for weeks during a strong uptrend. Use as a regime modifier ("excessive bullish leverage exists") not an entry trigger.

5. **Open interest without volume context is noisy**. OI rising + price rising = trend confirmation. OI rising + price flat/falling = distribution. OI falling = liquidation or position unwind. The briefing only shows raw OI; no trend interpretation is applied.

6. **Transient fetch failures are silent**. If Binance is unreachable (rare), the three derivatives lines simply don't appear. No error is raised. This is intentional — the briefing must not fail because of a non-essential data source.
