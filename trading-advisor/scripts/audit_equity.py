#!/usr/bin/env python3
"""Audit paper trading equity history from ledger, portfolio, and journal."""
import json, sqlite3, os
from datetime import datetime, timezone
from collections import defaultdict

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(REPORTS_DIR, "paper_trading")
DB = os.path.join(SKILL_DIR, "strategy", "journal.db")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_val(v, default="N/A"):
    if v is None:
        return default
    if isinstance(v, float):
        return round(v, 2)
    return v


def main():
    portfolio = load_json(os.path.join(PAPER_DIR, "portfolio.json"))
    ledger = load_json(os.path.join(PAPER_DIR, "ledger.json"))
    trades = ledger.get("trades") or []
    closed = [t for t in trades if t.get("closed_at") or t.get("status") in ("closed", "exit")]
    open_trades = [t for t in trades if not t.get("closed_at") and t.get("status") not in ("closed", "exit")]

    # Reconstruct realized P&L from closed trades
    open_pos_map = portfolio.get("positions") or {}
    starting = portfolio.get("starting_capital", 10000.0)
    cash = portfolio.get("cash", starting)

    lines = []
    lines.append("# Paper Trading Equity Audit")
    lines.append("")
    lines.append(f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"- Starting capital: {fmt_val(starting)}")
    lines.append(f"- Cash: {fmt_val(cash)}")
    lines.append(f"- Open positions: {len(open_pos_map)}")
    lines.append("")

    # Closed trades detail
    lines.append("## Closed trades")
    lines.append("")
    lines.append("| Date | Symbol | Side | Entry | Exit | P&L % | Reason |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    realized_total_pct = []
    for t in closed:
        closed_at = (t.get("closed_at") or "")[:19].replace("T", " ")
        symbol = t.get("symbol", "?")
        side = t.get("side", "buy")
        entry = t.get("entry_price") or t.get("avg_entry") or t.get("entry") or "N/A"
        exit_price = t.get("exit_price") or t.get("Exit") or "N/A"
        pnl = t.get("pnl") or t.get("pnl_usd") or t.get("P&L") or t.get("pnl_pct")
        reason = t.get("outcome") or t.get("exit_reason") or t.get("reason") or "unknown"
        if pnl is None:
            pnl = "N/A"
        elif isinstance(pnl, (int, float)):
            pnl = f"{pnl:+.2f}%"
            try:
                realized_total_pct.append(float(pnl.replace('%','').replace('+','')))
            except Exception:
                pass
        else:
            pnl = str(pnl)
        lines.append(f"| {closed_at} | {symbol} | {side} | {fmt_val(entry)} | {fmt_val(exit_price)} | {pnl} | {reason} |")

    if not closed:
        lines.append("_No closed trades yet._")

    # Outcomes from journal DB
    lines.append("")
    lines.append("## Journal outcomes")
    lines.append("")
    if os.path.exists(DB):
        try:
            con = sqlite3.connect(DB)
            cur = con.cursor()
            rows = cur.execute(
                "SELECT o.closed_at, o.outcome, o.exit_price, o.pnl_pct, o.exit_reason, o.regime_at_close, s.symbol FROM outcomes o JOIN signals s ON s.id=o.signal_id ORDER BY o.closed_at DESC LIMIT 20"
            ).fetchall()
            if rows:
                lines.append("| Closed At | Symbol | Outcome | Exit Price | P&L % | Reason | Regime |")
                lines.append("| --- | --- | --- | --- | --- | --- | --- |")
                for r in rows:
                    closed_at = (r[0] or "")[:19].replace("T", " ")
                    pnl = f"{r[3]:+.2f}%" if isinstance(r[3], (int, float)) else "N/A"
                    lines.append(f"| {closed_at} | {r[6]} | {r[1]} | {fmt_val(r[2])} | {pnl} | {r[5] or ''} | {r[6]} |")
            else:
                lines.append("_No outcomes recorded yet._")
        except Exception as e:
            lines.append(f"_Journal DB error: {e}_")
    else:
        lines.append("_Journal DB not found._")

    # Open positions detail
    lines.append("")
    lines.append("## Open positions")
    lines.append("")
    if open_pos_map:
        lines.append("| Symbol | Entry | Qty | Current | P&L % | Stop | Target | Trail |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for sym, pos in open_pos_map.items():
            entry = pos.get("entry_price")
            qty = pos.get("quantity")
            curr = pos.get("current_price")
            pnl = pos.get("pnl_pct")
            stop = pos.get("stop") or pos.get("stop_loss")
            target = pos.get("target") or pos.get("take_profit")
            trail = ""
            if pos.get("trailing_activated"):
                trail = f"🔒 {fmt_val(pos.get('trailing_stop'))}"
            lines.append(f"| {sym} | {fmt_val(entry)} | {fmt_val(qty)} | {fmt_val(curr)} | {fmt_val(pnl)}% | {fmt_val(stop)} | {fmt_val(target)} | {trail} |")
    else:
        lines.append("_No open positions._")

    # Equity estimate
    lines.append("")
    lines.append("## Equity sanity check")
    lines.append("")
    unrealized = sum(
        (p.get("current_price") or 0.0) * (p.get("quantity") or 0.0) - (p.get("allocated") or 0.0)
        for p in open_pos_map.values()
    )
    equity_est = cash + sum((p.get("current_price") or 0.0) * (p.get("quantity") or 0.0) for p in open_pos_map.values())
    lines.append(f"- Unrealized P&L: {fmt_val(unrealized)}")
    lines.append(f"- Estimated equity: {fmt_val(equity_est)}")
    if realized_total_pct:
        avg_realized = sum(realized_total_pct) / len(realized_total_pct)
        lines.append(f"- Avg realized P&L per trade: {avg_realized:+.2f}% (over {len(realized_total_pct)} trades)")
    lines.append("")

    report = "\n".join(lines)
    out = os.path.join(PAPER_DIR, f"audit_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md")
    os.makedirs(os.path.dirname(out) if os.path.dirname(out) else ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
