---
title: 'Auditing Asset-Specific Preferences in Financial Large Language Models: Evidence from Bitcoin Representations and Portfolio Allocation'
authors: 'Wenbin Wu'
url: 'http://arxiv.org/abs/2606.02528v1'
source: 'arxiv/q-fin.GN cs.CY cs.LG'
query: 'cat:q-fin.*+AND+all:crypto'
retrieved: '2026-06-29T22:31:50.794863+00:00'
updated: '2026-06-01'
categories: 'q-fin.GN cs.CY cs.LG'
tier: 'B'
category: 'risk'
relevance: '1.0'
tags: [risk, crypto]
---

# Auditing Asset-Specific Preferences in Financial Large Language Models: Evidence from Bitcoin Representations and Portfolio Allocation

- **Source**: arXiv (q-fin.GN cs.CY cs.LG)
- **Tier**: B (preprint)
- **Updated**: 2026-06-01
- **URL**: http://arxiv.org/abs/2606.02528v1
- **Strategy tags**: risk, crypto
- **Relevance**: 1.0

## Abstract
Large language models now power robo-advisors and trading agents, yet whether they carry built-in biases toward specific assets is largely untested. We ask three questions: do LLMs systematically prefer certain financial instruments; can an internal representation with causal leverage over those preferences be identified; and does that representation affect downstream financial decisions?
  We develop a three-level audit protocol and apply it to Bitcoin. First, a behavioral audit of eight frontier LLMs shows that Bitcoin's ranking among money-like instruments is frame-dependent: models place it around rank 5 of 8 as "reliable money" but near the top under crisis and autonomous-agent frames, and an attribute-swap experiment confirms rankings track functional properties, not names. Second, we open a model's internals: a search across thousands of sparse-autoencoder features in Gemma 3 identifies a dominant Bitcoin-selective feature. Amplifying it shifts the model toward the asset and suppressing it shifts the model away, even when "Bitcoin" never appears in the prompt. Third, we test financial consequences: amplification raises Bitcoin's portfolio share by 5.2 percentage points while suppression lowers it by 4.6 pp, with amplification reallocating within crypto and suppression cutting total crypto exposure.
  We characterize this as bounded behavioral leverage (leverage meaning causal influence over outputs, not financial leverage): an identifiable internal feature can be perturbed to move financial choices, but only within measurable limits. The framework links internal representations to external recommendations, validated with random controls and mechanism boundaries. As LLMs become autonomous financial agents, this is a first step toward a behavioral layer for emerging know-your-agent (KYA) standards: knowing what an agent prefers, and how far that preference can be moved.

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

