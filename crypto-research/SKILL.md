---
name: crypto-research
description: "Curated crypto trading research module for Hermes Agent. Collects, stores, and references academic and white-paper sources for trading strategy and market structure."
version: 0.3.1
author: user
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cryptocurrency, research, trading]
---

# Crypto Trading Research Module

Collect and maintain research-grade sources for crypto trading strategy, market microstructure, on-chain methods, sentiment frameworks, execution quality, and risk models.

## Goal

Provide a citation-backed knowledge layer that `trading-advisor` can reference before making strategy claims — without searching individual paper files.

## Architecture (Strategy-Tagged Digest)

```
collect_papers_openalex.py  →  generate_research_digest.py  →  references/research-digest.md  →  advisor cites it
        │                              │                              │
   OpenAlex + arXiv q-fin         Actionable Findings Index       score-gated, tag-based match
   strategy_tags() + _auto_finding()  grouped by strategy tag      best_paper_for() ≥0.7 score
```

### Status (2026-06-28 — citation pipeline fixed)

The research citation gap is **closed**. The pipeline now uses tag-based matching with score gating:

| Layer | Status | Detail |
|-------|--------|--------|
| Daily enrichment cron | ✅ Runs, produces papers | `research-playbook-enrichment` (149x…) |
| Strategy tagging at ingestion | ✅ Auto-tags new papers | `strategy_tags()` in collector — momentum, liquidity, sentiment, risk, defi, prediction, arbitrage, execution, crypto, general |
| Auto-Finding generation | ✅ 1-sentence actionable hook | `_auto_finding()` — gated by strategy tag |
| Actionable Findings Index | ✅ 10 strategy tags, 111 papers | `research-digest.md` top section has `Finding:` + `Tags:` + `Relevance:` per entry |
| `best_paper_for()` matching | ✅ Score-gated tag/finding match | Score ≥0.7 for strong citation; tag-match + finding-mention + tier boost |
| Real citations in briefings | ✅ Active | DeFi → defi paper, BTC → prediction paper, ETH → defi paper — all ≥2.0 score |

### How tag-based matching works

The `recommend_term()` function in `briefing.py` dispatches coin names to strategy-domain hint lists:
- **DeFi tokens** (magma, aave, maple, compound) → defi/liquidity/prediction/arbitrage/crypto
- **BTC/bitcoin** → bitcoin/bitcoin prediction/crypto trading/prediction/risk
- **ETH/ethereum** → ethereum/defi/prediction/crypto trading/liquidity
- **Generic crypto** → all 9 strategy tags as fallback

`lookup_research()` scores each entry on four axes:
- +1.0 for primary-tag hit, +0.6 for secondary-tag hit
- +0.4 if the concept word appears in the Finding text
- +0.3 if the concept word appears in the title
- +0.3/.15 tier boost (A/B)

`best_paper_for()` returns results with score ≥0.7 (strong) or any match as weak fallback. Returns `{title, tier_label, finding, tags, score}`. The briefing renderer shows tier_label + finding + tags.

### How the old citation-gap known limitation was fixed

| Problem | Fix | When |
|---------|-----|------|
| Title word-overlap only | Tag + finding + title multi-axis scoring | 2026-06-28 |
| Abstract snippet in digest was ignored | `lookup_research()` now extracts `Finding:` lines from Actionable Findings Index | 2026-06-28 |
| `recommend_term()` generated generic terms | Domain-hinted dispatch: DeFi coins → defi/liquidity/prediction | 2026-06-28 |
| Paper tag field existed but unused | `strategy_tags()` writes `category`/`relevance`/`tags` to paper markdown frontmatter (read by digest generator from files, not index.json) | 2026-06-28 |
| No Auto-Finding in paper files | `_auto_finding()` generates 1-sentence actionable finding per paper | 2026-06-28 |

## Source Standards

Only **two free, no-auth APIs** are queried. All other candidates were systematically tested and rejected as noise.

### ACTIVE Sources

