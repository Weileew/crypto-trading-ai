#!/usr/bin/env python3
"""Portfolio engine — correlation-aware sizing, drawdown limits, exposure gating.

Reads portfolio state from the paper-trading ledger, computes trailing drawdown,
fetches historical returns for correlation analysis, and returns a penalty
multiplier that simple_rules() applies to candidate scores.

Integration points:
  - briefing.py simple_rules() calls portfolio_penalty() → score *= multiplier
  - orchestrator.py can call refresh_correlation_cache() after screening

Calibration constants live in strategy/research-calibrations.json under "portfolio".
"""
import json
import math
import os
import time as _time_module
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(REPORTS_DIR, "paper_trading")
STRATEGY_DIR = os.path.join(SKILL_DIR, "strategy")
CALIB_PATH = os.path.join(STRATEGY_DIR, "research-calibrations.json")
UA = "crypto-trading-advisor/0.1 (+https://example.com)"

# ── Calibrations ───────────────────────────────────────────────────────────────

_DEFAULTS = {
    "portfolio": {
        "concurrency_max": 3,
        "drawdown_limit_pct": 10.0,
        "drawdown_sizing_reduction_pct": 50.0,
        "max_exposure_pct": 20.0,
        "correlation_threshold": 0.70,
        "correlation_exposure_penalty": 0.50,
        "correlation_lookback_days": 30,
    }
}


def _load_calibrations():
    try:
        with open(CALIB_PATH, encoding="utf-8") as f:
            cal = json.load(f)
        return {**_DEFAULTS, **cal.get("portfolio", {})}
    except Exception:
        return _DEFAULTS["portfolio"]


# ── Portfolio State Reader ─────────────────────────────────────────────────────

def load_portfolio():
    """Return dict of open positions from paper_trader portfolio.json."""
    path = os.path.join(PAPER_DIR, "portfolio.json")
    try:
        with open(path, encoding="utf-8") as f:
            pf = json.load(f)
    except Exception:
        return {"positions": {}, "cash": 0.0, "starting_capital": 0.0}
    return pf


