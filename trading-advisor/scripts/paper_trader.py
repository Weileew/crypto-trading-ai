#!/usr/bin/env python3
"""Paper trading simulator for crypto recommendations."""
import os
import json
import re
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PAPER_DIR = os.path.join(REPORTS_DIR, "paper_trading")
os.makedirs(PAPER_DIR, exist_ok=True)

UA = "crypto-trading-advisor/0.1 (+https://example.com)"


def _get(url, params=None, headers=None, timeout=25):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if params:
        from urllib.parse import urlencode

        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        return {"_http_error": e.code, "_url": url}
    except Exception as e:
        return {"_fetch_error": str(e), "_url": url}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _safe_price(price):
    try:
        return float(price)
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


# Symbol → CoinGecko ID mapping (kept in-sync with signal_validator.py)
_SYM_TO_CG = {
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
    "usdt": "tether", "usdc": "usd-coin", "cro": "crypto-com-chain", "hbar": "hedera-hashgraph",
    "vet": "vechain", "theta": "theta-token", "fil": "filecoin", "egld": "elrond-erd-2",
    "algo": "algorand", "nano": "nano", "xlm": "stellar", "trx": "tron",
    "fxs": "frax-share", "cvx": "convex-finance", "yfi": "yearn-finance",
    "cake": "pancakeswap-token", "dydx": "dydx", "gmt": "stepn", "stx": "blockstack",
    "mina": "mina-protocol", "zil": "zilliqa", "waves": "waves", "kava": "kava",
    "anr": "anr-key", "jup": "jupiter-exchange-solana", "pyth": "pyth-network",
    "ondo": "ondo-finance", "ena": "ethena", "ethfi": "ether-fi",
    "pendle": "pendle", "alt": "altlayer", "strk": "starknet",
    "wld": "worldcoin-org", "manta": "manta-network", "dym": "dymension",
    "saga": "saga-2", "not": "notcoin", "io": "io-net",
}


def current_price_map(symbols):
    """Return a {symbol: price} map from CoinGecko for the requested symbols.

    Portfolio keys are uppercase symbols (e.g. 'VELVET', 'MAGMA').
    The function lowercases them and maps to CoinGecko internal IDs
    via _SYM_TO_CG before querying.
    """
    if not symbols:
        return {}
    cg_ids = []
    for s in symbols:
        label = (s or "").strip().lower()
        cg_id = _SYM_TO_CG.get(label, label)
        if cg_id:
            cg_ids.append(cg_id)
    if not cg_ids:
        return {}
    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids": ",".join(cg_ids), "vs_currencies": "usd"},
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
            out[cg_id] = float(p)
    return out


def parse_briefing_recommendations(text):
    """Extract buy bias recommendations from briefing markdown text."""
    recs, current = [], {}
    lines = text.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            if current:
                recs.append(current)
                current = {}
            continue
        if s.startswith("- Bias"):
            current["bias"] = s.split(":", 1)[-1].strip().lower()
        elif s.startswith("- Entry"):
            current["entry"] = s.split(":", 1)[-1].strip()
        elif s.startswith("- Stop"):
            current["stop"] = s.split(":", 1)[-1].strip()
        elif s.startswith("- Target"):
            current["target"] = s.split(":", 1)[-1].strip()
        elif s.startswith("- Research"):
            current["research"] = s.split(":", 1)[-1].strip()
        elif re.match(r"^\d+\.\s+\S", s) and not s.startswith("http"):
            if current:
                recs.append(current)
            current = {"name": s.split(".", 1)[-1].strip()}
    if current:
        recs.append(current)
    return [r for r in recs if r.get("bias", "").lower() in {"buy bias", "buy", "bullish", "long", "accumulate"}]

def recommended_symbols(recs):
    """Best-effort symbol extraction from recommendation names."""
    out = []
    for r in recs:
        name = r.get("name", "")
        candidate = name.split("(")[-1].split(")")[0].strip()
        if candidate:
            out.append(candidate.lower())
    return out


