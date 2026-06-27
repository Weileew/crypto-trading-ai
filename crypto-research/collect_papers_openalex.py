#!/usr/bin/env python3
"""Daily crypto-trading research enrichment — dual-source, noise-free.

Sources (high quality only):
  1. OpenAlex — peer-reviewed academic papers with full abstracts (primary)
  2. arXiv q-fin — preprints in quantitative finance / crypto (secondary)

Noise rejected:
  - Papers with crypto keywords but NO trading/finance context (cryptography, privacy, etc.)
  - Papers with trading keywords but NO crypto context (generic finance, commodities, etc.)
  - CrossRef (697K results, no abstracts, unfilterable)
  - Semantic Scholar (429 rate-limited)
  - SSRN (Cloudflare-blocked), GitHub (mixed quality), RePEc (no API)

Every paper indexed gets a tier rating:
  - Tier A: Peer-reviewed journal
  - Tier B: Preprint (arXiv, SSRN)
  - Tier C: Working paper / report (supplementary only)
"""
import json, os, re, time, xml.etree.ElementTree as ET, sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(ROOT, "papers")
OUT_MD = os.path.join(PAPERS_DIR, "arxiv")
INDEX_PATH = os.path.join(PAPERS_DIR, "index.json")
os.makedirs(OUT_MD, exist_ok=True)

UA = "crypto-research-collector/0.1 (+https://github.com/user)"
_DELAY = 0.35  # OpenAlex ~3 req/s
_ARXIV_DELAY = 3.0  # arXiv rate limit ~1 req/3s

# ── Tier-1 keywords (crypto-specific) ──
CRYPTO_KW = {
    "cryptocurrency", "crypto", "cryptocurrencies",
    "bitcoin", "btc", "ethereum", "eth",
    "blockchain", "defi", "decentralized finance",
    "token", "nft", "non-fungible token",
    "stablecoin", "on-chain", "onchain",
    "crypto-asset", "cryptoasset", "altcoin",
    "proof of stake", "proof of work", "pos network",
    "wallet", "mining",
}

# ── Tier-2 keywords (trading/finance: at least one required alongside Tier-1) ──
TRADING_KW = {
    "trading", "market", "price", "prediction", "forecast",
    "portfolio", "risk", "liquidity", "volatility",
    "microstructure", "sentiment", "arbitrage", "momentum",
    "execution", "hedging", "hedge", "order book", "limit order",
    "investment", "returns", "valuation", "pricing",
    "derivative", "futures", "options", "swap", "yield",
    "return", "profit", "loss", "drawdown",
    "signal", "alpha", "beta", "factor",
    "efficiency", "bubble", "crash",
}

# ── OpenAlex queries (15 crypto-trading topics) ──
OPENALEX_QUERIES = [
    "cryptocurrency trading strategy machine learning",
    "Bitcoin price prediction deep learning",
    "crypto market microstructure liquidity",
    "crypto sentiment analysis trading",
    "cryptocurrency risk management portfolio",
    "DeFi trading liquidity automated market maker",
    "crypto on-chain metrics predictive",
    "crypto arbitrage efficiency",
    "crypto momentum mean reversion",
    "blockchain market quality microstructure",
    "crypto limit order book",
    "algorithmic crypto trading execution",
    "crypto volatility forecasting",
    "crypto derivatives hedging",
    "crypto asset pricing factor",
]

# ── arXiv q-fin queries (category-filtered) ──
ARXIV_QUERIES = [
    "cat:q-fin.*+AND+all:crypto",
    "cat:q-fin.*+AND+all:bitcoin",
    "cat:q-fin.*+AND+all:blockchain+market",
    "cat:q-fin.*+AND+all:cryptocurrency+trading",
    "cat:q-fin.*+AND+(all:defi+OR+all:decentralized+finance)",
    "cat:cs.CE+AND+all:crypto+trading",
    "cat:cs.LG+AND+all:cryptocurrency+trading",
]


