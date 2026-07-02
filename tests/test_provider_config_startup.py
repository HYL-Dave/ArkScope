from __future__ import annotations

import sqlite3
import asyncio

import pytest


def test_profile_db_failure_boots_setup_only(monkeypatch):
    from src.api.app import create_app, lifespan
    from src.api.routes.health import healthz
    from src.api.routes import providers_config
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
