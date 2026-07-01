#!/usr/bin/env python3
"""Sync category/relevance/tags from paper markdown frontmatter into index.json.

See playbook-alpha-pipeline skill's scripts/sync_index_fields.py for canonical source.
This is a managed copy kept in sync.
"""
import json, os, re, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(SKILL_DIR, "papers", "index.json")
PAPERS_DIR = os.path.join(SKILL_DIR, "papers", "arxiv")

if not os.path.exists(INDEX_PATH):
    print(f"Index not found: {INDEX_PATH}")
    sys.exit(1)

with open(INDEX_PATH, encoding="utf-8") as f:
    idx = json.load(f)

papers = idx.get("papers", [])
updated = errors = 0

for p in papers:
    path = p.get("path", "")
    if not path or not os.path.exists(path):
        alt = os.path.join(SKILL_DIR, path)
        if os.path.exists(alt):
            path = alt
        else:
            errors += 1
            continue
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read(2000)
    except Exception:
        errors += 1
        continue

    m = re.search(r"^category:\s*['\"]?([^\s'\"#]+)['\"]?", text, re.MULTILINE)
    category = m.group(1) if m else ""
    m = re.search(r"^relevance:\s*['\"]?([\d.]+)['\"]?", text, re.MULTILINE)
    relevance = float(m.group(1)) if m else 0.0
    m = re.search(r"^tags:\s*\[([^\]]*)\]", text, re.MULTILINE)
    tags = [t.strip().strip("'\"") for t in m.group(1).split(",")] if m else []

    changed = False
    if category and p.get("category") != category:
        p["category"] = category; changed = True
    if relevance and p.get("relevance") != relevance:
        p["relevance"] = relevance; changed = True
    if tags and p.get("tags") != tags:
        p["tags"] = tags; changed = True
    if changed:
        updated += 1

idx["count"] = len(papers)
with open(INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(idx, f, indent=2, ensure_ascii=False)

print(f"Updated {updated} index entries · {errors} errors · {len(papers)} total")

if os.path.isdir(PAPERS_DIR):
    md = [f for f in os.listdir(PAPERS_DIR) if f.endswith(".md")]
    indexed_paths = set(os.path.abspath(p.get("path", "")) for p in papers)
    orphans = sum(1 for f in md if os.path.abspath(os.path.join(PAPERS_DIR, f)) not in indexed_paths)
    print(f"Orphan .md files: {orphans}" if orphans else "No orphans — disk matches index")
