#!/usr/bin/env python3
"""Daily crypto briefing generator."""
import argparse
import json
import os
import re
import subprocess
import time as _time_module
from datetime import UTC, datetime
from urllib.request import Request, urlopen

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

UA = "crypto-trading-advisor/0.1 (+https://example.com)"

QUERY_PAPERS = os.path.join(
    os.path.dirname(SKILL_DIR), "crypto-research", "scripts", "query_papers.py"
)

# Consolidated digest — single file replacing per-paper lookups
RESEARCH_DIGEST = os.path.join(
    os.path.dirname(SKILL_DIR), "crypto-research", "references", "research-digest.md"
)

# Research-calibrated parameters — loaded from strategy/research-calibrations.json
_CALIBRATIONS = None
_CALIB_PATH = os.path.join(SKILL_DIR, "strategy", "research-calibrations.json")

# Portfolio engine — correlation-aware sizing, drawdown limits, exposure gating
PORTFOLIO_ENGINE = None
_PORTFOLIO_ENGINE_PATH = os.path.join(SKILL_DIR, "strategy", "portfolio_engine.py")

# Derivatives cache — fetched once per briefing run
_DERIVATIVES_CACHE = None


def _fetch_derivatives_once():
    """Fetch BTC derivatives summary once per process and cache it."""
    global _DERIVATIVES_CACHE
    if _DERIVATIVES_CACHE is None:
        try:
            from free_data import fetch_derivatives_summary
            _DERIVATIVES_CACHE = fetch_derivatives_summary("BTCUSDT")
        except Exception:
            _DERIVATIVES_CACHE = {}
    return _DERIVATIVES_CACHE


def _load_calibrations() -> dict:
    global _CALIBRATIONS
    if _CALIBRATIONS is not None:
        return _CALIBRATIONS
    try:
        with open(_CALIB_PATH, encoding="utf-8") as f:
            _CALIBRATIONS = json.load(f)
    except Exception:
        _CALIBRATIONS = {"regime": {}, "liq_uidity": {}, "sentiment": {}}
    return _CALIBRATIONS

from free_data import (
    _get,
    build_tokocrypto_ticker_map,
    compute_tokocrypto_depth_metrics,
    fetch_defillama_protocols,
    fetch_defillama_yields,
    fetch_dex_screener_search,
    fetch_fear_greed,
    fetch_stablecoin_net_flows,
    fetch_tokocrypto_depth,
    fetch_tokocrypto_tickers,
    fetch_tokocrypto_usdt_pairs,
)

# CG-specific rate limiter — free tier is 10-30 req/min, play safe at 6s spacing
_CG_MIN_INTERVAL = 6.0
_CG_LAST_CALL = _time_module.time() - (_CG_MIN_INTERVAL - 0.5)  # stagger first call
# Separate budget for the global endpoint — it rate-limits differently
_CG_GLOBAL_MIN_INTERVAL = 12.0
_CG_GLOBAL_LAST_CALL = 0.0


def _get_cg(url, params=None):
    """CoinGecko-specific GET with conservative rate limiting (6s min interval)."""
    global _CG_LAST_CALL
    wait = _CG_MIN_INTERVAL - (_time_module.time() - _CG_LAST_CALL)
    if wait > 0:
        _time_module.sleep(wait)
    result = _get(url, params=params, retries=4, backoff=2.0)
    _CG_LAST_CALL = _time_module.time()
    return result


def _get_cg_global():
    """Fetch CoinGecko global with a separate, more conservative rate budget."""
    global _CG_GLOBAL_LAST_CALL
    wait = _CG_GLOBAL_MIN_INTERVAL - (_time_module.time() - _CG_GLOBAL_LAST_CALL)
    if wait > 0:
        _time_module.sleep(wait)
    result = _get("https://api.coingecko.com/api/v3/global", retries=3, backoff=3.0)
    _CG_GLOBAL_LAST_CALL = _time_module.time()
    return result


def _extract_market_items(raw):
    """Normalise CoinGecko /coins/markets response into a list of dicts."""
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), list):
            return raw["data"]
        return []
    if isinstance(raw, list):
        return [it for it in raw if isinstance(it, dict)]
    return []


def _fetch_coingecko_page(page=1, per_page=250):
    """Fetch one page of CoinGecko /coins/markets (top N by market cap)."""
    raw = _get_cg(
        "https://api.coingecko.com/api/v3/coins/markets",
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h,7d",
        },
    )
    items = _extract_market_items(raw)
    return items


def _fetch_coingecko_coin_list():
    """Return dict {SYMBOL: id} for all coins on CoinGecko."""
    raw = _get_cg("https://api.coingecko.com/api/v3/coins/list")
    if not isinstance(raw, list):
        return {}
    mapping = {}
    for c in raw:
        if isinstance(c, dict):
            sym = (c.get("symbol") or "").upper()
            if sym:
                mapping[sym] = c.get("id")
    return mapping


def _extract_single_coin_market(coin_data):
    """Extract /coins/markets-shaped fields from a /coins/{id} response."""
    if not isinstance(coin_data, dict):
        return None
    md = coin_data.get("market_data") or {}
    current_price = None
    if isinstance(md.get("current_price"), dict):
        current_price = md["current_price"].get("usd")
    market_cap = None
    if isinstance(md.get("market_cap"), dict):
        market_cap = md["market_cap"].get("usd")
    total_volume = None
    if isinstance(md.get("total_volume"), dict):
        total_volume = md["total_volume"].get("usd")
    return {
        "id": coin_data.get("id"),
        "symbol": coin_data.get("symbol"),
        "name": coin_data.get("name"),
        "current_price": current_price,
        "market_cap": market_cap,
        "market_cap_change_percentage_24h": md.get("market_cap_change_percentage_24h"),
        "price_change_percentage_24h": md.get("price_change_percentage_24h"),
        "total_volume": total_volume,
    }


def fetch_markets():
    """Fetch tradable USDT market data with pagination + batched search fallback.

    Phase 1 — pagination: fetch CoinGecko /coins/markets pages 1-2 (500 coins).
    Phase 2 — gate: keep only symbols that trade as Binance USDT pairs.
    Phase 3 — batch fallback: for any Binance USDT pair still missing, resolve
    via CoinGecko /coins/list and batch-fetch price data via /simple/price
    (1-2 calls instead of 228 individual lookups).
    """
    # Phase 1: paginated CoinGecko market data
    page1 = _fetch_coingecko_page(page=1, per_page=250)
    page2 = _fetch_coingecko_page(page=2, per_page=250)

    # Merge, deduplicate by coin id (keep first occurrence = higher mcap)
    # Gracefully handle partial failures (a page might return non-list on 429)
    all_pages = []
    for p in (page1, page2):
        if isinstance(p, list):
            all_pages.extend(p)

    seen_ids = set()
    all_coins = []
    for coin in all_pages:
        cid = coin.get("id") if isinstance(coin, dict) else None
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            all_coins.append(coin)

    # Phase 2: TokoCrypto USDT gate
    tokocrypto_usdt = fetch_tokocrypto_usdt_pairs()

    if not tokocrypto_usdt:
        # Fallback to Binance if TokoCrypto API is unavailable
        try:
            req = Request("https://api.binance.com/api/v3/exchangeInfo", headers={"User-Agent": UA})
            with urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
            binance_usdt = set()
            for s in data.get("symbols", []):
                if isinstance(s, dict) and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                    binance_usdt.add((s.get("baseAsset") or "").upper())
            tokocrypto_usdt = binance_usdt
        except Exception:
            pass

    if not tokocrypto_usdt:
        return all_coins

    gated = []
    coin_symbols_found = set()
    for item in all_coins:
        if not isinstance(item, dict):
            continue
        sym = (item.get("symbol") or "").upper()
        if sym in tokocrypto_usdt:
            gated.append(item)
            coin_symbols_found.add(sym)

    # Phase 3: batch fallback via /simple/price (avoids N individual /coins/{id} calls)
    missing_symbols = tokocrypto_usdt - coin_symbols_found
    if missing_symbols:
        sym_to_id = _fetch_coingecko_coin_list()
        # Collect CoinGecko IDs for missing symbols
        missing_ids = []
        remaining_unresolved = []
        for sym in sorted(missing_symbols):
            cg_id = sym_to_id.get(sym)
            if cg_id:
                missing_ids.append(cg_id)
            else:
                remaining_unresolved.append(sym)

        # Batch-fetch via /simple/price in chunks of 150
        CHUNK = 150
        for i in range(0, len(missing_ids), CHUNK):
            chunk = missing_ids[i:i + CHUNK]
            simple_raw = _get_cg(
                "https://api.coingecko.com/api/v3/simple/price",
                {
                    "ids": ",".join(chunk),
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                },
            )
            if not isinstance(simple_raw, dict):
                continue
            # Build reverse-ID→symbol map for this chunk
            id_to_sym = {v: k for k, v in sym_to_id.items() if v in chunk}
            for cg_id, price_entry in simple_raw.items():
                sym = id_to_sym.get(cg_id)
                if not sym:
                    continue
                usd = price_entry.get("usd")
                if usd is None:
                    continue
                # /simple/price returns: usd, usd_market_cap, usd_24h_vol, usd_24h_change
                # No market_cap_change_percentage_24h here — conservative scoring.
                gated.append({
                    "id": cg_id,
                    "symbol": sym.lower(),
                    "name": sym.title(),  # best guess without /coins/{id}
                    "current_price": usd,
                    "market_cap": price_entry.get("usd_market_cap"),
                    "market_cap_change_percentage_24h": None,
                    "price_change_percentage_24h": price_entry.get("usd_24h_change"),
                    "total_volume": price_entry.get("usd_24h_vol"),
                })
        if remaining_unresolved:
            pass  # silently skip — no CoinGecko entry at all

    # Phase 4: TokoCrypto ticker enrichment (merge exchange-specific data)
    try:
        all_tickers = fetch_tokocrypto_tickers()
        ticker_map = build_tokocrypto_ticker_map(all_tickers)
        if ticker_map:
            for item in gated:
                sym = (item.get("symbol") or "").upper()
                tdata = ticker_map.get(sym)
                if tdata:
                    item.update(tdata)
    except Exception:
        pass  # enrichment is non-fatal — continue without TokoCrypto data

    return gated


def fetch_global():
    return _get_cg_global()


def fetch_fear_greed():
    data = _get("https://api.alternative.me/fng/?limit=1&format=json")
    return ((data.get("data") or [{}])[0]) if isinstance(data, dict) else data


def fetch_coincap(limit=120):
    data = _get("https://api.coincap.io/v2/assets", {"limit": limit})
    return (data.get("data") or data) if isinstance(data, dict) else data


def now_iso():
    return datetime.now(UTC).isoformat()


def run_query(term, limit=3, min_tier=None):
    if not os.path.exists(QUERY_PAPERS):
        return []
    try:
        cmd = ["python3", QUERY_PAPERS, term, "--limit", str(limit)]
        if min_tier:
            cmd += ["--min-tier", min_tier]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        return data.get("results", [])[:limit]
    except Exception:
        return []