def load_ledger(days=90):
    """Return list of trade dicts from ledger.json within lookback."""
    path = os.path.join(PAPER_DIR, "ledger.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    trades = data if isinstance(data, list) else data.get("trades", [])
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    recent = []
    for t in trades:
        ts = 0.0
        if t.get("closed_at"):
            try:
                ts = datetime.fromisoformat(t["closed_at"].replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError):
                pass
        if ts >= cutoff:
            recent.append(t)
    return recent


# ── Drawdown ───────────────────────────────────────────────────────────────────

def compute_drawdown(portfolio, ledger):
    """Compute trailing portfolio drawdown as a percentage of starting capital.

    Returns (current_equity, peak_equity, drawdown_pct).
    Current equity = cash + sum of position values (estimated at entry price).
    Peak equity = max of (starting_capital, cash + closed_pnl).
    """
    starting = portfolio.get("starting_capital", 10000.0)
    cash = portfolio.get("cash", 0.0)

    # Sum of closed trade P&L (only trades with actual pnl values)
    closed_pnl = 0.0
    for t in ledger:
        pnl = t.get("pnl_usd") or t.get("pnl", 0.0)
        if isinstance(pnl, (int, float)):
            closed_pnl += pnl

    # Value of open positions at entry prices
    positions = portfolio.get("positions", {})
    open_value = 0.0
    for sym, pos in positions.items():
        entry = pos.get("entry_price") or pos.get("avg_entry", 0.0)
        qty = pos.get("quantity") or pos.get("qty", 0.0)
        if entry and qty:
            open_value += entry * qty

    current_equity = cash + open_value
    peak_equity = max(starting, cash + closed_pnl + open_value)

    if peak_equity <= 0:
        return current_equity, peak_equity, 0.0

    drawdown_pct = (peak_equity - current_equity) / peak_equity * 100.0
    drawdown_pct = max(0.0, drawdown_pct)  # no negative drawdown
    return current_equity, peak_equity, round(drawdown_pct, 2)


# ── Correlation ────────────────────────────────────────────────────────────────

_CACHED_RETURNS = {}  # symbol_lower → list of daily returns
_CACHED_LAST_CALL = 0.0
_CG_MIN_INTERVAL = 6.0


def _cg_throttle():
    global _CACHED_LAST_CALL
    wait = _CG_MIN_INTERVAL - (_time_module.time() - _CACHED_LAST_CALL)
    if wait > 0:
        _time_module.sleep(wait)
    _CACHED_LAST_CALL = _time_module.time()


def fetch_daily_returns(symbol, coin_id=None, days=30):
    """Fetch daily close prices from CoinGecko and return list of daily returns.

    Uses simple (close_t - close_{t-1}) / close_{t-1} for each consecutive pair.
    Caches results per symbol within the process lifetime.
    Returns [] on any failure.
    """
    sym = (symbol or "").lower()
    if sym in _CACHED_RETURNS:
        return _CACHED_RETURNS[sym]

    if not coin_id:
        coin_id = sym

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": min(days, 90)}

    _cg_throttle()
    req = Request(f"{url}?{_urlencode(params)}", headers={"User-Agent": UA})
    closes = []
    try:
        with urlopen(req, timeout=20) as resp:
            ohlc = json.loads(resp.read().decode())
        if not isinstance(ohlc, list) or len(ohlc) < 2:
            _CACHED_RETURNS[sym] = []
            return []
        closes = [x[4] for x in ohlc]
    except (HTTPError, OSError, ValueError, json.JSONDecodeError):
        _CACHED_RETURNS[sym] = []
        return []

    returns = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            continue
        r = (closes[i] - prev) / prev
        returns.append(round(r, 6))
    _CACHED_RETURNS[sym] = returns
    return returns


def _urlencode(params):
    from urllib.parse import urlencode
    return urlencode(params)


def _pearson(xs, ys):
    """Pearson correlation coefficient between two equal-length lists."""
    n = len(xs)
    if n < 3:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    r = numer / (denom_x * denom_y)
    return max(-1.0, min(1.0, r))


def get_pair_correlation(sym_a, coin_id_a, sym_b, coin_id_b, days=30):
    """Return Pearson correlation between two symbols' daily returns."""
    ra = fetch_daily_returns(sym_a, coin_id_a, days)
    rb = fetch_daily_returns(sym_b, coin_id_b, days)
    n = min(len(ra), len(rb))
    if n < 3:
        return 0.0
    return _pearson(ra[-n:], rb[-n:])


# ── Main Public API ────────────────────────────────────────────────────────────

# Alias map for known symbols (mirrors signal_validator.py's ALIAS)
_ALIAS = {
    "btc": "bitcoin", "eth": "ethereum", "bnb": "binancecoin", "sol": "solana",
    "xrp": "ripple", "ada": "cardano", "avax": "avalanche-2", "doge": "dogecoin",
    "dot": "polkadot", "matic": "matic-network", "link": "chainlink", "uni": "uniswap",
    "ltc": "litecoin", "atom": "cosmos", "apt": "aptos", "arb": "arbitrum",
    "op": "optimism", "near": "near", "ftm": "fantom", "icp": "internet-computer",
    "aave": "aave", "comp": "compound-governance-token", "mkr": "maker", "snx": "havven",
    "crv": "curve-dao-token", "1inch": "1inch", "enj": "enjincoin", "mana": "decentraland",
    "sand": "the-sandbox", "gala": "gala", "axs": "axie-infinity", "imx": "immutable-x",
    "ldo": "lido-dao", "rpl": "rocket-pool", "sui": "sui", "sei": "sei-network",
    "tia": "celestia", "bonk": "bonk", "wif": "dogwifcoin", "pepe": "pepe",
    "shib": "shiba-inu", "floki": "floki", "render": "render-token", "rndr": "render-token",
    "celo": "celo", "osmosis": "osmosis", "inj": "injective-protocol", "ckb": "nervos-network",
    "ronin": "ronin", "magma": "magma-finance", "velvet": "velvet", "skyai": "skyai",
}


def _resolve_coin_id(sym):
    return _ALIAS.get((sym or "").lower(), (sym or "").lower())


def portfolio_penalty(proposed_symbol=None, proposed_score=0.0):
    """Compute portfolio-level penalty multiplier for a candidate score.

    Args:
        proposed_symbol: Symbol being scored (e.g. 'btc', 'magma'). If None,
                         returns only global (drawdown) penalty.
        proposed_score: Current raw score of the candidate (before portfolio adj).

    Returns:
        (multiplier, reasons)
        - multiplier: 0.0 to 1.0 — multiply the candidate score by this
        - reasons: list of human-readable strings explaining adjustments
    """
    cal = _load_calibrations()
    reasons = []

    # 1. Read portfolio state
    portfolio = load_portfolio()
    ledger = load_ledger(days=90)

    positions = portfolio.get("positions", {})
    open_count = len(positions)
    cash = portfolio.get("cash", 0.0)
    starting = portfolio.get("starting_capital", 10000.0)

    # 2. Concurrency check
    concurrency_max = cal.get("concurrency_max", 3)
    if open_count >= concurrency_max:
        reasons.append(f"portfolio at max concurrency ({open_count}/{concurrency_max})")
        return 0.0, reasons

    # 3. Drawdown check
    current_equity, peak_equity, dd_pct = compute_drawdown(portfolio, ledger)
    dd_limit = cal.get("drawdown_limit_pct", 10.0)
    dd_reduction = cal.get("drawdown_sizing_reduction_pct", 50.0) / 100.0

    if dd_pct >= dd_limit:
        reasons.append(f"drawdown {dd_pct:.1f}% ≥ limit {dd_limit:.0f}% — gating")
        return 0.0, reasons
    elif dd_pct > 0:
        # Proportional drawdown penalty: scale linearly from 0% = 1.0x to limit = (1 - reduction)
        drawdown_ratio = dd_pct / dd_limit
        drawdown_mult = 1.0 - (drawdown_ratio * dd_reduction)
        drawdown_mult = max(0.5, drawdown_mult)
        if drawdown_mult < 1.0:
            reasons.append(f"portfolio drawdown {dd_pct:.1f}% → size {drawdown_mult:.0%}")
    else:
        drawdown_mult = 1.0

    # 4. Exposure check (total capital at risk)
    max_exposure = cal.get("max_exposure_pct", 20.0) / 100.0
    if starting > 0:
        total_at_risk = (cash / starting) * (1.0 - drawdown_mult)
        # Not a hard gate — just reporting for now

    multiplier = drawdown_mult

    # 5. Correlation check (if proposed_symbol provided)
    if proposed_symbol and positions:
        correlation_threshold = cal.get("correlation_threshold", 0.70)
        correlation_penalty = cal.get("correlation_exposure_penalty", 0.50)

        proposed_sym_lower = (proposed_symbol or "").lower()
        proposed_cg = _resolve_coin_id(proposed_sym_lower)

        # Only check correlation if we can get returns data for proposed coin
        proposed_returns = fetch_daily_returns(proposed_sym_lower, proposed_cg,
                                                days=cal.get("correlation_lookback_days", 30))
        if proposed_returns and len(proposed_returns) >= 3:
            max_corr = 0.0
            max_corr_with = ""

            for existing_sym in positions:
                existing_cg = _resolve_coin_id(existing_sym)
                existing_returns = fetch_daily_returns(existing_sym, existing_cg,
                                                        days=cal.get("correlation_lookback_days", 30))
                if existing_returns and len(existing_returns) >= 3:
                    n = min(len(proposed_returns), len(existing_returns))
                    if n >= 3:
                        corr = _pearson(proposed_returns[-n:], existing_returns[-n:])
                        if abs(corr) > abs(max_corr):
                            max_corr = corr
                            max_corr_with = existing_sym

            if abs(max_corr) >= correlation_threshold and max_corr_with:
                penalty = correlation_penalty
                reasons.append(
                    f"r={max_corr:.2f} with {max_corr_with} (>={correlation_threshold}) → "
                    f"score ×{1 - penalty:.0%}"
                )
                multiplier *= (1.0 - penalty)

    if not reasons:
        reasons.append("within portfolio limits")

    return round(multiplier, 3), reasons


def clear_cache():
    """Clear the per-process returns cache. Call between briefing runs."""
    _CACHED_RETURNS.clear()


# ── Calibrations Feedback Loop ────────────────────────────────────────────────

_JOURNAL_DB = os.path.join(STRATEGY_DIR, "journal.db")


def _read_journal(sql: str, params=()) -> list:
    """Run a read query on the strategy journal DB. Returns [] on failure."""
    import sqlite3
    try:
        conn = sqlite3.connect(_JOURNAL_DB)
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def journal_performance(days=30, exclude_sources=None) -> dict:
    """Read trailing performance from the strategy journal.

    Returns a dict with empirical trading stats or {"status": "no_data"}.
    """
    if exclude_sources is None:
        exclude_sources = ['signal_validator']

    cutoff = (datetime.now(timezone.utc).timestamp() - days * 86400) * 1000

    # Most recent performance snapshot
    rows = _read_journal(
        "SELECT win_rate, profit_factor, avg_pnl_pct, avg_win_pct, avg_loss_pct, "
        "       total_signals, closed_signals, win_count, loss_count "
        "FROM performance ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return {"status": "no_data"}

    r = rows[0]
    win_rate = r[0]
    pf = r[1]
    avg_pnl = r[2]
    avg_win = r[3]
    avg_loss = r[4]
    total = r[5] or 0
    closed = r[6] or 0
    wins = r[7] or 0
    losses = r[8] or 0

    # Read raw outcomes for deeper analysis (filtering out excluded sources)
    placeholders = ','.join('?' for _ in exclude_sources)
    source_filter = f"AND s.source NOT IN ({placeholders})" if exclude_sources else ""
    outcomes = _read_journal(
        f"SELECT o.outcome, o.pnl_pct, o.duration_hours, o.exit_reason, s.symbol "
        f"FROM outcomes o JOIN signals s ON o.signal_id = s.id "
        f"WHERE 1=1 {source_filter} ORDER BY o.id DESC",
        tuple(exclude_sources) if exclude_sources else ()
    )

    # Compute stop-hit rate
    stop_hit = sum(1 for o in outcomes if o[0] in ("hit_stop", "stop") or (o[3] or "").startswith("stop"))
    target_hit = sum(1 for o in outcomes if o[0] in ("hit_target", "target") or (o[3] or "").startswith("target"))
    expired = sum(1 for o in outcomes if o[0] == "expired")
    trailing = sum(1 for o in outcomes if o[0] == "trailing_stop")
    total_closed = len(outcomes)

    return {
        "status": "ok",
        "total_signals": total,
        "closed": closed,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "profit_factor": round(pf, 2) if pf is not None else None,
        "avg_pnl_pct": round(avg_pnl, 2) if avg_pnl is not None else None,
        "avg_win_pct": round(avg_win, 2) if avg_win is not None else None,
        "avg_loss_pct": round(avg_loss, 2) if avg_loss is not None else None,
        "stop_hit_rate": round(stop_hit / total_closed * 100, 1) if total_closed else None,
        "target_hit_rate": round(target_hit / total_closed * 100, 1) if total_closed else None,
        "trailing_stop_rate": round(trailing / total_closed * 100, 1) if total_closed else None,
        "expired_rate": round(expired / total_closed * 100, 1) if total_closed else None,
        "total_closed": total_closed,
    }


def calibration_health() -> tuple:
    """Compare empirical trading performance against research-calibrated thresholds.

    Returns (health_lines, score) where:
      health_lines: list of human-readable strings
      score: 0.0 (bad) to 1.0 (all calibrations validated)
    """
    cal = _load_calibrations()
    perf = journal_performance(days=30)
    issues = []
    notes = []

    # Read portfolio state
    portfolio = load_portfolio()
    ledger = load_ledger(days=90)
    eq, peak, dd_pct = compute_drawdown(portfolio, ledger)

    # Read strategy params
    params_path = os.path.join(STRATEGY_DIR, "params.json")
    params = {}
    try:
        with open(params_path, encoding="utf-8") as f:
            params = json.load(f)
    except Exception:
        pass

    screening = params.get("screening", {})
    risk = params.get("risk", {})
    dyn = params.get("dynamic_risk", {})

    dd_limit = cal.get("drawdown_limit_pct", 10.0)
    concurrency = cal.get("concurrency_max", 3)
    corr_threshold = cal.get("correlation_threshold", 0.70)
    spread_ideal = cal.get("spread_ideal_bps", 3.0)
    high_vol = cal.get("high_vol_threshold", 0.03)
    low_vol = cal.get("low_vol_threshold", 0.015)

    # 1. Drawdown health
    if dd_pct > 0:
        pct_of_limit = dd_pct / dd_limit * 100
        if dd_pct >= dd_limit * 0.8:
            issues.append(f"drawdown {dd_pct:.1f}% at {pct_of_limit:.0f}% of limit ({dd_limit:.0f}%)")
        elif dd_pct >= dd_limit * 0.5:
            notes.append(f"drawdown {dd_pct:.1f}% — {pct_of_limit:.0f}% of limit headroom")
        else:
            notes.append(f"drawdown {dd_pct:.1f}% — well within {dd_limit:.0f}% limit")
    else:
        notes.append("no drawdown — portfolio at peak")

    # 2. Concurrency health
    open_count = len(portfolio.get("positions", {}))
    if open_count > 0:
        if open_count >= concurrency:
            notes.append(f"at concurrency limit ({open_count}/{concurrency})")
        else:
            notes.append(f"open positions {open_count}/{concurrency}")

    # 3. Win rate vs expected (momentum papers: 58-65% directional accuracy)
    wr = perf.get("win_rate")
    if wr is not None and perf.get("closed", 0) >= 5:
        if wr < 0.40:
            issues.append(f"win rate {wr:.1%} below 40% — tighten params")
        elif wr > 0.65:
            notes.append(f"win rate {wr:.1%} above typical paper range — consider loosening")
        elif wr >= 0.50:
            notes.append(f"win rate {wr:.1%} within expected range")
        else:
            notes.append(f"win rate {wr:.1%} — below 50%, monitor")
    elif perf.get("closed", 0) > 0:
        notes.append(f"win rate: {wr} ({perf.get('closed')} closed signals — insufficient sample)")
    else:
        notes.append("no closed signals yet")

    # 4. Stop-hit rate vs expected
    shr = perf.get("stop_hit_rate")
    if shr is not None and perf.get("total_closed", 0) >= 5:
        if shr > 70:
            issues.append(f"stop hit rate {shr:.0f}% > 70% — stops too tight")
        elif shr > 50:
            notes.append(f"stop hit rate {shr:.0f}% — monitor for tightening")
        else:
            notes.append(f"stop hit rate {shr:.0f}% within normal range")

    # 5. Profit factor
    pf = perf.get("profit_factor")
    if pf is not None and perf.get("closed", 0) >= 5:
        if pf < 1.0:
            issues.append(f"profit factor {pf:.2f} < 1.0 — negative expectancy")
        elif pf < 1.5:
            notes.append(f"profit factor {pf:.2f} — below target, worth monitoring")
        else:
            notes.append(f"profit factor {pf:.2f} — above 1.5, healthy")

    # 6. Vol-regime thresholds check (are we getting enough high-vol setups?)
    pavg = perf.get("avg_pnl_pct")
    if pavg is not None and perf.get("closed", 0) >= 5:
        if pavg > 0:
            notes.append(f"avg PnL +{pavg:.2f}%")
        else:
            notes.append(f"avg PnL {pavg:.2f}% — negative")

    score = 1.0
    if issues:
        score -= 0.2 * len(issues)
    if perf.get("closed", 0) < 5:
        score -= 0.1  # insufficient data penalty
    score = max(0.1, min(1.0, score))

    lines = [
        "## Research Calibration Health",
    ]
    lines.append(f"- Data: {perf.get('closed', 0)} closed trades · "
                 f"{'insufficient (<5)' if perf.get('closed', 0) < 5 else 'sufficient sample'}")
    lines.append(f"- Score: {'🟢' if score >= 0.7 else '🟡' if score >= 0.4 else '🔴'} {score:.0%}")
    for n in notes:
        lines.append(f"  · {n}")
    for issue in issues:
        lines.append(f"  ⚠️ {issue}")
    if not issues and perf.get("closed", 0) >= 5:
        lines.append("  ✅ All calibrations within expected range")
    if perf.get("closed", 0) < 5:
        lines.append("  ℹ️ Accumulate ≥5 closed trades for meaningful calibration check")

    # Parameter optimizer findings (if available)
    _opt_path = os.path.join(STRATEGY_DIR, "optimizer_report.json")
    if os.path.exists(_opt_path):
        try:
            with open(_opt_path, encoding="utf-8") as _opf:
                _opt = json.load(_opf)
            _recs = _opt.get("recommendations", [])
            _non_trivial = [r for r in _recs if "no adjustments needed" not in r.lower()]
            if _non_trivial:
                lines.append("  📊 Parameter optimizer:")
                for _r in _non_trivial[:3]:
                    lines.append(f"    → {_r}")
        except Exception:
            pass

    return lines, score


def suggest_adjustments() -> list[str]:
    """Return recommended calibration tuning based on empirical performance.

    Returns list of action strings (may be empty if no adjustments needed).
    """
    cal = _load_calibrations()
    perf = journal_performance(days=30)
    suggestions = []

    if perf.get("closed", 0) < 5:
        return ["Need ≥5 closed signals before suggesting calibration adjustments."]

    wr = perf.get("win_rate")
    shr = perf.get("stop_hit_rate")
    pf = perf.get("profit_factor")

    # Win rate below 40% → tighten screening params
    if wr is not None and wr < 0.40:
        suggestions.append(
            f"Win rate {wr:.1%} < 40%: consider raising min_24h_change_pct "
            f"(from 3.0%) or score_threshold (from 25) in params.json"
        )

    # Stop hit rate > 70% → widen stops
    if shr is not None and shr > 70:
        suggestions.append(
            f"Stop hit rate {shr:.0f}% > 70%: consider widening stop distances "
            f"or lowering dynamic risk's base_stop_pct in params.json"
        )

    # Profit factor < 1.0 → signal quality issue
    if pf is not None and pf < 1.0:
        suggestions.append(
            f"Profit factor {pf:.2f} < 1.0: review trap-filter scores or "
            f"increase correlation_threshold in research-calibrations.json"
        )

    # Correlation threshold calibration
    portfolio = load_portfolio()
    if len(portfolio.get("positions", {})) > 1:
        suggestions.append(
            "Multiple concurrent positions: verify correlation_threshold=0.70 "
            "in research-calibrations.json is catching same-sector moves"
        )

    return suggestions


if __name__ == "__main__":
    import sys
    print("=== Portfolio Engine ===")
    portfolio = load_portfolio()
    ledger = load_ledger()
    eq, peak, dd = compute_drawdown(portfolio, ledger)
    print(f"Cash: ${portfolio.get('cash', 0):,.2f}")
    print(f"Open positions: {len(portfolio.get('positions', {}))}")
    print(f"Equity: ${eq:,.2f} / Peak: ${peak:,.2f} → Drawdown: {dd:.2f}%")
    print()

    proposed = sys.argv[1] if len(sys.argv) > 1 else None
    if proposed:
        mult, reasons = portfolio_penalty(proposed)
        print(f"Proposed: {proposed}")
        print(f"Multiplier: {mult}")
        for r in reasons:
            print(f"  - {r}")
    else:
        mult, reasons = portfolio_penalty()
        print(f"Global multiplier: {mult}")
        for r in reasons:
            print(f"  - {r}")
    print("Done.")
