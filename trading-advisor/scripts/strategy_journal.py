#!/usr/bin/env python3
"""Strategy journal — persistent SQLite store for signals, outcomes, params, and performance.

This is the long-term memory of the trading advisor. Every signal, outcome,
parameter adjustment, and performance snapshot lives here so the orchestrator
can learn from past results and adapt in real-time.

Usage:
    python3 strategy_journal.py record-signal --symbol BTC --bias bullish ...   # record a new signal
    python3 strategy_journal.py close-signal --id 5 --outcome hit_target ...    # close an open signal
    python3 strategy_journal.py performance                                      # show performance report
    python3 strategy_journal.py params-history                                   # show param change log
"""
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(SKILL_DIR, "strategy")
DB_PATH = os.path.join(DB_DIR, "journal.db")
PARAMS_PATH = os.path.join(DB_DIR, "params.json")
os.makedirs(DB_DIR, exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    bias TEXT NOT NULL,
    entry_price REAL,
    target_price REAL,
    stop_price REAL,
    confidence TEXT,
    score REAL,
    source TEXT DEFAULT 'briefing',
    batch_id TEXT,
    strategy_params_version INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    closed_at TEXT,
    outcome TEXT NOT NULL,
    exit_price REAL,
    pnl_pct REAL,
    duration_hours REAL,
    regime_at_close TEXT,
    exit_reason TEXT,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE TABLE IF NOT EXISTS params_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applied_at TEXT NOT NULL,
    trigger TEXT DEFAULT 'init',
    params_json TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at TEXT NOT NULL,
    period TEXT DEFAULT 'all_time',
    total_signals INTEGER DEFAULT 0,
    closed_signals INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    win_rate REAL,
    avg_pnl_pct REAL,
    avg_win_pct REAL,
    avg_loss_pct REAL,
    profit_factor REAL,
    avg_duration_hours REAL,
    best_symbol TEXT,
    worst_symbol TEXT,
    current_streak INTEGER DEFAULT 0,
    param_snapshot_id INTEGER
);

CREATE TABLE IF NOT EXISTS news_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    source TEXT,
    headline TEXT NOT NULL,
    url TEXT,
    sentiment TEXT,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_generated ON signals(generated_at);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal ON outcomes(signal_id);
