---
title: 'Geometric Gradient Rectification for Safe Open-Set Semi-Supervised Learning'
authors: 'Jiahe Chen, Qian Shao, Qiyuan Chen, Jiaying He, Jintai Chen, Jian Wu, Hongxia Xu'
url: 'http://arxiv.org/abs/2606.26973v1'
source: 'arxiv/cs.CV cs.LG'
query: 'cat:cs.LG+AND+all:cryptocurrency+trading'
retrieved: '2026-06-29T22:32:12.113838+00:00'
updated: '2026-06-25'
categories: 'cs.CV cs.LG'
tier: 'B'
category: 'defi'
relevance: '0.85'
tags: [defi]
---

# Geometric Gradient Rectification for Safe Open-Set Semi-Supervised Learning

- **Source**: arXiv (cs.CV cs.LG)
- **Tier**: B (preprint)
- **Updated**: 2026-06-25
- **URL**: http://arxiv.org/abs/2606.26973v1
- **Strategy tags**: defi
- **Relevance**: 0.85

## Abstract
Open-set semi-supervised learning aims to leverage unlabeled data that may contain out-of-distribution outliers while maintaining performance on in-distribution classes. Existing methods mainly follow two paradigms: filtering suspicious samples or incorporating unlabeled objectives with soft weighting. We argue that both face a common trade-off: aggressive filtering can discard informative but hard ID samples, whereas utilization can introduce auxiliary gradients that conflict with supervised learning when pseudo labels are wrong. We therefore shift the focus from sample selection to gradient-level control. We propose \textit{Geometric Gradient Rectification} (GGR), a plug-in framework that uses the supervised gradient as an anchor and projects conflicting auxiliary gradients onto an admissible region in gradient space. This makes the applied auxiliary update first-order non-opposing within the rectified coordinate block while preserving orthogonal components that may still carry useful representation signals. We further extend GGR with subspace-aware rectification to stabilize the anchor under noisy mini-batch gradients. Experiments on CIFAR and ImageNet benchmarks show that GGR improves representative OSSL baselines in most settings and yields gains in both closed-set generalization and open-set robustness. Code will be available at https://github.com/JiaheChen2002/GGR.

## Auto-Finding
DeFi finding: yields, lending rates, or AMM dynamics have exploitable structure for token-selection and yield strategy.

## Notes

