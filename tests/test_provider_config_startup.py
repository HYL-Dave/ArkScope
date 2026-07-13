from __future__ import annotations

import sqlite3
import asyncio

import pytest


def test_lifespan_reconciles_interrupted_scheduler_state(monkeypatch):
    from src.api.app import create_app, lifespan

    called = {"reconcile": False}

    def _reconcile():
        called["reconcile"] = True
        return {"scheduler_sources": ["ibkr_news"], "provider_run_ids": [106]}

    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "1")
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: None)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        _reconcile,
    )

    async def _run_lifespan():
        async with lifespan(create_app()):
            assert called["reconcile"] is True

    asyncio.run(_run_lifespan())


def test_profile_db_failure_boots_setup_only(monkeypatch):
    from src.api.app import create_app, lifespan
    from src.api.routes.health import healthz
    from src.api.routes import providers_config
    import src.api.routes.portfolio_capture  # noqa: F401
    import src.provider_config_runtime as runtime

    runtime.clear_provider_config_setup_required()
    started = {"scheduler": False}

    async def _scheduler_loop():
        started["scheduler"] = True

    def _fail_apply_env(store):
        raise sqlite3.OperationalError("profile_state.db readonly")

    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.data_provider_config.apply_env", _fail_apply_env)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.api.dependencies.get_portfolio_capture_service",
        lambda: (_ for _ in ()).throw(
            AssertionError("capture service constructed during setup-only boot")
        ),
        raising=False,
    )
    monkeypatch.setattr("src.service.data_scheduler.scheduler_loop", _scheduler_loop)

    async def _run_lifespan():
        async with lifespan(create_app()):
            assert healthz() == {"status": "ok"}
            cfg = providers_config.providers_config(store=None)
            assert cfg["setup"]["required"] is True
            assert cfg["setup"]["code"] == "provider_config_setup_required"
            assert "profile_state.db readonly" in cfg["setup"]["reason"]
            assert started["scheduler"] is False

    asyncio.run(_run_lifespan())

    cfg = providers_config.providers_config(store=None)
    assert cfg["setup"]["required"] is True
    assert cfg["setup"]["code"] == "provider_config_setup_required"
    assert "profile_state.db readonly" in cfg["setup"]["reason"]
    assert started["scheduler"] is False


def test_lifespan_starts_data_and_portfolio_scheduler_tasks(monkeypatch, tmp_path):
    from src.api.app import create_app, lifespan
    import src.api.routes.portfolio_capture  # noqa: F401

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: None)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        lambda: None,
    )
    started = []
    cancelled = []

    class CaptureService:
        def __init__(self):
            self.reconcile_calls = 0

        def reconcile_startup(self):
            self.reconcile_calls += 1
            return []

    capture_service = CaptureService()
    monkeypatch.setattr(
        "src.api.dependencies.get_portfolio_capture_service",
        lambda: capture_service,
        raising=False,
    )

    async def data_loop():
        started.append("data")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append("data")
            raise

    async def portfolio_loop(service):
        assert service is capture_service
        started.append("portfolio")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append("portfolio")
            raise

    monkeypatch.setattr("src.service.data_scheduler.scheduler_loop", data_loop)
    monkeypatch.setattr(
        "src.portfolio_capture_scheduler.portfolio_capture_scheduler_loop",
        portfolio_loop,
    )

    async def _run_lifespan():
        async with lifespan(create_app()):
            await asyncio.sleep(0)
            assert set(started) == {"data", "portfolio"}
            assert capture_service.reconcile_calls == 1
        assert set(cancelled) == {"data", "portfolio"}

    asyncio.run(_run_lifespan())


def test_disable_scheduler_env_prevents_both_scheduler_tasks(monkeypatch, tmp_path):
    from src.api.app import create_app, lifespan
    import src.api.routes.portfolio_capture  # noqa: F401

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "yes")
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: None)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        lambda: None,
    )

    class CaptureService:
        def __init__(self):
            self.reconcile_calls = 0

        def reconcile_startup(self):
            self.reconcile_calls += 1
            return []

    capture_service = CaptureService()
    monkeypatch.setattr(
        "src.api.dependencies.get_portfolio_capture_service",
        lambda: capture_service,
        raising=False,
    )

    async def forbidden_data_loop():
        raise AssertionError("data scheduler started while disabled")

    async def forbidden_portfolio_loop(service):
        raise AssertionError("portfolio scheduler started while disabled")

    monkeypatch.setattr(
        "src.service.data_scheduler.scheduler_loop", forbidden_data_loop
    )
    monkeypatch.setattr(
        "src.portfolio_capture_scheduler.portfolio_capture_scheduler_loop",
        forbidden_portfolio_loop,
    )

    async def _run_lifespan():
        async with lifespan(create_app()):
            await asyncio.sleep(0)
            assert capture_service.reconcile_calls == 1

    asyncio.run(_run_lifespan())


def test_provider_work_routes_refuse_in_setup_only(monkeypatch):
    from fastapi import HTTPException
    from src.api.routes import providers_config, schedule
    import src.provider_config_runtime as runtime

    runtime.mark_provider_config_setup_required("profile DB unavailable")
    try:
        with pytest.raises(HTTPException) as e1:
            providers_config.test_provider("polygon")
        assert e1.value.status_code == 503
        assert e1.value.detail["code"] == "provider_config_setup_required"

        with pytest.raises(HTTPException) as e2:
            schedule.run_now("polygon_news")
        assert e2.value.status_code == 503
        assert e2.value.detail["code"] == "provider_config_setup_required"
    finally:
        runtime.clear_provider_config_setup_required()
