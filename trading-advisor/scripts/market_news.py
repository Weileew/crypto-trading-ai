#!/usr/bin/env python3
"""Market news monitor — fetches free news from multiple sources and classifies sentiment.

Sources (free, no API key required):
  - CoinTelegraph RSS feed
  - CoinDesk RSS feed
  - Alternative.me Fear & Greed Index
  - BTC dominance as sentiment proxy

Usage:
    python3 market_news.py                # fetch and print latest news
    python3 market_news.py --cache        # fetch and store in journal DB
    python3 market_news.py --compact      # short one-liner summary only
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# Sentiment keywords for headline classification
_BULLISH_KW = {"surge", "rally", "bull", "high", "gain", "up", "breakout",
               "positive", "green", "ath", "all-time high", "record", "adopt",
               "approve", "partnership", "launch", "upgrade", "inflow"}
_BEARISH_KW = {"crash", "dump", "bear", "low", "drop", "down", "decline",
               "negative", "red", "ban", "crackdown", "hack", "exploit",
               "outflow", "fraud", "regulation", "investigation", "sell-off",
               "correction", "fear", "panic", "liquidation"}

_RATE_DELAY = 1.5
_last_call = 0.0


def _wait():
    global _last_call
    wait = _RATE_DELAY - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)


def _get(url, params=None, timeout=20):
    _wait()
    h = {"User-Agent": UA}
    full_url = url
    if params:
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        full_url = f"{url}{sep}{urlencode(params)}"
    try:
        global _last_call
        with urlopen(Request(full_url, headers=h), timeout=timeout) as resp:
            _last_call = time.time()
            data = resp.read().decode()
            try:
                return json.loads(data)
            except (json.JSONDecodeError, ValueError):
                return data
    except Exception as e:
        return {"_error": str(e)}


def _classify_sentiment(headline: str) -> str:
    """Classify a headline as bullish, bearish, or neutral."""
    hl = headline.lower()
    bullish_score = sum(1 for kw in _BULLISH_KW if kw in hl)
    bearish_score = sum(1 for kw in _BEARISH_KW if kw in hl)
    if bullish_score > bearish_score:
        return "bullish"
    elif bearish_score > bullish_score:
        return "bearish"
    return "neutral"


def fetch_fear_greed() -> dict:
    """Alternative.me Fear & Greed Index."""
    raw = _get("https://api.alternative.me/fng/?limit=1&format=json")
    if isinstance(raw, dict) and "data" in raw and raw["data"]:
        entry = raw["data"][0]
        return {
            "value": entry.get("value"),
            "classification": entry.get("value_classification"),
            "source": "alternative.me",
        }
    return {"value": None, "classification": "n/a", "source": "alternative.me"}


def fetch_rss_headlines(url: str, source_name: str, limit: int = 5) -> list[dict]:
    """Fetch and parse an RSS feed for news headlines. Returns list of headline dicts."""
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return []

    data = _get(url, timeout=15)
    if isinstance(data, dict) and "_error" in data:
        return []
    if not isinstance(data, str):
        return []

    headlines = []
    try:
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items:
            # NOTE: Element.__len__ returns child count, so bool(element) is False for
            # text-only elements. Cannot use `or` for fallback — must use explicit None check.
            title_el = item.find("title")
            if title_el is None:
                title_el = item.find("atom:title", ns)
            link_el = item.find("link")
            if link_el is None:
                link_el = item.find("atom:link", ns)
            if title_el is None or title_el.text is None:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            link = ""
            if link_el is not None:
                link = link_el.text or link_el.get("href", "")
            headlines.append({
                "source": source_name,
                "headline": title,
                "url": link,
                "sentiment": _classify_sentiment(title),
                "summary": "",
            })
            if len(headlines) >= limit:
                break
    except ET.ParseError:
        return []

    return headlines


def fetch_fallback_headlines() -> list[dict]:
    """Fallback headlines based on Fear & Greed when RSS feeds are unavailable."""
    fng = fetch_fear_greed()
    val = fng.get("value")
    cls = fng.get("classification", "n/a")
    headlines = [
        {
            "source": "FearGreed",
            "headline": f"Fear & Greed Index: {val}/100 ({cls})" if val else f"Fear & Greed: {cls}",
            "url": "https://alternative.me/crypto/fear-and-greed-index/",
            "sentiment": "bearish" if cls and "fear" in cls.lower() else ("bullish" if cls and "greed" in cls.lower() else "neutral"),
            "summary": f"Market sentiment is in {cls} territory." if cls else "",
        },
    ]
    return headlines


def fetch_market_news(limit: int = 8, prefer_fallback: bool = False) -> list[dict]:
    """Fetch news from all available sources, deduped by headline."""
    all_headlines = []

    # Primary: RSS feeds from major crypto news sites
    if not prefer_fallback:
        feeds = [
            ("https://cointelegraph.com/rss", "CoinTelegraph"),
            ("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
        ]
        for feed_url, source_name in feeds:
            rss = fetch_rss_headlines(feed_url, source_name, limit=max(3, limit // 2))
            all_headlines.extend(rss)

    # Always include Fear & Greed
    all_headlines.extend(fetch_fallback_headlines())

    # Deduplicate by headline text
    seen = set()
    deduped = []
    for h in all_headlines:
        key = h["headline"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(h)

    return deduped[:limit]


def format_compact(news_list: list[dict]) -> str:
    """Format news as a compact block for embedding in briefings."""
    lines = ["## Market News"]
    if not news_list:
        lines.append("No news data available.")
        return "\n".join(lines)

    bullish = sum(1 for n in news_list if n.get("sentiment") == "bullish")
    bearish = sum(1 for n in news_list if n.get("sentiment") == "bearish")
    neutral_cnt = len(news_list) - bullish - bearish

    lines.append(f"Sentiment: 🟢{bullish} / 🔴{bearish} / ⚪{neutral_cnt}")
    for n in news_list:
        icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(n.get("sentiment", "neutral"), "⚪")
        lines.append(f"- {icon} {n['headline']}")
    return "\n".join(lines)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Market news monitor")
    p.add_argument("--cache", action="store_true", help="Store news in journal DB")
    p.add_argument("--compact", action="store_true", help="Compact output for embedding")
    p.add_argument("--limit", type=int, default=8, help="Max headlines")
    args = p.parse_args()

    news = fetch_market_news(limit=args.limit)

    if args.compact:
        print(format_compact(news))
        return

    if args.cache:
        try:
            from strategy_journal import cache_news
            cache_news(news)
            print(f"Cached {len(news)} headlines.")
        except ImportError:
            print("Warning: strategy_journal not available, skipping cache.")
        except Exception as e:
            print(f"Warning: cache failed: {e}")

    for n in news:
        icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(n.get("sentiment", "neutral"), "⚪")
        print(f"{icon} [{n['source']}] {n['headline']}")
        if n.get("url"):
            print(f"   {n['url']}")
    print(f"\n{len(news)} headlines from {len(set(n['source'] for n in news))} sources")


if __name__ == "__main__":
    main()
