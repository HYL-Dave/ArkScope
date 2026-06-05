"""Tests for the local profile-state store (multi-list) and its API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_dal, get_profile_store
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
def client(tmp_path, monkeypatch):
    test_store = ProfileStateStore(tmp_path / "api_profile.db")
    monkeypatch.setattr(
        "src.api.routes.profile.get_watchlist_overview",
        lambda dal: CANNED_OVERVIEW,
    )
    app = create_app()
    app.dependency_overrides[get_dal] = lambda: None
    app.dependency_overrides[get_profile_store] = lambda: test_store
    return TestClient(app)


def test_cockpit_shape_seeds_and_archive_filter(client):
    r = client.get("/cockpit/watchlist")
    assert r.status_code == 200
    data = r.json()
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
    lists = client.get("/profile/lists").json()["lists"]
    assert {li["name"] for li in lists} == {"Holdings", "Interested"}

    # archive AAPL -> hidden by default, visible with include_archived
    assert client.post("/profile/tickers/AAPL/archive", json={"archived": True}).status_code == 200
    hidden = client.get("/cockpit/watchlist").json()
    assert hidden["shown"] == 2 and hidden["archived_count"] == 1
    assert all(x["ticker"] != "AAPL" for x in hidden["rows"])

    shown = client.get("/cockpit/watchlist", params={"include_archived": True}).json()
    assert shown["shown"] == 3
    aapl = next(x for x in shown["rows"] if x["ticker"] == "AAPL")
    assert aapl["archived"] is True and aapl["lists"] == []

    # restore brings it back to active
    assert client.post("/profile/tickers/AAPL/archive", json={"archived": False}).status_code == 200
    assert client.get("/cockpit/watchlist").json()["shown"] == 3


def test_notes_endpoints(client):
    client.get("/cockpit/watchlist")  # seed
    assert client.post("/profile/tickers/MSFT/notes", json={"body": "earnings 7/22"}).status_code == 200
    listed = client.get("/profile/tickers/MSFT/notes").json()
    assert listed["ticker"] == "MSFT" and len(listed["notes"]) == 1
    note_id = listed["notes"][0]["id"]

    msft = next(x for x in client.get("/cockpit/watchlist").json()["rows"] if x["ticker"] == "MSFT")
    assert msft["note_count"] == 1

    assert client.delete(f"/profile/tickers/MSFT/notes/{note_id}").status_code == 200
    assert client.delete(f"/profile/tickers/MSFT/notes/{note_id}").status_code == 404


def test_add_note_blank_is_422(client):
    assert client.post("/profile/tickers/MSFT/notes", json={"body": ""}).status_code == 422
