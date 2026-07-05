from __future__ import annotations

import os

import pytest


def test_required_checks_cover_pg_exit_surfaces():
    from scripts.smoke.pg_unreachable_e2e import REQUIRED_CHECKS

    names = {check.name for check in REQUIRED_CHECKS}
    assert {
        "healthz",
        "system_status",
        "provider_config",
        "provider_health",
        "schedule_status",
        "market_status",
        "market_update_retired",
        "price_read",
        "price_coverage",
        "news_status",
        "news_feed",
        "news_ticker",
        "news_sentiment",
        "fundamentals_stored",
        "iv_history",
        "sa_feed",
        "sa_health",
        "macro_status",
        "macro_health",
        "macro_ipo",
        "reports",
        "universe_summaries",
    } <= names


def test_report_sanitizes_poison_dsn(tmp_path):
    from scripts.smoke.pg_unreachable_e2e import CheckResult, SmokeReport

    report = SmokeReport(
        ok=False,
        poison_label="postgresql://user:secret@host/db?connect_timeout=1",
        pg_attempts=["postgresql://user:secret@host/db?connect_timeout=1"],
        checks=[CheckResult(name="x", ok=False, status_code=500, detail="password=secret123")],
    )
    data = report.to_sanitized_dict()
    text = str(data)
    assert "secret123" not in text
    assert "user:secret" not in text
    assert "postgresql://user:***@host/db" in text


def test_pg_poison_records_and_raises():
    from scripts.smoke.pg_unreachable_e2e import PgPoison

    poison = PgPoison()
    with pytest.raises(RuntimeError, match="PG_UNREACHABLE_E2E_POISON"):
        poison.connect("postgresql://u:p@host/db")
    assert len(poison.attempts) == 1
    assert poison.attempts[0].startswith("postgresql://u:***@host/db")


def test_smoke_fails_if_any_pg_attempt_is_recorded(monkeypatch):
    from scripts.smoke import pg_unreachable_e2e as smoke

    monkeypatch.setattr(smoke, "run_route_checks", lambda client: [])

    class FakePoison(smoke.PgPoison):
        def __init__(self):
            super().__init__()
            self.attempts.append("postgresql://u:***@host/db")

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(smoke, "PgPoison", FakePoison)
    report = smoke.run_smoke(client_factory=FakeClient)
    assert report.ok is False


def test_smoke_fails_on_bad_route_status():
    from scripts.smoke.pg_unreachable_e2e import CheckSpec, run_route_checks

    class Response:
        status_code = 500

        def json(self):
            return {"error": "boom"}

    class Client:
        def request(self, method, path):
            return Response()

    checks = [CheckSpec("bad", "GET", "/bad", 200)]
    result = run_route_checks(Client(), checks)[0]
    assert result.ok is False
    assert result.status_code == 500


def test_market_status_assertion_requires_no_pg_fallback():
    from scripts.smoke.pg_unreachable_e2e import _assert_market_status

    with pytest.raises(AssertionError):
        _assert_market_status({
            "pg_fallback_active": True,
            "prices_authority": "pg",
            "routing_enabled": False,
        })


def test_run_smoke_restores_environment_flags(monkeypatch):
    from scripts.smoke import pg_unreachable_e2e as smoke

    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "already-set")
    monkeypatch.delenv("ARKSCOPE_PG_UNREACHABLE_E2E", raising=False)
    monkeypatch.setattr(smoke, "run_route_checks", lambda client: [])

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    smoke.run_smoke(client_factory=FakeClient)

    assert os.environ["ARKSCOPE_DISABLE_SCHEDULER"] == "already-set"
    assert "ARKSCOPE_PG_UNREACHABLE_E2E" not in os.environ


def test_pg_poison_redacts_kwarg_credentials():
    # All current call sites pass a positional DSN, but psycopg2.connect(host=...,
    # password=...) is legal — a future call site must not leak credentials into
    # pg_attempts (dict repr defeats the URL/key=value sanitizer regexes).
    from scripts.smoke.pg_unreachable_e2e import PgPoison

    poison = PgPoison()
    with pytest.raises(RuntimeError, match="PG_UNREACHABLE_E2E_POISON"):
        poison.connect(host="h", dbname="d", user="u", password="s3cret", connect_timeout=3)

    label = poison.attempts[0]
    assert "s3cret" not in label
    assert "password" in label  # key survives for diagnostics; value is redacted


