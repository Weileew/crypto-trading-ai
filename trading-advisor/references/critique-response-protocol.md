# Critique Response Protocol

Due-diligence workflow for responding to external audits/critiques of the trading system.

## When to Use

Whenever an external party (critic, user, auditor) delivers structured feedback on:
- Briefing quality, formatting, or decision-support adequacy
- Signal logic, pipeline filters, or scoring methodology  
- Performance metrics, P&L reporting, or risk measurement
- Any claim about what the system does or fails to do

Do NOT jump to implementation. Follow the protocol first.

## Step 1: Deconstruct the Critique

Read each claim independently. Do not accept or reject the verdict as a whole.

| Claim Type | How To Handle |
|---|---|
| Factual error | Note the mistake (wrong threshold, misdiagnosed root cause) |
| Valid observation | Accept the pain point, verify severity |
| Style/format preference | Note for later — separate from functional bugs |
| Implementation complaint | Trace to actual code path before agreeing |

**Key insight from experience**: Critics often correctly identify pain points (UX gaps, missing features) but misdiagnose the code-level cause. E.g., "pipeline filters too rigid" → the real cause was the regime gate blocking everything. Validate each cause, don't just fix the symptom the critic identified.

## Step 2: Ground-Truth Against Running Code

For every factual claim:

1. **Read the actual code** — do not assume code matches documentation
2. **Check for parallel rendering paths** — when the claim involves two display sections that reference the same coin or metric, verify they compute independently. The Opportunities section and Watch Levels section may both compute stop/target from the same source data but diverge when one handles flags (e.g., `_bottom_fishing`) the other doesn't. Always trace both code paths.
3. **Run the pipeline** — execute `briefing.py --compact` and inspect live output
4. **Check the data** — inspect portfolio.json, ledger.json, signal_performance.json
5. **Check cron delivery** — what the user receives may differ from saved report files (saved files can be stale from before a code fix)
6. **Simulate the alternative** — bypass the suspected gate/filter and run scoring to quantify what would pass

### Example: The F&G ≤15 Hard Block Audit

The critic claimed "hard-blocking at F&G < 20 is lazy." Due diligence revealed:
- Actual threshold was ≤15 (not <20) — factual error by critic
- The regime gate WAS the cause of "no picks" — but the critic blamed pipeline filters
- Simulating bypass: 52 candidates flowed through, DYDX scored 38.61 — confirming the critic's core point about missing opportunities

## Step 3: Cross-Reference Documentation vs Code

This is the most critical and most frequently skipped step. A known anti-pattern:

**Documentation describes features that were never coded.**

Signs to check:
- Does `signal_validator.summarize_with_empyrical()` exist as an importable function?
- Does `summarize()` return `avg_win_pct`, `avg_loss_pct`, `avg_pnl_pct`, or just the basic metrics?
- Are the `references/` files a faithful description of the current code, or aspirational?
- Does each `from X import Y` in user-facing code actually resolve? (A silent `except Exception: pass` can mask dead imports for weeks.)
- Are example outputs in the docs reproducible by running the current code verbatim?

### Real Bug Found: Dead Import

In the v3.2 audit:
- `signal-quality.md` documented `summarize_with_empyrical()` with full Python code
- `briefing.py` line 1500 imported it: `from signal_validator import summarize_with_empyrical`
- The function **never existed** in `signal_validator.py` — the import always threw `ImportError`
- The `except Exception: pass` swallowed the error silently
- The entire VaR/Expectancy/R-ratio performance metrics block was **completely inert** for weeks

Always verify: if you can't `import` the function, the integration block is dead code.

## Step 4: Dependency-Order Implementation

When multiple fixes are needed, order by dependency:

1. **Infrastructure/API** — no dependents, build first
   - Add a new function to a module (e.g., `summarize_with_empyrical()`)  
   - Extend existing functions with new return fields
2. **Shared utilities** — one dependent, build second
   - Extend `summarize()` to return avg_win_pct/avg_loss_pct so the briefing renderer can use them
3. **Integration points** — multiple dependents, build last
   - Wire the new function into the briefing renderer
   - Update halt detection, regime messaging, action items
4. **Guard removal / UI changes** — only after underlying function works
   - Remove `if not _halted:` guards
   - Add new display sections
   - Update empty-state messaging

**Test each change before moving to the next.**

## Step 4.5: UX/Precision Thresholds

