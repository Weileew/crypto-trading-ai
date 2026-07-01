#!/usr/bin/env python3
"""Paper trading simulator for crypto recommendations."""
import os
import json
import re
import uuid
import time as _time_module
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(REPORTS_DIR, "paper_trading")
os.makedirs(PAPER_DIR, exist_ok=True)

# CoinGecko calls use the shared rate-limited getter from free_data
import importlib.util as _pt_ilu
_pt_fd_path = os.path.join(SKILL_DIR, "scripts", "free_data.py")
_pt_spec = _pt_ilu.spec_from_file_location("free_data_pt", _pt_fd_path)
_pt_mod = _pt_ilu.module_from_spec(_pt_spec)
_pt_spec.loader.exec_module(_pt_mod)
_get_cg = _pt_mod._get_cg
resolve_coin_id = _pt_mod.resolve_coin_id


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _current_strategy_identity():
    """Return {strategy_id, strategy_snapshot} from params.json.

    Generates a deterministic strategy ID from the params version + current date.
    Ensures every position knows which strategy version created it.
    Falls back to 'legacy' if params.json is missing.
    """
    params_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "strategy", "params.json"
    )
    try:
        with open(params_path) as f:
            params = json.load(f)
        version = params.get("version", 1)
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        strategy_id = f"tok-v{version}-{date}"
        snapshot = {
            "screening": dict(params.get("screening", {})),
            "risk": dict(params.get("risk", {})),
        }
    except Exception:
        strategy_id = "legacy"
        snapshot = {}
    return {"strategy_id": strategy_id, "strategy_snapshot": snapshot}


def _safe_price(price):
    """Safely convert a string to float, stripping common formatting artifacts.

    Handles:
      - Prefixes: "near 0.355", "~0.355", "around 0.355"
      - Suffixes: "0.3973 (+8%)", "0.355 (stop)", "0.3973 (+8"
      - Plain numbers: "0.355"
    """
    if price is None:
        return None
    s = str(price).strip()
    # Strip leading prefixes FIRST: "near", "~", "around", "above", "below"
    s = re.sub(r"^(near|~|around|above|below)\s*", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing parenthetical annotations: "(+8%)", "(stop)", etc.
    if "(" in s:
        s = s.split("(")[0].strip()
    # Strip trailing space-separated annotations last
    if " " in s:
        s = s.split(" ")[0].strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _safe_float(val):
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        return f
    except (TypeError, ValueError):
        return None


def portfolio_path():
    return os.path.join(PAPER_DIR, "portfolio.json")


def ledger_path():
    return os.path.join(PAPER_DIR, "ledger.json")


def load_portfolio():
    path = portfolio_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            portfolio = json.load(f)
        _normalize_legacy_positions_and_trades(portfolio, {})
        return portfolio
    return {
        "starting_capital": 10000.0,
        "cash": 10000.0,
        "positions": {},
        "last_updated": _utc_now(),
    }


def save_portfolio(portfolio):
    portfolio["last_updated"] = _utc_now()
    path = portfolio_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)
    return path


def load_ledger():
    path = ledger_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        _normalize_legacy_positions_and_trades({}, ledger)
        return ledger
    return {"trades": [], "last_updated": _utc_now()}


def save_ledger(ledger):
    ledger["last_updated"] = _utc_now()
    path = ledger_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    return path


