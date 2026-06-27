#!/usr/bin/env python3
"""Continuous improvement pass for trading advisor.

Inputs: reports/signal_performance.json
Outputs: reports/adjustment_log.json and inline heuristic updates for advisor rules.
"""
import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = SKILL_DIR / "reports"
PERF_PATH = REPORTS_DIR / "signal_performance.json"
ADJUSTMENT_PATH = REPORTS_DIR / "adjustment_log.json"

MIN_SAMPLE = 5
LOW_WIN_RATE = 40.0
HIGH_STOP_RATE = 70.0


def load_perf():
    if not PERF_PATH.exists():
        return None
    try:
        return json.loads(PERF_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def analyze(perf):
    summary = perf.get("summary") if isinstance(perf, dict) else None
    if not summary or summary.get("total_signals", 0) < MIN_SAMPLE:
        return {"status": "insufficient_data", "total_signals": (summary or {}).get("total_signals", 0)}
    signals = perf.get("signals") or []
    best = [s for s in signals if s.get("validation_status") == "backtested"]
    win_rate = summary.get("win_rate")
    stop_hit_rate = summary.get("stop_hit_rate")
    suggestions = []
    if isinstance(win_rate, (int, float)) and win_rate < LOW_WIN_RATE:
        suggestions.append("lower_confidence_threshold")
    if isinstance(stop_hit_rate, (int, float)) and stop_hit_rate > HIGH_STOP_RATE:
        suggestions.append("tighten_stop_placement")
    if suggestions:
        note = "; ".join(suggestions)
        out = {
            "status": "review",
            "win_rate": win_rate,
            "stop_hit_rate": stop_hit_rate,
            "suggestions": suggestions,
            "evidence": f"{len(best)} backtested signals",
        }
        ADJUSTMENT_PATH.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        return out
    out = {"status": "ok", "win_rate": win_rate, "stop_hit_rate": stop_hit_rate}
    ADJUSTMENT_PATH.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def main():
    perf = load_perf()
    if perf is None:
        print(f"No performance file at {PERF_PATH}")
        return
    result = analyze(perf)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
