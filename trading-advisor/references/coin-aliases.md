## CoinGecko ID Resolution (single source of truth)

**Target:** Centralize ticker→CG-ID mapping across all scripts.

### Architecture (as of 2026-06-29)

```
strategy/coin_aliases.json   ← shared JSON (86+ entries)
       │
       ▼
scripts/free_data.py         ← resolve_coin_id(sym) + _smart_coingecko_search()
       │
       ├── scripts/signal_validator.py  (import via importlib)
       └── scripts/paper_trader.py      (import via importlib)
```

### Resolution order (3 tiers)

1. **Alias file** (`strategy/coin_aliases.json`) — exact lookup, returns known CG ID.
2. **Smart CG search** (`_smart_coingecko_search()`) — scans top 10 search results for exact symbol match. Handles short tickers like `syn`→`synapse-2`, `rif`→`rif-token` where naive top-result lookup returns a different coin.
3. **Raw label** — if both fail, returns the ticker as-is (will likely fail CG candle fetch, but Binance klines fallback catches it).

### Adding a new coin

Edit only `strategy/coin_aliases.json`. Do NOT touch `signal_validator.py` or `paper_trader.py` — they import from `free_data.py` automatically.

```json
{
  "new_ticker": "coin-gecko-id-from-api",
  ...
}
```

### Finding a CG API ID

1. Search on coingecko.com for the coin.
2. Scroll down to the **API ID** field on the coin page.
3. OR use the smart search: `python3 -c 'from scripts.free_data import _smart_coingecko_search; print(_smart_coingecko_search("ticker"))'`

### Stablecoins

Set to `null` in `coin_aliases.json` (they are stripped during load and not used for candle fetching).

### What was removed

- `ALIAS` dict from `signal_validator.py`
- `_SYM_TO_CG` dict from `paper_trader.py`
- Local `_coingecko_search()` and `resolve_coin_id()` from `signal_validator.py`
