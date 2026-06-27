# Crypto Research Module Inventory

Use this file as a simple manifest to track which papers are kept, what they cover, and how strong the evidence is.

## Maintenance Rules
- Keep this file updated when adding or removing papers.
- Each entry should have fields: `id`, `title`, `authors`, `year`, `url`, `tag`, `tier`, `date_added`, `last_reviewed`, `notes`, `rating`.
- When deprecating a paper, mark it `status: deprecated` and include a `superseded_by` note.

## Current Corpus Size
Papers added: check `scripts/query_papers.py` against saved inventory.

## Tag Summary
- `microstructure` - orderbook/liquidity
- `sentiment` - news/social sentiment
- `onchain` - blockchain analytics
- `strategy` - momentum/mean reversion
- `risk` - risk models and position sizing
- `execution` - latency, slippage, nuance

## Quality Notes
- Primary sources only: peer-reviewed papers and accepted conference papers.
- Secondary sources allowed if methodology is unique and source is verifiable.
- All Tier C sources must include a short plain-language summary of claim strength.
- Deprecated papers should remain readable to prevent link rot issues.
