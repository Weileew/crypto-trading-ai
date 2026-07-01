# Paper Trading M2M Update Script (`paper-m2m-update.sh`)

## Overview
The `paper-trading-m2m` cron job runs every 10 minutes in `no_agent` mode (zero LLM tokens). It executes `~/.hermes/scripts/paper-m2m-update.sh` which calls `python3 scripts/paper_trader.py --update --summary`.

## File Location
- Script: `~/.hermes/scripts/paper-m2m-update.sh`
- Skill workdir: `~/.hermes/skills/trading-advisor/`
- Data: `reports/paper_trading/portfolio.json`, `ledger.json`
- Strategy journal: `strategy/journal.db` (not `reports/paper_trading/journal.db` which is a stale 0-byte file)

## Script Behavior
Three output paths:

| Condition | Output | Cron Delivery |
|-----------|--------|---------------|
| No positions closed (`Journal: synced` absent) | Silent (exit 0, no stdout) | Nothing delivered — Telegram stays quiet ✅ |
| Position(s) closed (`Journal: synced` detected) | Formatted card notification | Telegram notifies with card-style layout |
| Error (non-zero exit from paper_trader.py) | `⚠️ M2M ERROR` banner + raw output | Telegram alerts |

## Notification Format (card-style UX)

When a position closes, delivers a **card-style** block. No raw tables, no Markdown tables — Telegram variable-width font breaks column alignment, so every notification uses vertical cards with `▎` indented fields and `━━━` separators.

### Profit close:
```
🟢 VELVET CLOSED ▲ PROFIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▎ Return:  🟢 +150.86%
▎ Entry:   $0.709546  →  Exit: $1.78
▎ Reason:  🎯 Target Hit
🕐 Closed:  2026-06-28 14:27:46

📊  OPEN POSITIONS (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
▎ RE  🔴 -2.17%
  ▎ Entry $0.616837 → $0.603439
  ▎ Qty: 310.2849 · Alloc: $191.40

💰  PORTFOLIO
━━━━━━━━━━━━━━━━━━━━━
▎ Equity:  $9,374.36
▎ Cash:    $9,187.12
▎ Return:  🔴 -6.26%
```

### Loss close:
```
🔴 SKYAI CLOSED ▼ LOSS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▎ Return:  🔴 -5.29%
▎ Entry:   $0.367899  →  Exit: $0.348422
▎ Reason:  🛑 Stop-Loss
🕐 Closed:  2026-06-27 11:29:16
```

### Reason emoji mapping:
| Reason | Icon | Label |
|--------|------|-------|
| `stop-loss`, `stop` | 🛑 | Stop-Loss |
| `target-hit`, `target` | 🎯 | Target Hit |
| `trailing_stop`, `trailing` | 🔒 | Trailing Stop |
| `backtest_stop` | 📊 | Backtest Stop |
| anything else | ⚡ | (pass-through) |

## Notification UX Rules
1. **Hero metric first**: symbol + result (PROFIT/LOSS) is the very first line — immediately scannable
2. **P&L % is second line**: color-coded with 🟢/🔴 emoji matching direction
3. **Entry → Exit arrow**: shows price movement direction visually
4. **Reason icon + label**: each close reason has a dedicated icon
5. **Clock icon** on timestamp for quick temporal context
6. **Open positions section below**: shows current open positions with live P&L, trailing stop status
7. **Portfolio summary**: equity (comma-formatted), cash, total return %
8. No trailing stop shown when `trailing_activated=false` (stale or unarmed)
9. Empty portfolio shows `📊  OPEN POSITIONS: none`

## How It Works (data flow)

1. `paper_trader.py --update --summary` runs M2M update and prints summary
2. Script captures full output in `$OUTPUT`
3. Script checks for `Journal: synced` substring → if absent, exits silently
4. Awk parser extracts the **first row** under `| Recent closed trades |` (most recent close)
5. Fields parsed: `DATE|SYM|entry=X|exit=X|PNL%|REASON`
6. `entry=` and `exit=` prefixes stripped from price values
7. Card formatted and echoed to stdout, followed by open positions + portfolio
8. Cron delivers stdout to origin (Telegram)

## Awk Parser (`│` vs `|` pitfall)

The summary table uses regular pipe `|` characters (Markdown), NOT Unicode box-drawing `│` (U+2502).

**WRONG** (would silently match nothing → notification never fires):
```awk
in_table && /│/ {  # U+2502 — never matches pipe-delimited output
```

