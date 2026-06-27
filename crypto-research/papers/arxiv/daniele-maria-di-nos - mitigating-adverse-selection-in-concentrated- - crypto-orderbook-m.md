---
title: 'Mitigating Adverse Selection in Concentrated Liquidity AMMs with Dynamic Fees: An Agent-Based Model Approach'
authors: 'Daniele Maria Di Nosse, Fabrizio Lillo'
url: 'http://arxiv.org/abs/2606.23070v1'
source: 'arxiv'
query: 'crypto orderbook microstructure'
retrieved: '2026-06-26T14:20:09.347001+00:00'
updated: '2026-06-22T09:18:56Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Mitigating Adverse Selection in Concentrated Liquidity AMMs with Dynamic Fees: An Agent-Based Model Approach

## Source
- arXiv: http://arxiv.org/abs/2606.23070v1

## Summary
Automated Market Makers based on concentrated liquidity, such as Uniswap v3, significantly improve capital efficiency but expose Liquidity Providers (LPs) to adverse selection costs, formalized as Loss-Versus-Rebalancing (LVR). While theoretical literature quantifies these costs, the interplay between realistic blockchain microstructure and endogenous pricing mechanisms remains under-explored. This paper develops a granular Agent-Based Model of a Uniswap v3 pool interacting with a stochastic reference market governed by Heston volatility dynamics. The framework incorporates discrete block propagation, mempool latency, and a heterogeneous population of agents, including latency-sensitive arbitrageurs, smart routers, Maximal Extractable Value searchers, and active LPs benchmarked against a frictionless rebalancing strategy. We propose and evaluate dynamic fee schedules driven by volatility and order-flow toxicity proxies intended to compensate LPs for adverse-selection losses. Our simulations investigate the conditions under which LPs can achieve positive hedged Profit and Loss (fees minus LVR). The analysis suggests that dynamic fee adjustments can improve hedged LP profitability mainly by increasing fee income in states associated with stale-price risk. Depending on the configuration, these rules may also affect realized LVR, but the current aggregate results support compensation for LVR more directly than a reduction of LVR itself.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

