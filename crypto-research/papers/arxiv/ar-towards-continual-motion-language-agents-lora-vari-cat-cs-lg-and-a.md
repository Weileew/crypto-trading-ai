---
title: 'Towards Continual Motion-Language Agents: LoRA Variants for Incremental Motion Understanding and Generation'
authors: 'Bertram Taetz, Hugo Albuquerque Cosme da Silva, Gabriele Bleser-Taetz'
url: 'http://arxiv.org/abs/2606.30266v1'
source: 'arxiv/cs.LG cs.AI'
query: 'cat:cs.LG+AND+all:cryptocurrency+trading'
retrieved: '2026-06-30T13:59:06.211654+00:00'
updated: '2026-06-29'
categories: 'cs.LG cs.AI'
tier: 'B'
category: 'risk'
relevance: '0.85'
tags: [risk, defi, crypto]
---

# Towards Continual Motion-Language Agents: LoRA Variants for Incremental Motion Understanding and Generation

- **Source**: arXiv (cs.LG cs.AI)
- **Tier**: B (preprint)
- **Updated**: 2026-06-29
- **URL**: http://arxiv.org/abs/2606.30266v1
- **Strategy tags**: risk, defi, crypto
- **Relevance**: 0.85

## Abstract
Motion-language agents must possess the bidirectional capability to both understand human movement (motion-to-text, M2T) and generate it from natural language (text-to-motion, T2M). While foundational models have achieved strong performance in static settings, autonomous agents operating in dynamic environments must continuously incorporate new motion concepts -- such as novel athletic styles or specialized gestures -- without catastrophic forgetting of previously acquired skills. We investigate the stability-plasticity trade-off in bidirectional motion-language learning under sequential task exposure. Building on a frozen large language model backbone, we introduce low-rank adaptation (LoRA) variants designed to mitigate inter-task interference. We specifically propose mixture-of-experts architectures that utilize an autoencoder-based router to select task-specific experts at inference time, so that no task-label is needed. To evaluate these methods, we establish a reproducible five-task benchmark derived from HumanML3D through semantic clustering of motion descriptions. Our experimental results demonstrate near-zero forgetting across both M2T and T2M directions while maintaining high generation and captioning quality. Furthermore, we show that hard expert selection via routing significantly outperforms soft expert blending in quality metrics, indicating that preserving expert isolation is critical for maintaining performance in our continual learning setting. Finally, we observe that a divergence between token-level accuracy and downstream generation quality may occur, highlighting the need for more comprehensive evaluation protocols in future research on lifelong motion-language agents.

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

