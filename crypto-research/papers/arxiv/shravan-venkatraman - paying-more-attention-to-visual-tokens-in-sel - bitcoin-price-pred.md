---
title: 'Paying More Attention to Visual Tokens in Self-Evolving Large Multimodal Models'
authors: 'Shravan Venkatraman, Ritesh Thawkar, Omkar Thawakar, Rao Muhammad Anwer, Hisham Cholakkal, Salman Khan, Fahad Khan'
url: 'http://arxiv.org/abs/2606.27373v1'
source: 'arxiv'
query: 'Bitcoin price prediction'
retrieved: '2026-06-26T14:20:10.479654+00:00'
updated: '2026-06-25T17:59:55Z'
category: 'pending_tag'
relevance: 'tbd'
---

# Paying More Attention to Visual Tokens in Self-Evolving Large Multimodal Models

## Source
- arXiv: http://arxiv.org/abs/2606.27373v1

## Summary
Recently, self-evolving large multimodal models (LMMs) have received attention for improving visual reasoning in a purely unsupervised setting. However, multi-role self-play and self-consistency reward schemes in existing self-evolving LMMs optimize answer agreement without ensuring the decoder attends to visual content, relying instead on statistical language priors to produce self consistent outputs. This leads to a persistent failure mode we term visual under-conditioning, where the decoder relies on language priors rather than the image during generation, manifesting as insufficient attention to visual tokens. As a result, current self-evolving LMMs struggle on vision--language understanding tasks such as image captioning and visual question answering. To address this, we propose VISE (Visual Invariance Self-Evolution), a purely unsupervised self-evolving framework that directly regularizes the model's visual conditioning policy through two complementary invariance-based rewards: a geometric invariance reward that enforces spatial consistency under known transformations, and a semantic invariance reward that penalizes evidence-agnostic generation by requiring the model to recognize the absence of evidence when predicted regions are perturbed. VISE operates within a single model without specialist roles, external reward models, or annotations, and is trained on raw unlabeled images. Experiments on 18 benchmarks demonstrate the efficacy of our approach. Using Qwen3-VL-2B as the base model, VISE achieves gains of $+16.85$ CIDEr on COCO and $+19.66$ CIDEr on TextCaps, reduces object hallucination by $5.0$ Chair-I points, and generalizes across four model families and scales. Our code and models are available at https://mbzuai-oryx.github.io/VISE

## Relevance
- To be evaluated and tagged as microstructure / sentiment / onchain / strategy / risk.

## Notes

