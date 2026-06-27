---
title: 'Continual Robot Policy Learning via Variational Neural Dynamics'
authors: 'Jiaxu Xing, Zhiyuan Zhu, Yunfan Ren, Ismail Geles, Yifan Zhai, Rudolf Reiter, Davide Scaramuzza'
url: 'http://arxiv.org/abs/2606.27353v1'
source: 'arxiv'
query: 'crypto machine learning trading'
retrieved: '2026-06-26T14:20:13.879522+00:00'
updated: '2026-06-25T17:56:04Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Continual Robot Policy Learning via Variational Neural Dynamics

## Source
- arXiv: http://arxiv.org/abs/2606.27353v1

## Summary
Robots deployed in the real world rarely operate under a single fixed dynamics model: wind changes, payloads vary, batteries drain, contacts shift, and hardware wears. Yet most learning-based controllers are trained once and deployed as if learning were complete. This prevents the robot from using deployment experience to further improve task performance. In this work, we propose a continual learning framework that uses real-world experience to improve robot policies under hidden and recurring dynamics. Our method learns a condition-aware dynamics model from real state-action trajectories by combining an analytical physics prior with a neural residual for unmodeled effects. A recurrent encoder infers the current hidden condition from recent interaction, and this estimate conditions both the residual model and the policy. Policy learning is performed via differentiable simulation using diverse learned dynamics sampled from the latent model. At deployment, these sampled conditions are replaced by conditions inferred online from recent real interaction, allowing the policy to recover recurring dynamics by recognition rather than residual re-fitting. Through extensive simulation studies and real-world experiments, we demonstrate that the framework improves policy performance under diverse unobserved disturbances. On real quadrotor trajectory tracking under changing wind, the policy recovers from recurring disturbances in roughly 1s, about 5x faster than online residual re-fitting. It also reduces large-disturbance hover and tracking errors by 65.7% and 53.3% over the state-of-the-art online adaptation approaches

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

