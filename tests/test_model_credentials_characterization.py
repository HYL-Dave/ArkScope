"""S1 characterization tests — PIN the CURRENT LLM CredentialStore + config-route
behavior BEFORE the auth_type schema delta, so the regression gate ("old api_key
behavior unchanged") becomes provable. These must be GREEN on today's code = the
baseline.

A few assertions intentionally document behavior S1 WILL change (the legacy
`oauth`/`setup_token` auth_type values; the route allow-set that currently rejects
the explicit modes). Those are marked CURRENT-BASELINE and get updated in the
schema-delta step; the api_key CRUD / discovery / _resolve ones must STAY green.
"""

from __future__ import annotations

import pytest

from src.model_credentials import (
    CredentialStore,
    _mask_secret,
    _resolve_api_credential,
    discover_models,
    provider_credentials,
)
# aliased: the function is literally named test_model → pytest would mis-collect it
from src.model_credentials import test_model as run_model_test

_ENV_KEYS = (
    "OPENAI_API_KEY", "OPENAI_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
    "OPENAI_OAUTH_TOKEN", "ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_SETUP_TOKEN",
)


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


@pytest.fixture()
def clean_env(monkeypatch):
    """Hermetic: don't load config/.env, and clear provider env keys so discovery
    has no ambient credential (→ no network)."""
    monkeypatch.setattr("src.model_credentials.ensure_env_loaded", lambda: None)
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


