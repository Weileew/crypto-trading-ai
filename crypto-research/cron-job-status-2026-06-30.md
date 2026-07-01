# Crypto Research Cron Job Status — 2026-06-30

Snapshot of the crypto-research skill cron job as of the scheduled cron run on 2026-06-30 05:00 WIB.

## Active Job

| Job ID | Name | Schedule | Status | Last Run | Next Run | Notes |
|--------|------|----------|--------|----------|----------|-------|
| 49dfd654806a | research-playbook-enrichment | 30 5 * * * | active | 2026-06-29T05:32:02 ✅ | 2026-06-30T05:30:00 | Skills: crypto-research, workdir: skill dir |

## Pipeline Execution Order

The cron job runs two scripts sequentially from `/home/ubuntu/.hermes/skills/crypto-research`:

1. **`scripts/collect_papers_openalex.py`** — Fetches new papers from OpenAlex + arXiv q-fin
   - 15 OpenAlex queries (8 papers each, sorted by relevance)
   - 7 arXiv queries (category-filtered on q-fin.*, cs.CE, cs.LG)
   - Two-layer relevance filter (crypto + trading/finance keywords)
   - Updates `papers/index.json` with new entries (category, relevance, tags)
   - Runs `cleanup_orphans()` before and after — disk and index always synced

2. **`scripts/generate_research_digest.py`** — Regenerates `references/research-digest.md`
   - Reads `papers/index.json` → groups by strategy tag (10 categories)
   - Produces Actionable Findings Index (score-gated citations for trading-advisor)
   - Applies `DROP_KW` reject list for noise papers found in audits
   - Triple-guard dedup: URL match → exact title → ≥80% word overlap (tier-aware)

## Index Status (as of 2026-06-29 run)

- **Papers indexed**: 111
- **Approved**: 110
- **Rejected**: 29
- **Categories**: momentum (17), liquidity (14), sentiment (13), risk (12), defi (11), prediction (11), arbitrage (7), execution (7), crypto (19), general (20)
- **Tier A (peer-reviewed)**: ~70%
- **Tier B (preprint/arXiv q-fin)**: ~30%
- **Tier C (supplementary)**: 0%

## Recent Digest

`references/research-digest.md` last updated 2026-06-28, 866 lines, 75KB

Key sections:
- **Actionable Findings Index** — 10 strategy tags with score-gated entries (Finding + Tags + Relevance)
- **Full Paper Reference** — topic-grouped archival listings (Price Prediction, Sentiment Analysis, Market Microstructure, Risk Management, DeFi & AMM, Arbitrage, Trading Strategies, On-Chain Analytics, Derivatives, Crypto as Asset Class, General)

## Integration with trading-advisor

The `trading-advisor` skill's `briefing.py` calls `best_paper_for(concept, fallback_terms)` which:
1. Reads the Actionable Findings Index section of `research-digest.md`
2. Scores each entry on 4 axes:
   - +1.0 primary tag hit / +0.6 secondary tag hit
   - +0.4 if concept word appears in Finding text
   - +0.3 if concept word appears in title
   - +0.3/.15 tier boost (A/B)
2. Returns best match with score ≥0.7 (strong) or any match (weak fallback)

Recent citations in briefings:
- 2026-06-28: SYN → "peer-reviewed General crypto-market finding: adds empirical support for the thesis that crypto returns exhibit non-random walk properties exploitable by systematic strategies" (Tier A, score ≥2.0)
- 2026-06-29: No high-confidence setups → no citations rendered

## Cron Drift Guard (#44585)

This job was created with an implicit snapshot of the global provider/model. If the global config changes (e.g., switching providers), the cron safety system blocks the run with:
> `Skipped to prevent unintended spend: global inference config drifted since this job was created`

**Fix**: Update the job with an explicit provider/model pin matching current global config:
```
cronjob action=update job_id=49dfd654806a model={"provider":"nous","model":"stepfun-3.7-flash:free"}
```

## Maintenance Notes

- **Weekly**: Review papers with `category: 'pending_tag'` → assign proper tag
- **Weekly**: Check for orphan .md files (`ls papers/arxiv/*.md | wc -l` vs index count)
- **Weekly**: Run `scripts/sync_index_fields.py` to backfill frontmatter → index.json
- **After major enrichment**: Spot-check Tier B/C papers for noise; add offending keywords to `DROP_KW` in `generate_research_digest.py`