def current_price_map(symbols):
    """Return a {symbol: price} map from CoinGecko for the requested symbols.

    Portfolio keys are uppercase symbols (e.g. 'VELVET', 'MAGMA').
    The function lowercases them and maps to CoinGecko internal IDs
    via resolve_coin_id before querying.
    """
    if not symbols:
        return {}
    # Build list of CG IDs, keeping track of original → CG ID mapping
    orig_to_cgid = {}
    cg_ids = []
    cg_ids_set = set()
    for s in symbols:
        label = (s or "").strip().lower()
        cg_id = resolve_coin_id(label)
        if cg_id and cg_id not in cg_ids_set:
            cg_ids_set.add(cg_id)
            cg_ids.append(cg_id)
            orig_to_cgid[s] = cg_id
    if not cg_ids:
        return {}
    data = _get_cg(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": ",".join(cg_ids), "vs_currencies": "usd"},
        timeout=20,
    )
    if not isinstance(data, dict):
        return {}
    # Reverse map: cg_id → original symbol (uppercase)
    cgid_to_orig = {v: k for k, v in orig_to_cgid.items()}
    out = {}
    for cg_id, payload in data.items():
        if not isinstance(payload, dict):
            continue
        p = payload.get("usd")
        if isinstance(p, (int, float)) and p > 0:
            orig_key = cgid_to_orig.get(cg_id, cg_id)
            out[orig_key] = float(p)
    return out


def parse_briefing_recommendations(text):
    """Extract buy bias recommendations from briefing markdown text.
    
    Handles both formats:
    1. Compact briefing: structured bullet fields (- Bias:, - Entry:, - Stop:, - Target:)
    2. Full briefing: single-line Alpha Candidates with pipe-separated fields
    """
    recs, current = [], {}
    lines = text.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            if current:
                recs.append(current)
                current = {}
            continue
        
        # Compact format: structured bullet fields
        if s.startswith("- Bias"):
            current["bias"] = s.split(":", 1)[-1].strip().lower()
            continue
        elif s.startswith("- Entry"):
            current["entry"] = s.split(":", 1)[-1].strip()
            continue
        elif s.startswith("- Stop"):
            current["stop"] = s.split(":", 1)[-1].strip()
            continue
        elif s.startswith("- Target"):
            current["target"] = s.split(":", 1)[-1].strip()
            continue
        elif s.startswith("- Research"):
            current["research"] = s.split(":", 1)[-1].strip()
            continue
        
        # Full briefing format: "1. Name (sym) | price=X | 24h=Y% | mcap_chg=Z% | score=... | ..."
        if re.match(r"^\d+\.\s+\S", s) and "|" in s and "price=" in s:
            if current:
                recs.append(current)
            # Parse the full briefing line
            parts = [p.strip() for p in s.split("|")]
            # First part: "1. Name (sym)"
            header = parts[0]
            name_match = re.match(r"^\d+\.\s+(.+?)\s*\((\w+)\)", header)
            if name_match:
                current = {"name": name_match.group(1).strip(), "symbol": name_match.group(2).strip()}
            else:
                # Fallback: just take everything after the number
                current = {"name": header.split(".", 1)[-1].strip()}
            # Parse pipe-separated fields
            for part in parts[1:]:
                if part.startswith("price="):
                    current["entry"] = part.replace("price=", "").strip()
                elif part.startswith("24h="):
                    current["change_24h"] = part.replace("24h=", "").strip()
                elif part.startswith("mcap_chg="):
                    current["mcap_chg"] = part.replace("mcap_chg=", "").strip()
                elif part.startswith("score="):
                    current["score"] = part.replace("score=", "").strip()
            # Full briefing doesn't have explicit bias/stop/target - use defaults
            # The bias can be inferred from the context or we set default
            current["bias"] = "bullish"  # Default for Alpha Candidates
            current["stop"] = "?"
            current["target"] = "?"
            continue
        
        # Compact format: numbered item without pipe separators (section header)
        if re.match(r"^\d+\.\s+\S", s) and not s.startswith("http"):
            if current:
                recs.append(current)
            current = {"name": s.split(".", 1)[-1].strip()}
            continue
    
    if current:
        recs.append(current)
    
    # Filter and normalise compound biases like "mean-reversion - bullish" -> "bullish"
    buy = []
    for r in recs:
        bias = (r.get("bias") or "").lower()
        if "bullish" in bias:
            bias = "bullish"
        elif "bearish" in bias:
            bias = "bearish"
        if bias not in {"buy bias", "buy", "bullish", "long", "accumulate"}:
            continue
        r["bias"] = bias
        buy.append(r)
    return buy

