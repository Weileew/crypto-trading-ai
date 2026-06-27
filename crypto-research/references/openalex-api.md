# OpenAlex API — Research Collection Reference

## Overview

OpenAlex is a free, open scholarly index (replaces arXiv for crypto queries).
- **No auth/API key required** — anonymous access is free
- **Rate limit**: ~10 req/s anonymous (tested: 0.35s delay between calls is safe)
- **Output**: JSON with metadata, abstract, citations, authorships
- Doc: https://docs.openalex.org/

## Key Endpoints

### Search works
```
GET https://api.openalex.org/works?search={query}&per_page={n}&sort=relevance_score:desc
```
- `per_page`: max 200, default 25. Use 8 for daily enrichment to minimise bandwidth.
- `sort`: `relevance_score:desc` (default), `publication_date:desc`
- `select`: comma-separated fields to reduce payload size
  - Recommended: `id,doi,title,authorships,publication_year,primary_location,abstract_inverted_index`
- `filter`: more precise scoping e.g. `filter=from_publication_date:2023-01-01`

### Get single work
```
GET https://api.openalex.org/works/{doi_or_openalex_id}
```

## Response Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | OpenAlex ID (e.g. `W123456789`) |
| `doi` | string | DOI URL or null |
| `title` | string | Paper title |
| `authorships[].author.display_name` | string | Author name |
| `publication_year` | int | Year published |
| `primary_location.source.display_name` | string | Journal / venue name |
| `abstract_inverted_index` | dict or null | Word→position list (see below) |

## Decoding `abstract_inverted_index`

OpenAlex stores abstracts as inverted indices to save bandwidth. Reconstruct with:

```python
def decode_abstract(inv_index):
    if not inv_index:
        return ""
    words = []
    for token, positions in inv_index.items():
        for pos in positions:
            words.append((pos, token))
    words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in words)
```

## Working Query Examples

These all return 1K-50K relevant results on OpenAlex (verified June 2026):

| Query | Approx results | Relevance |
|-------|---------------|-----------|
| `cryptocurrency trading strategy machine learning` | 16K | High — includes prediction papers |
| `Bitcoin price prediction deep learning` | 14K | High — includes econometrics |
| `crypto market microstructure liquidity` | 1K | High — niche but targeted |
| `crypto sentiment analysis trading` | 8K | Medium — includes general sentiment |
| `cryptocurrency risk management portfolio` | 49K | High — includes crypto-portfolio |
| `DeFi trading liquidity automated market maker` | 5K | High — targeted DeFi |
| `crypto on-chain metrics predictive` | 2K | High — blockchain analytics |
| `crypto arbitrage efficiency` | 1K | High — market efficiency |
| `crypto momentum mean reversion` | 3K | High — trading strategies |
| `crypto limit order book` | 1K | High — microstructure |
| `crypto volatility forecasting` | 4K | High — risk models |

## Relevance Filter Heuristic

OpenAlex returns papers ranked by `relevance_score`, but some high-scoring papers
may be unrelated to crypto (e.g., general ML papers, physics papers). Use a
two-pass filter:

**Pass 1 — Title keywords**: `crypto`, `bitcoin`, `ethereum`, `blockchain`,
`defi`, `token`, `nft`, `trading`, `market`, `liquidity`, `order book`,
`sentiment`, `momentum`, `volatility`, `portfolio`, `risk`, `arbitrage`,
`prediction`, `microstructure`, `execution`, `hedging`, `limit order`, `amm`,
`automated market maker`, `stablecoin`, `on-chain`, `onchain`, `wallet`, `mining`

**Pass 2 — Abstract keywords** (if title is ambiguous): `cryptocurrency`,
`bitcoin`, `blockchain`, `ethereum`, `token`, `defi`

Papers failing both passes are likely false positives from general ML/statistics.

## Migration Notes (June 2026)

**Previous source**: arXiv API (`export.arxiv.org`)
- Failed: returned 0 entries for `ti:cryptocurrency+trading` queries
- Rate-limited: `Rate exceeded.` on subsequent queries
- Narrow search scope: `ti:` (title-only) too restrictive for crypto queries

**Replacement**: OpenAlex
- Works: returned 16K+ results for same queries
- No rate limits hit: 0.35s delay between calls, never hit 429
- Broad search scope: fulltext + title + abstract + keywords
- Results include DOIs from Elsevier, IEEE, Springer, SSRN