# --- CredentialStore CRUD (api_key; pure SQLite, the load-bearing path) ------
def test_add_api_key_returns_stored_credential(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k1", secret="sk-AAAA1111BBBB")
    assert c.provider == "openai" and c.auth_type == "api_key" and c.alias == "k1"
    assert c.secret == "sk-AAAA1111BBBB" and c.active is True
    assert isinstance(c.id, int)
    assert isinstance(c.created_at, str) and c.created_at == c.updated_at


def test_list_and_get(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k1", secret="sk-xxxxxxxxxxxx")
    assert [x.id for x in store.list()] == [c.id]
    assert store.list(provider="anthropic") == []
    assert store.get(f"local:{c.id}").alias == "k1"
    assert store.get("local:9999") is None
    assert store.get("not-a-local-id") is None  # non-local id → None


def test_single_active_per_provider(store):
    a = store.add(provider="openai", auth_type="api_key", alias="a", secret="sk-aaaaaaaaaa11")
    b = store.add(provider="openai", auth_type="api_key", alias="b", secret="sk-bbbbbbbbbb22")
    active = {x.alias: x.active for x in store.list(provider="openai")}
    assert active == {"a": False, "b": True}  # newest make_active wins; single active
    an = store.add(provider="anthropic", auth_type="api_key", alias="an", secret="sk-ant-cccccccc")
    assert an.active is True
    assert store.get(f"local:{b.id}").active is True  # anthropic active independent of openai


def test_update_alias_secret_active_reactivates(store):
    a = store.add(provider="openai", auth_type="api_key", alias="a", secret="sk-aaaaaaaaaa11", make_active=False)
    b = store.add(provider="openai", auth_type="api_key", alias="b", secret="sk-bbbbbbbbbb22", make_active=True)
    upd = store.update(f"local:{a.id}", alias="a2", active=True)
    assert upd.alias == "a2" and upd.active is True
    assert store.get(f"local:{b.id}").active is False  # activating a deactivates b
    assert store.update("local:9999", alias="x") is None  # missing → None


def test_delete(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxxxx")
    assert store.delete(f"local:{c.id}") is True
    assert store.delete(f"local:{c.id}") is False
    assert store.delete("bad") is False


def test_row_dto_observable_fields(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxxxx")
    got = store.get(f"local:{c.id}")
    # pin the observable api_key fields (subset → survives additive S1 columns)
    assert (got.id, got.provider, got.auth_type, got.alias, got.secret, got.active) == (
        c.id, "openai", "api_key", "k", "sk-xxxxxxxxxxxx", True,
    )


# --- provider_credentials() masked inventory --------------------------------
def test_provider_credentials_local_api_key_row(store, clean_env):
    store.add(provider="openai", auth_type="api_key", alias="local-oa", secret="sk-realkeyvalue9")
    oa = provider_credentials(store)["openai"]
    local = next(c for c in oa if c.id.startswith("local:"))
    assert local.auth_type == "api_key" and local.editable is True
    assert local.can_discover_models is True and local.can_test_models is True
    assert local.masked and "sk-realkeyvalue9" not in (local.masked or "")  # secret never leaked


def test_provider_credentials_placeholders_use_explicit_modes(store, clean_env):
    # The OpenAI ChatGPT-OAuth placeholder stays as the lone S3 signpost (OpenAI
    # has no import route yet). The two Anthropic env placeholders are REMOVED:
    # the working Claude setup-token path renders as an import-created local: row
    # (see test_provider_credentials_oauth_local_row_no_secret_no_crash), so the
    # env rows were redundant + misleading.
    inv = provider_credentials(store)
    oa = {c.id: c for c in inv["openai"]}
    an = {c.id: c for c in inv["anthropic"]}
    assert oa["openai:OPENAI_OAUTH_TOKEN"].auth_type == "chatgpt_oauth"
    assert oa["openai:OPENAI_OAUTH_TOKEN"].can_discover_models is False  # still not a direct key
    # the two Anthropic env placeholders are gone (superseded by the token-store import row)
    assert "anthropic:ANTHROPIC_OAUTH_TOKEN" not in an
    assert "anthropic:ANTHROPIC_SETUP_TOKEN" not in an


# --- discovery / test on the api_key path (no-network paths) -----------------
def test_discover_models_missing_credential_falls_back_to_seed(store, clean_env):
    res = discover_models("openai", credential_id=None, store=store)
    assert res.status == "missing_credential"
    assert len(res.models) > 0 and all(m.source == "seed" for m in res.models)  # no network


def test_run_model_test_missing_credential(store, clean_env):
    res = run_model_test("openai", "gpt-5.4", credential_id=None, store=store)
    assert res.status == "missing_credential" and res.model == "gpt-5.4"


def test_resolve_api_credential_picks_api_key(store, clean_env):
    api = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-realkeyvalue9", make_active=True)
    r = _resolve_api_credential("openai", f"local:{api.id}", store)
    assert r is not None and r.secret == "sk-realkeyvalue9" and r.auth_type == "api_key"


def test_resolve_api_credential_ignores_non_apikey_rows(store, clean_env):
    # an OAuth row (created via add_oauth_credential — secret stays in the
    # token-store) does NOT resolve as a usable API credential.
    o = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="o", make_active=False)
    assert _resolve_api_credential("anthropic", f"local:{o.id}", store) is None


# --- config route allow-set (handler-direct; not TestClient) -----------------
def test_route_rejects_unknown_auth_type(store):
    from fastapi import HTTPException

    from src.api.routes.config_routes import CredentialCreate, add_credential

    body = CredentialCreate(provider="openai", auth_type="bogus", alias="k", secret="sk-x", make_active=True)
    with pytest.raises(HTTPException) as ei:
        add_credential(body, store=store)
    assert ei.value.status_code == 400


def test_route_rejects_oauth_modes_with_import_hint(store, monkeypatch, clean_env):
    # HARDENED: the generic add route is for DIRECT API keys only. OAuth/legacy
    # modes are rejected (use the OAuth import route) so a token can't reach
    # llm_credentials.secret via the API. Nothing is persisted on rejection.
    from fastapi import HTTPException

    from src.api.routes import config_routes as cr

    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: None)
    for mode in ("chatgpt_oauth", "claude_code_oauth", "oauth", "setup_token"):
        body = cr.CredentialCreate(provider="anthropic", auth_type=mode, alias="o", secret="tok-value-1234", make_active=True)
        with pytest.raises(HTTPException) as ei:
            cr.add_credential(body, store=store)
        assert ei.value.status_code == 400 and "import" in str(ei.value.detail).lower()
    assert store.list() == []  # NOTHING persisted — no token leaked into the DB


def test_route_accepts_api_key(store, monkeypatch, clean_env):
    from src.api.routes import config_routes as cr

    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: None)  # neutralize write gate
    body = cr.CredentialCreate(provider="openai", auth_type="api_key", alias="k", secret="sk-realkeyvalue9", make_active=True)
    res = cr.add_credential(body, store=store)
    assert res["credential"]["auth_type"] == "api_key" and res["credential"]["id"].startswith("local:")


# ===========================================================================
# S1 NEW behavior: explicit auth modes, legacy normalization, OAuth metadata
# ===========================================================================
def test_read_normalizes_legacy_auth_types(store):
    # Pre-existing legacy rows (inserted raw to bypass add()'s write-normalize)
    # must normalize to provider-specific explicit modes ON READ.
    import sqlite3

    now = "2026-01-01T00:00:00+00:00"
    with sqlite3.connect(store.db_path) as conn:
        for prov, at, alias in [("anthropic", "setup_token", "s"), ("anthropic", "oauth", "o"), ("openai", "oauth", "o2")]:
            conn.execute(
                "INSERT INTO llm_credentials (provider,auth_type,alias,secret,active,created_at,updated_at) "
                "VALUES (?,?,?,?,0,?,?)", (prov, at, alias, "tok", now, now),
            )
        conn.commit()
    modes = {c.alias: c.auth_type for c in store.list()}
    assert modes["s"] == "claude_code_oauth"   # setup_token → claude_code_oauth
    assert modes["o"] == "claude_code_oauth"   # anthropic oauth → claude_code_oauth
    assert modes["o2"] == "chatgpt_oauth"      # openai oauth → chatgpt_oauth


def test_add_rejects_oauth_modes_and_bogus(store):
    # HARDENED: add() is for DIRECT API keys only. OAuth/legacy modes must use
    # add_oauth_credential() (so a token can't land in llm_credentials.secret).
    for mode in ("oauth", "setup_token", "chatgpt_oauth", "claude_code_oauth"):
        with pytest.raises(ValueError):
            store.add(provider="anthropic", auth_type=mode, alias="a", secret="tok-1234")
    with pytest.raises(ValueError):
        store.add(provider="openai", auth_type="bogus", alias="d", secret="x")
    # api_key still works
    assert store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxx").auth_type == "api_key"


@pytest.mark.parametrize("bad", ["sk-a\nINJECT=evil", "sk-a\rfoo", "sk-a\tb"])
def test_add_rejects_control_chars_in_secret(store, bad):
    # a newline in a secret would break the .env export line (truncating the
    # secret + injecting a spurious KEY=value); reject control chars at the
    # store boundary so a corrupt/injected secret never persists.
    with pytest.raises(ValueError):
        store.add(provider="openai", auth_type="api_key", alias="k", secret=bad)


@pytest.mark.parametrize("bad_alias", ["a\nINJECT=evil", "a\rb", "a\tb"])
def test_add_rejects_control_chars_in_alias(store, bad_alias):
    # a newline in an alias would break OUT of its '# comment' line on export and
    # inject an arbitrary env var into the .env; reject at the boundary.
    with pytest.raises(ValueError):
        store.add(provider="openai", auth_type="api_key", alias=bad_alias, secret="sk-okkey1234")


def test_add_rejects_quote_wrapped_secret(store):
    # a fully quote-wrapped secret is silently de-quoted by the loader on
    # re-import (round-trip corruption); reject so the stored form is canonical.
    with pytest.raises(ValueError):
        store.add(provider="openai", auth_type="api_key", alias="k", secret='"sk-wrapped123"')
    # an interior quote (not a wrapping pair) is fine
    assert store.add(provider="openai", auth_type="api_key", alias="k2", secret='sk-mid"quote9').secret == 'sk-mid"quote9'


def test_add_oauth_rejects_control_chars_in_alias(store):
    with pytest.raises(ValueError):
        store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="x\nINJECT=evil")