def recommended_symbols(recs):
    """Best-effort symbol extraction from recommendation names."""
    out = []
    for r in recs:
        name = r.get("name", "")
        candidate = name.split("(")[-1].split(")")[0].strip()
        if candidate:
            out.append(candidate.lower())
    return out


def open_position(portfolio, rec, executed_price, strategy_id=None, strategy_snapshot=None):
    symbol = recommended_symbols([rec])[0]
    if not symbol:
        return None
    if float(executed_price) <= 0:
        return None
    # Prevent overwriting an existing open position for the same symbol (case-insensitive)
    if any(existing_sym.upper() == symbol.upper() for existing_sym in (portfolio.get("positions") or {})):
        return None
    allocation = min(
        portfolio["cash"],
        max(portfolio["cash"] * 0.05, 10.0),
    )
    quantity = allocation / float(executed_price)
    if quantity <= 0:
        return None
    # Determine bias from the rec
    bias = (rec.get("bias") or "").lower()
    if bias not in ("bullish", "bearish"):
        bias = "bullish"  # default for legacy
    position = {
        "symbol": symbol,
        "name": rec.get("name"),
        "bias": bias,
        "trade_id": f"trade_{uuid.uuid4().hex[:10]}",
        "entry_price": round(float(executed_price), 8),
        "quantity": round(quantity, 8),
        "allocated": round(allocation, 2),
        "opened_at": _utc_now(),
        "stop": _safe_price(rec.get("stop")),
        "target": _safe_price(rec.get("target")),
        "status": "open",
        "current_price": round(float(executed_price), 8),
        "pnl_usd": 0.0,
        "pnl_pct": 0.0,
        "strategy_id": strategy_id or "legacy",
        "strategy_snapshot": strategy_snapshot or {},
        # Multi-stage trailing stop fields
        "highest_price": round(float(executed_price), 8) if bias == "bullish" else None,
        "lowest_price": round(float(executed_price), 8) if bias == "bearish" else None,
        "trailing_stop": None,
        "trailing_activated": False,
    }
    portfolio["cash"] = round(portfolio["cash"] - position["allocated"], 2)
    portfolio["positions"][symbol] = position
    return position


def close_position(portfolio, symbol, close_price, reason="manual"):
    pos = (portfolio.get("positions") or {}).get(symbol)
    if not pos:
        return None
    price = _safe_price(close_price)
    if price is None:
        return None
    proceeds = round(pos["quantity"] * price, 2)
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)
    pnl = round(proceeds - pos["allocated"], 2)
    pct = round((pnl / pos["allocated"]) * 100, 2) if pos["allocated"] else 0.0
    closed = {
        "trade_id": pos.get("trade_id"),
        "symbol": symbol,
        "name": pos.get("name"),
        "bias": pos.get("bias", "bullish"),
        "entry_price": pos.get("entry_price"),
        "exit_price": price,
        "quantity": pos["quantity"],
        "allocated": pos["allocated"],
        "opened_at": pos.get("opened_at"),
        "closed_at": _utc_now(),
        "pnl_usd": pnl,
        "pnl_pct": pct,
        "reason": reason,
    }
    del portfolio["positions"][symbol]
    return closed


