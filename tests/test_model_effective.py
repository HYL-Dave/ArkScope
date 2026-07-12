"""Effective picker tests (P2.7 Task 4): per-task verified/advanced partition."""

import hashlib
from dataclasses import replace

import src.model_effective as model_effective_module
from src.model_discovery_cache import ModelDiscoveryCache
from src.model_effective import (
    ActiveCredential,
    effective_model_view,
    effective_model_view_v2,
    task_auth_executable,
)
from src.model_capabilities import capability_for
from src.model_routing import TaskRoute


def _fp(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:16]


def test_task_auth_executable_matrix():
    opus = capability_for("claude-opus-4-8")
    gpt = capability_for("gpt-5.5")
    # Card tasks use the selected provider's active direct or subscription path.
    assert task_auth_executable("card_synthesis", "anthropic", "api_key", opus) is True
    assert task_auth_executable("card_synthesis", "anthropic", "api_key_pool", opus) is False
    assert task_auth_executable("card_synthesis", "anthropic", "claude_code_oauth", opus) is True
    assert task_auth_executable("card_translation", "openai", "chatgpt_oauth", gpt) is True
    assert task_auth_executable("card_synthesis", "openai", "claude_code_oauth", gpt) is False
    assert task_auth_executable("card_translation", "anthropic", "chatgpt_oauth", opus) is False
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
    # Cards are executable through the Claude subscription adapter, but a
    # seed-only channel still cannot promote any candidate to verified.
    assert view["tasks"]["card_synthesis"]["verified"] == []
    assert any(m["badge"] == "seed" for m in view["tasks"]["card_synthesis"]["advanced"])


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


def test_resolver_pool_identity_and_fingerprint_match_discovery(monkeypatch, tmp_path):
    # Review round-2 MF1: the pool scope must be built from the SAME
    # (_resolve_api_credential) identity that discovery writes with — real
    # auth_mode api_key_pool (fail-closed stays) AND the fingerprint of the
    # SELECTED single key, so the cache round-trips.
    from src.model_credentials import (
        _resolve_api_credential,
        resolve_active_credential,
        secret_fingerprint,
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEYS", "sk-pool-a,sk-pool-b")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))

    cred = resolve_active_credential("openai")
    assert cred is not None                                  # pool DOES resolve
    assert cred.auth_mode == "api_key_pool"                  # never masquerades
    resolved = _resolve_api_credential("openai", cred.credential_id)
    assert cred.secret_fingerprint == secret_fingerprint(resolved.secret)

    # discovery write → cache read-back under the resolver's scope
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode=cred.auth_mode,
                     credential_id=cred.credential_id,
                     secret_fingerprint=cred.secret_fingerprint,
                     status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"}])
    scope = cache.get(provider="openai", auth_mode=cred.auth_mode,
                      credential_id=cred.credential_id,
                      secret_fingerprint=cred.secret_fingerprint)
    assert scope.status == "ok"
    assert [m.model_id for m in scope.models] == ["gpt-5.6-luna"]


def test_dated_discovery_ids_resolve_to_registry_capability(tmp_path):
    # Review MF4: providers return DATED ids (claude-haiku-4-5-20251001); exact
    # canonical comparison missed them from verified, while capability_for
    # recognizing them kept them out of custom — they vanished entirely. The
    # view must classify via capability_for(discovered_id) and keep the
    # provider's REAL executable id in the option.
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="anthropic", auth_mode="api_key", credential_id="a1",
                     secret_fingerprint=_fp("sk-ant"), status="ok",
                     models=[{"id": "claude-haiku-4-5-20251001", "label": "Haiku 4.5",
                              "source": "provider_api"}])
    creds = {
        "anthropic": ActiveCredential(provider="anthropic", credential_id="a1",
                                      auth_mode="api_key",
                                      secret_fingerprint=_fp("sk-ant")),
        "openai": None,
    }
    view = effective_model_view(cache=cache, routes=_routes_mixed(), credentials=creds)
    synth = view["tasks"]["card_synthesis"]
    verified_ids = [m["id"] for m in synth["verified"]]
    assert "claude-haiku-4-5-20251001" in verified_ids   # real executable id kept
    all_ids = verified_ids + [m["id"] for m in synth["advanced"]]
    assert "claude-haiku-4-5-20251001" in all_ids        # never vanishes


