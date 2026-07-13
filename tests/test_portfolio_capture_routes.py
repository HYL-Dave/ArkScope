from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import importlib
import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.portfolio_capture import (
    CaptureReviewChange,
    CaptureReviewPreview,
    CaptureStart,
    PortfolioCaptureService,
)
from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
    CaptureRun,
    CaptureRunNotReviewable,
    CaptureRunSuperseded,
    PortfolioCaptureBusy,
    PositionObservation,
    ProviderReadiness,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore


NOW = datetime(2026, 7, 14, 5, 0, tzinfo=timezone.utc)
RAW_ACCOUNT_ID = "DU-ROUTE-SECRET-123"


def _routes():
    return importlib.import_module("src.api.routes.portfolio_capture")


def _service(
    tmp_path,
    *,
    readiness: ProviderReadiness,
) -> tuple[PortfolioCaptureService, PortfolioStore, PortfolioObservationStore]:
    db = tmp_path / "profile_state.db"
    portfolio = PortfolioStore(db)
    observations = PortfolioObservationStore(db)
    service = PortfolioCaptureService(
        observations=observations,
        portfolio=portfolio,
        reader=lambda: (_ for _ in ()).throw(AssertionError("Gateway reader called")),
        provider_readiness=lambda: readiness,
        write_allowed=lambda action, detail: True,
        clock=lambda: NOW,
    )
    return service, portfolio, observations


def _capture_result(account_id: str = RAW_ACCOUNT_ID) -> BrokerCaptureResult:
    finished = "2026-07-14T05:00:00+00:00"
    return BrokerCaptureResult(
        finished_at_utc=finished,
        discovered_accounts=(BrokerAccountRef(account_id, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult("complete"),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(
            AccountSnapshotObservation(
                broker_account_id=account_id,
                as_of_utc=finished,
                base_currency="USD",
                net_liquidation=100_000,
            ),
        ),
        positions=(
            PositionObservation(
                broker_account_id=account_id,
                broker_con_id="265598",
                symbol="AAPL",
                asset_class="stock",
                quantity=2,
                avg_cost=150,
                currency="USD",
            ),
        ),
        executions=(),
        commissions=(),
    )


def _run(run_id: int = 1, *, state: str = "running") -> CaptureRun:
    return CaptureRun(
        id=run_id,
        trigger="manual",
        state=state,
        started_at="2026-07-14T05:00:00+00:00",
        finished_at=None if state == "running" else "2026-07-14T05:00:01+00:00",
        account_leg_state="not_attempted" if state == "running" else "complete",
        execution_leg_state="not_attempted" if state == "running" else "complete",
        position_leg_state="not_attempted" if state == "running" else "complete",
        discovered_account_count=0,
        new_account_count=0,
        archived_activity_count=0,
        inserted_execution_count=0,
        inserted_commission_count=0,
        unmatched_count=0,
        data_conflict_count=0,
        error_code=None,
        error_detail=None,
        effective_client_id=71,
        coverage_notes=(),
    )


def test_portfolio_capture_router_mounts_on_real_app(monkeypatch, tmp_path):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    from fastapi.testclient import TestClient

    from src.api.app import create_app
    from src.api.dependencies import get_portfolio_capture_service

    service, _, _ = _service(
        tmp_path / "route-service", readiness=ProviderReadiness(configured=True)
    )
    app = create_app()
    app.dependency_overrides[get_portfolio_capture_service] = lambda: service

    routes = {
        (getattr(route, "path", None), method)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }

    assert ("/portfolio/capture", "GET") in routes
    assert ("/portfolio/capture/settings", "PUT") in routes
    assert ("/portfolio/capture/runs", "POST") in routes
    assert ("/portfolio/capture/runs/{run_id}/apply", "POST") in routes

    with TestClient(app) as client:
        response = client.get("/portfolio/capture")
    assert response.status_code == 200
    assert response.json()["settings"]["provider_configured"] is True


def test_capture_status_defaults_enabled_only_when_ibkr_is_configured(
    monkeypatch, tmp_path
):
    routes = _routes()
    from src.api import dependencies
    from src.data_provider_config import DataProviderConfigStore

    provider_store = DataProviderConfigStore(tmp_path / "provider_state.db")
    monkeypatch.setattr(
        dependencies, "get_data_provider_store", lambda: provider_store
    )
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4002")
    assert dependencies._ibkr_capture_readiness().configured is True

    monkeypatch.delenv("IBKR_HOST")
    monkeypatch.delenv("IBKR_PORT")
    dependency_missing = dependencies._ibkr_capture_readiness()
    assert dependency_missing == ProviderReadiness(
        configured=False,
        code="provider_config_missing",
        status="not_configured",
        provider="ibkr",
        field="host",
    )

    singleton_db = tmp_path / "singleton" / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(singleton_db))
    dependencies.get_portfolio_capture_service.cache_clear()
    dependencies.get_portfolio_observation_store.cache_clear()
    dependencies.get_portfolio_store.cache_clear()
    try:
        singleton = dependencies.get_portfolio_capture_service()
        assert dependencies.get_portfolio_capture_service() is singleton
        assert singleton.observations.path == singleton_db
        assert singleton.portfolio.path == singleton_db
    finally:
        dependencies.get_portfolio_capture_service.cache_clear()
        dependencies.get_portfolio_observation_store.cache_clear()
        dependencies.get_portfolio_store.cache_clear()

    configured, _, configured_store = _service(
        tmp_path / "configured", readiness=ProviderReadiness(configured=True)
    )
    missing, _, missing_store = _service(
        tmp_path / "missing",
        readiness=ProviderReadiness(
            configured=False,
            code="provider_config_missing",
            status="not_configured",
            provider="ibkr",
            field="host",
        ),
    )

    configured_out = routes.get_capture_status(service=configured)
    missing_out = routes.get_capture_status(service=missing)

    assert configured_out["settings"] == {
        "enabled": True,
        "interval_minutes": 15,
        "source": "default",
        "provider_configured": True,
    }
    assert missing_out["settings"]["enabled"] is False
    assert missing_out["settings"]["provider_configured"] is False
    assert configured_store.get_stored_settings() is None
    assert missing_store.get_stored_settings() is None


def test_capture_status_reports_provider_missing_without_calling_gateway(tmp_path):
    routes = _routes()
    service, _, _ = _service(
        tmp_path,
        readiness=ProviderReadiness(
            configured=False,
            code="provider_config_missing",
            status="not_configured",
            provider="ibkr",
            field="port",
        ),
    )

    out = routes.get_capture_status(service=service)

    assert out["provider_issue"] == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "ibkr",
        "field": "port",
    }
    assert out["running"] is False


