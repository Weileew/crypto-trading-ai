#!/usr/bin/env python3
"""Read-only crypto market snapshot; no transfers, no signing, no KYC reads."""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
os.makedirs(REPORTS, exist_ok=True)


def write_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def read_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class MarketSnapshot:
    def __init__(self, assets, market_data, global_data, fng):
        self.assets = assets
        self.market_data = market_data
        self.global_data = global_data
        self.fng = fng

    def summary(self) -> dict:
        top = (self.market_data or [])[:15] if isinstance(self.market_data, list) else []
        return {
            "timestamp": self.fng.get("timestamp") if isinstance(self.fng, dict) else None,
            "fng": self.fng,
            "btc_dominance_pct": self.global_data.get("data", {}).get("market_cap_percentage", {}).get("btc") if isinstance(self.global_data, dict) else None,
            "top_movers": _top_movers(top),
        }


def _top_movers(top):
    out = []
    for c in top:
        out.append({
            "symbol": c.get("symbol"),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_24h": c.get("price_change_percentage_24h"),
            "change_7d": c.get("price_change_percentage_7d_in_currency"),
            "volume": c.get("total_volume"),
            "mcap": c.get("market_cap"),
        })
    return out[:12]
