---
title: 'Beyond the Smile: A Hybrid Convolutional VAE for Crypto Volatility Surfaces'
authors: 'Sadanand Singh, Allam Reddy, Manan Chopra'
url: 'http://arxiv.org/abs/2606.16961v1'
source: 'arxiv/cs.LG q-fin.CP'
query: 'cat:q-fin.*+AND+all:crypto'
retrieved: '2026-06-30T14:32:42.659347+00:00'
updated: '2026-06-15'
categories: 'cs.LG q-fin.CP'
tier: 'B'
category: 'risk'
relevance: '0.85'
tags: [risk, arbitrage, crypto]
---

# Beyond the Smile: A Hybrid Convolutional VAE for Crypto Volatility Surfaces

- **Source**: arXiv (cs.LG q-fin.CP)
- **Tier**: B (preprint)
- **Updated**: 2026-06-15
- **URL**: http://arxiv.org/abs/2606.16961v1
- **Strategy tags**: risk, arbitrage, crypto
- **Relevance**: 0.85

## Abstract
We present a convolutional variational autoencoder for cryptocurrency implied-volatility surfaces, together with a deployable predictor that combines it with a quadratic smile re-fit through a deterministic per-tenor routing rule. Trained on 6,034 fully-filled hourly Binance Options surfaces of BTC and ETH spanning May-October 2023 and parameterised on a common $6 \times 7$ tenor-delta grid, the model attains a hidden-cell surface-completion RMSE in the 0.94-1.56 vol-point range across both markets and mask rates 10-50%. The hybrid predictor attains 0.83 vol points at 50% masking against 7.00 for the smile re-fit alone, an eightfold reduction obtained at no additional inference cost. Under structurally-correlated hole patterns that emulate the withdrawal of an entire tenor of strikes, the smile re-fit incurs 9.6-13.1 vol points of error while the learned model remains at 1.5-1.9, isolating a regime in which the generative model is the only viable predictor. Joint training on BTC and ETH improves the in-distribution model on both markets by 9-27% relative to the better-performing single-symbol counterpart, indicating a substantially shared vol-surface manifold across the two largest cryptocurrencies over the observation window. The hybrid is calendar- and butterfly-arbitrage-free at the listed strikes, a property that the parametric smile re-fit alone fails at high mask rates. The per-snapshot reconstruction error of the trained model flags the late-October ETF-anticipation rally and the August $17$, $2023$ flash crash as elevated-error periods without supervision. All training and evaluation infrastructure is released to support reproducible follow-on work.

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

