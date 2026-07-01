#!/usr/bin/env python3
"""Strategy dashboard — unified view of all TOK strategy state.

Reads from: params.json, research-calibrations.json, optimizer_report.json,
portfolio.json, ledger.json, journal.db.

Outputs a single consolidated report for the orchestrator or manual runs.

Usage:
    python3 strategy/dashboard.py
    python3 strategy/dashboard.py --compact   # one-liner per section
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY_DIR = os.path.join(SKILL_DIR, "strategy")
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(REPORTS_DIR, "paper_trading")


def _r(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _db(query):
    db_path = os.path.join(STRATEGY_DIR, "journal.db")
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def section_panel(params: dict, cal: dict) -> list[str]:
    """Current strategy parameters vs research calibrations."""
    lines = ["## Strategy Configuration"]
    scr = params.get("screening", {})
    risk = params.get("risk", {})
    dyn = params.get("dynamic_risk", {})

    lines.append(f"- Screening: min_mcap=${scr.get('min_mcap', 0):,}  "
                 f"min_change={scr.get('min_24h_change_pct', 0)}%  "
                 f"score_threshold={scr.get('score_threshold', 0)}")
    lines.append(f"- Risk: {risk.get('risk_per_trade_pct', 0)}% per trade  "
                 f"stop={risk.get('stop_loss_pct', 0)}%  "
                 f"target={risk.get('target_pct', 0)}%")
    if dyn.get("enabled"):
        lines.append(f"- Dynamic risk: ✅  target {dyn.get('min_target_pct', 5)}-{dyn.get('max_target_pct', 15)}%  "
                     f"stop {dyn.get('min_stop_pct', 2)}-{dyn.get('max_stop_pct', 8)}%")
    lines.append(f"- Portfolio: concurrency_max={cal.get('portfolio', {}).get('concurrency_max', 3)}  "
                 f"drawdown_limit={cal.get('portfolio', {}).get('drawdown_limit_pct', 10)}%  "
                 f"correlation_threshold={cal.get('portfolio', {}).get('correlation_threshold', 0.7)}")
    lines.append(f"- Regime: high_vol={cal.get('regime', {}).get('high_vol_threshold', 0.03)}  "
                 f"low_vol={cal.get('regime', {}).get('low_vol_threshold', 0.015)}")
    lines.append(f"- Liquidity: ideal_spread={cal.get('liquidity', {}).get('spread_ideal_bps', 3)}bps  "
                 f"min_depth=${cal.get('liquidity', {}).get('depth_confidence_min_usd', 50000):,}")
    lines.append(f"- Derivatives: funding_extreme={cal.get('derivatives', {}).get('funding_extreme_positive', 0.001)}")
    return lines


def section_portfolio() -> list[str]:
    """Paper trading portfolio state."""
    pf = _r(os.path.join(PAPER_DIR, "portfolio.json"), {})
    lines = ["## Portfolio"]
    cash = pf.get("cash", 0)
    starting = pf.get("starting_capital", 10000)
    positions = pf.get("positions", {})
    equity = cash + sum(
        p.get("current_price", 0) * p.get("quantity", 0) for p in positions.values()
    )
    drawdown = (starting - equity) / starting * 100 if starting > 0 else 0
    lines.append(f"- Equity: ${equity:,.2f}  Cash: ${cash:,.2f}  "
                 f"P&L: {equity - starting:+,.2f} ({drawdown:+.2f}%)")
    lines.append(f"- Open positions: {len(positions)}")
    for sym, p in sorted(positions.items()):
        pnl = p.get("pnl_pct", 0)
        trail = p.get("trailing_stop")
        trail_s = f" trail=${trail}" if trail else ""
        lines.append(f"  {'🟢' if pnl > 0 else '🔴'} {sym}: {pnl:+.2f}%  "
                     f"entry=${p.get('entry_price', '?')}  curr=${p.get('current_price', '?')}{trail_s}")
    return lines


def section_performance() -> list[str]:
    """Trailing performance from journal."""
    rows = _db(
        "SELECT win_rate, profit_factor, avg_pnl_pct, total_signals, closed_signals, "
        "win_count, loss_count, computed_at FROM performance ORDER BY id DESC LIMIT 1"
    )
    lines = ["## Performance"]
    if rows:
        r = rows[0]
        wr = f"{r[0]:.1%}" if r[0] else "N/A"
        pf = f"{r[1]:.2f}" if r[1] else "N/A"
        ap = f"{r[2]:+.2f}%" if r[2] else "N/A"
        lines.append(f"- Win rate: {wr}  Profit factor: {pf}  Avg PnL: {ap}")
        lines.append(f"- {r[5]}W / {r[6]}L  ({r[4]} closed of {r[3]} total)")
        lines.append(f"- Last updated: {r[7]}")
    else:
        lines.append("- No performance data yet.")
    return lines


def section_optimizer() -> list[str]:
    """Latest parameter optimizer recommendations."""
    opt = _r(os.path.join(STRATEGY_DIR, "optimizer_report.json"))
    lines = ["## Parameter Optimizer"]
    if not opt:
        lines.append("- No optimizer report yet. Run `python3 strategy/parameter_optimizer.py`")
        return lines
    lines.append(f"- Analyzed {opt.get('coins_analyzed', 0)} coins on {opt.get('generated_at', '?')[:10]}")
    recs = opt.get("recommendations", [])
    if recs:
        for r in recs:
            lines.append(f"  → {r}")
    return lines


def section_calibration_health() -> list[str]:
    """Calibration health from portfolio engine."""
    try:
        # Direct import from absolute path
        import importlib.util
        _pe_path = os.path.join(SKILL_DIR, "strategy", "portfolio_engine.py")
        spec = importlib.util.spec_from_file_location("portfolio_engine", _pe_path)
        pe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pe)
        lines, score = pe.calibration_health()
        return lines
    except Exception as e:
        return ["## Calibration Health", f"- Error: {e}"]


def section_daily_schedule() -> list[str]:
    """Today's upcoming cron jobs."""
    cron_path = os.path.expanduser("~/.hermes/cron/jobs.json")
    jobs = _r(cron_path, {"jobs": []})
    lines = ["## Today's Schedule"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trading_jobs = [j for j in jobs.get("jobs", []) if "trading" in j.get("name", "").lower()]
    if not trading_jobs:
        trading_jobs = jobs.get("jobs", [])[:5]
    for j in sorted(trading_jobs, key=lambda x: x.get("next_run_at", "")):
        nr = j.get("next_run_at", "?")
        nm = j.get("name", "?")
        lines.append(f"- {nr[:16]}  {nm}")
    return lines


def main(compact=False):
    sections = [
        section_panel(
            _r(os.path.join(STRATEGY_DIR, "params.json"), {}),
            _r(os.path.join(STRATEGY_DIR, "research-calibrations.json"), {}),
        ),
        section_portfolio(),
        section_performance(),
        section_optimizer(),
        section_calibration_health(),
        section_daily_schedule(),
    ]

    output = []
    for s in sections:
        if compact:
            # One-line summary per section
            header = s[0] if s else "?"
            first_line = s[1] if len(s) > 1 else ""
            output.append(f"{header}: {first_line}")
        else:
            output.extend(s)
            output.append("")

    print("\n".join(output))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", action="store_true", help="One-liner per section")
    args = ap.parse_args()
    main(compact=args.compact)
