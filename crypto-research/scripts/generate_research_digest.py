#!/usr/bin/env python3
"""Generate consolidated research digest from all indexed papers.

Reads papers/index.json, extracts key findings from each paper's markdown
file, groups by topic, and writes a single references/research-digest.md
that the trading advisor can use for citation-backed decision making.
"""
import json, os, re
from datetime import datetime, timezone
from collections import defaultdict

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(SKILL_DIR, "papers", "arxiv")
INDEX_PATH = os.path.join(SKILL_DIR, "papers", "index.json")
DIGEST_PATH = os.path.join(SKILL_DIR, "references", "research-digest.md")
os.makedirs(os.path.dirname(DIGEST_PATH), exist_ok=True)

# Explicit reject list — papers about security, malware, NFT marketing, etc.
REJECT_KW = [
    "ransomware", "malware", "attack detection", "cyber",
    "crypto-book", "crypto pagan", "crypto-pagan",
    "nft terms", "nft used in", "nft marketing",
    "smart contract security", "vulnerability",
    "cryptograph", "quantum key", "post-quantum",
    "privacy-preserv", "zero-knowledge",
    "consensus algorithm", "sharding", "scalability",
    "geometric gradient", "semi-supervised",
    "stochastic gradient",
]

# Topic classifier
TOPIC_RULES = [
    ("Price Prediction & Forecasting", ["price", "prediction", "forecast", "predicting", "predictive"]),
    ("Sentiment Analysis", ["sentiment", "social media", "twitter", "news", "tweet"]),
    ("Market Microstructure & Liquidity", ["microstructure", "order book", "limit order", "liquidity", "market quality"]),
    ("Risk Management & Volatility", ["risk", "volatility", "drawdown", "hedging", "hedge", "portfolio", "variance"]),
    ("DeFi & Automated Market Makers", ["defi", "decentralized finance", "amm", "automated market", "uniswap"]),
    ("Arbitrage & Market Efficiency", ["arbitrage", "efficiency", "pricing", "market efficiency"]),
    ("Trading Strategies & Execution", ["trading", "strategy", "momentum", "signal", "execution", "alpha"]),
    ("On-Chain & Blockchain Analytics", ["on-chain", "onchain", "blockchain", "wallet", "proof of stake"]),
    ("Derivatives & Futures", ["futures", "derivative", "options", "swap"]),
    ("Crypto as Asset Class", ["bitcoin is not", "correlation", "safe haven", "diversif", "asset class", "commonality"]),
]


def classify(title: str) -> str:
    t = (title or "").lower()
    for cat, kws in TOPIC_RULES:
        if any(kw in t for kw in kws):
            return cat
    return "General Crypto Trading & Markets"


def extract_abstract(path: str) -> str:
    """Read the first ~200 chars of the Abstract/Summary section from markdown."""
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read(4000)
        m = re.search(r"## (?:Abstract|Summary)\n(.+?)(?:\n## |\Z)", content, re.DOTALL)
        if m:
            text = m.group(1).strip().replace("\n", " ")[:300]
            return text
        return ""
    except Exception:
        return ""


def tier_badge(tier: str) -> str:
    return {"A": "🟢 Tier A", "B": "🟡 Tier B", "C": "⭕ Tier C"}.get(tier, f"Tier {tier}")


