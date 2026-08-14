"""Stable native-host persistence diagnostics for active SA saves."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import MagicMock

import src.sa_native_host as host


def _failure(code: str, *, retryable: bool, message: str) -> dict:
    return {
        "status": "error",
        "error_code": code,
        "retryable": retryable,
        "message": message,
    }


def _active_save_cases():
    return (
        (
            host._handle_save_market_news,
            "save_sa_market_news",
            {"items": []},
            {"status": "ok", "saved": 0, "need_detail": []},
        ),
        (
            host._handle_save_market_news_detail,
            "save_sa_market_news_detail",
            {"news_id": "news-1", "body_markdown": "body"},
            True,
        ),
        (
            host._handle_save_articles_meta,
            "save_sa_articles_meta",
            {"articles": [], "mode": "quick"},
            {
                "status": "ok",
                "saved": 0,
                "need_content": [],
                "need_comments": [],
                "unresolved_symbols": [],
                "auto_upgrade": False,
            },
        ),
        (
            host._handle_save_article_content,
            "save_sa_article_with_comments",
            {"article_id": "article-1", "body_markdown": "body", "comments": []},
            {"ok": True, "reconciliation": {"status": "ok", "enrichment": []}},
        ),
        (
            host._handle_save_comments_only,
            "save_sa_comments_only",
            {"article_id": "article-1", "comments": []},
            {
                "prepared_comments": 0,
                "net_new_comments": 0,
                "stored_comments_total": 0,
                "comment_scan_usable": True,
            },
        ),
    )


def _invoke(case, *, result=None, error: Exception | None = None):
    handler, method_name, message, default_result = case
    dal = MagicMock()
    method = getattr(dal, method_name)
    if error is not None:
        method.side_effect = error
    else:
        method.return_value = default_result if result is None else result
    return handler(dal, json.loads(json.dumps(message)))


def _diagnostics() -> dict:
    return {
        "schema_version": 1,
        "entries": [
            {
                "occurred_at": "2026-08-14T01:00:10Z",
                "stage": "local_persistence",
                "reason_code": "database_busy",
                "target_kind": "article_detail",
                "target_ref": "article-1",
                "retryable": True,
                "attempt_count": 1,
                "message": "Local database is busy.",
            }
        ],
        "omitted_count": 0,
    }


def test_sqlite_busy_maps_to_database_busy_without_raw_exception():
    result = _invoke(
        _active_save_cases()[0],
        error=sqlite3.OperationalError("database is locked at /home/private.db"),
    )

    assert result == _failure(
        "database_busy",
        retryable=True,
        message="Local database is busy; retry later.",
    )
    assert "private.db" not in json.dumps(result)


def test_sqlite_integrity_maps_to_database_integrity_failed_without_raw_exception():
    result = _invoke(
        _active_save_cases()[2],
        error=sqlite3.IntegrityError("UNIQUE constraint failed: users.email"),
    )

    assert result == _failure(
        "database_integrity_failed",
        retryable=False,
        message="Local database integrity validation failed.",
    )
    assert "users.email" not in json.dumps(result)


def test_unknown_save_exception_maps_to_database_write_failed_without_raw_exception():
    result = _invoke(
        _active_save_cases()[3],
        error=RuntimeError("unexpected /private/path SELECT secret FROM credentials"),
    )

    assert result == _failure(
        "database_write_failed",
        retryable=True,
        message="Local database write failed; retry later.",
    )
    assert "private" not in json.dumps(result)
    assert "SELECT" not in json.dumps(result)


def test_false_save_result_maps_to_database_write_failed():
    result = _invoke(_active_save_cases()[1], result=False)

    assert result == _failure(
        "database_write_failed",
        retryable=True,
        message="Local database write failed; retry later.",
    )


def test_active_save_handlers_share_the_closed_failure_envelope():
    expected = _failure(
        "database_write_failed",
        retryable=True,
        message="Local database write failed; retry later.",
    )

    results = [
        _invoke(case, error=RuntimeError("handler-specific raw detail"))
        for case in _active_save_cases()
    ]

    assert results == [expected] * 5
    assert all(set(result) == set(expected) for result in results)

    returned_failures = []
    for index, case in enumerate(_active_save_cases()):
        result = False if index == 1 else {
            "status": "error",
            "error": "handler-specific raw detail",
        }
        returned_failures.append(_invoke(case, result=result))
    assert returned_failures == [expected] * 5


def test_successful_save_response_has_no_failure_diagnostic():
    results = [_invoke(case) for case in _active_save_cases()]

    assert all(result.get("status") == "ok" for result in results)
    for result in results:
        assert "error_code" not in result
        assert "retryable" not in result
        assert "message" not in result


def test_extension_record_native_bridge_forwards_closed_diagnostics_without_extra_fields(
    monkeypatch,
):
    calls = []

    def fake_post(payload):
        calls.append(payload)
        return {"status": "ok", "persisted": True, "run_id": 73}

    monkeypatch.setattr(host, "_post_extension_job_to_sidecar", fake_post)
    event = {
        "action": "record_extension_job",
        "client_event_id": "evt-native-diagnostics",
        "started_at": "2026-08-14T01:00:00Z",
        "finished_at": "2026-08-14T01:00:30Z",
        "result": {
            "schema_version": 1,
            "operation": "market_news_sync",
            "mode": "quick",
            "phases": {
                "list_navigation": {"state": "complete", "reason_code": None},
                "list_scrape": {"state": "complete", "reason_code": None},
                "metadata_save": {"state": "complete", "reason_code": None},
                "detail_fetch": {"state": "complete", "reason_code": None},
                "capture_readback": {"state": "complete", "reason_code": None},
            },
            "item_outcomes": [],
        },
        "extension_diagnostics": _diagnostics(),
    }

    response = host._handle_record_extension_job(None, event)

    assert response == {
        "status": "ok",
        "persisted": True,
        "run_id": 73,
        "error_code": None,
    }
    assert calls == [
        {
            "client_event_id": event["client_event_id"],
            "started_at": event["started_at"],
            "finished_at": event["finished_at"],
            "result": event["result"],
            "extension_diagnostics": event["extension_diagnostics"],
        }
    ]
    assert "action" not in calls[0]


def test_native_response_projection_never_contains_path_sql_stack_or_secret_sentinels():
    raw = (
        "/home/user/private.db SELECT token FROM secrets "
        "Traceback Bearer SECRET user@example.test"
    )

    results = [
        _invoke(case, error=RuntimeError(raw)) for case in _active_save_cases()
    ]
    serialized = json.dumps(results, sort_keys=True)

    for sentinel in (
        "/home/user/private.db",
        "SELECT",
        "Traceback",
        "Bearer",
        "SECRET",
        "user@example.test",
    ):
        assert sentinel not in serialized
    assert all(result["error_code"] == "database_write_failed" for result in results)
