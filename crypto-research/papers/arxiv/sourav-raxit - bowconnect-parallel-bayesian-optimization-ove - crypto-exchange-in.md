---
title: 'BOWConnect: Parallel Bayesian Optimization over Windows with Learned Local Cost Maps for Sample-Efficient Kinodynamic Motion Planning'
authors: 'Sourav Raxit, Abdullah Al Redwan Newaz, Jose Fuentes, Leonardo Bobadilla'
url: 'http://arxiv.org/abs/2606.27292v1'
source: 'arxiv'
query: 'crypto exchange inefficiency'
retrieved: '2026-06-26T14:20:15.376381+00:00'
updated: '2026-06-25T17:11:33Z'
category: 'pending_tag'
relevance: 'tbd'
---

# BOWConnect: Parallel Bayesian Optimization over Windows with Learned Local Cost Maps for Sample-Efficient Kinodynamic Motion Planning

## Source
- arXiv: http://arxiv.org/abs/2606.27292v1

## Summary
This paper presents BOWConnect, a bidirectional parallel kinodynamic motion planner that addresses three fundamental limitations of existing sampling-based methods: sample inefficiency in high-dimensional state spaces, unreliable cost heuristics under dynamic constraints, and poor performance in narrow passage environments. Unlike classical planners that rely on random control sampling and geometric distance heuristics, BOWConnect integrates Bayesian Optimization over Windows (BOW) as a learning-based steering function within a parallel tree-based exploration framework, enabling each worker to learn local cost maps and constraints to guide sampling toward dynamically feasible and collision-free controls. A bidirectional architecture simultaneously grows forward and backward trees from the start and goal regions in parallel threads, with a spatial hashing mechanism enabling fast connection queries and a boundary value problem solver generating kinodynamically consistent bridge trajectories. Extensive evaluations across ten benchmark environments demonstrate that BOWConnect achieves 100\% success while delivering the fastest or near-fastest planning time in complex scenarios, including narrow passages and non-convex spaces where state-of-the-art planners fail or degrade substantially. Real-world deployment on a ground vehicle and a quadrotor confirms real-time planning with no collisions. Videos of real-world and simulated experiments, high-resolution versions of the figures, and the open-source code are available at https://bow-connect.github.io/.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

