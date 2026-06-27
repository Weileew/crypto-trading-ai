#!/usr/bin/env python3
"""Trade-planning helper: derives position parameters from plan inputs.
This module never returns a trade signal. It only computes allocation fractions,
stop/placement helpers, and risk-derived fields from adviser inputs.
"""
import os
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SKILL_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

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


def load_briefing(today=None):
    if today is None:
        today = _utc_today()
    path = os.path.join(REPORTS_DIR, f"daily_briefing_{today}.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _utc_today():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_plan_input(
    capital,
    risk_per_trade,
    stop_distance,
    price,
    name="trade",
    symbol="",
    confidence="medium",
    allocation_cap=None,
):
    """Build plan input object from adviser-supplied parameters.

    Returns a structure the adviser can approve or reject. This function never
    emits a trade signal.
    """
    capital = _safe_float(capital, 0.0)
    risk_per_trade = _safe_float(risk_per_trade, 0.0)
    stop_distance = _safe_float(stop_distance, 0.0)
    price = _safe_float(price, 0.0)

    allocation = capital * risk_per_trade
    if allocation <= 0 or stop_distance <= 0 or price <= 0:
        return {
            "name": name,
            "symbol": symbol,
            "confidence": confidence,
            "status": "invalid_input",
            "reason": "capital, risk_per_trade, stop_distance, and price must be positive.",
        }

    quantity = allocation / price
    stop = price - stop_distance
    target = price + (stop_distance * 2)

    allocation_cap = _safe_float(allocation_cap, 0.0)
    if allocation_cap > 0:
        allocation_cap = min(allocation, allocation_cap)
        quantity = allocation_cap / price

    plan = {
        "name": name,
        "symbol": symbol,
        "confidence": confidence,
        "status": "draft",
        "capital": capital,
        "risk_per_trade": risk_per_trade,
        "allocated_usd": round(allocation, 2),
        "price": price,
        "stop": round(stop, 6),
        "target": round(target, 6),
        "stop_distance": round(stop_distance, 6),
        "quantity": round(quantity, 6),
    }
    if allocation_cap > 0:
        plan["allocation_cap"] = round(allocation_cap, 2)

    return plan


def recommend_allocation(plan, capital, max_risk_per_trade=0.02):
    """Given a draft plan, derive recommended allocation fraction.

    The adviser provides risk and confidence inputs. This helper returns only
    dimensionless parameters for adviser review.
    """
    capital = _safe_float(capital, 0.0)
    max_risk_per_trade = _safe_float(max_risk_per_trade, 0.02)
    allocated = _safe_float(plan.get("allocated_usd", 0.0), 0.0)

    if capital <= 0:
        return {"status": "invalid_capital", "allocation_fraction": 0.0}

    allocation_fraction = allocated / capital
    capped_fraction = min(allocation_fraction, max_risk_per_trade)
    return {
        "status": "ok",
        "allocation_fraction": round(allocation_fraction, 6),
        "recommended_fraction": round(capped_fraction, 6),
        "exceeds_max": allocation_fraction > max_risk_per_trade,
    }


def session_plan_path(today=None):
    if today is None:
        today = _utc_today()
    return os.path.join(REPORTS_DIR, f"trade_plan_{today}.md")


def save_plan(plan):
    path = session_plan_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(plan, indent=2))
    return path


def summarize(plan):
    if not plan:
        return "No parameter draft available."
    lines = [
        f"Name: {plan.get('name','-')}",
        f"Symbol: {plan.get('symbol','-')}",
        f"Confidence: {plan.get('confidence','-')}",
        f"Allocated: {plan.get('allocated_usd','-')}",
        f"Price: {plan.get('price','-')}",
        f"Stop: {plan.get('stop','-')}",
        f"Target: {plan.get('target','-')}",
        f"Quantity: {plan.get('quantity','-')}",
    ]
    if plan.get("allocation_cap") is not None:
        lines.append(f"Allocation cap: {plan.get('allocation_cap')}")
    return "\n".join(lines)
