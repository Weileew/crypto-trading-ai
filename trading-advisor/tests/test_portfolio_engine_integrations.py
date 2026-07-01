#!/usr/bin/env python3
"""Tests for portfolio_engine tool integrations (empyrical, Optuna)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategy'))

import portfolio_engine
import pytest


class TestEmpyricalIntegration:
    """Test empyrical metrics in portfolio_engine."""

    @pytest.mark.skipif(not portfolio_engine.EMPYRICAL_AVAILABLE, reason="empyrical not available")
    def test_journal_performance_empyrical(self):
        """Test enhanced journal performance with empyrical metrics."""
        result = portfolio_engine.journal_performance_empyrical(days=30)

        assert "empyrical_available" in result
        if result["status"] == "ok":
            assert "empyrical_metrics" in result
            if result["empyrical_metrics"]:
                expected_keys = [
                    "sharpe_ratio", "max_drawdown", "calmar_ratio",
                    "sortino_ratio", "omega_ratio", "annual_return",
                    "annual_volatility", "stability", "var_95", "cvar_95"
                ]
                for key in expected_keys:
                    assert key in result["empyrical_metrics"]

    @pytest.mark.skipif(not portfolio_engine.EMPYRICAL_AVAILABLE, reason="empyrical not available")
    def test_calibration_health_empyrical(self):
        """Test calibration health includes empyrical metrics."""
        lines, score = portfolio_engine.calibration_health_empyrical()

        assert isinstance(lines, list)
        assert isinstance(score, float)
        assert 0 <= score <= 1
        # Check empyrical section is included
        empyrical_section = any("Empyrical Risk Metrics" in line for line in lines)
        assert empyrical_section


class TestOptunaIntegration:
    """Test Optuna portfolio parameter optimization."""

    @pytest.mark.skipif(not portfolio_engine.OPTUNA_AVAILABLE, reason="optuna not available")
    def test_optimize_portfolio_params(self):
        """Test Optuna portfolio optimization runs."""
        # Use 60 days to get more data
        result = portfolio_engine.optimize_portfolio_params(n_trials=5, lookback_days=60)

        # Should either succeed or fail gracefully with error message
        if "error" in result:
            assert "insufficient journal data" in result["error"]
        else:
            assert "best_params" in result
            assert "best_value" in result
            expected_keys = {"concurrency_max", "drawdown_limit_pct", "correlation_threshold", "correlation_penalty"}
            assert set(result["best_params"].keys()) == expected_keys

    @pytest.mark.skipif(not portfolio_engine.OPTUNA_AVAILABLE, reason="optuna not available")
    def test_suggest_params_file_updates(self):
        """Test suggestion generation."""
        # Test with error result
        error_result = {"error": "test error"}
        suggestions = portfolio_engine.suggest_params_file_updates(error_result)
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert "Optimization failed" in suggestions[0]

        # Test with success result
        success_result = {
            "best_params": {
                "concurrency_max": 4,
                "drawdown_limit_pct": 12.0,
                "correlation_threshold": 0.65,
                "correlation_penalty": 0.5
            },
            "best_value": 1.5,
            "n_trials": 10
        }
        suggestions = portfolio_engine.suggest_params_file_updates(success_result)
        assert isinstance(suggestions, list)
        assert any("params.json" in s for s in suggestions)
        assert any("research-calibrations.json" in s for s in suggestions)


class TestCorrelationMatrix:
    """Test correlation matrix function."""

    def test_get_correlation_matrix_structure(self):
        """Test correlation matrix returns expected structure."""
        result = portfolio_engine.get_correlation_matrix(["BTC", "ETH"], days=30)
        assert "matrix" in result
        assert "high_corr_pairs" in result
        assert isinstance(result["matrix"], dict)
        assert isinstance(result["high_corr_pairs"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])