#!/usr/bin/env python3
"""Tests for signal_validator tool integrations (vectorbt, empyrical)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategy'))

import numpy as np
import pandas as pd
import pytest
import signal_validator


class TestVectorBTIntegration:
    """Test vectorbt backtest integration."""

    @pytest.mark.skipif(not signal_validator.VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_backtest_vectorbt_basic(self):
        """Test basic vectorbt backtest runs without error."""
        close = pd.Series(
            np.cumprod(1 + np.random.randn(100) * 0.02) * 100,
            index=pd.date_range(end=pd.Timestamp.now(), periods=100, freq='D')
        )
        entries = pd.Series(np.random.rand(100) > 0.95, index=close.index)
        exits = pd.Series(np.random.rand(100) > 0.95, index=close.index)

        result = signal_validator.backtest_vectorbt(close, entries, exits)

        assert "stats" in result
        assert "total_return" in result
        assert "sharpe" in result
        assert "max_drawdown" in result
        assert "win_rate" in result
        assert "profit_factor" in result
        assert "total_trades" in result

    @pytest.mark.skipif(not signal_validator.VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_backtest_vectorbt_with_stops(self):
        """Test vectorbt backtest with stop loss and take profit."""
        close = pd.Series(
            np.cumprod(1 + np.random.randn(100) * 0.02) * 100,
            index=pd.date_range(end=pd.Timestamp.now(), periods=100, freq='D')
        )
        entries = pd.Series(np.random.rand(100) > 0.95, index=close.index)
        exits = pd.Series(np.random.rand(100) > 0.95, index=close.index)

        result = signal_validator.backtest_vectorbt(
            close, entries, exits,
            stop_pct=0.05,   # 5% stop loss
            target_pct=0.10, # 10% take profit
            trailing_pct=0.03 # 3% trailing
        )

        assert "stats" in result
        assert result["total_trades"] >= 0


class TestEmpyricalIntegration:
    """Test empyrical metrics integration."""

    @pytest.mark.skipif(not signal_validator.EMPYRICAL_AVAILABLE, reason="empyrical not available")
    def test_empyrical_metrics_basic(self):
        """Test empyrical metrics calculation."""
        returns = pd.Series(np.random.randn(100) * 0.01)

        metrics = signal_validator._empyrical_metrics(returns)

        expected_keys = [
            "sharpe_ratio", "max_drawdown", "calmar_ratio",
            "sortino_ratio", "omega_ratio", "annual_return",
            "annual_volatility", "stability", "tail_ratio",
            "var_95", "cvar_95"
        ]
        for key in expected_keys:
            assert key in metrics

    @pytest.mark.skipif(not signal_validator.EMPYRICAL_AVAILABLE, reason="empyrical not available")
    def test_empyrical_metrics_insufficient_data(self):
        """Test empyrical metrics with insufficient data."""
        returns = pd.Series([0.01])  # Only 1 data point

        metrics = signal_validator._empyrical_metrics(returns)

        assert metrics == {}  # Returns empty dict for insufficient data


class TestSummarizeWithEmpyrical:
    """Test enhanced summarize with empyrical metrics."""

    @pytest.mark.skipif(not signal_validator.EMPYRICAL_AVAILABLE, reason="empyrical not available")
    def test_summarize_with_empyrical(self):
        """Test summarize_with_empyrical includes empyrical metrics."""
        test_signals = [
            {"validation_status": "backtested", "pnl_pct": 2.5, "exit_reason": "target", "r_multiple": 1.2, "symbol": "BTC"},
            {"validation_status": "backtested", "pnl_pct": -1.8, "exit_reason": "stop", "r_multiple": -0.8, "symbol": "ETH"},
            {"validation_status": "backtested", "pnl_pct": 3.1, "exit_reason": "trailing_stop", "r_multiple": 1.5, "symbol": "SOL"},
        ]

        summary = signal_validator.summarize_with_empyrical(test_signals)

        assert "empyrical_metrics" in summary
        assert "empyrical_available" in summary
        assert summary["empyrical_available"] is True
        assert "sharpe_ratio" in summary["empyrical_metrics"]

    def test_summarize_without_empyrical(self):
        """Test summarize works without empyrical (fallback)."""
        # This should work even if empyrical is not available
        test_signals = [
            {"validation_status": "backtested", "pnl_pct": 2.5, "exit_reason": "target", "r_multiple": 1.2, "symbol": "BTC"},
        ]
        summary = signal_validator.summarize(test_signals)
        assert "total_signals" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])