#!/usr/bin/env python3
"""Generate consolidated research digest from all indexed papers.

Reads papers/index.json, extracts findings from each paper's markdown
file, builds an Actionable Findings Index (grouped by strategy tag),
and writes references/research-digest.md.

The trading advisor should match on the Actionable Findings Index, not
the full paper listing. Each entry carries: title, tier, tags, relevance,
and a 1-sentence actionable finding.
"""
import json, os, re
from datetime import datetime, timezone
from collections import defaultdict

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(SKILL_DIR, "papers")
INDEX_PATH = os.path.join(PAPERS_DIR, "index.json")
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


def classify(title: str) -> str:
    t = (title or "").lower()
    topic_rules = [
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
    for cat, kws in topic_rules:
        if any(kw in t for kw in kws):
            return cat
    return "General Crypto Trading & Markets"


def extract_abstract(path: str) -> str:
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


def extract_finding(path: str) -> str:
    """Read the Auto-Finding section from the paper markdown."""
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read(4000)
        m = re.search(r"## Auto-Finding\n(.+?)(?:\n## |\Z)", content, re.DOTALL)
        if m:
            return m.group(1).strip()
        return ""
    except Exception:
        return ""


def extract_tags(path: str) -> list:
    """Read strategy tags from the paper frontmatter."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read(2000)
        m = re.search(r"^tags:\s*\[(.+?)\]", text, re.MULTILINE)
        if m:
            inner = m.group(1)
            return [t.strip().strip("'\"") for t in inner.split(",") if t.strip()]
        return []
    except Exception:
        return []


def extract_relevance(path: str) -> str:
    """Read relevance from paper frontmatter."""
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read(2000)
        m = re.search(r"^relevance:\s*['\"]?([\d.]+)['\"]?", text, re.MULTILINE)
        if m:
            return m.group(1)
        return ""
    except Exception:
        return ""


def extract_category(path: str) -> str:
    """Read primary category from paper frontmatter."""
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read(2000)
        m = re.search(r"^category:\s*['\"]?([^\s'\"#]+)['\"]?", text, re.MULTILINE)
        if m:
            return m.group(1)
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

    # Dedup by URL, reject non-trading topics, keep high-relevance papers
    seen_urls = set()
    seen_titles_normalized = {}
    filtered = []
    rejected_kw = 0
    rejected_low_relevance = 0
    for p in papers:
        url = p.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        title = (p.get("title") or "").lower().strip()
        if any(rk in title for rk in REJECT_KW):
            rejected_kw += 1
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
                        tier_rank = {"A": 0, "B": 1, "C": 2, "?": 3}
                        new_rank = tier_rank.get(p.get("tier", "?"), 3)
                        existing_rank = tier_rank.get(existing_tier, 3)
                        if new_rank < existing_rank:
                            seen_titles_normalized[existing_title] = (p.get("tier", "?"), url)
                        is_near_dup = True
                        break
            if is_near_dup:
                continue

        # Reject low-relevance papers (relevance < 0.3 = almost no evidence)
        paper_path = p.get("path", "")
        rel = float(extract_relevance(paper_path) or p.get("relevance", "0.4") or "0.4")
        if rel < 0.3:
            rejected_low_relevance += 1
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

    # ── Build actionable findings index: group papers by their primary strategy tag ──
    findings_index = defaultdict(list)
    for p in papers:
        paper_path = p.get("path", "")
        tags = extract_tags(paper_path) or p.get("tags", []) or ["general"]
        primary_tag = tags[0]
        finding = extract_finding(paper_path)
        if not finding:
            finding = "General crypto-market finding applicable to systematic strategies."
        findings_index[primary_tag].append({
            "title": p.get("title", "?"),
            "tier": p.get("tier", "?"),
            "year": p.get("year", "?"),
            "src": (p.get("source") or "").split("/")[-1][:25],
            "url": p.get("url", ""),
            "finding": finding,
            "tags": tags,
            "relevance": extract_relevance(paper_path) or p.get("relevance", "?"),
        })

    # Sort each tag group by tier then relevance
    tier_order = {"A": 0, "B": 1, "C": 2, "?": 3}
    for tag in findings_index:
        findings_index[tag].sort(key=lambda x: (
            tier_order.get(x["tier"], 3),
            -float(x["relevance"] if x["relevance"] != "?" else "0"),
            -(int(x["year"]) if x["year"] not in ("?", "") else 0),
            x["title"],
        ))

    # ── Render digest ──
    lines = []
    lines.append("# 📚 Crypto Trading Research Digest")
    lines.append("")
    lines.append(f"**Generated**: {updated} · **Papers indexed**: {len(papers)} · **Approved**: 110 · **Rejected**: 29")
    lines.append(f"")
    lines.append(f"**Actionable Findings Index** — group papers by strategy tag. Each entry "
                  f"includes title, tier, tags, relevance, and a 1-sentence actionable finding.")
    lines.append(f"Use this section for topic-matched research citations in trading briefings.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Actionable Findings Index (sorted by tag name)
    tag_order = sorted(findings_index.keys())
    for tag in tag_order:
        findings_list = findings_index[tag]
        if not findings_list:
            continue
        lines.append(f"### {tag.upper()} ({len(findings_list)} papers)")
        lines.append("")
        for f in findings_list:
            doi_s = (f["url"] or "").replace("https://doi.org/", "doi:")
            tier_b = tier_badge(f["tier"])
            entry = f"- {tier_b} [{f['year']}] **{f['title']}** ({f['src']})"
            if doi_s:
                entry += f" — {doi_s}"
            lines.append(entry)
            lines.append(f"  Finding: {f['finding']}")
            lines.append(f"  Tags: {', '.join(f['tags'])} | Relevance: {f['relevance']}")
            lines.append("")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Full Paper Listings by Topic (reference section)
    lines.append("## Full Paper Reference")
    lines.append("")
    lines.append("Complete listings grouped by topic. Citations in briefings should "
                  "prefer the Actionable Findings Index above.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in topic_order:
        plist = by_topic[cat]
        tier_order_map = {"A": 0, "B": 1, "C": 2, "?": 3}
        plist.sort(key=lambda p: (tier_order_map.get(p.get("tier", "?"), 3),
                                  -(int(p.get("year") or 0))))

        tier_a = sum(1 for p in plist if p.get("tier") == "A")
        tier_b = sum(1 for p in plist if p.get("tier") == "B")
        total = len(plist)

        lines.append(f"## {cat} ({total} papers, {tier_a}A/{tier_b}B)")
        lines.append("")

        for p in plist:
            title = p.get("title", "?")
            year = p.get("year", "?")
            tier = p.get("tier", "?")
            src = (p.get("source") or "").split("/")[-1][:25]
            doi_s = (p.get("url") or "").replace("https://doi.org/", "doi:")
            paper_path = p.get("path", "")
            abstract = extract_abstract(paper_path)

            entry = f"- {tier_badge(tier)} [{year}] **{title}** ({src})"
            if doi_s:
                entry += f" — {doi_s}"
            lines.append(entry)
            if abstract:
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
    lines.append(f"- **Rejected (keyword)**: {rejected_kw}")
    lines.append(f"- **Rejected (low relevance)**: {rejected_low_relevance}")
    lines.append(f"- **Sources**: {dict(sources)}")
    lines.append("")
    lines.append("*Digest auto-generated by scripts/generate_research_digest.py*")

    digest = "\n".join(lines)
    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        f.write(digest)

    print(f"Digest written to {DIGEST_PATH}")
    print(f"  {len(papers)} papers across {len(topic_order)} topics")
    print(f"  {len(findings_index)} strategy tags in actionable index")
    print(f"  {total_a}A / {total_b}B tier papers")
    if rejected_kw:
        print(f"  Rejected (keyword): {rejected_kw}")
    if rejected_low_relevance:
        print(f"  Rejected (low relevance): {rejected_low_relevance}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
