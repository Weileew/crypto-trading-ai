#!/usr/bin/env python3
"""
paper_executor.py

Parse today’s daily briefing and open paper trades directly into the existing
reports/paper_trading/ledger.json + portfolio.json, then refresh market values
via paper_trader.py --update --summary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = SKILL_DIR / "reports"
PAPER_DIR = REPORTS_DIR / "paper_trading"
LEDGER_PATH = PAPER_DIR / "ledger.json"
PORTFOLIO_PATH = PAPER_DIR / "portfolio.json"
os.makedirs(PAPER_DIR, exist_ok=True)

# CoinGecko price fetching via free_data (shared rate-limited getter)
import importlib.util as _pe_ilu
_pe_fd_path = SKILL_DIR / "scripts" / "free_data.py"
if _pe_fd_path.exists():
    _pe_spec = _pe_ilu.spec_from_file_location("free_data_pe", str(_pe_fd_path))
    _pe_mod = _pe_ilu.module_from_spec(_pe_spec)
    _pe_spec.loader.exec_module(_pe_mod)
    _get_cg = _pe_mod._get_cg
    resolve_coin_id = _pe_mod.resolve_coin_id
    _HAS_LIVE_PRICES = True
else:
    _get_cg = None
    resolve_coin_id = None
    _HAS_LIVE_PRICES = False


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# briefing parsing
# ---------------------------------------------------------------------------
def load_briefing(date: str) -> str | None:
    path = REPORTS_DIR / f"daily_briefing_{date}.md"
    if not path.exists():
        print(f"No briefing found for {date}: {path}", file=sys.stderr)
        return None
    return path.read_text(encoding="utf-8")


def _canonical_bias(bias: str) -> str:
    s = (bias or "").strip().lower()
    if s in {"buy bias", "bullish", "long", "accumulate", "buy"}:
        return s
    # Handle compound bias strings like "mean-reversion - bullish"
    if "bullish" in s:
        return "bullish"
    if "bearish" in s:
        return "bearish"
    return s


def parse_recommendations(text: str):
    recs = []
    current = {}
    lines = text.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            if current:
                recs.append(current)
                current = {}
            continue
        if s.startswith("## ") or s.startswith("- Confidence") or s.startswith("- Why") or s.startswith("- Liquidity"):
            continue
        if re.match(r"^\d+\.\s+\S", s) and not s.startswith("http"):
            if current:
                recs.append(current)
            current = {"name": s.split(".", 1)[-1].strip()}
            continue
        if s.startswith("- Bias"):
            current["bias"] = _canonical_bias(s.split(":", 1)[-1])
        elif s.startswith("- Entry"):
            current["entry"] = s.split(":", 1)[-1].strip()
        elif s.startswith("- Stop"):
            current["stop"] = s.split(":", 1)[-1].strip()
        elif s.startswith("- Target"):
            current["target"] = s.split(":", 1)[-1].strip()
    if current:
        recs.append(current)

    buy = []
    for r in recs:
        bias = r.get("bias") or ""
        if bias not in {"buy bias", "bullish", "long", "accumulate", "buy"}:
            continue
        entry = r.get("entry")
        stop = r.get("stop")
        target = r.get("target")
        if not (entry and stop and target):
            continue
        m = re.search(r"\(([^)]+)\)", r.get("name", ""))
        if m:
            symbol = m.group(1).strip().upper()
        else:
            symbol = r.get("name", "").strip().split()[-1].upper()
        buy.append({"symbol": symbol, "name": r.get("name"), "bias": r.get("bias"), "entry": entry, "stop": stop, "target": target})
    return buy


def parse_price(v) -> float | None:
    if not v:
        return None
    s = str(v).replace("%", "").strip()
    s = re.sub(r"^(near|~|around|above|below)\s*", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing parenthetical annotations: "(+8%)", "(stop)", etc.
    if "(" in s:
        s = s.split("(")[0].strip()
    # Strip trailing space-separated annotations
    if " " in s:
        s = s.split(" ")[0].strip()
    try:
        return float(s)
    except ValueError:
        return None


def fetch_live_prices(symbols):
    """Fetch current prices from CoinGecko for a list of symbol names.

    Returns {uppercase_symbol: price} mapping. Falls back to empty dict
    if free_data is unavailable or the API call fails.
    """
    if not _HAS_LIVE_PRICES or not symbols:
        return {}
    cg_ids = []
    sym_to_cg = {}
    for s in symbols:
        label = (s or "").strip().lower()
        cg_id = resolve_coin_id(label)
        if cg_id and cg_id not in sym_to_cg:
            sym_to_cg[cg_id] = s.upper()
            cg_ids.append(cg_id)
    if not cg_ids:
        return {}
    data = _get_cg(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": ",".join(cg_ids), "vs_currencies": "usd"},
        timeout=20,
    )
    if not isinstance(data, dict):
        return {}
    out = {}
    for cg_id, payload in data.items():
        if not isinstance(payload, dict):
            continue
        p = payload.get("usd")
        if isinstance(p, (int, float)) and p > 0:
            orig_sym = sym_to_cg.get(cg_id)
            if orig_sym:
                out[orig_sym] = float(p)
    return out


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
RISK_PER_TRADE = 0.02      # fraction of cash per trade
MAX_POSITIONS = 5

# ---------------------------------------------------------------------------
# ledger + portfolio mutation
# ---------------------------------------------------------------------------
def open_trades(date: str, recs):
    ledger = _load_json(LEDGER_PATH, {"trades": [], "last_updated": _now()})
    portfolio = _load_json(PORTFOLIO_PATH, {"starting_capital": 10000.0, "cash": 10000.0, "positions": {}, "last_updated": _now()})

    opened = 0
    skipped = 0
    detail = []
    existing_keys = {
        (t.get("date"), t.get("symbol")) for t in ledger.get("trades", []) if t.get("status") == "opened"
    }
    # Also check portfolio for any open position with the same symbol (cross-day dedup)
    portfolio_open_symbols = {
        s.upper() for s in (portfolio.get("positions") or {}).keys()
    }

    # Fetch live prices once for all recommended symbols
    rec_symbols = [r.get("symbol") for r in recs if r.get("symbol")]
    live_prices = fetch_live_prices(rec_symbols)

    for rec in recs:
        rec_entry = parse_price(rec.get("entry"))
        rec_stop = parse_price(rec.get("stop"))
        rec_target = parse_price(rec.get("target"))
        if rec_entry is None or rec_stop is None or rec_target is None:
            skipped += 1
            detail.append({"symbol": rec["symbol"], "status": "skipped", "reason": "invalid_price"})
            continue
        key = (date, rec["symbol"])
        if key in existing_keys:
            skipped += 1
            detail.append({"symbol": rec["symbol"], "status": "skipped", "reason": "already_open_today"})
            continue
        # Prevent opening a second position in the same symbol while one is still open
        if rec["symbol"].upper() in portfolio_open_symbols:
            skipped += 1
            detail.append({"symbol": rec["symbol"], "status": "skipped", "reason": "position_already_open_in_portfolio"})
            continue

        # Use live market price as entry, adjust stop/target proportionally
        live_price = live_prices.get(rec["symbol"].upper())
        if live_price is not None and live_price > 0 and rec_entry > 0:
            ratio = live_price / rec_entry
            entry = round(live_price, 8)
            stop = round(rec_stop * ratio, 8)
            target = round(rec_target * ratio, 8)
        else:
            entry = rec_entry
            stop = rec_stop
            target = rec_target

        risk_amount = portfolio.get("cash", 0.0) * RISK_PER_TRADE
        risk_amount = max(risk_amount, 10.0)
        risk_amount = min(risk_amount, portfolio.get("cash", 0.0))
        qty = risk_amount / entry
        if qty <= 0:
            skipped += 1
            detail.append({"symbol": rec["symbol"], "status": "skipped", "reason": "zero_qty"})
            continue
        cost = round(entry * qty, 2)
        if cost > portfolio.get("cash", 0.0):
            skipped += 1
            detail.append({"symbol": rec["symbol"], "status": "skipped", "reason": "insufficient_cash"})
            continue

        now_ts = _now()
        bias = (rec.get("bias") or "bullish").lower()
        if bias not in ("bullish", "bearish"):
            bias = "bullish"
        trade = {
            "trade_id": f"trade_{uuid.uuid4().hex[:10]}",
            "date": date,
            "opened_at": now_ts,
            "symbol": rec["symbol"],
            "name": rec.get("name", ""),
            "side": "buy",
            "type": "open",
            "quantity": qty,
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": target,
            "status": "opened",
            "closed_at": None,
            "exit_price": None,
            "pnl_usd": None,
            "pnl_pct": None,
            "validation_status": "pending",
            "notes": f"Opening recommended setup from briefing {date}",
        }
        ledger.setdefault("trades", []).append(trade)
        portfolio["cash"] = round(portfolio.get("cash", 10000.0) - entry * qty, 6)
        positions = portfolio.setdefault("positions", {})
        sym_key = rec["symbol"].upper()
        positions[sym_key] = {
            "symbol": rec["symbol"],
            "name": rec.get("name", ""),
            "bias": bias,
            "quantity": qty,
            "entry_price": entry,
            "current_price": entry,
            "stop_loss": stop,
            "take_profit": target,
            "pnl_usd": 0.0,
            "pnl_pct": 0.0,
            "trade_id": trade["trade_id"],
            "opened_at": now_ts,
            # Multi-stage trailing stop fields
            "highest_price": round(entry, 8) if bias == "bullish" else None,
            "lowest_price": round(entry, 8) if bias == "bearish" else None,
            "trailing_stop": None,
            "trailing_activated": False,
        }
        opened += 1
        detail.append({"symbol": rec["symbol"], "status": "opened", "trade_id": trade["trade_id"]})

    _save_json(PORTFOLIO_PATH, portfolio)
    _save_json(LEDGER_PATH, ledger)
    return {"date": date, "opened": opened, "skipped": skipped, "detail": detail}


# ---------------------------------------------------------------------------
# refresh mark-to-market
# ---------------------------------------------------------------------------
def refresh_m2m() -> dict:
    cp = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "paper_trader.py"), "--update", "--summary"],
        cwd=str(SKILL_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    return {"exit_code": cp.returncode, "stdout": cp.stdout[-600:], "stderr": cp.stderr[-600:]}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    args = ap.parse_args()

    text = load_briefing(args.date)
    if text is None:
        sys.exit(2)

    recs = parse_recommendations(text)
    if not recs:
        print(json.dumps({"date": args.date, "opened": 0, "skipped": 0, "detail": [], "refresh": refresh_m2m()}))
        return

    result = open_trades(args.date, recs)
    result["refresh"] = refresh_m2m()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
