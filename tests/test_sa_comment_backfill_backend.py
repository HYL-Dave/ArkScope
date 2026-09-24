"""Hermetic acquisition continuity tests using the real SQLite backend and DAL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from src import sa_capture_store as store
from src.sa.article_reader import read_article
from src.tools.backends.sa_capture_backend import SACaptureBackend
from src.tools.data_access import DataAccessLayer


@pytest.fixture
def backend(tmp_path):
    return SACaptureBackend(sa_db=str(tmp_path / "sa.db"), market_db=str(tmp_path / "market.db"))


def meta(article_id, count=5):
    return dict(article_id=article_id, url=f"https://seekingalpha.com/article/{article_id}",
                title=article_id, published_date="2026-09-01", comments_count=count,
                comments_count_observed_at="2026-09-24T00:00:00Z")


def comment(comment_id="c1", **changes):
    return dict(dict(comment_id=comment_id, commenter=comment_id,
                     comment_text="Retained complete comment " + comment_id, upvotes=0), **changes)


def row(backend, article_id="a"):
    return backend.get_sa_article_with_comments(article_id)


def scan(backend, article_id="a", comments=None, reason="stable_bottom", mode="backfill", rounds=5, count=5):
    return backend.update_article_comments(
        article_id, [comment()] if comments is None else comments,
        provider_comments_count=count, comment_scan_mode=mode,
        comment_scan_stop_reason=reason, comment_scan_stable_bottom_rounds=rounds,
    )


def seed(backend, article_id="a", count=5):
    backend.upsert_sa_articles_meta([meta(article_id, count)])
    # Body-only retention is not a comment acquisition attempt.
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown='body' WHERE article_id=?", (article_id,))


def age_attempt(backend, article_id="a", hours=7):
    attempted = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET comment_scan_attempted_at=? WHERE article_id=?", (attempted, article_id))


def recent_policy(**changes):
    return dict(dict(scope="recent", window_days=30, reference_at="2026-09-24T12:00:00Z",
                     cutoff_at="2026-08-25T12:00:00Z", date_basis="displayed_date_browser_local_if_unzoned",
                     coverage="unverified", recent_count=1, older_count=9, unknown_date_count=0,
                     context_count=0, deferred_historical_controls=2), **changes)


def test_recent_terminal_does_not_require_historical_count_or_overwrite_history(backend, tmp_path):
    seed(backend, count=100)
    scan(backend, comments=[comment("old", comment_date="2026-01-01")], count=90)
    result = backend.update_article_comments("a", [comment("new", comment_date="2026-09-23")],
        provider_comments_count=100, comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5, comment_scan_policy=recent_policy())
    assert result["comment_backfill_pending"] is False
    assert result["comment_scan_policy"]["coverage"] == "unverified"
    assert row(backend)["provider_comments_count_at_last_scan"] == 90
    assert {c["comment_id"] for c in row(backend)["comments"]} == {"old", "new"}
    coverage = read_article(backend._sa_db, "a")["coverage"]["comments"]
    assert coverage["scan_policy"]["scope"] == "recent"
    assert coverage["complete"] is None
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    assert dal.save_sa_articles_meta([meta("a", 100)])["need_comments"] == []
    assert dal.save_sa_articles_meta([meta("a", 101)])["need_comments"][0]["article_id"] == "a"


def test_old_only_recent_scan_is_not_scheduled_forever_as_missing_history(backend, tmp_path):
    seed(backend)
    result = backend.update_article_comments("a", [comment("old", comment_date="2026-01-01")], provider_comments_count=5,
        comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5, comment_scan_policy=recent_policy(recent_count=0))
    assert result["comment_scan_usable"] is True
    assert result["comment_backfill_pending"] is False
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    assert dal.save_sa_articles_meta([meta("a")])["need_comments"] == []


@pytest.mark.parametrize("enrichment", [False, True])
def test_historical_pending_cannot_promote_or_delay_completed_recent_work(backend, tmp_path, monkeypatch, enrichment):
    seed(backend)
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET comment_recovery_state='pending' WHERE article_id='a'")
    backend.update_article_comments("a", [comment()], provider_comments_count=5,
        comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5, comment_scan_policy=recent_policy())
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET comments_fetched_at='2020-01-01T00:00:00+00:00' WHERE article_id='a'")
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    if enrichment:
        monkeypatch.setattr(backend, "reconcile_sa_articles", lambda **kwargs: {
            "status":"ok", "enrichment":[{"article_id":"a", "url":"u"}]})
    result = dal.save_sa_articles_meta([meta("a")], mode="full")
    items = result["reconciliation"]["enrichment"] if enrichment else result["need_comments"]
    assert len(items) == 1
    assert "comment_scan_mode" not in items[0]


def test_manual_capture_without_count_keeps_known_scheduling_checkpoint(backend, tmp_path):
    seed(backend)
    scan(backend, count=5)
    backend.save_article_with_comments("a", "body", [comment()],
        comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5, comment_scan_policy=recent_policy())
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    assert dal.save_sa_articles_meta([meta("a", 5)])["need_comments"] == []


@pytest.mark.parametrize("changes", [{"scope":"all"}, {"window_days":0}, {"coverage":"complete"},
                                      {"recent_count":-1}, {"cutoff_at":"invalid"}])
def test_invalid_scope_receipt_cannot_modify_article_or_comments(backend, changes):
    seed(backend)
    before = row(backend)
    with pytest.raises(ValueError, match="comment_scan_policy"):
        backend.save_article_with_comments("a", "replacement body", [comment()], comment_scan_policy=recent_policy(**changes))
    assert row(backend) == before


@pytest.mark.parametrize("reason", ["timeout", "max_scrolls"])
@pytest.mark.parametrize("empty", [False, True])
def test_budget_stop_preserves_comments_without_advancing_checkpoint(backend, reason, empty):
    seed(backend)
    scan(backend, count=2)
    before = row(backend)
    result = scan(backend, comments=[] if empty else [comment(), comment("c2")], reason=reason)
    after = row(backend)
    assert after["provider_comments_count_at_last_scan"] == 2
    assert after["comment_backfill_pending"] == 1
    assert after["comment_scan_stop_reason"] == reason
    assert after["comment_scan_attempted_at"]
    assert len(after["comments"]) == (1 if empty else 2)
    assert result["net_new_comments"] == (0 if empty else 1)
    assert after["comment_recovery_state"] == before["comment_recovery_state"]
    coverage = read_article(backend._sa_db, "a")["coverage"]["comments"]
    assert coverage["backfill_pending"] is True
    assert coverage["scan_stop_reason"] == reason
    assert "comment_backfill_pending" in coverage["gap_reasons"]


@pytest.mark.parametrize("reason,rounds", [(None, 5), ("unknown", 5), ("stable_bottom", 4)])
def test_only_terminal_evidence_clears_pending(backend, reason, rounds):
    seed(backend)
    scan(backend, reason="timeout")
    scan(backend, reason=reason, rounds=rounds)
    assert row(backend)["comment_backfill_pending"] == 1
    assert row(backend)["provider_comments_count_at_last_scan"] is None
    scan(backend)
    assert row(backend)["comment_backfill_pending"] == 0
    assert row(backend)["provider_comments_count_at_last_scan"] == 5


@pytest.mark.parametrize("mode,rounds", [("quick", 2), ("full", 4), ("backfill", 5)])
def test_completion_uses_existing_profile_thresholds(backend, mode, rounds):
    seed(backend)
    scan(backend, reason="timeout")
    scan(backend, mode=mode, rounds=rounds - 1)
    assert row(backend)["comment_backfill_pending"] == 1
    scan(backend, mode=mode, rounds=rounds)
    assert row(backend)["comment_backfill_pending"] == 0


def test_unknown_first_scan_does_not_fabricate_completion(backend):
    seed(backend)
    scan(backend, reason=None)
    assert row(backend)["provider_comments_count_at_last_scan"] is None
    assert row(backend)["comment_backfill_pending"] == 1


def test_controls_unresolved_records_attempt_without_mutating_comments(backend):
    seed(backend)
    scan(backend, count=2)
    before = row(backend)
    scan(backend, comments=[comment(comment_text="truncated")], reason="controls_unresolved")
    after = row(backend)
    assert after["comments"] == before["comments"]
    assert after["provider_comments_count_at_last_scan"] == 2
    assert after["comments_fetched_at"] == before["comments_fetched_at"]
    assert after["comment_backfill_pending"] == 1


@pytest.mark.parametrize("upvotes", [0, None])
def test_exact_persisted_values_skip_update_but_enrichments_and_edits_write(backend, upvotes):
    seed(backend)
    scan(backend, comments=[comment(upvotes=upvotes)])
    with store.connect(backend._sa_db) as conn:
        conn.executescript("""
            CREATE TABLE comment_updates (comment_id TEXT);
            CREATE TRIGGER audit_comment_update AFTER UPDATE ON sa_article_comments
            BEGIN INSERT INTO comment_updates VALUES (new.comment_id); END;
        """)
    result = scan(backend, comments=[comment(upvotes=upvotes)])
    with store.connect(backend._sa_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM comment_updates").fetchone()[0] == 0
    assert result["changed_comments"] == 0
    assert result["skipped_comments"] == 1
    rich = comment(upvotes=3, comment_date="2026-09-01T00:00:00Z", parent_comment_id="parent")
    result = scan(backend, comments=[rich, comment("c2")])
    assert result["net_new_comments"] == 1
    assert result["changed_comments"] == 1
    assert row(backend)["comments"][0]["upvotes"] == 3
    scan(backend, comments=[dict(rich, comment_text="A real shorter edit")])
    assert any(c["comment_text"] == "A real shorter edit" for c in row(backend)["comments"])


def test_unsafe_partial_observation_does_not_shorten_existing_text(backend):
    seed(backend)
    scan(backend)
    original = row(backend)["comments"][0]["comment_text"]
    scan(backend, comments=[comment(comment_text="Retained", upvotes=2)], reason="timeout")
    assert row(backend)["comments"][0]["comment_text"] == original
    assert row(backend)["comments"][0]["upvotes"] == 2


def test_per_article_first_capture_and_ordinary_changed_count(backend, tmp_path):
    seed(backend, "old")
    scan(backend, "old")
    seed(backend, "first-comments", count=0)
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    result = dal.save_sa_articles_meta([meta("old", 6), meta("new"), meta("first-comments", 0)])
    assert result["need_content"][0]["comment_scan_mode"] == "backfill"
    items = {a["article_id"]: a for a in result["need_comments"]}
    assert "comment_scan_mode" not in items["old"]
    assert items["first-comments"]["comment_scan_mode"] == "backfill"
    assert "new" not in items


@pytest.mark.parametrize("mode", ["quick", "full", "backfill"])
def test_pending_retry_cooldown_and_once_per_pass(backend, tmp_path, mode):
    for article_id in ("a", "b", "changed"):
        seed(backend, article_id)
        scan(backend, article_id)
    for article_id in ("a", "b"):
        scan(backend, article_id, reason="timeout")
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    incoming = [meta("a", 6), meta("a", 6), meta("b", 6), meta("changed", 6)]
    result = dal.save_sa_articles_meta(incoming, mode=mode)
    ids = [a["article_id"] for a in result["need_comments"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == ({"a", "b", "changed"} if mode == "backfill" else {"changed"})
    for article_id in ("a", "b"):
        age_attempt(backend, article_id)
    result = dal.save_sa_articles_meta(incoming, mode=mode)
    pending = [a for a in result["need_comments"] if a["article_id"] != "changed"]
    assert len(pending) == (1 if mode == "quick" else 2)
    assert all(a["comment_scan_mode"] == "backfill" for a in pending)
    assert not result["need_content"]


def test_empty_timeout_does_not_loop_as_first_capture(backend, tmp_path):
    seed(backend)
    scan(backend, comments=[], reason="timeout")
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    assert dal.save_sa_articles_meta([meta("a")])["need_comments"] == []
    age_attempt(backend)
    assert dal.save_sa_articles_meta([meta("a")])["need_comments"][0]["comment_scan_mode"] == "backfill"


def test_first_reconciliation_enrichment_uses_backfill(backend, tmp_path):
    from tests.test_sa_article_reconciliation_backend import _article, _pick, _refresh

    _refresh(backend, "current", [_pick()])
    incoming = _article("bodyless", title="Stock Buy: a new portfolio position", ticker=None, list_ticker=None)
    backend.upsert_sa_articles_meta([incoming])
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    result = dal.save_sa_articles_meta([incoming], mode="quick")
    assert result["reconciliation"]["enrichment"] == [{
        "article_id": "bodyless",
        "url": "https://seekingalpha.com/alpha-picks/articles/bodyless-fixture",
        "comment_scan_mode": "backfill",
    }]


def test_enrichment_cannot_bypass_pending_retry_cooldown(backend, tmp_path):
    from tests.test_sa_article_reconciliation_backend import _article, _pick, _refresh

    _refresh(backend, "current", [_pick()])
    incoming = _article("bodyless", title="Stock Buy: a new portfolio position", ticker=None, list_ticker=None)
    backend.upsert_sa_articles_meta([incoming])
    scan(backend, "bodyless", reason="timeout")
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    result = dal.save_sa_articles_meta([incoming], mode="quick")
    assert result["need_content"] == result["need_comments"] == []
    assert result["reconciliation"]["enrichment"] == []


def test_quick_pending_body_work_shares_the_single_retry_budget(backend, tmp_path):
    for article_id in ("a", "b"):
        backend.upsert_sa_articles_meta([meta(article_id)])
        scan(backend, article_id, reason="timeout")
        age_attempt(backend, article_id)
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    result = dal.save_sa_articles_meta([meta("a"), meta("b")])
    assert len(result["need_content"]) + len(result["need_comments"]) == 1


@pytest.mark.parametrize("body", [True, False])
def test_dal_save_returns_boolean_pending_and_attempt_for_empty_capture(backend, tmp_path, body):
    seed(backend)
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    kwargs = dict(provider_comments_count=5, comment_scan_stop_reason="timeout", comment_scan_mode="backfill")
    result = (dal.save_sa_article_with_comments("a", "valid body", [], **kwargs) if body
              else dal.save_sa_comments_only("a", [], **kwargs))
    assert result["comment_backfill_pending"] is True
    assert result["comment_scan_attempted_at"] == row(backend)["comment_scan_attempted_at"]
    assert result["comment_scan_stop_reason"] == "timeout"


@pytest.mark.parametrize("mode,limit", [("full", 2), ("backfill", 3)])
@pytest.mark.parametrize("identity_pending", [False, True])
def test_pending_work_retains_configured_caps_and_priority(backend, tmp_path, monkeypatch, mode, limit, identity_pending):
    from src.agents.config import get_agent_config

    config = get_agent_config()
    monkeypatch.setattr(config, "sa_comments_backfill_per_full_scan", 2)
    monkeypatch.setattr(config, "sa_comments_backfill_per_backfill_scan", 3)
    for article_id in ("p1", "p2", "p3", "p4", "ttl", "changed"):
        seed(backend, article_id)
        scan(backend, article_id)
        if article_id.startswith("p"):
            if identity_pending:
                scan(backend, article_id, comments=[comment("new")], count=6, mode="quick", rounds=2)
                assert row(backend, article_id)["comment_recovery_state"] == "pending"
                assert row(backend, article_id)["comment_backfill_pending"] == 0
            else:
                scan(backend, article_id, reason="timeout")
            age_attempt(backend, article_id)
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET comments_fetched_at='2020-01-01T00:00:00+00:00' WHERE article_id='ttl'")
    dal = DataAccessLayer(base_path=tmp_path, backend=backend)
    result = dal.save_sa_articles_meta([meta("changed", 6)], mode=mode)
    ids = [item["article_id"] for item in result["need_comments"]]
    assert ids == ["changed", "p4", "p3", "p2"][:limit + 1]


def test_v4_migration_is_concurrent_and_preserves_unknown_history(tmp_path):
    path = str(tmp_path / "old.db")
    with store.connect(path) as conn:
        conn.execute("INSERT INTO sa_articles(article_id,url,title,comments_fetched_at) VALUES ('a','u','t','2026-01-01')")
        for column in ("comment_backfill_pending", "comment_scan_attempted_at", "comment_scan_stop_reason", "comment_scan_policy"):
            if column in {r[1] for r in conn.execute("PRAGMA table_info(sa_articles)")}:
                conn.execute(f"ALTER TABLE sa_articles DROP COLUMN {column}")
        conn.execute("DELETE FROM schema_migrations WHERE version > 4")
        conn.execute("PRAGMA user_version=4")

    def migrate(_):
        conn = store.connect(path)
        try:
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(migrate, range(4))) == [store.SCHEMA_VERSION] * 4
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT comments_fetched_at, comment_backfill_pending, comment_scan_attempted_at, comment_scan_stop_reason FROM sa_articles").fetchone() == ("2026-01-01", 0, None, None)
        assert conn.execute("SELECT count(*) FROM schema_migrations WHERE version=5").fetchone()[0] == 1


@pytest.fixture
def v4_backend(backend):
    seed(backend)
    with store.connect(backend._sa_db) as conn:
        for column in ("comment_backfill_pending", "comment_scan_attempted_at", "comment_scan_stop_reason", "comment_scan_policy"):
            conn.execute(f"ALTER TABLE sa_articles DROP COLUMN {column}")
        conn.execute("DELETE FROM schema_migrations WHERE version>4")
        conn.execute("PRAGMA user_version=4")
    return backend


def test_reader_keeps_v4_capture_readable_without_migration(v4_backend):
    backend = v4_backend
    result = read_article(backend._sa_db, "a")
    assert result["status"] == "ok"
    coverage = result["coverage"]["comments"]
    assert coverage["scan_attempted_at"] is None
    assert coverage["scan_stop_reason"] is None
    assert coverage["complete"] is None
    with sqlite3.connect(backend._sa_db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4


def test_article_list_keeps_v4_rows_visible_without_migration(v4_backend):
    articles = v4_backend.query_sa_articles()
    assert [article["article_id"] for article in articles] == ["a"]
    assert articles[0]["comment_backfill_pending"] is None
    assert articles[0]["comment_scan_attempted_at"] is None
    assert articles[0]["comment_scan_stop_reason"] is None
    with sqlite3.connect(v4_backend._sa_db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sa_articles)")}
        assert "comment_backfill_pending" not in columns


def test_quick_submission_does_not_treat_v4_articles_as_empty(v4_backend, tmp_path):
    dal = DataAccessLayer(base_path=tmp_path, backend=v4_backend)
    result = dal.save_sa_articles_meta([meta("a", 6)], mode="quick")
    assert result.get("auto_upgrade") is not True
    assert result["saved"] == 1
    with sqlite3.connect(v4_backend._sa_db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION
        assert conn.execute("SELECT comments_count FROM sa_articles WHERE article_id='a'").fetchone()[0] == 6
