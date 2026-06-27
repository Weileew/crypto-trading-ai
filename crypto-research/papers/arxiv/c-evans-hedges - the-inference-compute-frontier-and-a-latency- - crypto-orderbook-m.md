---
title: 'The Inference-Compute Frontier and a Latency-Efficient Architecture for Limit Order Book Prediction'
authors: 'C. Evans Hedges'
url: 'http://arxiv.org/abs/2606.25986v1'
source: 'arxiv'
query: 'crypto orderbook microstructure'
retrieved: '2026-06-26T14:20:09.345893+00:00'
updated: '2026-06-24T15:54:09Z'
category: 'pending_tag'
relevance: 'tbd'
---

# The Inference-Compute Frontier and a Latency-Efficient Architecture for Limit Order Book Prediction

## Source
- arXiv: http://arxiv.org/abs/2606.25986v1

## Summary
We study whether a scaling-law-style inference-compute frontier appears in limit order book prediction. Using FI-2010 and a suite of models ranging from small decision trees to neural LOB architectures, we find that the realized empirical frontier of predictive loss versus structural forward work is well summarized by a power law. In particular, with MLPLOB held out as an architecture family, a power-law fit to the low- and mid-compute non-MLPLOB frontier extrapolates across multiple orders of magnitude and attains $R^2=0.941$ on the excluded high-compute MLPLOB target frontier.
  A similar exercise in latency space gives substantially weaker results, showing that latency is not merely noisy compute. We use this gap to motivate FastBiNLOB, a dense axis-separable LOB mixer built from hardware-friendly temporal and feature mixing operations. In a five-seed experiment, FastBiNLOB exceeds the published $y_{10}$ and $y_{100}$ macro-F1 targets at notably lower latency than existing published SOTA architectures.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

