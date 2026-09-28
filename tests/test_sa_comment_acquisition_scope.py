"""Discussion work follows effective membership without rewriting retained history."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from src.profile_state import ProfileStateStore
from src.sa.article_acquisition_settings import ARTICLE_SETTINGS_KEY
from src.tools.backends.sa_capture_backend import SACaptureBackend
from src.tools.data_access import DataAccessLayer
from tests.test_sa_article_acquisition_scope import scope_case, accept, AT
from tests.test_sa_article_body_recovery import pick, article, link, NARRATIVE


@pytest.fixture
def scope_capture(scope_case, monkeypatch, tmp_path):
    capture, profile, conn = scope_case
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(capture))
    backend = SACaptureBackend(sa_db=str(capture), market_db=str(tmp_path / "market.db"))
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)

    def setup(state, path="count"):
        pick(conn, 1, "LIVE", status="current" if state == "current" else "closed")
        if state in {"partial", "reentered"}:
            pick(conn, 1 if state == "partial" else 2, "LIVE", picked="2024-01-10" if state == "partial" else "2026-01-01")
        article(conn, "1001", ticker="LIVE", body=None if path == "first_detail" else NARRATIVE)
        link(conn, 1, 1, "1001")
        accept(scope_case)
        if state == "terminal":
            with sqlite3.connect(profile) as p:
                p.execute("UPDATE sa_tracking_memberships SET reason='terminal_delisting',removed_at=?,current_tracking=0", (AT,))
        if path != "first_detail":
            backend.update_article_comments("1001", [{"comment_id":"old", "commenter":"reader", "comment_text":"Retained old discussion"}],
                provider_comments_count=1,comment_scan_mode="backfill",comment_scan_stop_reason="stable_bottom",comment_scan_stable_bottom_rounds=5)
            conn.execute("UPDATE sa_articles SET comments_fetched_at='2020-01-01T00:00:00+00:00',comment_scan_attempted_at='2020-01-01T00:00:00+00:00'")
            if path == "pending":
                conn.execute("UPDATE sa_articles SET comment_backfill_pending=1,comment_recovery_state='pending'")
            conn.commit()
        if path == "enrichment":
            monkeypatch.setattr(backend, "reconcile_sa_articles", lambda **kw: {"status":"ok","enrichment":[{"article_id":"1001", "url":"https://seekingalpha.com/article/1001-fixture"}]})

    def history():
        return {
            "links": conn.execute("SELECT * FROM sa_pick_article_links").fetchall(),
            "comments": conn.execute("SELECT * FROM sa_article_comments").fetchall(),
            "scan": conn.execute("SELECT comments_fetched_at,comment_backfill_pending,comment_scan_attempted_at,comment_scan_policy FROM sa_articles").fetchall(),
        }

    def select_comments(mode="quick", path="count"):
        metadata = [] if path in {"ttl", "pending"} else [{"article_id":"1001", "url":"https://seekingalpha.com/article/1001-fixture",
            "title":"Portfolio review", "published_date":"2026-09-01", "ticker":"LIVE",
            "comments_count":2, "comments_count_observed_at":"2026-09-28T04:00:00Z"}]
        return dal.save_sa_articles_meta(metadata, mode=mode)

    return SimpleNamespace(setup=setup,history=history,select_comments=select_comments,conn=conn,profile=profile,capture=capture,dal=dal)


@pytest.mark.parametrize("state", ["current", "partial", "reentered", "former", "terminal"])
@pytest.mark.parametrize("mode,path", [(mode,path) for mode in ("quick","full","backfill")
    for path in ("count","pending","enrichment","first_detail")] + [("full","ttl"),("backfill","ttl")])
def test_every_selector_uses_current_first_membership(scope_capture, state, mode, path):
    scope_capture.setup(state,path)
    before = scope_capture.history()
    reply = scope_capture.select_comments(mode,path)
    assert reply["status"] == "ok", reply
    groups = reply["need_content"] + reply["need_comments"] + reply["reconciliation"].get("enrichment",[])
    eligible_ids = {item["article_id"] for item in groups if item.get("comments_allowed",True)}
    if state in {"current","partial","reentered"}:
        assert "1001" in eligible_ids, reply
    else:
        assert "1001" not in eligible_ids, reply
        assert reply["comment_scope"]["excluded_count"] == 1
        if state == "terminal":
            assert not groups, "permanent exclusions cannot be requeued by fresh metadata"
    assert scope_capture.history() == before


def test_tracked_scope_is_opt_in_and_rechecked_after_narrowing(scope_capture):
    scope_capture.setup("former")
    store = ProfileStateStore(scope_capture.profile)
    store.set_setting(ARTICLE_SETTINGS_KEY,json.dumps({"comment_scope":"tracked"}))
    assert scope_capture.select_comments()["need_comments"]
    store.set_setting(ARTICLE_SETTINGS_KEY,json.dumps({"comment_scope":"current"}))
    assert scope_capture.select_comments()["need_comments"] == []


def test_missing_authority_is_deferred_not_empty_success(scope_capture):
    scope_capture.setup("current")
    with sqlite3.connect(scope_capture.profile) as p:
        p.execute("DROP TABLE sa_tracking_memberships")
    reply = scope_capture.select_comments()
    assert reply["status"] == "deferred"
    assert reply["error_code"] == "sa_article_scope_unavailable"
    assert reply["need_comments"] == []


def test_native_eligibility_is_fresh_read_only_and_exact(scope_capture):
    from src.sa_native_host import handle_message
    scope_capture.setup("reentered")
    message = {"action":"get_article_acquisition_eligibility","operation":"comments","article_id":"1001"}
    before = scope_capture.history()
    assert handle_message(message)["allowed"] is True
    with sqlite3.connect(scope_capture.profile) as p:
        p.execute("UPDATE sa_tracking_memberships SET reason='terminal_delisting',removed_at=?,current_tracking=0", (AT,))
    assert handle_message(message)["allowed"] is False
    assert handle_message({**message,"operation":"delete"})["status"] == "error"
    assert handle_message({**message,"article_id":"1001-extra"})["status"] == "error"
    assert scope_capture.history() == before


def test_body_only_capture_does_not_create_a_comment_attempt(scope_capture):
    scope_capture.setup("former")
    before = scope_capture.history()
    result = scope_capture.dal.save_sa_article_with_comments("1001",NARRATIVE,[],capture_comments=False)
    assert result["body_saved"] is True
    assert result["comments_scope_skipped"] is True
    assert scope_capture.history() == before


def test_native_body_only_receipt_never_advances_comment_checkpoint(scope_capture):
    from src.sa_native_host import _handle_save_article_content
    scope_capture.setup("former")
    before = scope_capture.history()
    result = _handle_save_article_content(scope_capture.dal,{"article_id":"1001","body_markdown":NARRATIVE,
        "comments":[],"comments_scope_skipped":True})
    assert result["status"] == "ok"
    assert result["body_saved"] is True
    assert result["comments_scope_skipped"] is True
    assert scope_capture.history() == before


def test_native_observes_full_exit_then_reentry_without_moving_old_link(scope_capture):
    from src.sa_native_host import handle_message
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
    scope_capture.setup("current")
    message = {"action":"get_article_acquisition_eligibility","operation":"comments","article_id":"1001"}
    old_links = scope_capture.history()["links"]
    assert handle_message(message)["allowed"] is True
    scope_capture.conn.execute("UPDATE sa_alpha_picks SET is_stale=1 WHERE portfolio_status='current'")
    pick(scope_capture.conn,1,"LIVE",status="closed")
    at = "2026-09-28T04:00:00+00:00"
    scope_capture.conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=? WHERE is_stale=0", (at,))
    scope_capture.conn.commit()
    tracking = SaTrackingMembershipStore(scope_capture.profile)
    tracking.reconcile(read_sa_tracking_observations(scope_capture.capture),at=at)
    assert handle_message(message)["allowed"] is False
    pick(scope_capture.conn,2,"LIVE",picked="2026-09-28")
    at = "2026-09-28T05:00:00+00:00"
    scope_capture.conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=? WHERE is_stale=0", (at,))
    scope_capture.conn.commit()
    tracking.reconcile(read_sa_tracking_observations(scope_capture.capture),at=at)
    assert handle_message(message)["allowed"] is True
    assert scope_capture.history()["links"] == old_links