def update_mark_to_market(portfolio):
    """Update positions to current prices. Closes positions that hit stop/target/trail.
    
    Returns a list of closed position dicts for journal syncing.
    """
    symbols = list((portfolio.get("positions") or {}).keys())
    prices = current_price_map(symbols)
    closed_positions = []
    for sym, pos in list((portfolio.get("positions") or {}).items()):
        price = prices.get(sym)
        if price is None:
            continue
        try:
            pos["current_price"] = round(price, 8)
            pos["pnl_usd"] = round(pos["quantity"] * pos["current_price"] - pos["allocated"], 2)
            pos["pnl_pct"] = round((pos["pnl_usd"] / pos["allocated"]) * 100, 2) if pos["allocated"] else 0.0
            # Fixed stop-loss / take-profit check
            stop_val = _safe_float(pos.get("stop"))
            target_val = _safe_float(pos.get("target"))
            if stop_val is not None and price <= stop_val:
                _closed = close_position(portfolio, sym, price, reason="stop-loss")
                if _closed:
                    closed_positions.append(_closed)
                continue
            elif target_val is not None and price >= target_val:
                _closed = close_position(portfolio, sym, price, reason="target-hit")
                if _closed:
                    closed_positions.append(_closed)
                continue
            # --- Multi-stage trailing stop ---
            bias = (pos.get("bias") or "bullish").lower()
            entry = _safe_float(pos.get("entry_price")) or 0

            # Load trailing stages from params.json (once per M2M tick)
            _trail_stages = [(2.0, 1.0), (6.0, 2.0), (12.0, 3.0)]
            try:
                _tp = json.loads(open(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "strategy", "params.json"
                )).read())
                _custom = _tp.get("dynamic_risk", {}).get("trailing_stages")
                if _custom and isinstance(_custom, list) and len(_custom) > 0:
                    _trail_stages = [(float(a), float(d)) for a, d in _custom]
            except Exception:
                pass

            def _trail_params(profit_pct):
                """Return (activation_threshold, trail_distance) for given profit level.
                Reads stages from params.json dynamic_risk.trailing_stages.
                Default: [[2,1], [6,2], [12,3]] — profit 2% → trail 1%, 6% → 2%, 12% → 3%.
                """
                act, dist = _trail_stages[0][0], _trail_stages[0][1]
                for a, d in _trail_stages:
                    if profit_pct >= a:
                        act, dist = a, d
                return act, dist

            if bias == "bullish" and entry > 0:
                highest = _safe_float(pos.get("highest_price")) or entry
                if price > highest:
                    pos["highest_price"] = round(price, 8)
                    highest = price
                profit_pct = ((price - entry) / entry) * 100
                act, dist = _trail_params(profit_pct)
                activated = pos.get("trailing_activated", False)
                if not activated and profit_pct >= act:
                    pos["trailing_stop"] = round(highest * (1 - dist / 100), 8)
                    pos["trailing_activated"] = True
                    activated = True
                elif activated:
                    _, dist = _trail_params(((pos.get("highest_price") or entry) - entry) / entry * 100)
                    if price > highest:
                        pos["trailing_stop"] = round(highest * (1 - dist / 100), 8)
                    trail_stop = _safe_float(pos.get("trailing_stop"))
                    if trail_stop is not None and price <= trail_stop:
                        _closed = close_position(portfolio, sym, price, reason="trailing_stop")
                        if _closed:
                            closed_positions.append(_closed)
                        continue
            elif bias == "bearish" and entry > 0:
                lowest = _safe_float(pos.get("lowest_price")) or entry
                if price < lowest:
                    pos["lowest_price"] = round(price, 8)
                    lowest = price
                profit_pct = ((entry - price) / entry) * 100
                act, dist = _trail_params(profit_pct)
                activated = pos.get("trailing_activated", False)
                if not activated and profit_pct >= act:
                    pos["trailing_stop"] = round(lowest * (1 + dist / 100), 8)
                    pos["trailing_activated"] = True
                elif activated:
                    _, dist = _trail_params(((entry - (pos.get("lowest_price") or entry)) / entry) * 100)
                    if price < lowest:
                        pos["trailing_stop"] = round(lowest * (1 + dist / 100), 8)
                    trail_stop = _safe_float(pos.get("trailing_stop"))
                    if trail_stop is not None and price >= trail_stop:
                        _closed = close_position(portfolio, sym, price, reason="trailing_stop")
                        if _closed:
                            closed_positions.append(_closed)
                        continue
        except Exception:
            continue  # skip malformed position rather than crashing the whole update
    return closed_positions


