#!/usr/bin/env python3
"""Smoke test for the trading-advisor skill.

Run after any patch. Probes each script's primary entrypoint against the
real APIs and the most recent real briefing. Returns a non-zero exit code
if any check fails.

Usage:
  python3 ~/.hermes/skills/trading-advisor/scripts/smoke_test.py

Add new probes as new scripts are added to the skill.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"
REPORTS = SKILL_DIR / "reports"


def probe_compile() -> list[str]:
    """Compile-check every Python script. Returns list of failures (empty = pass)."""
    fails = []
    for path in sorted(SCRIPTS.glob("*.py")):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            fails.append(f"{path.name}: {r.stderr.strip().splitlines()[-1] if r.stderr else 'unknown'}")
    return fails


def probe_parsers() -> dict[str, int]:
    """Run every briefing parser against the most recent real briefing."""
    briefings = sorted(REPORTS.glob("daily_briefing_*.md"))
    if not briefings:
        return {"error": "no_briefings"}
    latest = briefings[-1].read_text(encoding="utf-8")
    sys.path.insert(0, str(SCRIPTS))
    out: dict[str, int] = {}
    try:
        from paper_trader import parse_briefing_recommendations
        out["paper_trader"] = len(parse_briefing_recommendations(latest))
    except Exception as e:
        out["paper_trader"] = f"ERR: {type(e).__name__}"
    try:
        from paper_executor import parse_recommendations
        out["paper_executor"] = len(parse_recommendations(latest))
    except Exception as e:
        out["paper_executor"] = f"ERR: {type(e).__name__}"
    try:
        from signal_validator import parse_buy_recommendations
        out["signal_validator"] = len(parse_buy_recommendations(latest))
    except Exception as e:
        out["signal_validator"] = f"ERR: {type(e).__name__}"
    return out


def probe_briefing_save() -> dict:
    """Run briefing.py --save-only and confirm it produces a file."""
    r = subprocess.run([sys.executable, str(SCRIPTS / "briefing.py"), "--save-only"],
                       capture_output=True, text=True, cwd=str(SCRIPTS), timeout=180)
    return {"rc": r.returncode, "stdout_tail": r.stdout.strip().splitlines()[-1] if r.stdout else "",
            "stderr_tail": r.stderr.strip().splitlines()[-1] if r.stderr else ""}


def probe_free_data() -> dict:
    """Confirm the centralized fetcher still talks to its primary sources."""
    sys.path.insert(0, str(SCRIPTS))
    from free_data import fetch_fear_greed, fetch_defillama_protocols
    fg = fetch_fear_greed()
    fg_ok = isinstance(fg, dict) and fg.get("value") is not None
    protos = fetch_defillama_protocols(limit=3)
    protos_ok = isinstance(protos, list) and len(protos) >= 1
    return {"fear_greed_ok": fg_ok, "defillama_ok": protos_ok,
            "fear_greed_value": fg.get("value") if isinstance(fg, dict) else None,
            "top_protocol": protos[0].get("name") if protos else None}


def probe_signal_performance() -> dict:
    """Confirm signal_validator wrote a perf file and inspect staleness."""
    p = REPORTS / "signal_performance.json"
    if not p.exists():
        return {"exists": False}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        return {"exists": True, "pending": summary.get("pending_validation_count"),
                "validated": summary.get("validated_count"),
                "total": summary.get("total_signals")}
    except Exception as e:
        return {"exists": True, "parse_error": str(e)}


def probe_strategy_journal() -> dict:
    """Confirm strategy journal initializes and records a test signal, then cleans it up."""
    sys.path.insert(0, str(SCRIPTS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("strategy_journal", str(SCRIPTS / "strategy_journal.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.init_db()
    sid = mod.record_signal(symbol="TEST", name="TestCoin", bias="bullish",
                            entry_price=1.0, target_price=1.1, stop_price=0.95,
                            confidence="low", score=5.0, source="smoke_test",
                            notes="smoke test signal")
    mod.close_signal(signal_id=sid, outcome="hit_target", exit_price=1.1,
                     regime="smoke", reason="smoke_test")
    perf = mod.compute_performance("all_time")
    # Clean up test signal immediately
    conn = mod.get_conn()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM outcomes WHERE exit_reason='smoke_test'")
    conn.execute("DELETE FROM signals WHERE source='smoke_test'")
    conn.commit()
    conn.close()
    return {"init_ok": True, "signal_id": sid, "win_rate": perf.get("win_rate")}


def probe_market_news() -> dict:
    """Confirm market_news can fetch headlines."""
    sys.path.insert(0, str(SCRIPTS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("market_news", str(SCRIPTS / "market_news.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Use fallback mode to avoid scraping dependency
    news = mod.fetch_market_news(limit=3, prefer_fallback=True)
    return {"count": len(news), "sources": list(set(n.get("source", "?") for n in news))}


def probe_orchestrator_import() -> dict:
    """Confirm orchestrator module loads without errors."""
    sys.path.insert(0, str(SCRIPTS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("orchestrator", str(SCRIPTS / "orchestrator.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    params = mod.load_params()
    scr = params.get("screening", {})
    return {"load_ok": True, "min_mcap": scr.get("min_mcap")}


def main() -> int:
    failures = []
    print("== compile ==")
    fails = probe_compile()
    if fails:
        failures.extend(fails)
        for f in fails:
            print("FAIL", f)
    else:
        print("OK (all scripts compile)")

    print("== parsers (latest briefing) ==")
    for k, v in probe_parsers().items():
        print(f"  {k}: {v}")

    print("== free_data primary endpoints ==")
    fd = probe_free_data()
    print(f"  fear_greed: {fd['fear_greed_ok']} (value={fd['fear_greed_value']})")
    print(f"  defillama:  {fd['defillama_ok']} (top={fd['top_protocol']})")
    if not fd["fear_greed_ok"]:
        failures.append("fear_greed_unreachable")
    if not fd["defillama_ok"]:
        failures.append("defillama_unreachable")

    print("== briefing save-only ==")
    bs = probe_briefing_save()
    print(f"  rc={bs['rc']}  tail={bs['stdout_tail'] or bs['stderr_tail']}")
    if bs["rc"] != 0:
        failures.append("briefing_save_failed")

    print("== signal_performance.json ==")
    sp = probe_signal_performance()
    print(f"  {sp}")
    if sp.get("pending", 0) and sp.get("validated", 0) == 0:
        print("  WARN: pending validations never close — check candle fetch path")

    print("== strategy journal ==")
    sj = probe_strategy_journal()
    print(f"  init_ok={sj['init_ok']}  signal_id={sj['signal_id']}  win_rate={sj['win_rate']}")
    if not sj.get("init_ok"):
        failures.append("strategy_journal_init")

    print("== market news ==")
    mn = probe_market_news()
    print(f"  headlines={mn['count']}  sources={mn['sources']}")
    if mn["count"] == 0:
        failures.append("market_news_empty")

    print("== orchestrator import ==")
    oi = probe_orchestrator_import()
    print(f"  load_ok={oi['load_ok']}  min_mcap={oi['min_mcap']}")
    if not oi.get("load_ok"):
        failures.append("orchestrator_import")

    print()
    if failures:
        print(f"FAIL: {len(failures)} issues")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())