def test_update_rejects_control_chars(store):
    k = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-okkey1234")
    with pytest.raises(ValueError):
        store.update(f"local:{k.id}", secret="sk-a\nINJECT=evil")
    with pytest.raises(ValueError):
        store.update(f"local:{k.id}", alias="a\nINJECT=evil")


def test_add_rejects_api_key_pool(store):
    # api_key_pool is an env-compat READ representation only (provider_credentials
    # still renders pool inventory rows from a comma-separated env var). A STORED
    # local:N pool row is UNRESOLVABLE: _resolve_api_credential derives a pool
    # secret by parsing an index off the credential id and indexing the env var,
    # which a DB row has no source for. So pool keys must be stored as individual
    # api_key rows; add() rejects the pool mode outright.
    with pytest.raises(ValueError):
        store.add(provider="openai", auth_type="api_key_pool", alias="p", secret="sk-poolkey12345")
    # api_key still works (regression)
    assert store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-singlekey999").auth_type == "api_key"


def test_provider_credentials_dedups_env_key_matching_a_db_row(store, clean_env, monkeypatch):
    # Interop export writes the active key to bare OPENAI_API_KEY AND it is a DB
    # row. The inventory must show that secret ONCE (the editable DB row), not
    # also as a second read-only env row — else the duplicate-row confusion the
    # whole credential rework set out to kill comes back.
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-shared99999", make_active=True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shared99999")
    ids = [c.id for c in provider_credentials(store)["openai"]]
    assert "openai:OPENAI_API_KEY" not in ids  # env row suppressed (secret already a DB row)
    assert any(i.startswith("local:") for i in ids)  # the DB row remains


