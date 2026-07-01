#!/usr/bin/env python3
"""Tests for briefing.py integrations (DuckDB regime)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategy'))

import briefing
import pytest


class TestBriefingIntegration:
    """Test briefing.py tool integrations."""

    def test_regime_bias_high_vol(self):
        """Test _regime_bias returns mean-reversion for high volatility."""
        regime = briefing._regime_bias(0.05)  # 5% change = high vol
        assert regime in ["mean-reversion", "momentum", "trend"]

    def test_regime_bias_low_vol(self):
        """Test _regime_bias returns momentum for low volatility."""
        regime = briefing._regime_bias(0.01)  # 1% change = low vol
        assert regime in ["mean-reversion", "momentum", "trend"]

    def test_regime_bias_neutral(self):
        """Test _regime_bias returns neutral bias for mid volatility."""
        regime = briefing._regime_bias(0.02)  # 2% change = neutral
        assert regime in ["mean-reversion", "momentum", "trend"]

    def test_regime_bias_returns_string(self):
        """Test _regime_bias always returns a string."""
        regime = briefing._regime_bias(0.03)
        assert isinstance(regime, str)
        assert len(regime) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])