# ── Helpers ──
def is_crypto_trading(title: str, abstract: str = "") -> bool:
    """Strict two-layer relevance check. Requires BOTH a crypto keyword AND a
    trading/finance keyword in the title (or abstract as fallback)."""
    t = (title or "").lower()
    a = (abstract or "").lower()
    # Layer 1: crypto keyword must appear in title OR abstract
    has_crypto = any(kw in t for kw in CRYPTO_KW) or any(kw in a for kw in CRYPTO_KW)
    if not has_crypto:
        return False
    # Layer 2: trading/finance keyword must appear in title OR abstract
    has_trading = any(kw in t for kw in TRADING_KW) or any(kw in a for kw in TRADING_KW)
    return has_trading


def infer_tier(source: str, publisher: str = "") -> str:
    """Assign quality tier based on source and publisher."""
    src = (source or "").lower()
    pub = (publisher or "").lower()
    if any(p in pub for p in [
        "elsevier", "springer", "ieee", "acm", "oxford university",
        "cambridge university", "taylor & francis", "sage",
        "wiley", "mdpi", "frontiers", "peerj", "plos",
        "american economic", "journal of finance", "ssrn",
        "henry stewart", "world scientific",
    ]):
        return "A"
    if "arxiv" in src or "ssrn" in src:
        return "B"
    return "C"


def safe_slug(s, limit=60):
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", s.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:limit] or "untitled"


def save_index(index_data):
    index_data["updated"] = datetime.now(timezone.utc).isoformat()
    index_data["count"] = len(index_data["papers"])
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, default=str)
    snap = os.path.join(PAPERS_DIR, "arxiv_latest.json")
    with open(snap, "w", encoding="utf-8") as f:
        json.dump({
            "fetched": datetime.now(timezone.utc).isoformat(),
            "items": index_data["papers"],
        }, f, indent=2, default=str)
    return INDEX_PATH


def load_index():
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"updated": "", "count": 0, "papers": []}


# ── OpenAlex collector ──
def _fetch(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return {"error": str(e)}
    return {"error": "max retries"}


def decode_abstract(inv_index):
    if not inv_index:
        return ""
    words = []
    for token, positions in inv_index.items():
        for pos in positions:
            words.append((pos, token))
    words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in words)