def _normalize_position(pos):
    if not isinstance(pos, dict):
        return pos
    out = {
        "symbol": pos.get("symbol") or pos.get("Symbol") or "",
        "name": pos.get("name") or pos.get("Name") or "",
        "quantity": float(
            pos.get("quantity")
            or pos.get("qty")
            or pos.get("Quantity")
            or 0.0
        ),
        "entry_price": float(
            pos.get("entry_price")
            or pos.get("avg_entry")
            or pos.get("entry")
            or pos.get("Entry")
            or 0.0
        ),
        "allocated": float(
            pos.get("allocated")
            or pos.get("allocation")
            or pos.get("Entry value")
            or 0.0
        ),
        "current_price": float(pos.get("current_price") or pos.get("price") or 0.0),
        "stop": pos.get("stop") or pos.get("stop_loss") or pos.get("Stop"),
        "target": pos.get("target") or pos.get("take_profit") or pos.get("Target"),
        "pnl_usd": float(pos.get("pnl_usd") or pos.get("P&L") or 0.0),
        "pnl_pct": float(pos.get("pnl_pct") or 0.0),
        "status": pos.get("status") or "open",
        "trade_id": pos.get("trade_id") or pos.get("Trade ID") or "",
        "opened_at": pos.get("opened_at") or pos.get("Opened At") or "",
        "strategy_id": pos.get("strategy_id") or "legacy",
        "strategy_snapshot": pos.get("strategy_snapshot") or {},
        # Trailing stop fields — preserve if set, default to None/False for legacy
        "bias": pos.get("bias") or "bullish",
        "highest_price": pos.get("highest_price"),
        "lowest_price": pos.get("lowest_price"),
        "trailing_stop": pos.get("trailing_stop"),
        "trailing_activated": pos.get("trailing_activated", False),
    }
    if not out["allocated"] and out["entry_price"] and out["quantity"]:
        out["allocated"] = round(out["quantity"] * out["entry_price"], 2)
    return out


def _migrate_legacy_schema(obj):
    """Best-effort normalization for inline schema drift."""
    if isinstance(obj, dict):
        positions = obj.get("positions")
        if isinstance(positions, dict):
            for key, value in list(positions.items()):
                positions[key] = _normalize_position(value)
        trades = obj.get("trades")
        if isinstance(trades, list):
            obj["trades"] = [
                {
                    **trade,
                    "side": trade.get("side") or trade.get("Side") or "buy",
                    "qty": float(
                        trade.get("qty")
                        or trade.get("quantity")
                        or trade.get("Qty")
                        or 0.0
                    ),
                    "entry_price": float(
                        trade.get("entry_price")
                        or trade.get("avg_entry")
                        or trade.get("entry")
                        or trade.get("Entry")
                        or 0.0
                    ),
                }
                for trade in trades
                if isinstance(trade, dict)
            ]


def _normalize_legacy_positions_and_trades(portfolio, ledger):
    if isinstance(portfolio, dict):
        _migrate_legacy_schema(portfolio)
    if isinstance(ledger, dict):
        _migrate_legacy_schema(ledger)


def open_today(portfolio, text):
    recs = parse_briefing_recommendations(text)
    prices = current_price_map(recommended_symbols(recs))
    si = _current_strategy_identity()
    executed = []
    for rec in recs:
        syms = recommended_symbols([rec])
        sym = (syms or [""])[0]
        price = prices.get(sym)
        if not sym or price is None:
            continue
        pos = open_position(portfolio, rec, price,
                            strategy_id=si["strategy_id"],
                            strategy_snapshot=si["strategy_snapshot"])
        if pos:
            executed.append(pos)
    return executed



