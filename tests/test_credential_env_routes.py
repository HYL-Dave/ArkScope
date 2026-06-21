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
    # default-DISABLED apply boundary for every test (the real switch is opt-in);
    # require_profile_state_write is a no-op audit log today, so the apply flag is
    # the actual code-enforced gate.
    monkeypatch.delenv("ARKSCOPE_CREDENTIAL_APPLY_ENABLED", raising=False)
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


def test_import_env_route_refuses_real_write_when_apply_disabled(store, monkeypatch, _hermetic_env, _gate):
    # apply disabled by default (the _gate fixture clears the flag) — a real
    # (non-dry-run) import must be refused 403 with NO write, NO gate call.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-routeimport1")
    with pytest.raises(HTTPException) as ei:
        cr.import_env_route(cr.ImportEnvRequest(dry_run=False), store=store)
    assert ei.value.status_code == 403
    assert store.list() == [] and _gate == []  # nothing written, gate not reached


def test_import_env_route_real_writes_and_gates(store, monkeypatch, _hermetic_env, _gate):
    monkeypatch.setenv("ARKSCOPE_CREDENTIAL_APPLY_ENABLED", "1")  # explicitly enable apply
    monkeypatch.setenv("OPENAI_API_KEY", "sk-routeimport2")
    res = cr.import_env_route(cr.ImportEnvRequest(dry_run=False), store=store)
    assert res["dry_run"] is False and len(store.list()) == 1
    assert len(_gate) == 1  # real write goes through the profile-state gate
    assert "sk-routeimport2" not in json.dumps(res)  # response is labels/counts, no secret


def test_export_env_route_refused_when_apply_disabled(store, tmp_path, _gate):
    # apply disabled by default — a real file write must be refused 403, no file.
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-x111", make_active=True)
    path = tmp_path / "out.env"
    with pytest.raises(HTTPException) as ei:
        cr.export_env_route(cr.ExportEnvRequest(path=str(path)), store=store)
    assert ei.value.status_code == 403
    assert not path.exists() and _gate == []  # nothing written, gate not reached


def test_export_env_route_writes_0600_and_returns_labels(store, tmp_path, monkeypatch, _gate):
    monkeypatch.setenv("ARKSCOPE_CREDENTIAL_APPLY_ENABLED", "1")  # explicitly enable apply
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


def test_update_route_key_to_key_switch_keeps_single_active(store, _gate):
    # set-active across two api_key rows (key↔key) must leave exactly one active.
    a = store.add(provider="openai", auth_type="api_key", alias="A", secret="sk-aaaa11111", make_active=True)
    b = store.add(provider="openai", auth_type="api_key", alias="B", secret="sk-bbbb22222", make_active=False)
    cr.update_credential(f"local:{b.id}", cr.CredentialUpdate(active=True), store=store)
    act = [r for r in store.list(provider="openai") if r.active]
    assert len(act) == 1 and act[0].id == b.id  # switched to B, A deactivated (index holds)


def test_update_route_key_oauth_switch_both_directions(store, _gate):
    # set-active across an api_key and a Claude OAuth row (key↔OAuth), both ways,
    # always single active for the provider.
    oauth = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)
    key = store.add(provider="anthropic", auth_type="api_key", alias="A key", secret="sk-ant-aaaa111", make_active=False)
    cr.update_credential(f"local:{key.id}", cr.CredentialUpdate(active=True), store=store)
    act = [r for r in store.list(provider="anthropic") if r.active]
    assert len(act) == 1 and act[0].id == key.id  # OAuth deactivated, key active
    cr.update_credential(f"local:{oauth.id}", cr.CredentialUpdate(active=True), store=store)
    act = [r for r in store.list(provider="anthropic") if r.active]
    assert len(act) == 1 and act[0].id == oauth.id and act[0].auth_type == "claude_code_oauth"  # back to OAuth


def test_update_route_oauth_metadata_label_and_expiry(store, _gate):
    oauth = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)

    out = cr.update_credential(
        f"local:{oauth.id}",
        cr.CredentialUpdate(account_label="Claude Max", expires_at="2027-06-16T00:00:00+00:00"),
        store=store,
    )

    cred = out["credential"]
    assert cred["account_label"] == "Claude Max"
    assert cred["expires_at"] == "2027-06-16T00:00:00+00:00"
    assert store.get(f"local:{oauth.id}").account_label == "Claude Max"
    assert "Claude Max" not in json.dumps(_gate, default=str)


def test_export_env_route_refuses_symlink_to_arbitrary_file(store, tmp_path, _gate):
    # a symlink to ANY file (not just config/.env) must be refused — the route's
    # config/.env realpath-guard is not enough; an islink check covers the rest.
    victim = tmp_path / "victim.conf"
    victim.write_text("KEEP=1\n")
    os.chmod(victim, 0o644)
    link = tmp_path / "out.env"
    os.symlink(str(victim), str(link))
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-x111", make_active=True)
    with pytest.raises(HTTPException) as ei:
        cr.export_env_route(cr.ExportEnvRequest(path=str(link)), store=store)
    assert ei.value.status_code == 400
    assert victim.read_text() == "KEEP=1\n"  # victim untouched
    assert _gate == []  # refused before the write gate


def test_export_env_route_refuses_symlink_to_live_env(store, tmp_path, monkeypatch, _gate):
    # a symlink whose TARGET is the live env must be refused too (realpath, not
    # abspath) — else write_env_export would write THROUGH it and clobber the
    # live env. Point env_file_path at a temp 'live env' so the real one is never
    # at risk even if the guard regresses.
    fake_live = tmp_path / "live.env"
    fake_live.write_text("DATABASE_URL=keep-me\n")
    monkeypatch.setattr(cr, "env_file_path", lambda: fake_live)
    link = tmp_path / "sneaky.env"
    os.symlink(str(fake_live), str(link))
    with pytest.raises(HTTPException) as ei:
        cr.export_env_route(cr.ExportEnvRequest(path=str(link)), store=store)
    assert ei.value.status_code == 400
    assert _gate == []  # refused before any write
    assert fake_live.read_text() == "DATABASE_URL=keep-me\n"  # live env untouched
