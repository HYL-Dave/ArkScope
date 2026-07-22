from __future__ import annotations

import asyncio
import sqlite3
from functools import lru_cache

import pytest


def _sqlite_operational_error(code: int) -> sqlite3.OperationalError:
    error = sqlite3.OperationalError("opaque sqlite failure")
    error.sqlite_errorcode = code
    return error


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


def test_lifespan_migrates_calibration_before_scheduler_start(
    monkeypatch, tmp_path
):
    from src.api.app import create_app, lifespan
    from src.investor_profile_calibration_schema import CalibrationSchemaMismatch
    import src.provider_config_runtime as runtime

    profile_db = tmp_path / "profile_state.db"
    calls: list[str] = []
    scenario = {"provider_fails": False, "migration_error": None}

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())

    def _apply_env(store):
        calls.append("apply_provider_env")
        if scenario["provider_fails"]:
            raise sqlite3.OperationalError("profile_state.db readonly")

    def _migrate(db_path):
        calls.append("migrate_calibration")
        assert db_path == str(profile_db)
        if scenario["migration_error"] is not None:
            raise scenario["migration_error"]

    class CalibrationStore:
        def reconcile_interrupted_turns(self):
            calls.append("reconcile_calibration")
            return 0

    @lru_cache(maxsize=1)
    def _calibration_store():
        calls.append("construct_calibration_store")
        return CalibrationStore()

    def _reconcile_runtime():
        calls.append("reconcile_scheduler_telemetry")
        return None

    class CaptureService:
        def reconcile_startup(self):
            calls.append("reconcile_portfolio_capture")
            return []

    capture_service = CaptureService()

    async def _data_loop():
        calls.append("start_data_scheduler")
        await asyncio.Event().wait()

    async def _portfolio_loop(service):
        assert service is capture_service
        calls.append("start_portfolio_scheduler")
        await asyncio.Event().wait()

    monkeypatch.setattr("src.data_provider_config.apply_env", _apply_env)
    monkeypatch.setattr(
        "src.investor_profile_calibration_schema.migrate_calibration_schema",
        _migrate,
    )
    monkeypatch.setattr(
        "src.api.dependencies.get_investor_calibration_store",
        _calibration_store,
    )
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        _reconcile_runtime,
    )
    monkeypatch.setattr(
        "src.api.dependencies.get_portfolio_capture_service",
        lambda: capture_service,
        raising=False,
    )
    monkeypatch.setattr("src.service.data_scheduler.scheduler_loop", _data_loop)
    monkeypatch.setattr(
        "src.portfolio_capture_scheduler.portfolio_capture_scheduler_loop",
        _portfolio_loop,
    )

    async def _run_lifespan():
        async with lifespan(create_app()):
            await asyncio.sleep(0)

    try:
        for provider_fails in (False, True):
            calls.clear()
            scenario.update(provider_fails=provider_fails, migration_error=None)
            asyncio.run(_run_lifespan())

            assert calls[:5] == [
                "apply_provider_env",
                "migrate_calibration",
                "construct_calibration_store",
                "reconcile_calibration",
                "reconcile_scheduler_telemetry",
            ]
            if provider_fails:
                assert "start_data_scheduler" not in calls
                assert "start_portfolio_scheduler" not in calls
            else:
                assert calls.index("reconcile_scheduler_telemetry") < calls.index(
                    "start_data_scheduler"
                )
                assert calls.index("reconcile_scheduler_telemetry") < calls.index(
                    "start_portfolio_scheduler"
                )

        wrapped_busy = CalibrationSchemaMismatch(
            "calibration schema fingerprint mismatch"
        )
        busy_code = getattr(sqlite3, "SQLITE_BUSY", 5)
        wrapped_busy.__cause__ = _sqlite_operational_error(busy_code | (3 << 8))
        calls.clear()
        scenario.update(provider_fails=False, migration_error=wrapped_busy)
        asyncio.run(_run_lifespan())
        assert calls == [
            "apply_provider_env",
            "migrate_calibration",
            "reconcile_scheduler_telemetry",
        ]
        assert runtime.provider_config_setup_state().required is True

        for error in (
            CalibrationSchemaMismatch("calibration schema mismatch"),
            RuntimeError("calibration migration logic failure"),
        ):
            calls.clear()
            scenario.update(provider_fails=False, migration_error=error)
            with pytest.raises(type(error), match=str(error)):
                asyncio.run(_run_lifespan())
            assert calls == ["apply_provider_env", "migrate_calibration"]
    finally:
        runtime.clear_provider_config_setup_required()


