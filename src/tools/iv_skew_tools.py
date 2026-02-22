"""
IV skew analysis tool (Batch 3b).

Provides get_iv_skew_analysis() — analyzes implied volatility skew from live option chain:
- Smile/smirk shape classification (put_skew, smile, call_skew, flat)
- 25-delta skew
- Skew gradient (IV change per strike distance)
- Term structure skew across expirations
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_SKEW_THRESHOLD = 1.05  # 5% above ATM IV to classify as elevated


def _classify_skew_shape(
    atm_iv: float,
    otm_put_avg_iv: float,
    otm_call_avg_iv: float,
) -> str:
    """Classify IV skew shape based on OTM vs ATM IV relationship."""
    if atm_iv <= 0:
        return "flat"

    put_elevated = otm_put_avg_iv > atm_iv * _SKEW_THRESHOLD
    call_elevated = otm_call_avg_iv > atm_iv * _SKEW_THRESHOLD

    if put_elevated and call_elevated:
        return "smile"
    elif put_elevated:
        return "put_skew"
    elif call_elevated:
        return "call_skew"
    return "flat"


def _find_nearest_delta(
    quotes: List[Dict], target_delta: float,
) -> Optional[Dict]:
    """Find the quote with delta closest to target_delta."""
    best = None
    best_diff = float("inf")
    for q in quotes:
        d = q.get("delta")
        if d is None:
            continue
        diff = abs(d - target_delta)
        if diff < best_diff:
            best_diff = diff
            best = q
    return best


def _compute_skew_gradient(
    quotes: List[Dict], spot: float, side: str = "put",
) -> Optional[float]:
    """
    Compute IV gradient: change in IV per $1 strike distance from ATM.

    Uses linear regression on OTM options.
    """
    points = []
    for q in quotes:
        iv = q.get("iv")
        strike = q.get("strike")
        if iv is None or strike is None:
            continue

        if side == "put" and strike < spot:
            distance = spot - strike
            points.append((distance, iv))
        elif side == "call" and strike > spot:
            distance = strike - spot
            points.append((distance, iv))

    if len(points) < 2:
        return None

    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])

    # Linear regression: IV = a + b * distance
    if np.std(x) == 0:
        return None

    slope = float(np.polyfit(x, y, 1)[0])
    return round(slope, 6)


def _generate_interpretation(
    skew_shape: str, skew_25d: Optional[float],
) -> str:
    """Generate a human-readable interpretation of the skew."""
    parts = []

    if skew_shape == "put_skew":
        parts.append(
            "Pronounced put skew indicates elevated demand for downside protection. "
            "This is the most common pattern, especially in equity markets."
        )
    elif skew_shape == "smile":
        parts.append(
            "Volatility smile with elevated IV on both wings suggests the market "
            "is pricing significant tail risk in both directions."
        )
    elif skew_shape == "call_skew":
        parts.append(
            "Unusual call skew indicates elevated upside speculation or short squeeze risk. "
            "This is uncommon and may signal momentum-driven positioning."
        )
    else:
        parts.append(
            "Relatively flat IV curve suggests balanced supply/demand for options "
            "across strikes, with no strong directional hedging bias."
        )

    if skew_25d is not None:
        if abs(skew_25d) > 0.10:
            parts.append(f"25-delta skew of {skew_25d:.3f} is extreme.")
        elif abs(skew_25d) > 0.05:
            parts.append(f"25-delta skew of {skew_25d:.3f} is moderately elevated.")
        else:
            parts.append(f"25-delta skew of {skew_25d:.3f} is within normal range.")

    return " ".join(parts)


# ── Main tool function ──────────────────────────────────────


def get_iv_skew_analysis(
    ticker: str,
    expiry: Optional[str] = None,
    num_strikes: int = 10,
) -> Dict[str, Any]:
    """
    Analyze IV skew from live option chain data.

    Builds on get_option_chain() output to compute skew metrics:
    shape classification, 25-delta skew, gradient, and term structure skew.

    Args:
        ticker: Stock ticker symbol.
        expiry: Target expiration YYYYMMDD (default: nearest with >=7 DTE).
        num_strikes: Strikes above/below ATM (default: 10).

    Returns:
        Dict with skew metrics, per-strike data, and interpretation.
    """
    from .option_chain_tools import get_option_chain

    ticker = ticker.upper()

    # Get option chain data
    chain_data = get_option_chain(ticker, expiry=expiry, num_strikes=num_strikes)

    if "error" in chain_data:
        return chain_data

    spot = chain_data.get("spot_price", 0)
    calls = chain_data.get("chain", {}).get("calls", [])
    puts = chain_data.get("chain", {}).get("puts", [])

    if not calls and not puts:
        return {"error": "No option quotes available", "ticker": ticker}

    # Find ATM IV (nearest strike to spot)
    all_quotes = calls + puts
    atm_iv = None
    for q in sorted(calls, key=lambda x: abs(x.get("strike", 0) - spot)):
        if q.get("iv") is not None:
            atm_iv = q["iv"]
            break
    if atm_iv is None:
        for q in sorted(puts, key=lambda x: abs(x.get("strike", 0) - spot)):
            if q.get("iv") is not None:
                atm_iv = q["iv"]
                break

    if atm_iv is None or atm_iv <= 0:
        return {"error": "No ATM IV data available", "ticker": ticker}

    # OTM put avg IV (strikes below spot)
    otm_put_ivs = [q["iv"] for q in puts if q.get("iv") and q.get("strike", 0) < spot]
    otm_put_avg_iv = float(np.mean(otm_put_ivs)) if otm_put_ivs else atm_iv

    # OTM call avg IV (strikes above spot)
    otm_call_ivs = [q["iv"] for q in calls if q.get("iv") and q.get("strike", 0) > spot]
    otm_call_avg_iv = float(np.mean(otm_call_ivs)) if otm_call_ivs else atm_iv

    # Classify shape
    skew_shape = _classify_skew_shape(atm_iv, otm_put_avg_iv, otm_call_avg_iv)

    # 25-delta skew
    skew_25d = None
    skew_25d_detail = None
    put_25d = _find_nearest_delta(puts, -0.25)
    call_25d = _find_nearest_delta(calls, 0.25)

    if put_25d and call_25d and put_25d.get("iv") and call_25d.get("iv"):
        skew_25d = round(put_25d["iv"] - call_25d["iv"], 4)
        skew_25d_detail = {
            "put_25d_iv": put_25d["iv"],
            "put_25d_strike": put_25d["strike"],
            "call_25d_iv": call_25d["iv"],
            "call_25d_strike": call_25d["strike"],
        }

    # Skew gradient
    skew_gradient_puts = _compute_skew_gradient(puts, spot, "put")
    skew_gradient_calls = _compute_skew_gradient(calls, spot, "call")

    # Per-strike skew (where both call and put exist at same strike)
    call_iv_map = {q["strike"]: q.get("iv") for q in calls if q.get("strike")}
    put_iv_map = {q["strike"]: q.get("iv") for q in puts if q.get("strike")}
    common_strikes = sorted(set(call_iv_map.keys()) & set(put_iv_map.keys()))

    per_strike_skew = []
    for strike in common_strikes:
        c_iv = call_iv_map[strike]
        p_iv = put_iv_map[strike]
        if c_iv is not None and p_iv is not None:
            per_strike_skew.append({
                "strike": strike,
                "call_iv": c_iv,
                "put_iv": p_iv,
                "skew": round(p_iv - c_iv, 4),
            })

    # Term structure skew
    term_structure_skew = []
    for ts in chain_data.get("term_structure", []):
        c_iv = ts.get("atm_iv_call")
        p_iv = ts.get("atm_iv_put")
        if c_iv is not None and p_iv is not None:
            term_structure_skew.append({
                "expiry": ts["expiry"],
                "dte": ts["dte"],
                "atm_call_iv": c_iv,
                "atm_put_iv": p_iv,
                "skew": round(p_iv - c_iv, 4),
            })

    interpretation = _generate_interpretation(skew_shape, skew_25d)

    return {
        "ticker": ticker,
        "spot_price": spot,
        "selected_expiry": chain_data.get("selected_expiry"),
        "selected_dte": chain_data.get("selected_dte"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skew_shape": skew_shape,
        "atm_iv": round(atm_iv, 4),
        "otm_put_avg_iv": round(otm_put_avg_iv, 4),
        "otm_call_avg_iv": round(otm_call_avg_iv, 4),
        "skew_25d": skew_25d,
        "skew_25d_detail": skew_25d_detail,
        "skew_gradient_puts": skew_gradient_puts,
        "skew_gradient_calls": skew_gradient_calls,
        "per_strike_skew": per_strike_skew,
        "term_structure_skew": term_structure_skew,
        "interpretation": interpretation,
    }
