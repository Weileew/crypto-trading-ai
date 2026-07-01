# Compact Daily Trading Briefing Template

Use this for short, actionable daily briefings focused on trade opportunities.

## Format
```markdown
# 📊 Daily Crypto Briefing
- Date: YYYY-MM-DD
- Style: balanced swing/day spot
- Exchange: TokoCrypto (pairs gated by USDT availability)
━ F&G: 18 (Extreme Fear) · BTC: 66.4% · Pulse: 🔴 · Fees: low · 2 picks  ← At-a-glance summary

━━━
## ⚠️ Risk
Not financial advice. This is a checklist, not a green light. Preserve capital first.

━━━
## 📊 Market Regime
- BTC dominance: X%
- Risk icon: 😱/🤑 — Fear/Greed label
- Market pulse: 🟢 risk-on / 🔴 risk-off
- Market cap shift: strongest stream above X%
- BTC funding: 🟡 neutral (5% annualized)
- BTC OI: $X
- Long/short: X.XXx (signal)
- BTC fees: 🟢 low (fast=X, hour=X sat/vB)

⚠️ Macro risk: Extreme Fear — even quality signals carry elevated macro risk. Size down, tighten stops.
📈 N coins scanned → N ≥ $50M mcap → N ≥ 3% move  ← Screening funnel

📋 Paper Trading Recap  (only if recent closed trades exist)
- 🟢/🔴 SYM: outcome (P&L%)

🎯 Opportunities  (skipped if none, with reason)
1. Name (symbol)
- Bias: (mean-reversion|momentum) - bullish|bearish
- Why: X.XX% move; regime-aware thesis
- Entry: near <price>
- Stop: <price> (-X.X%)
- Target: <price> (+X%)  — dynamic 5–15% based on vol+score
- Confidence: medium ███████░░░░░
- TokoCrypto · $<depth> depth · <spread> bps spread · exec quality
- Sizing: XX% multiplier (spread-adjusted)  — only if <1.0
- Portfolio: reason  — only if penalty active
- Derivatives: reason  — only if funding adjustment active
- ⚠️ trap_flag · ⚠️ trap_flag  — only when trap filters fire
- Research: [🟢 peer-reviewed] finding snippet
  Strong/Relevant match — tags: X,Y

━━━
## 🔭 Watch Levels
- BTC levels: see latest market data
- Review opportunities above for entry timing

━━━
## 📈 Quick P&L
- Paper: `python3 scripts/paper_trader.py --summary`

━━━
## 📋 Today's Action
- 1) Confirm regime at market open
- 2) Review TokoCrypto orderbook for opportunity coins
- 3) Verify 1h/4h trend alignment before entry

📰 Market News  (compact block, non-fatal — only if fetch succeeds)
- Sentiment: 🟢N / 🔴N / ⚪N
- 🟢/🔴/⚪ headline

## Orchestrator Status  (only with --orchestrator flag)
- Params: ...
- Performance: ...
```

## Rules
- Max 300 words
- Max 2 trade ideas
- Only include setups with 2+ agreeing signals
- If no valid setups, explain WHY nothing passed (all below thresholds / only 1 candidate)
- Always include risk disclosure first
- Optional visuals: use DOM bar, risk icon, confidence bar when `--visuals` is enabled
- Do not append full paper trading table to briefing; keep references only
- Enhanced mode (`--enhanced`) can append compact DeFi, DEX, and stablecoin flow notes for regime context
- Opportunity items show live TokoCrypto orderbook depth (`TokoCrypto · $<depth> depth · <spread> bps spread`) from `_format_depth_line()` — degrades to ticker-level spread if depth fetch fails
- Trap flags appear when any of the 9 trading trap filters fire (see `references/trap-filters.md`)
- Target displays include percentage: `(+X%)` for bullish, `(-X%)` for bearish — dynamic per candidate (5–15%)
- Macro context banner auto-appears when Fear & Greed < 20 (`⚠️ Macro risk: Extreme Fear...`) or < 30 (`⚡ Macro note: Fear...`)
- Summary bar (line starting with `━`) shows F&G, BTC dominance, pulse icon, network fees, and pick count at a glance
- Section separators (━━━) and emoji headers provide visual hierarchy on Telegram variable-width font
- Empty-state for Opportunities includes a reason: "all screened below thresholds" or "only 1 passed — insufficient for pair analysis"