def test_provider_credentials_dedups_pool_entry_matching_a_db_row(store, clean_env, monkeypatch):
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-inboth111", make_active=True)
    monkeypatch.setenv("OPENAI_API_KEYS", "sk-inboth111,sk-poolonly222")
    oa = provider_credentials(store)["openai"]
    masks = [c.masked for c in oa if c.auth_type == "api_key_pool"]
    # the pool entry equal to the DB secret is deduped; the distinct pool key stays
    assert _mask_secret("sk-inboth111") not in masks
    assert _mask_secret("sk-poolonly222") in masks


def test_provider_credentials_keeps_env_key_not_in_db(store, clean_env, monkeypatch):
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-indb1111", make_active=True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-onlyinenv222")
    ids = [c.id for c in provider_credentials(store)["openai"]]
    assert "openai:OPENAI_API_KEY" in ids  # a DISTINCT env key still surfaces


def _insert_legacy_pool_row(store, *, secret="sk-legacypool999", active=1):
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO llm_credentials "
            "(provider, auth_type, alias, secret, active, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("openai", "api_key_pool", "legacy pool", secret, active, "t", "t"),
        )
        conn.commit()
    return next(r for r in store.list() if r.auth_type == "api_key_pool")


def test_legacy_local_pool_row_not_resolved_as_direct_key(store, clean_env):
    # C3a blocks NEW pool rows; a crafted LEGACY local api_key_pool row must also
    # be inert on READ — a stored pool row is unresolvable (its secret is not an
    # env-indexable pool), so it must not resolve as a direct key.
    row = _insert_legacy_pool_row(store)
    assert _resolve_api_credential("openai", f"local:{row.id}", store=store) is None


def test_legacy_local_pool_row_marked_unusable_in_inventory(store, clean_env):
    row = _insert_legacy_pool_row(store)
    inv = {c.id: c for c in provider_credentials(store)["openai"]}
    c = inv[f"local:{row.id}"]
    assert c.can_discover_models is False and c.can_test_models is False  # not a usable direct key


def test_update_rejects_secret_on_api_key_pool_row(store):
    # update() must MIRROR add()/C3a: a secret can only be written onto a plain
    # api_key row. api_key_pool is an env-compat-only representation and a stored
    # local:N pool row is unresolvable, so writing a secret onto one is rejected.
    # add() now refuses to create a pool row, so craft a legacy one directly.
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO llm_credentials "
            "(provider, auth_type, alias, secret, active, created_at, updated_at) "
            "VALUES (?,?,?,?,0,?,?)",
            ("openai", "api_key_pool", "legacy-pool", "sk-old00000000", "t", "t"),
        )
        conn.commit()
    pool_row = next(c for c in store.list() if c.auth_type == "api_key_pool")
    with pytest.raises(ValueError):
        store.update(f"local:{pool_row.id}", secret="sk-new00000000")
    # alias/active updates on the pool row are still allowed (no secret write)
    assert store.update(f"local:{pool_row.id}", alias="renamed").alias == "renamed"


