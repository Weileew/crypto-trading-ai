#!/usr/bin/env python3
"""Collect crypto trading research metadata from arXiv into tagged markdown papers."""
import os
import re
import json
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(ROOT, "papers")
OUT_MD = os.path.join(PAPERS_DIR, "arxiv")
os.makedirs(OUT_MD, exist_ok=True)

UA = "crypto-research-collector/0.1"

QUERIES = [
    "cryptocurrency trading strategy",
    "crypto limit order book microstructure",
    "cryptocurrency market liquidity",
    "Bitcoin trading",
    "crypto on-chain metrics",
    "crypto sentiment trading",
    "crypto risk management",
    "crypto momentum mean reversion",
    "Bitcoin predictive signals",
    "crypto exchange liquidity",
    "Ethereum trading",
    "crypto arbitrage",
    "crypto quantitative trading",
]


def fetch(url):
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"ERROR:{e}"


def arxiv_search_xml(query, max_results=15):
    q = query.replace(" ", "+")
    url = f"https://export.arxiv.org/api/query?search_query=ti:{q}&start=0&max_results={max_results}&sortBy=submittedDate"
    return fetch(url)


def parse_entries(xml_text):
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        title = re.sub(r"\s+", " ", title)
        link = entry.find("atom:id", ns)
        authors = [
            (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("atom:author", ns)
        ]
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        updated = entry.findtext("atom:updated", default="", namespaces=ns)
        out.append({
            "title": title,
            "url": (link.text.strip() if link is not None and link.text else None),
            "authors_raw": ", ".join(authors),
            "updated": updated,
            "summary": summary,
        })
    return out


def safe_slug(s, limit=60):
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", s.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:limit] or "untitled"


def paper_path(item, query):
    first = item.get("authors_raw", "").split(",")[0].strip() or "Unknown"
    first = safe_slug(first, 20)
    title = safe_slug(item.get("title", ""), 45)
    name = f"{first} - {title} - {safe_slug(query, 18)}"
    return os.path.join(OUT_MD, f"{name}.md"), first, title, safe_slug(query, 18)


def write_md(path, item, query):
    url = item.get("url") or ""
    authors = item.get("authors_raw") or ""
    updated = item.get("updated") or ""
    summary = item.get("summary") or ""
    content = f"""---
title: '{item.get('title','').replace("'", "''")}'
authors: '{authors.replace("'", "''")}'
url: '{url}'
source: 'arxiv'
query: '{query}'
retrieved: '{datetime.now(timezone.utc).isoformat()}'
updated: '{updated}'
category: 'pending_tag'
relevance: 'tbd'
---

# {item.get('title','')}

## Source
- arXiv: {url}

## Summary
{summary}

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def save_index(index):
    path = os.path.join(PAPERS_DIR, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "count": len(index), "papers": index}, f, indent=2, default=str)
    return path


def main():
    seen = set()
    index = []
    total = 0
    for q in QUERIES:
        xml = arxiv_search_xml(q)
        if xml.startswith("ERROR"):
            print("ERROR", q, xml)
            continue
        entries = parse_entries(xml)
        print("query", q, "entries", len(entries))
        for item in entries:
            url = item.get("url")
            if url and url in seen:
                continue
            seen.add(url)
            path, _, _, tag = paper_path(item, q)
            write_md(path, item, q)
            index.append({
                "path": path,
                "title": item.get("title"),
                "authors": item.get("authors_raw"),
                "url": url,
                "query": q,
                "tag": tag,
            })
            total += 1
    idx_path = save_index(index)
    # Also keep a flat snapshot for compatibility
    snap = os.path.join(PAPERS_DIR, "arxiv_latest.json")
    with open(snap, "w", encoding="utf-8") as f:
        json.dump({"fetched": datetime.now(timezone.utc).isoformat(), "items": index}, f, indent=2, default=str)
    print("Saved", total, "papers to", OUT_MD)
    print("Index:", idx_path)


if __name__ == "__main__":
    main()
