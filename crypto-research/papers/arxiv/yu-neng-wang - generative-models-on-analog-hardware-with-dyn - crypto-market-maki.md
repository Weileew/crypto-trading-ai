---
title: 'Generative Models on Analog Hardware with Dynamics'
authors: 'Yu-Neng Wang, Sara Achour'
url: 'http://arxiv.org/abs/2606.27294v1'
source: 'arxiv'
query: 'crypto market making'
retrieved: '2026-06-26T14:20:13.291635+00:00'
updated: '2026-06-25T17:13:00Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Generative Models on Analog Hardware with Dynamics

## Source
- arXiv: http://arxiv.org/abs/2606.27294v1

## Summary
Analog hardware platforms such as coupled oscillators and Analog Ising Machines naturally solve differential equations at a fraction of the energy cost of digital computation, making them attractive for low-power generative modeling, yet a fundamental mismatch exists: modern generative models assume flexible, software-defined dynamics, whereas analog hardware imposes fixed, physics-determined differential equations with limited approximation capacity. This paper introduces Analog Interaction Systems (AIS), a unified framework for hardware-implementable dynamical systems, and empirically characterizes their expressivity gap relative to neural network baselines. Two hardware-compatible mechanisms are proposed to narrow this gap - time-varying piecewise parameters and hidden physical states - and a Wasserstein GAN training procedure is developed to enable training of these models without requiring them to follow a specific trajectory. We characterize how area and power scale with connection density and precision, showing that sparse connectivity and low-bit-width quantized parameters are necessary for practical implementation, and estimate an energy cost of 23uJ per generated image for the chosen architecture, representing a 2-orders-of-magnitude improvement over digital baselines. On MNIST and Fashion-MNIST, our oscillator-based AIS achieves FID scores of 27.6 and 80.8, outperforming the best prior hardware-implementable analog generative models by 3-4x with a 4-bit sparse architecture.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

