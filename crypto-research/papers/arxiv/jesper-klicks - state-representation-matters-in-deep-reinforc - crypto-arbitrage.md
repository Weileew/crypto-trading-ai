---
title: 'State Representation Matters in Deep Reinforcement Learning: Application to Energy Trading'
authors: 'Jesper Klicks, Sander Vržina, Vincent François-Lavet'
url: 'http://arxiv.org/abs/2606.27032v1'
source: 'arxiv'
query: 'crypto arbitrage'
retrieved: '2026-06-26T14:20:14.874850+00:00'
updated: '2026-06-25T13:39:57Z'
category: 'pending_tag'
relevance: 'tbd'
---

# State Representation Matters in Deep Reinforcement Learning: Application to Energy Trading

## Source
- arXiv: http://arxiv.org/abs/2606.27032v1

## Summary
Energy trading decisions depend not only on current market prices, but also on expected future market conditions, and operational constraints. This makes the state representation given to a reinforcement learning agent an important design choice. We study this in HydroDam, a pumped-storage arbitrage environment, using a fixed Double DQN agent. The environment, action space, reward function, network, and training protocol are kept fixed; only the market features are changed. We compare absolute price/calendar features, relative features that compare current prices with recent market history, forecast features, and all combinations of these three feature families. Policies are trained and selected using 2007--2011 Belgian day-ahead prices and evaluated on two test settings: a later same-market test set from 2012--2025 and 39 other ENTSO-E market zones. Absolute features only reaches 28.8% on the test set and a median 5.7% across zones. Relative-only and forecast-only states also stay below a rolling price-score heuristic in the cross-zone median. Combining feature families is much stronger: absolute + relative reaches 49.9% on the test set and a 39.8% cross-zone median, while absolute + relative + forecast reaches 55.6% and 47.5%. These results suggest that state representation is not a minor preprocessing choice in storage-trading RL, but a central part of the policy design: robust transfer requires combining price scale, recent relative price context, and short-horizon forecast information, rather than relying on any single feature family.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