def test_unknown_discovery_ids_do_not_flood_advanced(tmp_path):
    # Review MF5: an OpenAI key lists ~129 models (voice/embeddings/images) the
    # app cannot execute; registry-unknown ids must NOT auto-enter advanced —
    # unknown ids are for the explicit custom input; only a route pin survives.
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="o1",
                     secret_fingerprint=_fp("sk-oai"), status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"},
                             {"id": "whisper-1", "label": "whisper", "source": "provider_api"},
                             {"id": "text-embedding-3-large", "label": "emb", "source": "provider_api"},
                             {"id": "mystery-model", "label": "?", "source": "provider_api"}])
    routes = _routes_mixed()  # ai_research pins mystery-model
    creds = {
        "anthropic": None,
        "openai": ActiveCredential(provider="openai", credential_id="o1",
                                   auth_mode="api_key",
                                   secret_fingerprint=_fp("sk-oai")),
    }
    view = effective_model_view(cache=cache, routes=routes, credentials=creds)
    research = view["tasks"]["ai_research"]
    advanced_ids = {m["id"] for m in research["advanced"]}
    assert "whisper-1" not in advanced_ids               # unknown, unpinned → absent
    assert "text-embedding-3-large" not in advanced_ids
    assert "mystery-model" in advanced_ids               # route pin survives (badge route)
    assert [m["id"] for m in research["verified"]] == ["gpt-5.6-luna"]


def test_v2_both_providers_present_regardless_of_route(tmp_path):
    routes = {
        task: TaskRoute(task=task, provider="openai", model="gpt-5.4-mini", effort="default")
        for task in ("card_synthesis", "card_translation", "ai_research")
    }
    view = effective_model_view_v2(
        cache=_seed_cache(tmp_path),
        routes=routes,
        credentials=_credentials(),
    )

    assert set(view["providers"]) == {"openai", "anthropic"}
    for task in routes:
        assert view["tasks"][task]["current_provider"] == "openai"
        assert set(view["tasks"][task]["providers"]) == {"openai", "anthropic"}
        assert view["tasks"][task]["providers"]["anthropic"]["models"]


def test_v2_entry_schema_and_grouping(tmp_path):
    view = effective_model_view_v2(
        cache=_seed_cache(tmp_path), routes=_routes_mixed(), credentials=_credentials(),
    )
    synth = view["tasks"]["card_synthesis"]["providers"]["anthropic"]
    entries = {entry["id"]: entry for entry in synth["models"]}

    assert entries["claude-opus-4-8"]["status"] == "visible"
    assert entries["claude-opus-4-8"]["visible_to_credential"] is True
    assert entries["claude-opus-4-7"]["status"] == "advanced"
    assert entries["claude-opus-4-7"]["visible_to_credential"] is True
    assert not ({"claude-opus-4-5", "claude-sonnet-4-5"} & entries.keys())
    for entry in entries.values():
        assert set(entry) == {
            "id", "label", "status", "visible_to_credential",
            "eligible", "reason_code", "thinking_mode", "effort_options",
        }

    research = view["tasks"]["ai_research"]["providers"]["openai"]
    research_entries = {entry["id"]: entry for entry in research["models"]}
    assert research_entries["mystery-model"]["status"] == "route"
    assert all(entry["id"] not in {"whisper-1", "text-embedding-3-large"}
               for entry in research["models"])