def test_lifespan_reconciles_pending_calibration_turns_before_scheduler_start(
    monkeypatch, tmp_path
):
    from src.api.app import create_app, lifespan
    from src.api.dependencies import get_investor_calibration_store
    from src.investor_profile_calibration import CalibrationStore
    from src.investor_profile_calibration_schema import migrate_calibration_schema

    profile_dbs = (tmp_path / "profile-a.db", tmp_path / "profile-b.db")
    turn_ids = ("pending-a", "pending-b")

    for db_path, turn_id in zip(profile_dbs, turn_ids):
        migrate_calibration_schema(db_path)
        store = CalibrationStore(db_path)
        session = store.start_session()
        store.begin_answer_turn(
            session_id=session.id,
            turn_id=turn_id,
            answer=f"Answer for {turn_id}",
        )
        assert store.get_turn(turn_id).status == "pending"

    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "1")
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: None)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        lambda: None,
    )

    class CaptureService:
        def reconcile_startup(self):
            return []

    monkeypatch.setattr(
        "src.api.dependencies.get_portfolio_capture_service",
        lambda: CaptureService(),
        raising=False,
    )

    async def _forbidden_data_loop():
        raise AssertionError("data scheduler started while disabled")

    async def _forbidden_portfolio_loop(service):
        raise AssertionError("portfolio scheduler started while disabled")

    monkeypatch.setattr(
        "src.service.data_scheduler.scheduler_loop", _forbidden_data_loop
    )
    monkeypatch.setattr(
        "src.portfolio_capture_scheduler.portfolio_capture_scheduler_loop",
        _forbidden_portfolio_loop,
    )

    async def _run_lifespan():
        async with lifespan(create_app()):
            await asyncio.sleep(0)

    get_investor_calibration_store.cache_clear()
    try:
        for index, (db_path, turn_id) in enumerate(zip(profile_dbs, turn_ids)):
            monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db_path))
            asyncio.run(_run_lifespan())
            assert CalibrationStore(db_path).get_turn(turn_id).status == "interrupted"
            if index == 0:
                assert (
                    CalibrationStore(profile_dbs[1]).get_turn(turn_ids[1]).status
                    == "pending"
                )
    finally:
        get_investor_calibration_store.cache_clear()


def test_profile_db_failure_boots_setup_only(monkeypatch, tmp_path):
    from src.api.app import create_app, lifespan
    from src.api.routes.health import healthz
    from src.api.routes import providers_config
    import src.api.routes.portfolio_capture  # noqa: F401
    import src.provider_config_runtime as runtime

    runtime.clear_provider_config_setup_required()
    started = {"scheduler": False}

    async def _scheduler_loop():
        started["scheduler"] = True

    unavailable_parent = tmp_path / "unavailable-parent"
    unavailable_parent.write_text("not a directory", encoding="utf-8")
    unavailable_db = unavailable_parent / "profile_state.db"

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(unavailable_db))
    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: None)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: object())
    monkeypatch.setattr(
        "src.service.data_scheduler.reconcile_interrupted_runtime_state",
        lambda: None,
    )
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
            assert cfg["setup"]["reason"]
            assert started["scheduler"] is False

    asyncio.run(_run_lifespan())

    cfg = providers_config.providers_config(store=None)
    assert cfg["setup"]["required"] is True
    assert cfg["setup"]["code"] == "provider_config_setup_required"
    assert cfg["setup"]["reason"]
    assert started["scheduler"] is False

    sqlite_error = _sqlite_operational_error(getattr(sqlite3, "SQLITE_ERROR", 1))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "logic-error.db"))
    monkeypatch.setattr(
        "src.investor_profile_calibration_schema.migrate_calibration_schema",
        lambda db_path: (_ for _ in ()).throw(sqlite_error),
    )

    async def _run_fail_fast():
        async with lifespan(create_app()):
            raise AssertionError("SQLITE_ERROR reached application startup")

    with pytest.raises(sqlite3.OperationalError) as exc_info:
        asyncio.run(_run_fail_fast())
    assert exc_info.value is sqlite_error
    assert runtime.provider_config_setup_state().required is False


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
