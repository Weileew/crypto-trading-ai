---
title: 'Stochastic Gradient Optimization with Model-Assisted Sampling'
authors: 'Jonne Pohjankukka, Jukka Heikkonen'
url: 'http://arxiv.org/abs/2606.27171v1'
source: 'arxiv/cs.LG stat.ME'
query: 'cat:cs.LG+AND+all:cryptocurrency+trading'
retrieved: '2026-06-27T05:19:20.149447+00:00'
updated: '2026-06-25'
categories: 'cs.LG stat.ME'
tier: 'B'
category: 'pending_tag'
---

# Stochastic Gradient Optimization with Model-Assisted Sampling

- **Source**: arXiv (cs.LG stat.ME)
- **Tier**: B (preprint)
- **Updated**: 2026-06-25
- **URL**: http://arxiv.org/abs/2606.27171v1

## Abstract
This work addresses the problem of variance in stochastic gradient estimation for machine learning optimization. Deep learning relies on mini-batch methods such as stochastic gradient descent, which approximate full gradients but introduce noise, creating trade-offs between convergence stability, speed, and generalization. Existing methods, including variance reduction techniques (e.g., SVRG and SAG) and adaptive optimizers, aim to mitigate gradient noise but may introduce additional computational overhead. We propose a model-assisted sampling framework that interprets mini-batch gradients through survey sampling theory, treating the dataset as a fixed finite population and gradients as sample-based estimates. Our aim is to bridge machine learning optimization and survey sampling theory by combining their perspectives on sample-based estimation and variance reduction. By incorporating auxiliary gradient-prediction models, we construct more efficient gradient estimators, with uniform sampling arising as a special case when no auxiliary information is used. Our approach integrates easily with existing optimizers, improving efficiency without altering their dynamics. Empirical results on synthetic and six benchmark datasets show performance gains in 71-86% of the experiments, particularly for medium-sized input spaces in our benchmarks. Notably, with momentum-based optimizers such as AdamW, the proposed estimator achieves clearly better generalization in roughly half the training epochs compared to baseline estimator.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk / execution.

## Notes