def test_v2_eligibility_split_provider_vs_model(tmp_path, monkeypatch):
    base = capability_for("gpt-5.4-mini")
    no_structured = replace(
        base,
        id="gpt-no-structured",
        label="GPT no structured",
        supports_structured_output=False,
    )
    original_all = model_effective_module.all_models
    original_capability = model_effective_module.capability_for
    monkeypatch.setattr(
        model_effective_module,
        "all_models",
        lambda provider=None: (
            original_all(provider) + ((no_structured,) if provider in (None, "openai") else ())
        ),
    )
    monkeypatch.setattr(
        model_effective_module,
        "capability_for",
        lambda model_id: no_structured if model_id == no_structured.id else original_capability(model_id),
    )

    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(
        provider="openai", auth_mode="api_key", credential_id="o1",
        secret_fingerprint=_fp("sk-oai"), status="ok",
        models=[{"id": no_structured.id, "label": no_structured.label, "source": "provider_api"}],
    )
    creds = {
        "openai": ActiveCredential("openai", "o1", "api_key", _fp("sk-oai")),
        "anthropic": ActiveCredential("anthropic", "ao", "claude_code_oauth", "oauth"),
    }
    routes = {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="openai", model=no_structured.id),
        "card_translation": TaskRoute(task="card_translation", provider="anthropic", model="claude-sonnet-5"),
        "ai_research": TaskRoute(task="ai_research", provider="openai", model="gpt-5.4-mini"),
    }
    view = effective_model_view_v2(cache=cache, routes=routes, credentials=creds)

    openai_card = view["tasks"]["card_synthesis"]["providers"]["openai"]
    missing_cap = next(entry for entry in openai_card["models"] if entry["id"] == no_structured.id)
    assert openai_card["executable"] is True
    assert missing_cap["eligible"] is False
    assert missing_cap["reason_code"] == "task_capability_missing"

    anthropic_card = view["tasks"]["card_translation"]["providers"]["anthropic"]
    assert anthropic_card["executable"] is True
    assert anthropic_card["reason_code"] is None
    assert anthropic_card["models"]
    assert all(entry["eligible"] is True for entry in anthropic_card["models"])


def test_v2_route_pin_unknown_model_is_eligible_with_warning(tmp_path):
    routes = _routes_mixed()
    view = effective_model_view_v2(
        cache=_seed_cache(tmp_path), routes=routes, credentials=_credentials(),
    )
    openai = view["tasks"]["ai_research"]["providers"]["openai"]
    route = next(entry for entry in openai["models"] if entry["id"] == "mystery-model")
    assert route["status"] == "route"
    assert route["eligible"] is True
    assert route["reason_code"] == "model_not_in_registry"
    assert route["thinking_mode"] == "none"
    assert all(entry["id"] != "mystery-model"
               for entry in view["tasks"]["ai_research"]["providers"]["anthropic"]["models"])

    missing = effective_model_view_v2(
        cache=ModelDiscoveryCache(tmp_path / "missing.db"),
        routes=routes,
        credentials={"openai": None, "anthropic": None},
    )
    missing_route = next(
        entry for entry in missing["tasks"]["ai_research"]["providers"]["openai"]["models"]
        if entry["id"] == "mystery-model"
    )
    assert missing_route["eligible"] is False
    assert missing_route["reason_code"] == "missing_active_credential"


def test_v2_missing_credential_provider_reason(tmp_path):
    view = effective_model_view_v2(
        cache=ModelDiscoveryCache(tmp_path / "profile.db"),
        routes=_routes_mixed(),
        credentials={"openai": None, "anthropic": None},
    )
    assert view["providers"] == {"openai": None, "anthropic": None}
    for task in view["tasks"].values():
        for block in task["providers"].values():
            assert block["executable"] is False
            assert block["reason_code"] == "missing_active_credential"
            assert block["cache_state"] == "never_discovered"
            assert block["models"]
            assert all(entry["eligible"] is False for entry in block["models"])