def test_capture_settings_put_requires_gate_and_persists_atomically(
    monkeypatch, tmp_path
):
    routes = _routes()
    from src.api import dependencies

    service, _, observations = _service(
        tmp_path, readiness=ProviderReadiness(configured=True)
    )
    body = routes.CaptureSettingsBody(enabled=False, interval_minutes=45)

    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )
    with pytest.raises(PermissionError, match="denied"):
        routes.put_capture_settings(body, service=service)
    assert observations.get_stored_settings() is None

    gate_calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: gate_calls.append((action, detail)),
    )
    out = routes.put_capture_settings(body, service=service)

    assert gate_calls == [
        (
            "portfolio_capture_settings_write",
            {"enabled": False, "interval_minutes": 45},
        )
    ]
    stored = observations.get_stored_settings()
    assert (stored.enabled, stored.interval_minutes) == (False, 45)
    assert out["settings"]["source"] == "database"

    dependency_gate_calls = []
    monkeypatch.setattr(
        "src.api.permissions.require_profile_state_write",
        lambda action, detail=None: dependency_gate_calls.append((action, detail)),
    )
    assert dependencies._portfolio_capture_write_allowed(
        "portfolio_capture", {"trigger": "manual"}
    ) is True
    assert dependency_gate_calls == [
        ("portfolio_capture", {"trigger": "manual"})
    ]


def test_capture_settings_model_rejects_invalid_interval_without_store_call():
    routes = _routes()

    class SpyService:
        called = False

        def update_settings(self, **kwargs):
            self.called = True

    service = SpyService()

    with pytest.raises(ValidationError):
        routes.CaptureSettingsBody(enabled=True, interval_minutes=4)
    with pytest.raises(ValidationError):
        routes.CaptureSettingsBody(enabled=True, interval_minutes=1441)
    assert service.called is False