def write_openalex_md(path, work, query):
    title = (work.get("title") or "Untitled").strip()
    authors = ", ".join(
        (a.get("author") or {}).get("display_name", "Unknown")
        for a in (work.get("authorships") or [])
    )
    doi = work.get("doi") or ""
    url = doi or f"https://openalex.org/{work.get('id', '')}"
    year = work.get("publication_year", "")
    abstract = decode_abstract(work.get("abstract_inverted_index"))
    source_name = (work.get("primary_location") or {}).get("source") or {}
    pub_display = source_name.get("display_name", "OpenAlex")
    tier = infer_tier("openalex", pub_display)

    content = f"""---
title: '{title.replace("'", "''")}'
authors: '{authors.replace("'", "''")}'
url: '{url}'
source: 'openalex/{pub_display}'
query: '{query}'
retrieved: '{datetime.now(timezone.utc).isoformat()}'
year: '{year}'
doi: '{doi}'
tier: '{tier}'
category: 'pending_tag'
---

# {title}

- **Source**: OpenAlex ({pub_display})
- **Tier**: {tier} {'(peer-reviewed)' if tier == 'A' else '(preprint)' if tier == 'B' else '(supplementary)'}
- **Year**: {year}
- **DOI**: {doi}

## Abstract
{abstract[:2500] if abstract else '(No abstract available)'}

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk / execution.

## Notes

"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def collect_openalex(index_data, existing_urls, existing_titles):
    total_new = 0
    total_rejected = 0

    for query in OPENALEX_QUERIES:
        time.sleep(_DELAY)
        url_q = query.replace(" ", "+")
        url = (f"https://api.openalex.org/works?search={url_q}&per_page=8"
               f"&sort=relevance_score:desc&select=id,doi,title,authorships,"
               f"publication_year,primary_location,abstract_inverted_index")
        data = _fetch(url)
        if not isinstance(data, dict) or "error" in data:
            print(f"  [OA] ERROR {query}: {data.get('error', 'unknown')}")
            continue

        results = data.get("results") or []
        if not results:
            continue

        for work in results:
            title = (work.get("title") or "").strip()
            doi = work.get("doi") or ""
            url_work = doi or f"openalex-{work.get('id', '')}"
            abstract = decode_abstract(work.get("abstract_inverted_index"))

            # Dedup (URL + title + near-duplicate word-overlap)
            if url_work in existing_urls:
                continue
            if title.lower().strip() in existing_titles:
                continue
            new_words = set(re.findall(r"[a-zA-Z0-9]+", (title or "").lower()))
            if len(new_words) > 2:
                is_near = False
                for existing in existing_titles:
                    existing_words = set(re.findall(r"[a-zA-Z0-9]+", existing))
                    if len(existing_words) > 2:
                        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
                        if overlap >= 0.80:
                            is_near = True
                            break
                if is_near:
                    total_rejected += 1
                    continue

            # Strict relevance filter (two-layer)
            if not is_crypto_trading(title, abstract):
                total_rejected += 1
                continue

            # Write paper
            path = os.path.join(OUT_MD, f"oa-{safe_slug(title, 50)}-{safe_slug(query, 15)}.md")
            write_openalex_md(path, work, query)

            author_str = ", ".join(
                (a.get("author") or {}).get("display_name", "Unknown")
                for a in (work.get("authorships") or [])
            ) or "Unknown"

            entry = {
                "path": path,
                "title": title,
                "authors": author_str,
                "url": url_work,
                "query": query,
                "tag": safe_slug(query, 15),
                "source": "openalex",
                "year": work.get("publication_year"),
                "tier": infer_tier("openalex",
                    ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")),
            }
            index_data["papers"].append(entry)
            existing_urls.add(url_work)
            existing_titles.add(title.lower().strip())
            total_new += 1

        print(f"  [OA] {query[:45]}: ...")

    return index_data, total_new, total_rejected


# ── arXiv q-fin collector ──
def _fetch_arxiv(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code == 429:
                time.sleep(5 ** attempt)
                continue
            return f"ERROR:HTTP {e.code}"
        except Exception as e:
            if attempt < retries:
                time.sleep(3 ** attempt)
                continue
            return f"ERROR:{e}"
    return "ERROR:max retries"


def parse_arxiv_entries(xml_text):
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", "", ns) or "").strip()
        title = re.sub(r"\s+", " ", title)
        link = entry.find("atom:id", ns)
        summary = (entry.findtext("atom:summary", "", ns) or "").strip()
        updated = entry.findtext("atom:updated", "", ns) or ""
        authors = ", ".join(
            (a.findtext("atom:name", "", ns) or "").strip()
            for a in entry.findall("atom:author", ns)
        )
        cats = [c.get("term", "") for c in entry.findall("atom:category", ns)]
        out.append({
            "title": title,
            "url": link.text.strip() if link is not None and link.text else "",
            "authors_raw": authors,
            "updated": updated,
            "summary": summary,
            "categories": cats,
        })
    return out


def write_arxiv_md(path, item, query):
    title = (item.get("title") or "Untitled").strip()
    authors = item.get("authors_raw", "")
    url = item.get("url", "")
    updated = (item.get("updated") or "").split("T")[0]
    summary = (item.get("summary") or "")[:2500]
    cats = " ".join(item.get("categories", []))
    content = f"""---
title: '{title.replace("'", "''")}'
authors: '{authors.replace("'", "''")}'
url: '{url}'
source: 'arxiv/{cats}'
query: '{query}'
retrieved: '{datetime.now(timezone.utc).isoformat()}'
updated: '{updated}'
categories: '{cats}'
tier: 'B'
category: 'pending_tag'
---

# {title}

