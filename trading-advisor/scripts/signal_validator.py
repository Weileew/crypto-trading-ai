#!/usr/bin/env python3
"""Historical signal validator for crypto trading advisor.

Reads daily briefings, extracts buy-bias recommendations with Entry/Stop/Target,
backtests them against daily candles, and writes reports/signal_performance.json.

Primary candle source: CoinGecko market_chart.
Fallback: Binance klines.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
PERF_PATH = os.path.join(REPORTS_DIR, "signal_performance.json")
os.makedirs(REPORTS_DIR, exist_ok=True)

UA = "crypto-trading-advisor/0.1 (+https://example.com)"
_GLOBAL_LAST = 0.0
_GLOBAL_SLEEP = 0.6


def _throttle():
    global _GLOBAL_LAST
    wait = _GLOBAL_SLEEP - (time.time() - _GLOBAL_LAST)
    if wait > 0:
        time.sleep(wait)


def _get(url, headers=None, params=None, timeout=20, retries=3, backoff=1.25):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if params:
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    req = Request(url, headers=h)
    last = None
    for attempt in range(1, retries + 1):
        _throttle()
        try:
            with urlopen(req, timeout=timeout) as r:
                global _GLOBAL_LAST
                _GLOBAL_LAST = time.time()
                return json.loads(r.read().decode())
        except HTTPError as e:
            _GLOBAL_LAST = time.time()
            if e.code == 429 or 500 <= e.code < 600:
                last = e
                time.sleep(backoff * attempt)
                continue
            return {"_http_error": e.code, "url": url}
        except Exception as e:
            _GLOBAL_LAST = time.time()
            last = e
            time.sleep(backoff * attempt)
    return {"_fetch_error": str(last), "url": url}


ALIAS = {
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
_DAYS_CAP = 90
_DAYS_REDUCED = 30


def fetch_coingecko_market_chart(coin_id: str, days: int = 30):
    data = _get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": days},
        timeout=25,
        retries=2,
    )
    if not isinstance(data, dict):
        return []
    return data.get("prices", []) or []


def fetch_binance_klines(symbol: str, days: int = 60):
    sym = (symbol or "").strip().upper()
    alias = {
        "VELVET": "VELVETUSDT", "SKYAI": "SKYAIUSDT", "MAGMA": "MAGMAUSDT",
    }
    pair = alias.get(sym)
    if not pair:
        if sym.endswith("USDT") or sym.endswith("BUSD"):
            pair = sym
        else:
            pair = f"{sym}USDT"
    limit = min(max(days, 1), 1000)
    data = _get(
        "https://api.binance.com/api/v3/klines",
        {"symbol": pair, "interval": "1d", "limit": limit},
        timeout=20,
        retries=2,
    )
    if not isinstance(data, list):
        return []
    out = []
    for row in data:
        out.append([int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])])
    return out


def _coingecko_search(query: str):
    data = _get(
        "https://api.coingecko.com/api/v3/search",
        {"query": query},
        timeout=20,
        retries=2,
    )
    if not isinstance(data, dict):
        return None
    hits = data.get("coins") or []
    if not hits:
        return None
    top = hits[0]
    return {
        "id": top.get("id"),
        "symbol": top.get("symbol"),
        "name": top.get("name"),
    }


def resolve_coin_id(sym: str):
    label = (sym or "").strip().lower()
    coin_id = ALIAS.get(label, label)
    if coin_id != label:
        # ALIAS had a known CoinGecko id — use it directly
        return coin_id
    # Unknown ticker — try CG search as fallback
    hit = _coingecko_search(label)
    if hit and hit.get("id"):
        return hit["id"]
    return coin_id  # still the raw label; may fail on market_chart


def load_briefings(days: int = 30):
    out = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if not os.path.isdir(REPORTS_DIR):
        return out
    for fn in os.listdir(REPORTS_DIR):
        if not fn.startswith("daily_briefing_") or not fn.endswith(".md"):
            continue
        try:
            dt = datetime.strptime(fn, "daily_briefing_%Y-%m-%d.md").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt < cutoff:
            continue
        with open(os.path.join(REPORTS_DIR, fn), encoding="utf-8") as f:
            out.append((dt.date().isoformat(), f.read()))
    out.sort()
    return out


def parse_buy_recommendations(text: str):
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
        # Track the structured fields regardless of prefix format.
        if re.match(r"^[-*]\s*Bias\b", s, re.IGNORECASE):
            current["bias"] = s.split(":", 1)[-1].strip().lower()
            continue
        if re.match(r"^[-*]\s*Entry\b", s, re.IGNORECASE):
            current["entry"] = s.split(":", 1)[-1].strip()
            continue
        if re.match(r"^[-*]\s*Stop\b", s, re.IGNORECASE):
            current["stop"] = s.split(":", 1)[-1].strip()
            continue
        if re.match(r"^[-*]\s*Target\b", s, re.IGNORECASE):
            current["target"] = s.split(":", 1)[-1].strip()
            continue
        if re.match(r"^\d+\.\s+\S", s) and not s.startswith("http"):
            if current:
                recs.append(current)
                current = {}
            current["name"] = s.split(".", 1)[-1].strip()
            continue
        # Allow plain title lines that look like signal headers.
        if not s.startswith("-") and not s.startswith("#") and len(s) < 140 and "(" in s:
            if current:
                recs.append(current)
                current = {}
            current["name"] = s.strip()
            continue

    if current:
        recs.append(current)
    buy = [r for r in recs if (r.get("bias") or "").lower() in {"buy bias", "bullish", "long", "accumulate", "buy"}]
    return buy


def symbol_from_name(name: str) -> str:
    m = re.search(r"\(([^)]+)\)", name or "")
    if m:
        return m.group(1).strip().lower()
    return (name or "").strip().split()[-1].lower()


def parse_price(v):
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


def backtest(candles, signal_date, entry, stop, target, max_candles=14):
    try:
        sig_dt = datetime.strptime(signal_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
    except ValueError:
        return None
    future = [(datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date().isoformat(), row) for row in candles]
    future = sorted((d, r) for d, r in future if d > sig_dt.isoformat())
    if not future:
        return None

    # Multi-stage trailing stop config (from params.json or defaults)
    _trail_params_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "strategy", "params.json"
    )
    _trail_stages = [(2.0, 1.0), (6.0, 2.0), (12.0, 3.0)]  # (activation%, distance%)
    try:
        with open(_trail_params_path) as _tf:
            _tp = json.load(_tf)
        _dr = _tp.get("dynamic_risk", {})
        if not _dr.get("enabled", True):
            _trail_stages = []
    except Exception:
        pass

    def _trail_for_profit(pct):
        """Return (activation_threshold, trail_distance) for the given profit level."""
        for act, dist in reversed(_trail_stages):
            if pct >= act:
                return act, dist
        return _trail_stages[0] if _trail_stages else (999, 0)

    highest_price = entry
    trailing_stop_price = None
    trailing_activated = False

    for i, (_, row) in enumerate(future[:max_candles]):
        low, high, close = row[3], row[2], row[4]

        # Fixed stop / target checks (highest priority)
        if low <= stop:
            return {"exit_price": stop, "exit_reason": "stop", "exit_date": future[i][0], "entry_open": future[0][1][1], "holding_candles": i + 1}
        if high >= target:
            return {"exit_price": target, "exit_reason": "target", "exit_date": future[i][0], "entry_open": future[0][1][1], "holding_candles": i + 1}

        # Track highest price for trailing stop
        if high > highest_price:
            highest_price = high

        # Multi-stage trailing stop
        profit_pct = ((close - entry) / entry) * 100
        act, dist = _trail_for_profit(profit_pct)
        if not trailing_activated and profit_pct >= act:
            trailing_stop_price = highest_price * (1 - dist / 100)
            trailing_activated = True
        elif trailing_activated:
            _, dist = _trail_for_profit(((highest_price - entry) / entry) * 100)
            ts_new = highest_price * (1 - dist / 100)
            if ts_new > trailing_stop_price:
                trailing_stop_price = ts_new
            if low <= trailing_stop_price:
                return {"exit_price": trailing_stop_price, "exit_reason": "trailing_stop", "exit_date": future[i][0], "entry_open": future[0][1][1], "holding_candles": i + 1}

    last_date, last_row = future[-1]
    return {"exit_price": last_row[4], "exit_reason": "timeout", "exit_date": last_date, "entry_open": future[0][1][1], "holding_candles": min(len(future), max_candles)}


def prune_stale_pending(signals, stale_days=90):
    """Drop pending_validation signals older than stale_days from the output."""
    cutoff = datetime.now(timezone.utc).date()
    out = []
    pruned = 0
    for s in signals:
        if s.get("validation_status") == "pending_validation":
            try:
                d = datetime.strptime(s["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                out.append(s)
                continue
            if (cutoff - d).days >= stale_days:
                pruned += 1
                continue  # drop stale pending
        out.append(s)
    return out, pruned


def summarize(signals):
    if not signals:
        return {"total_signals": 0}
    wins = [s for s in signals if s.get("validation_status") == "backtested" and ((s.get("pnl_pct") or 0) > 0)]
    validated = [s for s in signals if s.get("validation_status") == "backtested"]
    pending = sum(1 for s in signals if s.get("validation_status") == "pending_validation")
    return {
        "total_signals": len(signals),
        "validated_count": len(validated),
        "wins": len(wins),
        "losses": len(validated) - len(wins),
        "win_rate": round(len(wins) / len(validated) * 100, 2) if validated else None,
        "target_hit_rate": round(sum(1 for s in validated if s.get("exit_reason") == "target") / len(validated) * 100, 2) if validated else None,
        "stop_hit_rate": round(sum(1 for s in validated if s.get("exit_reason") == "stop") / len(validated) * 100, 2) if validated else None,
        "trailing_stop_rate": round(sum(1 for s in validated if s.get("exit_reason") == "trailing_stop") / len(validated) * 100, 2) if validated else None,
        "avg_r_multiple": round(sum(s.get("r_multiple", 0.0) for s in validated) / len(validated), 3) if validated else None,
        "best_signal": max(validated, key=lambda s: s.get("r_multiple", 0.0)).get("symbol") if validated else None,
        "best_r_multiple": round(max(s.get("r_multiple", 0.0) for s in validated), 3) if validated else None,
        "worst_signal": min(validated, key=lambda s: s.get("r_multiple", 0.0)).get("symbol") if validated else None,
        "worst_r_multiple": round(min(s.get("r_multiple", 0.0) for s in validated), 3) if validated else None,
        "pending_validation_count": pending,
    }


def main(days: int = 30, max_candles: int = 14):
    briefings = load_briefings(days=days)
    if not briefings:
        print("No recent briefings found.")
        return

    seen = set()
    out = []
    for date, text in briefings:
        recs = parse_buy_recommendations(text)
        for rec in recs:
            name = rec.get("name", "")
            sym = symbol_from_name(name)
            entry = parse_price(rec.get("entry"))
            stop = parse_price(rec.get("stop"))
            target = parse_price(rec.get("target"))
            if entry is None or stop is None or target is None:
                continue
            key = (date, sym)
            if key in seen:
                continue
            seen.add(key)
            coin_id = resolve_coin_id(sym)
            effective_days = min(days + 30, _DAYS_CAP)
            if coin_id != sym:
                effective_days = min(effective_days, _DAYS_REDUCED)
            candles = fetch_coingecko_market_chart(coin_id, days=effective_days)
            if not candles:
                candles = fetch_binance_klines(sym, days=days + 30)
            bt = None
            if candles:
                bt = backtest(candles, date, entry, stop, target, max_candles=max_candles)
                if bt:
                    risk = abs(entry - stop)
                    r = ((bt["exit_price"] - entry) / risk) if risk else 0.0
                    out.append({
                        "date": date, "symbol": sym, "name": name,
                        "entry": entry, "stop": stop, "target": target,
                        **bt,
                        "pnl_pct": round(((bt["exit_price"] - entry) / entry) * 100.0, 3),
                        "r_multiple": round(r, 3),
                        "validation_status": "backtested",
                    })
                    continue
            # No candles or backtest couldn’t run — still record the signal.
            out.append({
                "date": date, "symbol": sym, "name": name,
                "entry": entry, "stop": stop, "target": target,
                "exit_reason": "no_data",
                "validation_status": "pending_validation",
            })

    out, pruned = prune_stale_pending(out, stale_days=_DAYS_CAP)

    perf = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": out,
        "summary": summarize(out),
        "pending_validation_stale_days": _DAYS_CAP,
        "pruned_stale_count": pruned,
    }
    with open(PERF_PATH, "w", encoding="utf-8") as f:
        json.dump(perf, f, indent=2, default=str)
    print(json.dumps(perf["summary"], indent=2))

    # Also write validated outcomes to the strategy journal for the orchestrator
    if out:
        try:
            _write_to_journal(out)
        except Exception as e:
            print(f"  Journal write skipped: {e}")


def _write_to_journal(signals: list[dict]):
    """Write validated signal outcomes to the strategy journal."""
    import importlib.util
    j_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "scripts", "strategy_journal.py")
    if not os.path.exists(j_path):
        return
    spec = importlib.util.spec_from_file_location("strategy_journal", j_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.init_db()

    for sig in signals:
        if sig.get("validation_status") != "backtested":
            continue
        sym = sig.get("symbol", "???")
        bias = "bullish"  # signal_validator only processes buy recs
        entry = sig.get("entry", 0)
        target = sig.get("target")
        stop = sig.get("stop")
        exit_price = sig.get("exit_price")
        outcome = "hit_target" if sig.get("exit_reason") in ("target", "target_hit") else (
            "hit_stop" if sig.get("exit_reason") in ("stop", "stop_hit") else
            "trailing_stop" if sig.get("exit_reason") == "trailing_stop" else "expired"
        )
        pnl = sig.get("pnl_pct")
        duration_h = sig.get("bars_count", 0) * 24  # approximate from daily candles

        # First, try to match an existing open signal in the journal
        open_signals = mod.get_open_signals()
        matched = [s for s in open_signals if s["symbol"] == sym and abs((s.get("entry_price") or 0) - entry) / max(entry, 1) < 0.05]

        if matched:
            # Close the matched signal
            mod.close_signal(
                signal_id=matched[0]["id"],
                outcome=outcome,
                exit_price=exit_price,
                regime="signal_validator",
                reason=f"backtest_{sig.get('exit_reason', 'unknown')}",
            )
        else:
            # No matching open signal — record a standalone outcome
            sid = mod.record_signal(
                symbol=sym, name=sig.get("name", sym), bias=bias,
                entry_price=entry, target_price=target, stop_price=stop,
                confidence="medium", score=None,
                source="signal_validator", batch_id=f"validate_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                notes=f"Backtested: {sig.get('exit_reason', '?')} PnL={pnl}%",
            )
            mod.close_signal(
                signal_id=sid, outcome=outcome, exit_price=exit_price,
                regime="signal_validator", reason=f"backtest_{sig.get('exit_reason', 'unknown')}",
            )


if __name__ == "__main__":
    main()
