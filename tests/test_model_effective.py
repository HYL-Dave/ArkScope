"""Effective picker tests (P2.7 Task 4): per-task verified/advanced partition."""

import hashlib

from src.model_discovery_cache import ModelDiscoveryCache
from src.model_effective import (
    ActiveCredential,
    effective_model_view,
    task_auth_executable,
)
from src.model_capabilities import capability_for
from src.model_routing import TaskRoute


def _fp(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:16]


def test_task_auth_executable_matrix():
    opus = capability_for("claude-opus-4-8")
    gpt = capability_for("gpt-5.5")
    # card tasks: sync clients → api_key ONLY (pool unwired, oauth fail-closed)
    assert task_auth_executable("card_synthesis", "anthropic", "api_key", opus) is True
    assert task_auth_executable("card_synthesis", "anthropic", "api_key_pool", opus) is False
    assert task_auth_executable("card_synthesis", "anthropic", "claude_code_oauth", opus) is False
    assert task_auth_executable("card_translation", "openai", "chatgpt_oauth", gpt) is False
    # ai_research: oauth on own provider OK; pool still False (unwired)
    assert task_auth_executable("ai_research", "anthropic", "claude_code_oauth", opus) is True
    assert task_auth_executable("ai_research", "openai", "chatgpt_oauth", gpt) is True
    assert task_auth_executable("ai_research", "openai", "api_key", gpt) is True
    assert task_auth_executable("ai_research", "openai", "api_key_pool", gpt) is False
    # mixed / unknown fail closed
    assert task_auth_executable("ai_research", "openai", "claude_code_oauth", gpt) is False
    assert task_auth_executable("card_synthesis", "anthropic", None, opus) is False
    assert task_auth_executable("card_synthesis", "openai", "api_key", opus) is False


def _routes_mixed() -> dict:
    # Round-3 MF1: the DEFAULT config shape — anthropic cards + openai research.
    return {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="anthropic",
                                    model="claude-opus-4-8", effort="default"),
        "card_translation": TaskRoute(task="card_translation", provider="anthropic",
                                      model="claude-sonnet-4-6", effort="default"),
        "ai_research": TaskRoute(task="ai_research", provider="openai",
                                 model="mystery-model", effort="default"),
    }


def _credentials():
    return {
        "anthropic": ActiveCredential(provider="anthropic", credential_id="a1",
                                      auth_mode="api_key",
                                      secret_fingerprint=_fp("sk-ant")),
        "openai": ActiveCredential(provider="openai", credential_id="o1",
                                   auth_mode="chatgpt_oauth",
                                   secret_fingerprint="oauth"),
    }


