"""
Symbol search — local-first ticker/name autocomplete for add-ticker.

Backed by the SEC-seeded local symbol catalog (``src.symbol_catalog``), so typing
a keyword returns instant suggestions + catches typos without a per-keystroke API
call. PURE READ. Each hit is flagged ``tracked`` when it belongs to the accepted
active-universe snapshot, so the UI can show what's new vs already tracked.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src import symbol_catalog
from src.active_universe import ActiveUniverseUnavailable, build_active_universe_snapshot
from src.api.dependencies import get_profile_store
from src.profile_state import ProfileStateStore, _norm

router = APIRouter(tags=["symbols"])


@router.get("/symbols/search")
def symbols_search(
    q: str = "",
    limit: int = 20,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Autocomplete ticker/company-name matches for ``q`` (≤ ``limit``)."""
    try:
        snapshot = build_active_universe_snapshot(profile_db=store.db_path)
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from None
    hits = symbol_catalog.search(q, limit=limit, active_tickers=snapshot.tickers)
    tracked = set(snapshot.tickers)
    return {
        "q": q,
        "results": [
            {"ticker": h["ticker"], "name": h["name"], "tracked": _norm(h["ticker"]) in tracked}
            for h in hits
        ],
    }
