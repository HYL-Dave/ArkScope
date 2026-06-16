"""C3b — import api_key credentials from a .env-style env mapping into named DB
rows. Single-pass dedup by exact secret, source-aware aliases, ≤1 active set per
provider (only if none already active), additive + idempotent. Hermetic: a FAKE
env dict is passed (never os.environ), FAKE keys only, CredentialStore on tmp_path.
"""

from __future__ import annotations

import pytest

from src.model_credentials import CredentialStore, import_env_credentials


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


def _openai(store):
    return [c for c in store.list() if c.provider == "openai"]


def test_import_explodes_pool_into_named_rows(store):
    env = {"OPENAI_API_KEYS": "sk-aaa111,sk-bbb222,sk-ccc333"}
    import_env_credentials(store, env=env)
    rows = _openai(store)
    assert len(rows) == 3
    assert all(r.auth_type == "api_key" for r in rows)  # never stored as pool
    secrets = {r.secret for r in rows}
    assert secrets == {"sk-aaa111", "sk-bbb222", "sk-ccc333"}
    # source-aware, non-positional aliases
    assert all(r.alias and "[" not in r.alias for r in rows)


def test_import_dedups_duplicate_secret(store):
    # the verified real case: OPENAI_API_KEYS re-lists the single OPENAI_API_KEY
    env = {"OPENAI_API_KEY": "sk-dup999", "OPENAI_API_KEYS": "sk-distinct1,sk-dup999"}
    import_env_credentials(store, env=env)
    rows = _openai(store)
    assert len(rows) == 2  # collapses to 2 distinct rows, NOT 3
    assert {r.secret for r in rows} == {"sk-dup999", "sk-distinct1"}
    # the single-var alias wins the collision (processed first)
    dup = next(r for r in rows if r.secret == "sk-dup999")
    assert dup.alias == "OpenAI primary"


def test_import_sets_one_active_when_none_exists(store):
    env = {"OPENAI_API_KEY": "sk-x111", "OPENAI_API_KEYS": "sk-y222,sk-z333"}
    import_env_credentials(store, env=env)
    active = [r for r in _openai(store) if r.active]
    assert len(active) == 1  # exactly one active per provider
    assert active[0].secret == "sk-x111"  # the first-added (primary) row


def test_import_respects_existing_active(store):
    store.add(provider="openai", auth_type="api_key", alias="mine", secret="sk-existing0", make_active=True)
    import_env_credentials(store, env={"OPENAI_API_KEYS": "sk-new111,sk-new222"})
    active = [r for r in _openai(store) if r.active]
    assert len(active) == 1 and active[0].secret == "sk-existing0"  # import did not steal active


def test_import_is_idempotent(store):
    env = {"OPENAI_API_KEY": "sk-i111", "OPENAI_API_KEYS": "sk-i222,sk-i111"}
    import_env_credentials(store, env=env)
    n1 = len(_openai(store))
    res2 = import_env_credentials(store, env=env)  # re-import unchanged env
    assert len(_openai(store)) == n1  # no new rows
    assert res2["openai"]["added"] == [] and res2["openai"]["skipped"] == n1


def test_import_empty_or_missing_is_noop(store):
    res = import_env_credentials(store, env={"OPENAI_API_KEYS": " , ,"})  # blanks only
    assert _openai(store) == []
    assert res["openai"]["added"] == []
    import_env_credentials(store, env={})  # nothing at all → no error
    assert store.list() == []


def test_import_drops_blank_pool_entries(store):
    import_env_credentials(store, env={"OPENAI_API_KEYS": "sk-a111,,sk-b222,"})
    rows = _openai(store)
    assert {r.secret for r in rows} == {"sk-a111", "sk-b222"}  # no empty-secret rows


def test_import_handles_both_providers(store):
    env = {"OPENAI_API_KEY": "sk-oa1", "ANTHROPIC_API_KEY": "sk-ant-1"}
    res = import_env_credentials(store, env=env)
    provs = {c.provider for c in store.list()}
    assert provs == {"openai", "anthropic"}
    assert res["openai"]["activated"] and res["anthropic"]["activated"]


def test_import_unquotes_whole_pool(store):
    # WHOLE-VALUE quoting (the form .env.template documents as correct:
    # OPENAI_API_KEYS="sk-a,sk-b") must unwrap the outer quotes BEFORE the comma
    # split, so the commas inside are seen and the secrets carry no boundary
    # quote. (Per-entry quoting "a","b" is invalid dotenv and is not supported.)
    import_env_credentials(store, env={"OPENAI_API_KEYS": '"sk-q111,sk-q222"'})
    assert {r.secret for r in _openai(store)} == {"sk-q111", "sk-q222"}


def test_import_whole_quoted_pool_dedups_against_single(store):
    # gpt-5.5's exact regression: single=sk-a, pool='"sk-a,sk-b"' → 2 rows, no
    # boundary quotes, the unquoted single's "OpenAI primary" wins the collision.
    import_env_credentials(store, env={"OPENAI_API_KEY": "sk-a", "OPENAI_API_KEYS": '"sk-a,sk-b"'})
    rows = _openai(store)
    assert len(rows) == 2
    assert {r.secret for r in rows} == {"sk-a", "sk-b"}  # not {'"sk-a', 'sk-b"', 'sk-a'}
    primary = next(r for r in rows if r.secret == "sk-a")
    assert primary.alias == "OpenAI primary"


def test_import_single_quoted_pool_dedups_against_single(store):
    # a single-entry whole-quoted pool that equals the single var dedups to 1
    import_env_credentials(store, env={"OPENAI_API_KEY": "sk-same1", "OPENAI_API_KEYS": '"sk-same1"'})
    rows = _openai(store)
    assert len(rows) == 1 and rows[0].secret == "sk-same1" and rows[0].alias == "OpenAI primary"


def test_import_drops_pool_entries_that_unquote_to_empty(store):
    import_env_credentials(store, env={"OPENAI_API_KEYS": '"",sk-real1'})
    assert {r.secret for r in _openai(store)} == {"sk-real1"}  # the "" entry produced no row


def test_import_does_not_steal_active_from_oauth_row(store):
    # a working OAuth credential (e.g. a Claude setup-token) the user set active
    # must NOT be silently deactivated by an api_key import — switching is an
    # explicit user action in Settings, never an import side effect.
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude", make_active=True)
    res = import_env_credentials(store, env={"ANTHROPIC_API_KEY": "sk-ant-new1"})
    active = [c for c in store.list() if c.provider == "anthropic" and c.active]
    assert len(active) == 1 and active[0].auth_type == "claude_code_oauth"  # OAuth stays active
    assert res["anthropic"]["activated"] is None  # import added the key but did not activate it


def test_import_summary_carries_no_secret(store):
    env = {"OPENAI_API_KEY": "sk-secretval123", "OPENAI_API_KEYS": "sk-poolsecret456"}
    res = import_env_credentials(store, env=env)
    blob = repr(res)
    assert "sk-secretval123" not in blob and "sk-poolsecret456" not in blob  # only labels/counts
