"""
Option chain analysis tool (Batch 2a).

Provides get_option_chain() — live option chain from IBKR with computed metrics:
- Available expirations summary
- Call/put quotes around ATM for selected expiry
- Put/Call ratio (volume + OI), max pain, OI concentration
- IV term structure across expirations
- Bid-ask spread quality assessment
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── IBKR singleton (lazy) ──────────────────────────────────

_ibkr = None


def _get_ibkr():
    """Get or create IBKR singleton connection (separate client_id)."""
    global _ibkr
    if _ibkr is not None:
        try:
            if _ibkr._ib and _ibkr._ib.isConnected():
                return _ibkr
        except Exception:
            pass
        _ibkr = None

    from data_sources.ibkr_source import IBKRDataSource

    base_id = int(os.getenv("IBKR_CLIENT_ID", "1"))
    _ibkr = IBKRDataSource(client_id=base_id + 10, readonly=True)
    _ibkr.connect()
    return _ibkr


# ── Helper functions ───────────────────────────────────────


def _select_nearest_expiry(
    expirations: List[str], min_dte: int = 7
) -> Optional[str]:
    """Pick the nearest expiry with at least min_dte days to expiration."""
    today = date.today()
    candidates = []
    for exp in expirations:
        try:
            exp_date = datetime.strptime(exp, "%Y%m%d").date()
            dte = (exp_date - today).days
            if dte >= min_dte:
                candidates.append((dte, exp))
        except ValueError:
            continue
    if not candidates:
        # Fallback: pick the nearest even if < min_dte
        for exp in expirations:
            try:
                exp_date = datetime.strptime(exp, "%Y%m%d").date()
                dte = (exp_date - today).days
                if dte > 0:
                    candidates.append((dte, exp))
            except ValueError:
                continue
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _calculate_dte(expiry: str) -> int:
    """Calculate days to expiration from YYYYMMDD string."""
    try:
        exp_date = datetime.strptime(expiry, "%Y%m%d").date()
        return (exp_date - date.today()).days
    except ValueError:
        return 0


def _calculate_max_pain(
    calls: List[Dict], puts: List[Dict], all_strikes: List[float]
) -> Optional[float]:
    """Find strike where total option holder loss is maximized (= max pain)."""
    if not calls and not puts:
        return None

    call_oi = {q["strike"]: q.get("oi") or 0 for q in calls}
    put_oi = {q["strike"]: q.get("oi") or 0 for q in puts}

    min_pain = float("inf")
    max_pain_strike = None

    for settle in all_strikes:
        pain = 0
        for s, oi in call_oi.items():
            if settle > s:
                pain += (settle - s) * oi * 100
        for s, oi in put_oi.items():
            if settle < s:
                pain += (s - settle) * oi * 100
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = settle

    return max_pain_strike


def _format_quote(q) -> Dict[str, Any]:
    """Convert OptionQuote dataclass to simplified dict."""
    bid = q.bid or 0
    ask = q.ask or 0
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
    spread_pct = round(((ask - bid) / mid) * 100, 2) if mid > 0 else None

    return {
        "strike": q.strike,
        "bid": q.bid,
        "ask": q.ask,
        "last": q.last,
        "volume": q.volume,
        "oi": q.open_interest,
        "iv": round(q.implied_vol, 4) if q.implied_vol else None,
        "delta": round(q.delta, 4) if q.delta else None,
        "spread_pct": spread_pct,
    }


def _select_atm_strikes(
    all_strikes: List[float], spot: float, num_strikes: int
) -> List[float]:
    """Select num_strikes above and below ATM (total up to 2*num_strikes)."""
    sorted_strikes = sorted(all_strikes)
    # Find ATM index
    atm_idx = min(range(len(sorted_strikes)), key=lambda i: abs(sorted_strikes[i] - spot))
    low = max(0, atm_idx - num_strikes)
    high = min(len(sorted_strikes), atm_idx + num_strikes + 1)
    return sorted_strikes[low:high]


def _select_term_structure_expiries(
    expirations: List[str], max_count: int
) -> List[str]:
    """Select evenly-spaced expirations for term structure."""
    today = date.today()
    valid = []
    for exp in expirations:
        try:
            exp_date = datetime.strptime(exp, "%Y%m%d").date()
            dte = (exp_date - today).days
            if dte > 0:
                valid.append((dte, exp))
        except ValueError:
            continue
    valid.sort()
    if len(valid) <= max_count:
        return [exp for _, exp in valid]
    # Evenly space
    step = len(valid) / max_count
    return [valid[int(i * step)][1] for i in range(max_count)]


# ── Main tool function ─────────────────────────────────────


def get_option_chain(
    ticker: str,
    expiry: Optional[str] = None,
    num_strikes: int = 10,
    max_expirations_for_term_structure: int = 6,
) -> Dict[str, Any]:
    """
    Get live option chain from IBKR with analysis metrics.

    Returns P/C ratio, max pain, OI concentration, IV term structure,
    and bid-ask quality assessment. Requires IBKR gateway running.

    Args:
        ticker: Stock ticker symbol.
        expiry: Target expiration (YYYYMMDD). Default: nearest with >=7 DTE.
        num_strikes: Strikes above/below ATM to fetch (default: 10).
        max_expirations_for_term_structure: Max expirations for IV term structure.

    Returns:
        Dict with chain data, metrics, OI concentration, and term structure.
    """
    ticker = ticker.upper()
    api_calls = 0

    try:
        ibkr = _get_ibkr()
    except Exception as e:
        return {"error": f"IBKR connection failed: {e}", "ticker": ticker}

    # Step 1: Get spot price + chain params
    try:
        quote = ibkr.get_current_quote(ticker)
        api_calls += 1
        spot = None
        if quote:
            spot = quote.get("last") or quote.get("close")
        if not spot:
            return {"error": f"Could not get spot price for {ticker}", "ticker": ticker}
    except Exception as e:
        return {"error": f"Failed to get spot price: {e}", "ticker": ticker}

    try:
        chain_params_list = ibkr.get_option_chain_params(ticker)
        api_calls += 1
        if not chain_params_list:
            return {"error": f"No option chain found for {ticker}", "ticker": ticker}
        # Use SMART exchange (largest strike/expiry set)
        chain_params = max(chain_params_list, key=lambda p: len(p.expirations))
        all_expirations = sorted(chain_params.expirations)
        all_strikes = sorted(chain_params.strikes)
    except Exception as e:
        return {"error": f"Failed to get chain params: {e}", "ticker": ticker}

    # Step 2: Select target expiry
    selected_expiry = expiry or _select_nearest_expiry(all_expirations)
    if not selected_expiry:
        return {"error": "No valid expirations found", "ticker": ticker}
    selected_dte = _calculate_dte(selected_expiry)

    # Expirations summary
    expirations_summary = [
        {"expiry": exp, "dte": _calculate_dte(exp)}
        for exp in all_expirations[:20]  # Cap at 20 for readability
        if _calculate_dte(exp) > 0
    ]

    # Step 3: Select ATM strikes
    strikes = _select_atm_strikes(all_strikes, spot, num_strikes)
    if not strikes:
        return {"error": "No valid strikes around ATM", "ticker": ticker}

    # Step 4: Fetch call + put quotes
    call_quotes = []
    put_quotes = []
    try:
        raw_calls = ibkr.get_option_chain_quotes(
            ticker, selected_expiry, strikes, right="C",
            delayed=True, max_strikes=len(strikes),
        )
        api_calls += len(strikes)
        call_quotes = [_format_quote(q) for q in raw_calls if q]
    except Exception as e:
        logger.warning(f"Failed to get call quotes: {e}")

    try:
        raw_puts = ibkr.get_option_chain_quotes(
            ticker, selected_expiry, strikes, right="P",
            delayed=True, max_strikes=len(strikes),
        )
        api_calls += len(strikes)
        put_quotes = [_format_quote(q) for q in raw_puts if q]
    except Exception as e:
        logger.warning(f"Failed to get put quotes: {e}")

    # Step 5: IV term structure
    term_structure = []
    ts_expiries = _select_term_structure_expiries(
        all_expirations, max_expirations_for_term_structure
    )
    # Find ATM strike
    atm_strike = min(all_strikes, key=lambda s: abs(s - spot))

    for ts_exp in ts_expiries:
        ts_entry = {
            "expiry": ts_exp,
            "dte": _calculate_dte(ts_exp),
            "atm_iv_call": None,
            "atm_iv_put": None,
        }
        try:
            cq = ibkr.get_option_quote(
                ticker, ts_exp, atm_strike, "C", delayed=True
            )
            api_calls += 1
            if cq and cq.implied_vol:
                ts_entry["atm_iv_call"] = round(cq.implied_vol, 4)
        except Exception:
            pass
        try:
            pq = ibkr.get_option_quote(
                ticker, ts_exp, atm_strike, "P", delayed=True
            )
            api_calls += 1
            if pq and pq.implied_vol:
                ts_entry["atm_iv_put"] = round(pq.implied_vol, 4)
        except Exception:
            pass
        term_structure.append(ts_entry)

    # Step 6: Compute derived metrics
    total_call_vol = sum(q.get("volume") or 0 for q in call_quotes)
    total_put_vol = sum(q.get("volume") or 0 for q in put_quotes)
    total_call_oi = sum(q.get("oi") or 0 for q in call_quotes)
    total_put_oi = sum(q.get("oi") or 0 for q in put_quotes)

    pc_ratio_volume = (
        round(total_put_vol / total_call_vol, 3)
        if total_call_vol > 0
        else None
    )
    pc_ratio_oi = (
        round(total_put_oi / total_call_oi, 3)
        if total_call_oi > 0
        else None
    )

    max_pain_strike = _calculate_max_pain(call_quotes, put_quotes, strikes)

    # Bid-ask spread quality
    spreads = [
        q["spread_pct"]
        for q in call_quotes + put_quotes
        if q.get("spread_pct") is not None
    ]
    avg_spread_pct = round(sum(spreads) / len(spreads), 2) if spreads else None

    liquid_strikes = sum(
        1 for q in call_quotes + put_quotes if (q.get("bid") or 0) > 0
    )

    # OI concentration (top 5 by OI)
    call_by_oi = sorted(call_quotes, key=lambda q: q.get("oi") or 0, reverse=True)
    put_by_oi = sorted(put_quotes, key=lambda q: q.get("oi") or 0, reverse=True)

    return {
        "ticker": ticker,
        "spot_price": spot,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "expirations_summary": expirations_summary,
        "selected_expiry": selected_expiry,
        "selected_dte": selected_dte,
        "chain": {
            "calls": call_quotes,
            "puts": put_quotes,
        },
        "metrics": {
            "pc_ratio_volume": pc_ratio_volume,
            "pc_ratio_oi": pc_ratio_oi,
            "max_pain_strike": max_pain_strike,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "avg_spread_pct": avg_spread_pct,
            "liquid_strikes": liquid_strikes,
        },
        "oi_concentration": {
            "calls": [
                {"strike": q["strike"], "oi": q["oi"]}
                for q in call_by_oi[:5]
                if (q.get("oi") or 0) > 0
            ],
            "puts": [
                {"strike": q["strike"], "oi": q["oi"]}
                for q in put_by_oi[:5]
                if (q.get("oi") or 0) > 0
            ],
        },
        "term_structure": term_structure,
        "data_quality": {
            "api_calls_made": api_calls,
            "quotes_received": len(call_quotes) + len(put_quotes),
            "data_type": "delayed_15min",
        },
    }
