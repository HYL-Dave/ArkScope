import sqlite3

import pytest

from src import sa_capture_store
from src.profile_state import ProfileStateStore
from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
from tests.test_sa_article_body_recovery import article, pick, link


AT = "2026-09-28T03:34:13+00:00"


@pytest.fixture
def scope_case(tmp_path):
    capture = tmp_path / "capture.db"
    profile = tmp_path / "profile.db"
    conn = sa_capture_store.connect(str(capture))
    ProfileStateStore(profile)
    with sqlite3.connect(profile) as p:
        SaTrackingMembershipStore.install(p)
    yield capture, profile, conn
    conn.close()


def context(case):
    from src.sa.article_acquisition_scope import read_article_scope_context
    capture, profile, conn = case
    conn.commit()
    return read_article_scope_context(sa_db=capture, profile_db=profile)


def accept(case):
    capture, profile, conn = case
    conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (AT,))
    conn.commit()
    SaTrackingMembershipStore(profile).reconcile(
        read_sa_tracking_observations(capture), at=AT, bootstrap_actor="attended_user")


def decide(case, aid="1001", operation="comments", **settings):
    from src.sa.article_acquisition_scope import decide_article_acquisition
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
    return decide_article_acquisition(aid, operation=operation,
        settings=ArticleAcquisitionSettings(**settings), context=context(case))


@pytest.mark.parametrize("symbol", ["VISN", "RCL"])
def test_stale_current_does_not_reactivate_former_discussions(scope_case, symbol):
    _, profile, conn = scope_case
    pick(conn, 1, symbol, stale=1)
    pick(conn, 1, symbol, status="closed")
    article(conn, "1001", ticker=symbol)
    accept(scope_case)
    before = list(conn.iterdump())
    result = decide(scope_case)
    assert result["allowed"] is False
    assert result["effective_membership"] == "former"
    assert decide(scope_case, operation="body")["allowed"] is True
    assert decide(scope_case, comment_scope="tracked")["allowed"] is True
    assert list(conn.iterdump()) == before
    assert SaTrackingMembershipStore(profile).list_memberships()[0]["portfolio_status"] == "closed"


@pytest.mark.parametrize("reentry", [False, True])
def test_current_wins_without_rewriting_old_cohort_links(scope_case, reentry):
    _, _, conn = scope_case
    pick(conn, 1, "LIVE", status="closed")
    pick(conn, 2 if reentry else 1, "LIVE", picked="2026-01-01" if reentry else "2024-01-10")
    article(conn, "1001", published="2024-01-10")
    link(conn, 1, 1, "1001")
    accept(scope_case)
    before = list(conn.iterdump())
    result = decide(scope_case)
    assert result["allowed"] is True
    assert result["effective_membership"] == "current"
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("symbol", ["ARCH", "LTHM", "TA"])
def test_terminal_exclusion_survives_fresh_current_metadata(scope_case, symbol):
    _, profile, conn = scope_case
    pick(conn, 1, symbol, status="closed")
    article(conn, "1001", ticker=symbol)
    link(conn, 1, 1, "1001")
    accept(scope_case)
    with sqlite3.connect(profile) as p:
        p.execute("UPDATE sa_tracking_memberships SET reason='terminal_delisting',removed_at=?,current_tracking=0", (AT,))
    pick(conn, 2, symbol, picked="2026-09-01")
    for operation in ("body", "comments"):
        result = decide(scope_case, operation=operation, comment_scope="tracked")
        assert result["allowed"] is False
        assert result["reason_code"] == "sa_article_permanently_excluded"


def test_unknown_ownership_is_body_only_without_source_conflict(scope_case):
    _, _, conn = scope_case
    article(conn, "1001")
    assert decide(scope_case)["allowed"] is False
    assert decide(scope_case, operation="body")["allowed"] is True
    assert decide(scope_case, operation="body", body_scope="current")["allowed"] is False


