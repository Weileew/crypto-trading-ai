---
title: 'The Inference-Compute Frontier and a Latency-Efficient Architecture for Limit Order Book Prediction'
authors: 'C. Evans Hedges'
url: 'http://arxiv.org/abs/2606.25986v1'
source: 'arxiv/cs.LG q-fin.ST q-fin.TR'
query: 'cat:q-fin.*+AND+all:blockchain+market'
retrieved: '2026-06-29T22:31:57.792872+00:00'
updated: '2026-06-24'
categories: 'cs.LG q-fin.ST q-fin.TR'
tier: 'B'
category: 'liquidity'
relevance: '0.85'
tags: [liquidity, prediction, execution]
---

# The Inference-Compute Frontier and a Latency-Efficient Architecture for Limit Order Book Prediction

- **Source**: arXiv (cs.LG q-fin.ST q-fin.TR)
- **Tier**: B (preprint)
- **Updated**: 2026-06-24
- **URL**: http://arxiv.org/abs/2606.25986v1
- **Strategy tags**: liquidity, prediction, execution
- **Relevance**: 0.85

## Abstract
We study whether a scaling-law-style inference-compute frontier appears in limit order book prediction. Using FI-2010 and a suite of models ranging from small decision trees to neural LOB architectures, we find that the realized empirical frontier of predictive loss versus structural forward work is well summarized by a power law. In particular, with MLPLOB held out as an architecture family, a power-law fit to the low- and mid-compute non-MLPLOB frontier extrapolates across multiple orders of magnitude and attains $R^2=0.941$ on the excluded high-compute MLPLOB target frontier.
  A similar exercise in latency space gives substantially weaker results, showing that latency is not merely noisy compute. We use this gap to motivate FastBiNLOB, a dense axis-separable LOB mixer built from hardware-friendly temporal and feature mixing operations. In a five-seed experiment, FastBiNLOB exceeds the published $y_{10}$ and $y_{100}$ macro-F1 targets at notably lower latency than existing published SOTA architectures.

## Auto-Finding
Liquidity finding: confirms that orderbook depth and spread dynamics predict short-term price pressure — useful for entry timing and slippage checks.

## Notes