def test_manual_capture_returns_running_or_terminal_blocked_shape():
    routes = _routes()
    starts = [
        CaptureStart(accepted=True, run=_run(), state="running"),
        CaptureStart(
            accepted=True,
            run=replace(
                _run(2, state="blocked"),
                account_leg_state="not_attempted",
                execution_leg_state="not_attempted",
                position_leg_state="not_attempted",
                error_code="provider_config_missing",
                error_detail="not_configured: ibkr: host",
            ),
            state="blocked",
            error_code="provider_config_missing",
            error_detail="not_configured: ibkr: host",
        ),
    ]

    class StubService:
        def __init__(self):
            self.calls = []

        def trigger(self, trigger, *, background):
            self.calls.append((trigger, background))
            return starts.pop(0)

    service = StubService()
    body = routes.CaptureRunBody()

    running = routes.start_capture_run(body, service=service)
    blocked = routes.start_capture_run(body, service=service)

    assert running["accepted"] is True
    assert running["state"] == "running"
    assert running["run"]["id"] == 1
    assert blocked["accepted"] is True
    assert blocked["state"] == "blocked"
    assert blocked["error_code"] == "provider_config_missing"
    assert blocked["run"]["state"] == "blocked"
    assert service.calls == [("manual", True), ("manual", True)]


def test_capture_status_recent_runs_contains_no_raw_broker_account_id(tmp_path):
    routes = _routes()
    service, portfolio, observations = _service(
        tmp_path, readiness=ProviderReadiness(configured=True)
    )
    account = portfolio.upsert_broker_account(
        "ibkr",
        RAW_ACCOUNT_ID,
        f"Legacy IBKR {RAW_ACCOUNT_ID}",
        sync_mode="ibkr_review",
    )
    run = observations.create_run(trigger="manual", effective_client_id=71)
    observations.commit_capture(run.id, _capture_result())
    observations.finish_run(run.id, state="succeeded")

    out = routes.get_capture_status(service=service)
    rendered = json.dumps(out, sort_keys=True)

    assert RAW_ACCOUNT_ID not in rendered
    assert out["review"]["changes"][0]["account_id"] == account.id
    assert out["review"]["changes"][0]["account_label"].startswith("IBKR · ")
    assert out["review"]["changes"][0]["broker_account_id_hash"]
    assert portfolio.get_account(account.id).label == f"Legacy IBKR {RAW_ACCOUNT_ID}"


def test_apply_review_requires_write_gate_and_uses_run_id(monkeypatch):
    routes = _routes()

    class StubService:
        def __init__(self):
            self.calls = []

        def apply_review_run(self, run_id):
            self.calls.append(run_id)
            if run_id == 404:
                raise KeyError(run_id)
            if run_id == 401:
                raise CaptureRunNotReviewable("incomplete")
            if run_id == 402:
                raise CaptureRunSuperseded("newer run")
            if run_id == 403:
                raise PortfolioCaptureBusy("capture active")
            assert run_id == 500
            return CaptureReviewPreview(
                run_id=run_id,
                changes=(
                    CaptureReviewChange(
                        kind="update",
                        account_id=7,
                        account_label="IBKR · abcdef12",
                        broker_account_id_hash="abcdef123456",
                        broker_con_id="265598",
                        symbol="AAPL",
                        quantity=2,
                        before={"quantity": 1},
                        after={"quantity": 2},
                    ),
                ),
                applies=True,
            )

    service = StubService()
    gates = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: gates.append((action, detail)),
    )

    expected = {
        404: (404, "capture_run_not_found"),
        401: (409, "capture_run_not_reviewable"),
        402: (409, "capture_run_superseded"),
        403: (409, "portfolio_capture_busy"),
    }
    for run_id, (status, code) in expected.items():
        with pytest.raises(HTTPException) as exc:
            routes.apply_capture_run(run_id, service=service)
        assert exc.value.status_code == status
        assert exc.value.detail["code"] == code

    out = routes.apply_capture_run(500, service=service)

    assert out["run_id"] == 500
    assert out["applies"] is True
    assert service.calls == [404, 401, 402, 403, 500]
    assert gates == [
        ("portfolio_capture_apply", {"run_id": run_id})
        for run_id in [404, 401, 402, 403, 500]
    ]