def test_title_candidate_does_not_authorize_discussion_collection(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "LIVE")
    article(conn, "1001", title="LIVE: Stock Buy", published="2024-01-10")
    accept(scope_case)
    assert decide(scope_case, operation="body", body_scope="current")["allowed"] is True
    assert decide(scope_case, operation="comments")["allowed"] is False
    assert decide(scope_case, operation="comments", comment_scope="tracked")["allowed"] is False


def test_conflicting_source_identity_is_not_overridden_by_wide_scope(scope_case):
    _, _, conn = scope_case
    article(conn, "1001", listed="AAA", detail="BBB")
    for op in ("body", "comments"):
        assert decide(scope_case, operation=op)["allowed"] is False


def test_missing_profile_authority_blocks_without_creating_it(tmp_path):
    from src.sa.article_acquisition_scope import read_article_scope_context
    capture = tmp_path / "capture.db"
    conn = sa_capture_store.connect(str(capture))
    conn.close()
    profile = tmp_path / "missing.db"
    result = read_article_scope_context(sa_db=capture, profile_db=profile)
    assert result["status"] == "unavailable"
    assert not profile.exists()


def test_uninstalled_tracking_is_not_treated_as_empty_exclusions(scope_case):
    from src.sa.article_acquisition_scope import read_article_scope_context
    capture, profile, _ = scope_case
    other = profile.with_name("not-installed.db")
    ProfileStateStore(other)
    assert read_article_scope_context(sa_db=capture, profile_db=other)["status"] == "unavailable"


def manifest(case, **values):
    from src.sa.article_body_recovery import build_recovery_manifest
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
    return build_recovery_manifest(case[0], as_of="2026-09-28",
        settings=ArticleAcquisitionSettings(**values), scope_context=context(case))


def test_default_manifest_includes_old_former_and_unknown_dates(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "OLD", status="closed")
    article(conn, "1001", published="2022-01-01", ticker="OLD")
    article(conn, "1002", published=None)
    accept(scope_case)
    result = manifest(scope_case)
    assert result["status"] == "ok"
    assert {r["article_id"] for r in result["targets"]} == {"1001", "1002"}
    assert "published_date_unknown" in next(r for r in result["targets"] if r["article_id"] == "1002")["reasons"]
    assert result["scope"]["recent_days"] == 0
    assert result["cutoff"] is None


def test_current_only_holds_former_without_deleting_it(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "OLD", status="closed")
    article(conn, "1001", ticker="OLD")
    accept(scope_case)
    before = list(conn.iterdump())
    result = manifest(scope_case, body_scope="current")
    assert result["targets"] == []
    assert result["held"][0]["reason_code"] == "sa_article_former_out_of_scope"
    assert list(conn.iterdump()) == before


def test_age_limit_holds_undated_nonentry_but_not_current_entry(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "LIVE")
    article(conn, "1001", published="2022-01-01")
    article(conn, "1002", published=None)
    article(conn, "1003", published="2020-01-01")
    link(conn, 1, 1, "1001")
    accept(scope_case)
    result = manifest(scope_case, body_lookback_days=365)
    assert [r["article_id"] for r in result["targets"]] == ["1001"]
    assert {r["article_id"] for r in result["held"]} == {"1002", "1003"}
    result = manifest(scope_case, body_lookback_days=2**53 - 1)
    assert {r["article_id"] for r in result["targets"]} == {"1001", "1003"}
    assert result["cutoff"] == "0001-01-01"


def test_preview_policy_hash_changes_without_truncating_inventory(scope_case):
    _, _, conn = scope_case
    for aid in ("1001", "1002", "1003"):
        article(conn, aid)
    first = manifest(scope_case)
    limited = manifest(scope_case, max_articles_per_job=1)
    assert len(limited["targets"]) == 3
    assert first["manifest_id"] != limited["manifest_id"]


