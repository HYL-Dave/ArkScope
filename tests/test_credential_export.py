"""C4b/C4c — export api_key credentials to a .env block and round-trip them.

Interop format (user-chosen): the ACTIVE api_key per provider → bare
OPENAI_API_KEY / ANTHROPIC_API_KEY (a vanilla SDK / the scorer still work);
extra keys → ARKSCOPE_<PROVIDER>_KEY__<alias_slug>. OAuth credentials are
machine-local (token-store) and are NEVER exported — only a commented stub.
Aliases ride on their OWN comment line (never inline, since the loader does not
strip inline # comments and would fold them into the secret). FAKE keys only.
"""

from __future__ import annotations

import pytest

import os
import stat

from src.auth_drivers import PlaintextTokenStore
from src.auth_drivers.token_store import StoredTokenRecord
from src.env_keys import unquote_env_value
from src.model_credentials import (
    CredentialStore,
    export_env_credentials,
    import_env_credentials,
    write_env_export,
)


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


def _parse_env(text: str) -> dict[str, str]:
    # mimic the PRODUCTION loader (src.env_keys.ensure_env_loaded): skip
    # blank/comment lines, partition on first '=', then unquote_env_value — NOT a
    # weaker v.strip(), so the round-trip is asserted the way it actually loads.
    env: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("=")
            env[k.strip()] = unquote_env_value(v)
    return env


def test_export_writes_active_key_to_bare_var(store):
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-active111", make_active=True)
    text = export_env_credentials(store)
    assert "OPENAI_API_KEY=sk-active111" in text
    assert "ARKSCOPE_OPENAI_KEY__" not in text  # the only key is the bare active one


def test_export_extra_keys_under_arkscope_names(store):
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-active111", make_active=True)
    store.add(provider="openai", auth_type="api_key", alias="scoring free tier", secret="sk-extra222", make_active=False)
    text = export_env_credentials(store)
    assert "OPENAI_API_KEY=sk-active111" in text
    assert "ARKSCOPE_OPENAI_KEY__scoring_free_tier=sk-extra222" in text


def test_export_secret_lines_have_no_inline_comment(store):
    # the loader does NOT strip inline # comments → a KEY=value line must carry no
    # trailing comment, or the secret would be corrupted on re-import.
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-active111", make_active=True)
    env = _parse_env(export_env_credentials(store))
    assert env["OPENAI_API_KEY"] == "sk-active111"  # exactly the secret, nothing appended


def test_export_excludes_oauth_token(store, tmp_path):
    # OAuth row has secret=NULL in the DB; its token lives in a SEPARATE
    # token-store. export takes only the store → it CANNOT reach the token.
    c = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude", make_active=True)
    tok = PlaintextTokenStore(tmp_path / "tok.json")
    tok.save(provider="anthropic", auth_mode="claude_code_oauth", credential_id=f"local:{c.id}",
             record=StoredTokenRecord(access_token="setup-tok-SECRET-zzz"))
    text = export_env_credentials(store)
    assert "setup-tok-SECRET-zzz" not in text  # token never exported
    assert "ANTHROPIC_API_KEY" not in text  # OAuth is not written as a key
    assert "my claude" in text and "not exported" in text  # only a commented stub


def test_export_never_emits_an_oauth_rows_secret(store):
    # defense-in-depth: even a LEGACY OAuth row with an (illegally) non-NULL
    # secret column must never be promoted to a key var — export filters api_key
    # rows by `and r.secret` and OAuth rows by auth_type only (comment stub).
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO llm_credentials "
            "(provider, auth_type, alias, secret, active, created_at, updated_at) "
            "VALUES (?,?,?,?,0,?,?)",
            ("anthropic", "claude_code_oauth", "legacy oauth", "tok-LEAK-should-not-appear", "t", "t"),
        )
        conn.commit()
    text = export_env_credentials(store)
    assert "tok-LEAK-should-not-appear" not in text  # OAuth secret never exported as a key
    assert "ANTHROPIC_API_KEY" not in text


def test_export_skips_legacy_api_key_pool_row(store):
    # a crafted LEGACY local api_key_pool row must NOT be exported as a key
    # (stored pool rows are retired/unresolvable; only auth_type=api_key exports).
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO llm_credentials "
            "(provider, auth_type, alias, secret, active, created_at, updated_at) "
            "VALUES (?,?,?,?,1,?,?)",
            ("openai", "api_key_pool", "legacy pool", "sk-legacypool999", "t", "t"),
        )
        conn.commit()
    text = export_env_credentials(store)
    assert "sk-legacypool999" not in text  # legacy pool secret never exported as a key
    assert "OPENAI_API_KEY=" not in text


def test_write_env_export_is_0600_and_contains_keys(store, tmp_path):
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-active111", make_active=True)
    path = tmp_path / "creds_export.env"
    summary = write_env_export(str(path), store=store)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600  # owner-only (it holds real secrets)
    assert "OPENAI_API_KEY=sk-active111" in path.read_text()  # file has the secret — that's its purpose
    # the returned SUMMARY is counts/labels only — never a secret
    assert summary["key_count"] == 1 and "OPENAI_API_KEY" in summary["vars"]
    assert "sk-active111" not in repr(summary)


def test_write_env_export_tightens_existing_world_readable_file(store, tmp_path):
    path = tmp_path / "pre.env"
    path.write_text("stale")
    os.chmod(path, 0o644)  # pre-existing, group/world readable
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-x111", make_active=True)
    write_env_export(str(path), store=store)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600  # tightened


def test_write_env_export_summary_never_carries_a_token(store, tmp_path):
    c = store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude", make_active=True)
    tok = PlaintextTokenStore(tmp_path / "tok.json")
    tok.save(provider="anthropic", auth_mode="claude_code_oauth", credential_id=f"local:{c.id}",
             record=StoredTokenRecord(access_token="tok-SECRET-zzz"))
    summary = write_env_export(str(tmp_path / "x.env"), store=store)
    assert "tok-SECRET-zzz" not in repr(summary)
    assert "tok-SECRET-zzz" not in (tmp_path / "x.env").read_text()


def test_export_roundtrips_secrets_and_active(store, tmp_path):
    store.add(provider="openai", auth_type="api_key", alias="OpenAI primary", secret="sk-active111", make_active=True)
    store.add(provider="openai", auth_type="api_key", alias="scoring", secret="sk-extra222", make_active=False)
    store.add(provider="anthropic", auth_type="api_key", alias="A primary", secret="sk-ant-aaa111", make_active=True)
    env = _parse_env(export_env_credentials(store))

    store2 = CredentialStore(tmp_path / "p2.db")
    import_env_credentials(store2, env=env)
    got = {(r.provider, r.secret): r.active for r in store2.list()}
    assert len(got) == 3  # every secret preserved, no dups
    assert got[("openai", "sk-active111")] is True   # the active (bare-var) key round-trips active
    assert got[("openai", "sk-extra222")] is False
    assert got[("anthropic", "sk-ant-aaa111")] is True
