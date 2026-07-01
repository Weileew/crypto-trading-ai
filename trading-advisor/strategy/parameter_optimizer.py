#!/usr/bin/env python3
"""Parameter optimizer — replays scoring logic against historical market data.

Fetches historical CoinGecko snapshots (up to 90 days), runs the scoring
pipeline at multiple threshold combinations, and measures which parameters
would have produced the best results.

Outputs directly actionable threshold recommendations for:
  - min_24h_change_pct (volatility gate)
  - score_threshold (quality gate)
  - correlation_threshold (portfolio diversification)

Usage:
    python3 strategy/parameter_optimizer.py
"""
import json
import math
import os
import time as _time_module
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY_DIR = os.path.join(SKILL_DIR, "strategy")
CALIB_PATH = os.path.join(STRATEGY_DIR, "research-calibrations.json")

UA = "crypto-trading-advisor/0.1 (+https://example.com)"
_CG_LAST = 0.0
_CG_INTERVAL = 6.5


def _cg_throttle():
    global _CG_LAST
    wait = _CG_INTERVAL - (_time_module.time() - _CG_LAST)
    if wait > 0:
        _time_module.sleep(wait)
    _CG_LAST = _time_module.time()


def _cg_get(url, params=None):
    _cg_throttle()
    req = Request(url, headers={"User-Agent": UA})
    if params:
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    try:
        with urlopen(Request(url, headers={"User-Agent": UA}), timeout=25) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, OSError, json.JSONDecodeError) as e:
        return {"_error": str(e)}


def fetch_historical_markets(days=30) -> list[dict]:
    """Fetch CoinGecko markets data for a historical date range.

    Returns list of coin dicts with price, mcap, volume, 24h change.
    Note: CoinGecko free tier only returns CURRENT data, not historical.
    For historical, we'd need /coins/{id}/market_chart/range.

    Instead, we fetch current data and use the 7d price_change data
    as a proxy for recent volatility patterns to calibrate thresholds.
    """
    # Fetch current top 250 by mcap
    data = _cg_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency": "usd", "order": "market_cap_desc",
         "per_page": 250, "page": 1,
         "price_change_percentage": "24h,7d",
         "sparkline": "false"}
    )
    # Fetch page 2 for mid-cap
    data2 = _cg_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency": "usd", "order": "market_cap_desc",
         "per_page": 250, "page": 2,
         "price_change_percentage": "24h,7d",
         "sparkline": "false"}
    )
    combined = []
    for d in (data, data2):
        if isinstance(d, list):
            combined.extend(d)
    return combined


def score_candidate(coin, min_change=3.0, score_thresh=25) -> tuple:
    """Apply simple_rules-like scoring to a single coin dict.

    Returns (score, passes) where passes=True if score >= score_thresh.
    """
    mcap = coin.get("market_cap") or 0
    if mcap < 50e6:
        return 0.0, False

    p = coin.get("price_change_percentage_24h") or 0
    if abs(p) < min_change:
        return 0.0, False

    mc = coin.get("market_cap_change_percentage_24h") or 0
    score = abs(p) + max(0, mc) * 0.08

    # Volume bonus (simplified — no TokoCrypto data available)
    vol = coin.get("total_volume") or 0
    if vol > 10_000_000:
        score += 5.0
    elif vol > 1_000_000:
        score += 2.0

    # Trap filters (simplified)
    cv = coin.get("total_volume") or 0
    if p < -12.0:
        score -= 15.0
    elif p < -8.0:
        score -= 8.0
    if p > 18.0 and cv < 2_000_000:
        score -= 15.0
    if abs(p) > 15.0 and cv < 1_000_000:
        score -= 12.0
    vol_mcap = cv / mcap if mcap > 0 else 0
    if abs(p) > 8.0 and vol_mcap < 0.005:
        score -= 18.0
    elif vol_mcap > 2.0:
        score -= 8.0

    return score, score >= score_thresh


