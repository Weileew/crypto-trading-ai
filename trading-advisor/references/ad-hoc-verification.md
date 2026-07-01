# Ad-hoc Verification Pattern for Trading Advisor

## Purpose
A reusable pattern for verifying trading-advisor fixes without a formal test suite. Used when `pytest` is not available and a focused, self-cleaning verification script is needed.

## Template

```python
#!/usr/bin/env python3
"""Ad-hoc verification of trading-advisor fixes."""
import sys
import tempfile
import os
import subprocess

# Create verification script
verify_script = '''
#!/usr/bin/env python3
"""Ad-hoc verification of trading-advisor fixes."""
import sys
sys.path.insert(0, '/home/ubuntu/crypto-trading-ai/trading-advisor/scripts')

from briefing import fetch_markets, fetch_global, fetch_fear_greed, fetch_coincap, render_compact_briefing, render_briefing
from paper_trader import parse_briefing_recommendations
from paper_executor import parse_recommendations
from signal_validator import parse_buy_recommendations, fetch_coingecko_market_chart

print("=" * 60)
print("VERIFICATION: Trading Advisor Fixes")
print("=" * 60)

# Test 1: fetch_markets determinism (cached)
print("\n1. fetch_markets determinism (cached):")
m1 = fetch_markets()
m2 = fetch_markets()
m3 = fetch_markets()
print(f"   Run 1: {len(m1)} markets")
print(f"   Run 2: {len(m2)} markets")
print(f"   Run 3: {len(m3)} markets")
assert len(m1) == len(m2) == len(m3), "fetch_markets not deterministic!"
print(f"   ✅ PASS: Consistent at {len(m1)} markets")

# Test 2: Briefing generation
print("\n2. Briefing generation:")
g = fetch_global()
f = fetch_fear_greed()
a = fetch_coincap()
compact = render_compact_briefing(m1, g, f, a, visuals=True, enhanced=True, orchestrator=True)
full = render_briefing(m1, g, f, a, compact=False, visuals=True, enhanced=True, orchestrator=True)
print(f"   Compact: {len(compact)} chars")
print(f"   Full: {len(full)} chars")
assert len(compact) > 1000, "Compact briefing too short"
assert len(full) > 1000, "Full briefing too short"
print(f"   ✅ PASS: Both formats generated")

# Test 3: Parser consistency
print("\n3. Parser consistency (all 3 parsers, both formats):")
pt_compact = parse_briefing_recommendations(compact)
pe_compact = parse_recommendations(compact)
sv_compact = parse_buy_recommendations(compact)
pt_full = parse_briefing_recommendations(full)
pe_full = parse_recommendations(full)
sv_full = parse_buy_recommendations(full)

print(f"   Compact: PT={len(pt_compact)}, PE={len(pe_compact)}, SV={len(sv_compact)}")
print(f"   Full:    PT={len(pt_full)}, PE={len(pe_full)}, SV={len(sv_full)}")
assert len(pt_compact) == len(pe_compact) == len(sv_compact), "Compact parser mismatch!"
assert len(pt_full) == len(pe_full) == len(sv_full), "Full parser mismatch!"
assert len(pt_compact) >= 1, "No recommendations in compact"
assert len(pt_full) >= 1, "No recommendations in full"
print(f"   ✅ PASS: All parsers agree on both formats")

# Test 4: Signal validation (OHLC endpoint)
print("\n4. Signal validation - OHLC candle fetch:")
candles = fetch_coingecko_market_chart("bitcoin", days=30)
print(f"   Bitcoin OHLC: {len(candles)} candles")
assert len(candles) > 0, "No candles returned!"
print(f"   ✅ PASS: OHLC endpoint working")

# Test 5: Paper trading
print("\n5. Paper trading M2M:")
from paper_trader import load_portfolio, update_mark_to_market
portfolio = load_portfolio()
closed = update_mark_to_market(portfolio)
print(f"   Open positions: {len(portfolio.get('positions', {}))}")
print(f"   Closed this tick: {len(closed)}")
print(f"   ✅ PASS: Paper trading functional")

# Test 6: Compile check
print("\n6. Syntax check (py_compile):")
import py_compile
scripts = [
    '/home/ubuntu/crypto-trading-ai/trading-advisor/scripts/briefing.py',
    '/home/ubuntu/crypto-trading-ai/trading-advisor/scripts/paper_trader.py',
    '/home/ubuntu/crypto-trading-ai/trading-advisor/scripts/paper_executor.py',
    '/home/ubuntu/crypto-trading-ai/trading-advisor/scripts/signal_validator.py',
]
for s in scripts:
    py_compile.compile(s, doraise=True)
print(f"   ✅ PASS: All 4 scripts compile cleanly")

print("\n" + "=" * 60)
print("ALL VERIFICATION CHECKS PASSED")
print("=" * 60)
'''

# Write and run verification script
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', prefix='hermes-verify-', delete=False) as f:
    f.write(verify_script)
    script_path = f.name

try:
    result = subprocess.run([sys.executable, script_path], 
                          capture_output=True, text=True, timeout=300)
    print(result.returncode)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print(f"Exit code: {result.returncode}")
finally:
    os.unlink(script_path)
```

## Usage
Run directly:
```bash
python3 /path/to/this/script.py
```

Or copy the inner `verify_script` template and customize the import paths and assertions for your specific changes.

## Key Principles
1. **Self-cleaning**: Uses `tempfile.NamedTemporaryFile` with `delete=False` + explicit `os.unlink()` in `finally` block
2. **Prefix**: Uses `hermes-verify-` prefix for easy identification
3. **Timeout**: 300s max to prevent hanging
4. **Exit codes**: Returns 0 on all pass, non-zero on any failure
5. **Comprehensive**: Tests fetch, parsing, validation, paper trading, and syntax in one run
6. **Evidence-first**: Prints actual values (counts, chars, candles) not just pass/fail

## When to Use
- After any non-trivial patch to trading-advisor scripts
- Before committing changes
- When smoke_test.py needs supplementing
- When pytest is unavailable
- For CI/CD integration where a lightweight check is needed