def summary(portfolio):
    positions = list((portfolio.get("positions") or {}).values())
    unrealised = 0.0
    winners = 0
    losers = 0
    for pos in positions:
        unrealised += pos.get("pnl_usd") or 0.0
        if pos.get("pnl_pct", 0) > 0:
            winners += 1
        elif pos.get("pnl_pct", 0) < 0:
            losers += 1
    equity = round(portfolio.get("cash", 0.0) + sum((p.get("current_price") or 0.0) * (p.get("quantity") or 0.0) for p in positions), 2)
    starting = round(portfolio.get("starting_capital", 0.0), 2)
    return_pct = ((equity - starting) / starting * 100) if starting else 0.0
    open_count = len(positions)
    return {
        "starting_capital": starting,
        "cash": round(portfolio.get("cash", 0.0), 2),
        "open_positions": open_count,
        "equity": round(equity, 2),
        "return_pct": round(return_pct, 2),
        "unrealised_pnl_usd": round(unrealised, 2),
        "unrealised_winners": winners,
        "unrealised_losers": losers,
    }


def format_summary(portfolio, ledger):
    s = summary(portfolio)
    positions = list((portfolio.get("positions") or {}).values())

    # Group positions by strategy_id for per-strategy P&L
    by_strategy = {}
    for pos in positions:
        sid = pos.get("strategy_id", "legacy")
        by_strategy.setdefault(sid, []).append(pos)

    lines = [
        "# Paper Trading",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Starting capital | {s['starting_capital']} |",
        f"| Cash | {s['cash']} |",
        f"| Equity | {s['equity']} |",
        f"| Return | {s['return_pct']}% |",
        "",
        "| Strategy | Positions | P&L |",
        "| --- | --- | --- |",
    ]
    for sid, plist in sorted(by_strategy.items()):
        pnl = sum(p.get("pnl_usd") or 0.0 for p in plist)
        lines.append(f"| {sid} | {len(plist)} | ${pnl:+.2f} |")

    lines += [
        "",
        "| Symbol | Strategy | Entry | Current | P&L % | Trail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for pos in positions:
        sid = pos.get("strategy_id", "legacy")
        # Trailing stop status
        ts_active = pos.get("trailing_activated", False)
        ts_price = pos.get("trailing_stop")
        if ts_active and ts_price:
            trail_status = f"🔒 ${ts_price}"
        elif ts_active:
            trail_status = "🔒 active"
        else:
            trail_status = ""
        lines.append(
            f"| {pos.get('symbol','')} | {sid} | {pos.get('entry_price','')} | {pos.get('current_price','')} | {pos.get('pnl_pct','')}% | {trail_status} |"
        )
    closed = [t for t in (ledger.get("trades") or []) if t.get("status") in ("closed", "exit") or t.get("closed_at")]
    recent_closed = closed[-10:]
    lines += ["", "| Recent closed trades |", "| --- | --- | --- | --- |"]
    shown = 0
    for trade in recent_closed:
        closed_at = (trade.get("closed_at") or "")[:19].replace("T", " ")
        pnl_pct = trade.get("pnl_pct")
        reason = trade.get("outcome") or trade.get("exit_reason") or trade.get("reason") or ""
        if pnl_pct is not None:
            pnl_s = f"{pnl_pct:+.2f}%"
        else:
            pnl_fallback = trade.get("pnl") or trade.get("pnl_usd") or trade.get("P&L")
            pnl_s = f"{pnl_fallback:+.2f}%" if isinstance(pnl_fallback, (int, float)) else (str(pnl_fallback) if pnl_fallback is not None else "N/A")
        entry = trade.get("entry_price") or trade.get("avg_entry") or trade.get("entry") or "N/A"
        exit_price = trade.get("exit_price") or trade.get("Exit") or "N/A"
        lines.append(
            f"| {closed_at} | {trade.get('symbol', '?')} | entry={entry} | exit={exit_price} | {pnl_s} | {reason} |"
        )
        shown += 1
    # Fallback: if ledger has no recent closed trades, pull from journal.db outcomes
    if shown == 0:
        try:
            import importlib.util as _iu
            _jp = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "scripts", "strategy_journal.py"
            )
            if os.path.exists(_jp):
                _spec = _iu.spec_from_file_location("_sj_fb", _jp)
                _mod = _iu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _mod.init_db()
                rows = _mod.get_conn().execute(
                    "SELECT o.closed_at, o.outcome, o.exit_price, o.pnl_pct, o.exit_reason, o.regime_at_close, s.symbol "
                    "FROM outcomes o JOIN signals s ON s.id=o.signal_id ORDER BY o.id DESC LIMIT ?",
                    (10,),
                ).fetchall()
                for r in rows:
                    pnl_s = f"{r[3]:+.2f}%" if isinstance(r[3], (int, float)) else "N/A"
                    lines.append(
                        f"| {(r[0] or '')[:19].replace('T', ' ')} | {r[6] or '?'} | entry= | exit={r[2] if r[2] is not None else ''} | {pnl_s} | {r[4] or r[1] or ''} |"
                    )
                shown = len(rows)
        except Exception:
            pass
    if shown == 0:
        lines.append("| — | — | — | — | — | — |")
    return "\n".join(lines)


