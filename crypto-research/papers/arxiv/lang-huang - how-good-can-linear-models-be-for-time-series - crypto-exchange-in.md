---
title: 'How Good Can Linear Models Be for Time-Series Forecasting?'
authors: 'Lang Huang, Jinglue Xu, Luke Darlow'
url: 'http://arxiv.org/abs/2606.27282v1'
source: 'arxiv'
query: 'crypto exchange inefficiency'
retrieved: '2026-06-26T14:20:15.376533+00:00'
updated: '2026-06-25T16:57:50Z'
category: 'pending_tag'
relevance: 'tbd'
---

# How Good Can Linear Models Be for Time-Series Forecasting?

## Source
- arXiv: http://arxiv.org/abs/2606.27282v1

## Summary
Time-series forecasting research has been moving steadily toward larger architectures, from specialized transformers to general-purpose foundation models, on the assumption that capacity is what unlocks accuracy. We take the opposite position: most of the gap can be closed at far lower cost by tuning preprocessing rather than scaling models. We use Ridge regression as the testbed, since it has a closed-form solution and interpretable weights, which let the optimal hyperparameters be read off the search directly. We search over context length, local normalization, regularization, and augmentation on eight standard benchmarks and find three patterns. (1) Optimal lookback is strongly series-specific and often non-monotonic in forecast horizon, with fitted power-law exponents ranging from $+0.46$ on ETTm2 to $-0.19$ on Exchange and Traffic, challenging the convention that longer horizons need longer history. (2) Normalizing over a learned trailing fraction of the context, rather than its entirety, is almost universally preferred. (3) Series within the same dataset often disagree on hyperparameters; the optimal degree of cross-series sharing varies from fully shared to fully per-series. The resulting models beat prior linear forecasters on most dataset-horizon entries and exceed Transformer, MLP, and CNN baselines on six of eight benchmarks. The optimized hyperparameters also serve as a diagnostic on the data itself, revealing structures that larger models absorb silently into their learned parameters.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

