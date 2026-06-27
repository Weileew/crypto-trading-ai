#!/usr/bin/env python3
"""Crypto trading data fetcher for free public endpoints."""
import os
import json
import time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

UA = "crypto-trading-advisor/0.1 (+https://example.com)"

# Gentle rate limit: delay between sequential calls.
_RATE_DELAY_SECS = 0.55
# CoinGecko documented public rate limit is 5–15 req/min — stay conservative.
# Each _get_with_backoff respects retries + exponential delays; use sparingly.
_LAST_CALL_TS = 0.0


def _wait_rate_limit():
    global _LAST_CALL_TS
    wait = _RATE_DELAY_SECS - (time.time() - _LAST_CALL_TS)
    if wait > 0:
        time.sleep(wait)


def _get(url, params=None, headers=None, timeout=20, retries=3, backoff=1.25):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if params:
        from urllib.parse import urlencode
        if "?" in url:
            url = url + "&" + urlencode(params)
        else:
            url = url + "?" + urlencode(params)
    req = Request(url, headers=h)
    last_err = None
    for attempt in range(1, retries + 1):
        _wait_rate_limit()
        try:
            with urlopen(req, timeout=timeout) as resp:
                global _LAST_CALL_TS
                _LAST_CALL_TS = time.time()
                return json.loads(resp.read().decode())
        except HTTPError as e:
            _LAST_CALL_TS = time.time()
            if e.code == 429 or 500 <= e.code < 600:
                last_err = e
                time.sleep(backoff * attempt)
                continue
            return {"_http_error": e.code, "_url": url}
        except Exception as e:
            _LAST_CALL_TS = time.time()
            last_err = e
            time.sleep(backoff * attempt)
    return {"_fetch_error": str(last_err), "_url": url}

def fetch_coingecko_markets(vs_currency="usd", per_page=250, page=1):
    data = _get("https://api.coingecko.com/api/v3/coins/markets", {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": page,
        "sparkline": "false",
        "price_change_percentage": "24h,7d",
    })
    return data

def fetch_coingecko_global():
    return _get("https://api.coingecko.com/api/v3/global")

def fetch_coincap_assets(limit=100):
    data = _get("https://api.coincap.io/v2/assets", {"limit": limit})
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def fetch_dex_screener_search(query="bitcoin", limit=20):
    """Return top DEX pairs for a query; free registrationless JSON API."""
    data = _get(f"https://api.dexscreener.com/latest/dex/search?q={query}", timeout=20)
    if not isinstance(data, dict):
        return []
    pairs = data.get("pairs") or []
    out = []
    for p in pairs[:limit]:
        out.append(
            {
                "chain_id": p.get("chainId"),
                "dex_id": p.get("dexId"),
                "pair_address": p.get("pairAddress"),
                "base_token_symbol": (p.get("baseToken") or {}).get("symbol"),
                "quote_token_symbol": (p.get("quoteToken") or {}).get("symbol"),
                "price_usd": (p.get("priceUsd")),
                "txns_h1": ((p.get("txns") or {}).get("h1")),
                "volume_h6": ((p.get("volume") or {}).get("h6")),
                "price_change_h1": ((p.get("priceChange") or {}).get("h1")),
            }
        )
    return out


def fetch_defillama_protocols(limit=200):
    """Return DeFi protocols by TVL from DeFiLlama; gateway for sector rotation."""
    data = _get(f"https://api.llama.fi/v2/protocols", timeout=25)
    if not isinstance(data, list):
        return []
    if limit:
        data = data[:limit]
    out = []
    for p in data:
        out.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "tvl": p.get("tvl"),
                "mcap": p.get("mcap"),
                "chain_tvls": p.get("chainTvls"),
            }
        )
    return out


def fetch_defillama_yields(limit=200):
    """Return yield pool values for a quick yield / risk sentiment read."""
    data = _get("https://yields.llama.fi/pools", timeout=25)
    if not isinstance(data, dict) or data.get("status") != "success":
        return []
    pools = data.get("data") or []
    if limit:
        pools = pools[:limit]
    out = []
    for p in pools:
        out.append(
            {
                "chain": p.get("chain"),
                "project": p.get("project"),
                "symbol": p.get("symbol"),
                "tvl_usd": p.get("tvlUsd"),
                "apy": p.get("apy"),
                "stablecoin": p.get("stablecoin"),
                "il_risk": p.get("ilRisk"),
            }
        )
    return out


def fetch_defillama_stablecoins(limit=50):
    """Return stablecoin circulatory metrics for peg/flow sanity check."""
    data = _get("https://stablecoins.llama.fi/stablecoins", timeout=25)
    if not isinstance(data, dict):
        return []
    pegged = data.get("peggedAssets") or []
    if limit:
        pegged = pegged[:limit]
    out = []
    for s in pegged:
        circulating = (s.get("circulating") or {}).get("peggedUSD") or 0
        prev_day = ((s.get("circulatingPrevDay") or {}).get("peggedUSD") or circulating)
        out.append(
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "symbol": s.get("symbol"),
                "pegged_usd": circulating,
                "prev_day_pegged_usd": prev_day,
                "peg_type": s.get("pegType"),
                "peg_mechanism": s.get("pegMechanism"),
            }
        )
    return out