def test_v2_thinking_mode_carried_from_registry(tmp_path):
    view = effective_model_view_v2(
        cache=ModelDiscoveryCache(tmp_path / "profile.db"),
        routes=_routes_mixed(),
        credentials={"openai": None, "anthropic": None},
    )
    entries = {}
    for block in view["tasks"]["ai_research"]["providers"].values():
        entries.update({entry["id"]: entry for entry in block["models"]})
    assert entries["claude-fable-5"]["thinking_mode"] == "adaptive_always_on"
    assert entries["claude-sonnet-5"]["thinking_mode"] == "adaptive_default_on"
    assert entries["claude-opus-4-8"]["thinking_mode"] == "adaptive_opt_in"
    assert entries["claude-haiku-4-5"]["thinking_mode"] == "manual_budget"
    assert entries["gpt-5.4-mini"]["thinking_mode"] == "none"
    assert entries["mystery-model"]["thinking_mode"] == "none"


def test_v2_effort_options_are_model_specific(tmp_path):
    view = effective_model_view_v2(
        cache=ModelDiscoveryCache(tmp_path / "profile.db"),
        routes=_routes_mixed(),
        credentials={"openai": None, "anthropic": None},
    )
    entries = {}
    for block in view["tasks"]["ai_research"]["providers"].values():
        entries.update({entry["id"]: entry for entry in block["models"]})
    assert entries["gpt-5.6-luna"]["effort_options"] == [
        "none", "low", "medium", "high", "xhigh", "max",
    ]
    assert entries["gpt-5.4-mini"]["effort_options"] == [
        "none", "low", "medium", "high", "xhigh",
    ]
    assert entries["mystery-model"]["effort_options"] == []


def test_v2_visibility_is_orthogonal_to_tier(tmp_path):
    view = effective_model_view_v2(
        cache=_seed_cache(tmp_path), routes=_routes_mixed(), credentials=_credentials(),
    )
    entries = {
        entry["id"]: entry
        for entry in view["tasks"]["card_synthesis"]["providers"]["anthropic"]["models"]
    }
    assert entries["claude-opus-4-7"]["status"] == "advanced"
    assert entries["claude-opus-4-7"]["visible_to_credential"] is True
    assert entries["claude-sonnet-4-6"]["status"] == "advanced"
    assert entries["claude-sonnet-4-6"]["visible_to_credential"] is False

    seed_cache = ModelDiscoveryCache(tmp_path / "seed.db")
    seed_cache.record_run(
        provider="anthropic", auth_mode="claude_code_oauth", credential_id="ao",
        secret_fingerprint="oauth", status="seed_only", models=[],
    )
    seed_view = effective_model_view_v2(
        cache=seed_cache,
        routes=_routes_mixed(),
        credentials={
            "anthropic": ActiveCredential("anthropic", "ao", "claude_code_oauth", "oauth"),
            "openai": None,
        },
    )
    seed_entries = seed_view["tasks"]["ai_research"]["providers"]["anthropic"]["models"]
    assert all(entry["visible_to_credential"] is None for entry in seed_entries)


def test_v2_discovered_ineligible_default_stays_out_of_alias(tmp_path, monkeypatch):
    base = capability_for("gpt-5.4-mini")
    no_structured = replace(
        base,
        id="gpt-no-structured",
        label="GPT no structured",
        supports_structured_output=False,
    )
    original_all = model_effective_module.all_models
    original_capability = model_effective_module.capability_for
    monkeypatch.setattr(
        model_effective_module,
        "all_models",
        lambda provider=None: original_all(provider) + ((no_structured,) if provider in (None, "openai") else ()),
    )
    monkeypatch.setattr(
        model_effective_module,
        "capability_for",
        lambda model_id: no_structured if model_id == no_structured.id else original_capability(model_id),
    )
    cache = ModelDiscoveryCache(tmp_path / "profile.db")
    cache.record_run(
        provider="openai", auth_mode="api_key", credential_id="o1",
        secret_fingerprint=_fp("sk-oai"), status="ok",
        models=[{"id": no_structured.id, "label": no_structured.label, "source": "provider_api"}],
    )
    creds = {
        "openai": ActiveCredential("openai", "o1", "api_key", _fp("sk-oai")),
        "anthropic": None,
    }
    routes = {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="openai", model="gpt-5.4-mini"),
        "card_translation": TaskRoute(task="card_translation", provider="openai", model="gpt-5.4-mini"),
        "ai_research": TaskRoute(task="ai_research", provider="openai", model="gpt-5.4-mini"),
    }
    v2 = effective_model_view_v2(cache=cache, routes=routes, credentials=creds)
    v2_entry = next(
        entry for entry in v2["tasks"]["card_synthesis"]["providers"]["openai"]["models"]
        if entry["id"] == no_structured.id
    )
    assert v2_entry["status"] == "visible" and v2_entry["eligible"] is False

    legacy = effective_model_view(cache=cache, routes=routes, credentials=creds)
    legacy_ids = {
        entry["id"]
        for group in (legacy["tasks"]["card_synthesis"]["verified"],
                      legacy["tasks"]["card_synthesis"]["advanced"])
        for entry in group
    }
    assert no_structured.id not in legacy_ids


