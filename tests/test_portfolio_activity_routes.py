from __future__ import annotations

from dataclasses import asdict
import importlib
import json
import sqlite3

import pytest
from fastapi import HTTPException

from src.portfolio_activity import ActivityAnnotation, ActivityFilters, PortfolioActivityStore
from src.portfolio_state import PortfolioStore


RAW_ACCOUNT_ID = "DU123-ROUTE-SECRET"


def _routes():
    return importlib.import_module("src.api.routes.portfolio_activity")


def _store(tmp_path) -> PortfolioActivityStore:
    return PortfolioActivityStore(tmp_path / "profile_state.db")


def _table_counts(store: PortfolioActivityStore) -> dict[str, int]:
    tables = (
        "portfolio_accounts",
        "portfolio_positions",
        "portfolio_manual_adjustments",
        "portfolio_activity_annotations",
        "portfolio_broker_executions",
        "portfolio_unmatched_position_changes",
    )
    with store._connect() as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }


def test_portfolio_activity_router_mounts_on_real_app():
    from src.api.app import create_app

    routes = {
        (getattr(route, "path", None), method)
        for route in create_app().routes
        for method in (getattr(route, "methods", None) or set())
    }

    assert ("/portfolio/activity", "GET") in routes
    assert ("/portfolio/activity/annotations/{activity_id}", "PUT") in routes
    assert ("/portfolio/activity/annotations/{activity_id}", "DELETE") in routes


def test_get_activity_fresh_profile_is_empty_zero_authority_write_and_never_calls_gateway(
    monkeypatch, tmp_path
):
    routes = _routes()
    store = _store(tmp_path)
    before = _table_counts(store)
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("activity GET used write authority")
        ),
    )
    monkeypatch.setattr(
        "src.portfolio_capture_ibkr.read_ibkr_capture",
        lambda: (_ for _ in ()).throw(AssertionError("activity GET read Gateway")),
    )

    out = routes.get_activity(store=store)

    assert out["items"] == []
    assert _table_counts(store) == before


def test_get_activity_serializes_exact_shape_without_raw_broker_account_id(tmp_path):
    routes = _routes()
    path = tmp_path / "profile_state.db"
    portfolio = PortfolioStore(path)
    portfolio.upsert_broker_account(
        "ibkr", RAW_ACCOUNT_ID, f"Legacy IBKR {RAW_ACCOUNT_ID}"
    )

    out = routes.get_activity(store=PortfolioActivityStore(path))
    encoded = json.dumps(out, sort_keys=True)

    assert set(out) == {
        "accounts",
        "history_started_at_utc",
        "items",
        "summary",
        "next_cursor",
    }
    assert RAW_ACCOUNT_ID not in encoded
    assert '"broker_account_id"' not in encoded
    assert "broker_account_id_hash" in encoded
    assert out["accounts"][0]["label"].startswith("IBKR · ")


def test_get_activity_threads_all_filters_recent_limit_and_cursor_to_store(tmp_path):
    routes = _routes()
    real_store = _store(tmp_path)

    class SpyStore:
        filters = None

        def list_activity(self, filters):
            self.filters = filters
            return real_store.list_activity(ActivityFilters())

    store = SpyStore()
    out = routes.get_activity(
        date_from_et="2026-07-10",
        date_to_et="2026-07-15",
        account_id=7,
        symbol=" aapl ",
        source="broker",
        state="realized_gain",
        recent=False,
        limit=25,
        cursor="eyJhY3Rpdml0eV9pZCI6IngiLCJvY2N1cnJlZF9hdF91dGMiOiIyMDI2LTA3LTE1VDAwOjAwOjAwKzAwOjAwIn0",
        store=store,
    )

    assert out["items"] == []
    assert store.filters == ActivityFilters(
        date_from_et="2026-07-10",
        date_to_et="2026-07-15",
        account_id=7,
        symbol=" aapl ",
        source="broker",
        state="realized_gain",
        recent=False,
        limit=25,
        cursor="eyJhY3Rpdml0eV9pZCI6IngiLCJvY2N1cnJlZF9hdF91dGMiOiIyMDI2LTA3LTE1VDAwOjAwOjAwKzAwOjAwIn0",
    )


