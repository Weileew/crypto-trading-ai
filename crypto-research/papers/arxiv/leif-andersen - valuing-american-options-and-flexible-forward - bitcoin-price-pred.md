---
title: 'Valuing American options and Flexible Forwards contracts in time-dependent models'
authors: 'Leif Andersen, Andrey Itkin, Rakhymzhan Kazbek'
url: 'http://arxiv.org/abs/2606.27335v1'
source: 'arxiv'
query: 'Bitcoin price prediction'
retrieved: '2026-06-26T14:20:10.480368+00:00'
updated: '2026-06-25T17:46:02Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Valuing American options and Flexible Forwards contracts in time-dependent models

## Source
- arXiv: http://arxiv.org/abs/2606.27335v1

## Summary
A flexible forward (FF) is a customized FX hedging instrument that guarantees a fixed exchange rate while letting the holder choose the delivery date within a pre-agreed window. It is therefore an American-style option on timing, and its valuation must respect the volatility skew of the underlying currency pair. We price FF contracts (and, more generally, American options) under a time-inhomogeneous Heston model which captures the forward-skew term structure while preserving analytical tractability through a recursive (matrix) Riccati solution for the joint characteristic function. Extending the integral-equation (decomposition) approach to time-dependent coefficients, we derive a Volterra equation characterizing the early-exercise surface. The expectation in the decomposition formula is evaluated by two complementary spectral methods: a double cosine (COS) expansion of the transition density, and a damped-Sinc (DSINC) local-basis scheme that is more accurate and stays robust when a low Feller ratio or large vol-of-vol induces Gibbs oscillations in the COS series. Benchmarked against a penalty-iteration MCS-ADI finite-difference solver, both methods price a contract in about 1-2 seconds, roughly an order of magnitude faster than the finest finite-difference grid, while DSINC improves median accuracy over COS by about a factor of twelve. The experiments also show that the early-exercise surface is a substantially nonlinear function of the variance, contrary to the linear-in-variance approximation common in earlier work.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

