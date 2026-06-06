"""Tests for the local profile-state store (multi-list) and its API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes.profile import (
    ArchiveBody,
    ImportBody,
    NoteBody,
    add_ticker_note,
    cockpit_watchlist,
    delete_ticker_note,
    import_universe,
    list_ticker_notes,
    profile_lists,
    set_ticker_archived,
    universe,
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


def test_import_lists_allows_duplicate_membership(store):
    # A ticker may belong to several lists (by design).
    summary = store.import_lists(
        [
            {"name": "Tier 1 · Core", "kind": "tier", "tickers": ["NVDA", "AMD"]},
            {"name": "AI 基礎設施", "kind": "theme", "tickers": ["NVDA", "AVGO"]},
        ]
    )
    assert summary == {"lists_created": 2, "memberships_added": 4}
    agg = store.get_aggregate(["NVDA"])
    assert set(agg["NVDA"].lists) == {"Tier 1 · Core", "AI 基礎設施"}
    # Re-import is idempotent (nothing new created/added).
    again = store.import_lists([{"name": "Tier 1 · Core", "tickers": ["NVDA", "AMD"]}])
    assert again == {"lists_created": 0, "memberships_added": 0}


def test_aggregate_read_model_active_vs_archived_lists(store):
    # A ticker in two lists; archive it → active `lists` empties, but the
    # provenance survives in archived_lists / all_lists (gpt-5.5 read-model gap).
    store.import_lists(
        [
            {"name": "Holdings", "kind": "holdings", "tickers": ["NVDA"]},
            {"name": "Tier 1 · Core", "kind": "tier", "tickers": ["NVDA"]},
        ]
    )
    a = store.get_ticker("NVDA")
    assert set(a.lists) == {"Holdings", "Tier 1 · Core"}
    assert a.archived_lists == []
    assert set(a.all_lists) == {"Holdings", "Tier 1 · Core"}

    store.archive_ticker("NVDA")
    a = store.get_ticker("NVDA")
    assert a.archived is True
    assert a.lists == []  # no ACTIVE membership while archived
    assert set(a.archived_lists) == {"Holdings", "Tier 1 · Core"}  # provenance kept
    assert set(a.all_lists) == {"Holdings", "Tier 1 · Core"}


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


def test_cockpit_read_does_not_write(api_store):
    # A read must NOT seed the substrate (no implicit profile_state_write).
    data = cockpit_watchlist(dal=None, store=api_store)
    assert data["total"] == 3 and data["shown"] == 3 and data["archived_count"] == 0
    row = next(x for x in data["rows"] if x["ticker"] == "AAPL")
    for field in (
        "ticker", "group", "priority", "latest_close", "change_7d_pct",
        "news_count_7d", "sentiment_mean", "bullish_ratio", "lists",
        "archived", "tags", "note_count", "freshness", "per_ticker_error",
    ):
        assert field in row
    assert row["lists"] == []  # not imported yet → empty, not seeded by the read
    assert "followed" not in row  # follow/star deliberately not in v0
    assert profile_lists(store=api_store)["lists"] == []  # read created no lists


def test_import_universe_then_archive_filter(api_store):
    # Explicit import seeds the lists (dal=None → tiers no-op; groups only).
    imported = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert {li["name"] for li in imported["lists"]} == {"Holdings", "Interested"}

    lists = profile_lists(store=api_store)["lists"]
    assert {li["name"] for li in lists} == {"Holdings", "Interested"}

    data = cockpit_watchlist(dal=None, store=api_store)
    row = next(x for x in data["rows"] if x["ticker"] == "AAPL")
    assert row["lists"] == ["Holdings"]

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
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)  # explicit seed
    with pytest.raises(HTTPException) as exc:
        set_ticker_archived("NOPE", ArchiveBody(archived=True), store=api_store)
    assert exc.value.status_code == 404


def test_notes_endpoints(api_store):
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)  # explicit seed
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


def test_all_tickers_distinct_sorted(store):
    store.import_lists(
        [
            {"name": "L1", "tickers": ["AAPL", "MSFT"]},
            {"name": "L2", "tickers": ["MSFT", "NVDA"]},  # MSFT duplicate across lists
        ]
    )
    assert store.all_tickers() == ["AAPL", "MSFT", "NVDA"]


def test_universe_surfaces_all_imported_with_has_summary(api_store):
    # groups (3 overview tickers) + a universe-only list (NVDA not in overview)
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    api_store.import_lists([{"name": "Tier X", "kind": "tier", "tickers": ["NVDA", "AAPL"]}])

    u = universe(dal=None, store=api_store)
    rows = {r["ticker"]: r for r in u["rows"]}
    assert {"AAPL", "MSFT", "TSLA", "NVDA"} <= set(rows)
    # overview ticker → summary populated
    assert rows["AAPL"]["has_summary"] is True and rows["AAPL"]["latest_close"] == 200.0
    # universe-only ticker → no summary, but its list membership shows
    assert rows["NVDA"]["has_summary"] is False and rows["NVDA"]["latest_close"] is None
    assert "Tier X" in rows["NVDA"]["lists"]
    assert u["summarized"] == 3  # only the 3 overview tickers are summarized


def test_tier_named_lists_structure():
    from src.universe_config import TIER_NAMES, tier_named_lists

    lists = tier_named_lists()
    for li in lists:  # tolerant: empty if config absent, else well-formed
        assert li["kind"] == "tier"
        assert li["name"] in TIER_NAMES.values()
        assert li["tickers"] and all(isinstance(t, str) for t in li["tickers"])


def test_universe_batch_summary_fills_universe_only(api_store, monkeypatch):
    # A universe-only ticker (not in overview) gets market data from the batch
    # summary — so it is NOT stuck at has_summary=False.
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    api_store.import_lists([{"name": "Tier X", "kind": "tier", "tickers": ["NVDA"]}])
    monkeypatch.setattr(
        "src.api.routes.profile.get_universe_summaries",
        lambda dal, days=7: {
            "NVDA": {"latest_close": 905.1, "change_pct": 3.2, "total_volume": 1, "bars": 130, "news_count_7d": 9},
        },
    )
    u = universe(dal=None, store=api_store)
    nvda = next(r for r in u["rows"] if r["ticker"] == "NVDA")
    assert nvda["has_summary"] is True
    assert nvda["latest_close"] == 905.1 and nvda["change_7d_pct"] == 3.2 and nvda["news_count_7d"] == 9
    assert "Tier X" in nvda["lists"]