def lookup_research(concept):
    """Read consolidated research-digest.md and match the concept against the
    Actionable Findings Index (finding + tags + tier), not just title words.

    Scoring:
      +1.0 match for exact primary-tag hit
      +0.6 match for secondary-tag hit
      +0.4 match for finding-mention hit (substring)
      +0.3 match for title keyword hit
      Tier A > B > C reward
    """
    if not os.path.exists(RESEARCH_DIGEST):
        return None
    try:
        with open(RESEARCH_DIGEST, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None

    words = [w.lower() for w in concept.split() if len(w) > 2]
    if not words:
        return None

    entries = []
    current_title = None
    current_tier = None
    current_src = None
    current_url = None
    current_tags = []
    current_finding = ""

    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("- 🟢") or s.startswith("- 🟡"):
            # Flush prior entry if any
            if current_title and current_finding and current_tags:
                entries.append({
                    "title": current_title,
                    "tier": current_tier or "B",
                    "src": current_src or "",
                    "url": current_url or "",
                    "tags": current_tags,
                    "finding": current_finding,
                })
            # Parse new entry
            m_title = re.search(r"\*\*(.+?)\*\*", s)
            current_title = m_title.group(1) if m_title else None
            current_tier = "A" if s.startswith("- 🟢") else ("B" if s.startswith("- 🟡") else "C")
            current_src = re.search(r"\(([^)]+)\)", s)
            current_src = current_src.group(1)[:25] if current_src else ""
            doi_m = re.search(r"doi:\S+", s)
            current_url = f" — {doi_m.group()}" if doi_m else ""
            current_tags = []
            current_finding = ""
        elif s.startswith("Tags: ") and current_title:
            tag_part = s[len("Tags: "):]
            te = re.search(r"^(.*?)\s*\|", tag_part)
            current_tags = [t.strip() for t in (te.group(1) if te else tag_part).split(",") if t.strip()]
        elif s.startswith("Finding: ") and current_title:
            current_finding = s[len("Finding: "):]

    # Flush final entry
    if current_title and current_finding and current_tags:
        entries.append({
            "title": current_title,
            "tier": current_tier or "B",
            "src": current_src or "",
            "url": current_url or "",
            "tags": current_tags,
            "finding": current_finding,
        })

    if not entries:
        return None

    def score_entry(e):
        tags = [t.lower() for t in (e.get("tags") or []) or []]
        finding = (e.get("finding") or "").lower()
        title = (e.get("title") or "").lower()
        rel_try = re.search(r"Relevance:\s*([\d.]+)", text, re.IGNORECASE)
        # Try to grab relevance from the entry block if it’s been added later
        score = 0.0

        # Tag match
        for w in words:
            if w in tags:
                score += 1.0 if tags.index(w) == 0 else 0.6
        # Finding mention
        if any(w in finding for w in words):
            score += 0.4
        # Title keyword (de-emphasised)
        if any(w in title for w in words):
            score += 0.3

        # Tier boost
        tier_boost = {"A": 0.3, "B": 0.15, "C": 0.0}
        score += tier_boost.get(e.get("tier", "C"), 0.0)

        return score

    ranked = sorted(entries, key=lambda e: (-score_entry(e), e.get("title", "")))
    best = ranked[0]

    # Return a richer result so the renderer can show a useful line
    tier = best.get("tier", "B")
    tier_label = {"A": "🟢 peer-reviewed", "B": "🟡 preprint", "C": "⭕ supplementary"}.get(tier, tier)
    finding = (best.get("finding") or best.get("title", "Research")).strip()
    finding_short = finding[:120] + ("…" if len(finding) > 120 else "")
    ref = f"{best.get('title', 'paper')} — {finding_short}"
    return {
        "title": best.get("title"),
        "ref": ref,
        "tier": tier,
        "tier_label": tier_label,
        "score": score_entry(best),
        "tags": best.get("tags", []),
        "finding": finding,
        "path": best.get("path", ""),
    }


def best_paper_for(term, fallback_terms):
    """Find research citation using the consolidated digest only (Actionable Findings Index)."""
    terms = [term] + fallback_terms

    for t in terms:
        hit = lookup_research(t)
        if hit and hit.get("score", 0) >= 0.7:
            return hit

    # Fallback: accept weaker match if nothing strong
    for t in terms:
        hit = lookup_research(t)
        if hit:
            return hit

    return None


def recommend_term(symbol, name):
    sym = (symbol or "").lower()
    n = (name or "").lower()
    terms = [n, sym]

    # Strategy-domain-inferred terms — route coin names to known tag patterns
    domain_hints = []
    if sym in {"btc", "bitcoin"}:
        domain_hints = ["bitcoin", "bitcoin prediction", "crypto trading", "prediction", "risk"]
    elif sym in {"eth", "ethereum"}:
        domain_hints = ["ethereum", "defi", "prediction", "crypto trading", "liquidity"]
    elif any(kw in f"{sym} {n}" for kw in ("defi", "lending", "borrow", "swap", "yield",
                                            "uni", "aave", "compound", "magma", "maple", "curve",
                                            "eigen", "restak", "pendle", "gmx", "perpetual",
                                            "synth", "maker", "spark", "morpho", "balancer")):
        domain_hints = ["defi", "liquidity", "prediction", "arbitrage", "crypto trading"]
    elif any(kw in f"{sym} {n}" for kw in ("btc", "bitcoin", "staking", "pos", "stake",
                                            "validator", "liquid", "lido")):
        domain_hints = ["bitcoin prediction", "prediction", "risk", "crypto trading"]
    else:
        # Generic crypto — try all major strategy tags
        domain_hints = ["crypto trading", "prediction", "momentum", "liquidity", "risk",
                        "sentiment", "arbitrage", "defi", "execution"]

    terms += domain_hints
    return terms


def research_line(papers):
    if not papers:
        return "Research: no matching paper in current corpus"
    top = papers[0]
    # Handle both digest format (ref + tier) and query_papers format (title + path)
    if top.get("ref"):
        tier = top.get("tier", "?")
        tier_label = {"A": "🟢 peer-reviewed", "B": "🟡 preprint", "C": "⭕ supplementary"}.get(tier, tier)
        return f"Research: [{tier_label}] {top['ref']}"
    title = top.get("title") or "local paper"
    path = top.get("path") or ""
    tier = top.get("tier") or "?"
    tier_label = {"A": "🟢 peer-reviewed", "B": "🟡 preprint", "C": "⭕ supplementary"}.get(tier, tier)
    return f"Research: [{tier_label}] \"{title}\" ({path})"


def _lazy_load_portfolio_engine():
    """Import portfolio_engine on first use — avoids circular import and CG calls at module load."""
    global PORTFOLIO_ENGINE
    if PORTFOLIO_ENGINE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("portfolio_engine", _PORTFOLIO_ENGINE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        PORTFOLIO_ENGINE = mod
    return PORTFOLIO_ENGINE


def _funding_score_adjustment() -> tuple:
    """Compute score adjustment from BTC derivatives data (funding rate + L/S ratio).

    Fetched once per briefing run via module-level cache.

    Returns:
        (adjustment_pts, reason_str)
        adjustment_pts: positive = boost scores (favorable), negative = penalize (risky)
        reason_str: human-readable label or empty string
    """
    d = _fetch_derivatives_once()
    if not d or d.get("funding_rate") is None:
        return 0.0, ""

    adj = 0.0
    parts = []

    # Funding rate adjustment
    signal = d.get("funding_signal", "neutral")
    if signal == "extreme positive":
        adj -= 18.0
        parts.append("funding extreme positive — squeeze risk")
    elif signal == "positive":
        adj -= 5.0
        parts.append("funding positive — leverage elevated")
    elif signal == "negative":
        adj += 3.0
        parts.append("funding negative — shorts paying")
    elif signal == "extreme negative":
        adj += 8.0
        parts.append("funding extreme negative — short squeeze setup")

    # Long/short ratio adjustment
    ls_sig = d.get("ls_signal", "")
    if ls_sig == "crowded long":
        adj -= 5.0
        parts.append("L/S crowded long")
    elif ls_sig == "crowded short":
        adj += 5.0
        parts.append("L/S crowded short")

    if not parts:
        return 0.0, ""

    return adj, "; ".join(parts)


def _regime_max_stop(fng_value: int = 50) -> float:
    """Return maximum stop loss percentage based on Fear & Greed regime.
    
    In Extreme Fear, tighten stops to limit downside. In Extreme Greed,
    also tighten (pump risk). In normal conditions, use the full 8% range.
    """
    if fng_value <= 15:
        return 5.0   # Extreme Fear: tight stops, capital preservation
    elif fng_value <= 35:
        return 6.0   # Fear: moderate tightening
    elif fng_value >= 85:
        return 6.0   # Extreme Greed: tight stops (pump risk)
    elif fng_value >= 65:
        return 8.0   # Greed: normal range
    return 8.0       # Neutral: normal range


def _btc_atr_status():
    """Fetch BTCUSDT 1h klines from TokoCrypto and compute ATR(14) trend.

    Returns dict: {'status': 'expanding'|'contracting'|'stable',
                   'current_atr': float, 'avg_atr': float, 'ratio': float}
    On failure returns {'status': 'unknown', 'current_atr': 0, 'avg_atr': 0, 'ratio': 1.0}
    """
    try:
        from free_data import fetch_tokocrypto_klines
        klines = fetch_tokocrypto_klines("BTCUSDT", interval="1h", limit=30)
        if not isinstance(klines, list) or len(klines) < 15:
            return {"status": "unknown", "current_atr": 0, "avg_atr": 0, "ratio": 1.0}
        # Parse OHLC from klines: [time, open, high, low, close, ...]
        candles = []
        for k in klines:
            try:
                high = float(k[2])
                low = float(k[3])
                close = float(k[4])
                candles.append((high, low, close))
            except (IndexError, ValueError, TypeError):
                continue
        if len(candles) < 15:
            return {"status": "unknown", "current_atr": 0, "avg_atr": 0, "ratio": 1.0}
        # Compute true ranges
        trs = []
        for i in range(1, len(candles)):
            h, l, c = candles[i]
            pc = candles[i-1][2]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        if len(trs) < 14:
            return {"status": "unknown", "current_atr": 0, "avg_atr": 0, "ratio": 1.0}
        # Simple SMA for ATR (instead of EMA — good enough for direction detection)
        atr_14 = sum(trs[-14:]) / 14.0
        atr_14_ago = sum(trs[-28:-14]) / 14.0 if len(trs) >= 28 else atr_14
        ratio = atr_14 / atr_14_ago if atr_14_ago > 0 else 1.0
        if ratio > 1.25:
            status = "expanding"
        elif ratio < 0.75:
            status = "contracting"
        else:
            status = "stable"
        return {"status": status, "current_atr": round(atr_14, 2),
                "avg_atr": round(atr_14_ago, 2), "ratio": round(ratio, 3)}
    except Exception:
        return {"status": "unknown", "current_atr": 0, "avg_atr": 0, "ratio": 1.0}


def _bottom_fishing_pipeline(markets, loss_penalties, recent_winners, regime_mult=0.75):
    """Mean-reversion pipeline for Extreme Fear (F&G ≤ 15).

    Uses wider stops (5%), smaller position signals, and volatility-premium scoring.
    Skips coins where ATR is expanding (falling-knife filter).
    Returns list of candidate dicts with same schema as simple_rules.
    """
    STABLECOINS = {"usdt", "usdc", "busd", "dai", "ust", "tusd", "pax", "gusd", "usdp",
                   "fdusd", "steth", "wsteth", "reth", "frax", "lusd", "susd", "usde", "usd0"}
    candidates = []

    # ── ATR volatility gate ─────────────────────────────────────────────
    # In Extreme Fear, expanding ATR means catching a falling knife.
    # Skip bottom-fishing entirely when vol is still accelerating.
    atr_info = _btc_atr_status()
    atr_blocked = atr_info.get("status") == "expanding"
    atr_note = f"ATR: {atr_info['status']} ({atr_info['ratio']:.2f}x)" if atr_info.get("status") != "unknown" else ""

    for c in markets:
        if not isinstance(c, dict):
            continue
        sym = (c.get("symbol") or "").lower()
        name = (c.get("name") or "").lower()
        if sym in STABLECOINS:
            continue
        if any(token in [sym, name] for token in ["usd", "usdc", "usdt", "dai", "tether", "stable"]):
            continue
        mcap = c.get("market_cap") or 0
        if mcap < 50e6:
            continue
        p = c.get("price_change_percentage_24h") or 0

        # Bottom-fishing: only consider coins with negative 24h change (dip buying)
        # TOK is spot-only — no shorting. Positive moves can't be faded.
        if p >= 0:
            continue

        # Only consider moves in the 3-20% range
        # Too small (< 3%) = noise. Too large (> 20%) = insane vol, don't catch
        if abs(p) < 3.0 or abs(p) > 20.0:
            continue

        # ── ATR gate per coin: if ATR is expanding, skip (falling knife) ──
        if atr_blocked:
            continue

        mc = c.get("market_cap_change_percentage_24h") or 0
        cv = c.get("total_volume") or 0
        sym_upper = sym.upper()

        # Loss penalty
        _loss_penalty = loss_penalties.get(sym_upper, 0) if loss_penalties else 0

        # Score: mean-reversion logic
        # In extreme fear, big drops = potential snap-back
        # Use absolute price change as base, but give bonus to *down* moves
        # (mean reversion plays the bounce, not the continuation)
        score = abs(p) * 0.8  # core: size of move

        # Down-move bonus: bigger drop = higher snap-back potential
        if p < 0:
            score *= 1.2  # 20% bonus for downside moves
        else:
            score *= 0.9  # discount up-moves (less likely to reverse in fear)

        # Market cap flow bonus: if mcap flowing in despite price down → smart money
        if p < 0 and mc > 2.0:
            score += mc * 0.15
        elif p > 0:
            score += max(0, mc) * 0.08

        # Vol-premium bonus: larger moves have higher snap-back probability
        vol_premium = min(1.3, abs(p) / 5.0)
        score *= vol_premium

        # Liquidity check via TokoCrypto volume
        toko_vol = c.get("tokocrypto_volume_quote") or 0
        bid = c.get("tokocrypto_bid")
        ask = c.get("tokocrypto_ask")
        if bid and ask and bid > 0 and ask > 0:
            spread_bps = (ask - bid) / bid * 10000
            if spread_bps < 5:
                score += 3.0
            elif spread_bps > 20:
                score -= 10.0
            elif spread_bps > 10:
                score -= 5.0
            if toko_vol > 1_000_000:
                score += 2.0
            elif toko_vol > 100_000:
                score += 0.5
        else:
            score -= 5.0

        # Volume bonus
        if toko_vol > 0:
            score += min(toko_vol / 10_000_000, 5.0)

        # Win momentum boost
        if recent_winners and sym_upper in recent_winners:
            score += 2.0

        # Loss penalty
        if _loss_penalty:
            score -= _loss_penalty * 0.5  # halved in bottom-fishing (more forgiving)

        # Trap filters (relaxed — bottom-fishing is inherently higher risk)
        # Skip only extreme traps
        vol_mcap_ratio = cv / mcap if mcap > 0 else 0
        if abs(p) > 8.0 and vol_mcap_ratio < 0.002:
            score -= 15.0  # suspected fake volume
        if p < -15.0:
            score -= 8.0   # steep drop penalty (but don't hard-block)
        if abs(p) > 25.0:
            score -= 10.0   # overextended

        if score < 20:
            continue

        candidates.append({
            "symbol": c.get("symbol"),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "mcap": mcap,
            "change_24h": p,
            "mcap_change_24h": mc,
            "volume": cv,
            "score": round(score, 3),
            "trap_flags": [],
            "_bottom_fishing": True,
            "_atr_note": atr_note,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:10]


def simple_rules(markets):
    candidates = []
    if not isinstance(markets, list):
        return candidates
    STABLECOINS = {"usdt", "usdc", "busd", "dai", "ust", "tusd", "pax", "gusd", "usdp", "fdusd", "steth", "wsteth", "reth", "frax", "lusd", "susd", "usde", "usd0"}
    
    # ── Loss penalty: penalize score based on recency/severity of past losses ─
    # Instead of hard-blocking, we subtract a penalty so the coin can still
    # qualify if it shows genuinely strong momentum that overcomes its history.
    _loss_penalties = {}
    try:
        if os.path.exists(_cl_path):
            _loss_penalties = _cl_mod.get_loss_penalties(days=14)
    except Exception:
        pass
    
    # ── Win momentum: load proven winners for score boost ──────────
    _recent_winners = set()
    try:
        if os.path.exists(_cl_path):  # reuse the same loaded module
            _recent_winners = _cl_mod.get_recent_winners(days=30)
    except Exception:
        pass
    
    # ── Market regime gating: adjust scoring by fear & greed ──────
    _regime_mult = 1.0
    try:
        _fng_r = fetch_fear_greed()
        _fng_val = int(_fng_r.get('value', 50))
        if _fng_val <= 15:
            # ── Bottom-fishing mode: switch to mean-reversion pipeline ──
            # In Extreme Fear, the normal trend-following pipeline is too
            # aggressive (tight stops get hit). Instead, use wider stops,
            # volatility-premium scoring, and skip if ATR is still expanding.
            _bf_results = _bottom_fishing_pipeline(
                markets, _loss_penalties, _recent_winners, regime_mult=0.75
            )
            return _bf_results
        elif _fng_val >= 85:
            return []  # Extreme Greed: skip all signals (pump risk)
        elif _fng_val <= 35:
            _regime_mult = 0.75  # Fear: need stronger evidence, penalize scores
        elif _fng_val >= 65:
            _regime_mult = 1.15  # Greed: momentum friendly, boost scores
    except Exception:
        return []  # Can't determine regime → conservative: block signals
    
    # ── Read adaptation target for small-cap tier ────────────────
    # The $\ge 100M mcap tier uses params.json's min_24h_change_pct so the
    # adaptation system can tighten/loosen it. Other tiers use fixed thresholds.
    _adapt_change = 3.0
    try:
        _ap = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "strategy", "params.json")
        if os.path.exists(_ap):
            import json as _aj
            with open(_ap) as _af:
                _ad = _aj.load(_af)
            _adapt_change = float(_ad.get("screening", {}).get("min_24h_change_pct", 3.0))
    except Exception:
        pass
    
    for c in markets:
        if not isinstance(c, dict):
            continue
        sym = (c.get("symbol") or "").lower()
        name = (c.get("name") or "").lower()
        if sym in STABLECOINS:
            continue
        if any(token in [sym, name] for token in ["usd", "usdc", "usdt", "dai", "tether", "stable"]):
            continue
        mcap = c.get("market_cap") or 0
        if mcap < 50e6:
            continue
        p = c.get("price_change_percentage_24h") or 0
        # ── Market-cap-scaled volatility gate ──────────────────────
        # Large caps need less movement to be meaningful than micro-caps.
        # This prevents the same volatile micro-caps from dominating every run
        # and opens up BTC, ETH, SOL as valid opportunities.
        if mcap >= 50_000_000_000:      # > $50B: BTC, ETH, SOL
            min_change = 0.5
        elif mcap >= 10_000_000_000:    # > $10B: major L1s (ADA, AVAX, DOT)
            min_change = 1.0
        elif mcap >= 1_000_000_000:     # > $1B: mid-caps
            min_change = 2.0
        elif mcap >= 100_000_000:       # > $100M: small-caps (uses adapt_change from params.json)
            min_change = _adapt_change
        else:                           # $50M-$100M: micro-caps need strong signal
            min_change = 4.0
        if abs(p) < min_change:
            continue
        # ── Loss penalty: compute penalty for past losses ─────────────
        sym_upper = sym.upper()
        _loss_penalty = _loss_penalties.get(sym_upper, 0) if _loss_penalties else 0
        mc = c.get("market_cap_change_percentage_24h") or 0
        
        # Core score: price momentum + cap flow alignment
        score = abs(p) + max(0, mc) * 0.08
        
        # Regime multiplier: fear/greed adjusts confidence needed
        score *= _regime_mult
        
        # Regime-adjusted scoring: route to sector-appropriate strategy
        regime_strat = _regime_bias(p)
        if regime_strat == "mean-reversion":
            if abs(p) > 4.0:
                vol_premium = min(1.5, abs(p) / 3.0)
                score *= vol_premium
        elif regime_strat == "momentum":
            if toko_vol > 1_000_000 and abs(p) < 5.0:
                score *= 1.2
            score += max(0, mcap / 1_000_000_000) * 0.5
        
        # TokoCrypto liquidity assessment
        bid = c.get("tokocrypto_bid")
        ask = c.get("tokocrypto_ask")
        toko_vol = c.get("tokocrypto_volume_quote") or 0
        
        # Volume bonus (capped): higher volume on TokoCrypto = more reliable signal
        vol_bonus = min(toko_vol / 10_000_000, 10.0)
        score += vol_bonus
        
        if bid and ask and bid > 0 and ask > 0:
            spread_bps = (ask - bid) / bid * 10000
            if spread_bps < 5:      # tight spread — high confidence
                score += 5.0
            elif spread_bps > 20:   # wide spread — liquidity concern
                score -= 10.0
            elif spread_bps > 10:
                score -= 5.0
            # Bonus for meaningful daily volume on exchange
            if toko_vol > 1_000_000:
                score += 3.0
            elif toko_vol > 100_000:
                score += 1.0
        else:
            # No TokoCrypto ticker data — unknown liquidity, significant penalty
            score -= 5.0
        
        # ── Win momentum boost: small bonus for proven winners ──────
        if _recent_winners and sym_upper in _recent_winners:
            score += 3.0
        
        # ── Loss penalty: subtract penalty for past losses (decays over 14 days)
        # A -8% loss yesterday costs ~16 points; after 7 days ~8 points; after 14 days 0.
        # Strong momentum can still overcome the penalty.
        if _loss_penalty:
            score -= _loss_penalty
        
        # ── Trading Trap Filters ──────────────────────────────────────────
        trap_flags = []
        
        # 1. Falling knife: steep drop with momentum against you
        if p < -12.0:
            trap_flags.append("falling_knife")
            score -= 15.0
        elif p < -8.0:
            trap_flags.append("slipping")
            score -= 8.0
        
        # 2. Pump suspicion: extreme pump on thin volume
        cv = c.get("total_volume") or 0
        if p > 18.0 and (toko_vol < 100_000 or cv < 2_000_000):
            trap_flags.append("thin_pump")
            score -= 15.0
        elif p > 12.0 and toko_vol < 50_000:
            trap_flags.append("low_vol_pump")
            score -= 10.0
        
        # 3. Volume/price mismatch: big move but tiny volume = manipulation risk
        if abs(p) > 15.0 and cv < 1_000_000:
            trap_flags.append("manipulation_risk")
            score -= 12.0
        
        # 4. Mcap not confirming: price moves but mcap doesn't follow
        if abs(p) > 10.0 and abs(mc) < 2.0:
            trap_flags.append("mcap_divergence")
            score -= 8.0
        
        # 5. Over-extended: extreme move in either direction is risky
        if abs(p) > 25.0:
            trap_flags.append("overextended")
            score -= 10.0
        
        # 6. Volume/mcap quality: big move on suspiciously thin or bloated volume
        vol_mcap_ratio = cv / mcap if mcap > 0 else 0
        if abs(p) > 8.0 and vol_mcap_ratio < 0.005:
            # Price moved >8% on volume <0.5% of market cap — classic manipulation
            trap_flags.append("fake_volume")
            score -= 18.0
        elif abs(p) > 5.0 and vol_mcap_ratio < 0.002:
            trap_flags.append("fake_volume")
            score -= 18.0
        elif vol_mcap_ratio > 2.0:
            # Volume >200% of market cap in 24h — wash trading or panic
            trap_flags.append("abnormal_volume")
            score -= 8.0
        
        if score < 25:
            continue
        candidates.append(
            {
                "symbol": c.get("symbol"),
                "name": c.get("name"),
                "price": c.get("current_price"),
                "mcap": mcap,
                "change_24h": p,
                "mcap_change_24h": mc,
                "volume": c.get("total_volume"),
                "score": round(score, 3),
                "trap_flags": trap_flags,
            }
        )
    # Portfolio-level adjustment: apply drawdown/exposure/correlation penalty
    if candidates:
        try:
            pe = _lazy_load_portfolio_engine()
            cal_notes = pe._load_calibrations().get("portfolio", {})
            if cal_notes:
                portfolio_note = f"concurrency={len(pe.load_portfolio().get('positions', {}))}/{cal_notes.get('concurrency_max', 3)}"
            else:
                portfolio_note = ""
        except Exception:
            portfolio_note = ""
        # Fetch funding adjustment once for all candidates
        funding_adj, funding_reason = _funding_score_adjustment()
        for c in candidates:
            try:
                pe = _lazy_load_portfolio_engine()
                mult, reasons = pe.portfolio_penalty(c.get("symbol", ""), c["score"])
                c["score"] = round(c["score"] * mult, 3)
                c["portfolio_note"] = "; ".join(reasons)
            except Exception:
                c["portfolio_note"] = "portfolio engine error"
            # Apply funding-based adjustment
            if funding_adj != 0:
                c["score"] = round(c["score"] + funding_adj, 3)
                c["funding_note"] = funding_reason
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:15]


def _enrich_top_with_depth(candidates, limit=3):
    """Fetch TokoCrypto orderbook depth for top N candidates.
    
    Mutates candidates in-place, adding 'tokocrypto_depth' key with spread/depth metrics.
    Non-fatal — if depth fetch fails, candidate is unchanged.
    """
    if not candidates:
        return
    for c in candidates[:limit]:
        sym = (c.get("symbol") or "").upper()
        if not sym:
            continue
        try:
            depth = fetch_tokocrypto_depth(f"{sym}USDT", limit=20)
            metrics = compute_tokocrypto_depth_metrics(depth)
            if metrics:
                c["tokocrypto_depth"] = metrics
        except Exception:
            pass


def _format_depth_line(c):
    """Format a single liquidity line from candidate depth data.
    
    Returns string like '$12.3K depth · 3.2 bps spread' or empty string.
    """
    d = c.get("tokocrypto_depth")
    if not d:
        # Fall back to ticker-level bid/ask for basic spread
        bid = c.get("tokocrypto_bid")
        ask = c.get("tokocrypto_ask")
        if bid and ask and bid > 0 and ask > 0:
            spread = round((ask - bid) / bid * 10000, 2)
            vol = c.get("tokocrypto_volume_quote", 0)
            vol_str = f" ${vol:,.0f} vol" if vol else ""
            return f"TokoCrypto spread: {spread} bps{vol_str}"
        return "Liquidity: TokoCrypto — no depth data"
    spread = d.get("spread_bps", "?")
    total_depth = d.get("total_depth_usd", 0)
    if total_depth >= 1_000_000:
        depth_str = f"${total_depth/1e6:.1f}M"
    elif total_depth >= 1_000:
        depth_str = f"${total_depth/1e3:.0f}K"
    else:
        depth_str = f"${total_depth:.0f}"
    base = f"TokoCrypto · {depth_str} depth · {spread} bps spread"
    # Execution quality annotation from research calibrations
    try:
        cal = _load_calibrations().get("execution", {})
        baseline = cal.get("expected_baseline_spread_bps", 5.0)
        sigma = cal.get("anomaly_threshold_sigma", 2.0)
        if isinstance(spread, (int, float)) and spread > 0:
            ratio = spread / baseline
            if ratio > sigma * 1.5:
                base += f" · ⚠️ {ratio:.1f}x median — execution risk"
            elif ratio > sigma:
                base += f" · elevated ({ratio:.1f}x median)"
            elif ratio < 0.5:
                base += f" · tight (vs {baseline:.0f}bps median)"
            else:
                base += f" · normal (median {baseline:.0f}bps)"
        return base
    except Exception:
        return base


_TRAP_LABELS = {
    "falling_knife": "⚠️ falling knife",
    "slipping": "⚠️ slipping",
    "thin_pump": "⚠️ thin pump",
    "low_vol_pump": "⚠️ low-vol pump",
    "manipulation_risk": "⚠️ manipulation risk",
    "mcap_divergence": "⚠️ mcap divergence",
    "overextended": "⚠️ overextended",
    "fake_volume": "⚠️ fake volume",
    "abnormal_volume": "⚠️ abnormal volume",
}


def _format_trap_line(c):
    """Format trap flags as a human-readable line, e.g. '⚠️ falling knife · ⚠️ low volume'.
    Returns empty string if no traps flagged.
    """
    flags = c.get("trap_flags", [])
    if not flags:
        return ""
    labels = []
    for f in flags:
        lbl = _TRAP_LABELS.get(f, f"⚠️ {f}")
        labels.append(lbl)
    return " · ".join(labels)


def section(title):
    return f"## {title}\n"


def visual_dom_bar(pct, width=8):
    try:
        p = float(pct)
        p = max(0.0, min(100.0, p))
        filled = int(round(width * (p / 100.0)))
    except Exception:
        filled = 0
    return "█" * filled + "░" * (width - filled)


def _funnel_summary(markets, top=None, score_threshold=25.0, pick_symbol=None) -> list[str]:
    """Count screening funnel stages from raw markets list.

    Returns lines like ["📈 2478 coins scanned → 424 ≥ $50M mcap → 12 ≥ 3% move → 2 scored ≥ 25 (threshold)",
    "🎯 Near-miss: XRP 23.8 (-1.2 vs threshold) | DOGE 22.1 (-2.9)"].
    Returns [] if markets is empty.
    """
    if not isinstance(markets, list) or not markets:
        return []

    total_coins = len(markets)
    STABLECOINS = {"usdt", "usdc", "busd", "dai", "ust", "tusd", "pax",
                   "gusd", "usdp", "fdusd", "steth", "wsteth", "reth",
                   "frax", "lusd", "susd", "usde", "usd0"}

    passed_mcap = 0
    passed_move = 0
    scored_candidates = []  # (sym, score) for threshold distance

    for c in markets:
        sym = (c.get("symbol") or "").lower()
        name = (c.get("name") or "").lower()
        if sym in STABLECOINS:
            continue
        if sym in ("usd", "usdc", "usdt") or "stable" in name:
            continue
        mcap = c.get("market_cap") or 0
        if mcap < 50e6:
            continue
        passed_mcap += 1
        p = c.get("price_change_percentage_24h") or 0
        if abs(p) >= 3.0:
            passed_move += 1

    # Build scored candidates using the same logic as simple_rules (but lighter)
    # We'll reuse simple_rules if top is provided, otherwise compute lightweight scores
    near_misses = []
    if top is not None:
        # top already has scored candidates from simple_rules
        for c in top:
            score = c.get("score", 0)
            if score < score_threshold:
                # Skip if this symbol is the primary pick (avoid same-ticker collisions)
                _hsym = (c.get("symbol") or "").lower()
                if pick_symbol and _hsym == pick_symbol.lower():
                    continue
                near_misses.append((c.get("symbol", "?"), score))
        near_misses.sort(key=lambda x: x[1], reverse=True)

    lines = [
        f"📈 {total_coins} coins scanned → {passed_mcap} ≥ $50M mcap → {passed_move} ≥ 3% move",
    ]
    if near_misses:
        miss_str = " · ".join(f"{sym} {score:.1f} ({score - score_threshold:+.1f} vs threshold {score_threshold:.0f})" for sym, score in near_misses[:3])
        lines.append(f"\U0001f3af Near-miss: {miss_str}")

    return lines


def _news_compact_block() -> list[str]:
    """Fetch market news and return compact block lines.

    Returns [] if news fetch fails.
    """
    try:
        # Try sibling import first, then file-based import as fallback
        try:
            from scripts import market_news as _mn
        except ImportError:
            import importlib.util as _iu
            _mn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "scripts", "market_news.py")
            if os.path.exists(_mn_path):
                _spec = _iu.spec_from_file_location("_mn", _mn_path)
                _mn = _iu.module_from_spec(_spec)
                _spec.loader.exec_module(_mn)
            else:
                return []
        news = _mn.fetch_market_news(limit=4, prefer_fallback=False)
        if not news:
            return []
        bullish = sum(1 for n in news if n.get("sentiment") == "bullish")
        bearish = sum(1 for n in news if n.get("sentiment") == "bearish")
        neutral_cnt = len(news) - bullish - bearish
        lines = [
            "━━━",
            "## 📰 Market News",
            f"- Sentiment: 🟢{bullish} / 🔴{bearish} / ⚪{neutral_cnt}",
        ]
        for n in news:
            icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(
                n.get("sentiment", "neutral"), "⚪")
            lines.append(f"- {icon} {n['headline'][:100].strip()}")
        return lines
    except Exception:
        return []