#### Tier A — OpenAlex (peer-reviewed journals)
- Free scholarly index, no auth required, ~3 req/s rate limit
- Fetches 8 top-relevance papers per query across 15 crypto-trading topics
- Returns full abstracts via `abstract_inverted_index` (must decode)
- Publisher detection assigns tier: Elsevier/Springer/IEEE/ACM/Wiley/MDPI/PeerJ/etc → Tier A
- See `references/openalex-api.md` for API details

#### Tier B — arXiv q-fin (preprints)
- Category-filtered on `cat:q-fin.*` (quantitative finance) — without this filter, 100% of results are noise
- Also queries `cs.CE` and `cs.LG` with `all:cryptocurrency+trading`
- ~1 req/3s rate limit; always use `_ARXIV_DELAY = 3.0`
- The old `ti:` (title-only) search format returned 0 results — always use `all:` for full-text
- See `references/openalex-api.md`

### Two-Layer Relevance Filter (MANDATORY)

Every paper MUST pass BOTH layers before indexing. If only one layer matches, the paper is rejected:

| Layer | Keywords checked | Purpose |
|-------|-----------------|---------|
| 1 — Crypto | cryptocurrency, crypto, bitcoin, btc, ethereum, eth, blockchain, defi, token, nft, stablecoin, on-chain, crypto-asset, altcoin, proof of stake | Rejects non-crypto papers (bonds, commodities, general ML) |
| 2 — Trading/Finance | trading, market, price, prediction, forecast, portfolio, risk, liquidity, volatility, microstructure, sentiment, arbitrage, momentum, execution, hedging, order book, limit order, investment, returns, valuation, derivatives, futures | Rejects crypto-security papers (ransomware, cryptography, consensus protocols) |

Checked against title first. If title-only fails, abstract is checked as fallback.

### REJECTED Sources (tested, do not re-test)

| Source | Reason | Signals |
|--------|--------|---------|
| **CrossRef** | 697K results but <1% have abstracts — impossible to generate useful entries | No abstract, can't filter |
| **Semantic Scholar** | 429 Too Many Requests on free tier | Rate-limited even for 1 query |
| **SSRN** | Cloudflare-protected HTML page, no free API | Returns "Just a moment" challenge |
| **GitHub repos** | Only 11 repos for crypto+trading+research query, mixed quality | Too few, unreliable |
| **RePEc** | API endpoint returned 404 | Dead endpoint |
| **arXiv (unfiltered)** | `all:cryptocurrency+trading` returns papers from quantum physics and CS that merely mention "cryptocurrency" in passing | Category filter required (q-fin) |

### Hard Cutoff Rules

- Reject purely memecoin/pump-and-dump case studies
- Reject vague strategy descriptions with no identifiable signal definition or tested parameters
- Reject papers relying on future/out-of-sample claims without proper validation methodology
- Reject sources without clear date and verifiable authors or institution
- Reject duplicates (dedup by URL before indexing)

## Consolidated Digest

`references/research-digest.md` is the **single source of truth** for the advisor. It groups all papers by topic and sorts by quality tier (A → B → C), then by year (newest first).

### Triple-Guard Dedup (near-duplicate aware)

Three independent layers prevent duplicates at every stage of the pipeline:

| Layer | Where | What it catches | Method |
|-------|-------|----------------|--------|
| **1 — Collector** | `collect_papers_openalex.py` | Prevents duplicate papers from entering the index | URL match → exact title match → ≥80% word overlap in title |
| **2 — Digest generator** | `generate_research_digest.py` | Catches duplicates from legacy runs or batch imports | URL match → reject-keyword check → ≥80% word overlap **with tier-aware replacement** (if a preprint and a peer-reviewed version of the same paper exist, keeps the Tier A one) |
| **3 — Index rebuild** | Full regeneration wipe | Resets state by rewriting `research-digest.md` from scratch | Every run starts with an empty `seen_urls` / `seen_titles` set |

**Near-duplicate detection algorithm** (used in layers 1 and 2):
- Tokenize both titles into word sets (lowercased, alphanumeric-only)
- If `len(words_i & words_j) / max(len(words_i), len(words_j)) >= 0.80`, treat as near-duplicate
- On conflict: prefer higher tier (A > B > C), then newer year
- On tier tie: keep whichever was seen first

