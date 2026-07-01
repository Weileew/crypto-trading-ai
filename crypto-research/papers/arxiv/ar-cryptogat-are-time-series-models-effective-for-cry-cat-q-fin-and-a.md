---
title: 'CryptoGAT: Are Time Series Models Effective for Cryptocurrency Forecasting?'
authors: 'Yu Peng, Matloob Khushi, Josiah Poon'
url: 'http://arxiv.org/abs/2606.27670v1'
source: 'arxiv/cs.CE q-fin.ST'
query: 'cat:q-fin.*+AND+all:blockchain+market'
retrieved: '2026-06-30T14:32:48.788482+00:00'
updated: '2026-06-26'
categories: 'cs.CE q-fin.ST'
tier: 'B'
category: 'risk'
relevance: '0.85'
tags: [risk, prediction, crypto]
---

# CryptoGAT: Are Time Series Models Effective for Cryptocurrency Forecasting?

- **Source**: arXiv (cs.CE q-fin.ST)
- **Tier**: B (preprint)
- **Updated**: 2026-06-26
- **URL**: http://arxiv.org/abs/2606.27670v1
- **Strategy tags**: risk, prediction, crypto
- **Relevance**: 0.85

## Abstract
Cryptocurrency price prediction is a significant challenge in quantitative investment. In recent years, time series models have made significant progress in financial forecasting tasks, especially in the stock market. Despite the growing performance over the past few years, we question the validity of this line of research in cryptocurrency prediction. Specifically, time series models (e.g., LSTM, GRU, and Transformers) are effective at extracting temporal relationships in stock market data. However, in pure price-based cryptocurrency prediction, facing data with extreme volatility and wild swings, time series models have difficulty learning effective information. To validate our claim, we propose CryptoGAT, a lightweight Graph Attention Network that recasts cryptocurrency pure price prediction as a cross-asset graph problem rather than a temporal modeling task. Extensive experiments on real cryptocurrency benchmarks demonstrate that our proposed CryptoGAT outperforms various state-of-the-art forecasting methods with a notable margin. Moreover, we conduct comprehensive empirical studies to explore the fundamental differences exposed by time series models in stock and cryptocurrency prediction: differences in predictability of the signal and cross-asset dependencies. This finding opens up new research directions for the cryptocurrency pure price prediction task and inspires further graph-based exploration in the field. The source code is available at https://github.com/FanBroWell/CryptoGAT

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

