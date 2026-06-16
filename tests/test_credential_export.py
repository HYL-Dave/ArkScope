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

from src.auth_drivers import PlaintextTokenStore
from src.auth_drivers.token_store import StoredTokenRecord
from src.model_credentials import (
    CredentialStore,
    export_env_credentials,
    import_env_credentials,
)


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


def _parse_env(text: str) -> dict[str, str]:
    # mimic a .env load: skip blank/comment lines, split on first '='
    env: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("=")
            env[k.strip()] = v.strip()
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