def test_get_activity_maps_invalid_date_cursor_and_limit_to_typed_400(tmp_path):
    routes = _routes()
    invalid_filters = (
        {"date_from_et": "2026-07-16", "date_to_et": "2026-07-15"},
        {"cursor": "invalid"},
        {"limit": 0},
    )

    for kwargs in invalid_filters:
        with pytest.raises(HTTPException) as exc:
            routes.get_activity(store=_store(tmp_path), **kwargs)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "invalid_portfolio_activity"


def test_put_annotation_requires_write_gate_and_uses_full_replacement(monkeypatch, tmp_path):
    routes = _routes()
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )

    class SpyStore:
        received = None

        def put_annotation(self, activity_id, *, intent_label, note):
            self.received = (activity_id, intent_label, note)
            return ActivityAnnotation(intent_label=intent_label, note=note, updated_at_utc="now")

    store = SpyStore()
    activity_id = "order:7:70001"
    out = routes.put_annotation(
        activity_id,
        routes.PortfolioActivityAnnotationBody(
            intent_label="profit_take", note="trimmed exposure"
        ),
        store=store,
    )

    assert calls == [
        (
            "portfolio_activity_annotation_write",
            {"activity_id": activity_id, "action": "replace"},
        )
    ]
    assert store.received == (activity_id, "profit_take", "trimmed exposure")
    assert out == asdict(ActivityAnnotation("profit_take", "trimmed exposure", "now"))


def test_put_annotation_maps_missing_target_to_404_and_invalid_input_to_400(
    monkeypatch, tmp_path
):
    routes = _routes()
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *_args, **_kwargs: None)
    store = _store(tmp_path)
    body = routes.PortfolioActivityAnnotationBody(intent_label="other", note="note")

    with pytest.raises(HTTPException) as missing:
        routes.put_annotation("order:1:999999", body, store=store)
    with pytest.raises(HTTPException) as invalid:
        routes.put_annotation("order:1:0", body, store=store)

    assert missing.value.status_code == 404
    assert missing.value.detail["code"] == "portfolio_activity_not_found"
    assert invalid.value.status_code == 400
    assert invalid.value.detail["code"] == "invalid_portfolio_activity"


def test_delete_annotation_requires_gate_and_returns_idempotent_deleted_flag(
    monkeypatch, tmp_path
):
    routes = _routes()
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )

    class SpyStore:
        responses = iter((True, False))

        def delete_annotation(self, activity_id):
            assert activity_id == "manual:4"
            return next(self.responses)

    store = SpyStore()

    assert routes.delete_annotation("manual:4", store=store) == {
        "activity_id": "manual:4", "deleted": True
    }
    assert routes.delete_annotation("manual:4", store=store) == {
        "activity_id": "manual:4", "deleted": False
    }
    assert calls == [
        (
            "portfolio_activity_annotation_write",
            {"activity_id": "manual:4", "action": "delete"},
        ),
        (
            "portfolio_activity_annotation_write",
            {"activity_id": "manual:4", "action": "delete"},
        ),
    ]


def test_activity_storage_failure_is_typed_without_raw_exception_or_account_id(
    monkeypatch, tmp_path
):
    routes = _routes()
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *_args, **_kwargs: None)

    class BrokenStore:
        def list_activity(self, filters):
            raise sqlite3.OperationalError(f"database error for {RAW_ACCOUNT_ID}")

        def put_annotation(self, activity_id, *, intent_label, note):
            raise sqlite3.OperationalError(f"database error for {RAW_ACCOUNT_ID}")

        def delete_annotation(self, activity_id):
            raise sqlite3.OperationalError(f"database error for {RAW_ACCOUNT_ID}")

    store = BrokenStore()
    body = routes.PortfolioActivityAnnotationBody(intent_label="other", note="note")
    failures = [
        lambda: routes.get_activity(store=store),
        lambda: routes.put_annotation("manual:4", body, store=store),
        lambda: routes.delete_annotation("manual:4", store=store),
    ]

    for call in failures:
        with pytest.raises(HTTPException) as exc:
            call()
        assert exc.value.status_code == 503
        assert exc.value.detail == {
            "code": "portfolio_activity_unavailable",
            "action": "retry",
        }
        assert RAW_ACCOUNT_ID not in json.dumps(exc.value.detail)
