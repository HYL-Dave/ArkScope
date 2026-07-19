from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock

import src.sa_native_host as host
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.sa_capture_backend import SACaptureDatabaseBackend
from src.tools.data_access import DataAccessLayer


_V1_MINIMAL_SCHEMA = """
CREATE TABLE sa_alpha_picks (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    company TEXT NOT NULL,
    picked_date TEXT NOT NULL,
    closed_date TEXT,
    portfolio_status TEXT NOT NULL DEFAULT 'current',
    is_stale INTEGER NOT NULL DEFAULT 0,
    return_pct REAL,
    sector TEXT,
    sa_rating TEXT,
    holding_pct REAL,
    detail_report TEXT,
    detail_fetched_at TEXT,
    raw_data TEXT,
    last_seen_snapshot TEXT,
    canonical_article_id TEXT,
    fetched_at TEXT,
    updated_at TEXT
);
CREATE TABLE sa_articles (
    id INTEGER PRIMARY KEY,
    article_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    ticker TEXT,
    author TEXT,
    published_date TEXT,
    article_type TEXT,
    body_markdown TEXT,
    comments_count INTEGER DEFAULT 0,
    detail_fetched_at TEXT,
    comments_fetched_at TEXT,
    raw_data TEXT,
    fetched_at TEXT,
    updated_at TEXT
);
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
INSERT INTO schema_migrations(version, applied_at)
VALUES (1, '2026-06-13T00:00:00+00:00');
INSERT INTO sa_alpha_picks(
    symbol, company, picked_date, portfolio_status, is_stale
) VALUES ('BTSG', 'BrightSpring', '2026-07-15', 'current', 0);
PRAGMA user_version = 1;
"""


def _dal_with_backend(backend) -> DataAccessLayer:
    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._backend = backend
    return dal


def test_pick_refresh_and_article_meta_capture_commit_before_separate_reconciliation():
    pick_calls = []

    class PickDal:
        def apply_sa_refresh(self, **kwargs):
            pick_calls.append(("capture_picks", kwargs["scope"]))
            return 1

        def reconcile_sa_articles(self, **kwargs):
            pick_calls.append(("reconcile", kwargs))
            raise RuntimeError("private sqlite path")

        def record_sa_refresh_failure(self, *args, **kwargs):
            raise AssertionError("reconciliation must not poison capture metadata")

    pick_result = host._handle_refresh(
        PickDal(),
        "current",
        [{"symbol": "BTSG", "picked_date": "2026-07-15"}],
        datetime(2026, 7, 18, tzinfo=timezone.utc),
    )
    assert pick_calls[0] == ("capture_picks", "current")
    assert pick_calls[1][0] == "reconcile"
    assert pick_calls[1][1]["pick_keys"] == [("BTSG", "2026-07-15")]
    assert pick_result["status"] == "ok"
    assert pick_result["count"] == 1
    assert pick_result["reconciliation"] == {
        "status": "failed",
        "error_code": "reconciliation_failed",
        "enrichment": [],
    }
    assert "private sqlite path" not in json.dumps(pick_result)

    meta_calls = []

    class MetaBackend(DatabaseBackend):
        def __init__(self):
            self.query_count = 0

        def query_sa_articles(self, **kwargs):
            self.query_count += 1
            old = {
                "article_id": "old-bodyless",
                "url": "https://sa/old-bodyless",
                "has_content": False,
            }
            current = {
                "article_id": "6316639",
                "url": "https://sa/6316639",
                "has_content": False,
            }
            return [old] if self.query_count == 1 else [old, current]

        def upsert_sa_articles_meta(self, articles):
            meta_calls.append(("capture_meta", tuple(a["article_id"] for a in articles)))
            return len(articles)

        def sanitize_corrupted_sa_comments_counts(self):
            return 0

        def reconcile_sa_articles(self, **kwargs):
            meta_calls.append(("reconcile", kwargs))
            raise RuntimeError("secret database detail")

    meta_dal = _dal_with_backend(MetaBackend())
    meta_dal._compute_unresolved_symbols = lambda: []
    meta_result = meta_dal.save_sa_articles_meta(
        [{"article_id": "6316639", "url": "https://sa/6316639"}],
        mode="quick",
    )
    assert meta_calls[0] == ("capture_meta", ("6316639",))
    assert meta_calls[1][0] == "reconcile"
    assert meta_calls[1][1]["article_ids"] == ["6316639"]
    assert meta_result["need_content"] == [
        {"article_id": "6316639", "url": "https://sa/6316639"}
    ]
    assert meta_result["reconciliation"]["status"] == "failed"
    assert "secret database detail" not in json.dumps(meta_result)