- **Source**: arXiv ({cats})
- **Tier**: B (preprint)
- **Updated**: {updated}
- **URL**: {url}

## Abstract
{summary}

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk / execution.

## Notes

"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def collect_arxiv(index_data, existing_urls, existing_titles):
    total_new = 0
    total_rejected = 0

    for query in ARXIV_QUERIES:
        time.sleep(_ARXIV_DELAY)
        url = (f"https://export.arxiv.org/api/query?search_query={query}"
               f"&start=0&max_results=10&sortBy=submittedDate")
        xml = _fetch_arxiv(url)
        if xml.startswith("ERROR"):
            print(f"  [AR] ERROR {query[:40]}: {xml[:60]}")
            continue

        entries = parse_arxiv_entries(xml)
        if not entries:
            continue

        for item in entries:
            title = (item.get("title") or "").strip()
            url_work = item.get("url", "")
            abstract = item.get("summary", "")

            # Dedup (URL + title + near-duplicate word-overlap)
            if url_work in existing_urls:
                continue
            if title.lower().strip() in existing_titles:
                continue
            new_words = set(re.findall(r"[a-zA-Z0-9]+", (title or "").lower()))
            if len(new_words) > 2:
                is_near = False
                for existing in existing_titles:
                    existing_words = set(re.findall(r"[a-zA-Z0-9]+", existing))
                    if len(existing_words) > 2:
                        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
                        if overlap >= 0.80:
                            is_near = True
                            break
                if is_near:
                    total_rejected += 1
                    continue

            # Strict two-layer relevance filter
            if not is_crypto_trading(title, abstract):
                total_rejected += 1
                continue

            path = os.path.join(OUT_MD, f"ar-{safe_slug(title, 50)}-{safe_slug(query, 15)}.md")
            write_arxiv_md(path, item, query)

            entry = {
                "path": path,
                "title": title,
                "authors": item.get("authors_raw", "Unknown"),
                "url": url_work,
                "query": query,
                "tag": safe_slug(query, 15),
                "source": "arxiv",
                "year": item.get("updated", "")[:4] if item.get("updated") else "",
                "tier": "B",
            }
            index_data["papers"].append(entry)
            existing_urls.add(url_work)
            existing_titles.add(title.lower().strip())
            total_new += 1

        print(f"  [AR] {query[:40]}: +{len([e for e in entries if is_crypto_trading(e.get('title',''), e.get('summary',''))])} relevant / {len(entries)} total")

    return index_data, total_new, total_rejected


# ── Main ──
def main():
    index_data = load_index()
    existing_urls = {p.get("url") for p in index_data.get("papers", []) if p.get("url")}
    existing_titles = {p.get("title", "").lower().strip() for p in index_data.get("papers", [])}

    print(f"Index start: {index_data['count']} papers")

    # Source 1: OpenAlex (peer-reviewed)
    print("\n── OpenAlex ──")
    index_data, oa_new, oa_rej = collect_openalex(index_data, existing_urls, existing_titles)
    existing_urls = {p.get("url") for p in index_data["papers"] if p.get("url")}
    existing_titles = {p.get("title", "").lower().strip() for p in index_data["papers"]}

    # Source 2: arXiv q-fin (preprints)
    print("\n── arXiv q-fin ──")
    index_data, ar_new, ar_rej = collect_arxiv(index_data, existing_urls, existing_titles)

    # Save updated index
    save_index(index_data)

    total_new = oa_new + ar_new
    total_rejected = oa_rej + ar_rej

    print(f"\nResults: +{total_new} papers added, {total_rejected} rejected as non-crypto-trading")
    print(f"  OpenAlex: +{oa_new} new, {oa_rej} rejected")
    print(f"  arXiv:    +{ar_new} new, {ar_rej} rejected")
    print(f"  Index total: {index_data['count']} papers")
    print(f"\nNoise sources NOT queried: CrossRef, Semantic Scholar, SSRN, GitHub, RePEc")

    return 0

if __name__ == "__main__":
    sys.exit(main())