This catches "journal version" vs "preprint" of the same paper, minor title variations, and re-submissions with slightly different metadata.

### Digest structure (current — Actionable Findings Index format)
```
# Crypto Trading Research Digest

Generated: YYYY-MM-DD · Papers indexed: N · Approved: M · Rejected: K

**Actionable Findings Index** — group papers by strategy tag. Each entry
includes title, tier, tags, relevance, and a 1-sentence actionable finding.

---

### MOMENTUM (N papers)
- 🟢 Tier A [year] **Title** (source) — doi:...
  Finding: <1-sentence actionable hook based on strategy tag>
  Tags: momentum, crypto | Relevance: 0.8

### LIQUIDITY (N papers)
- 🟢 Tier A [year] **Title** (source) — doi:...
  Finding: <finding text>
  Tags: liquidity, risk | Relevance: 0.85

---

## Full Paper Reference
... (topic-grouped listings below for manual browsing)
```

The **Actionable Findings Index** is the section `lookup_research()` in `briefing.py` reads for score-gated matching. The Full Paper Reference is archival only.

### Topic classifier
Papers are automatically classified into: Price Prediction, Sentiment Analysis, Market Microstructure & Liquidity, Risk Management & Volatility, DeFi & Automated Market Makers, Arbitrage & Market Efficiency, Trading Strategies & Execution, On-Chain & Blockchain Analytics, Derivatives & Futures, Crypto as Asset Class, General Crypto Trading & Markets.

### Tier badge meanings
- **🟢 Tier A**: Peer-reviewed journal (Elsevier, Springer, IEEE, ACM, Wiley, MDPI, etc.)
- **🟡 Tier B**: Preprint (arXiv q-fin)
- **⭕ Tier C**: Supplementary (working papers, reports — use only as fallback)

### Lookup function (`briefing.py` → `lookup_research()`)
The `best_paper_for()` function in `trading-advisor/scripts/briefing.py` reads the Actionable Findings Index section of the digest file, scores each entry on tag-match + finding-mention + title-keyword + tier boost, and returns the best match with score ≥0.7 (strong) or any match (weak fallback). Returns `{title, tier_label, finding, tags, score}`. See `trading-advisor` skill → "Research Enrichment" section for full multi-axis scoring details.

## Tag Normalization

- `microstructure` — orderbook, liquidity, execution quality, exchange structure
- `sentiment` — social, news, retail/institutional sentiment signals
- `onchain` — on-chain metrics, wallet flows, miner activity, blockchain analytics
- `strategy` — momentum, mean reversion, pairs trading, systematic strategies
- `risk` — VaR, drawdown, portfolio construction, tail risk, position sizing
- `execution` — slippage, latency, techno-fundamental strategy components

## Cron Automation

A daily cron job `research-playbook-enrichment` (ID `49dfd654806a`) runs at **05:30 UTC+7** from the crypto-research skill directory. It executes in order:

1. `scripts/collect_papers_openalex.py` — fetches new papers from OpenAlex + arXiv q-fin, applies two-layer filter, updates `papers/index.json`
2. `scripts/generate_research_digest.py` — regenerates `references/research-digest.md` from the updated index (dedups by URL, applies reject keywords)

The job runs autonomously — no user action needed. The digest is always up to date before the morning briefing at 08:00.