When presenting metrics to end users, apply rounding gates that match the data's statistical significance:

| Metric type | Sample size | Display rule | Reason |
|---|---|---|---|
| Risk-adjusted (Sharpe, Sortino, Calmar) | n < 5 | Suppress entirely | Meaningless on <5 samples |
| Risk-adjusted | 5 ≤ n < 20 | `~1 (n=X, not meaningful)` | 2-decimal precision on <20 samples is false rigor. Round to 0 decimals, prefix `~`, append sample warning |
| Risk-adjusted | n ≥ 20 | Full 2-decimal precision | Statistically meaningful |
| Dollar deltas | | Suppress if |Δ| < $0.10 OR < 1bps | Near-zero deltas create visual confusion (green +0.01% next to red -$0.00). Define `_MIN_DELTA_DOLLARS` and `_MIN_DELTA_BPS` constants. |
| Win rate / Avg Win-Loss | All | Always show (1 decimal) | Basic counts, meaningful at any n |
| VaR/CVaR | n < 20 | Show but flag "may reflect single tail event" | Single outlier defines both VaR and CVaR on small samples |

**Key principle**: The disclaimer and the display must not fight each other. If you say "unstable estimate," don't show 2-decimal Sharpe.

## Step 5: Verify With Live Pipeline

After ALL changes, run the end-to-end pipeline with live API data:

```bash
cd /home/ubuntu/.hermes/skills/trading-advisor
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from briefing import simple_rules, fetch_markets, fetch_fear_greed, \
    render_compact_briefing, fetch_global, fetch_coincap
from signal_validator import summarize_with_empyrical

markets = fetch_markets()
fng = fetch_fear_greed()
global_data = fetch_global()
assets = fetch_coincap()

top = simple_rules(markets)
print(f'Candidates: {len(top)}')

text = render_compact_briefing(markets, global_data, fng, assets, enhanced=True)
assert 'python3 scripts' not in text, 'Ghost commands!'
assert '📰' not in text, 'News block present!'
assert 'VaR' in text, 'Performance metrics missing!'
assert 'Quick P&L' in text, 'P&L missing!'

with open('reports/signal_performance.json') as f:
    import json
    perf = json.load(f)
validated = [s for s in perf.get('signals', []) 
             if s.get('validation_status') == 'backtested' and s.get('pnl_pct') is not None]
emp = summarize_with_empyrical(validated)
assert emp.get('empyrical_available'), 'Empyrical metrics should work!'

print('ALL CHECKS PASSED')
"
```

### Verification Checklist

- [ ] No ghost commands (`python3 scripts/`) in delivered output
- [ ] No stale news block (`📰`) in compact briefing
- [ ] Funnel line present (`428 coins scanned → ...`)
- [ ] Correct regime messaging (`🎣 Bottom Fishing`, `🚫 HALTED`, or normal state)
- [ ] Performance metrics render (VaR, Expectancy, Win Rate, R)
- [ ] DoD snapshot saved to `reports/paper_trading/portfolio_snapshot.json`
- [ ] Empyrical metrics compute at runtime
- [ ] No silent `except Exception: pass` swallowing real errors

## Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Parallel rendering path divergence | Two sections of the same report show contradictory levels for the same coin (e.g., Opportunities says long, Watch Levels says short) | Check each rendering section independently — they may compute direction from raw `change_24h` without sharing the opportunity's override flags like `_bottom_fishing`. Two patterns exist: **(a) Direction divergence** — one path handles a flag (`_bottom_fishing → bullish`) the other doesn't → add the override to every path. **(b) Formula divergence** — each section computes stop/target percentages independently with different formulas (e.g., Opportunities includes `score_rr` and `_regime_max_stop`, Watch Levels doesn't) → fix is the **stored-value pattern**: store computed `_computed_target_pct` and `_computed_stop_pct` on the coin dict during the primary rendering loop, make Watch Levels (and any secondary section) read those stored values instead of recomputing. This eliminates divergence at the root and guarantees a single source of truth. After applying merge both fixes and re-check. |
| False precision on small samples | Sharpe 1.08 on n=5 trades — disclaimer says "unstable" but the display fights it | Gate risk-adjusted metrics at n≥20 for full precision; show `~N (n=X, not meaningful)` for 5-19; suppress below 5. |
| Trusting docs over code | Dead imports, baked-in examples that don't run | Cross-reference documentation vs code in Step 3 |
| Implementing before verifying | Fixing wrong root cause, missing dependencies | Follow Step 2 (ground truth) before Step 4 (implementation) |
| Multiplicative scoring bonuses | DYDX scored 102 instead of 52 | Test score ranges; prefer flat bonuses (`score += N`) over multiplicative chains |
| Silent error swallowing | VaR block never rendered for weeks | Remove `except Exception: pass` during development; verify the import actually resolves |
| Patch regression | A fix that worked in a previous round is broken in the current output even though the code appears to have been updated | When you `patch()` a section by replacing a block, overrides/state/flags that were added IN that block by a previous fix can be silently lost — the old lines are gone, and their logic with them. Always re-read both the OLD and NEW versions of the patched function after every edit. If your patch's `new_string` doesn't include all the logic the previous fix added, you've regressed. Defenses: (a) diff against the current file before writing a new patch; (b) prefer inserting new lines rather than replacing a whole block when the existing block has known overrides; (c) after every patch, grep for the flag/override to confirm it survived. |

