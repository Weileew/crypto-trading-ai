# TokoCrypto Liquidity Reference

## Two Access Modes

### Mode A — Public API (no API key, automated)
TokoCrypto exposes Binance-compatible REST endpoints on `www.tokocrypto.site` (separate subdomain from the web UI) that require **no authentication** for market data.

- **Base URL:** `https://www.tokocrypto.site/api/v3/`
- **Auth required?** ❌ No — only for private endpoints (balance, orders)
- **Coverage:** 3,609 symbols total · **674 USDT pairs** (vs 437 on Binance spot)
- **Rate limits:** Binance Cloud standard limits (~1200 req/min)
- **CCXT:** Supported since v1.92.42 via `ccxt.tokocrypto()`

| Endpoint | Works without key? | Use case |
|---|---|---|
| `/api/v3/exchangeInfo` | ✅ | Symbol list, trading status, filters |
| `/api/v3/ticker/24hr` | ✅ | 24hr price/vol stats per symbol |
| `/api/v3/depth` | ✅ | Orderbook bids/asks |
| `/api/v3/trades` | ✅ | Recent fills |
| `/api/v3/klines` | ✅ | OHLCV candles |
| `/api/v3/time` | ✅ | Server time |

**NOTE:** `www.tokocrypto.com/api/v3/*` (the `.com` domain) requires an API key even for public endpoints. Always use the `.site` subdomain for unauthenticated access.

### Mode B — Browser / Manual Snapshot (legacy)
For private data (account balances, order history) or when the `.site` API is unavailable.

## Files Generated
- `tokocrypto_snapshot_{symbol}.json`
- latest snapshot symlink: `tokocrypto_snapshot_latest.json`

## Procedure (Browser Mode)
1. Open TokoCrypto spot market for target coin pair in a browser-capable state.
2. Wait for orderbook to stabilize.
3. Extract:
   - best bid / best ask
   - sizes and cumulative depth within 1%
   - recent fills quantity range
   - spread basis points
4. Persist the result in JSON inside report workdir.
5. Compare previous snapshot to current to detect liquidity changes.

## Quick API Test (no key needed)
```bash
curl -s "https://www.tokocrypto.site/api/v3/depth?symbol=BTCUSDT&limit=5"
curl -s "https://www.tokocrypto.site/api/v3/exchangeInfo" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); \
   usdt=[s['symbol'] for s in d['symbols'] if s['symbol'].endswith('USDT')]; \
   print(f'{len(usdt)} USDT pairs'); print(usdt[:5])"
```

## Notes
- Do NOT treat unfilled depth as available capital; execution risk is high on thin orderbooks.
- Negative mark if best bid size < 0.1% of notional you would reasonably trade at once.
- Do NOT trade if spread > 0.5% unless there is an overwhelming trend reason and wide stop.
- Public API mode removes the geo-restriction issue — `.site` API is globally accessible even when the web UI blocks the IP.