def fetch_stablecoin_net_flows(limit=20):
    """Aggregate stablecoin net flow proxy from circulation delta top items."""
    rows = fetch_defillama_stablecoins(limit=200)
    rows = [r for r in rows if r.get("peg_type") == "peggedUSD"]
    rows.sort(key=lambda r: r.get("pegged_usd") or 0, reverse=True)
    top = rows[:limit]
    out = []
    for s in top:
        current = s.get("pegged_usd") or 0
        prev = s.get("prev_day_pegged_usd") or current
        delta = current - prev
        pct = ((delta / prev) * 100.0) if prev else 0.0
        out.append(
            {
                "symbol": s.get("symbol"),
                "name": s.get("name"),
                "pegged_usd": current,
                "daily_delta": delta,
                "daily_delta_pct": pct,
            }
        )
    return out


def fetch_fear_greed():
    # Alternative.me Fear & Greed
    url = "https://api.alternative.me/fng/?limit=1&format=json"
    data = _get(url)
    if isinstance(data, dict) and "data" in data and data["data"]:
        return data["data"][0]
    return data

def fetch_coingecko_ohlc(coin_id="bitcoin", days=1):
    # 1/7/30/90/180/365/max
    return _get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc", {"vs_currency": "usd", "days": days})

def get_ohlc_summary(coin_id="bitcoin", days=7):
    ohlc = fetch_coingecko_ohlc(coin_id, days)
    if not isinstance(ohlc, list) or not ohlc:
        return {"status": "missing"}
    closes = [x[4] for x in ohlc]
    highs = [x[2] for x in ohlc]
    lows = [x[3] for x in ohlc]
    return {
        "status": "ok",
        "start": ohlc[0][0],
        "end": ohlc[-1][0],
        "open": ohlc[0][1],
        "close": closes[-1],
        "high": max(highs),
        "low": min(lows),
        "min_low": min(lows),
        "max_high": max(highs),
        "h": len(ohlc),
    }

def get_simple_technicals(prices):
    # prices: list of closes
    out = {}
    if len(prices) < 14:
        return {"error": "not enough data"}
    def ema(vals, n):
        k = 2/(n+1)
        e = vals[0]
        for x in vals[1:]:
            e = x * k + e * (1-k)
        return e
    def rsi(vals, n=14):
        g = [max(0, vals[i]-vals[i-1]) for i in range(1, len(vals))]
        l = [max(0, vals[i-1]-vals[i]) for i in range(1, len(vals))]
        avg_g = sum(g[:n])/n
        avg_l = sum(l[:n])/n
        if avg_l == 0:
            return 100.0
        for i in range(n, len(vals)):
            avg_g = (avg_g*(n-1) + max(0, vals[i]-vals[i-1]))/n
            avg_l = (avg_l*(n-1) + max(0, vals[i-1]-vals[i]))/n
        rs = avg_g/avg_l
        return 100 - 100/(1+rs)
    out["last"] = prices[-1]
    out["ema20"] = ema(prices[-20:], 20) if len(prices) >= 20 else ema(prices, len(prices))
    out["ema50"] = ema(prices[-50:], 50) if len(prices) >= 50 else None
    out["ema200"] = ema(prices[-200:], 200) if len(prices) >= 200 else None
    out["rsi14"] = rsi(prices, 14)
    sma20 = sum(prices[-20:])/min(20, len(prices))
    out["sma20"] = sma20
    return out

# TokoCrypto liquidity: requires browser automation or manual entry via tokocrypto reference
def tokocrypto_snapshot_instructions():
    return {
        "instructions": "Open TokoCrypto spot orderbook page and record best bid/ask, spread(bps), depth within 1%.",
        "file_template": f"{REPORTS_DIR}/tokocrypto_snapshot_<SYMBOL>.json",
        "fields": ["best_bid", "best_ask", "bid_size", "ask_size", "spread_bps", "depth_within_1pct_quote", "recent_trades_last_5m_summary"]
    }

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def save(data, filename="latest_market_data.json"):
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"as_of": now_iso(), "data": data}, f, indent=2, default=str)
    return path

if __name__ == "__main__":
    print("Fetching Coingecko markets...")
    markets = fetch_coingecko_markets()
    print("global...")
    global_data = fetch_coingecko_global()
    print("Coincap assets...")
    assets = fetch_coincap_assets(limit=100)
    print("Fear & Greed...")
    fg = fetch_fear_greed()
    summary = {
        "coingecko_top5": markets[:5] if isinstance(markets, list) else markets,
        "global": global_data,
        "coincap_top5": assets[:5] if isinstance(assets, list) else assets,
        "fear_greed": fg,
    }
    path = save(summary, "latest_market_data.json")
    print("Saved", path)
