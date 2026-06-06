"""
Symbol search — local-first ticker/name autocomplete for add-ticker.

Backed by the SEC-seeded local symbol catalog (``src.symbol_catalog``), so typing
a keyword returns instant suggestions + catches typos without a per-keystroke API
call. PURE READ. Each hit is flagged ``tracked`` (already a member of some list)
so the UI can show what's new vs already in the universe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src import symbol_catalog
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
    hits = symbol_catalog.search(q, limit=limit)
    tracked = set(store.all_tickers())
    return {
        "q": q,
        "results": [
            {"ticker": h["ticker"], "name": h["name"], "tracked": _norm(h["ticker"]) in tracked}
            for h in hits
        ],
    }