def test_api_key_rows_leave_oauth_metadata_null(store):
    # api_key rows carry no OAuth metadata. (OAuth metadata roundtrip is covered
    # by test_add_oauth_credential_has_null_secret via add_oauth_credential.)
    k = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxxxx")
    kg = store.get(f"local:{k.id}")
    assert kg.expires_at is None and kg.account_label is None and kg.secret == "sk-xxxxxxxxxxxx"


# --- S4-prep: add_oauth_credential — secret stays NULL (token in token-store) ---
def test_add_oauth_credential_has_null_secret(store):
    c = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude",
                                   expires_at="2027-06-16T00:00:00+00:00", account_label="Pro plan")
    got = store.get(f"local:{c.id}")
    assert got.secret is None  # the real token lives in the token-store, NOT here
    assert got.auth_type == "claude_code_oauth" and got.active is True
    assert got.expires_at == "2027-06-16T00:00:00+00:00" and got.account_label == "Pro plan"


def test_add_oauth_credential_rejects_api_key_mode(store):
    with pytest.raises(ValueError):
        store.add_oauth_credential(provider="openai", auth_mode="api_key", alias="x")
    # legacy aliases normalize then are accepted as OAuth
    c = store.add_oauth_credential(provider="anthropic", auth_mode="setup_token", alias="s")
    assert store.get(f"local:{c.id}").auth_type == "claude_code_oauth"


def test_add_oauth_credential_rejects_cross_provider(store):
    # provider-specific matrix (matches the factory): a provider's wrong OAuth mode
    # must not create an invalid row the factory would later reject.
    with pytest.raises(ValueError):
        store.add_oauth_credential(provider="openai", auth_mode="claude_code_oauth", alias="x")
    with pytest.raises(ValueError):
        store.add_oauth_credential(provider="anthropic", auth_mode="chatgpt_oauth", alias="x")
    # the correct pairings work
    assert store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="o").auth_type == "chatgpt_oauth"
    assert store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="a").auth_type == "claude_code_oauth"


def test_update_secret_rejected_on_oauth_row(store):
    # an OAuth row's token lives in the token-store; update() must NOT let a secret
    # be written into the OAuth credential row.
    oc = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="c")
    with pytest.raises(ValueError):
        store.update(f"local:{oc.id}", secret="tok-injected-1234")
    assert store.get(f"local:{oc.id}").secret is None  # still NULL
    # non-secret updates (alias/active) on an OAuth row are fine
    upd = store.update(f"local:{oc.id}", alias="renamed")
    assert upd.alias == "renamed" and upd.secret is None
    # api_key rows can still update their secret
    k = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-aaaaaaaaaa11")
    assert store.update(f"local:{k.id}", secret="sk-bbbbbbbbbb22").secret == "sk-bbbbbbbbbb22"


def test_provider_credentials_oauth_local_row_no_secret_no_crash(store, clean_env):
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude")
    inv = provider_credentials(store)
    row = next(c for c in inv["anthropic"] if c.id.startswith("local:") and c.auth_type == "claude_code_oauth")
    assert row.masked is None  # no secret to mask
    assert row.can_discover_models is False and row.editable is True


def test_secret_nullable_migration_preserves_existing_rows(tmp_path):
    import sqlite3

    from src.model_credentials import CredentialStore

    p = tmp_path / "profile_state.db"
    # an OLD-schema db: secret NOT NULL, with an existing api_key row
    c = sqlite3.connect(str(p))
    c.executescript(
        "CREATE TABLE llm_credentials (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, "
        "auth_type TEXT NOT NULL DEFAULT 'api_key', alias TEXT NOT NULL, secret TEXT NOT NULL, "
        "active INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
        "INSERT INTO llm_credentials (provider,auth_type,alias,secret,active,created_at,updated_at) "
        "VALUES ('openai','api_key','old','sk-existing',1,'t','t');"
    )
    c.commit(); c.close()
    store = CredentialStore(p)  # construction triggers the secret-nullable rebuild
    rows = store.list()
    assert len(rows) == 1 and rows[0].alias == "old" and rows[0].secret == "sk-existing" and rows[0].active is True
    # and a NULL-secret OAuth row now inserts without a NOT NULL violation
    oc = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="c")
    assert store.get(f"local:{oc.id}").secret is None
