"""Discovery cache tests (P2.7 Task 3): per-credential entitlement observations."""

from src.model_discovery_cache import ModelDiscoveryCache

_SCOPE = dict(provider="openai", auth_mode="api_key", credential_id="c1")


def _mk(tmp_path):
    return ModelDiscoveryCache(tmp_path / "profile_state.db")


def test_successful_run_replaces_scope_rows_and_metadata(tmp_path):
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-1", status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    cache.record_run(**_SCOPE, secret_fingerprint="fp-1", status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-1")
    assert scope.status == "ok" and scope.discovered_at is not None
    assert [m.model_id for m in scope.models] == ["gpt-5.6-luna"]


def test_zero_model_success_is_not_never_discovered(tmp_path):
    # round-2 MF4: a live listing that returns an empty set must still read back
    # as a completed run, not as "never discovered".
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-1", status="ok", models=[])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-1")
    assert scope.status == "ok" and scope.models == [] and scope.discovered_at


def test_fingerprint_mismatch_reads_never_discovered(tmp_path):
    # round-2 MF4: same credential id, replaced secret → previous entitlement
    # must not be served.
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-old", status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-new")
    assert scope.status == "never_discovered" and scope.models == []
    # a new successful run under the new fingerprint supersedes the stale rows
    cache.record_run(**_SCOPE, secret_fingerprint="fp-new", status="ok",
                     models=[{"id": "gpt-5.6-sol", "label": "Sol", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-new")
    assert [m.model_id for m in scope.models] == ["gpt-5.6-sol"]


def test_seed_only_channel_records_seed_only_state(tmp_path):
    # claude_code_oauth has no live listing; the run is stored as seed_only with
    # no model rows — the UI shows seed candidates with a badge, no nudge loop.
    cache = _mk(tmp_path)
    cache.record_run(provider="anthropic", auth_mode="claude_code_oauth",
                     credential_id="oauth-1", secret_fingerprint="oauth",
                     status="seed_only", models=[])
    scope = cache.get(provider="anthropic", auth_mode="claude_code_oauth",
                      credential_id="oauth-1", secret_fingerprint="oauth")
    assert scope.status == "seed_only"


def test_unknown_scope_reads_never_discovered(tmp_path):
    cache = _mk(tmp_path)
    scope = cache.get(provider="anthropic", auth_mode="api_key",
                      credential_id="x", secret_fingerprint="fp")
    assert scope.status == "never_discovered" and scope.models == []


def test_schema_has_no_secret_columns(tmp_path):
    cache = _mk(tmp_path)
    with cache._connect() as conn:
        for table in ("model_discovery_runs", "model_discovery_models"):
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            assert not (cols & {"secret", "api_key", "token"}), table


# --- delete_scope (S3 credential-lifecycle hotfix) ------------------------------
def test_delete_scope_removes_runs_and_models_scoped(tmp_path):
    cache = _mk(tmp_path)
    cache.record_run(provider="openai", auth_mode="chatgpt_oauth", credential_id="local:7",
                     secret_fingerprint="oauth", status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"}])
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="local:3",
                     secret_fingerprint="fp-3", status="ok",
                     models=[{"id": "gpt-5.6-sol", "label": "Sol", "source": "provider_api"}])
    removed = cache.delete_scope(provider="openai", credential_id="local:7",
                                 auth_mode="chatgpt_oauth")
    assert removed == 2  # 1 run row + 1 model row
    gone = cache.get(provider="openai", auth_mode="chatgpt_oauth",
                     credential_id="local:7", secret_fingerprint="oauth")
    assert gone.status == "never_discovered" and gone.models == []
    kept = cache.get(provider="openai", auth_mode="api_key",
                     credential_id="local:3", secret_fingerprint="fp-3")
    assert kept.status == "ok" and [m.model_id for m in kept.models] == ["gpt-5.6-sol"]


def test_delete_scope_all_auth_modes_and_idempotent(tmp_path):
    # auth_mode=None wipes EVERY mode for that credential (the delete-route
    # cascade); a second call removes nothing and returns 0.
    cache = _mk(tmp_path)
    cache.record_run(provider="openai", auth_mode="chatgpt_oauth", credential_id="local:7",
                     secret_fingerprint="oauth", status="seed_only", models=[])
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="local:7",
                     secret_fingerprint="fp-x", status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"},
                             {"id": "gpt-5.6-terra", "label": "Terra", "source": "provider_api"}])
    removed = cache.delete_scope(provider="openai", credential_id="local:7")
    assert removed == 4  # 2 run rows + 2 model rows
    assert cache.delete_scope(provider="openai", credential_id="local:7") == 0
    for mode, fp in (("chatgpt_oauth", "oauth"), ("api_key", "fp-x")):
        scope = cache.get(provider="openai", auth_mode=mode,
                          credential_id="local:7", secret_fingerprint=fp)
        assert scope.status == "never_discovered", mode