def save_summary(portfolio, ledger):
    txt = format_summary(portfolio, ledger)
    path = os.path.join(PAPER_DIR, f"summary_{_utc_today()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    return path


def _sync_closed_to_journal(closed_positions):
    """Record closed positions in the strategy journal.
    
    For each closed position, tries to match an open signal in the journal
    by symbol + entry price (±5%). If matched, closes it. Otherwise records
    a standalone outcome.
    """
    if not closed_positions:
        return 0
    try:
        import importlib.util as _iu
        _jp = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "strategy_journal.py"
        )
        if not os.path.exists(_jp):
            return 0
        _spec = _iu.spec_from_file_location("_sj", _jp)
        _mod = _iu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.init_db()
    except Exception:
        return 0
    
    synced = 0
    for cp in closed_positions:
        sym = (cp.get("symbol") or "").upper()
        entry = _safe_float(cp.get("entry_price")) or 0
        exit_price = _safe_float(cp.get("exit_price")) or 0
        pnl = _safe_float(cp.get("pnl_pct")) or 0
        reason = cp.get("reason", "manual")
        bias = cp.get("bias", "bullish")
        
        # Map reason to journal outcome
        outcome_map = {
            "stop-loss": "hit_stop",
            "target-hit": "hit_target",
            "trailing_stop": "trailing_stop",
            "manual": "manual_close",
        }
        outcome = outcome_map.get(reason, "expired")
        
        # Try to match an open signal in the journal
        try:
            open_signals = _mod.get_open_signals()
            matched = [s for s in open_signals 
                       if s["symbol"] == sym 
                       and abs((s.get("entry_price") or 0) - entry) / max(entry, 1) < 0.05]
            if matched:
                _mod.close_signal(
                    signal_id=matched[0]["id"],
                    outcome=outcome,
                    exit_price=exit_price,
                    regime="paper_trader_m2m",
                    reason=reason,
                )
            else:
                # Guard: skip if a signal for this symbol+entry already exists
                # (prevents phantom duplicates from portfolio-reload bugs)
                if _mod.signal_exists(sym, entry):
                    synced += 1
                    continue
                # Record standalone
                sid = _mod.record_signal(
                    symbol=sym, name=cp.get("name", sym), bias=bias,
                    entry_price=entry, target_price=None, stop_price=None,
                    confidence="medium", score=None,
                    source="paper_trader", batch_id=f"m2m_{_utc_today()}",
                    notes=f"Auto-closed via {reason}: PnL={pnl}%",
                )
                _mod.close_signal(
                    signal_id=sid, outcome=outcome, exit_price=exit_price,
                    regime="paper_trader_m2m", reason=reason,
                )
            synced += 1
        except Exception:
            continue
    return synced


