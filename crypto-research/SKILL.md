---
name: crypto-research
description: "Curated crypto trading research module for Hermes Agent. Collects, stores, and references academic and white-paper sources for trading strategy and market structure."
version: 0.3.0
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

## Architecture (Consolidated Digest)

```
collect_papers_openalex.py  →  generate_research_digest.py  →  references/research-digest.md  →  advisor cites it
        │                              │                              │
   OpenAlex + arXiv q-fin         1 consolidated file            O(1) title scan
   2-layer relevance filter        topic-grouped, tiered          never touches individual files
```

The advisor reads **only** `references/research-digest.md` — a single markdown file. Individual paper files under `papers/arxiv/` are archival storage only and are never queried at runtime.

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

### Digest structure
```
# Crypto Trading Research Digest

Generated: YYYY-MM-DD · Papers indexed: N

## Price Prediction & Forecasting (N papers, XA/YB)
- 🟢 Tier A [year] **Title** (source) — doi:...
  > Abstract excerpt...
- 🟡 Tier B [year] **Title** (source) — doi:...

## Risk Management & Volatility (N papers, XA/YB)
...
```

### Topic classifier
Papers are automatically classified into: Price Prediction, Sentiment Analysis, Market Microstructure & Liquidity, Risk Management & Volatility, DeFi & Automated Market Makers, Arbitrage & Market Efficiency, Trading Strategies & Execution, On-Chain & Blockchain Analytics, Derivatives & Futures, Crypto as Asset Class, General Crypto Trading & Markets.

### Tier badge meanings
- **🟢 Tier A**: Peer-reviewed journal (Elsevier, Springer, IEEE, ACM, Wiley, MDPI, etc.)
- **🟡 Tier B**: Preprint (arXiv q-fin)
- **⭕ Tier C**: Supplementary (working papers, reports — use only as fallback)

### Lookup function (`briefing.py` → `lookup_research()`)
The `best_paper_for()` function in `trading-advisor/scripts/briefing.py` reads the digest file (O(1) file read, ~78KB), scans lines for bolded **titles**, counts how many search-concept words appear in each title, and returns the best Tier A match. It never touches `papers/arxiv/` files at runtime.

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
  collect_papers.py            # DEPRECATED — old arXiv-only collector, kept for reference
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

## Maintenance

### Daily (automated via cron)
- `scripts/collect_papers_openalex.py` — collects from both sources
- `scripts/generate_research_digest.py` — regenerates digest

### Weekly (manual)
- Review papers with `category: 'pending_tag'` → assign proper tag
- Deprecate sources when better evidence appears
- Check for source drift in OpenAlex API (the `abstract_inverted_index` format may change)

### Pipeline notes
- OpenAlex queries 15 crypto-trading topics, returning up to 8 top-relevance papers per topic per run
- arXiv queries 7 category-filtered queries (q-fin, cs.CE, cs.LG), returning up to 10 per query
- Dedup is by URL first, then near-duplicate ≥80% word overlap with tier-aware replacement. Triple layers: collector → digest generator → index rebuild.
- The two-layer filter typically rejects ~50% of arXiv results and ~25% of OpenAlex results as non-crypto-trading
- Audit runs surfaced noise papers (book reviews, ransomware surveys, NFT terminology glossaries, ML optimization) that passed the two-layer filter. Always spot-check a sample of Tier B/C papers after each major enrichment; if noise is found, add the offending keyword to `REJECT_KW` in `generate_research_digest.py` and re-run.

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

- **Two-layer filter is mandatory**: a paper with "crypto" in the title but no trading keyword is about cryptography, not trading. A paper with "trading" but no crypto keyword is about commodities or equities. Both must match.
- **arXiv requires category filter**: querying arXiv without `cat:q-fin.*` returns quantum physics, computer vision, and radio telescope papers that merely mention "cryptocurrency" in passing.
- **OpenAlex `source` is a dict, not a string**: `work.get("primary_location", {}).get("source", {})` returns `{"display_name": "...", ...}` — you must `.get("display_name", "")` before passing to functions.
- **OpenAlex abstracts are inverted-index format**: `decode_abstract(work.get("abstract_inverted_index"))` reconstructs the text from a word→positions dictionary.
- **Noise rejection is documented**: CrossRef, Semantic Scholar, SSRN, GitHub, and RePEc were all tested and rejected. Do not waste time re-testing them.
- **Use concept-level match, not keyword-in-filename**: A single hit in the filename is not enough; the title or summary must support the specific trading claim being made.
- **Not all matches are equal**: Prefer Tier A. Tier C only supports supplementary context.
- **External proof should be externally tagged**: Only use web when the consolidated digest has zero matches.
- **No-match is valid**: If no paper matches, write `no matching source in current corpus`. Do not fabricate a citation.
- **Audit noise papers after major enrichment**: The two-layer filter can still let through false positives (book reviews, ransomware surveys, NFT terminology glossaries, ML optimization papers that mention "crypto" in passing, papers where "crypto" means cryptocurrency-like in context). After each major enrichment, spot-check Tier B/C papers. If noise found, add the offending keyword to `REJECT_KW` in `generate_research_digest.py` (not just the title check — also verify `REJECT_KW` catches it on re-run). This session removed 6 noise papers via this audit process.

## Integration with trading-advisor

`trading-advisor` MUST reference `references/research-digest.md` before making any strategy claim.

### Citation lookup (runtime — fast path)
1. Call `best_paper_for(concept, fallback_terms)` in `briefing.py`.
2. It reads the digest once, scans bold titles, returns the best Tier A match.
3. Format: `Research: [🟢 peer-reviewed] "Paper Title" (doi:...)`.

### What counts as a match
- The match must be concept-level, not just keyword-in-title.
- A query like `liquidity` should match papers whose title references liquidity, orderbook, or execution quality.
- The digest search scans bolded **titles** only (not abstracts or topics) — so the match signal is trustworthy.

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
