---
title: 'Market Regime Council for Dynamic Credit Assignment in Multi-Agent LLM Decision Systems'
authors: 'Yunhua Pei, Zerui Ge, Jin Zheng, John Cartlidge'
url: 'http://arxiv.org/abs/2605.24490v1'
source: 'arxiv/cs.AI cs.LG q-fin.PM'
query: 'cat:q-fin.*+AND+all:crypto'
retrieved: '2026-06-29T22:31:50.795781+00:00'
updated: '2026-05-23'
categories: 'cs.AI cs.LG q-fin.PM'
tier: 'B'
category: 'risk'
relevance: '1.0'
tags: [risk, crypto]
---

# Market Regime Council for Dynamic Credit Assignment in Multi-Agent LLM Decision Systems

- **Source**: arXiv (cs.AI cs.LG q-fin.PM)
- **Tier**: B (preprint)
- **Updated**: 2026-05-23
- **URL**: http://arxiv.org/abs/2605.24490v1
- **Strategy tags**: risk, crypto
- **Relevance**: 1.0

## Abstract
Multi-agent LLM decision systems for portfolio management still lack a principled way to assign credit across specialist agents, remain vulnerable to cold-start dominance under regime shifts, and offer limited transparency into how final allocations are formed. We propose Market Regime Council (MRC), a cooperative multi-agent decision system that computes exact Shapley credits across all single, pairwise, and Grand-coalition outputs for online agent weighting. Instantiated with N=3 specialist agents, at each trading period, MRC recomputes coalition-based Shapley weights from exponentially weighted performance histories, uses a Bayesian adaptive mixture to stabilize early periods, applies regime-dependent multipliers to adjust agent authority, and records each rebalance through a five-layer causal trace. Over 1,037 trading days across 13 crypto assets and five seeds, MRC achieves a Sharpe ratio of 1.51 and a cumulative return of 440.1%, ranking first on CR, SR, and IR among active baselines and attaining the lowest MDD among active methods. Ablation results show that the gains come from Shapley-weighted integration across coalition outputs rather than from any single stage in isolation. Code and demo data are included in the supplementary material.

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