CREATE INDEX IF NOT EXISTS idx_performance_period ON performance(period);
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def load_params() -> dict:
    """Load current strategy params from params.json."""
    if not os.path.exists(PARAMS_PATH):
        return _default_params()
    with open(PARAMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_params(params: dict, trigger: str = "manual", notes: str = ""):
    """Save params to file and record a history entry."""
    params["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)
    conn = get_conn()
    conn.execute(
        "INSERT INTO params_history (applied_at, trigger, params_json, notes) VALUES (?, ?, ?, ?)",
        (params["last_updated"], trigger, json.dumps(params), notes),
    )
    conn.commit()
    conn.close()


def _default_params() -> dict:
    return {
        "version": 1,
        "last_updated": None,
        "screening": {
            "min_mcap": 25_000_000,
            "min_24h_change_pct": 2.0,
            "score_threshold": 20.0,
            "score_mcap_boost_weight": 0.05,
            "max_candidates": 15,
            "max_opportunities": 2,
        },
        "risk": {
            "risk_per_trade_pct": 2.0,
            "stop_loss_pct": 3.5,
            "target_pct": 8.0,
            "max_open_positions": 3,
        },
        "dynamic_risk": {
            "enabled": True,
            "base_target_pct": 8.0,
            "base_stop_pct": 3.5,
            "min_target_pct": 5.0,
            "max_target_pct": 15.0,
            "min_stop_pct": 2.0,
            "max_stop_pct": 8.0,
            "trailing_stages": [[2.0, 1.0], [6.0, 2.0], [12.0, 3.0]],
        },
        "adaptation": {
            "enabled": True,
            "min_signals_before_adjust": 20,
            "win_rate_target": 0.55,
            "win_rate_minimum": 0.40,
            "max_consecutive_losses": 5,
            "tighten_multiplier": 1.3,
            "loosen_multiplier": 0.85,
        },
    }


def current_strategy_identity() -> dict:
    """Return {strategy_id, strategy_snapshot} for the active strategy.

    The ID encodes the params version + date so every signal/position
    can be traced back to the exact strategy that generated it.
    Reuses strategy_journal's own load_params to stay consistent.
    """
    params = load_params()
    version = params.get("version", 1)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    strategy_id = f"tok-v{version}-{date}"
    snapshot = {
        "screening": dict(params.get("screening", {})),
        "risk": dict(params.get("risk", {})),
    }
    return {"strategy_id": strategy_id, "strategy_snapshot": snapshot}


# Re-export from briefing so orchestrator doesn't import private functions cross-module
try:
    import importlib.util as _iiu
    _bp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "briefing.py")
    _bspec = _iiu.spec_from_file_location("_briefing_rexport", _bp)
    _bmod = _iiu.module_from_spec(_bspec)
    _bspec.loader.exec_module(_bmod)
    _fetch_coingecko_coin_list = _bmod._fetch_coingecko_coin_list
except Exception:
    def _fetch_coingecko_coin_list() -> dict:
        return {}


# ---------------------------------------------------------------------------
# Signal operations
# ---------------------------------------------------------------------------

def record_signal(symbol: str, name: str, bias: str, entry_price: float,
                  target_price: float = None, stop_price: float = None,
                  confidence: str = "medium", score: float = None,
                  source: str = "briefing", batch_id: str = None,
                  notes: str = "") -> int:
    """Record a new signal in the journal. Returns signal ID."""
    conn = get_conn()
    params = load_params()
    cur = conn.execute(
        """INSERT INTO signals
           (generated_at, symbol, name, bias, entry_price, target_price,
            stop_price, confidence, score, source, batch_id, strategy_params_version, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            symbol.upper(), name, bias.lower(), entry_price,
            target_price, stop_price, confidence.lower(),
            score, source, batch_id, params.get("version", 1), notes,
        ),
    )
    signal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return signal_id


def close_signal(signal_id: int, outcome: str, exit_price: float = None,
                 regime: str = "", reason: str = "", estimated_duration_h: float = None) -> dict:
    """Close a signal with its outcome. Returns the outcome record.
    
    If estimated_duration_h is provided (e.g., from backtesting), use it
    instead of computing wall-clock time from signal creation to now.
    """
    conn = get_conn()
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    if not row:
        conn.close()
        return {"error": f"Signal {signal_id} not found"}

    entry = row["entry_price"]
    pnl_pct = None
    if entry and exit_price and entry > 0:
        if row["bias"] == "bullish":
            pnl_pct = round((exit_price - entry) / entry * 100, 2)
        else:
            pnl_pct = round((entry - exit_price) / entry * 100, 2)

    if estimated_duration_h is not None:
        duration_h = round(estimated_duration_h, 1)
        closed = datetime.now(timezone.utc)
    else:
        opened = datetime.fromisoformat(row["generated_at"])
        closed = datetime.now(timezone.utc)
        duration_h = round((closed - opened).total_seconds() / 3600, 1)

    now_iso = closed.isoformat()
    conn.execute(
        """INSERT INTO outcomes
           (signal_id, closed_at, outcome, exit_price, pnl_pct, duration_hours, regime_at_close, exit_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (signal_id, now_iso, outcome, exit_price, pnl_pct, duration_h, regime, reason),
    )
    conn.commit()
    conn.close()

    return {
        "signal_id": signal_id,
        "symbol": row["symbol"],
        "bias": row["bias"],
        "entry": entry,
        "exit": exit_price,
        "outcome": outcome,
        "pnl_pct": pnl_pct,
        "duration_hours": duration_h,
    }


def get_open_signals() -> list[dict]:
    """Return all signals with no outcome recorded."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.* FROM signals s
           LEFT JOIN outcomes o ON s.id = o.signal_id
           WHERE o.id IS NULL
           ORDER BY s.generated_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_signals(limit: int = 100) -> list[dict]:
    """Return signals with their outcomes, most recent first."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.*, o.outcome, o.pnl_pct, o.closed_at, o.duration_hours, o.exit_reason
           FROM signals s
           LEFT JOIN outcomes o ON s.id = o.signal_id
           ORDER BY s.generated_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def signal_exists(symbol: str, entry_price: float, tolerance: float = 0.05) -> bool:
    """Check if any signal (open or closed) exists for symbol + entry within tolerance.

    Used by paper_trader._sync_closed_to_journal to prevent creating duplicate
    standalone signal+close entries when a position is re-closed at the same price
    (e.g. trailing-stop re-trigger after a portfolio reload bug).
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT 1 FROM signals s
           WHERE s.symbol = ?
           AND s.entry_price IS NOT NULL
           AND ABS(s.entry_price - ?) / MAX(ABS(s.entry_price), 0.001) < ?
           LIMIT 1""",
        (symbol, entry_price, tolerance),
    ).fetchone()
    conn.close()
    return row is not None


def get_loss_penalties(days: int = 14) -> dict:
    """Return {symbol: penalty_score} based on recency and severity of losses.

    Each loss contributes: penalty = min(abs(pnl_pct) * 2, 30) × recency_factor
    where recency_factor decays from 1.0 (today) to 0.0 (after `days` days).
    Total penalty per symbol is capped at 40.

    This lets the scoring system naturally deprioritize bad picks without
    hard-blocking — a coin with strong enough momentum can overcome its past.
    """
    conn = get_conn()
    from datetime import timedelta, datetime as _dt
    now = _dt.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT s.symbol, o.pnl_pct, o.closed_at
           FROM outcomes o
           JOIN signals s ON s.id = o.signal_id
           WHERE o.closed_at >= ?
           AND o.outcome = 'hit_stop'
           ORDER BY o.closed_at DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()

    penalties = {}
    for r in rows:
        sym = r["symbol"]
        pnl = abs(r["pnl_pct"] or 0)
        closed = r["closed_at"]
        try:
            closed_dt = _dt.fromisoformat(closed) if closed else now
        except Exception:
            closed_dt = now
        days_ago = max(0, (now - closed_dt).total_seconds() / 86400)
        recency = max(0, 1.0 - days_ago / days)
        per_loss = min(pnl * 2, 30) * recency
        penalties[sym] = min(penalties.get(sym, 0) + per_loss, 40)

    return penalties


def get_recent_winners(days: int = 30) -> set:
    """Return set of symbol names that won (hit_target, trailing_stop, or expired+pnl>0) in the last N days.

    Used by simple_rules() to give a small score boost to proven winners,
    creating a virtuous quality cycle without hard-blocking new coins.
    """
    conn = get_conn()
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT DISTINCT s.symbol
           FROM outcomes o
           JOIN signals s ON s.id = o.signal_id
           WHERE o.closed_at >= ?
           AND (o.outcome IN ('hit_target', 'trailing_stop')
                OR (o.outcome = 'expired' AND (o.pnl_pct IS NOT NULL AND o.pnl_pct > 0)))""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return {r["symbol"] for r in rows}


# ---------------------------------------------------------------------------
# Performance computation
# ---------------------------------------------------------------------------

def compute_performance(period: str = "all_time", exclude_sources=None) -> dict:
    """Compute performance metrics for a given period.

    Args:
        period: 'all_time', 'trailing_30d', 'trailing_7d'
        exclude_sources: list of signal sources to exclude (e.g., ['signal_validator']).
                        Defaults to excluding 'signal_validator' so live metrics
                        don't include backtest quality-gate data.
    """
    if exclude_sources is None:
        exclude_sources = ['signal_validator']

    conn = get_conn()

    if period == "all_time":
        cutoff = "1970-01-01"
    elif period == "trailing_30d":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    elif period == "trailing_7d":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    else:
        cutoff = "1970-01-01"

    # Build source exclusion clause
    placeholders = ','.join('?' for _ in exclude_sources)
    source_filter = f"AND s.source NOT IN ({placeholders})" if exclude_sources else ""

    # Closed signals with PnL in period
    rows = conn.execute(
        f"""SELECT s.symbol, s.bias, o.outcome, o.pnl_pct, o.duration_hours, s.source
           FROM outcomes o
           JOIN signals s ON s.id = o.signal_id
           WHERE s.generated_at >= ? {source_filter}""",
        (cutoff,) + tuple(exclude_sources),
    ).fetchall()

    total = len(rows)
    # Categorize outcomes:
    #   hit_target          → win
    #   trailing_stop       → win (locked-in profit)
    #   expired + pnl > 0   → win (expired in profit)
    #   expired + pnl <= 0  → loss
    #   hit_stop            → loss
    closed = [r for r in rows if r["outcome"] in ("hit_target", "hit_stop", "trailing_stop", "expired")]
    wins = [r for r in closed if r["outcome"] == "hit_target" or r["outcome"] == "trailing_stop" or 
            (r["outcome"] == "expired" and (r["pnl_pct"] or 0) > 0)]
    losses = [r for r in closed if r["outcome"] == "hit_stop" or 
              (r["outcome"] == "expired" and (r["pnl_pct"] or 0) <= 0)]

    win_count = len(wins)
    loss_count = len(losses)
    closed_count = len(closed)
    win_rate = round(win_count / closed_count, 4) if closed_count > 0 else 0.0

    all_pnl = [r["pnl_pct"] for r in closed if r["pnl_pct"] is not None]
    win_pnl = [r["pnl_pct"] for r in wins if r["pnl_pct"] is not None]
    loss_pnl = [r["pnl_pct"] for r in losses if r["pnl_pct"] is not None]

    avg_pnl = round(sum(all_pnl) / len(all_pnl), 2) if all_pnl else 0.0
    avg_win = round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0.0
    avg_loss = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0

    total_win = sum(win_pnl) if win_pnl else 0.0
    total_loss = abs(sum(loss_pnl)) if loss_pnl else 1.0
    profit_factor = round(total_win / total_loss, 2) if total_loss > 0 else 0.0

    durations = [r["duration_hours"] for r in closed if r["duration_hours"] is not None]
    avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0

    # Best/worst symbol
    sym_pnl = {}
    for r in closed:
        if r["pnl_pct"] is not None:
            sym = r["symbol"]
            sym_pnl.setdefault(sym, []).append(r["pnl_pct"])
    best_sym = max(sym_pnl, key=lambda s: sum(sym_pnl[s]) / len(sym_pnl[s])) if sym_pnl else ""
    worst_sym = min(sym_pnl, key=lambda s: sum(sym_pnl[s]) / len(sym_pnl[s])) if sym_pnl else ""

    # Current streak
    placeholders = ','.join('?' for _ in exclude_sources)
    source_filter = f"AND s.source NOT IN ({placeholders})" if exclude_sources else ""
    recent = conn.execute(
        f"""SELECT o.outcome, o.pnl_pct FROM outcomes o
           JOIN signals s ON s.id = o.signal_id
           WHERE s.generated_at >= ? {source_filter}
           ORDER BY o.closed_at DESC
           LIMIT 20""",
        (cutoff,) + tuple(exclude_sources),
    ).fetchall()
    streak = 0
    for r in recent:
        outcome = r["outcome"]
        pnl = r["pnl_pct"] or 0
        is_win = outcome in ("hit_target", "trailing_stop") or (outcome == "expired" and pnl > 0)
        is_loss = outcome == "hit_stop" or (outcome == "expired" and pnl <= 0)
        if is_win:
            streak = streak + 1 if streak >= 0 else 1
        elif is_loss:
            streak = streak - 1 if streak <= 0 else -1
        else:
            break

    perf = {
        "period": period,
        "total_signals": total,
        "closed_signals": closed_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "avg_pnl_pct": avg_pnl,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "avg_duration_hours": avg_dur,
        "best_symbol": best_sym,
        "worst_symbol": worst_sym,
        "current_streak": streak,
    }

    # Store snapshot
    params = load_params()
    conn.execute(
        """INSERT INTO performance
           (computed_at, period, total_signals, closed_signals, win_count, loss_count,
            win_rate, avg_pnl_pct, avg_win_pct, avg_loss_pct, profit_factor,
            avg_duration_hours, best_symbol, worst_symbol, current_streak)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            period, perf["total_signals"], perf["closed_signals"],
            perf["win_count"], perf["loss_count"], perf["win_rate"],
            perf["avg_pnl_pct"], perf["avg_win_pct"], perf["avg_loss_pct"],
            perf["profit_factor"], perf["avg_duration_hours"],
            perf["best_symbol"], perf["worst_symbol"], perf["current_streak"],
        ),
    )
    conn.commit()
    conn.close()

    return perf


# ---------------------------------------------------------------------------
# Parameter adaptation
# ---------------------------------------------------------------------------

def adapt_params() -> dict:
    """Check performance and adjust strategy parameters if needed.

    Rules:
    - If win_rate < minimum over min_signals: tighten (increase thresholds)
    - If win_rate > target over min_signals: loosen (decrease thresholds)
    - If consecutive losses > max: tighten aggressively
    """
    params = load_params()
    if not params.get("adaptation", {}).get("enabled", False):
        return {"adjusted": False, "reason": "adaptation_disabled"}

    adapt = params["adaptation"]
    screening = params["screening"]

    # Get trailing performance
    perf = compute_performance("trailing_30d")

    if perf["closed_signals"] < adapt.get("min_signals_before_adjust", 20):
        return {
            "adjusted": False,
            "reason": f"insufficient_data ({perf['closed_signals']}/{adapt['min_signals_before_adjust']})",
            "performance": perf,
        }

    adjustments = []
    win_rate = perf["win_rate"]
    target = adapt.get("win_rate_target", 0.55)
    minimum = adapt.get("win_rate_minimum", 0.40)
    tighten_mul = adapt.get("tighten_multiplier", 1.3)
    loosen_mul = adapt.get("loosen_multiplier", 0.85)

    # Check consecutive losses
    streak = perf["current_streak"]
    max_losses = adapt.get("max_consecutive_losses", 5)

    if streak <= -max_losses:
        # Loss streak — tighten aggressively
        screening["min_24h_change_pct"] = round(screening["min_24h_change_pct"] * tighten_mul, 1)
        screening["score_threshold"] = round(screening["score_threshold"] * tighten_mul, 1)
        adjustments.append(f"loss_streak({-streak}): tightened thresholds ×{tighten_mul}")
        trigger = "loss_streak"
    elif win_rate < minimum:
        # Below minimum — tighten
        screening["min_24h_change_pct"] = round(screening["min_24h_change_pct"] * tighten_mul, 1)
        screening["score_threshold"] = round(screening["score_threshold"] * tighten_mul, 1)
        adjustments.append(f"win_rate({win_rate:.0%}<{minimum:.0%}): tightened ×{tighten_mul}")
        trigger = "win_rate_below_min"
    elif win_rate > target:
        # Above target — can loosen
        screening["min_24h_change_pct"] = round(screening["min_24h_change_pct"] * loosen_mul, 1)
        screening["score_threshold"] = round(screening["score_threshold"] * loosen_mul, 1)
        adjustments.append(f"win_rate({win_rate:.0%}>{target:.0%}): loosened ×{loosen_mul}")
        trigger = "win_rate_above_target"
    else:
        return {
            "adjusted": False,
            "reason": f"within_range (WR={win_rate:.0%}, target={target:.0%})",
            "performance": perf,
        }

    # Clamp values to sensible ranges
    screening["min_24h_change_pct"] = max(1.0, min(15.0, screening["min_24h_change_pct"]))
    screening["score_threshold"] = max(10.0, min(80.0, screening["score_threshold"]))

    notes = "; ".join(adjustments)
    save_params(params, trigger=trigger, notes=notes)

    return {
        "adjusted": True,
        "trigger": trigger,
        "adjustments": adjustments,
        "params": {k: screening[k] for k in ("min_24h_change_pct", "score_threshold")},
        "performance": perf,
    }


# ---------------------------------------------------------------------------
# News operations
# ---------------------------------------------------------------------------

def cache_news(headlines: list[dict]):
    """Store fetched news headlines in the cache."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for h in headlines:
        conn.execute(
            "INSERT INTO news_cache (fetched_at, source, headline, url, sentiment, summary) VALUES (?, ?, ?, ?, ?, ?)",
            (now, h.get("source", ""), h.get("headline", ""),
             h.get("url", ""), h.get("sentiment", "neutral"), h.get("summary", "")),
        )
    conn.commit()
    conn.close()


def get_recent_news(limit: int = 10) -> list[dict]:
    """Return most recent cached news."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_table(rows: list[dict], cols: list[str]):
    """Simple formatted table output."""
    if not rows:
        print("(no data)")
        return
    widths = {c: max(len(c), max((len(str(r.get(c, ""))) for r in rows), default=0)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("─" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print("  ".join(str(r.get(c, "") or "").ljust(widths[c]) for c in cols))


def cmd_record_signal(args: list[str]):
    """record-signal --symbol BTC --bias bullish --entry 50000 ..."""
    kwargs = {}
    for i in range(0, len(args), 2):
        key = args[i].lstrip("-").replace("-", "_")
        val = args[i + 1] if i + 1 < len(args) else None
        if val is not None:
            try:
                val = float(val)
            except ValueError:
                pass
        kwargs[key] = val
    sid = record_signal(
        symbol=kwargs.get("symbol", "???"),
        name=kwargs.get("name", kwargs.get("symbol", "???")),
        bias=kwargs.get("bias", "bullish"),
        entry_price=kwargs.get("entry", 0),
        target_price=kwargs.get("target"),
        stop_price=kwargs.get("stop"),
        confidence=kwargs.get("confidence", "medium"),
        score=kwargs.get("score"),
        source=kwargs.get("source", "briefing"),
        batch_id=kwargs.get("batch_id"),
        notes=kwargs.get("notes", ""),
    )
    print(f"Signal #{sid} recorded.")


def cmd_close_signal(args: list[str]):
    """close-signal --id 5 --outcome hit_target --exit 52000"""
    kwargs = {}
    for i in range(0, len(args), 2):
        key = args[i].lstrip("-").replace("-", "_")
        val = args[i + 1] if i + 1 < len(args) else None
        if val is not None:
            try:
                val = float(val)
            except ValueError:
                pass
        kwargs[key] = val
    result = close_signal(
        signal_id=int(kwargs.get("id", 0)),
        outcome=kwargs.get("outcome", "unknown"),
        exit_price=kwargs.get("exit"),
        regime=kwargs.get("regime", ""),
        reason=kwargs.get("reason", "cli"),
    )
    if "error" in result:
        print(result["error"])
    else:
        pnl = result.get("pnl_pct")
        pnl_str = f"PnL: {pnl:+.2f}%" if pnl is not None else "PnL: N/A"
        print(f"Signal #{result['signal_id']} {result['symbol']}: {result['outcome']} | {pnl_str}")


def cmd_performance(args: list[str]):
    """performance [all_time|trailing_30d|trailing_7d]"""
    period = args[0] if args else "all_time"
    perf = compute_performance(period)
    print(f"\n{'=' * 50}")
    print(f"  Performance ({perf['period']})")
    print(f"{'=' * 50}")
    print(f"  Signals:     {perf['total_signals']} total / {perf['closed_signals']} closed")
    print(f"  Wins/Losses: {perf['win_count']} / {perf['loss_count']}")
    print(f"  Win Rate:    {perf['win_rate']:.1%}")
    print(f"  Avg PnL:     {perf['avg_pnl_pct']:+.2f}%")
    print(f"  Avg Win:     {perf['avg_win_pct']:+.2f}%")
    print(f"  Avg Loss:    {perf['avg_loss_pct']:+.2f}%")
    print(f"  Profit Factor: {perf['profit_factor']:.2f}")
    print(f"  Avg Duration:  {perf['avg_duration_hours']:.1f}h")
    print(f"  Best Symbol:   {perf['best_symbol']}")
    print(f"  Worst Symbol:  {perf['worst_symbol']}")
    print(f"  Streak:        {'+' if perf['current_streak'] >= 0 else ''}{perf['current_streak']}")
    print()


def cmd_signals(args: list[str]):
    """signals [limit]"""
    limit = int(args[0]) if args else 20
    signals = get_all_signals(limit)
    if not signals:
        print("No signals recorded.")
        return
    cols = ["id", "symbol", "bias", "entry_price", "target_price", "outcome", "pnl_pct"]
    for s in signals:
        s["entry_price"] = f"${s.get('entry_price', 0):.4f}" if s.get("entry_price") else "-"
        s["target_price"] = f"${s.get('target_price', 0):.4f}" if s.get("target_price") else "-"
        s["pnl_pct"] = f"{s.get('pnl_pct', 0):+.2f}%" if s.get("pnl_pct") is not None else "-"
        s["outcome"] = s.get("outcome") or "open"
    _print_table(signals, cols)


def cmd_params_history(args: list[str]):
    """params-history"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM params_history ORDER BY applied_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        print("No param changes recorded.")
        return
    for r in rows:
        d = dict(r)
        print(f"#{d['id']} [{d['applied_at'][:19]}] trigger={d['trigger']} | {d['notes']}")
        if d.get("params_json"):
            p = json.loads(d["params_json"])
            scr = p.get("screening", {})
            print(f"   screening: min_24h_change={scr.get('min_24h_change_pct')}% | score_threshold={scr.get('score_threshold')}")


def cmd_adapt(args: list[str]):
    """adapt — run auto-parameter adjustment"""
    result = adapt_params()
    if result["adjusted"]:
        print(f"✅ Adjusted: {'; '.join(result['adjustments'])}")
        print(f"   New params: {result['params']}")
    else:
        print(f"⏸  No adjustment needed: {result['reason']}")
    if "performance" in result:
        p = result["performance"]
        print(f"   Performance: WR={p['win_rate']:.1%} | {p['win_count']}W/{p['loss_count']}L | PF={p['profit_factor']}")


def cmd_news(args: list[str]):
    """news [limit]"""
    limit = int(args[0]) if args else 10
    news = get_recent_news(limit)
    if not news:
        print("No cached news.")
        return
    for n in news:
        sentiment_icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(n.get("sentiment", "neutral"), "⚪")
        print(f"{sentiment_icon} [{n.get('source', '?')}] {n.get('headline', '')}")


def main():
    init_db()
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    handlers = {
        "record-signal": cmd_record_signal,
        "close-signal": cmd_close_signal,
        "performance": cmd_performance,
        "signals": cmd_signals,
        "params-history": cmd_params_history,
        "adapt": cmd_adapt,
        "news": cmd_news,
        "init": lambda _: print("DB initialized."),
    }

    handler = handlers.get(cmd)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {cmd}")
        print("Available: record-signal, close-signal, performance, signals, params-history, adapt, news, init")


if __name__ == "__main__":
    main()
