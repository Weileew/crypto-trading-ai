---
title: 'Not All Actions Are Equal: Rethinking Conditioning for Dexterous World Model'
authors: 'Zizhao Yuan, Zhengtu Liang, Taowen Wang, Qiwei Liang, Yichi Wang, Yunheng Wang, Yuetong Fang, Lusong Li, Zecui Zeng, Renjing Xu'
url: 'http://arxiv.org/abs/2606.27325v1'
source: 'arxiv'
query: 'Bitcoin price prediction'
retrieved: '2026-06-26T14:20:10.480571+00:00'
updated: '2026-06-25T17:36:35Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Not All Actions Are Equal: Rethinking Conditioning for Dexterous World Model

## Source
- arXiv: http://arxiv.org/abs/2606.27325v1

## Summary
Recent advances in action-conditioned world models show promising progress in modeling complex interactions and forecasting future states under diverse action sequences. While these models are often driven by stronger visual representations and model capacity, action conditioning itself remains underexplored. Most existing approaches compress the entire action sequence into a single representation, which works well for low-DoF control but becomes less reliable in high-DoF scenarios. We observe that high-DoF dexterous actions are inherently heterogeneous, spanning multiple orders of magnitude, where large-scale motions coexist with subtle but important signals. When uniformly aggregated, optimization exhibits an imbalance across action components, which hinders the modeling of fine-grained effects and affects action fidelity. We therefore propose DexAC-WM, which treats action conditioning as a structured process rather than global compression. DexAC preserves dimension-level semantics via action tokenization and aligns action signals with visual dynamics through local refinement and global modulation. To address the limited high-level semantic grounding in existing world models, we further introduce a semantic branch that provides rich object-scene priors, which enables world model to capture dynamic visual details while supporting high-DoF action-conditioned video prediction. Experiments on EgoDex and EgoVerse show that combining the semantic branch with DexAC significantly improves FID, FVD, and PCK, demonstrating gains in visual-temporal realism and action-following consistency. We further verify that DexAC extends to other backbones, showing the scalability of our structured action-conditioning design. These results suggest that scaling world models to high-DoF control requires both structured action modeling and semantic grounding.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

