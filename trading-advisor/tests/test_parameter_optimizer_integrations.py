#!/usr/bin/env python3
"""Tests for parameter_optimizer tool integrations (Optuna)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategy'))

import parameter_optimizer
import pytest


class TestOptunaIntegration:
    """Test Optuna optimization integration."""

    @pytest.mark.skipif(not parameter_optimizer.OPTUNA_AVAILABLE, reason="optuna not available")
    def test_optimize_with_optuna_runs(self):
        """Test Optuna optimization runs and returns best params."""
        result = parameter_optimizer.optimize_with_optuna(n_trials=5)

        assert "best_params" in result
        assert "best_value" in result
        assert "n_trials" in result
        assert "study" in result

        # Check expected param keys
        expected_keys = {"min_24h_change_pct", "score_threshold", "regime_multiplier"}
        assert set(result["best_params"].keys()) == expected_keys

    @pytest.mark.skipif(not parameter_optimizer.OPTUNA_AVAILABLE, reason="optuna not available")
    def test_optimize_with_optuna_param_bounds(self):
        """Test Optuna respects parameter bounds."""
        result = parameter_optimizer.optimize_with_optuna(n_trials=5)

        params = result["best_params"]
        assert 0.5 <= params["min_24h_change_pct"] <= 8.0
        assert 10 <= params["score_threshold"] <= 50
        assert 0.5 <= params["regime_multiplier"] <= 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])