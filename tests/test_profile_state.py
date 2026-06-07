"""Tests for the local profile-state store (multi-list) and its API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

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
    assert {li["kind"] for li in imported["lists"]} == {"imported_profile"}

    lists = profile_lists(store=api_store)["lists"]
    assert {li["name"] for li in lists} == {"Holdings", "Interested"}
    assert {li["kind"] for li in lists} == {"imported_profile"}

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


def test_tier_named_lists_structure():
    from src.universe_config import TIER_NAMES, tier_named_lists

    lists = tier_named_lists()
    for li in lists:  # tolerant: empty if config absent, else well-formed
        assert li["kind"] == "tier"
        assert li["name"] in TIER_NAMES.values()
        assert li["tickers"] and all(isinstance(t, str) for t in li["tickers"])


# --- tags (classification metadata, decoupled from list membership) -------


def test_get_tags_empty(store):
    assert store.get_tags([]) == {}
    assert store.get_tags(["NVDA"]) == {}  # no tags → ticker absent from result


def test_seed_tags_get_and_source_grouping(store):
    summary = store.seed_tags(
        [
            {"tag": "Tier 1 · Core", "source": "config:tier", "tickers": ["NVDA", "AMD"]},
            {"tag": "Mega Cap Tech", "source": "config:category", "tickers": ["NVDA"]},
        ]
    )
    assert summary == {"tags_added": 3}
    tags = store.get_tags(["NVDA", "AMD"])
    # config rows ordered by (source, tag): config:category before config:tier
    assert tags["NVDA"] == [
        {"tag": "Mega Cap Tech", "source": "config:category"},
        {"tag": "Tier 1 · Core", "source": "config:tier"},
    ]
    assert tags["AMD"] == [{"tag": "Tier 1 · Core", "source": "config:tier"}]
    # re-seed is idempotent (duplicate rows ignored)
    again = store.seed_tags([{"tag": "Tier 1 · Core", "source": "config:tier", "tickers": ["NVDA"]}])
    assert again == {"tags_added": 0}


def test_tag_add_remove_user_only_by_default(store):
    store.seed_tags([{"tag": "Mega Cap Tech", "source": "config:category", "tickers": ["AAPL"]}])
    store.add_tag("aapl", "watch-me")  # defaults to source="user", normalizes ticker
    # remove without source → ONLY the user tag goes; config tag is protected
    assert store.remove_tag("AAPL", "watch-me") is True
    assert store.remove_tag("AAPL", "Mega Cap Tech") is False  # not a user tag
    assert store.get_tags(["AAPL"]) == {"AAPL": [{"tag": "Mega Cap Tech", "source": "config:category"}]}
    # explicit source CAN remove a config tag
    assert store.remove_tag("AAPL", "Mega Cap Tech", source="config:category") is True
    assert store.get_tags(["AAPL"]) == {}


def test_seed_tags_replace_preserves_user_and_reflects_removal(store):
    store.seed_tags([{"tag": "Tier 1 · Core", "source": "config:tier", "tickers": ["NVDA", "AMD"]}])
    store.add_tag("NVDA", "my-thesis", "user")
    # re-seed config:tier WITHOUT AMD → AMD's config tag dropped; NVDA's kept; user kept
    store.seed_tags(
        [{"tag": "Tier 1 · Core", "source": "config:tier", "tickers": ["NVDA"]}],
        replace_sources=["config:tier"],
    )
    tags = store.get_tags(["NVDA", "AMD"])
    assert {"tag": "Tier 1 · Core", "source": "config:tier"} in tags["NVDA"]
    assert {"tag": "my-thesis", "source": "user"} in tags["NVDA"]
    assert "AMD" not in tags  # config tag removed and AMD had no other tags


def test_add_tag_rejects_blank(store):
    with pytest.raises(ValueError):
        store.add_tag("NVDA", "   ")
    with pytest.raises(ValueError):
        store.add_tag("", "x")


def test_config_tag_groups_structure():
    from src.universe_config import config_tag_groups

    groups = config_tag_groups()
    for g in groups:  # tolerant: empty if config absent, else well-formed
        assert g["source"] in {"config:tier", "config:category"}
        assert g["tag"] and isinstance(g["tag"], str)
        assert g["tickers"] and all(isinstance(t, str) and t == t.upper() for t in g["tickers"])
    if groups:  # real config present → both families emitted
        assert {g["source"] for g in groups} == {"config:tier", "config:category"}


def test_cockpit_universe_ticker_state_carry_tags(api_store):
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)  # seed lists
    api_store.seed_tags(
        [
            {"tag": "Mega Cap Tech", "source": "config:category", "tickers": ["AAPL", "MSFT"]},
            {"tag": "watch-me", "source": "user", "tickers": ["AAPL"]},
        ]
    )
    cockpit = {r["ticker"]: r for r in cockpit_watchlist(dal=None, store=api_store)["rows"]}
    assert {(t["tag"], t["source"]) for t in cockpit["AAPL"]["tags"]} == {
        ("Mega Cap Tech", "config:category"),
        ("watch-me", "user"),
    }
    assert cockpit["TSLA"]["tags"] == []  # untagged ticker → empty

    u = {r["ticker"]: r for r in universe(dal=None, store=api_store)["rows"]}
    assert {(t["tag"], t["source"]) for t in u["MSFT"]["tags"]} == {("Mega Cap Tech", "config:category")}

    state = get_ticker_state("AAPL", dal=None, store=api_store)
    assert ("watch-me", "user") in {(t["tag"], t["source"]) for t in state["tags"]}


def test_import_universe_seeds_theme_tags(api_store, monkeypatch):
    # A theme group ("theme:量子計算") becomes a config:theme tag; Holdings does not.
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
    tags = api_store.get_tags(["IONQ", "AAPL"])
    assert tags["IONQ"] == [{"tag": "量子計算", "source": "config:theme"}]
    assert "AAPL" not in tags  # Holdings group is not a theme → no tag

    # Re-import replaces config:theme (idempotent membership) but doesn't double-count
    again = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert again["tags"]["tags_added"] == 2  # replaced then re-added the same 2


def test_user_tag_add_remove_routes(api_store):
    import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    api_store.seed_tags([{"tag": "Mega Cap Tech", "source": "config:category", "tickers": ["AAPL"]}])

    # add a user tag → state reflects it with source='user'
    state = add_ticker_tag("aapl", TagBody(tag="my-watch"), store=api_store)
    pairs = {(t["tag"], t["source"]) for t in state["tags"]}
    assert ("my-watch", "user") in pairs
    assert ("Mega Cap Tech", "config:category") in pairs  # config tag untouched

    # removing the user tag works; the config tag is NOT removable via the API
    assert remove_ticker_tag("AAPL", "my-watch", store=api_store)["removed"] is True
    with pytest.raises(HTTPException) as exc:
        remove_ticker_tag("AAPL", "Mega Cap Tech", store=api_store)  # config tag → 404
    assert exc.value.status_code == 404
    remaining = {(t["tag"], t["source"]) for t in get_ticker_state("AAPL", dal=None, store=api_store)["tags"]}
    assert remaining == {("Mega Cap Tech", "config:category")}  # config survived

    # removing a non-existent user tag → 404
    with pytest.raises(HTTPException) as exc:
        remove_ticker_tag("AAPL", "nope", store=api_store)
    assert exc.value.status_code == 404


def test_user_tag_label_colliding_with_config_is_distinct(api_store):
    # A user tag whose label equals a config tag is a separate source='user' row.
    api_store.seed_tags([{"tag": "Mega Cap Tech", "source": "config:category", "tickers": ["AAPL"]}])
    add_ticker_tag("AAPL", TagBody(tag="Mega Cap Tech"), store=api_store)
    pairs = {(t["tag"], t["source"]) for t in get_ticker_state("AAPL", dal=None, store=api_store)["tags"]}
    assert pairs == {("Mega Cap Tech", "config:category"), ("Mega Cap Tech", "user")}
    # the API-removable one is the user row; config remains
    assert remove_ticker_tag("AAPL", "Mega Cap Tech", store=api_store)["removed"] is True
    pairs = {(t["tag"], t["source"]) for t in get_ticker_state("AAPL", dal=None, store=api_store)["tags"]}
    assert pairs == {("Mega Cap Tech", "config:category")}


def test_add_tag_blank_is_422():
    with pytest.raises(ValidationError):
        TagBody(tag="")


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