def test_legacy_alias_is_derived_from_v2(tmp_path):
    cache = _seed_cache(tmp_path)
    routes = _routes_mixed()
    creds = _credentials()
    v2 = effective_model_view_v2(cache=cache, routes=routes, credentials=creds)
    expected = {"tasks": {}}
    for task, task_block in v2["tasks"].items():
        provider = task_block["current_provider"]
        block = task_block["providers"][provider]
        expected["tasks"][task] = {
            "verified": [
                {"id": entry["id"], "label": entry["label"], "badge": None}
                for entry in block["models"]
                if entry["status"] == "visible" and entry["eligible"]
            ],
            "advanced": [
                {"id": entry["id"], "label": entry["label"], "badge": entry["status"]}
                for entry in block["models"]
                if entry["status"] in {"advanced", "seed", "route"}
            ],
            "cache_state": block["cache_state"],
            "discovered_at": block["discovered_at"],
        }
    assert effective_model_view(cache=cache, routes=routes, credentials=creds) == expected


def test_model_catalog_effective_gains_provider_indexed_shape(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr
    from src.model_credentials import CredentialStore

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)
    db = tmp_path / "profile_state.db"
    store = CredentialStore(db)
    anthropic = store.add(
        provider="anthropic", auth_type="api_key", alias="Claude primary",
        secret="sk-ant-" + "a" * 32, make_active=True,
    )
    openai = store.add(
        provider="openai", auth_type="api_key", alias="OpenAI primary",
        secret="sk-openai-" + "b" * 32, make_active=True,
    )

    out = cr.model_catalog(store=store)
    assert out["effective"]["providers"] == {
        "anthropic": {
            "credential_id": f"local:{anthropic.id}",
            "auth_mode": "api_key",
            "label": "Claude primary",
        },
        "openai": {
            "credential_id": f"local:{openai.id}",
            "auth_mode": "api_key",
            "label": "OpenAI primary",
        },
    }
    for task, block in out["effective"]["tasks"].items():
        assert {"verified", "advanced", "cache_state", "discovered_at"} <= set(block)
        assert block["current_provider"] == out["routes"][task]["provider"]
        assert set(block["providers"]) == {"openai", "anthropic"}

    monkeypatch.setattr(
        model_effective_module,
        "effective_model_view_v2",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("cache unavailable")),
    )
    assert cr.model_catalog(store=store)["effective"] == {"tasks": {}}


def test_v2_resolves_each_provider_scope_once(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr
    from src.model_credentials import CredentialStore
    from src.model_discovery_cache import DiscoveryScope

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)
    store = CredentialStore(tmp_path / "profile_state.db")
    store.add(provider="anthropic", auth_type="api_key", alias="A",
              secret="sk-ant-" + "a" * 32, make_active=True)
    store.add(provider="openai", auth_type="api_key", alias="O",
              secret="sk-openai-" + "b" * 32, make_active=True)
    calls = []

    class RecordingCache:
        def __init__(self, _path):
            pass

        def get(self, **scope):
            calls.append(scope)
            return DiscoveryScope(status="never_discovered", discovered_at=None, models=[])

    monkeypatch.setattr(cr, "ModelDiscoveryCache", RecordingCache)
    cr.model_catalog(store=store)
    assert [call["provider"] for call in calls] == ["openai", "anthropic"]
