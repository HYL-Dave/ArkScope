"""S1 piece-2: OAuth token-storage abstraction skeleton.

Strict scope: a token store (save/load/delete/status) keyed by
(provider, auth_mode, credential_id), keyring-first with a plaintext-0600 dev
fallback that is CLEARLY flagged in status. NO OAuth login/refresh, NO driver
factory, NO main-agent wiring, NO change to llm_credentials (the real token lives
HERE, never in CredentialStore.secret).
"""

from __future__ import annotations

import os
import stat

import pytest

from src.auth_drivers.token_store import (
    KeyringTokenStore,
    PlaintextTokenStore,
    StoredTokenRecord,
    get_token_store,
)

_REC = StoredTokenRecord(
    access_token="SECRET-ACCESS-TOKEN",
    refresh_token="SECRET-REFRESH-TOKEN",
    expires_at="2027-06-15T00:00:00+00:00",
    plan_type="plus",
    account_label="acct-redacted-1",
)
_KEY = dict(provider="openai", auth_mode="chatgpt_oauth", credential_id="local:1")


# --- PlaintextTokenStore (the always-available dev fallback) ----------------
@pytest.fixture()
def plain(tmp_path):
    return PlaintextTokenStore(tmp_path / "auth_tokens.json")


def test_plaintext_save_load_roundtrip(plain):
    plain.save(record=_REC, **_KEY)
    got = plain.load(**_KEY)
    assert got == _REC
    assert got.access_token == "SECRET-ACCESS-TOKEN" and got.refresh_token == "SECRET-REFRESH-TOKEN"


def test_plaintext_file_is_0600(plain):
    plain.save(record=_REC, **_KEY)
    mode = stat.S_IMODE(os.stat(plain.path).st_mode)
    assert mode == 0o600


def test_status_is_redacted_no_token_leak(plain):
    plain.save(record=_REC, **_KEY)
    st = plain.status(**_KEY)
    assert st["logged_in"] is True and st["backend"] == "plaintext_dev"
    assert st["expires_at"] == "2027-06-15T00:00:00+00:00" and st["plan_type"] == "plus"
    assert st["account_label"] == "acct-redacted-1"
    blob = repr(st)
    assert "SECRET-ACCESS-TOKEN" not in blob and "SECRET-REFRESH-TOKEN" not in blob


def test_status_logged_out_for_missing(plain):
    st = plain.status(**_KEY)
    assert st["logged_in"] is False and st["backend"] == "plaintext_dev"


def test_keys_are_separated_by_provider_auth_mode_credential(plain):
    plain.save(record=_REC, provider="openai", auth_mode="chatgpt_oauth", credential_id="local:1")
    other = StoredTokenRecord(access_token="OTHER-AT")
    plain.save(record=other, provider="anthropic", auth_mode="claude_code_oauth", credential_id="local:2")
    assert plain.load(provider="openai", auth_mode="chatgpt_oauth", credential_id="local:1").access_token == "SECRET-ACCESS-TOKEN"
    assert plain.load(provider="anthropic", auth_mode="claude_code_oauth", credential_id="local:2").access_token == "OTHER-AT"
    # a different credential_id under the same provider/mode is a distinct slot
    assert plain.load(provider="openai", auth_mode="chatgpt_oauth", credential_id="local:99") is None


def test_plaintext_delete(plain):
    plain.save(record=_REC, **_KEY)
    assert plain.delete(**_KEY) is True
    assert plain.load(**_KEY) is None
    assert plain.delete(**_KEY) is False


# --- KeyringTokenStore (mocked keyring — no live SecretService dependency) ---
@pytest.fixture()
def fake_keyring(monkeypatch):
    mem: dict[tuple[str, str], str] = {}
    import src.auth_drivers.token_store as ts

    monkeypatch.setattr(ts, "_kr_set", lambda svc, k, v: mem.__setitem__((svc, k), v))
    monkeypatch.setattr(ts, "_kr_get", lambda svc, k: mem.get((svc, k)))
    monkeypatch.setattr(ts, "_kr_delete", lambda svc, k: mem.pop((svc, k), None) is not None)
    return mem


def test_keyring_roundtrip_and_status(fake_keyring):
    ks = KeyringTokenStore(service="arkscope-test")
    assert ks.backend == "keyring"
    ks.save(record=_REC, **_KEY)
    assert ks.load(**_KEY) == _REC
    st = ks.status(**_KEY)
    assert st["logged_in"] is True and st["backend"] == "keyring"
    assert "SECRET-ACCESS-TOKEN" not in repr(st)
    assert ks.delete(**_KEY) is True and ks.load(**_KEY) is None


# --- factory: keyring-first, plaintext fallback (flagged) -------------------
def test_factory_explicit_plaintext(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_TOKEN_STORE", raising=False)
    s = get_token_store(prefer="plaintext", dev_path=tmp_path / "t.json")
    assert isinstance(s, PlaintextTokenStore) and s.backend == "plaintext_dev"


def test_factory_env_override_plaintext(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_TOKEN_STORE", "plaintext")
    assert get_token_store(dev_path=tmp_path / "t.json").backend == "plaintext_dev"


def test_factory_auto_falls_back_to_plaintext_when_keyring_unusable(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_TOKEN_STORE", raising=False)
    monkeypatch.setattr(KeyringTokenStore, "usable", staticmethod(lambda: False))
    s = get_token_store(dev_path=tmp_path / "t.json")
    assert isinstance(s, PlaintextTokenStore)
    assert s.status(**_KEY)["backend"] == "plaintext_dev"  # fallback is visible in status


# --- Piece 2.1 hardening ----------------------------------------------------
def test_factory_explicit_keyring_unavailable_fails_loud(monkeypatch):
    # EXPLICIT keyring must NOT silently degrade — fail loud (auto still falls back).
    monkeypatch.delenv("ARKSCOPE_TOKEN_STORE", raising=False)
    monkeypatch.setattr(KeyringTokenStore, "usable", staticmethod(lambda: False))
    with pytest.raises(RuntimeError):
        get_token_store(prefer="keyring")
    monkeypatch.setenv("ARKSCOPE_TOKEN_STORE", "keyring")
    with pytest.raises(RuntimeError):
        get_token_store()


def test_plaintext_write_is_atomic_no_temp_leftover(tmp_path):
    store = PlaintextTokenStore(tmp_path / "auth_tokens.json")
    store.save(record=_REC, **_KEY)
    store.save(record=StoredTokenRecord(access_token="AT2"), provider="anthropic", auth_mode="claude_code_oauth", credential_id="local:2")
    # atomic temp+replace leaves only the target file (no half-written .tmp)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["auth_tokens.json"]
    import json as _json

    with open(store.path, encoding="utf-8") as f:
        _json.load(f)  # always valid JSON after rewrites
    assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600


def test_status_never_includes_metadata(plain):
    rec = StoredTokenRecord(access_token="AT", metadata={"id_token": "SECRET-ID-TOKEN", "account_id": "acct-xyz"})
    plain.save(record=rec, **_KEY)
    st = plain.status(**_KEY)
    assert "metadata" not in st
    assert "SECRET-ID-TOKEN" not in repr(st) and "acct-xyz" not in repr(st)