def test_save_article_content_commits_before_reconciliation_failure_and_stays_ok():
    calls = []

    class Backend(DatabaseBackend):
        def __init__(self):
            pass

        def save_article_with_comments(
            self, article_id, body_markdown, comments, *,
            detail_ticker=None, detail_ticker_observed_at=None,
            provider_comments_count=None, comment_scan_mode="quick",
            comment_scan_stop_reason=None, comment_scan_stable_bottom_rounds=0,
        ):
            calls.append((
                "capture_body", article_id, body_markdown, detail_ticker,
                provider_comments_count, comment_scan_mode,
                comment_scan_stop_reason, comment_scan_stable_bottom_rounds,
            ))
            return {
                "ok": True,
                "prepared_comments": 0,
                "stored_comments_total": 0,
                "net_new_comments": 0,
            }

        def reconcile_sa_articles(self, **kwargs):
            calls.append((
                "reconcile",
                tuple(kwargs["article_ids"]),
                kwargs["max_events"],
                kwargs["enrichment_limit"],
            ))
            raise RuntimeError("synthetic sql failure")

    response = host._handle_save_article_content(_dal_with_backend(Backend()), {
        "article_id": "6316639",
        "body_markdown": "body",
        "detail_ticker": "BTSG",
        "detail_ticker_observed_at": "2026-07-18T12:00:00Z",
        "provider_comments_count": 265,
        "comment_scan_mode": "full",
        "comment_scan_stop_reason": "stable_bottom",
        "comment_scan_stable_bottom_rounds": 4,
        "comments": [],
    })
    assert calls == [
        (
            "capture_body", "6316639", "body", "BTSG", 265, "full",
            "stable_bottom", 4,
        ),
        ("reconcile", ("6316639",), 100, 4),
    ]
    assert response["status"] == "ok"
    assert response["article_id"] == "6316639"
    assert response["reconciliation"] == {
        "status": "failed",
        "error_code": "reconciliation_failed",
        "enrichment": [],
    }
    assert "synthetic sql failure" not in json.dumps(response)


def test_save_article_content_passes_detail_ticker_without_manual_symbol_injection():
    class Dal:
        def __init__(self):
            self.capture_kwargs = None

        def save_sa_article_with_comments(self, *args, **kwargs):
            self.capture_kwargs = kwargs
            return {
                "ok": True,
                "reconciliation": {"status": "ok", "enrichment": []},
            }

    dal = Dal()
    result = host._handle_save_article_content(dal, {
        "article_id": "6316639",
        "body_markdown": "body",
        "detail_ticker": "BTSG",
        "detail_ticker_observed_at": "2026-07-18T12:00:00Z",
        "provider_comments_count": 265,
        "comment_scan_mode": "backfill",
        "comment_scan_stop_reason": "stable_bottom",
        "comment_scan_stable_bottom_rounds": 5,
        "symbol": "WRONG-MANUAL-SYMBOL",
        "comments": [],
    })
    assert result["status"] == "ok"
    assert dal.capture_kwargs == {
        "detail_ticker": "BTSG",
        "detail_ticker_observed_at": "2026-07-18T12:00:00Z",
        "provider_comments_count": 265,
        "comment_scan_mode": "backfill",
        "comment_scan_stop_reason": "stable_bottom",
        "comment_scan_stable_bottom_rounds": 5,
    }


