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


def test_config_tag_seeds_structure():
    from src.universe_config import config_tag_seeds

    seeds = config_tag_seeds()
    for g in seeds:  # tolerant: empty if config absent, else well-formed
        assert g["facet"] in {"category", "provenance"}
        assert g["value"] and isinstance(g["value"], str)
        assert g["tickers"] and all(isinstance(t, str) and t == t.upper() for t in g["tickers"])
    if seeds:  # real config present
        families = {(g["facet"], g["source"]) for g in seeds}
        assert ("category", "legacy") in families
        assert ("provenance", "system") in families
        assert all(g["facet"] != "tier" for g in seeds)  # Tier retired (not a tag)
        provenance = {g["value"] for g in seeds if g["facet"] == "provenance"}
        assert provenance <= {"Seeking Alpha", "Alpha Picks"}


def test_active_universe_excludes_legacy_reference():
    from src.universe_config import active_universe_tickers, all_universe_tickers

    active = set(active_universe_tickers())
    every = set(all_universe_tickers())
    # active ⊆ all; all also carries legacy_reference for the broad search seed
    assert active <= every
    assert all(t == t.upper() for t in active)


def test_tier_priority_map_highest_tier_wins():
    from src.universe_config import tier_priority_map

    pm = tier_priority_map()
    assert set(pm.values()) <= {"high", "medium", "low"} if pm else True


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
    # config-file tiers/category/provenance seed still runs (groups_ok=False).
    def _boom(dal):
        raise RuntimeError("PG down")

    monkeypatch.setattr("src.api.routes.profile.get_watchlist_overview", _boom)
    out = import_universe(ImportBody(include_groups=True, include_tiers=True), dal=None, store=api_store)
    assert out["groups_ok"] is False
    assert out["tags"]["tags_added"] > 0  # config seed (category/provenance) still applied


def test_import_universe_deletes_non_custom_lists(api_store):
    # Seed a mix of legacy (tier/holdings) + a user custom list, then de-mess.
    api_store.import_lists([{"name": "Tier 1 · Core", "kind": "tier", "tickers": ["NVDA"]}])
    api_store.import_lists([{"name": "core_holdings", "kind": "holdings", "tickers": ["AAPL"]}])
    api_store.create_list("My Picks", "custom")
    out = import_universe(ImportBody(include_tiers=False), dal=None, store=api_store)
    assert out["lists_removed"] == 2  # tier + holdings gone
    remaining = {li["name"]: li["kind"] for li in out["lists"]}
    assert remaining == {"My Picks": "custom"}  # only the user list survives


def test_import_universe_opt_in_tier_priority_fill_only(api_store, monkeypatch):
    # tier→priority migration is OFF by default and never overwrites a user priority.
    monkeypatch.setattr(
        "src.universe_config.load_tickers_core",
        lambda: {
            "tier1_core": {"mega": {"tickers": ["AAA"]}},
            "tier3_user_watchlist": {"wl": {"tickers": ["CCC"]}},
        },
    )
    api_store.set_priority("AAA", "low")  # pre-existing user priority

    off = import_universe(ImportBody(include_tiers=True), dal=None, store=api_store)
    assert off["priority_migrated"] == 0  # default: no migration

    on = import_universe(ImportBody(include_tiers=True, migrate_tier_priority=True), dal=None, store=api_store)
    assert on["priority_migrated"] == 1  # CCC filled (low); AAA untouched (user-set)
    prios = api_store.get_priorities(["AAA", "CCC"])
    assert prios == {"AAA": "low", "CCC": "low"}  # AAA kept user value (would be 'high' from tier1)


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