## Origin

Derived from the 2026-07-01 v3.2 audit response session where a critic delivered a detailed 8-point critique. The protocol was built retroactively from what worked: due-diligence-first, cross-reference docs vs code, dependency-order implementation, live pipeline verification.

### Applied fix batch (2026-07-01, 8 issues fixed in briefing.py)

| Ref | Issue | Fix |
|-----|-------|-----|
| P0 | Watch Levels direction ignored `_bottom_fishing` | Added `_bottom_fishing → direction = bullish` override to Watch Levels renderer |
| P1 | Sharpe 1.08 on n=5 | Gated precision: n≥20 full, n=5-19 `~N (n=X, not meaningful)`, n<5 suppressed |
| P2 | F&G=11 vs L/S=1.21x divergence unsaid | Added divergence detection: when F&G<20 and L/S>1.2, surface the tension |
| P3 | "Near-miss: re 23.6 (-1.4)" unreadable | Added "vs threshold N" label so numbers are self-documenting |
| P4 | Low-score sole pick presented without caveat | Added `⚠️ Low conviction` note when single pick scores "low" |
| P5 | Two sizing instructions could conflict | Combined liq_mult + bottom-fishing 50% into single effective line |
| P6 | Generic research citation shown as authoritative | Added `⚠️ Generic citation` warning when paper score < 1.0 |
| P7 | `$-0.00 (-0.0bps)` with red arrow confusing | Raised delta threshold from $0.001 to $0.10 / 1bps |

### Applied fix batch (2026-07-01, second wave — 4 issues fixed in briefing.py)

The second round of critic feedback revealed deeper bugs and showed that the first wave's fixes were incomplete in two cases (P0 and P5):

| Ref | Issue | What was wrong with first pass | Fix |
|-----|-------|-------------------------------|-----|
| P0.2 | **Stop-loss mismatch between sections** — first pass only fixed the direction (short→long) but left two independent formulas computing stop/target% differently | First pass added `_bottom_fishing` override to Watch Levels but didn't address that Opportunities and Watch Levels used different formulas (different vol_factor, score_rr, regime_max_stop) | Store `_computed_target_pct` and `_computed_stop_pct` on the coin dict in the Opportunities loop. Watch Levels reads these values instead of recomputing from scratch. Single source of truth — sections **cannot** diverge. |
| P5.2 | **Sizing guidance disappeared** — first pass removed the 65% multiplier line instead of reconciling it with the 50% bottom-fishing rule | First pass didn't change the code; the 65% line just happened not to fire for that day's coin because liq_mult≥1.0. The latent contradiction remained. | Compute effective sizing when both paths are active: `liq_mult × 0.5` and display a single combined line. Today's Action defers to Opportunities sizing instead of duplicating a potentially conflicting number. |
| New | **Liquidity grade granularity** — $38K/1.6bps depth and $7K/8bps both graded C 🟠, masking meaningfully different liquidity profiles | Not a regressive fix — the grade function was reading inputs correctly but thresholds were too coarse | Added intermediate B tier: `spread < 5 AND depth > $30K` catches tight-spread/moderate-depth coins. RE moved from C→B. |
| New | **Research citation truncation** — "exploitable by" trailing off mid-sentence with no indicator of truncation | 140-char word-boundary trim plus `...` when the finding is cut. Short findings pass through unchanged. |