def test_save_comments_only_forwards_recovery_scan_evidence():
    dal = MagicMock()
    dal.save_sa_comments_only.return_value = {
        "prepared_comments": 0,
        "stored_comments_total": 592,
        "net_new_comments": 0,
        "comment_scan_usable": False,
        "comment_recovery_state": "pending",
    }
    result = host._handle_save_comments_only(dal, {
        "article_id": "a1",
        "comments": [],
        "provider_comments_count": 12,
        "comment_scan_mode": "backfill",
        "comment_scan_stop_reason": "stable_bottom",
        "comment_scan_stable_bottom_rounds": 5,
    })
    dal.save_sa_comments_only.assert_called_once_with(
        "a1",
        [],
        provider_comments_count=12,
        comment_scan_mode="backfill",
        comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5,
    )
    assert result["status"] == "ok"
    assert result["comment_scan_usable"] is False
    assert result["comment_recovery_state"] == "pending"


def test_get_reconciliation_queue_action_is_read_only_and_sanitized(
    tmp_path, monkeypatch
):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    conn.executescript(_V1_MINIMAL_SCHEMA)
    conn.close()
    backend = SACaptureDatabaseBackend(
        "postgresql://poison.invalid/arkscope", sa_db=str(path)
    )
    dal = _dal_with_backend(backend)
    monkeypatch.setattr(
        "src.tools.data_access.DataAccessLayer", lambda *args, **kwargs: dal
    )

    first = host.handle_message({"action": "get_reconciliation_queue", "limit": 50})
    assert first["status"] == "ok"
    assert first["total"] == 1
    assert "poison.invalid" not in json.dumps(first)

    check = sqlite3.connect(path)
    try:
        assert check.execute("PRAGMA user_version").fetchone()[0] == 2
        before = (
            check.execute("SELECT COUNT(*) FROM sa_pick_article_links").fetchone()[0],
            check.execute("SELECT COUNT(*) FROM sa_pick_article_decisions").fetchone()[0],
        )
    finally:
        check.close()
    second = host.handle_message({"action": "get_reconciliation_queue", "limit": 50})
    check = sqlite3.connect(path)
    try:
        after = (
            check.execute("SELECT COUNT(*) FROM sa_pick_article_links").fetchone()[0],
            check.execute("SELECT COUNT(*) FROM sa_pick_article_decisions").fetchone()[0],
        )
    finally:
        check.close()
    assert second == first
    assert before == after == (0, 0)


def test_resolve_and_accept_reconciliation_link_validates_exact_event_and_canonical_url(
    monkeypatch,
):
    class Dal:
        def __init__(self):
            self.accepted = []

        def resolve_sa_reconciliation_event(self, **kwargs):
            assert kwargs == {
                "symbol": "BTSG",
                "role": "entry",
                "event_anchor_date": "2026-07-15",
            }
            return {
                "status": "ok",
                "lineage_id": 7,
                "symbol": "BTSG",
                "role": "entry",
                "event_anchor_date": "2026-07-15",
            }

        def get_sa_article_detail(self, article_id):
            return {"article_id": article_id, "published_date": "2026-07-15"}

        def accept_sa_article_link(self, **kwargs):
            self.accepted.append(kwargs)
            return {"status": "ok", "link_id": 9, "article_id": kwargs["article_id"]}

    dal = Dal()
    monkeypatch.setattr(
        "src.tools.data_access.DataAccessLayer", lambda *args, **kwargs: dal
    )
    resolved = host.handle_message({
        "action": "resolve_reconciliation_event",
        "symbol": "BTSG",
        "role": "entry",
        "event_anchor_date": "2026-07-15",
    })
    assert resolved["status"] == "ok"
    accepted = host.handle_message({
        "action": "accept_reconciliation_link",
        "lineage_id": resolved["lineage_id"],
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "article_url": (
            "https://seekingalpha.com/alpha-picks/articles/"
            "6316639-stock-buy-top-health-care-services-stock-delivers-double-digit-growth"
        ),
        "replace_link_id": None,
        "confirm_warnings": False,
    })
    assert accepted["status"] == "ok"
    assert dal.accepted[0]["lineage_id"] == 7

    invalid = host.handle_message({
        "action": "accept_reconciliation_link",
        "lineage_id": 7,
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "article_url": "https://seekingalpha.com/alpha-picks/articles/999999-wrong",
    })
    assert invalid == {"status": "error", "error_code": "invalid_article_url"}
    assert len(dal.accepted) == 1


