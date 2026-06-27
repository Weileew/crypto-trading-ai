#!/usr/bin/env python3
"""Daily crypto briefing generator."""
import os
import json
import re
import subprocess
import argparse
import time as _time_module
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

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

from free_data import (
    _get,
    fetch_dex_screener_search,
    fetch_defillama_protocols,
    fetch_defillama_yields,
    fetch_defillama_stablecoins,
    fetch_stablecoin_net_flows,
)


# CG-specific rate limiter — free tier is 10-30 req/min, play safe at 6s spacing
_CG_MIN_INTERVAL = 6.0
_CG_LAST_CALL = _time_module.time() - (_CG_MIN_INTERVAL - 0.5)  # stagger first call


def _get_cg(url, params=None):
    """CoinGecko-specific GET with conservative rate limiting (3s min interval)."""
    global _CG_LAST_CALL
    wait = _CG_MIN_INTERVAL - (_time_module.time() - _CG_LAST_CALL)
    if wait > 0:
        _time_module.sleep(wait)
    result = _get(url, params=params, retries=4, backoff=2.0)
    _CG_LAST_CALL = _time_module.time()
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

    # Phase 2: Binance USDT gate
    try:
        req = Request("https://api.binance.com/api/v3/exchangeInfo", headers={"User-Agent": UA})
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        binance_usdt = set()
        for s in data.get("symbols", []):
            if isinstance(s, dict) and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                binance_usdt.add((s.get("baseAsset") or "").upper())
    except Exception:
        binance_usdt = set()

    if not binance_usdt:
        return all_coins

    gated = []
    coin_symbols_found = set()
    for item in all_coins:
        if not isinstance(item, dict):
            continue
        sym = (item.get("symbol") or "").upper()
        if sym in binance_usdt:
            gated.append(item)
            coin_symbols_found.add(sym)

    # Phase 3: batch fallback via /simple/price (avoids N individual /coins/{id} calls)
    missing_symbols = binance_usdt - coin_symbols_found
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

    return gated


def fetch_global():
    return _get_cg("https://api.coingecko.com/api/v3/global")


def fetch_fear_greed():
    data = _get("https://api.alternative.me/fng/?limit=1&format=json")
    return ((data.get("data") or [{}])[0]) if isinstance(data, dict) else data


