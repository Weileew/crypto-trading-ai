---
title: 'RouterVLA: Turning Smoke Tests into Supervision for Heterogeneous VLA Selection'
authors: 'Xingyu Ren, Chugang Yi, Ge Ma, Youran Sun'
url: 'http://arxiv.org/abs/2606.27355v1'
source: 'arxiv'
query: 'crypto machine learning trading'
retrieved: '2026-06-26T14:20:13.879445+00:00'
updated: '2026-06-25T17:56:33Z'
category: 'pending_tag'
relevance: 'tbd'
---

# RouterVLA: Turning Smoke Tests into Supervision for Heterogeneous VLA Selection

## Source
- arXiv: http://arxiv.org/abs/2606.27355v1

## Summary
We study whether pre-deployment evaluation rollouts can be reused to supervise policy selection. Robot teams routinely smoke test candidate vision-language-action (VLA) policies, then compress those trials into a global winner. RouterVLA evaluates this idea with outcome-disjoint cross-fitting: recorded probes build a profile for each frozen expert, and a separate trial scores the selected expert without entering its profile. Across 34,752 LIBERO-Plus rollout records, a transparent probe-success rule raises held-out success from 0.4686 to 0.6149, a +14.64pp gain. Under the scalar-only profiles studied here, learned scorers are statistically indistinguishable from this rule, showing that commissioning carries the routing value while extra scalar scorer capacity does not create it. Reusing the scored trial inflates the measured gain by $1.87\times$, so credible ledger routing needs outcome separation; model scaling improves individual policies, while commissioning-aware routing improves the system built from them.

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

