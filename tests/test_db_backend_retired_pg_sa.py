from datetime import datetime, timezone

from src.tools.backends.db_backend import DatabaseBackend


class _NoPGSA(DatabaseBackend):
    def __init__(self):
        pass

    def _get_conn(self):  # pragma: no cover - assertion surface
        raise AssertionError("retired PG SA method attempted to open PG")


def test_retired_pg_sa_methods_do_not_connect():
    b = _NoPGSA()
    now = datetime(2026, 7, 6, tzinfo=timezone.utc)

    assert b.apply_sa_refresh("current", [], now, now) == 0
    assert b.record_sa_refresh_failure("current", now, "x") is None
    assert b.query_sa_picks() == []
    assert b.get_sa_pick_detail("NVDA") is None
    assert b.update_sa_pick_detail("NVDA", "2026-01-01", "body") is False
    assert b.get_sa_refresh_meta() == {}
    assert b.upsert_sa_market_news([]) == 0
    assert b.query_sa_market_news() == []
    assert b.query_sa_market_news_recent_ids() == []
    assert b.query_sa_market_news_need_detail() == []
    assert b.invalidate_dirty_sa_market_news_detail() == 0
    assert b.save_sa_market_news_detail("n1", "body") is False
    assert b.upsert_sa_articles_meta([]) == 0
    assert b.sanitize_corrupted_sa_comments_counts() == 0
    assert b.cleanup_mixed_null_date_comment_duplicates() == {
        "groups_processed": 0,
        "comments_deleted": 0,
        "parent_links_repointed": 0,
    }
    assert b.save_article_with_comments("a1", "body", []) == {
        "ok": False,
        "prepared_comments": 0,
        "stored_comments_total": 0,
        "net_new_comments": 0,
        "reason": "pg_sa_retired",
    }
    assert b.update_article_comments("a1", []) == {
        "prepared_comments": 0,
        "stored_comments_total": 0,
        "net_new_comments": 0,
    }
    assert b.audit_unresolved_symbols() == {"unresolved_symbols": [], "resolved_by_fulltext": 0}
    assert b.reconcile_sa_articles(article_ids=["a1"]) == {
        "status": "unavailable",
        "reason": "pg_sa_retired",
        "enrichment": [],
    }
    assert b.query_sa_article_review_queue() == {"events": [], "total": 0}
    assert b.resolve_sa_reconciliation_event(
        symbol="NVDA", role="entry", event_anchor_date="2026-01-01"
    ) == {"status": "unavailable", "reason": "pg_sa_retired"}
    assert b.accept_sa_article_link() == {
        "status": "unavailable", "reason": "pg_sa_retired"
    }
    assert b.reject_sa_article_candidate() == {
        "status": "unavailable", "reason": "pg_sa_retired"
    }
    assert b.query_sa_articles() == []
    assert b.get_sa_article_with_comments("a1") is None