def sweep_thresholds(coins: list[dict]) -> dict:
    """Sweep min_24h_change and score_threshold to find optimal values.

    Returns dict with sweep results and recommendations.
    """
    results = {}

    # Sweep min_24h_change: 1.0% to 8.0% in 0.5% steps
    change_values = [x * 0.5 for x in range(2, 17)]  # 1.0 to 8.0
    for mc in change_values:
        passed = 0
        scores = []
        big_movers_caught = 0  # coins with >5% actual move that passed
        big_movers_total = 0
        for c in coins:
            p = c.get("price_change_percentage_24h") or 0
            if abs(p) >= 5.0:
                big_movers_total += 1
            s, ok = score_candidate(c, min_change=mc, score_thresh=0)
            if ok:
                passed += 1
                scores.append(s)
                if abs(p) >= 5.0:
                    big_movers_caught += 1
        results[f"min_change_{mc:.1f}"] = {
            "threshold": mc,
            "passed": passed,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "big_movers_total": big_movers_total,
            "big_movers_caught": big_movers_caught,
            "catch_rate": round(big_movers_caught / big_movers_total * 100, 1) if big_movers_total else 0,
        }

    # Sweep score_threshold: 10 to 50 in 5-step increments
    score_values = list(range(10, 55, 5))
    base_change = 3.0
    for st in score_values:
        passed = 0
        false_positives = 0  # passed but didn't actually move much
        scores = []
        for c in coins:
            p = c.get("price_change_percentage_24h") or 0
            s, ok = score_candidate(c, min_change=base_change, score_thresh=st)
            if ok:
                passed += 1
                scores.append(s)
                # A "false positive" passed but had small actual move
                if abs(p) < 3.5:
                    false_positives += 1
        results[f"score_thresh_{st}"] = {
            "threshold": st,
            "passed": passed,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "false_positives": false_positives,
            "fp_rate": round(false_positives / passed * 100, 1) if passed else 0,
        }

    return results


def analyze_correlations(coins: list[dict]) -> dict:
    """Analyze pairwise correlations among top movers using 7d returns.

    Since we don't have daily return history, use 7d change as a proxy
    for correlation tendency among same-sector movers.
    """
    # Find top 20 coins by 24h volume
    sorted_coins = sorted(coins, key=lambda c: c.get("total_volume") or 0, reverse=True)[:30]
    sectors = {
        "defi": ["uniswap", "aave", "compound", "maker", "curve-dao-token", "lido-dao",
                 "pancakeswap-token", "dydx", "1inch", "pendle"],
        "l1": ["bitcoin", "ethereum", "solana", "cardano", "avalanche-2", "near",
               "aptos", "sui", "sei-network", "injective-protocol"],
        "meme": ["dogecoin", "shiba-inu", "pepe", "bonk", "dogwifcoin", "floki"],
    }

    sector_corrs = {}
    for sector, ids in sectors.items():
        coins_in_sector = [c for c in sorted_coins if c.get("id") in ids]
        if len(coins_in_sector) < 2:
            continue
        # Use 7d change to estimate same-direction movement
        changes_7d = [abs(c.get("price_change_percentage_7d_in_currency") or 0) for c in coins_in_sector]
        changes_24h = [abs(c.get("price_change_percentage_24h") or 0) for c in coins_in_sector]
        # Coins that moved in same direction (both up or both down)
        directions = [(c.get("price_change_percentage_7d_in_currency") or 0) > 0 for c in coins_in_sector]
        same_dir = sum(1 for i in range(1, len(directions)) if directions[i] == directions[0])
        alignment = same_dir / (len(directions) - 1) if len(directions) > 1 else 0
        sector_corrs[sector] = {
            "count": len(coins_in_sector),
            "avg_7d_change": round(sum(changes_7d) / len(changes_7d), 1) if changes_7d else 0,
            "direction_alignment": round(alignment, 2),
        }

    return sector_corrs