def _compact_regime_block(fng_val=None):
    """Compact regime context from free no-registration sources.
    
    Args:
        fng_val: Optional Fear & Greed value. When <20, DeFi TVL leader is
                 skipped (noise in extreme fear) but stablecoin flows and
                 yields are kept (risk-off corroboration).
    """
    rows = []
    try:
        rows.append("## Regime (enhanced)")
        protos = fetch_defillama_protocols(limit=8)
        if protos:
            top = protos[0]
            # DeFi TVL is noise in Extreme Fear — capital is rotating to cash
            _skiptvl = False
            if fng_val is not None:
                try:
                    _skiptvl = int(fng_val) < 20
                except (ValueError, TypeError):
                    pass
            if not _skiptvl:
                rows.append(f"- DeFi top TVL: {top.get('name')} ({top.get('category')}) TVL ${round((top.get('tvl') or 0)/1e9,2)}B")
        pools = fetch_defillama_yields(limit=8)
        stable_pools = [p for p in pools if p.get("stablecoin")]
        if stable_pools:
            apys = [float(p.get("apy") or 0) for p in stable_pools[:3] if isinstance(p.get("apy"), (int, float))]
            if apys:
                rows.append(f"- Avg stablecoin pool APY: {round(sum(apys)/len(apys),2)}%")
        flows = fetch_stablecoin_net_flows(limit=5)
        nonnull = [f for f in flows if f.get("daily_delta_pct") is not None]
        if nonnull:
            best = max(nonnull, key=lambda f: f.get("daily_delta_pct") or 0)
            worst = min(nonnull, key=lambda f: f.get("daily_delta_pct") or 0)
            rows.append(f"- Stablecoin flows +top: {best.get('symbol')} {round(best.get('daily_delta_pct') or 0,2)}% / worst: {worst.get('symbol')} {round(worst.get('daily_delta_pct') or 0,2)}%")
        dex = fetch_dex_screener_search("bitcoin", 5)
        active = [d for d in dex if ((d.get("txns_h1") or {}).get("buys") or 0) + ((d.get("txns_h1") or {}).get("sells") or 0) > 0]
        if active:
            rows.append(f"- Active DEX BTC pairs: {len(active)}")
    except Exception as e:
        rows.append(f"- Regime data unavailable: {e.__class__.__name__}")
    return "\n".join(rows)


