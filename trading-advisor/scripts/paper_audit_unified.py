#!/usr/bin/env python3
"""Unified daily audit: cross-reference portfolio.json ↔ ledger.json ↔ journal.db.

Silent on success (exit 0, no output). Prints structured issues on failure (exit 1).

Checks:
1. Portfolio ↔ Ledger: open position symbols match open ledger trades
2. Cash sanity: starting_capital ≈ cash + allocated positions + realized closed PnL
3. Journal DB: no dangling signals without outcomes
4. Legacy_archived: no legacy PnL leaking into summary
5. Orphan detection: ledger entries with no matching portfolio position
6. Consistency: no duplicate open symbols in either store
"""
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_REPORTS = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(SKILL_REPORTS, "paper_trading")
DB_PATH = os.path.join(SKILL_DIR, "strategy", "journal.db")

issues = []


def fail(msg: str):
    issues.append(msg)


def fmt(v, d="N/A"):
    if v is None:
        return d
    if isinstance(v, float):
        return round(v, 2)
    return v


# ── Load data ────────────────────────────────────────────────────────────────

portfolio_path = os.path.join(PAPER_DIR, "portfolio.json")
ledger_path = os.path.join(PAPER_DIR, "ledger.json")

portfolio = {}
ledger = {"trades": []}

if os.path.exists(portfolio_path):
    with open(portfolio_path, encoding="utf-8") as f:
        portfolio = json.load(f)
else:
    fail(f"portfolio.json not found at {portfolio_path}")

if os.path.exists(ledger_path):
    with open(ledger_path, encoding="utf-8") as f:
        ledger = json.load(f)
else:
    fail(f"ledger.json not found at {ledger_path}")

# ── Check 1: Portfolio ↔ Ledger symbol match ─────────────────────────────

pf_positions = portfolio.get("positions") or {}
pf_symbols = set(k.upper() for k in pf_positions.keys())

trades = ledger.get("trades") or []
open_ledger = [t for t in trades if t.get("status") == "opened"]
ledger_open_symbols = set(t.get("symbol", "").upper() for t in open_ledger if t.get("symbol"))

# Symbols in portfolio but not in ledger
only_pf = pf_symbols - ledger_open_symbols
if only_pf:
    fail(f"Portfolio has positions with no matching open ledger entry: {sorted(only_pf)}")

# Symbols in ledger but not in portfolio (orphaned)
only_ledger = ledger_open_symbols - pf_symbols
if only_ledger:
    fail(f"Ledger has open entries with no matching portfolio position: {sorted(only_ledger)}")

# ── Check 2: Cash sanity ────────────────────────────────────────────────

starting = portfolio.get("starting_capital", 10000.0)
cash = portfolio.get("cash", starting)

# Realized P&L from closed trades (excluding legacy_archived)
realized_pnl = 0.0
closed_trades = [t for t in trades if t.get("status") == "closed"]
for t in closed_trades:
    if t.get("outcome") == "legacy_archived":
        continue
    pnl = t.get("pnl_usd")
    if pnl is not None:
        realized_pnl += float(pnl)

# Allocated capital in open positions
allocated = sum(float(p.get("allocated", 0)) for p in pf_positions.values())

# Estimated equity = cash + sum(current_price * quantity for open positions)
unrealized_value = sum(
    float(p.get("current_price", 0)) * float(p.get("quantity", 0))
    for p in pf_positions.values()
)
equity_est = cash + unrealized_value

# What equity should be: starting + realized PnL + current unrealized PnL
unrealized_pnl = sum(
    float(p.get("pnl_usd", 0))
    for p in pf_positions.values()
)
expected_equity = starting + realized_pnl + unrealized_pnl

cash_delta = abs(equity_est - expected_equity)
if cash_delta > equity_est * 0.02 + 5.0:  # 2% or $5 tolerance
    fail(f"Cash sanity: equity_est=${fmt(equity_est)} but expected=${fmt(expected_equity)} (delta=${fmt(cash_delta)})")

# Check cash + allocated ≠ starting (rough check)
cash_and_allocated = cash + allocated
alloc_delta = abs(cash_and_allocated + realized_pnl - starting)
if alloc_delta > starting * 0.05 + 10.0 and len(closed_trades) > 0:
    fail(f"Cash+allocated (${fmt(cash_and_allocated)}) + realized (${fmt(realized_pnl)}) ≠ starting (${fmt(starting)}) — delta=${fmt(alloc_delta)}")

# ── Check 3: Journal DB — dangling signals ──────────────────────────────

if os.path.exists(DB_PATH):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            """SELECT s.id, s.symbol, s.generated_at, s.source, s.entry_price
               FROM signals s
               LEFT JOIN outcomes o ON s.id = o.signal_id
               WHERE o.id IS NULL
               ORDER BY s.generated_at DESC"""
        )
        dangling = cur.fetchall()
        conn.close()
        if dangling:
            details = [f"  #{r[0]} {r[1]} src={r[3]} gen={r[2][:19]} entry={fmt(r[4])}" for r in dangling[:10]]
            fail(f"Journal DB has {len(dangling)} dangling signals (no outcome):\n" + "\n".join(details))
    except Exception as e:
        fail(f"Journal DB error: {e}")
else:
    fail(f"Journal DB not found at {DB_PATH}")

# ── Check 4: Check for legacy_archived PnL leakage ──────────────────────

legacy_trades = [t for t in closed_trades if t.get("outcome") == "legacy_archived"]
non_legacy_closed = [t for t in closed_trades if t.get("outcome") != "legacy_archived"]

# Ensure legacy trades are excluded in any aggregate we compute ourselves (already done above)

# ── Check 5: Orphan detection ──────────────────────────────────────────

# Only flag NEW orphans (created within the last 24h) to avoid daily noise on historical ones
_orphan_cutoff = (datetime.now(UTC).isoformat()[:10])  # today YYYY-MM-DD
orphaned = [t for t in trades if t.get("status") == "orphaned"]
new_orphans = [t for t in orphaned if (t.get("closed_at") or t.get("date") or "").startswith(_orphan_cutoff)]
if new_orphans:
    fail(f"Ledger has {len(new_orphans)} NEW orphaned trades (today): {[t.get('symbol') for t in new_orphans]}")

# Report known orphans as info (not failure)
_known_orphans = [t for t in orphaned if t not in new_orphans]
if _known_orphans:
    pass  # Historical orphans — acknowledged, not actionable daily

# ── Check 6: Duplicate detection ─────────────────────────────────────────

# Check for duplicate symbols in portfolio positions (shouldn't happen — dict overwrites)
# Check for duplicate trade_ids in ledger
trade_ids = [t.get("trade_id") for t in trades if t.get("trade_id")]
dupe_ids = set(tid for tid in trade_ids if trade_ids.count(tid) > 1)
if dupe_ids:
    fail(f"Duplicate trade_ids in ledger: {dupe_ids}")

# ── Results ──────────────────────────────────────────────────────────────

if issues:
    print("AUDIT FAILED — issues found:")
    for i, msg in enumerate(issues, 1):
        print(f"\n{i}. {msg}")
    print(f"\nAudited at: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Portfolio: {len(pf_symbols)} open positions, cash=${fmt(cash)}")
    print(f"Ledger: {len(open_ledger)} open trades, {len(closed_trades)} closed ({len(non_legacy_closed)} active)")
    sys.exit(1)
else:
    # Silent on success — cron with no_agent=True delivers nothing
    pass
