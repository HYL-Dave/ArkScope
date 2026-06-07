"""
Analyst consensus route — the credible, provider-native rating that replaces the
old ArkScope LLM "sentiment" in the cockpit.

Lazy + daily-cached: a row fetches its own consensus on demand; the first fetch
hits Finnhub (throttled ~1/sec) and caches for a day, so re-loads are instant.
Source-labeled "finnhub" — never presented as an ArkScope score.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.analyst_consensus import AnalystConsensusCache
from src.api.dependencies import get_consensus_cache
from src.env_keys import ensure_env_loaded

router = APIRouter(tags=["analysis"])


@router.get("/analysis/consensus/{ticker}")
def analyst_consensus(
    ticker: str,
    cache: AnalystConsensusCache = Depends(get_consensus_cache),
):
    """Analyst consensus for one ticker (cached daily). Never errors — the
    response carries a ``status`` (ok / cached / no_coverage / rate_limited /
    missing_key / provider_error) so the UI can tell "no coverage" from "key
    missing" / "API down". LIGHTWEIGHT: hits only Finnhub
    /stock/recommendation, not the full 4-endpoint analyst tool (which stays
    for detail / AI-card evidence)."""
    ensure_env_loaded()
    from src.analyst_consensus import fetch_recommendation_consensus

    return cache.get_or_fetch(ticker, fetch_recommendation_consensus)
