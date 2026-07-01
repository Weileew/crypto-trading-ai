#!/usr/bin/env python3
"""Smart cron schedule manager for the TOK trading system.

Central registry for all cron jobs, their CG call costs, and schedule
collision detection. Provides analysis, optimization suggestions, and
a machine-readable schedule view.

Usage:
    python3 strategy/cron_manager.py                    # full report
    python3 strategy/cron_manager.py --check-collisions # collision scan
    python3 strategy/cron_manager.py --budget           # CG budget report
    python3 strategy/cron_manager.py --schedule         # schedule timeline
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")

JOB_REGISTRY: List[Dict] = [
    {
        "name": "orchestrator-nightly",
        "job_id": "58e8183595d8",
        "schedule_cron": "0 4 * * *",
        "schedule_label": "04:00 daily",
        "cg_calls_per_run": 8,
        "runtime_s": 120,
        "no_agent": False,
        "description": "Full pipeline: news → briefing → journal → validate → adapt",
    },
    # REMOVED 2026-06-29 — tok-daily-diagnostic was a daily system health check
    # (smoke test + performance check) that never successfully delivered (message
    # too long for Telegram). ~80% overlap with orchestrator-nightly digest.
    # See cron-schedule.md for removed jobs list.
    {
        "name": "daily-crypto-trading-briefing-morning",
        "job_id": "f0fc8b054fc8",
        "schedule_cron": "0 8 * * *",
        "schedule_label": "08:00 daily",
        "cg_calls_per_run": 6,
        "runtime_s": 110,
        "no_agent": False,
        "description": "Morning briefing + paper_executor auto-open",
    },
    {
        "name": "daily-crypto-trading-briefing-afternoon",
        "job_id": "ccc18cada9a7",
        "schedule_cron": "0 14 * * *",
        "schedule_label": "14:00 daily",
        "cg_calls_per_run": 6,
        "runtime_s": 110,
        "no_agent": False,
        "description": "Afternoon briefing + paper_executor auto-open",
    },
    {
        "name": "paper-trading-m2m",
        "job_id": "91d6c930e1f3",
        "schedule_cron": "every 15m",
        "schedule_label": "every 15 min",
        "cg_calls_per_run": 1,
        "runtime_s": 3,
        "no_agent": True,
        "offset_minutes": 20,  # fires at ~XX:20/35/50/05 (offset baked from creation)
        "description": "Mark-to-market price update + trailing stop check",
    },
    {
        "name": "research-playbook-enrichment",
        "job_id": "49dfd654806a",
        "schedule_cron": "30 5 * * *",
        "schedule_label": "05:30 daily",
        "cg_calls_per_run": 0,
        "runtime_s": 120,
        "no_agent": False,
        "description": "Collect papers from OpenAlex + regenerate digest",
    },
    {
        "name": "parameter-optimizer-weekly",
        "job_id": "af1b44ab18eb",
        "schedule_cron": "0 6 * * 1",
        "schedule_label": "Mon 06:00",
        "cg_calls_per_run": 2,
        "runtime_s": 60,
        "no_agent": False,
        "description": "Sweep 500-coin CG data, recommend thresholds",
    },
    # REMOVED 2026-06-29 — advisor-continuous-improvement was a passive read-only
    # analyzer (improve.py) that echoed signal performance data without applying
    # any changes. Superseded by orchestrator-nightly (calibration_health +
    # suggest_adjustments) and parameter-optimizer-weekly.
    {
        "name": "auto-push-github",
        "job_id": "df36310d255c",
        "schedule_cron": "every 60m",
        "schedule_label": "every 60 min",
        "cg_calls_per_run": 0,
        "runtime_s": 5,
        "no_agent": True,
        "description": "Auto-push local changes to GitHub",
    },
    {
        "name": "crypto-backup-refresh",
        "job_id": "cd08dca87913",
        "schedule_cron": "0 */6 * * *",
        "schedule_label": "every 6 hours",
        "cg_calls_per_run": 0,
        "runtime_s": 10,
        "no_agent": True,
        "description": "Sync skills to crypto-trading-ai repo",
    },
    {
        "name": "discovery-engine-weekly",
        "job_id": "e2d7034a03f8",
        "schedule_cron": "0 10 * * 0",
        "schedule_label": "Sun 10:00",
        "cg_calls_per_run": 0,
        "runtime_s": 120,
        "no_agent": False,
        "description": "Self-architect discovery scan",
    },
    {
        "name": "cloud-backup-hermes",
        "job_id": "b973000ea6fc",
        "schedule_cron": "0 3 * * *",
        "schedule_label": "03:00 daily",
        "cg_calls_per_run": 0,
        "runtime_s": 120,
        "no_agent": True,
        "description": "Hermes config + data backup",
    },
    {
        "name": "weekly-performance-review",
        "job_id": "b366c4096b1b",
        "schedule_cron": "0 20 * * 0",
        "schedule_label": "Sun 20:00 weekly",
        "cg_calls_per_run": 0,
        "runtime_s": 90,
        "no_agent": False,
        "description": "Week-over-week trend: WR, best/worst, drawdown, F&G, optimizer",
    },
]

# CG free tier limits
CG_FREE_TIER = {"req_per_min": 10, "req_per_day": 14400}
CG_SAFETY_THRESHOLD = 500  # daily warning threshold
CG_MIN_SPACING_S = 6       # minimum seconds between CG calls


# ── Schedule parsers ──────────────────────────────────────────────

def parse_cron_minute(cron_expr: str) -> int | None:
    """Extract the minute field from a cron expression.
    
    Returns None for non-fixed-minute schedules like 'every 15m'.
    """
    expr = cron_expr.strip()
    if expr.startswith("every"):
        return None  # relative schedule, no fixed minute
    parts = expr.split()
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def parse_cron_hour(cron_expr: str) -> int | None:
    """Extract the hour field from a cron expression."""
    expr = cron_expr.strip()
    if expr.startswith("every"):
        return None
    parts = expr.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def get_fire_times(job: Dict) -> List[int]:
    """Return list of minute-of-day (0-1439) when this job fires.
    
    For daily fixed-time jobs: returns one minute.
    For weekly jobs: returns one minute (only on that day).
    For 'every N' jobs: returns multiple minutes based on offset.
    """
    cron = job["schedule_cron"]
    offset = job.get("offset_minutes", 0)
    if cron.startswith("every"):
        try:
            interval = int(cron.split()[1].replace("m", "").replace("h", ""))
            if "h" in cron.split()[1]:
                interval *= 60
            return [t % 1440 for t in range(offset, 1440 + offset, interval)]
        except (IndexError, ValueError):
            return []
    
    minute = parse_cron_minute(cron)
    hour = parse_cron_hour(cron)
    if minute is None or hour is None:
        return []
    return [hour * 60 + minute]


def get_cg_calls_per_day(job: Dict) -> int:
    """Compute total CG calls this job makes per day."""
    calls_per_run = job["cg_calls_per_run"]
    if calls_per_run == 0:
        return 0
    
    cron = job["schedule_cron"]
    if cron.startswith("every"):
        try:
            interval_min = int(cron.split()[1].replace("m", "").replace("h", ""))
            if "h" in cron.split()[1]:
                interval_min *= 60
            runs_per_day = max(1, 1440 // interval_min)
            return runs_per_day * calls_per_run
        except (IndexError, ValueError):
            return 0
    
    # Daily job
    if "daily" in job.get("schedule_label", "").lower():
        return calls_per_run
    
    # Weekly job -> daily avg
    if any(d in job.get("schedule_label", "").lower() for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "weekly"]):
        return round(calls_per_run / 7, 1)
    
    return calls_per_run


# ── Collision detection ──────────────────────────────────────────

def detect_collisions(jobs: List[Dict] = None) -> List[Dict]:
    """Find jobs that fire within the same minute and share CG calls.
    
    Returns list of collision dicts: {minute, jobs, total_cg_calls}.
    Only flags minutes where total CG calls > CG_FREE_TIER['req_per_min'] / 2
    (at half the limit, flag as caution).
    """
    if jobs is None:
        jobs = JOB_REGISTRY
    
    minute_map: Dict[int, List[Dict]] = {}
    for job in jobs:
        for minute in get_fire_times(job):
            if minute not in minute_map:
                minute_map[minute] = []
            minute_map[minute].append(job)
    
    collisions = []
    for minute in sorted(minute_map):
        jobs_here = minute_map[minute]
        cg_here = sum(j["cg_calls_per_run"] for j in jobs_here)
        if len(jobs_here) > 1 and cg_here > 0:
            collision = {
                "minute": minute,
                "time_label": f"{minute // 60:02d}:{minute % 60:02d}",
                "jobs": [j["name"] for j in jobs_here],
                "total_cg_calls": cg_here,
                "severity": "HIGH" if cg_here >= CG_FREE_TIER["req_per_min"] else 
                           "MEDIUM" if cg_here >= CG_FREE_TIER["req_per_min"] / 2 else "LOW",
            }
            collisions.append(collision)
    
    return collisions


def detect_proximity(jobs: List[Dict] = None) -> List[Dict]:
    """Find jobs that fire within N minutes of each other (same CG pressure window).
    
    Flags pairs of jobs within 5 minutes where both have CG calls.
    """
    if jobs is None:
        jobs = JOB_REGISTRY
    
    cg_jobs = [j for j in jobs if j["cg_calls_per_run"] > 0]
    proximity = []
    
    for i, a in enumerate(cg_jobs):
        a_times = get_fire_times(a)
        for b in cg_jobs[i + 1:]:
            b_times = get_fire_times(b)
            for at in a_times:
                for bt in b_times:
                    gap = abs(at - bt)
                    if 0 < gap <= 5:  # same or adjacent minute
                        proximity.append({
                            "job_a": a["name"],
                            "job_b": b["name"],
                            "gap_min": gap,
                            "a_time": f"{at // 60:02d}:{at % 60:02d}",
                            "b_time": f"{bt // 60:02d}:{bt % 60:02d}",
                            "total_cg": a["cg_calls_per_run"] + b["cg_calls_per_run"],
                        })
    
    return proximity


# ── Budget analysis ───────────────────────────────────────────────

def analyze_budget(jobs: List[Dict] = None) -> Dict:
    """Compute daily CG call budget across all jobs."""
    if jobs is None:
        jobs = JOB_REGISTRY
    
    total_daily = 0
    breakdown = []
    for job in jobs:
        daily = get_cg_calls_per_day(job)
        if daily > 0:
            breakdown.append({"name": job["name"], "calls_per_day": daily})
            total_daily += daily
    
    peak_cg_per_min = 0
    minute_map: Dict[int, int] = {}
    for job in jobs:
        for minute in get_fire_times(job):
            minute_map[minute] = minute_map.get(minute, 0) + job["cg_calls_per_run"]
            peak_cg_per_min = max(peak_cg_per_min, minute_map[minute])
    
    return {
        "total_daily_cg_calls": total_daily,
        "cg_free_tier_limit_per_day": CG_FREE_TIER["req_per_day"],
        "usage_pct": round(total_daily / CG_FREE_TIER["req_per_day"] * 100, 2),
        "safety_threshold": CG_SAFETY_THRESHOLD,
        "peak_cg_per_minute": peak_cg_per_min,
        "cg_limit_per_minute": CG_FREE_TIER["req_per_min"],
        "peak_usage_pct_of_minute": round(peak_cg_per_min / CG_FREE_TIER["req_per_min"] * 100, 1),
        "breakdown": sorted(breakdown, key=lambda x: -x["calls_per_day"]),
    }


def read_cg_counter() -> Optional[Dict]:
    """Read the daily CG call counter if it exists."""
    path = os.path.join(REPORTS_DIR, "cg_call_count.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ── TOK Performance Awareness ─────────────────────────────────────
# Performance thresholds used to classify trading health and adjust schedules.

PERF_THRESHOLDS = {
    "win_rate_good": 0.40,        # ≥40% = healthy
    "win_rate_hot": 0.55,         # ≥55% = hot streak, loosen schedule
    "win_rate_cold": 0.25,        # <25% = cold streak, tighten
    "profit_factor_good": 1.0,    # ≥1.0 = positive expectancy
    "profit_factor_hot": 1.5,     # ≥1.5 = strong positive
    "max_consecutive_losses": 5,  # loss streak threshold
    "drawdown_warn_pct": -5.0,    # warning threshold
    "drawdown_critical_pct": -10.0,  # critical threshold
    "min_closed_signals": 5,      # minimum signals for meaningful analysis
}


def read_tok_performance() -> Dict:
    """Read TOK trading performance from all available sources.

    Gathers signal validation stats, strategy journal metrics,
    portfolio drawdown, and strategy parameters. Returns a dict
    with all available data, gracefully handling missing sources.
    """
    result = {"state": "unknown", "signals": {}, "journal": {},
              "portfolio": {}, "params": {}, "streak": 0}

    # 1. Signal performance
    try:
        sp_path = os.path.join(REPORTS_DIR, "signal_performance.json")
        with open(sp_path) as f:
            sp = json.load(f)
        result["signals"] = {
            "validated": sp.get("summary", {}).get("validated_count", 0),
            "pending": sp.get("summary", {}).get("pending_validation_count", 0),
            "win_rate": sp.get("summary", {}).get("win_rate"),
        }
    except Exception:
        pass

    # 2. Strategy journal (SQLite)
    try:
        import sqlite3
        j_path = os.path.join(SKILL_DIR, "strategy", "journal.db")
        if os.path.exists(j_path):
            db = sqlite3.connect(j_path)
            db.row_factory = sqlite3.Row
            perf = db.execute(
                "SELECT * FROM performance ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if perf:
                result["journal"] = {
                    "total_signals": perf["total_signals"],
                    "closed_signals": perf["closed_signals"],
                    "win_count": perf["win_count"],
                    "loss_count": perf["loss_count"],
                    "win_rate": perf["win_rate"],
                    "avg_pnl_pct": perf["avg_pnl_pct"],
                    "avg_win_pct": perf["avg_win_pct"],
                    "avg_loss_pct": perf["avg_loss_pct"],
                    "profit_factor": perf["profit_factor"],
                    "current_streak": perf["current_streak"],
                }
                result["streak"] = perf["current_streak"] or 0
            db.close()
    except Exception:
        pass

    # 3. Portfolio / drawdown
    try:
        pf_path = os.path.join(REPORTS_DIR, "paper_trading", "portfolio.json")
        with open(pf_path) as f:
            pf = json.load(f)
        capital = 10000.0
        equity = pf.get("cash", capital)
        result["portfolio"] = {
            "equity": equity,
            "cash": pf.get("cash", 0),
            "open_positions": len(pf.get("positions", {})),
            "drawdown_pct": round(((equity - capital) / capital) * 100, 2),
        }
    except Exception:
        pass

    # 4. Strategy params
    try:
        pa_path = os.path.join(SKILL_DIR, "strategy", "params.json")
        with open(pa_path) as f:
            result["params"] = json.load(f)
    except Exception:
        pass

    return result


def classify_performance(perf: Dict) -> str:
    """Classify TOK trading health into a performance state.

    Returns one of: 'hot', 'normal', 'cold', 'critical', 'insufficient_data'.
    """
    j = perf.get("journal", {})
    closed = j.get("closed_signals", 0) or 0
    if closed < PERF_THRESHOLDS["min_closed_signals"]:
        return "insufficient_data"

    win_rate = j.get("win_rate", 0) or 0
    profit_factor = j.get("profit_factor", 0) or 0
    streak = perf.get("streak", 0) or 0
    dd = perf.get("portfolio", {}).get("drawdown_pct", 0) or 0

    # Check critical first (overrides everything)
    if dd <= PERF_THRESHOLDS["drawdown_critical_pct"]:
        return "critical"
    if streak <= -PERF_THRESHOLDS["max_consecutive_losses"] and win_rate < PERF_THRESHOLDS["win_rate_good"]:
        return "cold"
    if win_rate < PERF_THRESHOLDS["win_rate_cold"] and profit_factor < PERF_THRESHOLDS["profit_factor_good"]:
        return "cold"

    # Check hot
    if win_rate >= PERF_THRESHOLDS["win_rate_hot"] and profit_factor >= PERF_THRESHOLDS["profit_factor_hot"]:
        return "hot"
    if profit_factor >= PERF_THRESHOLDS["profit_factor_hot"] * 1.5:
        return "hot"

    # Check warm / warning
    if dd <= PERF_THRESHOLDS["drawdown_warn_pct"]:
        return "cold"  # moderate drawdown is cold, not critical

    return "normal"


def schedule_suggestions_for_performance(perf: Dict, state: str) -> List[str]:
    """Generate schedule change suggestions based on TOK performance state.

    Maps performance state to concrete cron schedule adjustments.
    The M2M frequency is the primary lever — faster when losing
    (tighter trailing stops), slower when winning (fewer API calls).
    """
    suggestions = []
    j = perf.get("journal", {})
    pf_data = perf.get("portfolio", {})
    dd = pf_data.get("drawdown_pct", 0) or 0
    streak = perf.get("streak", 0) or 0
    win_rate = j.get("win_rate", 0) or 0
    pf = j.get("profit_factor", 0) or 0
    closed = j.get("closed_signals", 0) or 0

    # ── State-specific suggestions ──────────────────────────────
    if state == "critical":
        suggestions.append(
            f"🔴 CRITICAL: Drawdown {dd:.1f}% exceeds {PERF_THRESHOLDS['drawdown_critical_pct']}% threshold. "
            f"Consider PAUSING briefing + orchestrator crons until recovery."
        )
        suggestions.append(
            f"🔄 SUGGEST: Increase M2M to every 15m for tighter trailing stop protection "
            f"during drawdown."
        )
        suggestions.append(
            f"🔄 SUGGEST: Pause morning/afternoon briefings — capital preservation mode."
        )

    elif state == "cold":
        streak_msg = f" (streak: {streak})" if streak < 0 else ""
        suggestions.append(
            f"🔶 COLD: Win rate {win_rate*100:.0f}%, profit factor {pf:.2f}{streak_msg}. "
            f"Maintaining signal flow for strategy optimization."
        )
        suggestions.append(
            f"✅ M2M already at every 15m (tighter trailing stops applied)."
        )
        suggestions.append(
            f"📊 Both briefings active — paper trading mode: more signals = more validation "
            f"data for faster strategy tuning."
        )

    elif state == "hot":
        suggestions.append(
            f"🟢 HOT: Win rate {win_rate*100:.0f}%, profit factor {pf:.2f}. "
            f"Loosening schedule to capture momentum."
        )
        suggestions.append(
            f"🔄 SUGGEST: M2M every 30m is fine — trailing stops less critical when winning. "
            f"Keep current."
        )
        suggestions.append(
            f"🔄 SUGGEST: Both briefings active — consider adding weekend briefing "
            f"if weekend volatility supports it."
        )

    elif state == "normal":
        suggestions.append(
            f"✅ NORMAL: Win rate {win_rate*100:.0f}%, profit factor {pf:.2f}. "
            f"Standard schedule is appropriate."
        )
        suggestions.append(
            f"🔄 SUGGEST: M2M every 30m is appropriate. No schedule changes needed."
        )

    else:  # insufficient_data
        suggestions.append(
            f"📊 INSUFFICIENT DATA: Only {closed} closed signals (< {PERF_THRESHOLDS['min_closed_signals']}). "
            f"Using default schedule until more data accumulates."
        )
        suggestions.append(
            f"🔄 SUGGEST: Keep M2M at every 30m. Both briefings active for data gathering."
        )

    # ── Cross-cutting: drawdown warning ─────────────────────────
    if dd <= PERF_THRESHOLDS["drawdown_warn_pct"] and state not in ("critical",):
        suggestions.append(
            f"📉 Drawdown {dd:.1f}% approaching critical ({PERF_THRESHOLDS['drawdown_critical_pct']}%). "
            f"Monitor closely."
        )

    # ── Validation backlog ──────────────────────────────────────
    sig = perf.get("signals", {})
    pending = sig.get("pending", 0) or 0
    if pending > 3:
        suggestions.append(
            f"📊 {pending} signals pending validation. Signal validator may need a manual run."
        )

    return suggestions


def performance_report(perf: Dict = None) -> str:
    """Generate a performance-aware schedule health report."""
    if perf is None:
        perf = read_tok_performance()
    state = classify_performance(perf)
    suggestions = schedule_suggestions_for_performance(perf, state)

    lines = ["🎯 TOK Performance State\n"]
    j = perf.get("journal", {})
    pf_data = perf.get("portfolio", {})

    # State badge
    state_icons = {"hot": "🟢 HOT", "normal": "✅ NORMAL", "cold": "🔶 COLD",
                   "critical": "🔴 CRITICAL", "insufficient_data": "📊 INSUFFICIENT"}
    lines.append(f"  State: {state_icons.get(state, '⚪ UNKNOWN')}\n")

    # Metrics
    if j.get("closed_signals", 0) or 0 > 0:
        lines.append(f"  Win rate:      {j.get('win_rate', 0)*100:.1f}% "
                     f"({j.get('win_count', 0)}W / {j.get('loss_count', 0)}L)")
        lines.append(f"  Profit factor: {j.get('profit_factor', 0):.2f}")
        lines.append(f"  Avg PnL:       {j.get('avg_pnl_pct', 0):+.2f}%")
        lines.append(f"  Streak:        {perf.get('streak', 0):+d}")

    if pf_data.get("drawdown_pct", 0) or 0 != 0:
        dd = pf_data["drawdown_pct"]
        dd_icon = "🟢" if dd > -3 else "🟡" if dd > -5 else "🔶" if dd > -10 else "🔴"
        lines.append(f"  Drawdown:      {dd_icon} {dd:.1f}%")

    lines.append(f"\n  Schedule Adjustments:")
    for s in suggestions:
        lines.append(f"    {s}")

    return "\n".join(lines)


# ── Optimization suggestions ──────────────────────────────────────

def suggest_optimizations(jobs: List[Dict] = None) -> List[str]:
    """Generate actionable schedule optimization suggestions."""
    if jobs is None:
        jobs = JOB_REGISTRY
    
    suggestions = []
    budget = analyze_budget(jobs)
    
    # Check collisions (only CG-carrying jobs matter)
    collisions = detect_collisions(jobs)
    for c in collisions:
        if c["severity"] == "HIGH":
            suggestions.append(
                f"🔴 HIGH: {c['time_label']} — {c['total_cg_calls']} CG calls/min "
                f"from {', '.join(c['jobs'])}. Move at least one job."
            )
    
    # Check proximity among CG jobs
    proximity = detect_proximity(jobs)
    for p in proximity[:5]:
        suggestions.append(
            f"⚡ Close pair: {p['job_a']} @ {p['a_time']} and {p['job_b']} @ {p['b_time']} "
            f"— {p['gap_min']}min gap, {p['total_cg']} combined CG calls."
        )
    
    # ── Auto-optimization: generate shift recommendations ──────
    minute_map: Dict[int, List[Dict]] = {}
    for job in jobs:
        for minute in get_fire_times(job):
            if minute not in minute_map:
                minute_map[minute] = []
            minute_map[minute].append(job)
    
    for minute in sorted(minute_map):
        jobs_here = minute_map[minute]
        cg_here = sum(j["cg_calls_per_run"] for j in jobs_here if j["cg_calls_per_run"] > 0)
        if cg_here >= CG_FREE_TIER["req_per_min"] * 0.7:
            # Find the most movable job
            cg_jobs = sorted(
                [j for j in jobs_here if j["cg_calls_per_run"] > 0],
                key=lambda j: -j["cg_calls_per_run"],
            )
            for j in cg_jobs[:2]:
                cron = j["schedule_cron"]
                if not cron.startswith("every"):
                    suggestions.append(
                        f"🔄 SUGGEST: Move {j['name']} from {cron} "
                        f"to avoid {cg_here}/{CG_FREE_TIER['req_per_min']} CG calls/min "
                        f"at {minute // 60:02d}:{minute % 60:02d}."
                    )
    
    # Check total budget
    if budget["total_daily_cg_calls"] > CG_SAFETY_THRESHOLD * 0.9:
        suggestions.append(
            f"📊 Daily budget: {budget['total_daily_cg_calls']} calls "
            f"({budget['usage_pct']}% of free tier) — approaching safety threshold."
        )
    
    # M2M summary
    m2m = next((j for j in jobs if j["name"] == "paper-trading-m2m"), None)
    if m2m:
        daily = get_cg_calls_per_day(m2m)
        pct = round(daily / max(budget["total_daily_cg_calls"], 1) * 100, 1)
        suggestions.append(
            f"📊 M2M: {daily} CG calls/day ({pct}% of total). "
            f"Currently {m2m['schedule_label']}."
        )
    
    if not any(s.startswith("🔴") or s.startswith("⚡") or s.startswith("🔄") for s in suggestions):
        suggestions.insert(0, "✅ No schedule conflicts found. All clear.")
    
    return suggestions


def auto_optimize(jobs: List[Dict] = None) -> List[Dict]:
    """Generate concrete schedule change recommendations.
    
    Returns list of {job_name, job_id, current_schedule, suggested_schedule, reason}.
    """
    if jobs is None:
        jobs = JOB_REGISTRY
    
    changes = []
    
    # Detect minutes with high CG load
    minute_map: Dict[int, List[Dict]] = {}
    for job in jobs:
        for minute in get_fire_times(job):
            if minute not in minute_map:
                minute_map[minute] = []
            minute_map[minute].append(job)
    
    for minute in sorted(minute_map):
        jobs_here = minute_map[minute]
        cg_here = sum(j["cg_calls_per_run"] for j in jobs_here if j["cg_calls_per_run"] > 0)
        if cg_here >= CG_FREE_TIER["req_per_min"] * 0.7:
            cg_jobs = sorted(
                [j for j in jobs_here if j["cg_calls_per_run"] > 0],
                key=lambda j: -j["cg_calls_per_run"],
            )
            for j in cg_jobs:
                cron = j["schedule_cron"]
                if cron.startswith("every"):
                    continue  # don't move relative schedules
                # Parse current hour
                hour = parse_cron_hour(cron)
                if hour is None:
                    continue
                # Suggest moving 1 hour forward or 1 hour back
                for shift in [1, -1, 2, -2]:
                    new_hour = (hour + shift) % 24
                    # Check if new hour is free of collisions
                    new_minute = minute % 60  # same minute
                    conflict = False
                    for other in jobs:
                        if other["name"] == j["name"]:
                            continue
                        for ot in get_fire_times(other):
                            if ot == new_hour * 60 + new_minute:
                                if other["cg_calls_per_run"] > 0:
                                    conflict = True
                                    break
                        if conflict:
                            break
                    if not conflict:
                        new_cron = cron.replace(str(hour), str(new_hour))
                        changes.append({
                            "job_name": j["name"],
                            "job_id": j.get("job_id", "?"),
                            "current_schedule": cron,
                            "suggested_schedule": new_cron,
                            "new_time": f"{new_hour:02d}:{new_minute:02d}",
                            "reason": f"Relieves {cg_here}/{CG_FREE_TIER['req_per_min']} CG calls/min contention at {minute // 60:02d}:{minute % 60:02d}",
                        })
                        break  # one suggestion per job per minute slot
    return changes


# ── Report generators ─────────────────────────────────────────────

def timeline_report(jobs: List[Dict] = None) -> str:
    """Generate a 24h timeline showing all job firings."""
    if jobs is None:
        jobs = JOB_REGISTRY
    
    lines = ["📅 Cron Schedule — 24h Timeline\n"]
    
    for hour in range(24):
        hour_label = f"{hour:02d}:00"
        slot_markers = []
        cg_count = 0
        
        for job in jobs:
            times = get_fire_times(job)
            for t in times:
                if t // 60 == hour:
                    minute = t % 60
                    icon = "💸" if job["cg_calls_per_run"] > 0 else "⚪"
                    cg_count += job["cg_calls_per_run"]
                    slot_markers.append(f"{icon} {job['name']} @ :{minute:02d}")
        
        if slot_markers:
            budget_bar = f" [CG: {cg_count}]" if cg_count > 0 else ""
            lines.append(f"{hour_label}{budget_bar}")
            for m in sorted(slot_markers):
                lines.append(f"  {m}")
    
    return "\n".join(lines)


def budget_report(jobs: List[Dict] = None) -> str:
    """Generate CG budget report."""
    if jobs is None:
        jobs = JOB_REGISTRY
    
    budget = analyze_budget(jobs)
    counter = read_cg_counter()
    
    lines = ["💰 CG Budget Report\n"]
    lines.append(f"Free tier limit:  {CG_FREE_TIER['req_per_day']}/day")
    lines.append(f"Safety threshold: {CG_SAFETY_THRESHOLD}/day")
    lines.append(f"Total scheduled:  {budget['total_daily_cg_calls']}/day ({budget['usage_pct']}%)")
    lines.append(f"Peak per minute:  {budget['peak_cg_per_minute']}/{CG_FREE_TIER['req_per_min']} ({budget['peak_usage_pct_of_minute']}%)")
    
    if counter:
        lines.append(f"\nActual today ({counter['date']}): {counter['count']} CG calls")
    
    lines.append("\nBreakdown by job:")
    for b in budget["breakdown"]:
        bar_len = max(1, int(b["calls_per_day"] / max(budget["breakdown"][0]["calls_per_day"], 1) * 30))
        bar = "█" * bar_len
        lines.append(f"  {bar} {b['name']}: {b['calls_per_day']}/day")
    
    return "\n".join(lines)


def collision_report(jobs: List[Dict] = None) -> str:
    """Generate collision detection report."""
    if jobs is None:
        jobs = JOB_REGISTRY
    
    collisions = detect_collisions(jobs)
    proximity = detect_proximity(jobs)
    suggestions = suggest_optimizations(jobs)
    
    lines = ["🔍 Schedule Collision Scan\n"]
    
    if not collisions:
        lines.append("✅ No same-minute collisions detected.\n")
    else:
        lines.append(f"⚠️ {len(collisions)} collision(s) detected:\n")
        for c in collisions:
            emoji = "🔴" if c["severity"] == "HIGH" else "🟡"
            lines.append(f"  {emoji} {c['time_label']} — {', '.join(c['jobs'])}")
            lines.append(f"     {c['total_cg_calls']} CG calls in same minute "
                        f"({c['total_cg_calls']}/{CG_FREE_TIER['req_per_min']} limit)")
    
    if proximity:
        lines.append(f"\n⚡ {len(proximity)} close-proximity pair(s) (≤5 min gap):")
        for p in proximity[:5]:
            lines.append(f"  • {p['job_a']} @ {p['a_time']} ↔ {p['job_b']} @ {p['b_time']} "
                        f"— {p['gap_min']}min, {p['total_cg']} CG calls")
    
    lines.append("\nSuggestions:")
    for s in suggestions:
        lines.append(f"  {s}")
    
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    
    if "--check-collisions" in args or "-c" in args:
        print(collision_report())
    elif "--budget" in args or "-b" in args:
        print(budget_report())
    elif "--schedule" in args or "-s" in args:
        print(timeline_report())
    elif "--auto-optimize" in args or "-o" in args:
        changes = auto_optimize()
        if changes:
            print("🔄 Auto-Optimize — Recommended Schedule Changes\n")
            for c in changes:
                print(f"  • {c['job_name']}: {c['current_schedule']} → {c['suggested_schedule']}")
                print(f"    ({c['new_time']}) — {c['reason']}")
                print(f"    Command: cronjob update job_id={c['job_id']} schedule='{c['suggested_schedule']}'")
                print()
        else:
            print("✅ No schedule changes needed — all clear.\n")
    elif "--performance" in args or "-p" in args:
        perf = read_tok_performance()
        print(performance_report(perf))
    else:
        # Full report
        print("=" * 60)
        print("  TOK Cron Schedule Manager")
        print("=" * 60)
        print()
        print(budget_report())
        print()
        print(collision_report())
        print()
        
        # Daily CG counter
        counter = read_cg_counter()
        if counter:
            pct = round(counter["count"] / CG_SAFETY_THRESHOLD * 100, 1)
            bar = "█" * max(1, int(pct / 5)) + "░" * max(0, 20 - max(1, int(pct / 5)))
            print(f"📊 Daily CG usage: {bar} {counter['count']}/{CG_SAFETY_THRESHOLD} ({pct}% of safety)")
        
        print()
        print("Flages:")
        print("  --check-collisions  -c   Collision scan only")
        print("  --budget            -b   CG budget report only")
        print("  --schedule          -s   24h timeline only")


if __name__ == "__main__":
    main()
