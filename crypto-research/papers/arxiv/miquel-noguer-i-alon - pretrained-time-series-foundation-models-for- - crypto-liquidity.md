---
title: 'Pretrained Time-Series Foundation Models for Financial Return Forecasting'
authors: 'Miquel Noguer I Alonso, Rodolfo Pereira Franklin'
url: 'http://arxiv.org/abs/2606.27100v1'
source: 'arxiv'
query: 'crypto liquidity'
retrieved: '2026-06-26T14:20:09.845240+00:00'
updated: '2026-06-25T14:35:59Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Pretrained Time-Series Foundation Models for Financial Return Forecasting

## Source
- arXiv: http://arxiv.org/abs/2606.27100v1

## Summary
Financial return forecasting is a difficult test case for time-series foundation models (TSFMs) due to low signal-to-noise ratios, structural breaks, heavy tails, and weak persistence. This paper benchmarks pretrained TSFMs against train-from-scratch neural baselines in a deliberately conservative financial setting. We evaluate TimeGPT/TimeGPT-LH, TimesFM-2.5, Moirai-2.0, Chronos, and Chronos-2 against NBEATS, NHITS, PatchTST, iTransformer, and KAN on five liquid U.S. equities (AAPL, AMZN, GOOG, JPM, META) using linear and log returns. Models are compared under an equalized context budget, a rolling-origin protocol, and against random-walk benchmarks. We provide a theoretical framing of pretraining as an inductive prior, linking PAC-Bayes transfer intuition, information-theoretic predictability limits, and attention geometry. This clarifies why strong model rankings need not imply economically meaningful predictability in noisy markets. Pragmatically, pretrained TSFMs dominate the ranking distribution, accounting for 8 of 10 task-level wins. Moirai-2.0 and TimesFM-2.5 achieve the strongest average ranks, leading tasks for AAPL, JPM, GOOG, and AMZN, while Chronos wins the remaining AMZN task. However, the iTransformer baseline wins both META tasks, showing local supervised learning can still outperform generic pretraining for specific assets. Crucially, gains over the random-walk benchmark are small and sparse. A one-sided Diebold-Mariano test rejects equal or inferior predictive accuracy only for Chronos on AMZN and Moirai-2.0 on GOOG. We conclude that TSFMs serve as useful practical priors that reduce model-development costs in low-data financial forecasting, but are not universal engines for statistically reliable alpha generation in realistic empirical deployment.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