def _regime_bias(change_24h: float) -> str:
    """Determine strategy bias from volatility regime using research-calibrated thresholds.
    
    Returns "momentum" (low-vol trend-following), "mean-reversion" (high-vol snap-back),
    "momentum" (neutral), or "indeterminate" when data is missing/zero.
    
    Enhanced with DuckDB journal analysis for empirical regime performance.
    """
    # Guard: missing or zero volatility → indeterminate (not momentum)
    if change_24h is None or change_24h == 0.0:
        return "indeterminate"
    cal = _load_calibrations().get("regime", {})
    vol = abs(change_24h)
    high = cal.get("high_vol_threshold", 0.03) * 100.0
    low = cal.get("low_vol_threshold", 0.015) * 100.0
    
    # Base regime from thresholds
    if vol >= high:
        base_regime = cal.get("high_vol_bias", "mean-reversion")
    elif vol <= low:
        base_regime = cal.get("low_vol_bias", "momentum")
    else:
        base_regime = cal.get("neutral_bias", "momentum")
    
    # Optional: Enhance with empirical journal performance by regime
    try:
        from free_data import get_regime_performance
        regime_perf = get_regime_performance(days=30, exclude_sources=['signal_validator'])
        if regime_perf and isinstance(regime_perf, list) and len(regime_perf) > 0:
            # Find best performing regime
            best_regime = max(regime_perf, key=lambda x: x.get("avg_pnl_pct", -999))
            if best_regime.get("avg_pnl_pct", -999) > 0 and best_regime.get("trades", 0) >= 3:
                # Override if empirical data strongly supports different regime
                empirical_regime = best_regime.get("regime", "").lower()
                if empirical_regime in ["mean-reversion", "momentum", "trend"]:
                    return empirical_regime
    except Exception:
        pass  # Silently fallback to threshold-based regime
    
    return base_regime


def _liquidity_multiplier(c: dict) -> float:
    """Compute position-size multiplier from TokoCrypto depth/spread data.

    Returns 0.5-1.0 multiplier based on research-calibrated liquidity thresholds.
    1.0 = ideal liquidity (no penalty), 0.5 = max penalty (thin market).
    """
    cal = _load_calibrations().get("liquidity", {})
    ideal = cal.get("spread_ideal_bps", 3.0)
    threshold = cal.get("spread_threshold_bps", 10.0)
    max_penalty = cal.get("max_size_penalty", 0.5)
    min_depth = cal.get("depth_confidence_min_usd", 50000.0)
    depth_max_penalty = cal.get("depth_penalty_max", 0.20)

    d = c.get("tokocrypto_depth", {})
    spread = (d or {}).get("spread_bps") or c.get("tokocrypto_spread_bps")
    depth = (d or {}).get("depth_within_1pct") or (d or {}).get("total_depth_usd") or c.get("tokocrypto_depth_usd", 0)

    if spread is None or spread == 0:
        return 1.0  # no liquidity data = no adjustment

    # Spread penalty: 0 at ideal, max_penalty at (or beyond) threshold
    spread_range = threshold - ideal
    excess = max(0.0, spread - ideal)
    spread_penalty = min(max_penalty, excess / spread_range * max_penalty) if spread_range > 0 else 0.0
    # Depth penalty: linear below confidence threshold
    depth_penalty = 0.0
    if depth and depth < min_depth:
        depth_penalty = depth_max_penalty * (1.0 - depth / min_depth)

    multiplier = 1.0 - spread_penalty - depth_penalty
    return round(max(0.5, min(1.0, multiplier)), 2)