def test_bootstrap_repo_root_inserts_src_import_path(monkeypatch):
    # Running `python scripts/smoke/pg_unreachable_e2e.py` sets sys.path[0] to
    # scripts/smoke, not the repo root. The harness must repair that before
    # importing src.* inside run_smoke().
    import sys
    from pathlib import Path
    from scripts.smoke import pg_unreachable_e2e as smoke

    root = str(Path(smoke.__file__).resolve().parents[2])
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != root])

    smoke._bootstrap_repo_root()

    assert sys.path[0] == root


def test_handler_direct_client_runs_healthz_without_testclient():
    # The live PG-unreachable smoke intentionally bypasses FastAPI TestClient:
    # in this environment TestClient/lifespan can hang before any route evidence
    # is produced. The harness must still exercise the same handlers.
    from scripts.smoke import pg_unreachable_e2e as smoke

    client = smoke._HandlerDirectClient(
        dal=object(),
        registry=object(),
        profile_store=object(),
        provider_store=None,
    )

    with client as active:
        response = active.request("GET", "/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_handler_direct_client_preserves_http_exception_detail(monkeypatch):
    from fastapi import HTTPException

    from scripts.smoke import pg_unreachable_e2e as smoke
    from src.api.routes import market_data

    def reject_update(store):
        raise HTTPException(
            status_code=409,
            detail={"code": "pg_market_update_retired"},
        )

    monkeypatch.setattr(market_data, "update_route", reject_update)
    client = smoke._HandlerDirectClient(
        dal=object(),
        registry=object(),
        profile_store=object(),
        provider_store=None,
    )

    with client as active:
        response = active.request("POST", "/market-data/update")

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "pg_market_update_retired"}}


def test_macro_disabled_503_is_explicit_config_state_not_pg_failure():
    from scripts.smoke.pg_unreachable_e2e import REQUIRED_CHECKS, run_route_checks

    class Response:
        status_code = 503

        def json(self):
            return {
                "detail": "macro_calendar.enabled is false in config. "
                "Enable it in config/user_profile.yaml to activate the FRED layer."
            }

    class Client:
        def request(self, method, path):
            return Response()

    checks = [
        check
        for check in REQUIRED_CHECKS
        if check.name in {"macro_health", "macro_ipo"}
    ]

    results = run_route_checks(Client(), checks)

    assert [result.ok for result in results] == [True, True]


def test_provider_config_policy_assertion_is_env_and_invariant_aware(monkeypatch):
    from scripts.smoke.pg_unreachable_e2e import (
        REQUIRED_CHECKS,
        _assert_provider_config_policy,
    )

    assert "provider_config_policy" in {check.name for check in REQUIRED_CHECKS}

    strict_body = {
        "env_fallback": {"enabled": False, "source": "env"},
        "providers": {"polygon": {"fields": [
            {"field": "api_key", "effective_source": "missing"}]}},
    }
    fallback_body = {
        "env_fallback": {"enabled": True, "source": "env"},
        "providers": {"polygon": {"fields": [
            {"field": "api_key", "effective_source": "missing"}]}},
    }
    leaking_body = {
        "env_fallback": {"enabled": False, "source": "default"},
        "providers": {"polygon": {"fields": [
            {"field": "api_key", "effective_source": "config/.env"}]}},
    }

    monkeypatch.setenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", "false")
    _assert_provider_config_policy(strict_body)
    with pytest.raises(AssertionError):
        _assert_provider_config_policy(fallback_body)

    monkeypatch.setenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", "true")
    _assert_provider_config_policy(fallback_body)
    with pytest.raises(AssertionError):
        _assert_provider_config_policy(strict_body)

    # env unset: no expectation on enabled, but strict-active responses must
    # never report a managed field sourced from config/.env.
    monkeypatch.delenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", raising=False)
    with pytest.raises(AssertionError):
        _assert_provider_config_policy(leaking_body)
