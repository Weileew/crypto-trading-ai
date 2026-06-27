# Compact Daily Trading Briefing Template

Use this for short, actionable daily briefings focused on trade opportunities.

## Format
```markdown
# 📊 Daily Crypto Briefing
- Date: YYYY-MM-DD
- Style: balanced swing/day spot
- Exchange: TokoCrypto (pairs gated by USDT availability)

## Risk
⚠️ Not financial advice. This is a checklist, not a green light. Preserve capital first.

## Market Regime
- BTC dominance: X%
- Risk icon: 😱/🤑 — Fear/Greed label
- Market pulse: 🟢 risk-on / 🔴 risk-off
- Market cap shift: strongest stream above X%

⚠️ Macro risk: Extreme Fear — even quality signals carry elevated macro risk. Size down, tighten stops.
_(Only shown when Fear & Greed < 20; milder note at < 30)_

## Opportunities
### 1. Name (symbol)
- Bias: bullish|bearish
- Why: 24h=±X.XX%; momentum + cap flow aligned
- Entry: near <price>
- Stop: <price>
- Target: <price> (+8%) or (-8%) for bearish
- Confidence: medium ███████░░░░░
- TokoCrypto · $<depth> depth · <spread> bps spread
- ⚠️ falling knife · ⚠️ thin pump _(only shown when trap filters fire)_
- Research: [🟢 peer-reviewed] "Paper Title" (doi:...)

## Watch Levels
- BTC key levels: see latest market data
- Review top 1-2 alts from opportunities above

## Quick P&L Monitor
- Paper trading: run `python3 scripts/paper_trader.py --summary`

## Today's Action
- 1) Confirm regime at market open
- 2) Review TokoCrypto orderbook for opportunity coins
- 3) Verify 1h/4h trend alignment before entry
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
- Opportunity items show live TokoCrypto orderbook depth (`TokoCrypto · $<depth> depth · <spread> bps spread`) from `_format_depth_line()` — degrades to ticker-level spread if depth fetch fails
- Trap flags appear when any of the 9 trading trap filters fire (see `references/trap-filters.md`)
- Target displays include percentage: `(+8%)` for bullish, `(-8%)` for bearish — direction is bias-aware
- Macro context banner auto-appears when Fear & Greed < 20 (`⚠️ Macro risk: Extreme Fear...`) or < 30 (`⚡ Macro note: Fear...`)