def open_position(portfolio, rec, executed_price):
    symbol = recommended_symbols([rec])[0]
    if not symbol:
        return None
    if float(executed_price) <= 0:
        return None
    allocation = min(
        portfolio["cash"],
        max(portfolio["cash"] * 0.05, 10.0),
    )
    quantity = allocation / float(executed_price)
    if quantity <= 0:
        return None
    position = {
        "symbol": symbol,
        "name": rec.get("name"),
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
        "symbol": symbol,
        "name": pos.get("name"),
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
    symbols = list((portfolio.get("positions") or {}).keys())
    prices = current_price_map(symbols)
    for sym, pos in list((portfolio.get("positions") or {}).items()):
        price = prices.get(sym)
        if price is None:
            continue
        pos["current_price"] = round(price, 8)
        pos["pnl_usd"] = round(pos["quantity"] * pos["current_price"] - pos["allocated"], 2)
        pos["pnl_pct"] = round((pos["pnl_usd"] / pos["allocated"]) * 100, 2) if pos["allocated"] else 0.0
        if pos.get("stop") and price <= float(pos["stop"]):
            close_position(portfolio, sym, price, reason="stop-loss")
        elif pos.get("target") and price >= float(pos["target"]):
            close_position(portfolio, sym, price, reason="target-hit")


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
    executed = []
    for rec in recs:
        syms = recommended_symbols([rec])
        sym = (syms or [""])[0]
        price = prices.get(sym)
        if not sym or price is None:
            continue
        pos = open_position(portfolio, rec, price)
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
    lines = [
        "# Paper Trading",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Starting capital | {s['starting_capital']} |",
        f"| Cash | {s['cash']} |",
        f"| Open positions | {s['open_positions']} |",
        f"| Equity | {s['equity']} |",
        f"| Return | {s['return_pct']}% |",
        f"| Unrealised P&L | {s['unrealised_pnl_usd']} |",
        "",
        "| Symbol | Name | Entry | Current | P&L | P&L % |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for pos in (portfolio.get("positions") or {}).values():
        lines.append(
            f"| {pos.get('symbol')} | {pos.get('name')} | {pos.get('entry_price')} | {pos.get('current_price')} | {pos.get('pnl_usd')} | {pos.get('pnl_pct')}% |"
        )
    closed = [t for t in (ledger.get("trades") or []) if t.get("status") in ("closed", "exit") or t.get("closed_at")]
    recent_closed = closed[-10:]
    if recent_closed:
        lines += ["", "| Recent closed trades |", "| --- | --- |"]
        for trade in recent_closed:
            closed_at = (trade.get("closed_at") or "")[:10]
            pnl = trade.get("pnl_usd") or trade.get("pnl") or trade.get("P&L")
            pnl_pct = trade.get("pnl_pct")
            lines.append(
                f"| {closed_at} | {trade.get('symbol')} | {pnl} | {pnl_pct}% |"
            )
    return "\n".join(lines)


def save_summary(portfolio, ledger):
    txt = format_summary(portfolio, ledger)
    path = os.path.join(PAPER_DIR, f"summary_{_utc_today()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    return path


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
        update_mark_to_market(portfolio)

    if args.paper_open:
        executed = open_today(portfolio, briefing_text)
        for pos in executed:
            ledger["trades"].append(
                {
                    "type": "open",
                    "symbol": pos.get("symbol"),
                    "name": pos.get("name"),
                    "allocated": pos.get("allocated"),
                    "entry_price": pos.get("entry_price"),
                    "quantity": pos.get("quantity"),
                    "opened_at": pos.get("opened_at"),
                    "stop": pos.get("stop"),
                    "target": pos.get("target"),
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
    update_mark_to_market(portfolio)
    save_portfolio(portfolio)
    save_ledger(ledger)
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
                    "type": "open",
                    "symbol": pos.get("symbol"),
                    "name": pos.get("name"),
                    "allocated": pos.get("allocated"),
                    "entry_price": pos.get("entry_price"),
                    "quantity": pos.get("quantity"),
                    "opened_at": pos.get("opened_at"),
                    "stop": pos.get("stop"),
                    "target": pos.get("target"),
                }
            )
    save_portfolio(portfolio)
    save_ledger(ledger)
    return executed


if __name__ == "__main__":
    main()
