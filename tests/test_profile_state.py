"""Tests for the local profile-state store (multi-list) and its API routes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src import active_universe, sa_capture_store
from src.api.routes import profile as profile_routes
from src.api.routes.profile import (
    ArchiveBody,
    ImportBody,
    ListCreateBody,
    ListRenameBody,
    MemberBody,
    NoteBody,
    add_member,
    PriorityBody,
    TagBody,
    add_ticker_note,
    add_ticker_tag,
    cockpit_watchlist,
    create_list,
    delete_list,
    delete_ticker_note,
    get_ticker_state,
    import_universe,
    list_ticker_notes,
    profile_lists,
    remove_member,
    remove_ticker_tag,
    rename_list,
    set_ticker_archived,
    set_ticker_priority,
    universe,
)
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore, UniverseSourceAnnotation
from src.universe_compat import flatten_generated_active_tickers

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
ROUTE_NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
ROUTE_NOW_TEXT = "2026-07-19T12:00:00+00:00"


def _insert_sa_pick(path: Path, symbol: str, *, picked_date: str = "2026-07-01") -> None:
    symbol_key = symbol.strip().upper()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sa_pick_lineages "
            "(symbol_key, picked_date, created_at) VALUES (?, ?, ?)",
            (symbol_key, picked_date, ROUTE_NOW_TEXT),
        )
        lineage_id = conn.execute(
            "SELECT lineage_id FROM sa_pick_lineages "
            "WHERE symbol_key=? AND picked_date=?",
            (symbol_key, picked_date),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO sa_alpha_picks "
            "(lineage_id, symbol, company, picked_date, portfolio_status, is_stale) "
            "VALUES (?, ?, ?, ?, 'current', 0)",
            (lineage_id, symbol, f"{symbol_key} Inc", picked_date),
        )


def _set_sa_current_refresh(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sa_refresh_meta "
            "(scope, last_attempt_at, last_success_at, ok, updated_at) "
            "VALUES ('current', ?, ?, 1, ?)",
            (ROUTE_NOW_TEXT, ROUTE_NOW_TEXT, ROUTE_NOW_TEXT),
        )


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


def test_list_crud_and_membership(store):
    li = store.create_list("My Picks")
    assert li.name == "My Picks" and li.kind == "custom" and li.total_count == 0
    # duplicate name rejected
    with pytest.raises(ValueError):
        store.create_list("My Picks")
    # rename
    li2 = store.rename_list(li.id, "Core Picks")
    assert li2.name == "Core Picks"
    # add members (per-list); add is idempotent
    store.add_member(li.id, "nvda")
    store.add_member(li.id, "AMD")
    store.add_member(li.id, "NVDA")  # idempotent
    agg = store.get_ticker("NVDA")
    assert "Core Picks" in agg.lists
    summary = next(x for x in store.list_watchlists() if x.id == li.id)
    assert summary.active_count == 2
    # add to unknown list → KeyError
    with pytest.raises(KeyError):
        store.add_member(999999, "AAPL")
    # remove from THIS list (hard delete membership, ticker survives elsewhere)
    store.create_list("Other")
    other = next(x for x in store.list_watchlists() if x.name == "Other")
    store.add_member(other.id, "NVDA")
    assert store.remove_member(li.id, "NVDA") is True
    agg = store.get_ticker("NVDA")
    assert agg.lists == ["Other"]  # gone from Core Picks, still in Other
    assert store.remove_member(li.id, "NVDA") is False  # already gone
    # delete list → its memberships vanish, ticker survives in others
    store.add_member(li.id, "TSLA")
    assert store.delete_list(li.id) is True
    assert store.get_ticker("TSLA").lists == []  # TSLA only lived in the deleted list
    assert store.get_ticker("AMD").lists == []   # AMD too
    assert all(x.name != "Core Picks" for x in store.list_watchlists())


def test_add_member_reactivates_archived(store):
    store.create_list("L")
    lid = next(x for x in store.list_watchlists() if x.name == "L").id
    store.add_member(lid, "NVDA")
    store.archive_ticker("NVDA")  # global archive
    assert store.get_ticker("NVDA").archived is True
    store.add_member(lid, "NVDA")  # re-add reactivates this membership
    assert store.get_ticker("NVDA").archived is False
    assert "L" in store.get_ticker("NVDA").lists


def test_priority_set_get_clear(store):
    assert store.get_priorities(["NVDA"]) == {}
    store.set_priority("nvda", "high")
    assert store.get_priorities(["NVDA", "AMD"]) == {"NVDA": "high"}
    store.set_priority("NVDA", "low")  # update
    assert store.get_priorities(["NVDA"]) == {"NVDA": "low"}
    store.set_priority("NVDA", None)  # clear
    assert store.get_priorities(["NVDA"]) == {}
    with pytest.raises(ValueError):
        store.set_priority("NVDA", "urgent")


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
def universe_databases(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile_state.db"
    sa_path = tmp_path / "sa_capture.db"
    profile_store = ProfileStateStore(profile_path)
    portfolio_store = PortfolioStore(profile_path)
    conn = sa_capture_store.connect(str(sa_path))
    conn.close()
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(sa_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent-market.db"))
    monkeypatch.setattr(
        profile_routes,
        "get_watchlist_overview",
        lambda dal: {"date": "2026-07-19", "ticker_count": 0, "tickers": []},
    )
    monkeypatch.setattr(profile_routes, "get_universe_summaries", lambda dal, days=7: {})
    return SimpleNamespace(
        profile_path=profile_path,
        sa_path=sa_path,
        profile=profile_store,
        portfolio=portfolio_store,
    )


@pytest.fixture()
def api_store(universe_databases, monkeypatch):
    test_store = universe_databases.profile
    test_store.replace_legacy_config_import(
        approved_memberships=["AAPL", "MSFT", "TSLA"],
        annotations=[],
    )
    monkeypatch.setattr(
        profile_routes,
        "get_watchlist_overview",
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


def test_import_universe_creates_no_lists_and_archive_filter(api_store):
    # De-mess: import no longer creates lists (it seeds tags + drops non-custom).
    imported = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert imported["lists"] == []
    assert profile_lists(store=api_store)["lists"] == []

    # Archive applies to list members → put AAPL in a user list, then archive it.
    created = create_list(ListCreateBody(name="Core"), store=api_store)
    add_member(created["id"], MemberBody(ticker="AAPL"), store=api_store)
    data = cockpit_watchlist(dal=None, store=api_store)
    row = next(x for x in data["rows"] if x["ticker"] == "AAPL")
    assert row["lists"] == ["Core"]

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


def test_list_crud_routes(api_store):
    created = create_list(ListCreateBody(name="My Picks"), store=api_store)
    lid = created["id"]
    assert created["name"] == "My Picks"
    # duplicate → 400
    with pytest.raises(HTTPException) as exc:
        create_list(ListCreateBody(name="My Picks"), store=api_store)
    assert exc.value.status_code == 400

    assert rename_list(lid, ListRenameBody(name="Picks"), store=api_store)["name"] == "Picks"
    with pytest.raises(HTTPException) as exc:
        rename_list(999999, ListRenameBody(name="x"), store=api_store)
    assert exc.value.status_code == 404

    # add member → appears in the ticker's lists (verified via the store directly);
    # then remove from THIS list.
    add_member(lid, MemberBody(ticker="nvda"), store=api_store)
    assert "Picks" in api_store.get_ticker("NVDA").lists
    assert remove_member(lid, "NVDA", store=api_store)["removed"] is True
    assert api_store.get_ticker("NVDA").lists == []
    with pytest.raises(HTTPException) as exc:
        remove_member(lid, "NVDA", store=api_store)  # already gone → 404
    assert exc.value.status_code == 404

    assert delete_list(lid, store=api_store)["deleted"] is True
    with pytest.raises(HTTPException) as exc:
        delete_list(lid, store=api_store)  # already gone → 404
    assert exc.value.status_code == 404


def test_create_list_blank_is_422():
    with pytest.raises(ValidationError):
        ListCreateBody(name="")


def test_set_priority_route_overrides_overview(api_store):
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    # AAPL's overview priority is "high"; user override → "low"
    set_ticker_priority("AAPL", PriorityBody(priority="low"), store=api_store)
    row = next(x for x in cockpit_watchlist(dal=None, store=api_store)["rows"] if x["ticker"] == "AAPL")
    assert row["priority"] == "low"
    # clear → falls back to the overview's "high"
    set_ticker_priority("AAPL", PriorityBody(priority=None), store=api_store)
    row = next(x for x in cockpit_watchlist(dal=None, store=api_store)["rows"] if x["ticker"] == "AAPL")
    assert row["priority"] == "high"
    # invalid → 400
    with pytest.raises(HTTPException) as exc:
        set_ticker_priority("AAPL", PriorityBody(priority="urgent"), store=api_store)
    assert exc.value.status_code == 400


def test_priority_route_overrides_universe_and_ticker_state(api_store):
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    set_ticker_priority("MSFT", PriorityBody(priority="high"), store=api_store)

    u = universe(dal=None, store=api_store)
    msft = next(x for x in u["rows"] if x["ticker"] == "MSFT")
    assert msft["priority"] == "high"  # overview says medium; user override wins

    state = get_ticker_state("MSFT", dal=None, store=api_store)
    assert state["ticker"] == "MSFT"
    assert state["priority"] == "high"

    set_ticker_priority("MSFT", PriorityBody(priority=None), store=api_store)
    state = get_ticker_state("MSFT", dal=None, store=api_store)
    assert state["priority"] == "medium"


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


def test_universe_route_uses_snapshot_and_keeps_archived_history_non_active(
    universe_databases, monkeypatch
):
    profile = universe_databases.profile
    profile.import_lists(
        [{"name": "History", "kind": "custom", "tickers": ["ARCHIVED", "HELD"]}]
    )
    profile.archive_ticker("ARCHIVED")
    profile.archive_ticker("HELD")
    account = universe_databases.portfolio.ensure_manual_account()
    universe_databases.portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="HELD",
        quantity=1,
    )
    _insert_sa_pick(universe_databases.sa_path, "SAONLY")
    _set_sa_current_refresh(universe_databases.sa_path)

    calls = []

    def build_snapshot(*, profile_db):
        calls.append(profile_db)
        return active_universe.build_active_universe_snapshot(
            profile_db=profile_db,
            sa_db=universe_databases.sa_path,
            now=ROUTE_NOW,
        )

    monkeypatch.setattr(
        profile_routes,
        "build_active_universe_snapshot",
        build_snapshot,
        raising=False,
    )

    active = universe(include_archived=False, dal=None, store=profile)
    assert calls == [profile.db_path]
    assert active["total"] == 3
    assert active["shown"] == 2
    assert active["archived_count"] == 1
    active_rows = {row["ticker"]: row for row in active["rows"]}
    assert set(active_rows) == {"HELD", "SAONLY"}
    assert active_rows["HELD"]["archived"] is False
    assert active_rows["HELD"]["archived_lists"] == ["History"]
    assert active_rows["HELD"]["sources"] == ["portfolio_open"]
    assert active_rows["SAONLY"]["sources"] == ["sa_alpha_picks_current"]
    assert set(active["source_status"]) == set(active_universe.SOURCE_KEYS)
    assert all(status["available"] for status in active["source_status"].values())

    with_history = universe(include_archived=True, dal=None, store=profile)
    assert calls == [profile.db_path, profile.db_path]
    all_rows = {row["ticker"]: row for row in with_history["rows"]}
    assert set(all_rows) == {"ARCHIVED", "HELD", "SAONLY"}
    assert all_rows["ARCHIVED"]["archived"] is True
    assert all_rows["ARCHIVED"]["sources"] == []
    assert all_rows["ARCHIVED"]["archived_lists"] == ["History"]


def test_universe_route_returns_sanitized_503_for_unavailable_source(
    universe_databases, monkeypatch
):
    hostile_path = universe_databases.sa_path.parent / "password=do-not-leak.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(hostile_path))

    with pytest.raises(HTTPException) as caught:
        universe(dal=None, store=universe_databases.profile)

    assert caught.value.status_code == 503
    assert caught.value.detail == {
        "code": "active_universe_unavailable",
        "status": "unavailable",
        "unavailable_sources": ["sa_alpha_picks_current"],
        "source_reasons": {"sa_alpha_picks_current": "source_db_missing"},
    }
    rendered = repr(caught.value.detail)
    assert "do-not-leak" not in rendered
    assert str(hostile_path) not in rendered


def test_legacy_overview_enriches_but_never_qualifies_universe(
    universe_databases, monkeypatch
):
    universe_databases.profile.import_lists(
        [{"name": "Accepted", "kind": "custom", "tickers": ["AAPL"]}]
    )
    monkeypatch.setattr(
        profile_routes,
        "get_watchlist_overview",
        lambda dal: {
            "date": "2026-07-19",
            "tickers": [
                {
                    "ticker": "AAPL",
                    "group": "Holdings",
                    "priority": "high",
                    "latest_close": 215.0,
                    "change_7d_pct": 2.5,
                    "news_count_7d": 3,
                    "sentiment_mean": 0.4,
                    "bullish_ratio": 0.75,
                },
                {
                    "ticker": "OVERVIEWONLY",
                    "group": "Interested",
                    "latest_close": 1.0,
                },
            ],
        },
    )

    response = universe(dal=None, store=universe_databases.profile)

    assert [row["ticker"] for row in response["rows"]] == ["AAPL"]
    assert response["rows"][0]["group"] == "Holdings"
    assert response["rows"][0]["latest_close"] == 215.0


def test_import_universe_uses_annotations_without_opening_json(
    universe_databases, monkeypatch
):
    profile = universe_databases.profile
    profile.replace_legacy_config_import(
        approved_memberships=[],
        annotations=[
            UniverseSourceAnnotation(
                "legacy_config_seed",
                "NVDA",
                "legacy_category",
                "tier1_core/sa_alpha_picks_auto",
            ),
            UniverseSourceAnnotation(
                "legacy_config_seed",
                "MSFT",
                "legacy_category",
                "tier2_expanded/seeking_picks_technology",
            ),
        ],
    )
    original_read_text = Path.read_text

    def reject_retired_json(path, *args, **kwargs):
        if path.name == "tickers_core.json":
            raise AssertionError("retired universe JSON was opened")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_retired_json)

    response = import_universe(
        ImportBody(include_groups=False, include_tiers=True),
        dal=None,
        store=profile,
    )

    assert response["tags"] == {"tags_added": 3}
    tags = profile.get_tags(["MSFT", "NVDA"])
    assert tags["NVDA"] == [
        {"facet": "provenance", "value": "Alpha Picks", "source": "legacy"}
    ]
    assert tags["MSFT"] == [
        {"facet": "category", "value": "Technology", "source": "legacy"},
        {"facet": "provenance", "value": "Seeking Alpha", "source": "legacy"},
    ]


def test_universe_export_route_is_deterministic_read_only_and_omits_settings(
    universe_databases, monkeypatch
):
    profile = universe_databases.profile
    profile.replace_legacy_config_import(
        approved_memberships=["AAPL"],
        annotations=[
            UniverseSourceAnnotation(
                "legacy_config_seed", "AAPL", "legacy_tier", "tier1_core"
            ),
            UniverseSourceAnnotation(
                "legacy_config_seed",
                "AAPL",
                "legacy_category",
                "tier1_core/mega_cap_tech",
            ),
        ],
    )
    profile.import_lists(
        [{"name": "History", "kind": "custom", "tickers": ["ARCHIVED"]}]
    )
    profile.archive_ticker("ARCHIVED")
    profile.set_setting("private-export-setting", "must-not-leak")
    _insert_sa_pick(universe_databases.sa_path, "SAONLY")
    _set_sa_current_refresh(universe_databases.sa_path)

    calls = []

    def build_snapshot(*, profile_db):
        calls.append(profile_db)
        return active_universe.build_active_universe_snapshot(
            profile_db=profile_db,
            sa_db=universe_databases.sa_path,
            now=ROUTE_NOW,
        )

    def reject_file_write(*args, **kwargs):
        raise AssertionError("route attempted to write an export file")

    monkeypatch.setattr(
        profile_routes,
        "build_active_universe_snapshot",
        build_snapshot,
        raising=False,
    )
    monkeypatch.setattr(
        profile_routes,
        "write_compat_export",
        reject_file_write,
        raising=False,
    )
    before = (
        profile.get_setting("private-export-setting"),
        profile.list_watchlists(include_archived=True),
        profile.list_universe_source_annotations(),
    )

    first = profile_routes.export_universe(store=profile)
    second = profile_routes.export_universe(store=profile)

    assert calls == [profile.db_path, profile.db_path]
    assert first == second
    assert first["_generated"]["generated_at"] == ROUTE_NOW_TEXT
    assert "settings" not in first
    assert "legacy_reference" not in first
    assert "must-not-leak" not in repr(first)
    assert flatten_generated_active_tickers(first) == {"AAPL", "SAONLY"}
    assert "ARCHIVED" not in repr(first)
    assert before == (
        profile.get_setting("private-export-setting"),
        profile.list_watchlists(include_archived=True),
        profile.list_universe_source_annotations(),
    )


# --- tags (two-dimensional facet × source, decoupled from list membership) ---


def test_get_tags_empty(store):
    assert store.get_tags([]) == {}
    assert store.get_tags(["NVDA"]) == {}  # no tags → ticker absent from result


def test_seed_tags_get_and_facet_grouping(store):
    summary = store.seed_tags(
        [
            {"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["NVDA", "AMD"]},
            {"facet": "provenance", "value": "Alpha Picks", "source": "system", "tickers": ["NVDA"]},
        ]
    )
    assert summary == {"tags_added": 3}
    tags = store.get_tags(["NVDA", "AMD"])
    # ordered by (facet, source, value): category before provenance
    assert tags["NVDA"] == [
        {"facet": "category", "value": "Mega Cap Tech", "source": "legacy"},
        {"facet": "provenance", "value": "Alpha Picks", "source": "system"},
    ]
    assert tags["AMD"] == [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy"}]
    # re-seed is idempotent (duplicate rows ignored)
    again = store.seed_tags(
        [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["NVDA"]}]
    )
    assert again == {"tags_added": 0}


def test_tag_add_remove_user_default_and_facets(store):
    store.seed_tags(
        [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["AAPL"]}]
    )
    store.add_tag("aapl", "量子計算")  # defaults facet=theme, source=user; normalizes ticker
    # remove without source → only the user tag on that (facet, value) goes
    assert store.remove_tag("AAPL", "量子計算") is True
    assert store.remove_tag("AAPL", "量子計算") is False  # already gone
    # the legacy category survives (it is not a user theme)
    assert store.get_tags(["AAPL"]) == {
        "AAPL": [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy"}]
    }
    # explicit source removes the legacy tag (legacy is editable / takeover-able)
    assert store.remove_tag("AAPL", "Mega Cap Tech", facet="category", source="legacy") is True
    assert store.get_tags(["AAPL"]) == {}


def test_seed_tags_is_additive_and_preserves_user(store):
    # seed_tags is a pure additive bootstrap: it NEVER deletes/replaces, so a
    # re-seed missing a ticker does not drop its previously-seeded tag, and user
    # edits always survive.
    store.seed_tags(
        [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["NVDA", "AMD"]}]
    )
    store.add_tag("NVDA", "my-thesis")  # user:theme
    store.seed_tags(
        [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["NVDA"]}]
    )
    tags = store.get_tags(["NVDA", "AMD"])
    assert {"facet": "category", "value": "Mega Cap Tech", "source": "legacy"} in tags["NVDA"]
    assert {"facet": "theme", "value": "my-thesis", "source": "user"} in tags["NVDA"]
    # AMD's seeded tag is NOT dropped (additive, not replace)
    assert {"facet": "category", "value": "Mega Cap Tech", "source": "legacy"} in tags["AMD"]


def test_add_tag_rejects_blank(store):
    with pytest.raises(ValueError):
        store.add_tag("NVDA", "   ")
    with pytest.raises(ValueError):
        store.add_tag("", "x")


def test_cockpit_universe_ticker_state_carry_tags(api_store):
    api_store.seed_tags(
        [
            {"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["AAPL", "MSFT"]},
            {"facet": "theme", "value": "watch-me", "source": "user", "tickers": ["AAPL"]},
        ]
    )
    cockpit = {r["ticker"]: r for r in cockpit_watchlist(dal=None, store=api_store)["rows"]}
    assert {(t["facet"], t["value"], t["source"]) for t in cockpit["AAPL"]["tags"]} == {
        ("category", "Mega Cap Tech", "legacy"),
        ("theme", "watch-me", "user"),
    }
    assert cockpit["TSLA"]["tags"] == []  # untagged ticker → empty

    u = {r["ticker"]: r for r in universe(dal=None, store=api_store)["rows"]}
    assert {(t["facet"], t["value"], t["source"]) for t in u["MSFT"]["tags"]} == {
        ("category", "Mega Cap Tech", "legacy")
    }

    state = get_ticker_state("AAPL", dal=None, store=api_store)
    assert ("theme", "watch-me", "user") in {
        (t["facet"], t["value"], t["source"]) for t in state["tags"]
    }


def test_import_universe_seeds_theme_tags_and_drops_groups(api_store, monkeypatch):
    # A theme group ("theme:量子計算") becomes a legacy:theme tag; holdings is dropped.
    monkeypatch.setattr(
        "src.api.routes.profile.get_watchlist_overview",
        lambda dal: {
            "date": "2026-06-05",
            "tickers": [
                {"ticker": "IONQ", "group": "theme:量子計算"},
                {"ticker": "RGTI", "group": "theme:量子計算"},
                {"ticker": "AAPL", "group": "Holdings"},
            ],
        },
    )
    out = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert out["tags"]["tags_added"] == 2  # IONQ, RGTI under 量子計算
    assert out["lists"] == []  # import creates no lists
    tags = api_store.get_tags(["IONQ", "AAPL"])
    assert tags["IONQ"] == [{"facet": "theme", "value": "量子計算", "source": "legacy"}]
    assert "AAPL" not in tags  # Holdings group is dropped (not preserved)

    # Re-import is additive + idempotent (no replace, no double-count)
    again = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert again["tags"]["tags_added"] == 0


def test_import_universe_theme_groups_best_effort(api_store, monkeypatch):
    # If the overview/DAL is unreachable, theme-group import is skipped but the
    # persisted reviewed category/provenance projection still runs.
    api_store.replace_legacy_config_import(
        approved_memberships=["AAPL", "MSFT", "TSLA"],
        annotations=[
            UniverseSourceAnnotation(
                "legacy_config_seed",
                "NVDA",
                "legacy_category",
                "tier1_core/sa_alpha_picks_auto",
            )
        ],
    )

    def _boom(dal):
        raise RuntimeError("PG down")

    monkeypatch.setattr("src.api.routes.profile.get_watchlist_overview", _boom)
    out = import_universe(ImportBody(include_groups=True, include_tiers=True), dal=None, store=api_store)
    assert out["groups_ok"] is False
    assert out["tags"] == {"tags_added": 1}


def test_import_universe_deletes_non_custom_lists(api_store):
    # Seed a mix of legacy (tier/holdings) + a user custom list, then de-mess.
    api_store.import_lists([{"name": "Tier 1 · Core", "kind": "tier", "tickers": ["NVDA"]}])
    api_store.import_lists([{"name": "core_holdings", "kind": "holdings", "tickers": ["AAPL"]}])
    api_store.create_list("My Picks", "custom")
    out = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert out["lists_removed"] == 2  # tier + holdings gone
    remaining = {li["name"]: li["kind"] for li in out["lists"]}
    assert remaining == {"My Picks": "custom"}  # only the user list survives


def test_universe_suppression_hides_ticker(api_store):
    from src.api.routes.profile import HiddenBody, set_ticker_hidden

    # A catalog/active-universe ticker shows in 全部標的 until suppressed.
    api_store.import_lists([{"name": "X", "kind": "custom", "tickers": ["ZZZZ"]}])
    assert "ZZZZ" in {r["ticker"] for r in universe(dal=None, store=api_store)["rows"]}

    out = set_ticker_hidden("zzzz", HiddenBody(hidden=True), store=api_store)
    assert out == {"ticker": "ZZZZ", "hidden": True}
    assert "ZZZZ" not in {r["ticker"] for r in universe(dal=None, store=api_store)["rows"]}
    assert api_store.get_hidden_tickers() == {"ZZZZ"}

    # unhide brings it back
    set_ticker_hidden("ZZZZ", HiddenBody(hidden=False), store=api_store)
    assert "ZZZZ" in {r["ticker"] for r in universe(dal=None, store=api_store)["rows"]}


def test_suppression_does_not_clobber_priority(store):
    store.set_priority("NVDA", "high")
    store.set_universe_hidden("NVDA", True)
    assert store.get_priorities(["NVDA"]) == {"NVDA": "high"}  # priority intact
    assert store.get_hidden_tickers() == {"NVDA"}
    store.set_priority("NVDA", "low")  # priority update must not clear hidden_at
    assert store.get_hidden_tickers() == {"NVDA"}


def test_provenance_system_normalized_to_legacy_editable(tmp_path):
    # A previously-seeded read-only 'system' provenance becomes editable 'legacy'
    # on store init (provenance is user-managed: added → closed).
    db = tmp_path / "prov.db"
    s = ProfileStateStore(db)
    s.seed_tags([{"facet": "provenance", "value": "Alpha Picks", "source": "system", "tickers": ["NVDA"]}])
    assert s.get_tags(["NVDA"])["NVDA"] == [
        {"facet": "provenance", "value": "Alpha Picks", "source": "system"}
    ]
    # re-open → _ensure_schema normalizes system→legacy
    ProfileStateStore(db)
    assert s.get_tags(["NVDA"])["NVDA"] == [
        {"facet": "provenance", "value": "Alpha Picks", "source": "legacy"}
    ]


def test_tag_catalog_groups_distinct_values_by_facet(api_store):
    from src.api.routes.profile import tag_catalog

    api_store.seed_tags(
        [
            {"facet": "theme", "value": "AI", "source": "user", "tickers": ["NVDA"]},
            {"facet": "theme", "value": "AI", "source": "legacy", "tickers": ["AMD"]},  # dup value
            {"facet": "theme", "value": "Space", "source": "user", "tickers": ["RKLB"]},
            {"facet": "category", "value": "Semis", "source": "legacy", "tickers": ["NVDA"]},
        ]
    )
    cat = tag_catalog(store=api_store)["catalog"]
    assert cat["theme"] == ["AI", "Space"]  # distinct + sorted, dup collapsed
    assert cat["category"] == ["Semis"]


def test_user_tag_add_remove_routes(api_store):
    api_store.seed_tags(
        [{"facet": "category", "value": "Mega Cap Tech", "source": "legacy", "tickers": ["AAPL"]}]
    )

    # add a user theme tag → state reflects it with source='user'
    state = add_ticker_tag("aapl", TagBody(value="my-watch"), store=api_store)
    pairs = {(t["facet"], t["value"], t["source"]) for t in state["tags"]}
    assert ("theme", "my-watch", "user") in pairs
    assert ("category", "Mega Cap Tech", "legacy") in pairs  # legacy untouched

    # remove the user tag (defaults facet=theme, source=user)
    assert remove_ticker_tag("AAPL", value="my-watch", store=api_store)["removed"] is True

    # a read-only source is rejected with 400 (cannot delete external facts)
    with pytest.raises(HTTPException) as exc:
        remove_ticker_tag("AAPL", value="Foo", source="system", store=api_store)
    assert exc.value.status_code == 400

    # legacy IS removable (takeover-able)
    assert (
        remove_ticker_tag("AAPL", value="Mega Cap Tech", facet="category", source="legacy", store=api_store)[
            "removed"
        ]
        is True
    )
    assert get_ticker_state("AAPL", dal=None, store=api_store)["tags"] == []

    # removing a non-existent editable tag → 404
    with pytest.raises(HTTPException) as exc:
        remove_ticker_tag("AAPL", value="nope", store=api_store)
    assert exc.value.status_code == 404


def test_user_tag_label_colliding_with_legacy_is_distinct(api_store):
    # A user tag whose (facet,value) equals a legacy tag is a separate user row.
    api_store.seed_tags([{"facet": "theme", "value": "AI", "source": "legacy", "tickers": ["AAPL"]}])
    add_ticker_tag("AAPL", TagBody(value="AI"), store=api_store)  # user:theme "AI"
    pairs = {(t["facet"], t["value"], t["source"]) for t in get_ticker_state("AAPL", dal=None, store=api_store)["tags"]}
    assert pairs == {("theme", "AI", "legacy"), ("theme", "AI", "user")}
    # default remove targets the user row; legacy remains
    assert remove_ticker_tag("AAPL", value="AI", store=api_store)["removed"] is True
    pairs = {(t["facet"], t["value"], t["source"]) for t in get_ticker_state("AAPL", dal=None, store=api_store)["tags"]}
    assert pairs == {("theme", "AI", "legacy")}


def test_add_tag_blank_is_422():
    with pytest.raises(ValidationError):
        TagBody(value="")


def test_tags_v1_to_v2_migration(tmp_path):
    # A pre-existing v1 ticker_tags(ticker, tag, source) table migrates in place:
    # config:* dropped (regenerated by re-import), user tags preserved as theme.
    import sqlite3

    db = tmp_path / "v1.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE ticker_tags (
            ticker TEXT NOT NULL, tag TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL,
            PRIMARY KEY (ticker, tag, source)
        );
        INSERT INTO ticker_tags VALUES
            ('NVDA', 'Tier 1 · Core', 'config:tier', '2026-01-01T00:00:00'),
            ('NVDA', 'Mega Cap Tech', 'config:category', '2026-01-01T00:00:00'),
            ('NVDA', '量子計算', 'config:theme', '2026-01-01T00:00:00'),
            ('NVDA', 'my-thesis', 'user', '2026-01-01T00:00:00');
        """
    )
    conn.commit()
    conn.close()

    store = ProfileStateStore(db)  # triggers migration on init
    tags = store.get_tags(["NVDA"])["NVDA"]
    # only the user tag survives, on the theme facet; config:* are gone
    assert tags == [{"facet": "theme", "value": "my-thesis", "source": "user"}]

    # the table is now v2 and re-init is a no-op
    ProfileStateStore(db)
    assert store.get_tags(["NVDA"])["NVDA"] == [
        {"facet": "theme", "value": "my-thesis", "source": "user"}
    ]


