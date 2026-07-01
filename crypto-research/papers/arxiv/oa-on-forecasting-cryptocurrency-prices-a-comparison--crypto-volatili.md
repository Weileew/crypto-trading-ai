---
title: 'On Forecasting Cryptocurrency Prices: A Comparison of Machine Learning, Deep Learning, and Ensembles'
authors: 'Kate Murray, Andrea Rossi, Diego Carraro, Andrea Visentin'
url: 'https://doi.org/10.3390/forecast5010010'
source: 'openalex/Forecasting'
query: 'crypto volatility forecasting'
retrieved: '2026-06-29T22:31:42.838657+00:00'
year: '2023'
doi: 'https://doi.org/10.3390/forecast5010010'
tier: 'C'
category: 'risk'
relevance: '0.85'
tags: [risk, prediction, crypto]
---

# On Forecasting Cryptocurrency Prices: A Comparison of Machine Learning, Deep Learning, and Ensembles

- **Source**: OpenAlex (Forecasting)
- **Tier**: C (supplementary)
- **Year**: 2023
- **DOI**: https://doi.org/10.3390/forecast5010010
- **Strategy tags**: risk, prediction, crypto
- **Relevance**: 0.85

## Abstract
Traders and investors are interested in accurately predicting cryptocurrency prices to increase returns and minimize risk. However, due to their uncertainty, volatility, and dynamism, forecasting crypto prices is a challenging time series analysis task. Researchers have proposed predictors based on statistical, machine learning (ML), and deep learning (DL) approaches, but the literature is limited. Indeed, it is narrow because it focuses on predicting only the prices of the few most famous cryptos. In addition, it is scattered because it compares different models on different cryptos inconsistently, and it lacks generality because solutions are overly complex and hard to reproduce in practice. The main goal of this paper is to provide a comparison framework that overcomes these limitations. We use this framework to run extensive experiments where we compare the performances of widely used statistical, ML, and DL approaches in the literature for predicting the price of five popular cryptocurrencies, i.e., XRP, Bitcoin (BTC), Litecoin (LTC), Ethereum (ETH), and Monero (XMR). To the best of our knowledge, we are also the first to propose using the temporal fusion transformer (TFT) on this task. Moreover, we extend our investigation to hybrid models and ensembles to assess whether combining single models boosts prediction accuracy. Our evaluation shows that DL approaches are the best predictors, particularly the LSTM, and this is consistently true across all the cryptos examined. LSTM reaches an average RMSE of 0.0222 and MAE of 0.0173, respectively, 2.7% and 1.7% better than the second-best model. To ensure reproducibility and stimulate future research contribution, we share the dataset and the code of the experiments.

## Auto-Finding
Risk finding: confirms that volatility clustering is persistent in crypto, supporting dynamic position sizing and regime-aware stop placement.

## Notes