> **⚠️ Cron config drift guard (#44585)**: This job was created with an implicit snapshot of the global provider/model. If the global config changes (e.g. switching from `custom/deepseek-v4-flash` to `nous/stepfun-3.7-flash:free`), the cron safety system **blocks the run** — it reports `Skipped to prevent unintended spend: global inference config drifted since this job was created`. The fix is to update the job with an explicit provider/model pin matching the current global config:
> ```
> cronjob action=update job_id=49dfd654806a model={"provider":"nous","model":"stepfun-3.7-flash:free"}
> ```
> There is no built-in "follow the global config" mode — the drift guard is intentional to prevent accidental spend on a paid model. If you change your global default, run the update command above to re-pin. Keep the job pinned to whatever `hermes model` is currently showing as the active provider/model.

## Output Inventory

```
papers/
  arxiv/                       # stored .md files (archival only — never queried at runtime)
  index.json                   # flat index across all papers with tier, source, year
references/
  research-digest.md           # CONSOLIDATED — the only file the advisor reads
  sources.md                   # source documentation
  openalex-api.md              # OpenAlex API reference
scripts/
  collect_papers_openalex.py   # daily enrichment (dual-source)
  generate_research_digest.py  # digest regeneration
  query_papers.py              # CLI search for manual debugging (tier-prioritized)
  sync_index_fields.py         # push frontmatter fields into index.json
  collect_papers.py            # DEPRECATED — old arXiv-only collector, kept for reference

### Instrumentation Scripts
- `scripts/sync_index_fields.py` — idempotent sync: reads every paper's markdown frontmatter and writes `category`, `relevance`, and `tags` into the corresponding `index.json` entry. Also reports orphan .md files (on disk but not tracked). Run after manual frontmatter edits or after each daily enrichment to keep index.json in sync.
```

### Index Fields
- `path` — file path in `papers/arxiv/`
- `title` — paper title
- `authors` — author string
- `url` — DOI or arXiv URL (used for dedup)
- `query` — search topic that found this paper
- `tag` — slug of query
- `source` — e.g. `openalex/Elsevier`, `arxiv/q-fin.TR`
- `year` — publication year
- `tier` — A (peer-reviewed), B (preprint), C (supplementary)
- `category` — **NEW** primary strategy tag (momentum, liquidity, sentiment, risk, defi, prediction, arbitrage, execution, crypto, general)
- `relevance` — **NEW** scalar 0.0-1.0 evidence score (crypto kw + trading kw + abstract size + trading/strategy keywords)
- `tags` — **NEW** list of all matching strategy tags

## Maintenance

### Daily (automated via cron)
- `scripts/collect_papers_openalex.py` — collects from both sources
- `scripts/generate_research_digest.py` — regenerates digest

### Weekly (manual)
- Review papers with `category: 'pending_tag'` → assign proper tag
- Deprecate sources when better evidence appears
- Check for source drift in OpenAlex API (the `abstract_inverted_index` format may change)
- **Check for orphan .md files**: run `ls papers/arxiv/*.md | wc -l` vs `python3 -c "import json; print(json.load(open('papers/index.json'))['count'])"`. If disk count > index count, run `scripts/sync_index_fields.py` to backfill, then delete uncovered orphan files (they accumulated due to frontmatter corruption and were skipped during indexing).
- **Verify index.json in-sync**: run `scripts/sync_index_fields.py` to push any missing frontmatter fields (category, relevance, tags) into index.json.

### Pipeline notes
- OpenAlex queries 15 crypto-trading topics, returning up to 8 top-relevance papers per topic per run
- arXiv queries 7 category-filtered queries (q-fin, cs.CE, cs.LG), returning up to 10 per query
- Dedup is by URL first, then near-duplicate ≥80% word overlap with tier-aware replacement. Triple layers: collector → digest generator → index rebuild.
- Auto-cleanup: collector runs `cleanup_orphans()` before and after enrichment, deleting any `.md` file in `papers/arxiv/` not tracked in `papers/index.json`. Disk and index are always synced — no manual orphan maintenance needed.
- The two-layer filter typically rejects ~50% of arXiv results and ~25% of OpenAlex results as non-crypto-trading
- `strategy_tags(title, abstract)` classifies every accepted paper into strategy tags (momentum, liquidity, sentiment, risk, defi, prediction, arbitrage, execution, crypto, general) and computes a relevance score (0.0-1.0) based on evidence signals (crypto kw + trading kw + abstract depth + strategy mentions)
- `is_relevant_for_tok(title, abstract)` is a broader backstop filter that catches crypto-market papers missed by the strict two-layer `is_crypto_trading()` filter. Papers with obvious crypto+market keywords pass even if the strict filter would reject them.
- `_auto_finding(title, abstract, tags)` generates a 1-sentence actionable finding per paper, gated by strategy tag. The finding text is stored in the markdown file's `## Auto-Finding` section and included in the digest's Actionable Findings Index.
- Existing papers (117 indexed .md files) have frontmatter with category, relevance, tags, and Auto-Finding. These fields are also synced into `papers/index.json` for programmatic access (run `scripts/sync_index_fields.py` to re-sync). New papers picked up by the daily cron are tagged automatically by `collect_papers_openalex.py`.
- Audit runs surfaced noise papers (book reviews, ransomware surveys, NFT terminology glossaries, ML optimization) that passed the two-layer filter. Always spot-check a sample of Tier B/C papers after each major enrichment; if noise is found, add the offending keyword to `DROP_KW` in `generate_research_digest.py` and re-run.

### Noise Paper Pollution Incident (2026-06-30)
**Problem**: 125 noise papers polluted `papers/index.json` with `source=None`, `tier=None`, `category=None`, `tags=None`. These were arXiv papers from June 2026 collected by the **deprecated** `collect_papers.py` (old arXiv-only collector using `ti:` title-only search) that wrote incomplete frontmatter (`category: 'pending_tag'`, `relevance: 'tbd'`, no `tags` field). The new collector `collect_papers_openalex.py` expects complete frontmatter and `source: 'arxiv'` or `'openalex'`.

**Root cause**: The deprecated collector (`collect_papers.py`) was run at some point and its output persisted in the index. The new collector's `cleanup_orphans()` only removes `.md` files not in the index — it does not clean stale index entries. The index `count` field (240) also drifted from actual paper count (115).

**Symptoms**:
- Digest showed 125 "GENERALI "GENERAL" entries with `Tier ? [?]` and placeholder findings
- `index.json` had `count: 240` but only 115 valid papers
- `sync_index_fields.py` could not fix because noise papers had no proper frontmatter tags/relevance

**Fix applied**:
1. Removed 125 noise entries from `papers/index.json` (filter `source is not None`)
2. Deleted 15 orphan `.md` files from disk matching noise query signatures
3. Fixed `index.json` count field to match actual paper list length
4. Regenerated clean digest (110 papers, 10 strategy tags)

**Prevention**:
- **Never run `collect_papers.py`** — it is deprecated and produces incomplete records
- After any manual index edit, run `python3 scripts/sync_index_fields.py` AND verify `index.json['count'] == len(index.json['papers'])`
- The daily cron uses `collect_papers_openalex.py` only — ensure no other scripts write to `papers/index.json`
- If `index.json` count drifts, it indicates stale entries; audit and clean before next digest generation

## Querying

### For manual debugging
```bash
python3 scripts/query_papers.py "sentiment" --limit 3
python3 scripts/query_papers.py "bitcoin price" --min-tier A  # Tier A only
```

Search is tier-prioritized (A → B → C) and uses word-level matching (each word in the query separately checked against titles).

### For the trading advisor at runtime
The advisor calls `best_paper_for(concept, fallback_terms)` in `briefing.py` which reads the consolidated digest file. It never calls `query_papers.py` at runtime or opens individual paper markdown files.

## Pitfalls
## Pitfalls
- **Two-layer filter is mandatory**: a paper with "crypto" in the title but no trading keyword is about cryptography, not trading. A paper with "trading" but no crypto keyword is about commodities or equities. Both must match.
- **arXiv requires category filter**: querying arXiv without `cat:q-fin.*` returns quantum physics, computer vision, and radio telescope papers that merely mention "cryptocurrency" in passing.
- **OpenAlex `source` is a dict, not a string**: `work.get("primary_location", {}).get("source", {})` returns `{"display_name": "...", ...}` — you must `.get("display_name", "")` before passing to functions.
- **OpenAlex abstracts are inverted-index format**: `decode_abstract(work.get("abstract_inverted_index"))` reconstructs the text from a word→positions dictionary.
- **Noise rejection is documented**: CrossRef, Semantic Scholar, SSRN, GitHub, and RePEc were all tested and rejected. Do not waste time re-testing them.
- **Use concept-level match, not keyword-in-filename**: A single hit in the filename is not enough; the title or summary must support the specific trading claim being made.
- **Not all matches are equal**: Prefer Tier A. Tier C only supports supplementary context.
- **External proof should be externally tagged**: Only use web when the consolidated digest has zero matches.
- **No-match is valid**: If no paper matches, write `no matching source in current corpus`. Do not fabricate a citation.
- **`_auto_finding()` is template-based, not AI-generated**: The function uses static keyword-to-template mapping. It does not read or summarise the abstract content. If you need a better finding, extend the template conditions in `_auto_finding()` or replace with an LLM call (expensive per-paper).
- **Audit noise papers after major enrichment**: The two-layer filter can still let through false positives (book reviews, ransomware surveys, NFT terminology glossaries, ML optimization papers that mention "crypto" in passing, papers where "crypto" means cryptocurrency-like in context). After each major enrichment, spot-check Tier B/C papers. If noise found, add the offending keyword to `DROP_KW` in `generate_research_digest.py` (NOT `REJECT_KW` — the digest generator now uses `DROP_KW` for its own reject list separate from the collector's `REJECT_KW`). Verify the keyword catches it on re-run.
- **Index fields synced from frontmatter**: The 117 indexed papers have `category`, `relevance`, and `tags` in their markdown frontmatter (set at collection time). These fields are also synced to `papers/index.json` via `scripts/sync_index_fields.py`. New papers collected by the daily cron get frontmatter fields automatically; run the sync script after a collection run to keep index.json in sync.
- **Index count drift indicates stale entries**: If `index.json['count']` != `len(index.json['papers'])`, the index has stale/ghost entries. Clean before regenerating digest. See `references/noise-pollution-incident-2026-06-30.md` for a full case study (125 noise papers from deprecated `collect_papers.py` polluted the index).
- **Never run deprecated `collect_papers.py`**: It uses `ti:` arXiv search (returns 0 relevant), writes incomplete frontmatter (`pending_tag`, `tbd`, no tags), and produces `source=None` in index entries. Only `collect_papers_openalex.py` is supported.

## Integration with trading-advisor

`trading-advisor` MUST reference `references/research-digest.md` before making any strategy claim.

### Citation lookup (runtime — fast path)
1. Call `best_paper_for(concept, fallback_terms)` in `briefing.py`.
2. It reads the Actionable Findings Index section of the digest.
3. Scores entries on tag-match (1.0 primary / 0.6 secondary) + finding-mention (0.4) + title-keyword (0.3) + tier boost.
4. Returns `{title, tier_label, finding, tags, score}` — only if score ≥ 0.7 (strong) or any match (weak fallback).
5. Renderer shows: `Research: [🟢 peer-reviewed] <finding> [Strong match — tags: X]`

### What counts as a match
- The match must be concept-level, not just keyword-in-title.
- A query like `liquidity` should match papers whose tags include `liquidity` or whose finding mentions liquidity dynamics.
- The Actionable Findings Index search scans `Finding:` + `Tags:` lines, not just bold titles — so the match signal includes both the finding text and the strategy tag.
- Score ≥0.7 is a strong match (primary tag hit + finding mention + tier boost). Below 0.7 is a weak fallback (generic crypto paper).

### Picking the best match
- The digest sorts by tier (A first), then by year. `best_paper_for` returns the top-scoring Tier A match.
- If multiple tiers match, cite the strongest tier first.
- Never cite a deprecated or superseded paper unless also citing its replacement.

### Decision-time rules
- If alpha is identified via a known strategy (momentum, mean-reversion, etc.), require at least one paper that demonstrates or tests that idea on crypto assets.
- If risk rule is applied (stop placement, position size), require a paper that discusses risk management for similar asset classes.
- If no paper matches, write `no matching source in current corpus`.

## Quality ground
- Tier A papers must be peer-reviewed or from institutional sources to be treated as primary citations.
- Tier C papers may only support supplementary context; they cannot override a stronger Tier A result.
- No-match is a valid and preferred outcome over a bad match.

## Linked Modules
- `trading-advisor` — the main advisor skill that references research-digest.md for citations
