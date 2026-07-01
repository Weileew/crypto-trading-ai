# Signal Quality Architecture

## Design Philosophy (user preferences)

These are hard rules derived from user corrections during signal quality work:

1. **Quality over quantity.** Never push signal quantity. Improve scoring to naturally select better candidates. More signals without better selection is noise, not data.

2. **Score penalties, not hard blocks.** Do not hard-block any coin/symbol. Use decaying score penalties (`get_loss_penalties()`, 14-day decay) so coins with genuine momentum can still overcome past losses. Conditions change — blocked coins today may be opportunities tomorrow.

3. **Paper trading = maximize validation data.** Never reduce briefing frequency or signal volume in paper trading mode. More signals = more validation data = faster strategy optimization. Only pause signal generation on real-money drawdown or extreme market regimes (F&G ≤15 Extreme Fear, F&G ≥85 Extreme Greed).

4. **Fail-close on uncertainty.** If a regime-check network call (fear-greed API) fails, default to blocking signals rather than allowing them. Conservative by default when the guardrail is unavailable.

5. **Simulation accuracy is paramount.** Wrong positions or false order identifications are catastrophic — they corrupt the P&L record and invalidate backtest data. Every open must pair with exactly one close via persistent `trade_id`. Every position must enter at current market price (not yesterday's recommended price), with stops/targets proportionally adjusted. The ledger must be a trustworthy audit trail — not a collection of ghost entries.

## Core Principle
**Paper trading = maximize signal data for strategy tuning.** Never reduce signal volume in paper mode. Only pause signal generation on real-money drawdown or extreme market regimes.

## Signal Pipeline (in order)

### Layer 1 — Hard Gates (pre-score, filter out)
| Gate | Condition | Notes |
|---|---|---|
| Stablecoin | sym/name contains USDT, USDC, DAI, etc. | ~12 filtered |
| Min mcap | `market_cap < $50M` | Micro-caps filtered |
| Scaled volatility | min % by mcap tier (see below) | Replaces flat 3% gate |

**Scaled volatility gate** (in `simple_rules()`, `briefing.py`):
- `mcap ≥ $50B` → `min_change = 0.5%` (BTC, ETH, SOL)
- `mcap ≥ $10B` → `min_change = 1.0%` (ADA, AVAX, DOT)
- `mcap ≥ $1B` → `min_change = 2.0%` (AAVE, ARB, APT)
- `mcap ≥ $100M` → `min_change = _adapt_change` (reads from params.json, adapts)
- `mcap < $100M` → `min_change = 4.0%` (micro-caps need strong evidence)

### Layer 2 — Scoring (rank candidates)
Base score = `|24h_change| + max(0, mcap_change) × 0.08`

| Modifier | Amount | Trigger |
|---|---|---|
| Regime multiplier | ×0.75 / ×1.0 / ×1.15 | F&G ≤35 / 36-64 / ≥65 |
| Volume bonus | up to +10 | TokoCrypto volume score |
| Spread bonus/penalty | +5 to -10 | Bid-ask spread bps |
| Unknown liquidity | -5 | No TokoCrypto data |
| **Win momentum** | **+3** | Coin won (hit_target/trailing_stop/expired+pnl>0) in last 30d |
| **Loss penalty** | **-score** | Decaying penalty for hit_stop losses (see below) |

### Layer 3 — Trap Filters (penalize bad setups)
| Trap | Penalty | Condition |
|---|---|---|
| Falling knife | -8 to -15 | `p < -8%` to `-12%+` |
| Thin pump | -15 | `p > 18%` + low volume |
| Low-volume pump | -15 | `p > 12%` + TokoCrypto vol < 50k |

## Loss Penalty (replaces hard block)

Each `hit_stop` outcome contributes:
```
per_loss_penalty = min(|pnl%| × 2, 30) × recency_factor
recency_factor decays from 1.0 → 0.0 over 14 days
total_penalty = min(sum of per_loss, 40)
```

The penalty is subtracted from the score AFTER all bonuses. A coin with strong momentum + volume can still overcome its history. After 14 days, penalty = 0 regardless of past.

### Example current penalties
| Coin | Picks | Avg Loss | Penalty | Needs Score |
|---|---|---|---|---|
| MANTA | 5× | -8.0% | 40.0 | ≥ 65 (hard but possible) |
| S | 5× | -8.0% | 40.0 | ≥ 65 |
| MAGMA | 2× | -3.5% | 13.9 | ≥ 39 |
| SKYAI | 1× | -5.3% | 9.4 | ≥ 34 |

After 7 days, penalties halve. After 14 days, all reset to 0.

## Win Momentum
Coins that won (hit_target, trailing_stop, or expired+pnl>0) in last 30 days get **+3 score bonus**. This creates a virtuous feedback loop for proven performers without hard-blocking newcomers.

## Regime Gating
- **F&G ≤ 15** (Extreme Fear): **Bottom-Fishing mode** — instead of blocking all signals, `simple_rules()` routes to `_bottom_fishing_pipeline()` with mean-reversion scoring.
  - **ATR Volatility Gate**: Before any scoring, `_btc_atr_status()` fetches BTCUSDT 1h klines and computes ATR(14) ratio. If ATR > 1.25× (expanding), bottom-fishing is **paused** — falling-knife risk. Empty-state shows: `🛑 Bottom-fishing paused: ATR expanding (1.33x) — falling knife risk. Waiting for volatility to contract.`
  - If ATR is stable/contracting (≤1.25×), scoring proceeds with wider stops (5% vs normal 3.5%)
  - **Spot-only constraint**: TOK is spot-only — no shorting. Pipeline filters to `p < 0` only (negative 24h change = dip buying). Positive-move coins are rejected. Direction is always `"bullish"`.
  - Scoring: down-moves get ×1.2 bonus (snap-back potential), up-moves discounted ×0.9. Range 3-20% move only (noise + insane-vol filter). Market cap flow bonus when `p < 0` and `mc > 2%`.
  - Empty-state if no picks pass threshold despite ATR being OK: `🤷 No mean-reversion setup passed the score threshold. Save powder.`
  - Action items when bottom-fishing active: `🎣 Bottom-fishing active — size at 50% normal, expect fake-outs` + `If ATR expands, exit partial position immediately`
- **F&G ≥ 85** (Extreme Greed): `simple_rules()` returns `[]` — pump risk. Full halt.
- **F&G 16-35** (Fear): scores penalized ×0.75
- **F&G 36-64** (Neutral): normal ×1.0
- **F&G ≥ 65** (Greed): scores boosted ×1.15
- **Fail-close**: If `fetch_fear_greed()` raises any exception (rate limit, timeout, network), `simple_rules()` returns `[]` — blocks signals rather than allowing them uncensored.

## Outcome Classification (performance metrics)
| Outcome | Classification | Notes |
|---|---|---|
| `hit_target` | Win | ✅ |
| `trailing_stop` | Win | Locked in profit ✅ (was invisible before fix) |
| `expired` + pnl > 0 | Win | Expired in profit ✅ (was counted as loss before fix) |
| `expired` + pnl ≤ 0 | Loss | Expired at/no profit |
| `hit_stop` | Loss | Hit stop loss |

## Validator Dedup
`signal_validator.py` calls `signal_exists()` before creating standalone outcomes. If a signal for (symbol, entry_price) within 5% tolerance already exists, the validator skips it instead of creating a duplicate signal+close pair.

## Duration Estimation Fix
`close_signal()` in `strategy_journal.py` accepts an optional `estimated_duration_h` parameter. When the signal validator backtests historical data, it passes `bars_count × 24` as the estimated duration instead of relying on wall-clock time (which was ~0 because the signal was created and immediately closed). Fixes `avg_duration_hours` showing 0.0 for all validator-created outcomes.

```python
# strategy_journal.py
def close_signal(signal_id, outcome, exit_price=None, regime="", reason="",
                 estimated_duration_h=None):
    ...
    if estimated_duration_h is not None:
        duration_h = round(estimated_duration_h, 1)
    else:
        # Normal wall-clock computation
        duration_h = round((now - opened).total_seconds() / 3600, 1)
```

## Regime-Aware Maximum Stop Loss

The hardcoded `min(8.0, ...)` cap on `adj_stop_pct` in `briefing.py` is now regime-dependent via `_regime_max_stop(fng_value)`:

| Regime | F&G Range | Max Stop | Rationale |
|---|---|---|---|
| Extreme Fear | ≤15 | **5%** | Capital preservation, volatile markets amplify losses |
| Fear | 16-35 | **6%** | Moderate tightening |
| Neutral | 36-64 | **8%** | Normal range |
| Greed | 65-84 | **8%** | Normal range |
| Extreme Greed | ≥85 | **6%** | Pump risk — tight stops prevent rug-pull losses |

Both `render_briefing()` and `render_compact_briefing()` apply the same helper function using the already-fetched F&G value. Positions opened during Extreme Fear have tighter stops (5% instead of 8%), containing individual losses without blocking the coin entirely.

```python
# briefling.py
def _regime_max_stop(fng_value: int = 50) -> float:
    if fng_value <= 15: return 5.0
    elif fng_value <= 35: return 6.0
    elif fng_value >= 85: return 6.0
    elif fng_value >= 65: return 8.0
    return 8.0
```

## Performance State & Schedule Map

### State classifier (in `strategy/cron_manager.py`)
Reads from strategy journal DB + portfolio + `signal_performance.json`:

| State | Win Rate | Streak | Drawdown |
|---|---|---|---|
| 🔴 CRITICAL | — | — | `≤ -10%` |
| 🔶 COLD | `<25%` or `<40%` + PF<1.0 | `≤ -5` | `≤ -5%` |
| ✅ NORMAL | 25-55% | > -5 | `> -5%` |
| 🟢 HOT | `≥55%` + PF≥1.5 | — | — |

### State-based schedule adjustments
| State | M2M | Briefings | Orchestrator | Auto-push |
|---|---|---|---|---|
| 🔴 CRITICAL | every 15m | Pause | Pause | every 60m |
| 🔶 COLD | every 15m | 2/day (keep data flowing) | 04:00 | every 60m |
| ✅ NORMAL | every 30m | 2/day | 04:00 | every 60m |
| 🟢 HOT | every 30m | 2/day | 04:00 | every 60m |

**CRITICAL RULE**: Never reduce briefing frequency in paper trading mode even during COLD streaks. More signals = more validation data = faster strategy optimization. Only pause on real-money drawdown.

## Cron Manager Usage

```bash
# Full report
python3 strategy/cron_manager.py

# Performance-aware suggestions
python3 strategy/cron_manager.py --performance

# Schedule collision scan
python3 strategy/cron_manager.py --check-collisions

# CG budget report
python3 strategy/cron_manager.py --budget

# 24h timeline
python3 strategy/cron_manager.py --schedule

# Auto-optimize (generates cronjob update commands)
python3 strategy/cron_manager.py --auto-optimize
```

## CG Rate Limits
- Free tier: ~14,400 calls/day, ~10 req/min, min 6s spacing
- All calls through `free_data._get_cg()` with 6s spacing + exponential backoff (3s × attempt)
- Daily counter at `reports/cg_call_count.json`
- Current usage: ~116 calls/day (0.8% of free tier)

## Related
- `references/critique-response-protocol.md` — Due-diligence workflow for responding to external audits

---

## Decision-Support Briefing Enhancements (v3.2 — 2026-07-01)

The critic audit (2026-07-01) identified that the briefing functioned as a status report but failed as a decision-support tool. Four anti-patterns were fixed:

### Pitfall: Force-fitting Missing Data (anti-pattern: 0.0% vol → "momentum")
**Don't** force missing/zero API data into a meaningful regime label. If BTC's 24h change is `None` or `0.0` (CG API returned no data), `_regime_bias()` returns `"indeterminate"` instead of `"momentum"`. The renderer shows `"Regime: Indeterminate (24h vol data unavailable for BTC)"`. Preserves credibility — a user who sees `"Regime bias: momentum (24h vol 0.0% vs thresholds: >3% mean-rev / <2% momentum)"` will (correctly) distrust the entire report.

Guard in `briefing.py` `_regime_bias()`:
```python
if change_24h is None or change_24h == 0.0:
    return "indeterminate"
```

### Pitfall: No Progressive Disclosure (anti-pattern: 50 lines → "nothing to do")
When the regime gate (F&G ≤ 15 or ≥ 85) has already killed all signals in `simple_rules()`, the briefing is for a **screen reader verifying confidence**, not a **decision-maker**. Skip verbose sections:
- **Keep**: summary bar, risk, one-line regime, halt notice, re-entry conditions, embedded Quick P&L
- **Skip**: BTC funding rate, OI, L/S ratio, mempool fees, performance metrics, paper recap, open positions, enhanced regime, orchestrator digest

Controlled by `_halted` flag in `render_compact_briefing()`. The halt message is:
```
🚫 **HALTED**: All signals blocked by extreme market regime. Capital preservation mode.
```

### Pitfall: Ghost Commands in Flat Reports (anti-pattern: shell commands in text output)
Never embed shell commands (`python3 scripts/paper_trader.py --summary`) in output delivered to Telegram or saved as a `.md` file — the user cannot execute them. **Fix**: read `portfolio.json` directly and embed actual data:
```python
# Compact real-time summary instead of a ghost command
- Paper: Equity $10,234.50 · Return 🟢 +2.35% · 1 open position(s)
```

### Pitfall: Literal `\n` in String Content (anti-pattern: `"━━━\\n## ..."` in output strings)
If you write `"━━━\\n## Performance"` as a single string in a list that will be joined with `"\n".join(txt)`, the `\\n` renders as literal text `\n` in the output, not as a line break. **Fix**: split into two separate `txt.append()` calls:
```python
# WRONG — renders as literal \n text
txt.append("━━━\\n## 📊 Performance (30d validated)")

# RIGHT — two separate list entries joined by \n.join()
txt.append("━━━")
txt.append("## 📊 Performance (30d validated)")
```

### Pitfall: Direction Logic Inversion for Mean-Reversion (anti-pattern: shorting the bottom)
When `_bottom_fishing` flags a candidate, the direction must ALWAYS be `"bullish"` regardless of 24h change sign — TOK is spot-only, no shorting. The original code used raw sign (`"bullish" if change_24h > 0 else "bearish"`), which meant a -14% dip got labeled "bearish" → target LOWER = SHORT recommendation at the bottom. **Fix**: the `_bottom_fishing_pipeline()` filters to `p < 0` only (positive moves can't be shorted), and the rendering code at line 1838 overrides direction:
```python
if c.get("_bottom_fishing"):
    direction = "bullish"
```

### Pitfall: `_regime_bias` Unit Mismatch (anti-pattern: comparing percentages to decimals)
Research calibrations store thresholds as decimals (`high_vol_threshold: 0.03` = 3%), but `_regime_bias()` receives percentage values (`1.0` = 1%). Without converting, `1.0 >= 0.03` is always True → everything classifies as "mean-reversion". **Fix**: multiply by 100 at read time:
```python
high = cal.get("high_vol_threshold", 0.03) * 100.0  # now 3.0%
low = cal.get("low_vol_threshold", 0.015) * 100.0   # now 1.5%
```

### Pitfall: Skill Directory Out of Sync (anti-pattern: editing repo files, cron runs skill dir)
The cron jobs run from `~/.hermes/skills/trading-advisor/` (the Hermes skill workdir). Code edits in `~/crypto-trading-ai/trading-advisor/scripts/` do NOT propagate. **Fix**: after every change, `cp` both `briefing.py` and `signal_validator.py` to the skill directory:
```bash
cp ~/crypto-trading-ai/trading-advisor/scripts/briefing.py \
   ~/.hermes/skills/trading-advisor/scripts/briefing.py
cp ~/crypto-trading-ai/trading-advisor/scripts/signal_validator.py \
   ~/.hermes/skills/trading-advisor/scripts/signal_validator.py
```

### Pitfall: Reusing Score Threshold Logic for Confidence Bars (anti-pattern: "Confidence" label)
The "Confidence" bar was a linear rescaling of the same scoring model used to rank candidates — circular reasoning presented as an independent measure. **Fix**: renaming to "Score" plus a separate **"Liq grade"** dimension derived from orderbook depth and spread (genuinely non-price):
```
Score: medium ████░░░░░░ · R/R 3.0x
Liq grade: B 🟡 (8bps spread · $125K depth)
```
Liq grade thresholds: A 🟢 (<5bps spread, >$500K depth), B 🟡 (<15bps, >$100K depth), C 🟠 (<30bps), D 🔴 (≥30bps). Falls back to ticker-level bid/ask when orderbook unavailable. Unknown grade shown as "⚪ unknown".

### Pitfall: Dev Noise in User-Facing Output (anti-pattern: orchestrator params in briefing)
Orchestrator status block (params, open signals, optimizer findings) is dev-venue noise in a decision briefing. Save to `reports/orchestrator_digest_{date}.md` instead of embedding. The `--orchestrator` flag now routes to the digest file; the briefing gets a one-liner reference only if not halted.

### Updated Example (v3.2 — Extreme Fear halt mode)
```markdown
# 📊 Daily Crypto Briefing
- Date: 2026-07-01
━ F&G: 11 (Extreme Fear) · BTC: 65.62% · Pulse: 🔴 · No picks

━━━
## ⚠️ Risk
Not financial advice.

━━━
## 📊 Market Regime
- BTC dominance: 65.62%
- Regime: Indeterminate (24h vol data unavailable for BTC)

⚠️ **Macro risk**: Extreme Fear.

## 🎯 Opportunities
🚫 **HALTED**: All signals blocked by extreme market regime.

━━━
## 📋 Today's Action
- 1) Check pre-market regime
- 2) Re-entry if F&G exits Extreme Fear (≥20)
- 3) Save powder until conditions met

━━━
## 📈 Quick P&L
- Paper: Equity $10,132.40 · Return 🔴 -1.34% · 0 open position(s)
```

### 1. Threshold Distance Metric (answers "How close was the best asset?")
`_funnel_summary()` now accepts scored candidates (`top` + `score_threshold`) and outputs a near-miss line:

```python
# briefing.py
def _funnel_summary(markets, top=None, score_threshold=25.0) -> list[str]:
    ...
    if top:
        near_misses = [(c["symbol"], c["score"]) for c in top if c["score"] < score_threshold]
        near_misses.sort(key=lambda x: x[1], reverse=True)
        miss_str = " · ".join(f"{sym} {score:.1f} ({score - score_threshold:+.1f})" 
                              for sym, score in near_misses[:3])
        lines.append(f"🎯 Near-miss: {miss_str}")
```

**Output example:**
```
📈 428 coins scanned → 170 ≥ $50M mcap → 53 ≥ 3% move
🎯 Near-miss: XRP 23.8 (-1.2) · DOGE 22.1 (-2.9) · ADA 21.5 (-3.5)
```

### 2. Regime Bias Banner (answers "Mean-reversion or momentum?")
Added to Market Regime section using `_regime_bias()` with research-calibrated volatility thresholds (1.5% / 3% from `research-calibrations.json`):

```python
# briefing.py — render_compact_briefing()
_regime_source = top[0] if top else next((c for c in markets if (c.get("symbol") or "").lower() == "btc"), None)
if _regime_source:
    _regime = _regime_bias(_regime_source.get("change_24h", 0))
    _vol = abs(_regime_source.get("change_24h", 0) or 0)
    _cal = _load_calibrations().get("regime", {})
    _hv = _cal.get("high_vol_threshold", 0.03) * 100
    _lv = _cal.get("low_vol_threshold", 0.015) * 100
    if _regime == "indeterminate":
        txt.append("- Regime: Indeterminate (24h vol data unavailable for BTC)")
    else:
        txt.append(f"- Regime bias: {_regime} (24h vol {_vol:.1f}% vs thresholds: >{_hv:.0f}% mean-rev / <{_lv:.0f}% momentum)")
```

**Output when data is available:**
```
- Regime bias: momentum (24h vol 2.1% vs thresholds: >3% mean-rev / <2% momentum)
```
**Output when BTC data is missing:**
```
- Regime: Indeterminate (24h vol data unavailable for BTC)
```

**Guard in `_regime_bias()`:**
```python
# briefing.py
def _regime_bias(change_24h: float) -> str:
    if change_24h is None or change_24h == 0.0:
        return "indeterminate"
    # ... threshold logic ...
```

### 3. Performance Metrics Block (answers "VaR / Expectancy if deploying 10%?")

Reads `signal_performance.json`, runs `summarize_with_empyrical()` on validated backtested signals:

```python
# signal_validator.py
def summarize_with_empyrical(signals):
    """Extended summary with empyrical risk metrics (VaR, CVaR, Sharpe,
    Sortino, Max DD, Calmar). Sets estimate_unstable=True when
    sample < 20, flags _var_cvar_identical when VaR ≈ CVaR."""
    base = summarize(signals)
    base["empyrical_available"] = False
    base["empyrical_metrics"] = None
    base["avg_win_pct"] = None
    base["avg_loss_pct"] = None
    validated = [s for s in signals
                 if s.get("validation_status") == "backtested"
                 and s.get("pnl_pct") is not None]
    base["sample_count"] = len(validated)
    base["estimate_unstable"] = len(validated) < 20
    if not validated:
        return base
    wins = [s["pnl_pct"] for s in validated if s.get("pnl_pct", 0) > 0]
    losses = [s["pnl_pct"] for s in validated if s.get("pnl_pct", 0) < 0]
    base["avg_win_pct"] = round(sum(wins)/len(wins), 3) if wins else None
    base["avg_loss_pct"] = round(sum(losses)/len(losses), 3) if losses else None
    if len(validated) < 3:
        return base
    import numpy as np, empyrical as ep
    returns = np.array([s["pnl_pct"]/100.0 for s in validated], dtype=np.float64)
    metrics = {
        "var_95": float(ep.value_at_risk(returns, 0.05)),
        "cvar_95": float(ep.conditional_value_at_risk(returns, 0.05)),
        "sharpe": float(ep.sharpe_ratio(returns, 0.0)),
        "sortino": float(ep.sortino_ratio(returns, 0.0)),
        "max_drawdown": float(ep.max_drawdown(returns)),
        "annual_volatility": float(ep.annual_volatility(returns)),
        "cagr": float(ep.cagr(returns)),
    }
    if abs(metrics["var_95"] - metrics["cvar_95"]) < 0.0001:
        metrics["_var_cvar_identical"] = True
    if len(returns) < 20:
        metrics["_small_sample_warning"] = \
            f"Only {len(returns)} sample(s). VaR/CVaR unreliable."
    base["empyrical_available"] = True
    base["empyrical_metrics"] = metrics
    return base
```

**Output example (small sample, estimate_unstable):**
```
━━━
## 📊 Performance (30d validated)
⚠️ Only 3 sample(s) — estimates unstable. VaR may reflect single tail event.
  VaR = CVaR: single worst outcome defines both. Not reliable for fat-tail risk.
- VaR (95%): -8.0% | CVaR: -8.0%
- Expectancy: 0.70% per trade | Win Rate: 40%
- Avg Win: +11.5% | Avg Loss: -6.5% | R: 1.77
```

**Briefing integration:** The performance block is no longer guarded by `if not _halted:` — the halt detection change (F&G ≤15 now activates bottom-fishing instead of halt) means metrics render during extreme fear. Only Extreme Greed (F&G ≥85) suppresses them. Small-sample warning renders when `estimate_unstable` is True; `_var_cvar_identical` line renders when VaR ≈ CVaR.
Per critic: "Unless your agent is performing NLP sentiment scoring that feeds into your weightings, this is just a digital newspaper. It adds zero value to your execution logic." The `_news_compact_block()` call was removed from `render_compact_briefing()`. The function definition still exists at line 995 for potential future use but is NOT called.

### 6. Resolved Architectural Gaps (2026-07-01 cycle)

| # | Gap | Resolution | Shipped |
|---|---|---|---|
| 1 | **No Bottom-Fishing mode** — `return []` at F&G ≤15 blocked all signals during capitulation | Replaced hard block with `_bottom_fishing_pipeline()` using mean-reversion scoring + ATR volatility gate. Wider stops (5%), down-move bonus (×1.2), 3-20% range filter. | v3.3 |
| 2 | **Performance metrics dead code** — `summarize_with_empyrical()` documented but never built; VaR/Expectancy/R-ratio block never executed | Built `summarize_with_empyrical()` using empyrical v0.5.12 + numpy. VaR, CVaR, Sharpe, Sortino, Calmar, Max DD, CAGR all compute. Small-sample warning (< 20) + VaR≈CVaR flag. | v3.3 |
| 3 | **No day-over-day delta** — Quick P&L showed absolute equity only | Saves/reads `reports/portfolio_snapshot.json`. Quick P&L shows `Δ24h 🟢 $+X.XX (+X.Xbps)` alongside total return. | v3.3 |
| 4 | **Performance metrics hidden during halt** — metrics block guarded by `if not _halted:` | F&G ≤15 now routes to bottom-fishing (not halt). Only F&G ≥85 is true halt. Metrics render during extreme fear. | v3.3 |
| 5 | **"Confidence" label misleading** — purely price-derived linear rescaling presented as sentiment | Renamed to "Score". Added separate "Liq grade" (A/B/C/D) from orderbook depth + spread — a genuinely non-price dimension. | v3.3 |

### 5. `signal_validator.summarize()` Extended (IMPLEMENTED 2026-07-01)

Added `avg_pnl_pct`, `avg_win_pct`, `avg_loss_pct` to base summary so empyrical metrics work on the briefing's parsed signals:

```python
# signal_validator.py
all_pnl = [s.get("pnl_pct") for s in validated if s.get("pnl_pct") is not None]
win_pnl = [s.get("pnl_pct") for s in wins if s.get("pnl_pct") is not None]
loss_pnl = [s.get("pnl_pct") for s in validated if s.get("pnl_pct") is not None and s not in wins]
avg_pnl = round(sum(all_pnl) / len(all_pnl), 2) if all_pnl else 0.0
avg_win = round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0.0
avg_loss = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
return {
    ...
    "avg_pnl_pct": avg_pnl,
    "avg_win_pct": avg_win,
    "avg_loss_pct": avg_loss,
}
```

Also added `summarize_with_empyrical()` which wraps `summarize()` with empyrical VaR, CVaR, Sharpe, Sortino, annual vol, and Calmar ratio. Uses `numpy` percentile for VaR/CVaR and `empyrical` for ratio-based metrics. Gracefully degrades with `empyrical_available=False` when <3 validated signals exist or imports fail.

**Briefing integration:** The performance block is no longer guarded by `if not _halted:` — the halt detection change (F&G ≤15 now activates bottom-fishing instead of halt) means metrics render during extreme fear. Only Extreme Greed (F&G ≥85) suppresses them.

---

## Complete Compact Briefing Example (v3.2 — Extreme Fear halted, no picks)

```markdown
# 📊 Daily Crypto Briefing
- Date: 2026-07-01
- Style: balanced swing/day spot
─ F&G: 11 (Extreme Fear) · BTC: 65.62% · Pulse: 🔴 · No picks

━━━
## ⚠️ Risk
Not financial advice.

━━━
## 📊 Market Regime
- BTC dominance: 65.62%
- Risk icon: 😱 - Extreme Fear
- Market pulse: 🔴 risk-off
- Regime: Indeterminate (24h vol data unavailable for BTC)

⚠️ **Macro risk**: Extreme Fear — even quality signals carry elevated risk.
📈 428 coins scanned → 170 ≥ $50M mcap → 53 ≥ 3% move

## 🎯 Opportunities
🚫 **HALTED**: All signals blocked by extreme market regime.

━━━
## 📋 Today's Action
- 1) Check pre-market regime
- 2) Re-entry if F&G exits Extreme Fear (≥20)
- 3) Save powder until conditions met

━━━
## 📈 Quick P&L
- Paper: Equity $10,132.40 · Return 🔴 -1.34% · 0 open position(s)
```

### Updated Example (v3.2 — Extreme Fear halted, no picks)
```markdown
# 📊 Daily Crypto Briefing
- Date: 2026-07-01
━ F&G: 11 (Extreme Fear) · BTC: 65.62% · Pulse: 🔴 · No picks

━━━
## ⚠️ Risk
Not financial advice.

━━━
## 📊 Market Regime
- BTC dominance: 65.62%
- Regime: Indeterminate (24h vol data unavailable for BTC)

⚠️ **Macro risk**: Extreme Fear.
📈 428 coins scanned → 170 ≥ $50M → 53 ≥ 3% move

## 🎯 Opportunities
🤷 No high-confidence setup today.

━━━
## 📋 Today's Action
- 1) Check pre-market regime
- 2) Re-entry if F&G exits Extreme Fear (≥20)
- 3) Save powder until conditions met

━━━
## 📈 Quick P&L
- Paper: Equity $10,132.40 · Return 🔴 -1.34% · 0 open position(s)
```

### Updated Example (v3.2 — Extreme Fear halted, no picks, first run) — Quick P&L with DoD delta
```markdown
## 📈 Quick P&L
- Paper: Equity $9,367.25 · Return 🟢 +0.00% · 0 open position(s)
```
When a prior `portfolio_snapshot.json` exists (saved after each run), the line shows:
```markdown
## 📈 Quick P&L
- Paper: Equity $9,367.25 · Return 🟢 +0.00% · Δ24h 🟢 $+42.50 (+4.5bps) · 0 open position(s)
```
Delta is displayed in dollars AND basis points (1% = 100bps). Snapshot is saved to `reports/portfolio_snapshot.json` with `{"equity": ..., "timestamp": "..."}` after each briefing run. First run has no prior snapshot and shows no Δ24h.

### Normal day with momentum picks
```markdown
# 📊 Daily Crypto Briefing
- Date: 2026-07-01
─ F&G: 45 (Neutral) · BTC: 62.1% · Pulse: 🟢 · Fees: low · 2 picks · 📈 momentum

━━━
## ⚠️ Risk
Not financial advice.

━━━
## 📊 Market Regime
- BTC dominance: 62.1%
- Risk icon: 😐 - Neutral
- Market pulse: 🟢 risk-on
- Regime bias: momentum (24h vol 2.1% vs thresholds: >3% mean-rev / <2% momentum)
- BTC funding: 🟡 neutral (5% annualized)
- BTC OI: $7,100,450,000
- Long/short: 1.15x (leaning long)
- BTC fees: 🟢 low (fast=3, hour=1 sat/vB)

📈 428 coins scanned → 170 ≥ $50M mcap → 53 ≥ 3% move
🎯 Near-miss: AAVE 23.8 (-1.2) · DOGE 22.1 (-2.9)

━━━
## 📊 Performance (30d validated)
⚠️ Only 3 sample(s) — estimates unstable. VaR may reflect single tail event.
- VaR (95%): -8.0% | CVaR: -8.0%
- Expectancy: 0.70% per trade | Win Rate: 40%
- Avg Win: +11.5% | Avg Loss: -6.5% | R: 1.77
- Sharpe: 2.39 | Sortino: 4.91 | Calmar: 0.15 (when sample ≥ 5)

## 🎯 Opportunities
1. Ethereum (ETH)
- Bias: momentum - bullish
- Why: 2.1% move; trending — momentum + cap flow aligned
- Entry: near 3450.0
- Stop: 3340.00 (-3.2%)
- Target: 3726.00 (+8.0%)
- Score: medium ████░░░░░░ · R/R 2.5x
- Liq grade: B 🟡 (8bps spread · $125K depth)
- TokoCrypto · $2.3M depth · 1.2 bps spread · tight (vs 5bps median)
- Research: 🟢 peer-reviewed ETH volatility clusters predict short-term momentum
```