def risk_icon(mood, fng_val=None):
    m = (mood or "").lower()
    if "fear" in m or "fear" in (mood or ""):
        if fng_val is not None:
            try:
                if int(fng_val) < 20:
                    return "😱"
                return "😟"
            except Exception:
                pass
        return "😟"
    if "greed" in m:
        return "🤑"
    return "😐"


def confidence_bar(label="medium", width=12):
    mapping = {"high": 0.85, "medium": 0.55, "low": 0.25}
    frac = mapping.get((label or "").lower(), 0.0)
    filled = int(round(width * frac))
    return "█" * filled + "░" * (width - filled)


def _safe_btc_dom(global_data):
    dom = None
    if isinstance(global_data, dict):
        inner = global_data.get("data") or {}
        mc = inner.get("market_cap_percentage") if isinstance(inner, dict) else None
        if isinstance(mc, dict):
            dom = mc.get("btc")
    return round(dom, 2) if dom is not None else "n/a"


def _btc_dom_from_markets(markets):
    """Fallback: compute BTC dominance from paginated CoinGecko markets data.
    
    BTC mcap should be in the first page (top 250 coins). Total mcap of the
    full list is used as denominator. Returns float or None.
    """
    if not isinstance(markets, list) or len(markets) < 2:
        return None
    btc_mcap = None
    total_mcap = 0.0
    for c in markets:
        if not isinstance(c, dict):
            continue
        mcap = c.get("market_cap") or 0
        total_mcap += mcap
        sym = (c.get("symbol") or "").lower()
        if sym == "btc":
            btc_mcap = mcap
    if btc_mcap and total_mcap > 0:
        return round(btc_mcap / total_mcap * 100, 2)
    return None


def _safe_fng_value_classification(fng):
    if isinstance(fng, dict):
        val = fng.get("value_classification")
        if val:
            return val
    return "n/a"


def _thresh_from_calibrations() -> float:
    """Read score_threshold from calibrations or params.json fallback."""
    try:
        cal = _load_calibrations()
        s = cal.get("screening", {})
        if s.get("score_threshold"):
            return float(s["score_threshold"])
    except Exception:
        pass
    # Fallback: read from strategy/params.json
    try:
        _p = os.path.join(SKILL_DIR, "strategy", "params.json")
        if os.path.exists(_p):
            with open(_p) as f:
                _pj = json.load(f)
            return float(_pj.get("screening", {}).get("score_threshold", 25.0))
    except Exception:
        pass
    return 25.0


def _safe_price(c):
    p = c.get("current_price")
    return float(p) if isinstance(p, (int, float)) and p > 0 else None


def _usdt_pairs():
    """Return set of TRADING USDT base assets on TokoCrypto.
    
    Fallback: attempts Binance if TokoCrypto API is unreachable.
    """
    tokopairs = fetch_tokocrypto_usdt_pairs()
    if tokopairs:
        return tokopairs
    # Fallback to Binance
    UA_local = "crypto-trading-advisor/0.1 (+https://example.com)"
    try:
        req = Request("https://api.binance.com/api/v3/exchangeInfo", headers={"User-Agent": UA_local})
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        symbols = set()
        for s in data.get("symbols", []):
            if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                symbols.add((s.get("baseAsset") or "").upper())
        return symbols
    except Exception:
        return set()


def render_briefing(markets, global_data, fng, assets, compact=False, visuals=False, enhanced=False, orchestrator=False):
    if compact:
        return render_compact_briefing(markets, global_data, fng, assets, visuals=visuals, enhanced=enhanced, orchestrator=orchestrator)
    dt = now_iso()
    top = simple_rules(markets) or []
    # Fetch TokoCrypto depth for top candidates
    _enrich_top_with_depth(top, limit=5)
    text = []
    text.append("## Daily Trading Briefing")
    text.append(f"- generated: {dt}")
    text.append("- profile: balanced swing/day spot")
    text.append("- pairs gated by TokoCrypto USDT availability")
    text.append("- sources: CoinGecko (prices/mcap), TokoCrypto (depth/spread), sentiment, defi sector, dex activity, stablecoin flows")
    text.append("")
    text += [
        section("Risk Disclosure"),
        "This is not financial advice. Spot crypto can be highly volatile; preserve capital first. Blindly copying a signal has negative expected value.",
        "",
        section("Macro Snapshot"),
        "Used generically because macro calls are extremely sensitive to current events; the best analysis must be combined with fresh news.",
        "- Trust but verify macro regime using fear&greed, equities, and Bitcoin dominance.",
        "",
        section("Sentiment"),
        f"- Fear & Greed: {fng.get('value')} ({fng.get('value_classification')})" if isinstance(fng, dict) and fng.get("value") else "",
        "",
        section("Alpha Candidates"),
    ]
    if not top:
        text.append("No high-intensity candidates found in tonight's market scan under current rules.")
    else:
        # Extract dynamic target/stop logic from compact briefing to stay in sync
        for i, c in enumerate(top, 1):
            direction = "bullish" if c.get("change_24h", 0) > 0 else "bearish"
            strategy = _regime_bias(c.get("change_24h", 0))
            bias = f"{strategy} - {direction}" if strategy != "momentum" else direction
            entry = c.get("price", 0)
            vol = abs(c.get("change_24h", 0) or 0)
            score = c.get("score", 25)
            base_target = 8.0; base_stop = 3.5
            vol_factor = max(0.5, vol / 3.0)
            score_rr = max(0.8, min(1.5, (score - 15) / 20))
            adj_target_pct = min(15.0, max(5.0, base_target * vol_factor * score_rr))
            _rms = _regime_max_stop(int(fng.get('value', 50)) if isinstance(fng, dict) else 50)
            adj_stop_pct = min(_rms, max(2.0, base_stop * (vol_factor ** 0.5) - max(0, (score - 25) * 0.03)))
            # Store on coin so Watch Levels and other sections reuse this (single source of truth)
            c["_computed_target_pct"] = adj_target_pct
            c["_computed_stop_pct"] = adj_stop_pct
            if direction == "bearish":
                target_price = round(entry * (1 - adj_target_pct / 100), 6)
                stop_price = round(entry * (1 + adj_stop_pct / 100), 6)
                target_label = f"{target_price} (-{adj_target_pct:.0f}%)"
                stop_label = f"{stop_price} (+{adj_stop_pct:.1f}%)"
            else:
                target_price = round(entry * (1 + adj_target_pct / 100), 6)
                stop_price = round(entry * (1 - adj_stop_pct / 100), 6)
                target_label = f"{target_price} (+{adj_target_pct:.0f}%)"
                stop_label = f"{stop_price} (-{adj_stop_pct:.1f}%)"
            # Thesis
            if strategy == "mean-reversion":
                thesis = f"{round(c.get('change_24h', 0),2)}% move; high-vol regime — targeting snap-back with tight stop"
            elif strategy == "momentum":
                thesis = f"{round(c.get('change_24h', 0),2)}% move; trending — momentum + cap flow aligned"
            else:
                thesis = f"{round(c.get('change_24h', 0),2)}% move; momentum + cap flow aligned"
            depth_line = _format_depth_line(c)
            trap_line = _format_trap_line(c)
            text.append(f"{i}. {c['name']} ({c['symbol']})")
            text.append(f"- Bias: {bias}")
            text.append(f"- Why: {thesis}")
            text.append(f"- Entry: near {entry:.6f}")
            text.append(f"- Stop: {stop_label}")
            text.append(f"- Target: {target_label}")
            text.append(f"- {depth_line}")
            if trap_line:
                text.append(f"- {trap_line}")
        text.append("")
        text.append("Use these as brainstorming targets, not trade tickets.")
    text += [
        "",
        section("Next Daily Briefing Checklist"),
        "- Re-run the scanner and freeze alpha candidates by 09:15 local time.",
        "- Verify 4h/1h trend and stop alignment on TokoCrypto.",
        "- Check TokoCrypto orderbook depth for opportunity coins.",
    ]
    return "\n".join(text)