def main():
    if not os.path.exists(INDEX_PATH):
        print(f"Index not found: {INDEX_PATH}")
        return 1

    with open(INDEX_PATH, encoding="utf-8") as f:
        idx = json.load(f)

    papers = idx.get("papers", [])
    updated = idx.get("updated", datetime.now(timezone.utc).isoformat())[:10]

    # Dedup by URL, reject non-trading topics
    seen_urls = set()
    seen_titles_normalized = {}  # normalized title -> tier + url
    filtered = []
    for p in papers:
        url = p.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        title = (p.get("title") or "").lower().strip()
        if any(rk in title for rk in REJECT_KW):
            continue

        # Near-duplicate check: >80% word overlap with existing papers
        words = set(re.findall(r"[a-zA-Z0-9]+", title))
        if len(words) > 2:
            is_near_dup = False
            for existing_title, (existing_tier, existing_url) in list(seen_titles_normalized.items()):
                existing_words = set(re.findall(r"[a-zA-Z0-9]+", existing_title))
                if len(words) > 2 and len(existing_words) > 2:
                    overlap = len(words & existing_words) / max(len(words), len(existing_words))
                    if overlap >= 0.80:
                        # Same paper — keep the one with better tier
                        tier_rank = {"A": 0, "B": 1, "C": 2, "?": 3}
                        new_rank = tier_rank.get(p.get("tier", "?"), 3)
                        existing_rank = tier_rank.get(existing_tier, 3)
                        if new_rank < existing_rank:
                            # New one has better tier — replace existing
                            seen_titles_normalized[existing_title] = (p.get("tier", "?"), url)
                        is_near_dup = True
                        break
            if is_near_dup:
                continue

        seen_titles_normalized[title] = (p.get("tier", "?"), url)
        filtered.append(p)
    papers = filtered

    # Group by topic
    by_topic = defaultdict(list)
    for p in papers:
        cat = classify(p.get("title", ""))
        by_topic[cat].append(p)

    # Sort topics by total count descending, then by Tier A count
    topic_order = sorted(
        by_topic.keys(),
        key=lambda c: (
            -sum(1 for p in by_topic[c] if p.get("tier") == "A"),
            -len(by_topic[c]),
            c,
        ),
    )

    lines = []
    lines.append(f"# 📚 Crypto Trading Research Digest")
    lines.append(f"")
    lines.append(f"**Generated**: {updated} · **Papers indexed**: {len(papers)}")
    lines.append(f"")
    lines.append(f"This digest consolidates all validated research papers for the trading advisor.")
    lines.append(f"Papers are grouped by topic and sorted by quality tier (A → B → C), then by year (newest first).")
    lines.append(f"Tier A = peer-reviewed journal · Tier B = preprint · Tier C = supplementary")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for cat in topic_order:
        plist = by_topic[cat]
        # Sort: tier A first, then year descending
        tier_order = {"A": 0, "B": 1, "C": 2, "?": 3}
        plist.sort(key=lambda p: (tier_order.get(p.get("tier", "?"), 3), -(int(p.get("year") or 0))))

        tier_a = sum(1 for p in plist if p.get("tier") == "A")
        tier_b = sum(1 for p in plist if p.get("tier") == "B")
        total = len(plist)

        lines.append(f"## {cat} ({total} papers, {tier_a}A/{tier_b}B)")
        lines.append(f"")

        for p in plist:
            title = p.get("title", "?")
            year = p.get("year", "?")
            tier = p.get("tier", "?")
            src = (p.get("source") or "").split("/")[-1][:25]
            doi_s = (p.get("url") or "").replace("https://doi.org/", "doi:")
            abstract = extract_abstract(p.get("path", ""))

            entry = f"- {tier_badge(tier)} [{year}] **{title}** ({src})"
            if doi_s:
                entry += f" — {doi_s}"
            lines.append(entry)
            if abstract:
                # Truncate cleanly
                ab_short = abstract[:200]
                if len(abstract) > 200:
                    ab_short = ab_short[:ab_short.rfind(" ")] + "…"
                lines.append(f"  > {ab_short}")
            lines.append("")

        lines.append("")

    # Stats block
    total_a = sum(1 for p in papers if p.get("tier") == "A")
    total_b = sum(1 for p in papers if p.get("tier") == "B")
    sources = defaultdict(int)
    for p in papers:
        s = (p.get("source") or "?").split("/")[0][:20]
        sources[s] += 1

    lines.append("---")
    lines.append("## Stats")
    lines.append(f"- **Total papers**: {len(papers)}")
    lines.append(f"- **Tier A (peer-reviewed)**: {total_a}")
    lines.append(f"- **Tier B (preprint)**: {total_b}")
    lines.append(f"- **Sources**: {dict(sources)}")
    lines.append("")
    lines.append("*Digest auto-generated by scripts/generate_research_digest.py*")

    digest = "\n".join(lines)
    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        f.write(digest)

    print(f"Digest written to {DIGEST_PATH}")
    print(f"  {len(papers)} papers across {len(topic_order)} topics")
    print(f"  {total_a}A / {total_b}B tier papers")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