def fetch_coincap(limit=120):
    data = _get("https://api.coincap.io/v2/assets", {"limit": limit})
    return (data.get("data") or data) if isinstance(data, dict) else data


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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
    """Read consolidated research digest for papers matching a concept.

    Searches paper titles (bold text) in the digest. Returns the top-tier,
    most-relevant paper match. Uses the single digest file instead of
    searching 78 individual paper files.
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

    # Find all paper entries: lines with 🟢/🟡 badge, bold title, DOI
    matches = []
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("- 🟢") and not s.startswith("- 🟡"):
            continue
        m = re.search(r"\*\*(.+?)\*\*", s)
        if not m:
            continue
        title = m.group(1)
        title_lower = title.lower()
        # Count how many concept words appear in title
        match_count = sum(1 for w in words if w in title_lower)
        if match_count == 0:
            continue
        tier = "A" if s.startswith("- 🟢") else ("B" if s.startswith("- 🟡") else "C")
        doi_match = re.search(r"(doi:[\d.]+/\S+)", s)
        doi_str = f" ({doi_match.group(1)})" if doi_match else ""
        matches.append({
            "title": title,
            "ref": f"{title}{doi_str}",
            "tier": tier,
            "score": match_count / len(words),  # fraction of concept words matched
        })

    if not matches:
        return None

    # Sort: Tier A first (0 < 1 < 2), then by score descending
    tier_order = {"A": 0, "B": 1, "C": 2}
    matches.sort(key=lambda x: (tier_order.get(x["tier"], 3), -x["score"]))
    return matches[0]


def best_paper_for(term, fallback_terms):
    """Find research citation using the consolidated digest only.

    Uses the research-digest.md single file — never searches individual paper files.
    This is O(78KB read + title scan) instead of O(78 file reads + grep).

    Priority: Tier A (peer-reviewed) over Tier B (preprint) over Tier C.
    """
    terms = [term] + fallback_terms

    # Consolidated source only
    for t in terms:
        hit = lookup_research(t)
        if hit:
            return hit

    return None


def recommend_term(symbol, name):
    sym = (symbol or "").lower()
    n = (name or "").lower()
    terms = [n, sym]
    if sym in {"btc", "eth"}:
        terms += [sym, f"bitcoin trading", f"{sym} trading"]
    else:
        terms += [f"crypto trading", f"cryptocurrency trading strategy"]
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


def simple_rules(markets):
    candidates = []
    if not isinstance(markets, list):
        return candidates
    STABLECOINS = {"usdt", "usdc", "busd", "dai", "ust", "tusd", "pax", "gusd", "usdp", "fdusd", "steth", "wsteth", "reth", "frax", "lusd", "susd", "usde", "usd0"}
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
        if mcap < 25e6:
            continue
        p = c.get("price_change_percentage_24h") or 0
        if abs(p) < 2.0:
            continue
        mc = c.get("market_cap_change_percentage_24h") or 0
        score = abs(p) + max(0, mc) * 0.05
        if score < 20:
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
            }
        )
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:15]


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


def _compact_regime_block():
    """Compact regime context from free no-registration sources."""
    rows = []
    try:
        rows.append("## Regime (enhanced)")
        protos = fetch_defillama_protocols(limit=8)
        if protos:
            top = protos[0]
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


def _safe_fng_value_classification(fng):
    if isinstance(fng, dict):
        val = fng.get("value_classification")
        if val:
            return val
    return "n/a"


def _safe_price(c):
    p = c.get("current_price")
    return float(p) if isinstance(p, (int, float)) and p > 0 else None


def _usdt_pairs():
    UA = "crypto-trading-advisor/0.1 (+https://example.com)"
    try:
        req = Request("https://api.binance.com/api/v3/exchangeInfo", headers={"User-Agent": UA})
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
    text = []
    text.append("# Daily Trading Briefing")
    text.append(f"- generated: {dt}")
    text.append("- profile: balanced swing/day spot")
    text.append("- sources: price/volume, sentiment, top alpha move scan, defi sector, dex activity, stablecoin flows")
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
        for i, c in enumerate(top, 1):
            text.append(
                f"{i}. {c['name']} ({c['symbol']}) | price={c['price']} | 24h={round(c['change_24h'],2)}% | mcap_chg={round(c['mcap_change_24h'],2)}% | score={c['score']}"
            )
        text.append("")
        text.append("Use these as brainstorming targets, not trade tickets.")
    text += [
        "",
        section("Next Daily Briefing Checklist"),
        "- Re-run the scanner and freeze alpha candidates by 09:15 local time.",
        "- Verify 4h/1h trend and stop alignment.",
        "- Check TokoCrypto liquidity on tokens with large notional flow.",
    ]
    return "\n".join(text)


def render_compact_briefing(markets, global_data, fng, assets, visuals=False, enhanced=False, orchestrator=False):
    dt = now_iso().split("T")[0]
    top = simple_rules(markets) or []
    sources_healthy = bool(markets)
    opps = (top or [])[:2]
    btc_dom = _safe_btc_dom(global_data)
    fng_str = _safe_fng_value_classification(fng)
    fng_val = fng.get("value") if isinstance(fng, dict) else None
    pulse = "🟢 risk-on" if fng_val is not None and str(fng_val) not in ("n/a", "None", "") and int(fng_val) > 45 else "🔴 risk-off"
    dom_bar = visual_dom_bar(btc_dom) if visuals and btc_dom != "n/a" else ""
    risk = risk_icon(fng_str, fng_val)
    txt = []
    txt.append("# 📊 Daily Crypto Briefing")
    txt.append(f"- Date: {dt}")
    txt.append("- Style: balanced swing/day spot")
    txt.append("")
    txt += [
        section("Risk"),
        "⚠️ Not financial advice. This is a checklist, not a green light. Preserve capital first.",
        "",
        section("Market Regime"),
        f"- BTC dominance: {btc_dom}% {dom_bar}",
        f"- Risk icon: {risk} - {fng_str}",
        f"- Market pulse: {pulse}",
        f"- Market cap shift: strongest stream above {round(top[0]['mcap_change_24h'], 1)}%" if top else "- Market cap shift: no high-intensity candidates filtered",
    ]
    if not sources_healthy:
        txt.append("⚠️ CoinGecko market data unavailable — opportunities reflect stale or incomplete data. Verify BTC price manually.")
    txt.append("")
    txt += [
        section("Opportunities"),
    ]
    if not opps:
        txt.append("🤷 No high-confidence setup today. Save powder, watch liquidity, and wait for 2-signal convergence.")
    else:
        for idx, c in enumerate(opps, 1):
            terms = recommend_term(c.get("symbol"), c.get("name"))
            paper = best_paper_for(terms[0], terms[1:])
            bias = "bullish" if c.get("change_24h", 0) > 0 else "bearish"
            invalidation = f"{round(c.get('price', 0) * 0.965, 4)}" if c.get("price") else "n/a"
            target = f"{round(c.get('price', 0) * 1.08, 4)}" if c.get("price") else "n/a"
            conf = confidence_bar("medium") if visuals else ""
            txt.append(f"{idx}. {c['name']} ({c['symbol']})")
            txt.append(f"- Bias: {bias}")
            txt.append(f"- Why: 24h={round(c.get('change_24h', 0),2)}%; momentum + cap flow aligned")
            txt.append(f"- Entry: near {c.get('price')}")
            txt.append(f"- Stop: {invalidation}")
            txt.append(f"- Target: {target}")
            txt.append(f"- Confidence: medium {conf}" if conf else "- Confidence: medium")
            txt.append(f"- Liquidity: see TokoCrypto snapshot")
            if paper:
                txt.append(f"- Research: {paper.get('title','paper')}")
            txt.append("")
    txt += [
        section("Watch Levels"),
        "- BTC key levels: see latest market data",
        "- Review top 1-2 alts from opportunities above",
        "",
        section("Quick P&L Monitor"),
        "- Paper trading: run `python3 scripts/paper_trader.py --summary`",
        "",
        section("Today's Action"),
        "- 1) Confirm regime at market open",
        "- 2) Check TokoCrypto liquidity for opportunity coins",
        "- 3) Review 1h trend and stop alignment before entry",
    ]
    if enhanced:
        try:
            compact_regime = _compact_regime_block()
        except Exception as e:
            compact_regime = "Regime data unavailable."
        txt += ["", compact_regime]
    if orchestrator:
        orch_block = _orchestrator_block()
        if orch_block:
            txt += [orch_block]
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
        rows.append(f"- Open signals: {len(open_sigs)}")
        if open_sigs:
            rows.append(f"  Symbols: {', '.join(s['symbol'] for s in open_sigs[:5])}")
        return "\n".join(rows)
    except Exception:
        return ""


def save(text):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    p.add_argument("--orchestrator", action="store_true", help="Append orchestrator status block (journal perf, open signals, params)")
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
            f.write("> Paper trading: for full portfolio view, run `python3 scripts/paper_trader.py --summary`.")


if __name__ == "__main__":
    main()