def test_accept_reconciliation_link_requires_confirmation_for_mismatch_or_replacement():
    class Dal:
        def __init__(self):
            self.accepted = []

        def get_sa_article_detail(self, article_id):
            return {"article_id": article_id, "published_date": "2026-07-12"}

        def accept_sa_article_link(self, **kwargs):
            self.accepted.append(kwargs)
            return {"status": "ok", "article_id": kwargs["article_id"]}

    dal = Dal()
    payload = {
        "lineage_id": 7,
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "article_url": "https://seekingalpha.com/alpha-picks/articles/6316639-btsg",
        "replace_link_id": 4,
        "confirm_warnings": False,
    }
    warning = host._handle_accept_reconciliation_link(dal, payload)
    assert warning == {
        "status": "confirmation_required",
        "warnings": ["date_mismatch", "replacement"],
        "candidate": {"article_id": "6316639", "published_date": "2026-07-12"},
    }
    assert dal.accepted == []

    confirmed = host._handle_accept_reconciliation_link(
        dal, {**payload, "confirm_warnings": True}
    )
    assert confirmed["status"] == "ok"
    assert dal.accepted[0]["replace_link_id"] == 4
    assert dal.accepted[0]["link_source"] == "user"


def test_reject_reconciliation_candidate_is_event_scoped_and_idempotent(monkeypatch):
    class Dal:
        def __init__(self):
            self.keys = []

        def reject_sa_article_candidate(self, **kwargs):
            self.keys.append(kwargs)
            return {"status": "ok", "decision_id": 12, "idempotent": True}

    dal = Dal()
    payload = {
        "lineage_id": 7,
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "reason_code": "user_rejected",
    }
    monkeypatch.setattr(
        "src.tools.data_access.DataAccessLayer", lambda *args, **kwargs: dal
    )
    first = host.handle_message({"action": "reject_reconciliation_candidate", **payload})
    second = host.handle_message({"action": "reject_reconciliation_candidate", **payload})
    assert first == second == {"status": "ok", "decision_id": 12, "idempotent": True}
    assert dal.keys == [payload, payload]


def test_compatibility_audit_returns_queue_without_mutation():
    class Dal:
        def query_sa_article_review_queue(self, limit=50):
            return {
                "events": [{
                    "lineage_id": 7,
                    "symbol": "BTSG",
                    "role": "entry",
                    "event_anchor_date": "2026-07-15",
                    "candidates": [],
                }],
                "total": 1,
            }

        def accept_sa_article_link(self, **kwargs):
            raise AssertionError("compatibility audit must be read-only")

        def reject_sa_article_candidate(self, **kwargs):
            raise AssertionError("compatibility audit must be read-only")

    result = host._handle_audit_unresolved(Dal())
    assert result["status"] == "ok"
    assert result["unresolved_symbols"] == ["BTSG"]
    assert result["resolved_by_fulltext"] == 0
    assert result["review_queue"]["total"] == 1


def test_retired_pg_reconciliation_methods_never_connect():
    class NoPG(DatabaseBackend):
        def __init__(self):
            pass

        def _get_conn(self):
            raise AssertionError("retired PG method attempted a connection")

    backend = NoPG()
    assert backend.reconcile_sa_articles(article_ids=["6316639"]) == {
        "status": "unavailable", "reason": "pg_sa_retired", "enrichment": [],
    }
    assert backend.query_sa_article_review_queue() == {"events": [], "total": 0}
    assert backend.resolve_sa_reconciliation_event(
        symbol="BTSG", role="entry", event_anchor_date="2026-07-15"
    ) == {"status": "unavailable", "reason": "pg_sa_retired"}
    assert backend.accept_sa_article_link(
        lineage_id=7, role="entry", event_anchor_date="2026-07-15",
        article_id="6316639",
    ) == {"status": "unavailable", "reason": "pg_sa_retired"}
    assert backend.reject_sa_article_candidate(
        lineage_id=7, role="entry", event_anchor_date="2026-07-15",
        article_id="6316639", reason_code="user_rejected",
    ) == {"status": "unavailable", "reason": "pg_sa_retired"}
