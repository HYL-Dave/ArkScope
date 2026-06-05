"""
Profile-state (research-universe lifecycle) + cockpit watchlist routes.

Reads merge PostgreSQL market data (via the DAL) with the local SQLite user
state (``ProfileStateStore``). Writes funnel through the ``profile_state_write``
permission choke-point.

``/cockpit/watchlist`` is the stable cockpit DTO: every row always carries the
full field set (explicit ``null`` / ``0`` / ``[]`` for missing data), unlike the
agent-tool-shaped ``/overview`` which omits absent fields. The substrate is the
multi-list model (ProductSpec §168); the v0 surface here renders a single
aggregate "All Active" view + an Archived filter.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_dal, get_profile_store
from src.api.permissions import require_profile_state_write
from src.profile_state import ProfileStateStore, _norm
from src.tools.analysis_tools import get_watchlist_overview
from src.tools.data_access import DataAccessLayer

router = APIRouter(tags=["profile"])


class ArchiveBody(BaseModel):
    archived: bool


class NoteBody(BaseModel):
    body: str = Field(min_length=1)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.get("/cockpit/watchlist")
def cockpit_watchlist(
    include_archived: bool = False,
    dal: DataAccessLayer = Depends(get_dal),
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Stable cockpit watchlist: market data joined with local user state.

    Archived tickers are hidden by default (``include_archived=true`` reveals
    them). The ticker universe is synced into the profile-state substrate from
    the overview's groups (additive, archive-preserving) on each load.
    """
    overview = get_watchlist_overview(dal)
    rows = overview.get("tickers", [])
    as_of = overview.get("date")

    require_profile_state_write("sync_universe", {"source": "overview", "rows": len(rows)})
    store.sync_universe(rows)
    agg = store.get_aggregate([r.get("ticker", "") for r in rows])

    out_rows: list[dict] = []
    archived_count = 0
    for r in rows:
        ticker = r.get("ticker", "")
        a = agg.get(_norm(ticker))
        archived = a.archived if a else False
        if archived:
            archived_count += 1
        if archived and not include_archived:
            continue
        out_rows.append(
            {
                "ticker": ticker,
                "group": r.get("group"),
                "priority": r.get("priority"),
                "latest_close": r.get("latest_close"),
                "change_7d_pct": r.get("change_7d_pct"),
                "news_count_7d": r.get("news_count_7d", 0),
                "sentiment_mean": r.get("sentiment_mean"),
                "bullish_ratio": r.get("bullish_ratio"),
                "lists": a.lists if a else [],
                "archived": archived,
                "tags": [],  # tag store deferred (UI defers tags too)
                "note_count": a.note_count if a else 0,
                # Per-source freshness is TBD; expose the overview as-of date so
                # the field is part of the stable contract from day one.
                "freshness": as_of,
                # Reserved: the overview nulls missing fields rather than
                # reporting per-ticker errors. Populated once it surfaces them.
                "per_ticker_error": None,
            }
        )

    return {
        "as_of": as_of,
        "generated_at": _utcnow(),
        "total": len(rows),
        "shown": len(out_rows),
        "archived_count": archived_count,
        "include_archived": include_archived,
        "rows": out_rows,
    }


@router.get("/profile/lists")
def profile_lists(
    include_archived: bool = False,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Named watchlists/tabs in the profile-state substrate (§168).

    The v0 cockpit does not render these as tabs yet, but they are populated by
    the universe sync and exposed so the multi-tab surface can be built later.
    """
    return {"lists": [asdict(li) for li in store.list_watchlists(include_archived=include_archived)]}


@router.get("/profile/tickers/{ticker}/state")
def get_ticker_state(
    ticker: str,
    store: ProfileStateStore = Depends(get_profile_store),
):
    return asdict(store.get_ticker(ticker))


@router.post("/profile/tickers/{ticker}/archive")
def set_ticker_archived(
    ticker: str,
    body: ArchiveBody,
    store: ProfileStateStore = Depends(get_profile_store),
):
    action = "archive" if body.archived else "restore"
    require_profile_state_write(action, {"ticker": ticker})
    try:
        agg = store.archive_ticker(ticker) if body.archived else store.restore_ticker(ticker)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0] if e.args else str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return asdict(agg)


@router.get("/profile/tickers/{ticker}/notes")
def list_ticker_notes(
    ticker: str,
    store: ProfileStateStore = Depends(get_profile_store),
):
    return {
        "ticker": _norm(ticker),
        "notes": [asdict(n) for n in store.list_notes(ticker)],
    }


@router.post("/profile/tickers/{ticker}/notes")
def add_ticker_note(
    ticker: str,
    body: NoteBody,
    store: ProfileStateStore = Depends(get_profile_store),
):
    require_profile_state_write("add_note", {"ticker": ticker})
    try:
        return asdict(store.add_note(ticker, body.body))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/profile/tickers/{ticker}/notes/{note_id}")
def delete_ticker_note(
    ticker: str,
    note_id: int,
    store: ProfileStateStore = Depends(get_profile_store),
):
    require_profile_state_write("delete_note", {"ticker": ticker, "note_id": note_id})
    if not store.delete_note(ticker, note_id):
        raise HTTPException(status_code=404, detail="note not found")
    return {"deleted": True, "id": note_id}
