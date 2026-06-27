# Compact Daily Trading Briefing Template

Use this for short, actionable daily briefings focused on trade opportunities.

## Format
```markdown
# 📊 Daily Crypto Briefing
Date: YYYY-MM-DD
Style: balanced swing/day spot

## Risk
⚠️ Not financial advice. This is a checklist, not a green light. Preserve capital first.

## Market Regime
- BTC dominance: X%
- Risk mood: fear / greed / neutral
- Market pulse: 🟢 risk-on / 🔴 risk-off
- Market cap shift: strongest stream above X%
- Optional visuals: BTC dominance bar, sentiment icon, confidence bar

## Opportunities
### 1. SYMBOL - Direction
- Why: 1-2 sentences with data
- Entry: price / condition
- Stop: price
- Target: price
- Confidence: high/medium/low
- Liquidity: healthy / thin

### 2. SYMBOL - Direction
- Why: 1-2 sentences with data
- Entry: price / condition
- Stop: price
- Target: price
- Confidence: high/medium/low
- Liquidity: healthy / thin

## Watch Levels
- Key support/resistance for BTC and 1-2 alts

## Quick P&L Monitor
- Paper trading: run `python3 scripts/paper_trader.py --summary`

## Today's Action
- 3 bullet max: what to check, when, and why
```

## Rules
- Max 300 words
- Max 2 trade ideas
- Only include setups with 2+ agreeing signals
- If no valid setups, say "No high-confidence setup today" and list what would need to change
- Always include risk disclosure first
- Optional visuals: use DOM bar, risk icon, confidence bar when `--visuals` is enabled
- Do not append full paper trading table to briefing; keep references only
- Enhanced mode (`--enhanced`) can append compact DeFi, DEX, and stablecoin flow notes for regime context