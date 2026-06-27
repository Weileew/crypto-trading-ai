#!/usr/bin/env python3
"""Refresh pre-market market context: liquidity snapshot + market snapshot."""
import os, sys
_cp = os.path.dirname
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
from market_snapshot import MarketSnapshot, write_json, read_json

REPORTS = os.path.join(_cp(current_dir), "reports")


def run():
    from free_data import fetch_markets, fetch_global, fetch_fear_greed, fetch_coincap
    markets = fetch_markets()
    global_data = fetch_global()
    fng = fetch_fear_greed()
    assets = fetch_coincap()
    snap = MarketSnapshot(assets, markets, global_data, fng)
    write_json(os.path.join(REPORTS, "pre_market_snapshot.json"), snap.summary())
    print("snapshot written to reports/pre_market_snapshot.json")


if __name__ == "__main__":
    run()