def test_accepted_alias_keeps_identity_but_not_origin_mutation(scope_case):
    _, profile, conn = scope_case
    pick(conn, 1, "OLD", status="closed")
    pick(conn, 2, "NEW", picked="2026-01-01")
    article(conn, "1001")
    link(conn, 1, 1, "1001")
    accept(scope_case)
    with sqlite3.connect(profile) as p:
        p.execute("CREATE TABLE ticker_identity_links(source_ticker TEXT,successor_ticker TEXT,reversed_at TEXT)")
        p.execute("INSERT INTO ticker_identity_links VALUES('OLD','NEW',NULL)")
    before = list(conn.iterdump())
    assert decide(scope_case)["allowed"] is True
    assert list(conn.iterdump()) == before


def test_shared_article_current_membership_survives_other_terminal_link(scope_case):
    _, profile, conn = scope_case
    pick(conn, 1, "RETIRED", status="closed")
    pick(conn, 2, "LIVE")
    article(conn, "1001")
    link(conn, 1, 1, "1001")
    link(conn, 2, 2, "1001")
    accept(scope_case)
    with sqlite3.connect(profile) as p:
        p.execute("UPDATE sa_tracking_memberships SET reason='terminal_delisting',removed_at=? WHERE ticker='RETIRED'", (AT,))
    assert decide(scope_case)["allowed"] is True


def test_older_closed_capture_does_not_override_newer_current_authority(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "LIVE")
    article(conn, "1001", ticker="LIVE")
    accept(scope_case)
    conn.execute("UPDATE sa_alpha_picks SET portfolio_status='closed', last_seen_snapshot='2026-08-01T00:00:00+00:00'")
    assert decide(scope_case)["allowed"] is True


def test_unapplied_newer_exit_is_not_stale_current_permission(scope_case):
    _, _, conn = scope_case
    pick(conn, 1, "LIVE")
    article(conn, "1001", ticker="LIVE")
    accept(scope_case)
    conn.execute("UPDATE sa_alpha_picks SET portfolio_status='closed', last_seen_snapshot='2026-09-29T00:00:00+00:00'")
    assert decide(scope_case)["allowed"] is False


def test_removed_old_cohort_does_not_disable_legitimate_new_cohort(scope_case):
    _, profile, conn = scope_case
    pick(conn, 1, "AGAIN", status="closed")
    pick(conn, 2, "AGAIN", picked="2026-02-01")
    article(conn, "1001")
    article(conn, "1002")
    link(conn, 1, 1, "1001")
    link(conn, 2, 2, "1002")
    accept(scope_case)
    store = SaTrackingMembershipStore(profile)
    old = next(r for r in store.list_memberships() if r["picked_date"] == "2024-01-10")
    store.remove(old["membership_id"], at=AT)
    assert decide(scope_case, "1001")["allowed"] is False
    assert decide(scope_case, "1002")["allowed"] is True


def test_symbol_reuse_without_article_link_does_not_inherit_new_current(scope_case):
    _, profile, conn = scope_case
    pick(conn, 1, "REUSE", status="closed")
    pick(conn, 2, "REUSE", picked="2026-02-01")
    article(conn, "1001", ticker="REUSE")
    accept(scope_case)
    with sqlite3.connect(profile) as p:
        p.execute("UPDATE sa_tracking_memberships SET reason='terminal_delisting',removed_at=? WHERE picked_date='2024-01-10'", (AT,))
    result = decide(scope_case)
    assert result["allowed"] is False
    assert result["reason_code"] == "sa_article_identity_conflict"


def test_manifest_refuses_context_from_a_different_capture_snapshot(scope_case):
    from src.sa.article_body_recovery import build_recovery_manifest
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
    capture, _, conn = scope_case
    article(conn, "1001")
    old = context(scope_case)
    article(conn, "1002")
    conn.commit()
    result = build_recovery_manifest(capture, settings=ArticleAcquisitionSettings(), scope_context=old)
    assert result["status"] == "unavailable"
    assert result["targets"] == []