def _sync_closed_to_ledger(ledger, closed_positions):
    """Update ledger entries with close info for any positions that were closed."""
    if not closed_positions:
        return
    for cp in closed_positions:
        tid = cp.get("trade_id")
        if not tid:
            continue
        for t in (ledger.get("trades") or []):
            if t.get("trade_id") == tid and t.get("status") in ("opened", None):
                t["status"] = "closed"
                t["closed_at"] = cp.get("closed_at", _utc_now())
                t["exit_price"] = cp.get("exit_price")
                t["pnl_usd"] = cp.get("pnl_usd")
                t["pnl_pct"] = cp.get("pnl_pct")
                t["exit_reason"] = cp.get("reason", "manual")
                break


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--briefing", default=None)
    p.add_argument("--open-today", action="store_true")
    p.add_argument("--paper-open", action="store_true")
    p.add_argument("--update", action="store_true")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()

    portfolio = load_portfolio()
    ledger = load_ledger()

    briefing_text = ""
    if args.briefing and os.path.exists(args.briefing):
        with open(args.briefing, "r", encoding="utf-8") as f:
            briefing_text = f.read()

    if args.update:
        closed = update_mark_to_market(portfolio)
        synced = _sync_closed_to_journal(closed)
        _sync_closed_to_ledger(ledger, closed)
        save_portfolio(portfolio)
        save_ledger(ledger)
        if synced:
            print(f"  Journal: synced {synced} closed position(s)")

    if args.paper_open:
        executed = open_today(portfolio, briefing_text)
        for pos in executed:
            ledger["trades"].append(
                {
                    "trade_id": pos.get("trade_id"),
                    "date": _utc_today(),
                    "symbol": pos.get("symbol"),
                    "name": pos.get("name"),
                    "side": "buy",
                    "type": "open",
                    "entry_price": pos.get("entry_price"),
                    "quantity": pos.get("quantity"),
                    "allocated": pos.get("allocated"),
                    "stop": pos.get("stop"),
                    "target": pos.get("target"),
                    "status": "opened",
                    "opened_at": pos.get("opened_at"),
                    "closed_at": None,
                    "exit_price": None,
                    "pnl_usd": None,
                    "pnl_pct": None,
                    "notes": f"Opening recommended setup from briefing {_utc_today()}",
                }
            )
        save_portfolio(portfolio)
        save_ledger(ledger)
        print(format_summary(portfolio, ledger))
        return

    if args.summary:
        print(format_summary(portfolio, ledger))
        return

    # Default: update + summary
    closed = update_mark_to_market(portfolio)
    synced = _sync_closed_to_journal(closed)
    _sync_closed_to_ledger(ledger, closed)
    save_portfolio(portfolio)
    save_ledger(ledger)
    if synced:
        print(f"  Journal: synced {synced} closed position(s)")
    print(format_summary(portfolio, ledger))


def open_today_from_briefing(briefing_path):
    portfolio = load_portfolio()
    ledger = load_ledger()
    _normalize_legacy_positions_and_trades(portfolio, ledger)
    if not os.path.exists(briefing_path):
        return []
    with open(briefing_path, "r", encoding="utf-8") as f:
        text = f.read()
    executed = open_today(portfolio, text)
    if executed:
        for pos in executed:
            ledger["trades"].append(
                {
                    "trade_id": pos.get("trade_id"),
                    "date": _utc_today(),
                    "symbol": pos.get("symbol"),
                    "name": pos.get("name"),
                    "side": "buy",
                    "type": "open",
                    "entry_price": pos.get("entry_price"),
                    "quantity": pos.get("quantity"),
                    "allocated": pos.get("allocated"),
                    "stop": pos.get("stop"),
                    "target": pos.get("target"),
                    "status": "opened",
                    "opened_at": pos.get("opened_at"),
                    "closed_at": None,
                    "exit_price": None,
                    "pnl_usd": None,
                    "pnl_pct": None,
                    "notes": f"Opening recommended setup from briefing {_utc_today()}",
                }
            )
    save_portfolio(portfolio)
    save_ledger(ledger)
    return executed


if __name__ == "__main__":
    main()
