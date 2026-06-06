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

Read endpoints are PURE READS — they never mutate profile state. Seeding the
list substrate from existing categories (user_profile groups + tickers_core
tiers) is an EXPLICIT, gated action (``POST /profile/import-universe``), so
opening a page never triggers a ``profile_state_write``.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_dal, get_profile_store
from src.api.permissions import require_profile_state_write
from src.profile_state import ProfileStateStore, _norm
from src.tools.analysis_tools import get_universe_summaries, get_watchlist_overview
from src.tools.data_access import DataAccessLayer
from src.universe_config import tier_named_lists

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

    PURE READ. Archived tickers are hidden by default (``include_archived=true``
    reveals them). Tickers present in the overview but not yet imported into the
    substrate simply show empty ``lists`` — run ``POST /profile/import-universe``
    to seed lists from existing categories. This endpoint never writes.
    """
    overview = get_watchlist_overview(dal)
    rows = overview.get("tickers", [])
    as_of = overview.get("date")

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


class ImportBody(BaseModel):
    include_groups: bool = True  # user_profile watchlists (Holdings / Interested / themes)
    include_tiers: bool = True   # config/tickers_core.json tier categories (the ~130 universe)


@router.post("/profile/import-universe")
def import_universe(
    body: ImportBody | None = None,
    dal: DataAccessLayer = Depends(get_dal),
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Seed the multi-list substrate from existing categories (EXPLICIT + gated).

    Sources (both on by default): user_profile watchlist groups (via the
    overview) and the ``tickers_core.json`` tiers. Additive and
    archive-preserving — safe to re-run; it never resurrects an archived
    membership or duplicates a list.
    """
    opts = body or ImportBody()
    named: list[dict] = []
    if opts.include_groups:
        overview = get_watchlist_overview(dal)
        by_group: dict[str, list[str]] = {}
        for r in overview.get("tickers", []):
            group = (r.get("group") or "Watchlist").strip() or "Watchlist"
            t = _norm(r.get("ticker"))
            if t:
                by_group.setdefault(group, []).append(t)
        named.extend({"name": g, "tickers": ts} for g, ts in by_group.items())
    if opts.include_tiers:
        named.extend(tier_named_lists())

    require_profile_state_write(
        "import_universe",
        {"groups": opts.include_groups, "tiers": opts.include_tiers, "lists": len(named)},
    )
    summary = store.import_lists(named)
    return {
        "imported": summary,
        "lists": [asdict(li) for li in store.list_watchlists()],
    }


@router.get("/profile/universe")
def universe(
    include_archived: bool = True,
    dal: DataAccessLayer = Depends(get_dal),
    store: ProfileStateStore = Depends(get_profile_store),
):
    """All imported tickers (the full tracked universe), not just the curated
    overview. PURE READ.

    Market summary comes from a cheap batch query over the whole universe
    (``get_universe_summaries`` — two queries, not one per ticker), enriched with
    the overview's group / priority / sentiment where the ticker is curated.
    ``has_summary`` is True when price data exists for the ticker in the window;
    universe tickers with no price bars render with null fields.
    """
    overview = get_watchlist_overview(dal)
    by_ticker = {r.get("ticker"): r for r in overview.get("tickers", []) if r.get("ticker")}
    as_of = overview.get("date")
    summaries = get_universe_summaries(dal)  # {TICKER: {latest_close, change_pct, ...}}

    tickers = sorted(set(store.all_tickers()) | set(by_ticker))
    agg = store.get_aggregate(tickers)

    rows: list[dict] = []
    archived_count = 0
    for t in tickers:
        a = agg.get(_norm(t))
        archived = a.archived if a else False
        if archived:
            archived_count += 1
        if archived and not include_archived:
            continue
        ov = by_ticker.get(t)
        s = summaries.get(_norm(t))
        # has_summary: real market data available (batch price OR curated overview)
        has_summary = bool(s) or ov is not None
        # price prefers the batch summary; falls back to the overview's value
        latest_close = (s.get("latest_close") if s else None)
        change_7d = (s.get("change_pct") if s else None)
        news_7d = (s.get("news_count_7d") if s else None)
        if latest_close is None and ov:
            latest_close = ov.get("latest_close")
        if change_7d is None and ov:
            change_7d = ov.get("change_7d_pct")
        if news_7d is None:
            news_7d = ov.get("news_count_7d", 0) if ov else 0
        rows.append(
            {
                "ticker": t,
                "has_summary": has_summary,
                "group": ov.get("group") if ov else None,
                "priority": ov.get("priority") if ov else None,
                "latest_close": latest_close,
                "change_7d_pct": change_7d,
                "news_count_7d": news_7d,
                # sentiment/bullish remain overview-only (curated) for now
                "sentiment_mean": ov.get("sentiment_mean") if ov else None,
                "bullish_ratio": ov.get("bullish_ratio") if ov else None,
                "lists": a.lists if a else [],
                "all_lists": a.all_lists if a else [],
                "archived_lists": a.archived_lists if a else [],
                "archived": archived,
                "note_count": a.note_count if a else 0,
            }
        )

    return {
        "as_of": as_of,
        "generated_at": _utcnow(),
        "total": len(tickers),
        "shown": len(rows),
        "archived_count": archived_count,
        "summarized": sum(1 for r in rows if r["has_summary"]),
        "rows": rows,
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


class ListCreateBody(BaseModel):
    name: str = Field(min_length=1)
    kind: str | None = None


class ListRenameBody(BaseModel):
    name: str = Field(min_length=1)


class MemberBody(BaseModel):
    ticker: str = Field(min_length=1)


@router.post("/profile/lists")
def create_list(
    body: ListCreateBody,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Create a user list. 400 if the name already exists."""
    require_profile_state_write("create_list", {"name": body.name})
    try:
        return asdict(store.create_list(body.name, body.kind))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/profile/lists/{list_id}")
def rename_list(
    list_id: int,
    body: ListRenameBody,
    store: ProfileStateStore = Depends(get_profile_store),
):
    require_profile_state_write("rename_list", {"list_id": list_id, "name": body.name})
    try:
        return asdict(store.rename_list(list_id, body.name))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0] if e.args else str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/profile/lists/{list_id}")
def delete_list(
    list_id: int,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Delete a list (and its memberships); tickers survive in other lists."""
    require_profile_state_write("delete_list", {"list_id": list_id})
    if not store.delete_list(list_id):
        raise HTTPException(status_code=404, detail=f"list {list_id} not found")
    return {"deleted": True, "id": list_id}


@router.post("/profile/lists/{list_id}/members")
def add_member(
    list_id: int,
    body: MemberBody,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Add a ticker to a specific list (reactivates an archived membership)."""
    require_profile_state_write("add_member", {"list_id": list_id, "ticker": body.ticker})
    try:
        store.add_member(list_id, body.ticker)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0] if e.args else str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return asdict(store.get_ticker(body.ticker))


@router.delete("/profile/lists/{list_id}/members/{ticker}")
def remove_member(
    list_id: int,
    ticker: str,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Remove a ticker from THIS list only (distinct from global archive)."""
    require_profile_state_write("remove_member", {"list_id": list_id, "ticker": ticker})
    if not store.remove_member(list_id, ticker):
        raise HTTPException(status_code=404, detail="membership not found")
    return {"removed": True, "list_id": list_id, "ticker": _norm(ticker)}


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
