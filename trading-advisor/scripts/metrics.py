#!/usr/bin/env python3
"""Shared Prometheus metrics for TOK trading system.

This module provides a single CollectorRegistry and shared metrics
to avoid duplication when multiple modules are imported.
"""
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# Single shared registry for the entire TOK system
TOK_REGISTRY = CollectorRegistry()

# Free Data metrics
FD_CG_CALLS = Counter('fd_cg_calls_total', 'Total CoinGecko API calls', ['status'], registry=TOK_REGISTRY)
FD_CG_LATENCY = Histogram('fd_cg_call_latency_seconds', 'CoinGecko API call latency', registry=TOK_REGISTRY)
FD_MARKETS_FETCHED = Counter('fd_markets_fetched_total', 'Total markets fetched', ['source'], registry=TOK_REGISTRY)
FD_MARKETS_PROCESSED = Gauge('fd_markets_processed', 'Number of markets processed in last run', registry=TOK_REGISTRY)

# Signal Validator metrics
SV_SIGNALS_PROCESSED = Counter('sv_signals_processed_total', 'Total signals processed', ['status'], registry=TOK_REGISTRY)
SV_BACKTEST_LATENCY = Histogram('sv_backtest_latency_seconds', 'Backtest latency', registry=TOK_REGISTRY)
SV_BACKTESTS_RUN = Counter('sv_backtests_run_total', 'Total backtests run', ['engine'], registry=TOK_REGISTRY)

# Portfolio Engine metrics
PE_PORTFOLIO_VALUE = Gauge('pe_portfolio_value', 'Current portfolio value', registry=TOK_REGISTRY)
PE_DRAWDOWN = Gauge('pe_drawdown_percent', 'Current portfolio drawdown percent', registry=TOK_REGISTRY)
PE_POSITIONS = Gauge('pe_open_positions', 'Number of open positions', registry=TOK_REGISTRY)
PE_OPTIMIZATION_TRIALS = Counter('pe_optimization_trials_total', 'Optuna optimization trials', ['status'], registry=TOK_REGISTRY)

# Briefing metrics
BR_BRIEFING_DURATION = Histogram('br_briefing_duration_seconds', 'Briefing generation duration', registry=TOK_REGISTRY)
BR_SIGNALS_GENERATED = Counter('br_signals_generated_total', 'Total signals generated', ['tier'], registry=TOK_REGISTRY)


def get_metrics() -> str:
    """Return Prometheus metrics as text for scraping."""
    return generate_latest(TOK_REGISTRY).decode('utf-8')