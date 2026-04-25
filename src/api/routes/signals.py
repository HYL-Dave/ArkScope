"""Signal detection routes."""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.signal_tools import (
    _prepare_news_df_for_signals,
    detect_anomalies,
    detect_event_chains,
    get_signal_factors,
    synthesize_signal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# Cross-sectional ranking maps URL-friendly factor names to the
# synthesizer's internal factor_type strings. ``volume_spike`` is the
# OUTPUT factor_type (``VOLUME_SPIKE``), distinct from the synthesizer's
# input bucket name ``volume_anomaly``. ``composite`` is special: it
# ranks by ``composite.score`` rather than a single factor's contribution.
_FACTOR_NAME_TO_TYPE: Dict[str, Optional[str]] = {
    "composite": None,
    "sector_momentum": "SECTOR_MOMENTUM",
    "event_chain": "EVENT_CHAIN",
    "sentiment_anomaly": "SENTIMENT_ANOMALY",
    "volume_spike": "VOLUME_SPIKE",
}

_VALID_UNIVERSES = ("watchlist", "alpha_picks")


def _validate_as_of_date(raw: Optional[str]) -> Optional[str]:
    """Validate YYYY-MM-DD format and that it parses to a real date."""
    if raw is None:
        return None
    if not _DATE_RE.match(raw):
        raise HTTPException(422, f"as_of_date must be YYYY-MM-DD, got: {raw!r}")
    try:
        date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(422, f"as_of_date is not a valid date: {raw!r}")
    return raw


def _resolve_universe(dal: DataAccessLayer, universe: str) -> List[str]:
    """Map universe name → deduplicated, uppercase ticker list.

    ``alpha_picks`` is intentionally deduped: the same symbol may have
    been picked multiple times (e.g. EAT, MFC, STRL across different
    cycles); cross-sectional ranking treats one ticker as one row.
    """
    if universe == "watchlist":
        wl = dal.get_watchlist(include_sectors=False)
        tickers = list(getattr(wl, "tickers", []) or [])
    elif universe == "alpha_picks":
        rows = dal.get_sa_portfolio(portfolio_status="current")
        tickers = [r.get("symbol") or "" for r in rows]
    else:
        raise HTTPException(422, f"unknown universe: {universe!r}")

    seen: set = set()
    out: List[str] = []
    for t in tickers:
        s = (t or "").strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _rank_value_for(factor: str, factors_result: dict) -> Optional[float]:
    """Pull the rank-eligible scalar out of a get_signal_factors result.

    Returns ``None`` when the requested factor is missing — the caller
    routes those tickers into ``missing_data_tickers`` rather than
    coercing them to a neutral score.
    """
    if factor == "composite":
        composite = factors_result.get("composite") or {}
        score = composite.get("score")
        return float(score) if score is not None else None
    target_type = _FACTOR_NAME_TO_TYPE.get(factor)
    if target_type is None:
        return None
    for f in factors_result.get("factors") or []:
        if f.get("factor_type") == target_type:
            v = f.get("contribution")
            return float(v) if v is not None else None
    return None


def _missing_reason(factors_result: dict, factor: str) -> Optional[str]:
    """Classify why a ticker is unrankable for the chosen factor."""
    dq = factors_result.get("data_quality") or {}
    if (dq.get("news_count") or 0) <= 0:
        return "no_news_in_window"
    if (dq.get("scored_news_count") or 0) <= 0:
        return "no_scored_news"
    target_type = _FACTOR_NAME_TO_TYPE.get(factor)
    if factor != "composite" and target_type in (dq.get("missing_factors") or []):
        return f"factor_not_computed:{factor}"
    if factor == "composite":
        composite = factors_result.get("composite") or {}
        if composite.get("score") is None:
            return "composite_unavailable"
    if dq.get("errors"):
        return "errors_during_computation"
    return None


# NOTE: static routes (e.g. /factor-rank) MUST be declared before the
# dynamic /{ticker} catch-all. Starlette matches in declaration order, so
# /signals/factor-rank would otherwise be captured as ticker="factor-rank".
# Regression test in tests/test_signal_factors_p1.py uses TestClient to
# guard this ordering.


@router.get("/factor-rank")
def factor_rank(
    universe: str = Query("watchlist", description="watchlist | alpha_picks"),
    factor: str = Query(
        "composite",
        description=(
            "Rank by composite or one of the synthesizer factor types "
            "(sector_momentum, event_chain, sentiment_anomaly, volume_spike)."
        ),
    ),
    top: int = Query(20, ge=1, le=200),
    days: int = Query(30, ge=1, le=9999),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "Anchor date YYYY-MM-DD. Default = global latest date in the "
            "preloaded news dataset (one anchor for all tickers, so the "
            "cross-section is reproducible)."
        ),
    ),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Cross-sectional rank of a universe by an existing signal factor.

    Recommendation breakdown only — this is *not* a price prediction.
    Tickers without enough data show up explicitly in
    ``missing_data_tickers`` with a reason rather than being coerced to
    a neutral HOLD. ``SECTOR_MOMENTUM`` is shared across same-sector
    tickers, so its ranking reflects sector-level flow rather than
    ticker-specific conviction.
    """
    if factor not in _FACTOR_NAME_TO_TYPE:
        raise HTTPException(
            422,
            f"unknown factor: {factor!r}. allowed={sorted(_FACTOR_NAME_TO_TYPE)}",
        )
    if universe not in _VALID_UNIVERSES:
        raise HTTPException(
            422,
            f"unknown universe: {universe!r}. allowed={list(_VALID_UNIVERSES)}",
        )
    anchor_param = _validate_as_of_date(as_of_date)

    tickers = _resolve_universe(dal, universe)
    if not tickers:
        return {
            "universe": universe,
            "factor": factor,
            "as_of_date": anchor_param,
            "ticker_count_total": 0,
            "ticker_count_ranked": 0,
            "ticker_count_missing_data": 0,
            "missing_data_tickers": [],
            "ranked": [],
            "errors": [],
            "notes": _factor_notes(factor),
        }

    # One news_df preload for the whole universe; per-ticker calls share
    # it via the news_df= argument so we never re-read DAL per ticker.
    shared_df = _prepare_news_df_for_signals(dal, ticker=None, days=days)

    # Single global anchor: either the caller-supplied date or the latest
    # date in the preloaded df. Without a fixed anchor, each ticker would
    # use its own latest date and the cross-section would mix time slices.
    if anchor_param is not None:
        global_anchor = anchor_param
    elif not shared_df.empty:
        global_anchor = str(shared_df["date"].max())
    else:
        global_anchor = date.today().isoformat()

    ranked: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    errors: List[str] = []

    for ticker in tickers:
        try:
            result = get_signal_factors(
                dal,
                ticker=ticker,
                days=days,
                as_of_date=global_anchor,
                news_df=shared_df,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("factor-rank: get_signal_factors failed for %s: %s", ticker, exc)
            missing.append({"ticker": ticker, "reason": f"exception:{exc}"})
            continue

        reason = _missing_reason(result, factor)
        if reason:
            missing.append({"ticker": ticker, "reason": reason})
            continue
        score = _rank_value_for(factor, result)
        if score is None:
            missing.append({"ticker": ticker, "reason": f"score_unavailable:{factor}"})
            continue

        composite = result.get("composite") or {}
        dq = result.get("data_quality") or {}
        ranked.append({
            "ticker": ticker,
            "score": round(float(score), 4),
            "composite_score": composite.get("score"),
            "action": composite.get("action"),
            "confidence": composite.get("confidence"),
            "risk_level": composite.get("risk_level"),
            "sector": result.get("sector"),
            "news_count": dq.get("news_count"),
            "scored_news_count": dq.get("scored_news_count"),
        })

        # Capture per-ticker errors at the top level so callers don't
        # have to walk the full result list to know something went wrong.
        if dq.get("errors"):
            errors.extend(f"{ticker}: {e}" for e in dq["errors"])

    ranked.sort(key=lambda r: r["score"], reverse=True)
    truncated = ranked[: max(1, int(top))]
    for i, row in enumerate(truncated, start=1):
        row["rank"] = i

    return {
        "universe": universe,
        "factor": factor,
        "as_of_date": global_anchor,
        "ticker_count_total": len(tickers),
        "ticker_count_ranked": len(ranked),
        "ticker_count_missing_data": len(missing),
        "missing_data_tickers": missing,
        "ranked": truncated,
        "errors": errors,
        "notes": _factor_notes(factor),
    }


def _factor_notes(factor: str) -> List[str]:
    """Per-factor caveats surfaced in the response so callers don't
    have to remember them."""
    notes: List[str] = [
        "Recommendation breakdown only — not a price prediction.",
    ]
    if factor == "sector_momentum":
        notes.append(
            "SECTOR_MOMENTUM is sector-shared. Same-sector tickers will get "
            "the same contribution; do not interpret as ticker-specific conviction."
        )
    if factor == "composite":
        notes.append(
            "Composite mixes weighted contributions from all factors. "
            "Signal-validation (forward-return decile analysis) is not yet wired — "
            "do not size positions on this rank alone."
        )
    return notes


# Dynamic ticker routes follow. They are registered AFTER /factor-rank so
# Starlette's first-match-wins ordering doesn't capture /factor-rank as
# ticker="factor-rank". /{ticker}/anomalies and /{ticker}/event-chains
# have an extra path segment so they don't collide with /{ticker}, but
# any future static /signals/<word> route must also be declared above
# this point.


@router.get("/{ticker}")
def signal_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    strategy: Optional[str] = Query(None),
    as_of_date: Optional[str] = Query(None, description="Anchor date YYYY-MM-DD (default: latest in data)"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Synthesize a multi-factor trading signal for a ticker."""
    result = synthesize_signal(
        dal, ticker=ticker, days=days, strategy=strategy,
        as_of_date=_validate_as_of_date(as_of_date),
    )
    return result.model_dump()


@router.get("/{ticker}/anomalies")
def anomalies_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    as_of_date: Optional[str] = Query(None, description="Anchor date YYYY-MM-DD (default: latest in data)"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Detect sentiment and volume anomalies for a ticker."""
    return detect_anomalies(
        dal, ticker=ticker, days=days, as_of_date=_validate_as_of_date(as_of_date),
    )


@router.get("/{ticker}/event-chains")
def event_chains_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Detect event chain patterns for a ticker."""
    return detect_event_chains(dal, ticker=ticker, days=days)