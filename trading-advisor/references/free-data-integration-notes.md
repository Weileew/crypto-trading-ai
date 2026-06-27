# Free Data Integration Notes

Validated without registration. Coverage:
- DeFiLlama: protocols by TVL, yield pools, stablecoin circulation, BTC TVL history
- DEX Screener: pair search with txn counts, volume, price change
- CoinGecko: markets, global, fear & gend, OHLC/market chart
- Binance: `exchangeInfo` USDT pair gate and klines fallback
- Alternative.me: Fear & Greed index

Validation:
- endpoints return JSON without auth
- CoinCap: DNS-blocked in some environments; not required for core flow
- BTC TVL chart endpoint returns ~1926 daily points with `totalLiquidityUSD`

Gotchas:
- `briefing.py` previously crashed when CoinGecko returned a non-list inside `data` or when Binance USDT gate was empty. `fetch_markets()` now normalizes both branches.
- DEX Screener hit counts can be low; treat txn/volume as directional unless TokoCrypto verifies liquidity.
- Stablecoin flows from `stablecoins.llama.fi` use `circulatingPrevDay` proxy for daily delta. Good for regime, not precise accounting.