def render_compact_briefing(markets, global_data, fng, assets, visuals=False, enhanced=False, orchestrator=False):
    dt = now_iso().split("T")[0]
    top = simple_rules(markets) or []
    # Fetch TokoCrypto depth for top 2 candidates (the ones shown in compact briefing)
    _enrich_top_with_depth(top, limit=2)
    sources_healthy = bool(markets)
    opps = (top or [])[:2]
    btc_dom = _safe_btc_dom(global_data)
    if btc_dom == "n/a":
        btc_dom = _btc_dom_from_markets(markets) or "n/a"
    fng_str = _safe_fng_value_classification(fng)
    fng_val = fng.get("value") if isinstance(fng, dict) else None
    pulse = "🟢 risk-on" if fng_val is not None and str(fng_val) not in ("n/a", "None", "") and int(fng_val) > 45 else "🔴 risk-off"
    dom_bar = visual_dom_bar(btc_dom) if visuals and btc_dom != "n/a" else ""
    risk = risk_icon(fng_str, fng_val)
    # ── Halt detection ───────────────────────────────────────────────
    # simple_rules() blocks all signals in Extreme Fear (≤15) and Extreme Greed (≥85).
    # When halted, skip verbose market data and show only halt notice + re-entry guidance.
    _halted = False
    if fng_val is not None:
        try:
            _fng_int_check = int(fng_val)
            if _fng_int_check >= 85:
                _halted = True
        except (ValueError, TypeError):
            pass
    txt = []
    txt.append("# 📊 Daily Crypto Briefing")
    # ── Unique run ID (date + HHMM, e.g. 20260701-1802) for audit trail ──
    try:
        _run_ts = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    except Exception:
        _run_ts = "unknown"
    txt.append(f"- ID: {_run_ts}")
    txt.append(f"- Date: {dt}")
    txt.append("- Style: balanced swing/day spot")
    txt.append("- Exchange: TokoCrypto (pairs gated by USDT availability)")

    # ── At-a-glance summary bar ────────────────────────────────────────────
    try:
        _fng_int = int(fng_val) if fng_val is not None and str(fng_val) not in ("n/a", "None", "") else None
    except (ValueError, TypeError):
        _fng_int = None
    _fee_summary = "-"
    try:
        from free_data import fetch_mempool_stats
        _fee = fetch_mempool_stats()
        if _fee.get("fees_ok"):
            _fee_summary = _fee.get("summary", "-")
    except Exception:
        pass
    _picks = len(opps)
    # Dominant strategy mode from picks
    _strategy_icon = ""
    if opps:
        _strategies = [_regime_bias(c.get("change_24h", 0)) for c in opps]
        _mode = max(set(_strategies), key=_strategies.count) if _strategies else ""
        if _mode == "mean-reversion":
            _strategy_icon = "🔁 mean-rev"
        elif _mode == "momentum":
            _strategy_icon = "📈 momentum"
    _pulse_icon = "🟢" if pulse == "🟢 risk-on" else "🔴" if pulse == "🔴 risk-off" else pulse
    _summary_parts = [
        f"F&G: {_fng_int} ({fng_str})" if _fng_int is not None else "F&G: n/a",
        f"BTC: {btc_dom}%",
        f"Pulse: {_pulse_icon}",
        f"Fees: {_fee_summary}",
        f"{_picks} pick{'s' if _picks != 1 else ''}" if _picks else "No picks",
    ]
    if _strategy_icon:
        _summary_parts.append(_strategy_icon)
    txt.append(f"━ {' · '.join(_summary_parts)}")

    # ── Separator ──────────────────────────────────────────────────────────
    txt.append("")
    txt += [
        "━━━",
        "## ⚠️ Risk",
        "Not financial advice. This is a checklist, not a green light. Preserve capital first.",
        "",
        "━━━",
        "## 📊 Market Regime",
        f"- BTC dominance: {btc_dom}% {dom_bar}" if btc_dom != "n/a" else "- BTC dominance: n/a",
        f"- Risk icon: {risk} - {fng_str}",
        f"- Market pulse: {pulse}",
        f"- Market cap shift: strongest stream above {round(top[0]['mcap_change_24h'], 1)}%" if top else "- Market cap shift: no high-intensity candidates filtered",
    ]
    # Regime bias (mean-reversion vs momentum) from volatility thresholds
    try:
        # Use BTC's 24h change for regime when no picks, or top pick's vol
        _regime_source = top[0] if top else next((c for c in markets if (c.get("symbol") or "").lower() == "btc"), None)
        if _regime_source:
            _regime = _regime_bias(_regime_source.get("change_24h", 0))
            _vol = abs(_regime_source.get("change_24h", 0) or 0)
            _cal = _load_calibrations().get("regime", {})
            _hv = _cal.get("high_vol_threshold", 0.03) * 100
            _lv = _cal.get("low_vol_threshold", 0.015) * 100
            if _regime == "indeterminate":
                txt.append("- Regime: Indeterminate (24h vol data unavailable for BTC)")
            else:
                txt.append(f"- Regime bias: {_regime} (24h vol {_vol:.1f}% vs thresholds: >{_hv:.0f}% mean-rev / <{_lv:.0f}% momentum)")
    except Exception:
        pass
    # Derivatives data (funding rate, OI, long/short ratio) — verbose, skip when halted
    if not _halted:
        try:
            _d = _fetch_derivatives_once()
            if _d.get("funding_rate") is not None:
                _fi = _d.get("funding_icon", "⚪")
                _fs = _d.get("funding_signal", "unknown")
                _ann = _d.get("annualized_pct", 0)
                txt.append(f"- BTC funding: {_fi} {_fs} ({_ann:.0f}% annualized)")
            if _d.get("oi_btc"):
                _oi = _d["oi_btc"]
                _oi_usd = _d.get("oi_usd", 0)
                _oi_str = f"${_oi_usd:,.0f}" if _oi_usd else f"{_oi:,.0f} BTC"
                txt.append(f"- BTC OI: {_oi_str}")
            if _d.get("ls_ratio"):
                _ls = _d["ls_ratio"]
                _ls_sig = _d.get("ls_signal", "?")
                txt.append(f"- Long/short: {_ls:.2f}x ({_ls_sig})")
                # Divergence note: sentiment vs positioning
                if _fng_int is not None and _fng_int < 20 and _d.get("ls_ratio") and _d["ls_ratio"] > 1.2:
                    txt.append("  \u26a1 Note: sentiment extreme fear but positioning not capitulated (L/S {:.2f}x long) \u2014 divergence suggests caution on sentiment-driven calls".format(_d["ls_ratio"]))
        except Exception:
            pass
        # On-chain data — BTC mempool fee estimates
        try:
            from free_data import fetch_mempool_stats
            _fee = fetch_mempool_stats()
            if _fee.get("fees_ok"):
                _fi = _fee.get("icon", "🟢")
                _fs = _fee.get("summary", "unknown")
                _ff = _fee.get("fastest", "?")
                _hf = _fee.get("hour", "?")
                txt.append(f"- BTC fees: {_fi} {_fs} (fast={_ff}, hour={_hf} sat/vB)")
        except Exception:
            pass
    if not sources_healthy:
        txt.append("⚠️ CoinGecko market data unavailable — opportunities reflect stale or incomplete data. Verify BTC price manually.")
    txt.append("")
    # Macro context banner in extreme conditions
    if fng_val is not None:
        try:
            fng_int = int(fng_val)
            if fng_int < 20:
                txt.append("⚠️ **Macro risk**: Extreme Fear — even quality signals carry elevated macro risk. Size down, tighten stops.")
            elif fng_int < 30:
                txt.append("⚡ **Macro note**: Fear — conservatism warranted. Prefer high-conviction setups only.")
        except (ValueError, TypeError):
            pass
    # Screening funnel — how many coins passed each stage
    funnel_lines = _funnel_summary(markets, top=opps, score_threshold=_thresh_from_calibrations(), pick_symbol=opps[0].get("symbol", "") if opps else None)
    if funnel_lines:
        txt.extend(funnel_lines)
        txt.append("")
    # Performance metrics — VaR, Expectancy, Win/Loss breakdown
    if not _halted:
        try:
            from signal_validator import summarize_with_empyrical
            import json
            _perf_path = os.path.join(SKILL_DIR, "reports", "signal_performance.json")
            if os.path.exists(_perf_path):
                with open(_perf_path, encoding="utf-8") as _pf:
                    _perf_data = json.load(_pf)
                _validated = [s for s in _perf_data.get("signals", []) if s.get("validation_status") == "backtested" and s.get("pnl_pct") is not None]
                if _validated:
                    _perf = summarize_with_empyrical(_validated)
                    if _perf.get("empyrical_available") and _perf.get("empyrical_metrics"):
                        _em = _perf["empyrical_metrics"]
                        _var95 = _em.get("var_95")
                        _cvar95 = _em.get("cvar_95")
                        _avg_win = _perf.get("avg_win_pct")
                        _avg_loss = _perf.get("avg_loss_pct")
                        _wr = _perf.get("win_rate")  # percentage (e.g., 40.0)
                        _expectancy = None
                        if _wr is not None and _avg_win is not None and _avg_loss is not None:
                            _expectancy = (_wr / 100.0 * _avg_win) + ((1 - _wr / 100.0) * _avg_loss)
                        _metrics_line = "━━━"
                        txt.append(_metrics_line)
                        txt.append("## 📊 Performance (30d validated)")
                        # Small-sample warning
                        if _perf.get("estimate_unstable"):
                            _n = _perf.get("sample_count", 0)
                            txt.append(f"⚠️ Only {_n} sample(s) — estimates unstable. VaR may reflect single tail event.")
                            if _em.get("_var_cvar_identical"):
                                txt.append("  VaR = CVaR: single worst outcome defines both. Not reliable for fat-tail risk.")
                        if _var95 is not None:
                            txt.append(f"- VaR (95%): {_var95*100:.1f}% | CVaR: {_cvar95*100:.1f}%")
                        if _expectancy is not None:
                            txt.append(f"- Expectancy: {_expectancy:.2f}% per trade | Win Rate: {_wr:.0f}%")
                        if _avg_win is not None and _avg_loss is not None:
                            txt.append(f"- Avg Win: +{_avg_win:.1f}% | Avg Loss: {_avg_loss:.1f}% | R: {abs(_avg_win/_avg_loss):.2f}")
                        # Additional empyrical metrics when sample >= 5
                        _sharpe = _em.get("sharpe")
                        _sortino = _em.get("sortino")
                        _calmar = _em.get("calmar")
                        if _sharpe is not None and _sortino is not None and _perf.get("sample_count", 0) >= 20:
                            _s_line = f"- Sharpe: {_sharpe:.2f} | Sortino: {_sortino:.2f}"
                            if _calmar is not None:
                                _s_line += f" | Calmar: {_calmar:.2f}"
                            txt.append(_s_line)
                        elif _sharpe is not None and _sortino is not None and _perf.get("sample_count", 0) >= 5:
                            _s_line = f"- Sharpe: ~{_sharpe:.0f} | Sortino: ~{_sortino:.0f} (n={_perf['sample_count']}, not meaningful)"
                            if _calmar is not None:
                                _s_line += f" | Calmar: ~{_calmar:.0f}"
                            txt.append(_s_line)
                        txt.append("")
        except Exception:
            pass
    if not _halted:
        # Paper trading recap — recently closed trades from ledger
        try:
            _ledger_path = os.path.join(SKILL_DIR, "reports", "paper_trading", "ledger.json")
            if os.path.exists(_ledger_path):
                with open(_ledger_path, encoding="utf-8") as _lf:
                    _ledger = json.load(_lf)
                _trades = _ledger.get("trades", []) if isinstance(_ledger, dict) else _ledger if isinstance(_ledger, list) else []
                # Filter: closed in last 48h, not legacy_archived
                _cutoff = (datetime.now(UTC).timestamp() - 172800) * 1000
                _recent = []
                for _t in _trades:
                    if _t.get("status") != "closed":
                        continue
                    if _t.get("outcome") == "legacy_archived":
                        continue
                    _ca = _t.get("closed_at", "")
                    if not _ca:
                        continue
                    try:
                        _cts = datetime.fromisoformat(_ca.replace("Z", "+00:00")).timestamp()
                    except (ValueError, AttributeError):
                        continue
                    if _cts * 1000 >= _cutoff:
                        _recent.append(_t)
            if _recent:
                txt.append(section("📋 Paper Trading Recap"))
                for _t in _recent[:4]:
                    _sym = _t.get("symbol", "?")
                    _out = _t.get("outcome", _t.get("reason", "closed"))
                    _pnl = _t.get("pnl_pct") or _t.get("pnl", 0)
                    _pnl_s = f"{_pnl:+.2f}%" if isinstance(_pnl, (int, float)) else "?"
                    _dur = _t.get("duration_hours") or ""
                    _dur_s = f" ({_dur:.1f}h)" if isinstance(_dur, (int, float)) else ""
                    _icon = "🟢" if (isinstance(_pnl, (int, float)) and _pnl > 0) else "🔴" if (isinstance(_pnl, (int, float)) and _pnl < 0) else "⚪"
                    txt.append(f"- {_icon} {_sym}: {_out} ({_pnl_s}){_dur_s}")
                txt.append("")
        except Exception:
            pass
    # Open positions — running P&L from paper portfolio
    if not _halted:
        try:
            _pfolio_path = os.path.join(SKILL_DIR, "reports", "paper_trading", "portfolio.json")
            if os.path.exists(_pfolio_path):
                with open(_pfolio_path, encoding="utf-8") as _pf:
                    _pfolio = json.load(_pf)
                _pfolio_ts = datetime.fromtimestamp(os.path.getmtime(_pfolio_path)).strftime("%H:%M")
                _positions = _pfolio.get("positions", {})
                if _positions:
                    # ── Refresh position prices from live TokoCrypto ticker data ──
                    # TokoCrypto prices are fresher than CoinGecko (fetched moments ago in fetch_markets)
                    _toko_price_map = {}
                    for _m in (markets or []):
                        _sym = (_m.get("symbol") or "").upper()
                        _toko_price = _m.get("tokocrypto_last")
                        if _sym and _toko_price and _toko_price > 0:
                            _toko_price_map[_sym] = float(_toko_price)
                    _refreshed = 0
                    _stale_cleared = 0
                    _toko_refreshed = set()  # symbols that got live TokoCrypto data
                    for _sym, _pos in _positions.items():
                        _fresh_price = _toko_price_map.get(_sym.upper())
                        if _fresh_price:
                            _toko_refreshed.add(_sym.upper())
                            if _pos.pop("_toko_stale", None) is not None:
                                _stale_cleared += 1
                            _old_price = _pos.get("current_price", 0)
                            if abs(_fresh_price - _old_price) / max(_old_price, 0.0001) > 0.001:  # >0.1% change
                                _refreshed += 1
                            _pos["current_price"] = round(_fresh_price, 8)
                            _pos["pnl_usd"] = round(_pos["quantity"] * _pos["current_price"] - _pos["allocated"], 2)
                            _pos["pnl_pct"] = round((_pos["pnl_usd"] / _pos["allocated"]) * 100, 2) if _pos["allocated"] else 0.0
                        else:
                            _pos["_toko_stale"] = True  # only cg/cached data available
                    # Staleness guard: flag ANY position without fresh TokoCrypto data
                    _all_stale = not _toko_refreshed and bool(_positions)  # true if market feed was entirely missing
                    if _all_stale:
                        txt.append("⚠️ Position prices not refreshed — TokoCrypto market data unavailable. Values may be stale.")
                    if _refreshed or _stale_cleared:
                        # Persist refreshed prices so m2m and next briefing pick them up
                        with open(_pfolio_path, "w", encoding="utf-8") as _pf:
                            json.dump(_pfolio, _pf, indent=2)
                        _pfolio_ts = datetime.fromtimestamp(os.path.getmtime(_pfolio_path)).strftime("%H:%M")
                    _cash = _pfolio.get("cash", 0)
                    _starting = _pfolio.get("starting_capital", 10000)
                    _equity = _cash + sum(
                        p.get("current_price", 0) * p.get("quantity", 0)
                        for p in _positions.values()
                    )
                    txt.append(section("💼 Open Positions"))
                    for _sym, _pos in sorted(_positions.items()):
                        _pnl = _pos.get("pnl_pct", 0)
                        _icon = "🟢" if (isinstance(_pnl, (int, float)) and _pnl > 0) else "🔴" if (isinstance(_pnl, (int, float)) and _pnl < 0) else "⚪"
                        _entry = _pos.get("entry_price", "?")
                        _cur = _pos.get("current_price", "?")
                        _trail = _pos.get("trailing_stop")
                        _trail_activated = _pos.get("trailing_activated", False)
                        _bias = _pos.get("bias", "bullish")
                        if _trail and _trail_activated:
                            _trail_s = f" · 🔒 locked @ ${_trail}"
                        elif _trail and not _trail_activated:
                            _trail_s = f" · 🤖 trail ready @ ${_trail}"
                        else:
                            _trail_s = ""
                        _highest = _pos.get("highest_price")
                        _highest_s = f" · high=${_highest}" if _highest else ""
                        _stale_flag = " ⚠️" if _pos.get("_toko_stale") else ""
                        txt.append(f"- {_icon} {_sym}: {_pnl:+.2f}% (entry=${_entry} → ${_cur}){_highest_s}{_trail_s}{_stale_flag}")
                    txt.append(f"  Equity: ${_equity:,.2f} · Cash: ${_cash:,.2f} · Positions: {len(_positions)} · Updated: {_pfolio_ts}")
                    txt.append("")
                    # Stash red-count for portfolio-health synthesis in Opportunities section
                    _red_positions = sum(1 for p in _positions.values() if (p.get("pnl_pct") or 0) < 0)
                else:
                    _red_positions = 0
            else:
                _red_positions = 0
        except Exception:
            _red_positions = 0
            pass
    txt += [
        section("🎯 Opportunities"),
    ]
    if not opps:
        # Better empty-state: explain why nothing passed
        if _halted:
            txt.append("🚫 **HALTED**: All signals blocked by extreme market regime. Capital preservation mode.")
        elif fng_val is not None and int(fng_val) <= 15:
            atr_info = _btc_atr_status()
            if atr_info.get("status") == "expanding":
                txt.append(f"🛑 **Bottom-fishing paused**: ATR expanding ({atr_info.get('ratio', 1):.2f}x) — falling knife risk. Waiting for volatility to contract.")
            else:
                txt.append("🤷 No mean-reversion setup passed the score threshold. Save powder.")
        else:
            _nope_reasons = []
            if not top:
                _nope_reasons.append("all screened below thresholds")
            elif len(top) < 2:
                _nope_reasons.append("only 1 passed — insufficient for pair analysis")
            txt.append(f"🤷 No high-confidence setup today. {'. '.join(_nope_reasons) if _nope_reasons else 'Save powder and watch for 2-signal convergence.'}")
    else:
        _port_notes = []  # collect portfolio notes for dedup below
        for idx, c in enumerate(opps, 1):
            terms = recommend_term(c.get("symbol"), c.get("name"))
            paper = best_paper_for(terms[0], terms[1:])
            direction = "bullish" if c.get("change_24h", 0) > 0 else "bearish"
            # ── Bottom-fishing: always LONG ──────────────────────────
            # TOK is spot-only (no shorting). Bottom-fishing pipeline already
            # filters to coins with negative 24h change. Direction is always bullish.
            if c.get("_bottom_fishing"):
                direction = "bullish"
            strategy = _regime_bias(c.get("change_24h", 0))
            bias = f"{strategy} - {direction}" if strategy != "momentum" else direction
            liq_mult = _liquidity_multiplier(c)
            entry = c.get("price", 0)
            if entry and entry > 0:
                # Dynamic target/stop: scale with volatility, improve RR with score
                vol = abs(c.get("change_24h", 3.0))
                score = c.get("score", 25)
                base_target = 8.0
                base_stop = 3.5
                # Volatility factor — more volatile = wider everything
                vol_factor = max(0.5, vol / 3.0)
                # Score RR boost — higher score = stretch target, tighten stop
                score_rr = max(0.8, min(1.5, (score - 15) / 20))
                # Liquidity-adjusted sizing
                adj_target_pct = min(15.0, max(5.0, base_target * vol_factor * score_rr))
                _rms = _regime_max_stop(int(fng.get('value', 50)) if isinstance(fng, dict) else 50)
                adj_stop_pct = min(_rms, max(2.0, base_stop * (vol_factor ** 0.5) - max(0, (score - 25) * 0.03)))
                target_pct = adj_target_pct
                stop_pct = adj_stop_pct
                # Store on coin for Watch Levels to reuse (single source of truth)
                c["_computed_target_pct"] = target_pct
                c["_computed_stop_pct"] = stop_pct
                if direction == "bearish":
                    target_price = round(entry * (1 - target_pct / 100), 6)
                    stop_price = round(entry * (1 + stop_pct / 100), 6)
                    target_label = f"{target_price:.6f} (-{target_pct:.0f}%)"
                    stop_label = f"{stop_price:.6f} (+{stop_pct:.1f}%)"
                else:
                    target_price = round(entry * (1 + target_pct / 100), 6)
                    stop_price = round(entry * (1 - stop_pct / 100), 6)
                    target_label = f"{target_price:.6f} (+{target_pct:.0f}%)"
                    stop_label = f"{stop_price:.6f} (-{stop_pct:.1f}%)"
            else:
                target_label = "n/a"
                stop_label = "n/a"
            # Dynamic confidence bar based on actual score (no --visuals flag needed)
            _score = c.get("score", 25)
            _score_threshold = _thresh_from_calibrations()
            _score_pct = min(1.0, max(0.15, (_score - _score_threshold) / (50 - _score_threshold))) if _score_threshold > 0 else min(0.8, _score / 60)
            _score_filled = int(round(10 * _score_pct))
            _score_bar = "█" * _score_filled + "░" * (10 - _score_filled)
            if _score >= 40:
                _conf_label = "high"
            elif _score >= 30:
                _conf_label = "medium"
            else:
                _conf_label = "low"
            # R/R ratio
            _rr = round(target_pct / stop_pct, 1) if stop_pct > 0 and target_pct > 0 else 0
            txt.append(f"{idx}. {c['name']} ({c['symbol']})")
            txt.append(f"- Bias: {bias}")
            # Regime-aware thesis
            if strategy == "mean-reversion":
                thesis = f"{round(c.get('change_24h', 0),2)}% move; high-vol regime — targeting snap-back with tight stop"
            elif strategy == "momentum":
                thesis = f"{round(c.get('change_24h', 0),2)}% move; trending — momentum + cap flow aligned"
            else:
                thesis = f"{round(c.get('change_24h', 0),2)}% move; momentum + cap flow aligned"
            txt.append(f"- Why: {thesis}")
            _entry_price = c.get('price', 0) or 0
            txt.append(f"- Entry: near {_entry_price:.6f}")
            txt.append(f"- Stop: {stop_label}")
            txt.append(f"- Target: {target_label}")
            # Score bar (price/volume-derived — a market structure score, not fundamental sentiment)
            txt.append(f"- Score: {_conf_label} {_score_bar} · R/R {_rr}x")
            # Low-conviction sole survivor qualifier
            if len(opps) == 1 and _conf_label == "low":
                txt.append("  \u26a0\ufe0f Low conviction on this pick \u2014 consider sitting out if above your minimum quality bar")
            # ── Portfolio-health synthesis: connect open position P&L with conviction ──
            if _red_positions >= 2 and _conf_label == "low":
                txt.append("  ⚠️ 2 open positions in the red + this is a low-conviction pick — consider sitting out entirely today")
            # Liquidity quality — non-price dimension from orderbook depth
            _depth_data = c.get("tokocrypto_depth")
            if isinstance(_depth_data, dict):
                _liq_spread = _depth_data.get("spread_bps", 999)
                _liq_total = _depth_data.get("total_depth_usd", 0)
                if _liq_spread < 5 and _liq_total > 500_000:
                    _liq_grade = "A 🟢"
                elif (_liq_spread < 5 and _liq_total > 30_000) or (_liq_spread < 15 and _liq_total > 100_000):
                    _liq_grade = "B 🟡"
                elif _liq_spread < 30:
                    _liq_grade = "C 🟠"
                else:
                    _liq_grade = "D 🔴"
                txt.append(f"- Liq grade: {_liq_grade} ({_liq_spread:.0f}bps spread · ${_liq_total:,.0f} depth)")
            else:
                # Fall back to ticker-level bid/ask
                _liq_bid = c.get("tokocrypto_bid")
                _liq_ask = c.get("tokocrypto_ask")
                _liq_vol = c.get("tokocrypto_volume_quote") or 0
                if _liq_bid and _liq_ask and _liq_bid > 0 and _liq_ask > 0:
                    _liq_spread = (float(_liq_ask) - float(_liq_bid)) / float(_liq_bid) * 10000
                    if _liq_spread < 10 and _liq_vol > 100_000:
                        _liq_grade = "B 🟡"
                    elif _liq_spread < 25:
                        _liq_grade = "C 🟠"
                    else:
                        _liq_grade = "D 🔴"
                    _liq_vol_s = f" ${_liq_vol:,.0f} vol" if _liq_vol else ""
                    txt.append(f"- Liq grade: {_liq_grade} ({_liq_spread:.0f}bps spread{_liq_vol_s})")
                else:
                    txt.append(f"- Liq grade: ⚪ unknown (no orderbook data)")
            txt.append(f"- {_format_depth_line(c)}")
            if liq_mult < 1.0:
                _bf_note = ""
                if opps and any(c.get("_bottom_fishing") for c in opps):
                    _eff = liq_mult * 0.5
                    _bf_note = f" (further reduced to {_eff:.0%} by bottom-fishing 50% rule)"
                txt.append(f"- Sizing: {liq_mult:.0%} multiplier (spread-adjusted){_bf_note}")
            port_note = c.get("portfolio_note", "")
            if port_note and port_note != "within portfolio limits":
                _port_notes.append(port_note)
            fund_note = c.get("funding_note", "")
            if fund_note:
                txt.append(f"- Derivatives: {fund_note}")
            trap_line = _format_trap_line(c)
            if trap_line:
                txt.append(f"- {trap_line}")
            if paper:
                tl = paper.get("tier_label", "🟢 peer-reviewed")
                finding = paper.get("finding", paper.get("title", "Research"))
                # Word-boundary truncation at 300 chars (findings are typically ~160 chars)
                _trim = finding[:300].strip()
                if len(finding) > 300:
                    _last_break = _trim.rfind(" ")
                    if _last_break > 90:
                        _trim = _trim[:_last_break]
                    _trim += "…"
                txt.append(f"- Research: {tl} {_trim}")
                if paper.get("score", 0) >= 1.0:
                    txt.append(f"  Strong match — tags: {', '.join(paper.get('tags', []))}")
                elif paper.get("score", 0) >= 0.7:
                    txt.append(f"  Relevant — tags: {', '.join(paper.get('tags', []))}")
                if paper.get("score", 0) < 1.0:
                    txt.append("  \u26a0\ufe0f Generic citation — does not specifically support this trade thesis")
            txt.append("")
    # Show dedup'd portfolio notes once (same note for all positions = portfolio-wide issue)
    if opps:
        _seen_port = set()
        for _pn in _port_notes:
            if _pn not in _seen_port:
                txt.append(f"- Portfolio: {_pn}")
                _seen_port.add(_pn)
    # ── Dynamic Watch Levels from picks and open positions ──────────────
    _watch_lines = ["━━━", section("🔭 Watch Levels")]
    if opps:
        # Show concrete levels from the top pick
        _c0 = opps[0]
        _c0_strat = _regime_bias(_c0.get("change_24h", 0))
        _c0_dir = "bullish" if _c0.get("change_24h", 0) > 0 else "bearish"
        if _c0.get("_bottom_fishing"):
            _c0_dir = "bullish"  # bottom-fishing is always long
        _c0_entry = _c0.get("price", 0)
        # Use values computed by Opportunities renderer (single source of truth)
        _c0_target_pct = _c0.get("_computed_target_pct")
        _c0_stop_pct = _c0.get("_computed_stop_pct")
        if _c0_target_pct is None or _c0_stop_pct is None:
            # Fallback: compute from volatility only (entry was 0 or missing)
            _c0_vol = abs(_c0.get("change_24h", 3.0))
            _c0_target_pct = min(15.0, max(5.0, 8.0 * max(0.5, _c0_vol / 3.0)))
            _c0_stop_pct = min(8.0, max(2.0, 3.5 * (max(0.5, _c0_vol / 3.0) ** 0.5)))
        if _c0_dir == "bearish":
            _watch_target = round(_c0_entry * (1 - _c0_target_pct / 100), 6)
            _watch_stop = round(_c0_entry * (1 + _c0_stop_pct / 100), 6)
        else:
            _watch_target = round(_c0_entry * (1 + _c0_target_pct / 100), 6)
            _watch_stop = round(_c0_entry * (1 - _c0_stop_pct / 100), 6)
        _watch_lines.append(f"- {_c0['symbol']}: trigger near ${_c0_entry:.6f} · stop ${_watch_stop:.6f} · target ${_watch_target:.6f}"[:120])
        if len(opps) > 1:
            _c1 = opps[1]
            _c1_entry = _c1.get("price", 0)
            _watch_lines.append(f"- {_c1['symbol']}: entry near ${_c1_entry:.6f}")
    _watch_lines.append(f"- BTC {btc_dom}% · F&G {fng_str} — extreme fear = size down, tighten stops")
    _watch_lines.append("")
    txt += _watch_lines
    # ── Today's Action tailored to regime ────────────────────────────────
    _act_lines = ["━━━", section("📋 Today's Action")]
    # Determine dominant strategy from all picks
    _all_strats = set()
    for _co in opps:
        _s = _regime_bias(_co.get("change_24h", 0))
        _all_strats.add(_s)
    if not opps:
        _act_lines.append("- 1) Check pre-market regime")
        _act_lines.append("- 2) Rescan when 1h/4h trends align")
        # Dynamic re-entry triggers when no picks pass screening
        _re_entry = []
        if _fng_int is not None and _fng_int < 20:
            _re_entry.append("F&G exits Extreme Fear (≥20)")
        elif _fng_int is not None and _fng_int < 30:
            _re_entry.append("F&G rises above Fear (≥30)")
        _act_lines.append(f"- 3) Re-entry if {' or '.join(_re_entry) if _re_entry else '1h/4h trends align'}")
        _act_lines.append("- 4) Save powder until conditions met")
    else:
        _dominant = "mean-reversion" if "mean-reversion" in _all_strats else "momentum"
        if _dominant == "mean-reversion":
            _act_lines.append("- 1) Quick in/out — mean-reversion fading works best < 4h")
            _act_lines.append("- 2) Tight stop discipline — don't let a snap-back flip into a trend loss")
            _act_lines.append("- 3) Verify 1h/4h overextension before entry")
            # Add ATR-specific guidance for bottom-fishing (F&G ≤ 15)
            if opps and any(c.get("_bottom_fishing") for c in opps):
                _act_lines.append("- 4) 🎣 Bottom-fishing active — size at 50% normal, expect fake-outs")
                _act_lines.append("- 5) If ATR expands, exit partial position immediately")
        else:
            _act_lines.append("- 1) Let momentum run — wait for 1h pullback to entry zone")
            _act_lines.append("- 2) Confirm trend on 4h timeframe before committing")
            _act_lines.append("- 3) Scale in on weakness, trail on strength")
    _act_lines += ["", "━━━", section("📈 Quick P&L")]
    # Embed actual paper trading summary instead of a ghost command
    try:
        _pt_pfolio_path = os.path.join(SKILL_DIR, "reports", "paper_trading", "portfolio.json")
        if os.path.exists(_pt_pfolio_path):
            import json as _pt_json
            with open(_pt_pfolio_path, encoding="utf-8") as _pt_f:
                _pt_data = _pt_json.load(_pt_f)
            _pt_cash = _pt_data.get("cash", 0)
            _pt_starting = _pt_data.get("starting_capital", 10000)
            _pt_positions = _pt_data.get("positions", {})
            _pt_equity = _pt_cash + sum(
                p.get("current_price", 0) * p.get("quantity", 0)
                for p in _pt_positions.values()
            ) if _pt_positions else _pt_cash
            _pt_return = ((_pt_equity - _pt_starting) / _pt_starting * 100) if _pt_starting else 0
            _pt_icon = "🟢" if _pt_return >= 0 else "🔴"
            # ── Day-over-Day delta ────────────────────────────────────────
            _dod_change = None
            _dod_pct = None
            try:
                _snap_path = os.path.join(SKILL_DIR, "reports", "portfolio_snapshot.json")
                if os.path.exists(_snap_path):
                    with open(_snap_path, encoding="utf-8") as _sf:
                        _snap = _pt_json.load(_sf)
                    _prev_equity = _snap.get("equity", _pt_equity)
                    if _prev_equity and _prev_equity > 0:
                        _dod_change = _pt_equity - _prev_equity
                        _dod_pct = (_dod_change / _prev_equity) * 100
                # Save today's snapshot
                with open(_snap_path, "w", encoding="utf-8") as _sf:
                    _pt_json.dump({"equity": round(_pt_equity, 2), "timestamp": datetime.now(UTC).isoformat()}, _sf)
            except Exception:
                pass
            # Build equity line with DoD delta
            _equity_line = f"- Paper: Equity ${_pt_equity:,.2f} · Return {_pt_icon} {_pt_return:+.2f}%"
            if _dod_change is not None and _dod_pct is not None and abs(_dod_change) > 0.10 and abs(_dod_pct * 100) >= 1.0:
                _dod_icon = "🟢" if _dod_change >= 0 else "🔴"
                # Show in dollars and bps (1% = 100 bps)
                _dod_bps = _dod_pct * 100
                _equity_line += f" · Δ24h {_dod_icon} ${_dod_change:+.2f} ({_dod_bps:+.1f}bps)"
            _equity_line += f" · {len(_pt_positions)} open position(s)"
            _act_lines.append(_equity_line)
        else:
            _act_lines.append("- Paper: no trading data yet")
    except Exception:
        _act_lines.append("- Paper: summary unavailable (read your positions above)")
    txt += _act_lines
    if enhanced and not _halted:
        try:
            compact_regime = _compact_regime_block(fng_val=fng_val)
        except Exception:
            compact_regime = "Regime data unavailable."
        txt += ["", compact_regime]
    if orchestrator:
        orch_block = _orchestrator_block()
        if orch_block:
            # Save to digest file instead of embedding in the briefing text
            _orch_digest = _save_orchestrator_digest(orch_block)
            if _orch_digest and not _halted:
                txt += ["", f"━━━\n## ⚙️ System\n📊 Orchestrator digest saved to `reports/{os.path.basename(_orch_digest)}`"]
            elif _halted:
                pass  # silently skip — no one reads orchestrator stats in a halted regime
    return "\n".join(txt)


