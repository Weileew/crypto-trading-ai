---
title: 'Persona-Trained Monte Carlo: Estimating Market-Outcome Distributions via Swarms of Persona-Conditioned Neural Policy Bots in a Limit Order Book'
authors: 'Salavat Ishbulatov'
url: 'http://arxiv.org/abs/2606.29556v1'
source: 'arxiv/cs.LG cs.MA'
query: 'cat:cs.LG+AND+all:cryptocurrency+trading'
retrieved: '2026-06-30T13:59:06.217081+00:00'
updated: '2026-06-28'
categories: 'cs.LG cs.MA'
tier: 'B'
category: 'liquidity'
relevance: '1.0'
tags: [liquidity, risk, defi]
---

# Persona-Trained Monte Carlo: Estimating Market-Outcome Distributions via Swarms of Persona-Conditioned Neural Policy Bots in a Limit Order Book

- **Source**: arXiv (cs.LG cs.MA)
- **Tier**: B (preprint)
- **Updated**: 2026-06-28
- **URL**: http://arxiv.org/abs/2606.29556v1
- **Strategy tags**: liquidity, risk, defi
- **Relevance**: 1.0

## Abstract
We propose Persona-Trained Monte Carlo (PTMC), a method for estimating distributions of market-outcome statistics by repeatedly simulating limit-order-book interaction among swarms of persona-conditioned neural-policy trading bots. Each run instantiates many bots sharing one trained policy network but conditioned on heterogeneous, individually sampled persona parameters drawn from a learned trader-heterogeneity distribution; the bots interact in a continuous double auction, and the resulting price path is one Monte Carlo sample. Repeating this over independent persona-population draws yields an ensemble from which a target market statistic is estimated. Randomness enters through persona draws, within-run action sampling, and optional exogenous shocks, not solely through price as in classical Monte Carlo. We distinguish PTMC from adjacent paradigms, including classical Monte Carlo, hand-coded agent-based models, single-agent reinforcement learning, and large-language-model-based generative agents. To justify the design, we survey cross-disciplinary foundations -- agent-based computational economics, market microstructure, behavioral finance, deep reinforcement learning, generative/LLM-based agents, news-driven trading, systemic risk, econophysics, and game theory -- connecting each literature to a specific design choice in the policy network, training data, or validation protocol. We formalize the PTMC estimator and its convergence properties, specify a candidate bot architecture and training objective, and propose a four-level validation methodology: stylized-fact matching, microstructure- and agent-level checks, and historical stress-test comparison against a zero-intelligence baseline. The framework is proposed but not implemented: we contribute a formal estimator, a cross-disciplinary design justification, and a validation roadmap, and conclude with open research questions.

## Auto-Finding
Liquidity finding: confirms that orderbook depth and spread dynamics predict short-term price pressure — useful for entry timing and slippage checks.

## Notes

