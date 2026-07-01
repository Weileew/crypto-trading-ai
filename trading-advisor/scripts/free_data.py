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


# ── CG-specific rate limiter (6s spacing, daily budget tracker) ──
_CG_LAST_CALL = 0.0
_CG_SLEEP = 6.0  # CG free tier: ~10 req/min → 6s min spacing
_CG_DAILY_COUNTER_PATH = os.path.join(REPORTS_DIR, "cg_call_count.json")
_CG_MAX_DAILY = 500  # safety threshold (actual free limit is ~14,400)


def _wait_cg():
    global _CG_LAST_CALL
    wait = _CG_SLEEP - (time.time() - _CG_LAST_CALL)
    if wait > 0:
        time.sleep(wait)


def _count_cg_call():
    """Increment daily CG call counter. Logs warning at 90% of threshold."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    try:
        with open(_CG_DAILY_COUNTER_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {"date": today, "count": 0}
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] += 1
    # Warn at 90% of threshold
    if data["count"] >= int(_CG_MAX_DAILY * 0.9) and data["count"] % 10 == 0:
        print(f"  ⚠️ CG calls today: {data['count']}/{_CG_MAX_DAILY} (90%+ of safety threshold)")
    with open(_CG_DAILY_COUNTER_PATH, "w") as f:
        json.dump(data, f)
    return data["count"]


def _get_cg(url, params=None, timeout=25, retries=3):
    """CG-specific GET with 6s spacing, exponential backoff, call counter."""
    _count_cg_call()
    h = {"User-Agent": UA}
    if params:
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    req = Request(url, headers=h)
    last_err = None
    for attempt in range(1, retries + 1):
        _wait_cg()
        try:
            with urlopen(req, timeout=timeout) as resp:
                global _CG_LAST_CALL
                _CG_LAST_CALL = time.time()
                return json.loads(resp.read().decode())
        except HTTPError as e:
            _CG_LAST_CALL = time.time()
            if e.code == 429 or 500 <= e.code < 600:
                last_err = e
                time.sleep(3.0 * attempt)  # aggressive backoff for CG
                continue
            return {"_http_error": e.code, "_url": url}
        except Exception as e:
            _CG_LAST_CALL = time.time()
            last_err = e
            time.sleep(2.0 * attempt)
            continue
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

# ── TokoCrypto Public API (no auth) ──────────────────────────────────────────
# Base endpoint for public market data — no API key needed.
_TOKO_BASE = "https://www.tokocrypto.site/api/v3"

def _toko_get(path, params=None, timeout=15):
    """GET from TokoCrypto public API with minimal rate-limiting."""
    from urllib.parse import urlencode
    url = f"{_TOKO_BASE}{path}"
    if params:
        url += "?" + urlencode(params)
    h = {"User-Agent": UA}
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_tokocrypto_exchange_info():
    """Return exchange info dict (all symbols, filters, rates)."""
    return _toko_get("/exchangeInfo")


def fetch_tokocrypto_usdt_pairs():
    """Return set of base asset symbols for TRADING USDT pairs on TokoCrypto."""
    data = fetch_tokocrypto_exchange_info()
    if not isinstance(data, dict):
        return set()
    pairs = set()
    for s in data.get("symbols", []):
        if isinstance(s, dict) and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            pairs.add((s.get("baseAsset") or "").upper())
    return pairs


def fetch_tokocrypto_tickers():
    """Return list of 24hr tickers for ALL pairs on TokoCrypto.
    
    Each entry: symbol, priceChange, priceChangePercent, lastPrice, volume,
    quoteVolume, bidPrice, bidQty, askPrice, askQty, highPrice, lowPrice, openPrice.
    """
    return _toko_get("/ticker/24hr")


def fetch_tokocrypto_ticker(symbol):
    """Return 24hr ticker for a single USDT pair (e.g. 'BTCUSDT')."""
    return _toko_get("/ticker/24hr", {"symbol": symbol.upper()})


def fetch_tokocrypto_book_ticker(symbol):
    """Return best bid/ask for a single pair. Lightweight single call."""
    return _toko_get("/ticker/bookTicker", {"symbol": symbol.upper()})


def fetch_tokocrypto_depth(symbol, limit=20):
    """Return orderbook depth for a pair.
    
    Returns dict with 'bids' and 'asks' lists of [price, qty].
    """
    limit = min(limit, 100)
    return _toko_get("/depth", {"symbol": symbol.upper(), "limit": limit})


def fetch_tokocrypto_klines(symbol, interval="1h", limit=100):
    """Return OHLCV klines for a pair.
    
    Each row: [openTime, open, high, low, close, volume, closeTime, quoteVolume,
               trades, takerBuyBaseVol, takerBuyQuoteVol, ignore]
    """
    limit = min(limit, 500)
    return _toko_get("/klines", {"symbol": symbol.upper(), "interval": interval, "limit": limit})


def compute_tokocrypto_depth_metrics(depth_data):
    """Compute spread and depth metrics from orderbook data.
    
    Returns dict with: spread_bps, bid_depth, ask_depth, total_depth, bid_count, ask_count
    or None if data is invalid.
    """
    if not isinstance(depth_data, dict):
        return None
    bids = depth_data.get("bids", [])
    asks = depth_data.get("asks", [])
    if not bids or not asks:
        return None
    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        if best_bid <= 0 or best_ask <= 0:
            return None
        spread_bps = round((best_ask - best_bid) / best_bid * 10000, 2)
        # Aggregate depth within 1% of mid price
        mid = (best_bid + best_ask) / 2
        pct_threshold = mid * 0.01
        bid_depth = sum(float(b[1]) * float(b[0]) for b in bids if abs(float(b[0]) - mid) <= pct_threshold)
        ask_depth = sum(float(a[1]) * float(a[0]) for a in asks if abs(float(a[0]) - mid) <= pct_threshold)
        return {
            "spread_bps": spread_bps,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "bid_depth_usd": round(bid_depth, 2),
            "ask_depth_usd": round(ask_depth, 2),
            "total_depth_usd": round(bid_depth + ask_depth, 2),
            "bid_count": len(bids),
            "ask_count": len(asks),
        }
    except (ValueError, TypeError, IndexError):
        return None


def build_tokocrypto_ticker_map(tickers):
    """Build {SYMBOL: dict} lookup from TokoCrypto 24hr tickers list.
    
    Returns dict keyed by base asset (e.g. 'BTC' → {lastPrice, volume, ...}).
    """
    if not isinstance(tickers, list):
        return {}
    tmap = {}
    for t in tickers:
        if not isinstance(t, dict):
            continue
        sym = t.get("symbol", "")
        # Only USDT pairs
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4].upper()
        try:
            tmap[base] = {
                "tokocrypto_last": float(t.get("lastPrice", 0)),
                "tokocrypto_volume_base": float(t.get("volume", 0)),
                "tokocrypto_volume_quote": float(t.get("quoteVolume", 0)),
                "tokocrypto_change_24h": float(t.get("priceChangePercent", 0)),
                "tokocrypto_bid": float(t.get("bidPrice", 0)),
                "tokocrypto_ask": float(t.get("askPrice", 0)),
                "tokocrypto_high": float(t.get("highPrice", 0)),
                "tokocrypto_low": float(t.get("lowPrice", 0)),
                "tokocrypto_open": float(t.get("openPrice", 0)),
            }
        except (ValueError, TypeError):
            continue
    return tmap


# Legacy TokoCrypto reference (manual browser approach)
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


# ── On-Chain Data (free, no auth) ─────────────────────────────────────────────
# Mempool.space — BTC fee estimates, no API key needed

_MEMPOOL_BASE = "https://mempool.space/api"


def fetch_btc_fees():
    """Return current BTC fee estimates from mempool.space.

    Returns dict {fastestFee, halfHourFee, hourFee, economyFee, minimumFee}
    all in sat/vB, or {"_error": "..."} on failure.
    """
    return _get(f"{_MEMPOOL_BASE}/v1/fees/recommended", timeout=15, retries=2)


def fetch_mempool_stats() -> dict:
    """Fetch BTC mempool fee data and format for briefing.

    Returns dict with keys: fees_ok, fastest, hour, summary, icon
    All keys present; failed fetches return empty dict.
    """
    fees = fetch_btc_fees()
    if not isinstance(fees, dict) or "_error" in fees or "fastestFee" not in fees:
        return {}

    fastest = fees.get("fastestFee", 0)
    hour = fees.get("hourFee", 0)
    economy = fees.get("economyFee", 0)

    # Interpret fee levels
    if fastest > 100:
        icon = "⚠️"
        summary = "high congestion"
    elif fastest > 30:
        icon = "🟡"
        summary = "elevated"
    elif fastest > 10:
        icon = "🟢"
        summary = "moderate"
    else:
        icon = "🟢"
        summary = "low"

    return {
        "fees_ok": True,
        "fastest": fastest,
        "hour": hour,
        "economy": economy,
        "summary": summary,
        "icon": icon,
    }


# ── Derivatives Data (free, no auth) ──────────────────────────────────────────
# Binance Futures public API — funding rate, open interest, long/short ratio
_FAPI_BASE = "https://fapi.binance.com"


def fetch_funding_rate(symbol="BTCUSDT", limit=1):
    """Return latest funding rate for a perpetual futures pair.

    Args:
        symbol: e.g. 'BTCUSDT', 'ETHUSDT'
        limit: number of historical records (1 = latest only)

    Returns:
        dict with {symbol, fundingRate (str), fundingTime, markPrice}
        or {"_error": "..."} on failure.
    """
    return _get(
        f"{_FAPI_BASE}/fapi/v1/fundingRate",
        {"symbol": symbol.upper(), "limit": min(limit, 100)},
        timeout=15, retries=2
    )


def fetch_open_interest(symbol="BTCUSDT"):
    """Return current open interest for a perpetual futures pair.

    Returns dict with {symbol, openInterest (str), time}
    or {"_error": "..."} on failure.
    """
    return _get(
        f"{_FAPI_BASE}/fapi/v1/openInterest",
        {"symbol": symbol.upper()},
        timeout=15, retries=2
    )


def fetch_long_short_ratio(symbol="BTCUSDT", period="1h", limit=1):
    """Return top trader long/short position ratio.

    Returns list of dicts with {symbol, longAccount, shortAccount,
    longShortRatio, timestamp} or {"_error": "..."} on failure.
    """
    return _get(
        f"{_FAPI_BASE}/futures/data/topLongShortPositionRatio",
        {"symbol": symbol.upper(), "period": period, "limit": min(limit, 500)},
        timeout=15, retries=2
    )


def interpret_funding_rate(rate_str: str) -> tuple:
    """Interpret a funding rate string into a human signal.

    Args:
        rate_str: e.g. "0.00004284" (decimal, 8h period)

    Returns:
        (signal_label, signal_icon, annualized_pct)
        signal_label: one of "extreme positive", "positive", "neutral",
                      "negative", "extreme negative"
        signal_icon: 🟢/🟡/🔴/⚠️
        annualized_pct: the rate annualized (×3 for 8h periods × 365)
    """
    try:
        rate = float(rate_str)
    except (TypeError, ValueError):
        return "unknown", "⚪", 0.0

    # Binance funding is per 8h. Annualized = rate * 3 * 365
    annualized = rate * 3 * 365 * 100  # in percent

    if rate > 0.001:      # >0.1% per 8h → extreme positive (crowded long)
        return "extreme positive", "⚠️", annualized
    elif rate > 0.0001:   # >0.01% per 8h → positive
        return "positive", "🟢", annualized
    elif rate > -0.0001:  # near zero → neutral
        return "neutral", "🟡", annualized
    elif rate > -0.001:   # >-0.1% → negative
        return "negative", "🔴", annualized
    else:                 # < -0.1% → extreme negative (crowded short)
        return "extreme negative", "⚠️", annualized


def fetch_derivatives_summary(symbol="BTCUSDT") -> dict:
    """Fetch funding rate, OI, and long/short ratio in a single call batch.

    Returns dict with keys: funding_rate, oi_btc, oi_usd, ls_ratio,
    ls_signal, signal, annualized_pct
    All keys present; failed fetches return None for that key.
    """
    out = {"symbol": symbol}

    # Funding rate
    fr = fetch_funding_rate(symbol, limit=1)
    if isinstance(fr, list) and len(fr) > 0:
        rate_str = fr[0].get("fundingRate", "0")
        out["funding_rate"] = float(rate_str)
        signal, icon, ann = interpret_funding_rate(rate_str)
        out["funding_signal"] = signal
        out["funding_icon"] = icon
        out["annualized_pct"] = round(ann, 1)
    else:
        out["funding_rate"] = None

    # Open interest
    oi = fetch_open_interest(symbol)
    if isinstance(oi, dict) and "openInterest" in oi:
        try:
            oi_btc = float(oi["openInterest"])
            out["oi_btc"] = round(oi_btc, 1)
            # Use latest mark price from funding rate to estimate USD value
            mark = None
            if isinstance(fr, list) and len(fr) > 0:
                mark = float(fr[0].get("markPrice", 0))
            if mark:
                out["oi_usd"] = round(oi_btc * mark, 0)
            out["oi_btc"] = out.get("oi_btc")  # already set
        except (ValueError, TypeError):
            out["oi_btc"] = None
    else:
        out["oi_btc"] = None

    # Long/short ratio
    ls = fetch_long_short_ratio(symbol, limit=1)
    if isinstance(ls, list) and len(ls) > 0:
        try:
            ratio = float(ls[0].get("longShortRatio", 1.0))
            out["ls_ratio"] = round(ratio, 3)
            if ratio > 1.5:
                out["ls_signal"] = "crowded long"
            elif ratio > 1.2:
                out["ls_signal"] = "leaning long"
            elif ratio < 0.67:
                out["ls_signal"] = "crowded short"
            elif ratio < 0.8:
                out["ls_signal"] = "leaning short"
            else:
                out["ls_signal"] = "balanced"
        except (ValueError, TypeError):
            out["ls_ratio"] = None
    else:
        out["ls_ratio"] = None

    return out


# ── Shared coin alias resolution (single source of truth) ───────────
_COIN_ALIASES_CACHE = None


def _load_coin_aliases():
    """Load & cache the shared coin_aliases.json (singleton)."""
    global _COIN_ALIASES_CACHE
    if _COIN_ALIASES_CACHE is not None:
        return _COIN_ALIASES_CACHE
    alias_path = os.path.join(SKILL_DIR, "strategy", "coin_aliases.json")
    try:
        with open(alias_path) as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    _COIN_ALIASES_CACHE = {k: v for k, v in raw.items() if v is not None}
    return _COIN_ALIASES_CACHE


def resolve_coin_id(sym: str) -> str:
    """Resolve a ticker symbol -> CoinGecko coin ID.

    Three-tier resolution:
    1.  Shared coin_aliases.json (single source of truth).
    2.  Smart CG search — scans up to 10 results, picks the one whose
        *symbol* matches the query (avoids short-ticker errors where
        the top search result is a completely different coin).
    3.  Falls through with the raw symbol (may fail on CG candle fetch,
        then Binance klines fallback catches it).
    """
    label = (sym or "").strip().lower()
    aliases = _load_coin_aliases()
    if label in aliases:
        return aliases[label]

    hit = _smart_coingecko_search(label)
    if hit:
        return hit
    return label


def _smart_coingecko_search(query: str):
    """Search CG and scan top results for an exact symbol match."""
    try:
        data = _get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": query},
            timeout=15,
            retries=2,
        )
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    coins = data.get("coins") or []
    ql = query.lower()
    for c in coins[:10]:
        sym = (c.get("symbol") or "").lower()
        if sym == ql:
            return c.get("id")
        name = (c.get("name") or "").lower()
        if ql in name and len(ql) > 3:
            return c.get("id")
    if coins:
        top = coins[0]
        top_sym = (top.get("symbol") or "").lower()
        if len(ql) >= 3 and (top_sym.startswith(ql) or ql.startswith(top_sym)):
            return top.get("id")
    return None


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