def _orchestrator_block() -> str:
    """Compact orchestrator status block from strategy journal."""
    try:
        import importlib.util as _iu
        _jp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "scripts", "strategy_journal.py")
        if not os.path.exists(_jp):
            return ""
        _spec = _iu.spec_from_file_location("_sj", _jp)
        _mod = _iu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.init_db()

        open_sigs = _mod.get_open_signals()
        perf = _mod.compute_performance("trailing_30d")
        params = _mod.load_params()

        rows = ["", "## Orchestrator Status"]
        scr = params.get("screening", {})
        rows.append(f"- Params: min_24h_chg={scr.get('min_24h_change_pct', '?')}% | score_threshold={scr.get('score_threshold', '?')} | risk={params.get('risk', {}).get('risk_per_trade_pct', '?')}%")
        rows.append(f"- Performance: {perf.get('closed_signals', 0)} closed | WR={perf.get('win_rate', 0):.1%} | PF={perf.get('profit_factor', 0):.2f}")
        # When PF < 1.0 or WR < 40%, surface suggest_adjustments() from portfolio engine
        _pf = perf.get('profit_factor', 1.0)
        _wr = perf.get('win_rate', 0.5)
        if (_pf is not None and _pf < 1.0) or (_wr is not None and _wr < 0.40):
            try:
                import importlib.util as _iu2
                _pe_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "strategy", "portfolio_engine.py"
                )
                if os.path.exists(_pe_path):
                    _spec2 = _iu2.spec_from_file_location("_pe_briefing", _pe_path)
                    _pe2 = _iu2.module_from_spec(_spec2)
                    _spec2.loader.exec_module(_pe2)
                    _adj = _pe2.suggest_adjustments()
                    if _adj:
                        for _a in _adj:
                            rows.append(f"  ⚠️ {_a}")
            except Exception:
                pass
        rows.append(f"- Open signals: {len(open_sigs)}")
        if open_sigs:
            rows.append(f"  Symbols: {', '.join(s['symbol'] for s in open_sigs[:5])}")
        # Parameter optimizer findings (if available)
        try:
            _opt_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "strategy", "optimizer_report.json"
            )
            if os.path.exists(_opt_path):
                import json as _json
                _opt = _json.loads(open(_opt_path, encoding="utf-8").read())
                _recs = _opt.get("recommendations", [])
                if _recs:
                    rows.append(f"  📊 Optimizer ({_opt.get('coins_analyzed', 0)} coins, {_opt.get('generated_at', '?')[:10]}):")
                    for _r in _recs[:2]:
                        rows.append(f"    → {_r}")
        except Exception:
            pass
        # Research-backed parameter sources from calibrations
        try:
            cal = _load_calibrations()
            liq = cal.get("liquidity", {})
            reg = cal.get("regime", {})
            rows.append(f"- Research: vol thresholds {reg.get('low_vol_threshold', 1.5)*100:.1f}%/{reg.get('high_vol_threshold', 3)*100:.0f}% "
                        f"(momentum/mean-reversion) | spread baseline {liq.get('spread_ideal_bps', 3):.0f}bps "
                        f"| impact model {liq.get('impact_model', 'sqrt')}")
        except Exception:
            pass
        return "\n".join(rows)
    except Exception:
        return ""


