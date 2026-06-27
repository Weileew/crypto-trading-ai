---
title: 'Autoregressive Boltzmann Generators'
authors: 'Danyal Rehman, Charlie B. Tan, Yoshua Bengio, Avishek Joey Bose, Alexander Tong'
url: 'http://arxiv.org/abs/2606.27361v1'
source: 'arxiv'
query: 'crypto machine learning trading'
retrieved: '2026-06-26T14:20:13.879342+00:00'
updated: '2026-06-25T17:58:21Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Autoregressive Boltzmann Generators

## Source
- arXiv: http://arxiv.org/abs/2606.27361v1

## Summary
Efficient sampling of molecular systems at thermodynamic equilibrium is a hallmark challenge in statistical physics. This challenge has driven the development of Boltzmann Generators (BGs), which allow rapid generation of uncorrelated equilibrium samples by combining a generative model with exact likelihoods and an importance sampling correction. However, modern BGs predominantly rely on normalizing flows (NFs), which either suffer from limited expressivity due to strict invertibility constraints (discrete time) or computationally expensive likelihoods (continuous time). In this paper, we propose Autoregressive Boltzmann Generators (ArBG) -- a novel autoregressive modelling framework -- that overcomes these limitations by departing from the flow-based BG paradigm. ArBG circumvents the topological constraints of flows and enables sequential inference-time interventions, while offering enhanced scalability by leveraging architectures effective in Large Language Models. We empirically demonstrate that ArBG leads to significant improvements over flow-based models across all benchmarks, but particularly in larger peptide systems such as the 10-residue Chignolin. Furthermore, we introduce Robin, a 132 million parameter transferable model trained with the ArBG framework which improves over the previous state-of-the-art, reducing the zero-shot energy error, E-W$_2$, on 8-residue systems by over 60$\%$. The code can be found at the following link: https://github.com/danyalrehman/autobg.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

