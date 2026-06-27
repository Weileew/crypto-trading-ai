# Free Crypto Data Source Playbook

Guidelines for pulling free crypto data without signing up for a paid API.

## Price/Market Data
- CoinGecko `/coins/markets` and `/coins/{id}/ohlc` for price, market cap, volume, circulating supply.
- CoinCap `/assets` or CSV for near-real-time prices with lighter rate limits.
- CoinMarketCap free tier for 1-minute delays on crypto data if API key is configured.
- CoinPaprika free for additional pairs and 24h aggregates.

## Technical Indicators
- Use OHLCV fetched nightly to compute:
  - EMA 20/50/200, SMA 20
  - RSI 14
  - ATR 14
  - MACD
  - Bollinger bands 20 2σ
  - VWAP per session
  - Volume profile / volume-weighted price zones

## Liquidity / Exchange
- TokoCrypto requires manual inspection via the TokoCrypto web UI. Record key metrics in a compact orderbook snapshot file for the advisor to read:
  - best bid/as size
  - best ask/as size
  - spread in basis points
  - depth within 1%
  - recent trade events summary
  Use `references/tokocrypto.md` for exact steps.

## Macro / Sentiment
- Fear & Greed Index API or direct HTML scrape daily.
- Stock indices for risk-on/risk-off bias: S&P 500, Nasdaq 100, DXY via free market data endpoints.
- Bitcoin dominance and ether dominance via CoinGecko.
- Optional: crypto news aggregators without auth.

## On-Chain
- Glassnode includes free data with an API key. Even with a free key, only use endpoints with available rate limits; do not average substitute on missing endpoints.
- CryptoQuant free alerts for netflow, exchange flows.
- Santiment only when publicly available aggregator data is present and cross-checked.

## News / Social
- For each coin search:
  - Low-latency free news via crypto aggregators
  - Social sentiment via free endpoints when available
  - YouTube whitepaper or roadmap summaries when relevant
- Label each signal as factual, claim, or rumor.

## Data Quality
- Prefer authoritative sources.
- Do not merge different TZ candles.
- If a required signal is missing, mark it explicitly.
- Mark stale data > 48 hours as invalid for day setup scoring.
