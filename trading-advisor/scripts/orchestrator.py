#!/usr/bin/env python3
"""Crypto Trading Orchestrator — the central coordinator.

The orchestrator runs the full pipeline:
  1. Load strategy parameters
  2. Fetch market news
  3. Run briefing with current params (scans ~424 coins, gates to USDT)
  4. Record new signals in the strategy journal
  5. Check open signals against current market data (signal validation)
  6. Compute trailing performance metrics
  7. Auto-adjust strategy parameters if performance data is sufficient
  8. Write a comprehensive digest report

This runs as a nightly cron job (30 3 * * *) and can also be triggered manually.

Usage:
    python3 orchestrator.py                          # full nightly run
    python3 orchestrator.py --quick                  # skip news + validation, briefing only
    python3 orchestrator.py --digest-only            # just print digest from existing data
    python3 orchestrator.py --dry-run                # run everything but don't save
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
STRATEGY_DIR = os.path.join(SKILL_DIR, "strategy")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(STRATEGY_DIR, exist_ok=True)

sys.path.insert(0, SCRIPTS_DIR)


def _ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_params() -> dict:
    """Load strategy params — provides defaults if file missing."""
    try:
        import strategy_journal
        return strategy_journal.load_params()
    except Exception:
        return {
            "screening": {"min_mcap": 25_000_000, "min_24h_change_pct": 2.0, "score_threshold": 20.0,
                          "max_candidates": 15, "max_opportunities": 2},
            "risk": {"risk_per_trade_pct": 2.0, "stop_loss_pct": 3.5, "target_pct": 8.0},
            "dynamic_risk": {"enabled": True, "base_target_pct": 8.0, "base_stop_pct": 3.5,
                             "min_target_pct": 5.0, "max_target_pct": 15.0,
                             "min_stop_pct": 2.0, "max_stop_pct": 8.0,
                             "trailing_stages": [[2.0, 1.0], [6.0, 2.0], [12.0, 3.0]]},
        }


def load_journal() -> object:
    """Import and return the strategy_journal module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "strategy_journal", os.path.join(SCRIPTS_DIR, "strategy_journal.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def phase_news(journal, dry_run: bool = False) -> list[dict]:
    """Phase 1: fetch and cache market news."""
    print("  Fetching market news...")
    try:
        from market_news import fetch_market_news, format_compact
        news = fetch_market_news(limit=8)
        if news and not dry_run:
            try:
                journal.cache_news(news)
            except Exception as e:
                print(f"  (cache skipped: {e})")
        return news
    except Exception as e:
        print(f"  News fetch failed: {e}")
        return []


def phase_briefing(params: dict, dry_run: bool = False) -> tuple:
    """Phase 2: run the briefing with current strategy params.
    
    Returns (briefing_text, candidates_list, batch_id).
    """
    print("  Running briefing with current strategy params...")
    try:
        from briefing import fetch_markets, simple_rules, render_compact_briefing, fetch_global, fetch_fear_greed, fetch_coincap

        markets = fetch_markets()
        global_data = fetch_global()
        fng = fetch_fear_greed()
        assets = fetch_coincap(limit=120)

        candidates = simple_rules(markets) if isinstance(markets, list) else []
        
        # Log market regime info for debugging
        try:
            _fng_r = fetch_fear_greed()
            _fng_v = int(_fng_r.get('value', 50))
            _fng_c = _fng_r.get('value_classification', '?')
            print(f"    Market regime: F&G={_fng_v} ({_fng_c})")
            if not candidates:
                print(f"    → No candidates (regime gate active)" if _fng_v <= 15 or _fng_v >= 85 else f"    → No candidates found")
        except Exception:
            pass

        # Apply parameter overrides from strategy params
        max_opps = params.get("screening", {}).get("max_opportunities", 2)
        score_threshold = params.get("screening", {}).get("score_threshold", 20.0)

        # Re-filter with current params (score threshold only — volatility gate
        # is already handled by simple_rules() with market-cap-scaled thresholds)
        filtered = []
        for c in (candidates or []):
            if c.get("score", 0) < score_threshold:
                continue
            filtered.append(c)
        candidates = filtered[:max_opps]

        text = render_compact_briefing(markets, global_data, fng, assets)
        batch_id = datetime.now(timezone.utc).strftime("briefing_%Y%m%d_%H%M%S")

        return text, candidates, batch_id
    except Exception as e:
        print(f"  Briefing failed: {e}")
        import traceback
        traceback.print_exc()
        return "Briefing generation failed.", [], "error"


def phase_journal_signals(journal, candidates: list, batch_id: str, params: dict, dry_run: bool = False) -> list[int]:
    """Phase 3: record new signals from the briefing in the strategy journal."""
    signal_ids = []
    if not candidates:
        print("  No candidates to record.")
        return signal_ids

    print(f"  Recording {len(candidates)} signals in journal...")
    journal.init_db()
    si = journal.current_strategy_identity()
    for c in candidates:
        sym = c.get("symbol", "???").upper()
        name = c.get("name", sym)
        entry = c.get("price") or 0
        target = c.get("target_price") or (entry * 1.08 if entry else None)
        stop = c.get("stop_price") or (entry * 0.965 if entry else None)
        bias = "bullish" if (c.get("change_24h") or 0) >= 0 else "bearish"

        if dry_run:
            sid = -1
        else:
            sid = journal.record_signal(
                symbol=sym, name=name, bias=bias,
                entry_price=entry, target_price=target, stop_price=stop,
                confidence=c.get("confidence", "medium"), score=c.get("score"),
                source="briefing", batch_id=batch_id,
                notes=f"strategy={si['strategy_id']} | score={c.get('score')} | 24h={c.get('change_24h', 0):.2f}%",
            )
        signal_ids.append(sid)
        print(f"    Signal #{sid}: {name} ({sym}) @ ${entry:.4f}")
    return signal_ids


def phase_validate_open(journal, dry_run: bool = False) -> list[dict]:
    """Phase 4: check open signals against current market data."""
    print("  Validating open signals...")
    open_signals = journal.get_open_signals()
    if not open_signals:
        print("    No open signals to validate.")
        return []

    # Get current prices for all open symbols
    symbols = list(set(s["symbol"] for s in open_signals))
    try:
        from free_data import _get
        # Resolve CoinGecko IDs for open signals
        try:
            sym_to_id = journal._fetch_coingecko_coin_list()
        except Exception:
            sym_to_id = {}

        # Batch price lookup
        ids = [sym_to_id.get(s.upper()) for s in symbols if sym_to_id.get(s.upper())]
        if ids:
            prices_raw = _get(
                "https://api.coingecko.com/api/v3/simple/price",
                {"ids": ",".join(ids), "vs_currencies": "usd"},
            )
            prices = {}
            for cg_id, entry in (prices_raw or {}).items():
                if isinstance(entry, dict):
                    usd = entry.get("usd")
                    if usd:
                        # Find which symbol this ID maps to
                        for sym, cid in sym_to_id.items():
                            if cid == cg_id:
                                prices[sym] = usd
                                break
        else:
            prices = {}
    except Exception as e:
        print(f"    Price fetch failed: {e}")
        prices = {}

    outcomes = []
    for signal in open_signals:
        sym = signal["symbol"]
        current_price = prices.get(sym)
        if not current_price:
            continue

        entry = signal.get("entry_price") or 0
        target = signal.get("target_price")
        stop = signal.get("stop_price")
        bias = signal.get("bias", "bullish")

        outcome = None
        if entry > 0 and target and stop:
            if bias == "bullish":
                if current_price >= target:
                    outcome = "hit_target"
                elif current_price <= stop:
                    outcome = "hit_stop"
            else:
                if current_price <= target:
                    outcome = "hit_target"
                elif current_price >= stop:
                    outcome = "hit_stop"
        # Trailing stop detection: check if current_price validates a trailing_stop close
        # from a prior M2M update in the paper trader (already reflected in journal)
        # This is handled by the paper_trader M2M loop; the orchestrator trusts
        # that paper_trader --update catches trailing stops between runs.

        if outcome and not dry_run:
            result = journal.close_signal(
                signal_id=signal["id"],
                outcome=outcome,
                exit_price=current_price,
                regime="auto_validation",
                reason="orchestrator_price_check",
            )
            outcomes.append(result)
            pnl = result.get("pnl_pct")
            pnl_s = f"{pnl:+.2f}%" if pnl is not None else "N/A"
            print(f"    CLOSE #{signal['id']} {sym}: {outcome} @ ${current_price} ({pnl_s})")
        elif outcome:
            print(f"    (DRY) CLOSE #{signal['id']} {sym}: {outcome} @ ${current_price}")

    if not outcomes and open_signals:
        print(f"    {len(open_signals)} signals still open (no prices or no thresholds met).")
    return outcomes


def phase_performance(journal, dry_run: bool = False) -> dict:
    """Phase 5: compute and store performance snapshot."""
    print("  Computing performance...")
    try:
        perf = journal.compute_performance("trailing_30d")
        print(f"    WR={perf['win_rate']:.1%} | {perf['win_count']}W/{perf['loss_count']}L | PF={perf['profit_factor']:.2f}")
        return perf
    except Exception as e:
        print(f"    Performance computation failed: {e}")
        return {}


def phase_adapt(journal, params: dict, dry_run: bool = False) -> dict:
    """Phase 6: auto-adjust strategy parameters based on performance."""
    print("  Checking parameter adaptation...")
    try:
        result = journal.adapt_params()
        if result.get("adjusted"):
            print(f"    ✅ Adjusted: {'; '.join(result.get('adjustments', []))}")
            print(f"    New thresholds: {result.get('params', {})}")
        else:
            print(f"    ⏸ {result.get('reason', 'no adjustment needed')}")
        return result
    except Exception as e:
        print(f"    Adaptation failed: {e}")
        return {"adjusted": False, "reason": f"error: {e}"}


def build_digest(news: list, briefing_text: str, candidates: list,
                 outcomes: list, perf: dict, adapt_result: dict,
                 params: dict, batch_id: str, dashboard_text: str = "") -> str:
    """Build the orchestrator digest report."""
    lines = []
    lines.append("# 📡 Orchestrator Digest")
    lines.append(f"Generated: {_ts()}")
    lines.append(f"Batch: {batch_id}")
    lines.append("")

    # Strategy params snapshot
    lines.append("## Strategy Parameters")
    scr = params.get("screening", {})
    risk = params.get("risk", {})
    lines.append(f"- Min mcap: ${scr.get('min_mcap', 0):,}")
    lines.append(f"- Min 24h change: {scr.get('min_24h_change_pct', 0)}%")
    lines.append(f"- Score threshold: {scr.get('score_threshold', 0)}")
    lines.append(f"- Risk per trade: {risk.get('risk_per_trade_pct', 0)}%")
    lines.append(f"- Stop loss: {risk.get('stop_loss_pct', 0)}%")
    dr = params.get("dynamic_risk", {})
    if dr.get("enabled"):
        lines.append(f"- Dynamic target/stop: ✅ enabled (range {dr.get('min_target_pct', 5)}%-{dr.get('max_target_pct', 15)}% / {dr.get('min_stop_pct', 2)}%-{dr.get('max_stop_pct', 8)}%)")
        _trail_stages = dr.get("trailing_stages", [[2, 1], [6, 2], [12, 3]])
        _trail_stages_str = " → ".join([f"+{s[0]:.0f}%/{s[1]:.0f}%" for s in _trail_stages])
        lines.append(f"- Trailing stop: {_trail_stages_str}")
    lines.append(f"- Target: {risk.get('target_pct', 0)}%")
    if adapt_result.get("adjusted"):
        lines.append(f"- 🔄 Auto-adjusted: {'; '.join(adapt_result.get('adjustments', []))}")
    lines.append("")

    # Trailing stops section (from paper trader portfolio)
    try:
        _pp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "reports", "paper_trading", "portfolio.json")
        if os.path.exists(_pp):
            with open(_pp) as _pf:
                _port = json.load(_pf)
            _trailed = []
            for _sym, _pos in (_port.get("positions") or {}).items():
                if _pos.get("trailing_activated"):
                    _trail = _pos.get("trailing_stop")
                    _hp = _pos.get("highest_price")
                    _cur = _pos.get("current_price", 0)
                    _pnl = _pos.get("pnl_pct", 0)
                    _s = f"🔒 {_sym}: trail=${_trail} (high=${_hp}, curr=${_cur}, P&L={_pnl:+.2f}%)" if _trail else f"🔒 {_sym}: active (P&L={_pnl:+.2f}%)"
                    _trailed.append(_s)
            if _trailed:
                lines.append("### Trailing Stops")
                for _s in _trailed:
                    lines.append(f"- {_s}")
                lines.append("")
    except Exception:
        pass

    # News summary
    lines.append("## Market News")
    if news:
        bullish = sum(1 for n in news if n.get("sentiment") == "bullish")
        bearish = sum(1 for n in news if n.get("sentiment") == "bearish")
        lines.append(f"🟢 {bullish} bullish · 🔴 {bearish} bearish · ⚪ {len(news) - bullish - bearish} neutral")
        for n in news[:5]:
            icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(n.get("sentiment", "neutral"), "⚪")
            lines.append(f"- {icon} {n['headline']}")
    else:
        lines.append("No news data.")
    lines.append("")

    # Opportunities
    lines.append("## Opportunities")
    if candidates:
        for i, c in enumerate(candidates, 1):
            lines.append(f"{i}. **{c['name']}** ({c['symbol']})")
            lines.append(f"   - Score: {c.get('score', '?')} | 24h: {c.get('change_24h', 0):+.2f}%")
            lines.append(f"   - Entry: ${c.get('price', 0):.4f}")
    else:
        lines.append("No high-confidence setups.")
    lines.append("")

    # Signal validation
    lines.append("## Signal Validation")
    if outcomes:
        for o in outcomes:
            pnl = o.get("pnl_pct")
            pnl_s = f"{pnl:+.2f}%" if pnl is not None else "N/A"
            lines.append(f"- {o.get('symbol', '?')}: {o.get('outcome', '?')} ({pnl_s})")
    else:
        lines.append("No signals closed this cycle.")
    lines.append("")

    # Performance
    lines.append("## Performance (trailing 30d)")
    if perf:
        lines.append(f"- Win rate: {perf.get('win_rate', 0):.1%}")
        lines.append(f"- {perf.get('win_count', 0)}W / {perf.get('loss_count', 0)}L")
        lines.append(f"- Avg PnL: {perf.get('avg_pnl_pct', 0):+.2f}%")
        lines.append(f"- Profit factor: {perf.get('profit_factor', 0):.2f}")
        lines.append(f"- Streak: {perf.get('current_streak', 0)}")
        lines.append(f"- Best: {perf.get('best_symbol', '?')} | Worst: {perf.get('worst_symbol', '?')}")
    else:
        lines.append("No data yet.")
    lines.append("")

    # Research calibration health
    # NOTE: Must use importlib.util.spec_from_file_location with absolute path,
    # NOT "from strategy.portfolio_engine import ...". The orchestrator runs from
    # the cron environment where STRATEGY_DIR is not in sys.path. The briefing.py
    # pattern (_lazy_load_portfolio_engine) uses SKILL_DIR-based absolute imports
    # which work regardless of CWD.working directory.
    try:
        import importlib.util as _iu
        _pe_path = os.path.join(STRATEGY_DIR, "portfolio_engine.py")
        if os.path.exists(_pe_path):
            _spec = _iu.spec_from_file_location("portfolio_engine", _pe_path)
            _pe = _iu.module_from_spec(_spec)
            _spec.loader.exec_module(_pe)
            cal_lines, cal_score = _pe.calibration_health()
            lines.extend(cal_lines)
            adj = _pe.suggest_adjustments()
            if adj:
                for a in adj:
                    lines.append(f"  → {a}")
        else:
            raise ImportError("portfolio_engine.py not found")
    except Exception as e:
        lines.append("## Research Calibration Health")
        lines.append(f"  ℹ️ Calibration check unavailable: {e}")
    lines.append("")

    # Dashboard (compact mode)
    if dashboard_text:
        lines.append("## Strategy Dashboard (compact)")
        for _dl in dashboard_text.split("\n"):
            lines.append(f"- {_dl.strip()}")
        lines.append("")

    # Briefing (compact)
    lines.append("## Full Briefing")
    lines.append(briefing_text)

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Crypto Trading Orchestrator")
    p.add_argument("--quick", action="store_true", help="Skip news + validation, briefing only")
    p.add_argument("--digest-only", action="store_true", help="Print digest from existing data")
    p.add_argument("--dry-run", action="store_true", help="Run everything but don't save")
    p.add_argument("--out", default=None, help="Output path for digest")
    args = p.parse_args()

    params = load_params()
    batch_id = datetime.now(timezone.utc).strftime("orchestrator_%Y%m%d_%H%M%S")

    if args.digest_only:
        print("Digest-only mode not yet implemented with stored data.")
        return

    print(f"\n{'=' * 50}")
    print(f"  Crypto Trading Orchestrator — {_ts()}")
    print(f"{'=' * 50}\n")

    # Load journal
    journal = load_journal()
    journal.init_db()

    total_start = time.time()

    # Phase 1: News
    news = []
    if not args.quick:
        news = phase_news(journal, dry_run=args.dry_run)
        print()

    # Phase 2: Briefing
    briefing_text, candidates, batch_id = phase_briefing(params, dry_run=args.dry_run)
    print()

    # Phase 3: Record signals
    if candidates:
        phase_journal_signals(journal, candidates, batch_id, params, dry_run=args.dry_run)
        print()

    # Phase 4: Validate open signals
    outcomes = []
    if not args.quick:
        outcomes = phase_validate_open(journal, dry_run=args.dry_run)
        print()

    # Phase 5: Performance
    perf = {}
    if not args.quick:
        perf = phase_performance(journal, dry_run=args.dry_run)
        print()

    # Phase 6: Auto-adapt params
    adapt_result = {}
    if not args.quick:
        adapt_result = phase_adapt(journal, params, dry_run=args.dry_run)
        print()

    # Phase 7: Strategy dashboard (optional, non-fatal)
    dashboard_text = ""
    if not args.quick:
        print("  Generating strategy dashboard...")
        try:
            import subprocess
            _dp = os.path.join(STRATEGY_DIR, "dashboard.py")
            _res = subprocess.run(
                [sys.executable, _dp, "--compact"],
                capture_output=True, text=True, timeout=30,
                cwd=STRATEGY_DIR,
            )
            if _res.returncode == 0 and _res.stdout.strip():
                dashboard_text = _res.stdout.strip()
        except Exception as e:
            print(f"    Dashboard skipped: {e}")

    # Build digest
    digest = build_digest(news, briefing_text, candidates, outcomes,
                          perf, adapt_result, params, batch_id, dashboard_text)

    # Save digest
    if args.out:
        out_path = args.out
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = os.path.join(REPORTS_DIR, f"orchestrator_digest_{today}.md")

    if not args.dry_run:
        os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(digest)
        print(f"Digest saved to {out_path}")
    else:
        print("[DRY RUN — no files saved]")

    elapsed = time.time() - total_start
    print(f"\nOrchestrator cycle complete in {elapsed:.0f}s")
    print(digest)


if __name__ == "__main__":
    main()