def test_default_watchlist_get_set_stale_and_404(api_store):
    from src.api.routes.profile import (
        DefaultWatchlistBody,
        get_default_watchlist,
        set_default_watchlist,
    )

    assert get_default_watchlist(store=api_store)["default_watchlist_id"] is None  # unset
    li = create_list(ListCreateBody(name="Core"), store=api_store)
    set_default_watchlist(DefaultWatchlistBody(list_id=li["id"]), store=api_store)
    assert get_default_watchlist(store=api_store)["default_watchlist_id"] == li["id"]

    with pytest.raises(HTTPException) as exc:  # unknown list → 404
        set_default_watchlist(DefaultWatchlistBody(list_id=999999), store=api_store)
    assert exc.value.status_code == 404

    delete_list(li["id"], store=api_store)  # default list deleted → reported null (stale)
    assert get_default_watchlist(store=api_store)["default_watchlist_id"] is None

    li2 = create_list(ListCreateBody(name="B"), store=api_store)
    set_default_watchlist(DefaultWatchlistBody(list_id=li2["id"]), store=api_store)
    set_default_watchlist(DefaultWatchlistBody(list_id=None), store=api_store)  # clear
    assert get_default_watchlist(store=api_store)["default_watchlist_id"] is None


def test_profile_settings_get_set(store):
    assert store.get_setting("default_watchlist_id") is None
    store.set_setting("default_watchlist_id", "7")
    assert store.get_setting("default_watchlist_id") == "7"
    store.set_setting("default_watchlist_id", "12")  # upsert
    assert store.get_setting("default_watchlist_id") == "12"
    store.set_setting("default_watchlist_id", None)  # clear
    assert store.get_setting("default_watchlist_id") is None


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
