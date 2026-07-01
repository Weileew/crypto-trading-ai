# Briefing Quality Audit

Systematic methodology for evaluating a trading briefing's quality against three dimensions identified during a real critique (2026-06-30):

## 1. Actionability — does a cash trader know what to do?

**What to check**: The "Today's Action" section when `opps` is empty.

**Code location**: `render_compact_briefing()` lines 1633-1636 in `scripts/briefing.py`

**Failure mode**: Vague instructions like "save powder" or "rescan when 1h/4h trends align" without concrete re-entry triggers.

**What should exist**: When picks=0, the briefing should compute and display numeric re-entry thresholds from data already in scope:
- F&G exit threshold (e.g. "rescan if F&G exits Extreme Fear ≥20")
- BTC price levels if available

**Data available in scope**: `fng_val` (line 1307), `btc_dom` (line 1303), `global_data` (parameter). No additional API calls needed — pure formatting.

---

## 2. Metric Relevance — does every number serve the regime context?

**What to check**: The enhanced regime block (`_compact_regime_block()`)

**Code location**: `scripts/briefing.py` lines 1019-1046

**Data fetched**: DeFiLlama protocols TVL, DeFiLlama yield pools (stablecoin APY), stablecoin net flows, DEX Screener BTC pairs.

**Regime gating**: As of 2026-06-30, the function takes NO `fng_val` parameter — it always fetches and displays all data regardless of Fear & Greed level.

**What to gate by F&G**:
- **DeFi top TVL** — noise in Extreme Fear (F&G < 20). Gate out with `if fng_val is None or int(fng_val) >= 20:`.
- **Stablecoin APY** — ACTUALLY RELEVANT in Extreme Fear. Elevated stable yields (>4%) indicate capital prefers to sit idle, corroborating risk-off thesis. Keep always.
- **Stablecoin flows** — marginal but relevant. The delta between best/worst flow shows where capital is rotating. Keep always.
- **DEX BTC pairs** — regime context regardless. Keep always.

---

## 3. Performance Context — is a bad number left hanging?

**What to check**: The orchestrator status block (`_orchestrator_block()`)

**Code location**: `scripts/briefing.py` lines 1670-1706

**Key data point**: Shows `WR` and `PF` from `compute_performance("trailing_30d")` which reads `journal.db` — this is the strategy journal's `outcomes` table, NOT the signal validator.

**Two data sources diverge**:

| Source | Scope | Location | Call |
|---|---|---|---|
| Strategy Journal (`journal.db`) | ALL signals from outcomes table | `_orchestrator_block()` → `compute_performance()` | 28 closed trades (as of Jun 30) |
| Signal Validator (`signal_performance.json`) | Backtests specific recommendations against candles | `signal_validator.py` → `reports/signal_performance.json` | 5-7 validated signals |

**When PF < 1.0 or WR < 40%**: The briefing shows the bad number but surfaces NO analysis or action plan. Yet the pipeline already computes this data:

1. **`suggest_adjustments()`** in `strategy/portfolio_engine.py` (lines 563-608) — produces concrete strings like:
   - `"Profit factor 0.88 < 1.0: review trap-filter scores or increase correlation_threshold"`
   - `"Win rate 42.9% < 40%: consider raising min_24h_change_pct or score_threshold"`
   - Uses same `journal_performance()` source so the sample size matches (28 trades, not 5)

2. **`parameter-optimizer-weekly`** (last run Jun 28) — produces `strategy/optimizer_report.json` with concrete recommendations:
   - `"Optimal min_24h_change_pct=5% (current=3%)"`
   - `"Optimal score_threshold=10 (current=25)"`

**Fix pattern**: In `_orchestrator_block()`, after the performance line, call `suggest_adjustments()` (via same `importlib.spec_from_file_location` pattern already used for `strategy_journal`) and append results when PF < 1.0. Also read `optimizer_report.json` if it exists.

**No circular import risk**: `_orchestrator_block()` imports `strategy_journal` via spec_from_file_location. `suggest_adjustments()` calls `journal_performance()` which reads `strategy_journal` independently. The portfolio_engine import pattern is the same already used by the orchestrator-nightly pipeline (`orchestrator.py` lines 405-410).

---

## Precedent Code Paths

The orchestrator-nightly (`scripts/orchestrator.py`) already does all three of these:
- Calls `calibration_health()` + `suggest_adjustments()` (lines 405-410)
- Runs full 7-phase pipeline: news → briefing → journal → validate → performance → adapt → calibration health → dashboard

The morning briefing just doesn't surface the adjustment data that the pipeline already produces.

---

## Verification Pattern

After any patch to these areas:
```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -m py_compile scripts/briefing.py

# Generate test briefing
python3 scripts/briefing.py --compact --save-only --enhanced --orchestrator

# Read output
cat reports/daily_briefing_$(date +%Y-%m-%d).md
```

Check:
- No picks → re-entry triggers present with numeric thresholds
- F&G < 20 → TVL line absent, stablecoin APY + flows present
- PF < 1.0 → suggest_adjustments() output visible below performance line