def _seed_cache(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="anthropic", auth_mode="api_key", credential_id="a1",
                     secret_fingerprint=_fp("sk-ant"), status="ok",
                     models=[{"id": "claude-opus-4-8", "label": "Opus 4.8", "source": "provider_api"},
                             {"id": "claude-opus-4-7", "label": "Opus 4.7", "source": "provider_api"}])
    cache.record_run(provider="openai", auth_mode="chatgpt_oauth", credential_id="o1",
                     secret_fingerprint="oauth", status="ok",
                     models=[{"id": "gpt-5.4-mini", "label": "mini", "source": "provider_api"},
                             {"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    return cache


def test_effective_view_handles_mixed_providers_per_task(tmp_path):
    view = effective_model_view(cache=_seed_cache(tmp_path), routes=_routes_mixed(),
                                credentials=_credentials())
    # anthropic api_key cards: opus-4.8 verified (visible+default+executable);
    # opus-4.7 visible but advanced-visibility → advanced
    synth = view["tasks"]["card_synthesis"]
    assert [m["id"] for m in synth["verified"]] == ["claude-opus-4-8"]
    assert any(m["id"] == "claude-opus-4-7" and m["badge"] == "advanced"
               for m in synth["advanced"])
    assert synth["cache_state"] == "ok" and synth["discovered_at"]
    # card_translation pins sonnet-4.6 (advanced visibility) → appears in advanced
    trans = view["tasks"]["card_translation"]
    assert any(m["id"] == "claude-sonnet-4-6" for m in trans["advanced"])
    # openai research under chatgpt_oauth: mini verified; gpt-5.5 pinned_only →
    # NOT shown despite visibility (round-4 MF1); mystery-model = route badge
    research = view["tasks"]["ai_research"]
    assert [m["id"] for m in research["verified"]] == ["gpt-5.4-mini"]
    advanced_ids = {m["id"] for m in research["advanced"]}
    assert "gpt-5.5" not in advanced_ids
    assert "mystery-model" in advanced_ids


def test_pinned_only_model_appears_only_when_route_pins_it(tmp_path):
    routes = _routes_mixed()
    routes["ai_research"] = TaskRoute(task="ai_research", provider="openai",
                                      model="gpt-5.5", effort="default")
    view = effective_model_view(cache=_seed_cache(tmp_path), routes=routes,
                                credentials=_credentials())
    research = view["tasks"]["ai_research"]
    pinned = [m for m in research["advanced"] if m["id"] == "gpt-5.5"]
    assert pinned and pinned[0]["badge"] == "route"
    # and still absent from every task that does NOT pin it
    assert all(m["id"] != "gpt-5.5"
               for m in view["tasks"]["card_synthesis"]["advanced"])


def test_effective_view_anthropic_oauth_research_is_executable_but_seed_only(tmp_path):
    # round-4 MF2: research routed to ANTHROPIC under claude_code_oauth.
    routes = {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="anthropic",
                                    model="claude-opus-4-8", effort="default"),
        "card_translation": TaskRoute(task="card_translation", provider="anthropic",
                                      model="claude-sonnet-4-6", effort="default"),
        "ai_research": TaskRoute(task="ai_research", provider="anthropic",
                                 model="claude-opus-4-8", effort="default"),
    }
    creds = {
        "anthropic": ActiveCredential(provider="anthropic", credential_id="ao",
                                      auth_mode="claude_code_oauth",
                                      secret_fingerprint="oauth"),
        "openai": None,
    }
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="anthropic", auth_mode="claude_code_oauth",
                     credential_id="ao", secret_fingerprint="oauth",
                     status="seed_only", models=[])
    view = effective_model_view(cache=cache, routes=routes, credentials=creds)
    research = view["tasks"]["ai_research"]
    # executable (oauth research on own provider) BUT nothing verifiable on a
    # seed_only channel:
    assert research["verified"] == []
    assert research["cache_state"] == "seed_only"
    assert any(m["badge"] == "seed" for m in research["advanced"])
    # round-5 SF: pinned_only Claude models must NOT resurface as seed candidates
    seed_ids = {m["id"] for m in research["advanced"]}
    assert not ({"claude-sonnet-4-5", "claude-opus-4-5"} & seed_ids)
    # cards under oauth are not even executable:
    assert view["tasks"]["card_synthesis"]["verified"] == []


def test_effective_view_missing_credential_fails_closed(tmp_path):
    view = effective_model_view(cache=ModelDiscoveryCache(tmp_path / "p.db"),
                                routes=_routes_mixed(),
                                credentials={"anthropic": None, "openai": None})
    for task_block in view["tasks"].values():
        assert task_block["verified"] == []
        assert task_block["cache_state"] == "never_discovered"
        assert all(m["badge"] in ("seed", "advanced", "custom", "route")
                   for m in task_block["advanced"])


def test_resolver_covers_env_only_keys(monkeypatch, tmp_path):
    # round-2 MF3/MF4: env-only active key resolves to a stable synthetic
    # credential id + auth_mode api_key + a fingerprint of the CURRENT secret.
    from src.model_credentials import resolve_active_credential

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-only")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    cred = resolve_active_credential("openai")
    assert cred is not None
    assert cred.auth_mode == "api_key" and cred.credential_id
    assert cred.secret_fingerprint == _fp("sk-env-only")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-rotated")
    assert resolve_active_credential("openai").secret_fingerprint == _fp("sk-rotated")


def test_model_catalog_route_gains_additive_effective_block(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr
    from src.model_credentials import CredentialStore

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setattr(cr, "resolve_active_credential", lambda provider, *a, **kw: None)
    out = cr.model_catalog(store=CredentialStore(tmp_path / "profile_state.db"))
    for key in ("providers", "tasks", "models", "effort_options", "routes"):
        assert key in out
    assert set(out["effective"]["tasks"]) == {
        "card_synthesis", "card_translation", "ai_research",
    }
    block = out["effective"]["tasks"]["ai_research"]
    assert {"verified", "advanced", "cache_state", "discovered_at"} <= set(block)
    assert block["cache_state"] == "never_discovered"   # fail-closed shape
