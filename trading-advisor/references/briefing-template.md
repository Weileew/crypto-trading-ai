# Daily Trading Briefing Template

Use this template when writing the daily crypto trading briefing.

## Format Guidance

- Convert market situation into clear sections
- Use concise headings for quick migration
- Label charts separately from text analysis

## Template

```markdown
# Daily Crypto Trading Briefing
- Date: YYYY-MM-DD
- User style: balanced swing / day spot
- Data freshness: state what is live versus cached

## Risk Disclosure
Every briefing must start with this block.
This is not financial advice. Trading spot crypto carries significant risk; you can lose principal.
Past performance does not predict future results. Use stop losses and proper position sizing.

## Macro Regime
- Bitcoin dominance: ___%
- Altcoin market cap trend: up / down / flat
- DXY / equities / risk sentiment: up / down / flat / mixed
- verdict: risk-on / neutral / risk-off
- reasoning: 2-3 explicit sentences

## Market Watch (TokoCrypto Liquidity Note)
- BTC_IDRT: best bid / ask, spread, depth
- Top alts by conversation / interest: name 2-3 max
- liquidity_flag: healthy / thin / avoid
- reasoning: why

## Market Movers & Liquid Trends
- volume spikes: list coins with clearer changes in volume
- distribution / accumulation notes on 24h and 72h basis
- leverage VWAP direction and comparison with spot VWAP if available

## Sentiment / News Flow
- macro: label as rumor / news / fact
- sector themes: names 3 themes most impacting today

## Setup Radar
- setups: list only setups meeting 2+ independent signals
- status: active / watching / invalidated
- time horizon: day / swing / both
- direction: long / short / cash
- trigger: price condition
- stop: price and justification
- target: price and justification
- probability: high / medium / low with reasoning
- risk/reward ratio estimate: numeric
- risk note: concise

## Standby Plan (if no position tonight)
- preconditions: what must hold for trade to be valid
- watch levels: key prices
- invalidation: what price / data cancels setup

## Action Checklist
- next data pull / forward-looking chart review time is 
- follow up coins / pairs most important to watch

## Source Quality Summary
- source_name: quality score and weakness in plain text
```

## Flow Rules

- Length: 1200-1500 words if possible
- Avoid vague words like possible, likely. Use specific reasoning and explicit percentage ranges if possible.
- Always show the alpha versus the cheapskate advice difference in one sentence or less, with sourcing detail.
- Extend to 3000 words only when asked for detailed deep analysis.
- Never send to user if a required input is missing; mark clearly "data_missing: source_name".
