# Crypto Trading Advisor + Orchestrator

**Hermes Agent-based crypto trading system** — automated daily briefings, signal validation, strategy adaptation, and paper trading.

## What's Included

### 🧠 Trading Advisor (`trading-advisor/`)
- **15 Python scripts** — briefing generator, paper trader, signal validator, orchestrator, market news, trade planner, daily loop, smoke tests
- **9 reference docs** — data sources, orchestrator setup, compact briefing template, audit checklist, cron schedule
- **Strategy journal** — SQLite DB of all signals, outcomes, parameter changes, and performance snapshots
- **Strategy params** — adaptive screening thresholds (min_mcap, min_24h_change, score_threshold)
- **Reports** — daily briefings, health heartbeat, signal performance, latest market data

### 🔄 Orchestrator (`trading-advisor/scripts/orchestrator.py`)
6-phase nightly pipeline:
1. **News Monitor** — CoinTelegraph + CoinDesk RSS + Fear & Greed
2. **Briefing** — screens ~424 coins across 97% of Binance USDT pairs
3. **Journal** — records signals to SQLite
4. **Validation** — checks open signals vs live prices
5. **Performance** — trailing 30d win rate, profit factor
6. **Adaptation** — auto-tightens on loss streaks, loosens on sustained wins

### 📚 Crypto Research (`crypto-research/`)
- **116 research papers** (76 peer-reviewed + 31 preprint + 9 general) on crypto trading, volatility, DeFi, market microstructure
- **Consolidated research digest** — topic-grouped, tiered summaries
- **Paper collector & query scripts** — OpenAlex-based, runs daily at 05:30

## Cron Schedule

| Job | Schedule | Purpose |
|-----|----------|---------|
| `orchestrator-nightly` | 04:00 UTC | Full 6-phase cycle |
| `morning-briefing` | 08:00 | Compact briefing + enhanced |
| `afternoon-briefing` | 14:00 | Compact briefing + enhanced |
| `paper-trading-m2m` | Every 6h | Mark-to-market update |
| `continuous-improvement` | Every 12h | Heuristic tuning |
| `research-enrichment` | 05:30 | New paper collection |
| `maintenance` | 02:00 | Housekeeping |

## Restore Instructions

```bash
# Clone this repo
git clone https://github.com/Weileew/crypto-trading-ai.git

# Copy skills back to Hermes
cp -r trading-advisor ~/.hermes/skills/
cp -r crypto-research ~/.hermes/skills/

# Re-create cron jobs via Hermes CLI
hermes cron list  # then recreate as needed
```

## Tech Stack
- **Platform:** Hermes Agent (skill-based system)
- **Data:** CoinGecko (free), Binance API, DeFiLlama, DEX Screener, Fear & Greed
- **DB:** SQLite (strategy journal)
- **Persistence:** Auto-pushed to GitHub every 15min via Hermes cron

---
*Backup generated: June 2026*
