# Noise Paper Pollution Incident — 2026-06-30

## Summary
125 noise papers polluted `papers/index.json` with incomplete metadata (`source=None`, `tier=None`, `category=None`, `tags=None`). These appeared in the digest as "GENERAL" entries with `Tier ? [?]` and placeholder findings.

## Root Cause
The **deprecated** collector `scripts/collect_papers.py` (old arXiv-only collector) was run at some point and produced papers with:
- `source: 'arxiv'` (string) but incomplete frontmatter
- `category: 'pending_tag'`, `relevance: 'tbd'`, **no `tags` field**
- Used `ti:` (title-only) arXiv search format which returns 0 relevant results
- The query `"cryptocurrency trading strategy"` matched papers with no crypto/trading content

The new collector `scripts/collect_papers_openalex.py` expects complete frontmatter with `category`, `relevance`, `tags`, and `source: 'arxiv'` or `'openalex'`. The `cleanup_orphans()` function only removes `.md` files not tracked in the index — it does **not** clean stale index entries.

## Detection
```bash
# Index count mismatch
python3 -c "import json; d=json.load(open('papers/index.json')); print(d['count'], len(d['papers']))"
# Output: 240 115  ← count field drifted

# Noise papers
python3 -c "import json; d=json.load(open('papers/index.json')); print([p for p in d['papers'] if p.get('source') is None])"
# 125 entries with source=None
```

## Remediation Steps
```bash
# 1. Remove noise from index.json
python3 -c "
import json
with open('papers/index.json') as f:
    data = json.load(f)
data['papers'] = [p for p in data['papers'] if p.get('source') is not None]
data['count'] = len(data['papers'])
with open('papers/index.json', 'w') as f:
    json.dump(data, f, indent=2)
"

# 2. Delete orphan .md files from disk
python3 -c "
import os, re
PAPERS_DIR = 'papers/arxiv'
for f in os.listdir(PAPERS_DIR):
    if not f.endswith('.md'): continue
    with open(os.path.join(PAPERS_DIR, f)) as fh:
        text = fh.read(2000)
    m = re.search(r\"^query:\\s*['\\\"]?([^'\\\"]+)['\\\"]?\", text, re.MULTILINE)
    if m and m.group(1) == 'cryptocurrency trading strategy':
        os.remove(os.path.join(PAPERS_DIR, f))
"

# 3. Regenerate digest
python3 scripts/generate_research_digest.py
```

## Prevention
- **Never run `collect_papers.py`** — it is deprecated (`DEPRECATED` comment in file)
- After any manual index edit: run `scripts/sync_index_fields.py` AND verify `index.json['count'] == len(index.json['papers'])`
- The daily cron (`research-playbook-enrichment`) uses only `collect_papers_openalex.py`
- If `index.json` count drifts from actual paper list length, audit and clean before next digest generation
- Spot-check Tier B/C papers after major enrichment for noise (book reviews, ML papers with "crypto" in passing, etc.)

## Files Modified
- `papers/index.json` — cleaned, count fixed (240 → 115)
- `papers/arxiv/*.md` — 15 orphan noise files deleted
- `references/research-digest.md` — regenerated clean (110 papers, 10 strategy tags)