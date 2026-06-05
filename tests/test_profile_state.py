"""Tests for the local profile-state store (multi-list) and its API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes.profile import (
    ArchiveBody,
    NoteBody,
    add_ticker_note,
    cockpit_watchlist,
    delete_ticker_note,
    list_ticker_notes,
    profile_lists,
    set_ticker_archived,
)
from src.profile_state import ProfileStateStore

# A canned /overview payload so the cockpit-DTO route never touches the DB.
CANNED_OVERVIEW = {
    "date": "2026-06-05",
    "ticker_count": 3,
    "tickers": [
        {
            "ticker": "AAPL", "group": "Holdings", "priority": "high",
            "latest_close": 200.0, "change_7d_pct": 1.5, "news_count_7d": 0,
            "sentiment_mean": None, "bullish_ratio": 0,
        },
        {
            "ticker": "MSFT", "group": "Holdings", "priority": "medium",
            "latest_close": 410.0, "change_7d_pct": -2.0, "news_count_7d": 4,
            "sentiment_mean": 0.3, "bullish_ratio": 0.5,
        },
        {
            "ticker": "TSLA", "group": "Interested", "priority": "low",
            "latest_close": None, "change_7d_pct": None, "news_count_7d": 1,
            "sentiment_mean": -0.1, "bullish_ratio": 0.25,
        },
    ],
}

SEED_ROWS = CANNED_OVERVIEW["tickers"]


# --- store unit tests -----------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    return ProfileStateStore(tmp_path / "profile_state.db")


def test_sync_universe_creates_lists_and_memberships(store):
    store.sync_universe(SEED_ROWS)
    lists = {li.name: li for li in store.list_watchlists()}
    assert set(lists) == {"Holdings", "Interested"}
    assert lists["Holdings"].kind == "holdings"
    assert lists["Holdings"].active_count == 2  # AAPL, MSFT
    assert lists["Interested"].active_count == 1  # TSLA

    agg = store.get_aggregate(["AAPL", "TSLA"])
    assert agg["AAPL"].lists == ["Holdings"]
    assert agg["AAPL"].archived is False
    assert agg["TSLA"].lists == ["Interested"]


def test_sync_universe_is_idempotent_and_archive_preserving(store):
    store.sync_universe(SEED_ROWS)
    store.archive_ticker("AAPL")
    # Re-sync must not resurrect the archived membership nor duplicate lists.
    store.sync_universe(SEED_ROWS)
    assert len({li.name for li in store.list_watchlists()}) == 2
    assert store.get_ticker("AAPL").archived is True


def test_default_aggregate_for_unknown_ticker(store):
    agg = store.get_ticker("NVDA")
    assert agg.ticker == "NVDA"
    assert agg.archived is False
    assert agg.lists == []
    assert agg.note_count == 0


def test_archive_restore_roundtrip(store):
    store.sync_universe(SEED_ROWS)
    a = store.archive_ticker("aapl")
    assert a.archived is True
    assert a.lists == []  # no active membership while archived
    assert store.get_ticker("AAPL").archived is True

    a = store.restore_ticker("AAPL")
    assert a.archived is False
    assert a.lists == ["Holdings"]


def test_notes_add_list_count_delete(store):
    n1 = store.add_note("aapl", "first thesis")
    n2 = store.add_note("AAPL", "second note")
    assert {n1.ticker, n2.ticker} == {"AAPL"}

    notes = store.list_notes("AAPL")
    assert [n.body for n in notes] == ["second note", "first thesis"]  # newest first
    assert store.get_ticker("AAPL").note_count == 2

    assert store.delete_note("AAPL", n1.id) is True
    assert store.delete_note("AAPL", n1.id) is False  # already gone
    assert store.get_ticker("AAPL").note_count == 1


def test_add_note_rejects_blank(store):
    with pytest.raises(ValueError):
        store.add_note("AAPL", "   ")


# --- API route tests ------------------------------------------------------


@pytest.fixture()
def api_store(tmp_path, monkeypatch):
    test_store = ProfileStateStore(tmp_path / "api_profile.db")
    monkeypatch.setattr(
        "src.api.routes.profile.get_watchlist_overview",
        lambda dal: CANNED_OVERVIEW,
    )
    return test_store


def test_cockpit_shape_seeds_and_archive_filter(api_store):
    data = cockpit_watchlist(dal=None, store=api_store)
    assert data["total"] == 3 and data["shown"] == 3 and data["archived_count"] == 0
    row = next(x for x in data["rows"] if x["ticker"] == "AAPL")
    for field in (
        "ticker", "group", "priority", "latest_close", "change_7d_pct",
        "news_count_7d", "sentiment_mean", "bullish_ratio", "lists",
        "archived", "tags", "note_count", "freshness", "per_ticker_error",
    ):
        assert field in row
    assert row["lists"] == ["Holdings"]
    assert "followed" not in row  # follow/star deliberately not in v0

    # cockpit load seeded the substrate
    lists = profile_lists(store=api_store)["lists"]
    assert {li["name"] for li in lists} == {"Holdings", "Interested"}

    # archive AAPL -> hidden by default, visible with include_archived
    assert set_ticker_archived("AAPL", ArchiveBody(archived=True), store=api_store)["archived"] is True
    hidden = cockpit_watchlist(dal=None, store=api_store)
    assert hidden["shown"] == 2 and hidden["archived_count"] == 1
    assert all(x["ticker"] != "AAPL" for x in hidden["rows"])

    shown = cockpit_watchlist(include_archived=True, dal=None, store=api_store)
    assert shown["shown"] == 3
    aapl = next(x for x in shown["rows"] if x["ticker"] == "AAPL")
    assert aapl["archived"] is True and aapl["lists"] == []

    # restore brings it back to active
    assert set_ticker_archived("AAPL", ArchiveBody(archived=False), store=api_store)["archived"] is False
    assert cockpit_watchlist(dal=None, store=api_store)["shown"] == 3


def test_archive_unknown_ticker_is_404(api_store):
    cockpit_watchlist(dal=None, store=api_store)  # seed
    with pytest.raises(HTTPException) as exc:
        set_ticker_archived("NOPE", ArchiveBody(archived=True), store=api_store)
    assert exc.value.status_code == 404


def test_notes_endpoints(api_store):
    cockpit_watchlist(dal=None, store=api_store)  # seed
    add_ticker_note("MSFT", NoteBody(body="earnings 7/22"), store=api_store)
    listed = list_ticker_notes("MSFT", store=api_store)
    assert listed["ticker"] == "MSFT" and len(listed["notes"]) == 1
    note_id = listed["notes"][0]["id"]

    msft = next(x for x in cockpit_watchlist(dal=None, store=api_store)["rows"] if x["ticker"] == "MSFT")
    assert msft["note_count"] == 1

    assert delete_ticker_note("MSFT", note_id, store=api_store) == {"deleted": True, "id": note_id}
    with pytest.raises(HTTPException) as exc:
        delete_ticker_note("MSFT", note_id, store=api_store)
    assert exc.value.status_code == 404


def test_add_note_blank_is_422():
    with pytest.raises(ValidationError):
        NoteBody(body="")
