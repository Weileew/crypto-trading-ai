---
title: 'RankGLU: Residual Gated Score Formation for Cross-Sectional Stock Prediction'
authors: 'Huixiang Xiao, Jian Xu, Feiyu Qu, Zixuan Xie, Xiangyu Li'
url: 'http://arxiv.org/abs/2606.08930v1'
source: 'arxiv/cs.CE'
query: 'cat:cs.CE+AND+all:crypto+trading'
retrieved: '2026-06-27T04:07:18.430463+00:00'
updated: '2026-06-08'
categories: 'cs.CE'
tier: 'B'
category: 'pending_tag'
---

# RankGLU: Residual Gated Score Formation for Cross-Sectional Stock Prediction

- **Source**: arXiv (cs.CE)
- **Tier**: B (preprint)
- **Updated**: 2026-06-08
- **URL**: http://arxiv.org/abs/2606.08930v1

## Abstract
Cross-sectional stock prediction is closer to a ranking problem than to ordinary return-magnitude regression, since portfolio decisions depend on the relative ordering of assets within each trading date. Existing temporal, graph-based, and market-conditioned attention models have improved stock representation learning, yet the final prediction head is often treated as a minor implementation detail. This paper argues that, under information-coefficient-oriented evaluation, score formation is a critical bottleneck: an over-flexible head can fit unstable return magnitude, whereas an overly linear head may underuse cross-feature interactions. We therefore develop RankGLU, a residual bottleneck gated linear unit for cross-sectional stock ranking. RankGLU keeps a direct linear scoring path and adds a bounded multiplicative branch, thereby preserving a stable ordering route while allowing controlled nonlinear interactions. The method is evaluated on CSI300 and CSI800 under a unified protocol with cross-sectional score normalization and an IC-augmented objective. Multi-seed experiments show that, on CSI300, RankGLU achieves the strongest mean IC among the internally controlled variants, improving from 0.0654+/-0.0052 for the original backbone and 0.0697+/-0.0030 for the ranking-aware backbone to 0.0727+/-0.0037, a gain that is consistent across all five seeds. Its best-seed result also exceeds the corresponding baselines. Ablation results further indicate that removing the GLU prediction head causes the clearest degradation among the tested component changes. Additional relation-path calibrations can produce high single-seed peaks, but their multi-seed behavior is less stable. The evidence suggests that ranking-aware stock models benefit most reliably from bounded residual score formation rather than from indiscriminate architectural expansion.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk / execution.

## Notes

