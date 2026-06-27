#!/usr/bin/env python3
"""Query collected crypto research papers by concept, with tier-prioritized results.

Usage:
  python3 query_papers.py <concept> [--limit N] [--source journal|arxiv] [--min-tier B]

Returns results sorted by quality tier (A → B → C), then by relevance score.
Only returns papers whose TITLE or SOURCE matches the concept — the old `query`
tag field is NOT used for matching to prevent false-positive noise.
"""
import os, sys, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "papers", "index.json")
PAPERS_DIR = os.path.join(ROOT, "papers", "arxiv")

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "?": 3}


def read_index():
    if os.path.exists(INDEX):
        with open(INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("papers", [])
        if items:
            return items
    return None


def relevance_score(item, concept):
    """Score 0-3: higher = more relevant. Checks each word in concept against
    title and source fields individually. This catches 'bitcoin price prediction'
    when searching 'bitcoin trading' because both words appear in the title."""
    title = (item.get("title") or "").lower()
    source = (item.get("source") or item.get("tag") or "").lower()
    doi = (item.get("url") or "").lower()

    if not concept:
        return 1

    words = [w.strip() for w in concept.lower().split() if len(w.strip()) > 2]
    if not words:
        return 0

    # Score: count how many concept words appear in title
    title_matches = sum(1 for w in words if w in title)
    source_matches = sum(1 for w in words if w in source)

    if title_matches == len(words):
        return 3  # all words in title = best match
    if title_matches >= 1:
        return 2 + (title_matches / len(words))  # partial title match
    if source_matches >= 1:
        return 1  # source match only
    return 0


def main():
    args = sys.argv[1:]
    limit = 10
    filter_source = None
    min_tier = None
    concept = None

    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
            continue
        if args[i] == "--source" and i + 1 < len(args):
            filter_source = args[i + 1]
            i += 2
            continue
        if args[i] == "--min-tier" and i + 1 < len(args):
            min_tier = args[i + 1].upper()
            i += 2
            continue
        if concept is None:
            concept = args[i]
        i += 1

    items = read_index()
    if items is None:
        items = []

    results = []
    for item in items:
        # Source filter
        if filter_source:
            src = (item.get("source") or item.get("tag") or "").lower()
            if filter_source.lower() not in src:
                continue

        # Min tier filter
        if min_tier:
            item_tier = (item.get("tier") or "?").upper()
            if TIER_ORDER.get(item_tier, 3) > TIER_ORDER.get(min_tier, 3):
                continue

        # Concept match (search in TITLE and SOURCE only — NOT in query tag)
        if concept:
            score = relevance_score(item, concept)
            if score == 0:
                continue  # concept not found in title or source
        else:
            score = 1

        tier = (item.get("tier") or "?").upper()
        results.append((TIER_ORDER.get(tier, 3), -score, item))

    # Sort by tier (A first), then by relevance descending, then by year descending
    results.sort(key=lambda x: (x[0], x[1], -(x[2].get("year") or 0)))
    results = [r[2] for r in results[:limit]]

    print(
        json.dumps(
            {
                "available": len(items),
                "filtered": len(results),
                "query": {
                    "text": concept,
                    "source": filter_source,
                    "min_tier": min_tier,
                    "limit": limit,
                },
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