def _save_orchestrator_digest(block: str) -> str:
    """Save orchestrator status block to a dated digest file instead of embedding in the briefing.
    
    Returns the file path, or empty string on failure.
    """
    if not block:
        return ""
    try:
        _digest_dir = os.path.join(REPORTS_DIR)
        os.makedirs(_digest_dir, exist_ok=True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        _path = os.path.join(_digest_dir, f"orchestrator_digest_{today}.md")
        with open(_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n<!-- generated: {now_iso()} -->\n")
            f.write(block)
        return _path
    except Exception:
        return ""


def save(text):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    path = os.path.join(REPORTS_DIR, f"daily_briefing_{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--save-only", action="store_true")
    p.add_argument("--out", default=None)
    p.add_argument("--compact", action="store_true")
    p.add_argument("--visuals", action="store_true")
    p.add_argument("--paper-open", action="store_true")
    p.add_argument("--enhanced", action="store_true")
    p.add_argument("--orchestrator", action="store_true", help="Save orchestrator status block to dated digest file (not embedded in briefing text)")
    args = p.parse_args()

    print("Pulling free market data...")
    markets = fetch_markets()
    global_data = fetch_global()
    fng = fetch_fear_greed()
    assets = fetch_coincap()

    text = render_briefing(
        markets, global_data, fng, assets, compact=args.compact, visuals=args.visuals, enhanced=args.enhanced, orchestrator=args.orchestrator
    )
    if args.out:
        p2 = args.out
        os.makedirs(os.path.dirname(p2) if os.path.dirname(p2) else ".", exist_ok=True)
        with open(p2, "w", encoding="utf-8") as f:
            f.write(text)
        print("Wrote", p2)
        return

    path = save(text)
    print("Briefing written to", path)

    if args.paper_open:
        import importlib.util
        spec = importlib.util.spec_from_file_location("paper_trader", os.path.join(os.path.dirname(__file__), "paper_trader.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        briefing_path = os.path.splitext(path)[0] + ".md"
        mod.open_today_from_briefing(briefing_path)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n\n")
            f.write("> Paper trading: summary embedded above. Full details in reports/paper_trading/summary_*.md.")


if __name__ == "__main__":
    main()
