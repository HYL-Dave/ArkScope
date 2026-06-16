"""Shim plumbing — import-env / export-env route handlers (handler-direct, no
TestClient per the route-unit-test convention). Temp DB + fake env + temp file
ONLY — never the real config/.env or profile DB. Responses carry counts/labels,
never a secret. FAKE keys only.
"""

from __future__ import annotations

import json
import os
import stat

import pytest
from fastapi import HTTPException

from src.api.routes import config_routes as cr
from src.env_keys import env_file_path
from src.model_credentials import CredentialStore

_LLM_ENV = ("OPENAI_API_KEY", "OPENAI_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS")


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


@pytest.fixture(autouse=True)
def _gate(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: calls.append((a, k)))
    return calls


@pytest.fixture()
def _hermetic_env(monkeypatch):
    # don't load the real config/.env; clear ambient LLM keys so only what the
    # test sets is seen by import_env_credentials.
    monkeypatch.setattr("src.model_credentials.ensure_env_loaded", lambda: None)
    for k in _LLM_ENV:
        monkeypatch.delenv(k, raising=False)


def test_import_env_route_dry_run_previews_without_writing(store, monkeypatch, _hermetic_env, _gate):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-routeimport1")
    res = cr.import_env_route(cr.ImportEnvRequest(dry_run=True), store=store)
    assert res["dry_run"] is True
    assert res["providers"]["openai"]["added"] == ["OpenAI primary"]
    assert store.list() == []  # dry-run wrote nothing
    assert _gate == []  # write gate NOT invoked for a preview


def test_import_env_route_real_writes_and_gates(store, monkeypatch, _hermetic_env, _gate):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-routeimport2")
    res = cr.import_env_route(cr.ImportEnvRequest(dry_run=False), store=store)
    assert res["dry_run"] is False and len(store.list()) == 1
    assert len(_gate) == 1  # real write goes through the profile-state gate
    assert "sk-routeimport2" not in json.dumps(res)  # response is labels/counts, no secret


def test_export_env_route_writes_0600_and_returns_labels(store, tmp_path, _gate):
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-routeexp1", make_active=True)
    path = tmp_path / "out.env"
    res = cr.export_env_route(cr.ExportEnvRequest(path=str(path)), store=store)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert "OPENAI_API_KEY" in res["vars"] and res["key_count"] == 1
    assert "sk-routeexp1" not in json.dumps(res)  # response has no secret
    assert "sk-routeexp1" in path.read_text()  # the FILE does (its purpose)
    assert len(_gate) == 1


def test_export_env_route_refuses_to_clobber_live_env(store, _gate):
    with pytest.raises(HTTPException) as ei:
        cr.export_env_route(cr.ExportEnvRequest(path=str(env_file_path())), store=store)
    assert ei.value.status_code == 400
    assert _gate == []  # refused BEFORE the write gate — no side effect


def test_export_env_route_rejects_blank_path(store, _gate):
    with pytest.raises(HTTPException) as ei:
        cr.export_env_route(cr.ExportEnvRequest(path="   "), store=store)
    assert ei.value.status_code == 400