**RIGHT** (matches actual Markdown table rows):
```awk
in_table && /^[[:space:]]*\|/ {
    gsub(/^[[:space:]]*\|[[:space:]]*/, "")
    gsub(/[[:space:]]*\|[[:space:]]*$/, "")
    split($0, fields, "[[:space:]]*[|][[:space:]]*")
    if (length(fields) >= 6 && fields[1] ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}/) {
        print fields[1] "|" fields[2] "|" fields[3] "|" fields[4] "|" fields[5] "|" fields[6]
        exit
    }
}
```

## Edge Cases Handled
- **No positions open**: portfolio section shows `OPEN POSITIONS: none`
- **Awk parse failure**: falls back to raw `$OUTPUT` with `🔔 POSITION(S) CLOSED (raw summary below)`
- **Empty or malformed portfolio.json**: Python inline code fails silently, script exits non-zero → error banner
- **`trailing_stop` key exists but `trailing_activated=false`**: trail value is a stale artifact, NOT displayed
- **Multiple closes same tick**: awk takes first row only (most recent by timestamp). Second close won't trigger a separate notification

## Common Issues & Fixes

| Issue | Root Cause | Fix |
|-------|------------|-----|
| M2M never saves | `--update` branch missing `save_portfolio()` / `save_ledger()` | Ensure both called after `update_mark_to_market()` |
| Double M2M per tick | `--update` falls through to default path | Early-return after update block when not `--summary` or `--paper-open` |
| Trailing stop resets | `_normalize_position()` strips new fields | Add all new fields to `_normalize_position()` in same patch as `open_position()` |
| `float("?")` crash | Stop/target stored as `"?"` from old briefings | Use `_safe_float()` + `try/except continue` per position |
| Price parser fails | Compact format emits `"0.3973 (+8%)"` | `_safe_price()` strips parenthetical annotations before `float()` |
| **Notification never fires** | Awk looks for `│` (U+2502) but output uses `\|` (pipe) | Change awk pattern to `/^[[:space:]]*\|/` — regex-escape the pipe |
| **Missing `fi` syntax error** | Nested `if` blocks without matching `fi` | Shellcheck: every `if` needs its own `fi`, at correct indentation level |
| **Notification shows wrong close** | Awk grabs first table row which may be legacy archived, not current close | Verify `Journal: synced N` shows N>0 for the actual close, not legacy_archived count |

## Data Accuracy Audit (June 2026)

Cross-referenced notification output against all three sources:

| Source | Check | Result |
|--------|-------|--------|
| `portfolio.json` | Equity = cash + Σ(current_price × qty) | ✅ Computed value matches reported equity |
| `ledger.json` | All closed trades have matching entry/exit/pnl | ✅ No discrepancies |
| `ledger.json` | No duplicate trade_ids | ✅ 5 trades, all unique |
| `strategy/journal.db` | No duplicate signal+entry+outcome | ⚠️ RE entries duplicated (4 signals for same entry $0.616837) — **does NOT affect notification**, which reads portfolio.json |
| `--summary` output | Cash, equity, positions match portfolio.json | ✅ Exact match |

**Known background issue**: The strategy journal (`strategy/journal.db`) has 4 duplicate signal entries for RE at entry $0.616837. Created by `_sync_closed_to_journal()` fallback path when M2M ticks trigger the trailing stop logic but don't actually close the position. This doesn't affect notifications (which read from portfolio.json), but inflates journal signal counts and corrupts win-rate stats. If win rate looks suspiciously low, check for this duplication pattern: same symbol + entry_price across consecutive signal IDs.

## Verification Commands
```bash
# Manual run (silent if no events)
cd /home/ubuntu/.hermes/skills/trading-advisor
bash ~/.hermes/scripts/paper-m2m-update.sh 2>&1; echo "EXIT: $?"

# Check portfolio state
cat reports/paper_trading/portfolio.json

# Check ledger
python3 -c "import json; d=json.load(open('reports/paper_trading/ledger.json')); [print(f'{t[\"trade_id\"]} {t[\"symbol\"]} status={t.get(\"status\",\"closed\")} entry={t.get(\"entry_price\",\"?\")} exit={t.get(\"exit_price\",\"N/A\")} pnl={t.get(\"pnl_pct\",\"N/A\")}') for t in d['trades']]"

# Verify journal signals
python3 -c "
import sqlite3
db = sqlite3.connect('strategy/journal.db')
cur = db.execute('SELECT s.id, s.symbol, s.entry_price, COUNT(*) as dup FROM signals s GROUP BY s.symbol, s.entry_price HAVING dup > 1')
for r in cur.fetchall():
    print(f'DUPLICATE: sym={r[1]} entry={r[2]} count={r[3]}')
db.close()
"
```