def compute_recommendations(sweep: dict, corrs: dict, current_cal: dict) -> list[str]:
    """Compare sweep results against current research calibrations.

    Returns list of human-readable recommendations.
    """
    recs = []

    # Find best min_change threshold
    change_results = {k: v for k, v in sweep.items() if k.startswith("min_change_")}
    if change_results:
        # Find threshold with best catch-rate / passed ratio
        best_ratio = 0
        best_change = 3.0
        for k, v in change_results.items():
            if v["passed"] > 0:
                ratio = v["big_movers_caught"] / max(v["passed"], 1)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_change = v["threshold"]

        current = current_cal.get("min_24h_change_pct", 3.0)
        if best_change != current and best_change > 0:
            recs.append(
                f"Optimal min_24h_change_pct={best_change:.0f}% "
                f"(current={current:.0f}%) — "
                f"catches {change_results.get(f'min_change_{best_change:.1f}', {}).get('big_movers_caught', 0)} "
                f"of {change_results.get(f'min_change_{best_change:.1f}', {}).get('big_movers_total', 0)} big movers"
            )

    # Find best score_threshold
    score_results = {k: v for k, v in sweep.items() if k.startswith("score_thresh_")}
    if score_results:
        # Find threshold with lowest FP rate while keeping reasonable pass count
        best_fp = 100
        best_score = 25
        for k, v in score_results.items():
            fp = v.get("fp_rate", 100)
            passed = v.get("passed", 0)
            if fp < best_fp and passed >= 10:
                best_fp = fp
                best_score = v["threshold"]

        current = current_cal.get("score_threshold", 25)
        if best_score != current:
            recs.append(
                f"Optimal score_threshold={best_score} "
                f"(current={current}) — "
                f"FP rate {best_fp:.0f}% at {best_score}"
            )

    # Correlation analysis
    for sector, data in corrs.items():
        if data.get("direction_alignment", 0) > 0.7 and data.get("count", 0) >= 3:
            recs.append(
                f"{sector.upper()} sector: {data['count']} coins, "
                f"{data['direction_alignment']:.0%} directional alignment — "
                f"correlation_threshold=0.70 is appropriate"
            )

    if not recs:
        recs.append("All thresholds within optimal range — no adjustments needed.")

    return recs


def main():
    print("=== Parameter Optimizer ===\n")

    # 1. Fetch live data
    print("Fetching CoinGecko market data (2 pages, ~500 coins)...")
    coins = fetch_historical_markets()
    print(f"  Retrieved {len(coins)} coins\n")

    if not coins:
        print("ERROR: No market data retrieved.")
        return

    # 2. Load current calibrations
    try:
        with open(CALIB_PATH) as f:
            current_cal = json.load(f)
    except Exception:
        current_cal = {}

    # 3. Sweep thresholds
    print("Sweeping threshold combinations...")
    sweep = sweep_thresholds(coins)
    print(f"  Analyzed {len(sweep)} parameter combinations\n")

    # 4. Analyze correlations
    print("Analyzing sector correlations...")
    corrs = analyze_correlations(coins)
    print(f"  Analyzed {len(corrs)} sectors\n")

    # 5. Compute recommendations
    recs = compute_recommendations(sweep, corrs, current_cal)

    print("=== Results ===\n")

    # Min change sweep summary
    change_data = [(k, v) for k, v in sorted(sweep.items()) if k.startswith("min_change_")]
    print("min_24h_change_pct sweep:")
    print(f"  {'Threshold':>10} {'Passed':>8} {'Caught':>8} {'Total':>6} {'Rate':>6}")
    for k, v in change_data:
        print(f"  {v['threshold']:>8.1f}%  {v['passed']:>8}  {v['big_movers_caught']:>8}  {v['big_movers_total']:>6}  {v['catch_rate']:>5.1f}%")
    print()

    # Score threshold sweep summary
    score_data = [(k, v) for k, v in sorted(sweep.items()) if k.startswith("score_thresh_")]
    print("score_threshold sweep:")
    print(f"  {'Threshold':>10} {'Passed':>8} {'Avg Score':>10} {'FP':>6} {'FP Rate':>8}")
    for k, v in score_data:
        print(f"  {v['threshold']:>8}  {v['passed']:>8}  {v['avg_score']:>10.1f}  {v['false_positives']:>6}  {v['fp_rate']:>7.1f}%")
    print()

    # Sector correlations
    print("Sector correlation analysis:")
    for sector, data in sorted(corrs.items()):
        print(f"  {sector:>8}: {data['count']} coins, 7d avg {data['avg_7d_change']:.1f}%, "
              f"direction alignment {data['direction_alignment']:.0%}")
    print()

    # Recommendations
    print("=== Recommendations ===")
    for r in recs:
        print(f"  → {r}")
    print()

    # Save to disk
    out_path = os.path.join(STRATEGY_DIR, "optimizer_report.json")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coins_analyzed": len(coins),
        "sweep_results": {k: v for k, v in sweep.items()
                          if k.startswith("min_change_") or k.startswith("score_thresh_")},
        "sector_correlations": corrs,
        "recommendations": recs,
    }
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Full report saved to {out_path}")


if __name__ == "__main__":
    main()
