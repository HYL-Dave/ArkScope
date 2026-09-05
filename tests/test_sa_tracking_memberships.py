from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.profile_state import ProfileStateStore


AT = "2026-09-05T01:00:00Z"


def observation(lineage: int, ticker: str, status: str = "closed", picked: str = "2025-01-01"):
    return {
        "lineage_id": lineage, "ticker": ticker, "picked_date": picked,
        "portfolio_status": status, "observed_at": AT,
    }


@pytest.fixture
def store(tmp_path: Path):
    from src.sa_tracking_memberships import SaTrackingMembershipStore

    path = tmp_path / "profile.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        SaTrackingMembershipStore.install(conn)
    return SaTrackingMembershipStore(path)


def test_former_removal_survives_sync_bootstrap_and_renamed_observation(store):
    old = observation(1, "OLD")
    store.reconcile((old,), at=AT, bootstrap_actor="attended_user")
    member = store.list_memberships()[0]
    store.remove(member["membership_id"], at=AT)
    store.reconcile((old,), at=AT, bootstrap_actor="attended_user")
    store.reconcile((observation(2, "NEW"),), at=AT, identity_links={"OLD": "NEW"})
    rows = store.list_memberships()
    assert len(rows) == 1
    assert rows[0]["state"] == "removed"
    assert store.active_sources(identity_links={"OLD": "NEW"}) == {}
    store.restore(member["membership_id"], at=AT)
    assert store.active_sources(identity_links={"OLD": "NEW"}) == {
        "sa_alpha_picks_former": {"NEW"},
    }


def test_unremoved_membership_follows_verified_alias_without_rewriting_origin(store):
    store.reconcile((observation(1, "OLD"),), at=AT, bootstrap_actor="attended_user")
    assert store.active_sources(identity_links={"OLD": "NEW"}) == {
        "sa_alpha_picks_former": {"NEW"},
    }
    assert store.list_memberships()[0]["ticker"] == "OLD"


def test_membership_display_follows_persisted_identity_without_erasing_removed_intent(store):
    store.reconcile((observation(1, "OLD"),), at=AT, bootstrap_actor="attended_user")
    member_id = store.list_memberships()[0]["membership_id"]
    store.remove(member_id, at=AT)
    with sqlite3.connect(store.path) as conn:
        conn.execute("CREATE TABLE ticker_identity_links (source_ticker TEXT, successor_ticker TEXT, reversed_at TEXT)")
        conn.execute("INSERT INTO ticker_identity_links VALUES ('OLD','NEW',NULL)")
    assert store.list_memberships()[0]["ticker"] == "NEW"
    assert store.list_memberships()[0]["state"] == "removed"
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT ticker FROM sa_tracking_memberships").fetchone()[0] == "OLD"


def test_current_to_former_is_retained_but_unseen_closed_is_candidate(store):
    store.reconcile((observation(1, "LIVE", "current"),), at=AT)
    store.reconcile((observation(1, "LIVE"), observation(2, "GAP")), at=AT)
    assert store.active_sources() == {"sa_alpha_picks_former": {"LIVE"}}
    states = {row["ticker"]: row["state"] for row in store.list_memberships()}
    assert states == {"GAP": "candidate", "LIVE": "tracking"}
    gap = next(row for row in store.list_memberships() if row["ticker"] == "GAP")
    store.accept(gap["membership_id"], at=AT)
    assert store.active_sources() == {"sa_alpha_picks_former": {"GAP", "LIVE"}}


def test_related_current_with_same_pick_anchor_is_held_not_globally_blacklisted(store):
    store.reconcile((observation(1, "OLD"),), at=AT, bootstrap_actor="attended_user")
    store.remove(store.list_memberships()[0]["membership_id"], at=AT)
    relations = {("OLD", "ACQ")}
    store.reconcile((observation(2, "ACQ", "current"),), at=AT, related_securities=relations)
    assert store.active_sources() == {}
    store.reconcile((observation(3, "ACQ", "current", "2026-08-01"),), at=AT, related_securities=relations)
    assert store.active_sources() == {"sa_alpha_picks_current": {"ACQ"}}


def test_removed_membership_cannot_be_accepted_instead_of_explicit_restore(store):
    store.reconcile((observation(1, "OLD"),), at=AT, bootstrap_actor="attended_user")
    member_id = store.list_memberships()[0]["membership_id"]
    store.remove(member_id, at=AT)
    with pytest.raises(ValueError, match="membership_restore_required"):
        store.accept(member_id, at=AT)


def test_receipts_are_append_only_idempotent_and_bind_the_observation(store):
    rows = (observation(1, "OLD"),)
    store.reconcile(rows, at=AT, bootstrap_actor="attended_user")
    store.reconcile(rows, at=AT, bootstrap_actor="attended_user")
    with sqlite3.connect(store.path) as conn:
        receipt = conn.execute("SELECT actor, observation_sha256 FROM sa_tracking_events").fetchall()
        assert len(receipt) == 1
        assert receipt[0][0] == "attended_user"
        assert len(receipt[0][1]) == 64
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            conn.execute("DELETE FROM sa_tracking_events")


def test_ambiguous_alias_binding_is_not_silently_accepted(store):
    store.reconcile((observation(1, "AAA"), observation(2, "BBB")), at=AT, bootstrap_actor="attended_user")
    store.reconcile((observation(3, "NEW", "current"),), at=AT, identity_links={"AAA": "NEW", "BBB": "NEW"})
    member = next(row for row in store.list_memberships() if row["ticker"] == "NEW")
    assert member["state"] == "candidate"
    assert member["reason"] == "identity_ambiguous"


def test_malformed_observation_rolls_back_whole_reconciliation(store):
    with pytest.raises(ValueError, match="tracking_observation"):
        store.reconcile((observation(1, "OK", "current"), observation(2, "BAD*")), at=AT)
    assert store.list_memberships() == []


def test_sync_projection_detects_unapplied_sa_observations_without_writing(store):
    rows = (observation(1, "OLD", "current"),)
    before = store.path.read_bytes()
    assert store.synchronization_status(rows) == "pending"
    assert store.path.read_bytes() == before
    store.reconcile(rows, at=AT)
    assert store.synchronization_status(rows) == "current"
    changed = (observation(1, "OLD", "closed"),)
    assert store.synchronization_status(changed) == "pending"
    store.reconcile(changed, at=AT)
    store.remove(store.list_memberships()[0]["membership_id"], at=AT)
    assert store.synchronization_status(changed) == "current"
    assert store.active_sources() == {}
