---
title: 'PhysiFormer: Learning to Simulate Mechanics in World Space'
authors: 'Yiming Chen, Yushi Lan, Andrea Vedaldi'
url: 'http://arxiv.org/abs/2606.27364v1'
source: 'arxiv'
query: 'Bitcoin price prediction'
retrieved: '2026-06-26T14:20:10.479946+00:00'
updated: '2026-06-25T17:59:00Z'
category: 'pending_tag'
relevance: 'tbd'
---

# PhysiFormer: Learning to Simulate Mechanics in World Space

## Source
- arXiv: http://arxiv.org/abs/2606.27364v1

## Summary
We present PhysiFormer, a diffusion transformer for physically-plausible 3D object motion. Unlike video world models that operate in view-dependent pixel space, PhysiFormer represents objects as 3D meshes expressed in world coordinates. Given the initial vertex positions and velocities, as well as object material type, rigid or elastic, the model samples future vertex trajectories. While related neural physics approaches build on ad-hoc latent spaces or explicitly enforce rigidity and causality, PhysiFormer shows that excellent results can be obtained without any such inductive biases, by casting vertex trajectory prediction as a single denoising diffusion process directly in world coordinates. The probabilistic formulation captures uncertainty in the learned dynamics, enabling diverse plausible futures from initial conditions, making this framework potentially useful for applications with unobserved uncertainty. The model features attention factorised over time, space, and objects for efficiency, enabling permutation-invariant multi-object reasoning without needing explicit object encoding. Trained on over 100k simulated trajectories, PhysiFormer generates rigid and elastic mechanics, and generalises to mixed-material settings, unseen real-world geometries, and larger object counts. It substantially outperforms autoregressive baselines in trajectory accuracy, rigidity preservation, and momentum-based physical consistency. Our results position coordinate-space diffusion as a promising step toward view-invariant, geometry-aware world modelling for robotics, graphics, and physical design. Visualisations, code, and models are available at https://yimingc9.github.io/physiformer.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

