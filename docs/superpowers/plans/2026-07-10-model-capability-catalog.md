# Model Capability Registry + Discovery Cache + Effective Picker (P2.7)

> **Status: DRAFT FOR REVIEW (round 4) 2026-07-10.** Implements PROJECT_PRIORITY_MAP
> §P2.7. Round-3 review returned 5 must-fix + a picker policy ruling; all code
> claims re-verified and folded: the effective view now takes per-provider
> credentials (mixed-provider routes tested), `api_key_pool` fails closed everywhere
> until actually wired into the live resolver, card tasks require tool calling
> (forced-tool synthesis verified at `card_synthesis.py:152`), the thinking schema
> grew to five modes with `manual_budget` matching today's non-adaptive Anthropic
> path, **structured refusal handling is in scope** (Fable's HTTP-200 refusal
> contract vs `agent.py:412` treating any non-tool_use stop as success), the
> `current|legacy` tier is replaced by `picker_visibility:
> default|advanced|pinned_only` per the adopted policy, the new-generation scope
> gains **Claude Sonnet 5**, and every remaining prose-only RED block is now
> complete executable test code. Docs-only; no runtime implementation has started.
> Author: Claude (implementer); reviewer: user.

**Goal:** One code-reviewed **capability registry** is the single source for model
facts; a **DB discovery cache** records per-credential visibility; an **effective
picker** shows, per task, only models that are visible to the active credential,
default-visibility, and executable under that task's auth mode. New generation
(Anthropic Fable 5 + Sonnet 5; OpenAI gpt-5.6 Sol/Terra/Luna) lands with
slice-time-verified facts and honest runtime support (refusal handling — no silent
fallback).

**Non-goals:** ANY default or recommendation flip (`agents/config.py`,
`model_routing.TASKS` — separate slice); `config/user_profile.yaml` scoring models;
scheduled discovery refresh; Ollama / OpenAI-compatible providers (schema must not
preclude; no entries); pricing display beyond `cost_tier`; removing
`model_catalog.py`; run/replay storage changes; route-validation authority
migration (`model_routing.EFFORT_OPTIONS` stays); **wiring `api_key_pool` into the
live resolver** (pool stays discovery/test-layer; executability returns False for
it until a dedicated slice wires it).

---

## Current Grounding (verified against code 2026-07-10, round-4 corrected)

1. **Nine drift sites** (contents as previously verified, unchanged): routing
   `MODEL_CATALOG` (exactly 7 ids) + `TASKS` + `EFFORT_OPTIONS` (wire values) +
   `model_provider()` + `is_seed_model()`; CLI `MODEL_CATALOG` (exactly 8 ids,
   `find_model("opus") == "claude-opus-4-7"` exact) + `EFFORT_OPTIONS_BY_MODEL`
   (anthropic-only; opus-4.8 missing = ruled Fix A) + `VALID_*_EFFORT`;
   `_ADAPTIVE_THINKING_MODELS`/`_EFFORT_MODELS`/`_MODEL_MAX_OUTPUT` (agent.py:102);
   `_COMPACTION_MODELS` (agent.py:32; opus-4.8 absent — Task 0 item);
   `_1M_GA_MODELS`/`_1M_BETA_MODELS` (subagent.py:25; opus-4.8 in neither —
   `_use_extended_context_beta("claude-opus-4-8", True)` returns False, wire
   preserved by Fix B); `_OPENAI_MODEL_MAX_OUTPUT` (agent.py:64);
   `_MODEL_CONTEXT_LIMITS` (context_manager.py:58; **opus-4.8 missing → 200_000
   fallback today** = ruled Fix B); `agents/config.py:43` (NOT changed);
   `ModelRoutingSection` at `Settings.tsx:2011` (test file uses the house
   createRoot/act harness with a local `catalog()` fixture + `render()` helper —
   verified by reading it).
2. **Thinking reality (round-3 MF4, verified)**: `_build_thinking_param`
   (agent.py:132) — adaptive-set models get `thinking: adaptive` when enabled
   (opt-in); **every other Anthropic model gets `enabled` + derived
   `budget_tokens`** (manual budget path); OpenAI models have no thinking param
   (reasoning effort instead). So today's truthful modes: opus-4.8/4.7,
   sonnet-4.6 = `adaptive_opt_in`; haiku-4.5, sonnet-4.5, opus-4.5 =
   `manual_budget`; all OpenAI = `none`.
3. **Refusal gap (round-3 MF4, verified)**: `agent.py:412` — any
   `stop_reason != "tool_use"` (except `"compaction"`) extracts text and logs a
   FINAL ANSWER. Fable's documented refusal contract (HTTP 200 +
   `stop_reason="refusal"`, possibly empty content) would therefore surface as a
   successful empty answer. `card_synthesis.py` similarly checks only for its
   forced tool block. Structured refusal handling is REQUIRED before Fable can be
   marked runtime-ready.
4. **Executability grounding (round-3 MF2, verified)**:
   - `live_resolver.resolve_live_auth()` resolves ONLY a DB `api_key` row
     (`db_api_key`) or falls through to env (`env_fallback`); OAuth-active →
     fail-closed for the sync clients that card tasks use
     (`card_synthesis.py:152` calls `live_anthropic_client()` and posts a
     **forced tool** — cards therefore require `supports_tool_calling`).
   - **`api_key_pool` appears NOWHERE in `live_resolver.py`** (grep zero hits for
     `OPENAI_API_KEYS`/`api_key_pool`): pools exist in the credential
     inventory/discovery/test layer only. A pool-active credential is NOT
     resolvable by the direct clients today → executability must return False for
     `api_key_pool` on every task until a wiring slice lands.
   - AI 研究 streaming supports api_key AND both OAuth driver paths.
5. **Credential identity is mutable under a fixed id**: `PUT
   /config/credentials/{id}` replaces `local:` secrets in place; env ids don't
   change when keys rotate → cache carries a `secret_fingerprint`.
6. **Discovery**: `discover_models()` live-only; `claude_code_oauth` driver returns
   `status="ok"` with SEED models (no live listing) → `seed_only` cache state.
   `_active_auth_mode()` (config_routes.py:77) is DB-only and id-less → replaced
   by `resolve_active_credential()` for cache addressing.
7. **New-generation scope (round-3 MF3): FIVE models** — Anthropic **Fable 5** and
   **Sonnet 5**; OpenAI **gpt-5.6 Sol / Terra / Luna**. Official per-model pages
   (Task 0 inputs): Fable announcement + effort + context-windows docs; Sol/Terra/
   Luna model pages; Claude release notes (Sonnet 5). Reviewer-supplied pricing to
   re-verify in Task 0: Sol $5/$30, Terra $2.50/$15, Luna $1/$6, Sonnet 5 $2/$10
   promo (later $3/$15). Known contract shapes to verify: Fable thinking
   always-on (explicit disable rejected) + refusal stop_reason; Sonnet 5 thinking
   default-on (omit = on, explicit disable allowed).
8. **Model-value rationale (user ruling 2026-07-10, drives visibility)**: de facto
   worth-listing OpenAI set = Sol / Terra / Luna / gpt-5.4-mini (Terra ≈ gpt-5.5
   capability at lower price; Luna slightly above gpt-5.4-mini price with a bigger
   capability step; gpt-5.4-mini stays relevant esp. under codex OAuth costing).
   Strongest-per-family = Fable 5 / Opus 4.8 / Sonnet 5; Haiku 4.5 retained for
   translation/notes-type work. Previous-generation Opus 4.7 / Sonnet 4.6 keep a
   path for now (Advanced) with **future removal expected**.

---

## Decisions Locked By This Plan

1. **Registry is code, cache is DB, picker is the per-task intersection.**
2. **Registry membership = official documentation; entitlement = cache.**
3. **Behavior-identical consolidation, verified against the LIVE old helpers**
   (Task 1 test imports the untouched old tables/helpers and compares
   programmatically; ruled fixes are the only enumerated exceptions).
4. **Ruled fixes**: Fix A (opus-4.8 CLI effort options None → opus tuple), Fix B
   (opus-4.8 context 200_000-fallback → 1_000_000 + `context_mode="ga_1m"`;
   wire-verified header behavior unchanged). Opus-4.8 compaction = Task 0 item →
   explicit Fix C proposal if docs support it.
5. **Compat views keep EXACT current membership** via `in_routing_seed` /
   `in_cli_catalog` flags (routing = the 7, CLI = the 8, alias placement
   preserved); Task 5 additions set both flags (ruled, visible in diff).
6. **`picker_visibility: "default" | "advanced" | "pinned_only"` replaces the
   tier axis** (round-3 policy, user-adopted):
   - `default`: claude-fable-5, claude-opus-4-8, claude-sonnet-5, claude-haiku-4-5,
     gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.4-mini.
   - `advanced`: claude-opus-4-7, claude-sonnet-4-6 (previous generation kept as a
     path; **future-removal note recorded in entry `notes`**).
   - `pinned_only`: gpt-5.5, gpt-5.4, gpt-5.4-nano, gpt-5.2, gpt-5.2-codex,
     claude-sonnet-4-5, claude-opus-4-5 — shown ONLY when a saved route pins them
     (badge `route`).
   - Discovery entitlement remains the final gate for the default list: a
     default-visibility model NOT visible to the active credential does not enter
     `verified`.
   - Visibility is a PICKER axis only — compat view flags (Decision 5) keep
     CLI/routing seed behavior unchanged.
7. **Two effort semantics stay split**: `model_routing.EFFORT_OPTIONS` (wire,
   incl. `default`) untouched + pinned; registry `effort_options` = model-supported
   set (anthropic per-model; OpenAI transcribe the provider-wide six-value
   reasoning set). CLI `get_effort_options()` keeps None-for-OpenAI.
8. **Thinking is a five-mode axis** (round-3 MF4):
   `thinking_mode: "none" | "manual_budget" | "adaptive_opt_in" |
   "adaptive_default_on" | "adaptive_always_on"`.
   Existing mapping per grounding §2; Sonnet 5 = `adaptive_default_on`; Fable 5 =
   `adaptive_always_on` (the anthropic agent must never emit a disable or
   budget_tokens for always-on models, and must not emit `thinking` at all for
   `none`/OpenAI — driven off the registry).
9. **Executability contract** (round-3 MF1+MF2):
   `task_auth_executable(task, provider, auth_mode, capability) -> bool`:
   - card_synthesis / card_translation: auth_mode == `api_key` only
     (**`api_key_pool` = False until wired**; OAuth fail-closed), AND
     `capability.supports_tool_calling` (forced-tool synthesis) AND
     `capability.supports_structured_output`.
   - ai_research: auth_mode ∈ {api_key, claude_code_oauth→anthropic,
     chatgpt_oauth→openai} (**pool = False here too**), AND
     `capability.supports_tool_calling`.
   - provider mismatch / unknown / None auth_mode → False.
   `effective_model_view(cache, routes, credentials: dict[Provider,
   ActiveCredential | None])` — per-task provider comes from that task's route;
   mixed-provider routing is first-class.
10. **Structured refusal handling is in scope (Task 5B)**: the anthropic agent
    loop and card synthesis recognize `stop_reason == "refusal"` and surface a
    structured refusal (event/error) — never an empty successful answer, never a
    hidden model fallback. **Escape hatch**: if implementation reveals depth
    beyond these two seams, Fable ships `runtime_ready=False` (excluded from
    `verified`, badge 「運行支援未接線」) and a follow-up slice is filed — that
    stop-loss replaces shipping a half-handled refusal path.
11. **Cache scope carries `secret_fingerprint`** (`sha256(secret)[:16]` for
    api_key; constant `"oauth"` for OAuth modes); mismatch reads
    `never_discovered`. States: `ok` (zero-model representable) / `seed_only`
    (badge, no nudge) / `never_discovered`. Replace-on-success,
    preserve-on-failure, no secret columns.
12. **Effective view carries `cache_state` + `discovered_at`**; UI copy 「最後驗證
    可見 <time>」; saved route model always selectable.
13. **API changes additive**; **provenance per entry**; **house store pattern**.

---

## Files

Create: `src/model_capabilities.py`, `src/model_discovery_cache.py`,
`src/model_effective.py`, `tests/test_model_capabilities.py`,
`tests/test_model_discovery_cache.py`, `tests/test_model_effective.py`.

Modify: `src/model_routing.py`, `src/agents/shared/model_catalog.py`,
`src/agents/anthropic_agent/agent.py` (tables + **refusal branch**),
`src/agents/openai_agent/agent.py`, `src/agents/shared/context_manager.py`,
`src/agents/shared/subagent.py`, `src/card_synthesis.py` (**refusal branch**),
`src/model_credentials.py`, `src/api/routes/config_routes.py`,
`apps/arkscope-web/src/api.ts`, `apps/arkscope-web/src/Settings.tsx`,
`apps/arkscope-web/src/ModelRoutingSection.test.ts`, `tests/test_model_routing.py`,
`tests/test_card_synthesis.py`, map + this plan.

NOT modified (ruled): `src/agents/config.py`, `model_routing.TASKS`,
`model_routing.EFFORT_OPTIONS`, `config/user_profile.yaml`, live_resolver pool
behavior.

---

## Stop-Loss Triggers

- A model lacks an official per-model page → not in the registry.
- Consolidation changes any live-helper output beyond Fixes A/B (+approved C).
- Compat view membership or alias resolution shifts beyond Task 5's flagged adds.
- Registry needs DAL/DB/network imports; API shape changes non-additively.
- Refusal handling needs more than the two named seams → Fable
  `runtime_ready=False` + follow-up slice (Decision 10), not a wider slice.
- Cache would need secrets; effective view wants to rewrite a route.
- Any default/recommendation flip; any `api_key_pool` wiring.

---

## Review Gates

1. Old-vs-new equivalence (executable, full id set, ruled-fix exceptions only).
2. View membership pins (7/8 exact; `find_model("opus")` exact).
3. Single-source grep over the four agent modules.
4. Prefix precedence structural; alias integrity (unique, no canonical collision,
   official aliases resolve).
5. Effort split pins (wire tuples unchanged; registry tuples exact; CLI
   None-for-OpenAI).
6. Executability matrix incl. pool-False, OAuth-cards-False, mixed provider.
7. Cache contracts incl. fingerprint mismatch, zero-model ok, seed_only.
8. Effective view: per-task, per-provider credentials, three cache states,
   `discovered_at` surfaced, route-model invariant.
9. **Refusal**: agent loop + card synthesis produce structured refusals from
   `stop_reason="refusal"` fakes; no empty-success path remains.
10. Frontend suite + typecheck + build; picker behavior incl. 最後驗證可見 copy.
11. PG smoke; full virgin A/B (sets identical, delta exact, warnings accounted).

---

## Task 0: Verify New-Generation + Contested Facts (no code)

1. WebFetch per-model pages: Fable 5 (announcement/effort/context), **Sonnet 5**
   (release notes / model page), Sol, Terra, Luna. Extract per model: canonical
   id, official aliases (`gpt-5.6` → Sol?), context, max output, thinking contract
   (five-mode mapping), effort set, compaction, context mode, structured-output,
   tool-calling, pricing.
2. Resolve contested facts: opus-4.8 context (→ Fix B confirmation), opus-4.8
   compaction (→ Fix C proposal or unchanged), Fable refusal contract fields
   (stop_reason value, stop_details shape) for the Task 5B tests.
3. Read-only live discovery per configured credential → entitlement table.
4. Emit both tables (capability + entitlement) into this plan; pricing lines
   feed the visibility sanity check (Decision 6 assignments re-confirmed against
   verified pricing).

Commit: `docs: verify new model generation facts`.
**Gate**: reviewer acks both tables + any Fix C before Task 1.

---

## Task 1: Capability Registry Module (existing models only)

**Files:** `src/model_capabilities.py`, `tests/test_model_capabilities.py`.

### Step 1: RED tests (complete, executable)

```python
import pytest

from src.model_capabilities import (
    ModelCapability,
    all_models,
    capability_for,
    default_picker_models,
)

_PRE_CONSOLIDATION_IDS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
    "claude-sonnet-4-5", "claude-opus-4-5",
    "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5.2-codex",
}

_RULED_FIXES = {
    ("claude-opus-4-8", "context_limit"),   # Fix B: 200_000 fallback → 1_000_000
    ("claude-opus-4-8", "context_mode"),    # Fix B: neither-set → ga_1m
    ("claude-opus-4-8", "effort_options"),  # Fix A: None → opus tuple (CLI helper)
}


def test_registry_covers_every_pre_consolidation_id():
    assert {m for m in _PRE_CONSOLIDATION_IDS if capability_for(m) is None} == set()


def test_registry_matches_live_legacy_helpers_except_ruled_fixes():
    from src.agents.anthropic_agent.agent import (
        _MODEL_MAX_OUTPUT as OLD_ANTH_OUT,
        _ADAPTIVE_THINKING_MODELS as OLD_ADAPTIVE,
        _COMPACTION_MODELS as OLD_COMPACT,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit
    from src.agents.shared.subagent import _1M_GA_MODELS, _1M_BETA_MODELS
    from src.agents.shared.model_catalog import get_effort_options

    for mid in sorted(_PRE_CONSOLIDATION_IDS):
        cap = capability_for(mid)
        # context limit
        old_ctx = get_model_context_limit(mid)
        if (mid, "context_limit") in _RULED_FIXES:
            assert cap.context_limit == 1_000_000 and old_ctx == 200_000, mid
        else:
            assert cap.context_limit == old_ctx, mid
        # max output
        if cap.provider == "anthropic":
            old_out = next((v for k, v in OLD_ANTH_OUT.items() if mid.startswith(k)), 64_000)
        else:
            old_out = _get_openai_max_output(mid)
        assert cap.max_output == old_out, mid
        # thinking mode (round-3 MF4 mapping: adaptive set → adaptive_opt_in;
        # other anthropic → manual_budget; openai → none)
        if cap.provider == "anthropic":
            expected_mode = (
                "adaptive_opt_in"
                if any(mid.startswith(m) for m in OLD_ADAPTIVE)
                else "manual_budget"
            )
        else:
            expected_mode = "none"
        assert cap.thinking_mode == expected_mode, mid
        # effort tuple (CLI helper contract is anthropic-only)
        old_tuple = get_effort_options(mid)
        if (mid, "effort_options") in _RULED_FIXES:
            assert old_tuple is None
            assert cap.effort_options == ("max", "xhigh", "high", "medium", "low"), mid
        elif cap.provider == "anthropic":
            assert cap.effort_options == (tuple(old_tuple) if old_tuple else ()), mid
        # compaction / context mode
        assert cap.supports_compaction == any(mid.startswith(m) for m in OLD_COMPACT), mid
        old_mode = (
            "ga_1m" if mid in _1M_GA_MODELS
            else "beta_1m" if mid in _1M_BETA_MODELS
            else "standard"
        )
        if (mid, "context_mode") in _RULED_FIXES:
            assert cap.context_mode == "ga_1m" and old_mode == "standard", mid
        else:
            assert cap.context_mode == old_mode, mid


def test_openai_models_record_provider_wide_effort_set():
    for mid in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2"):
        assert capability_for(mid).effort_options == (
            "none", "minimal", "low", "medium", "high", "xhigh",
        ), mid


def test_view_flags_pin_exact_current_memberships():
    routing = {c.id for c in all_models() if c.in_routing_seed}
    cli = {c.id for c in all_models() if c.in_cli_catalog}
    assert routing == {
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    }
    assert cli == {
        "claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.4-mini",
        "gpt-5.4-nano", "gpt-5.4", "gpt-5.2", "gpt-5.2-codex",
    }


def test_picker_visibility_matches_the_round3_ruling():
    vis = {c.id: c.picker_visibility for c in all_models()}
    # pre-consolidation ids only (new generation lands in Task 5 with `default`)
    assert vis["claude-opus-4-8"] == "default"
    assert vis["claude-haiku-4-5"] == "default"
    assert vis["gpt-5.4-mini"] == "default"
    assert vis["claude-opus-4-7"] == "advanced"
    assert vis["claude-sonnet-4-6"] == "advanced"
    for pinned in ("gpt-5.5", "gpt-5.4", "gpt-5.4-nano", "gpt-5.2",
                   "gpt-5.2-codex", "claude-sonnet-4-5", "claude-opus-4-5"):
        assert vis[pinned] == "pinned_only", pinned


def test_default_picker_models_helper():
    ids = {c.id for c in default_picker_models("openai")}
    assert ids == {"gpt-5.4-mini"}   # until Task 5 adds the 5.6 family
    assert {c.id for c in default_picker_models("anthropic")} == {
        "claude-opus-4-8", "claude-haiku-4-5",
    }


def test_prefix_precedence_is_structural_not_list_order():
    assert capability_for("gpt-5.4-mini-2026-x").id == "gpt-5.4-mini"
    assert capability_for("gpt-5.4-2026-x").id == "gpt-5.4"
    assert capability_for("gpt-5.2-codex-x").id == "gpt-5.2-codex"
    assert capability_for("claude-haiku-4-5-20251001").id == "claude-haiku-4-5"


def test_unknown_model_returns_none():
    assert capability_for("mystery-model") is None


def test_every_entry_carries_provenance_and_visibility():
    for cap in all_models():
        assert cap.source_url and cap.verified_at, cap.id
        assert cap.picker_visibility in ("default", "advanced", "pinned_only"), cap.id
        assert cap.thinking_mode in (
            "none", "manual_budget", "adaptive_opt_in",
            "adaptive_default_on", "adaptive_always_on",
        ), cap.id
```

### Step 2: Implement

`ModelCapability` frozen dataclass: `id`, `provider`, `label`,
`picker_visibility`, `thinking_mode`, `effort_options`, `supports_compaction`,
`context_mode`, `context_limit`, `max_output`, `supports_structured_output`,
`supports_tool_calling`, `runtime_ready: bool = True`, `in_routing_seed`,
`in_cli_catalog`, `aliases`, `quality`, `speed`, `cost_tier`, `recommended_for`,
`source_url`, `verified_at`, `notes`. Exact alias/id match then longest-prefix.
Pure stdlib. `default_picker_models(provider)` filters
`picker_visibility == "default" and runtime_ready`.

Commit: `feat: add model capability registry`.

---

## Task 2: Converge the Nine Sites (unchanged from round 3 except thinking modes)

Same RED/implementation as round 3 with the thinking-mode mapping corrected
(haiku/sonnet-4.5/opus-4.5 = `manual_budget`; `_build_thinking_param` derives its
adaptive/enabled+budget branch from `thinking_mode`, preserving today's outputs
for every existing model — pinned by the Task 1 old-vs-new test plus:

```python
def test_build_thinking_param_wire_shapes_preserved():
    from src.agents.anthropic_agent.agent import _build_thinking_param

    class _Cfg:  # minimal config double, mirrors the attributes the helper reads
        max_tokens = 8192
        anthropic_thinking = True

    adaptive, max_a = _build_thinking_param("claude-opus-4-8", True, _Cfg())
    assert adaptive == {"type": "adaptive"}
    budget, max_b = _build_thinking_param("claude-haiku-4-5", True, _Cfg())
    assert budget["type"] == "enabled" and budget["budget_tokens"] > 0
    none_param, _ = _build_thinking_param("claude-haiku-4-5", False, _Cfg())
    assert none_param is None
```

(exact expected shapes transcribed from the current helper's behavior at
implementation time — RED must show the assertion values match reality before the
registry swap). Views/effort/route-wire pins as in round 3
(`test_route_wire_effort_values_untouched`,
`test_derived_views_keep_exact_membership_and_aliases`,
`test_cli_effort_helper_contract_preserved_plus_fix_a`).

Commit: `feat: converge model facts onto the registry`.

---

## Task 3: Discovery Cache Store (round-3 fixtures kept, seam tests now code)

**Files:** `src/model_discovery_cache.py`, `src/model_credentials.py`,
`tests/test_model_discovery_cache.py`, `tests/test_model_routing.py`.

Store RED tests: as round 3 (replace-on-success, zero-model ok, fingerprint
mismatch → never_discovered + supersede, seed_only, unknown scope, no secret
columns — complete code already in round 3, carried verbatim).

**Caller-seam RED tests (round-3 MF5 — now code, in `tests/test_model_routing.py`):**

```python
def test_discover_models_success_writes_cache(monkeypatch, tmp_path):
    import src.model_credentials as mc

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    recorded = {}

    class _FakeCache:
        def record_run(self, **kw):
            recorded.update(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", lambda *a, **k: _FakeCache())

    class _FakeModels:
        data = [type("M", (), {"id": "gpt-5.6-luna"})()]

    class _FakeClient:
        def __init__(self, **kw): ...
        class models:  # noqa: N801 - mirrors sdk attribute
            @staticmethod
            def list():
                return _FakeModels()

    monkeypatch.setattr(mc, "_resolve_api_credential",
                        lambda *a, **k: type("C", (), {"id": "c1", "secret": "sk-x"})())
    monkeypatch.setattr("openai.OpenAI", _FakeClient)

    out = mc.discover_models("openai", "c1")
    assert out.status == "ok"
    assert recorded["status"] == "ok"
    assert recorded["secret_fingerprint"] == mc.secret_fingerprint("sk-x")
    assert [m["id"] for m in recorded["models"]] == ["gpt-5.6-luna"]


def test_discover_models_failure_records_nothing(monkeypatch, tmp_path):
    import src.model_credentials as mc

    calls = []

    class _FakeCache:
        def record_run(self, **kw):
            calls.append(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", lambda *a, **k: _FakeCache())
    monkeypatch.setattr(mc, "_resolve_api_credential",
                        lambda *a, **k: type("C", (), {"id": "c1", "secret": "sk-x"})())

    class _Boom:
        def __init__(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("openai.OpenAI", _Boom)
    out = mc.discover_models("openai", "c1")
    assert out.status == "error" and calls == []
```

(The oauth-route branch gets the same treatment handler-direct in Task 4's route
test: a fake driver result whose models are all `source="seed"` must record
`status="seed_only"`.)

Commit: `feat: cache per-credential model discovery`.

---

## Task 4: Resolver + Executability + Per-Task Effective View + Picker

**Files:** `src/model_credentials.py`, `src/model_effective.py`,
`config_routes.py`, `api.ts`, `Settings.tsx`, `ModelRoutingSection.test.ts`,
`tests/test_model_effective.py`.

### Step 1: RED tests (backend — complete)

```python
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


def _routes_mixed() -> dict[str, TaskRoute]:
    # Round-3 MF1: the DEFAULT config shape — anthropic cards + openai research.
    return {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="anthropic",
                                    model="claude-opus-4-8", effort="default"),
        "card_translation": TaskRoute(task="card_translation", provider="anthropic",
                                      model="claude-sonnet-4-6", effort="default"),
        "ai_research": TaskRoute(task="ai_research", provider="openai",
                                 model="mystery-model", effort="default"),
    }


def _credentials(tmp_path):
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
                                credentials=_credentials(tmp_path))
    # anthropic api_key cards: opus-4.8 verified (visible+default+executable);
    # opus-4.7 visible but advanced-visibility → advanced
    synth = view["tasks"]["card_synthesis"]
    assert [m["id"] for m in synth["verified"]] == ["claude-opus-4-8"]
    assert any(m["id"] == "claude-opus-4-7" for m in synth["advanced"])
    assert synth["cache_state"] == "ok" and synth["discovered_at"]
    # card_translation pins sonnet-4.6 (advanced visibility) → appears via route badge
    trans = view["tasks"]["card_translation"]
    assert any(m["id"] == "claude-sonnet-4-6" and m["badge"] in ("route", "advanced")
               for m in trans["advanced"])
    # openai research under chatgpt_oauth: mini verified; gpt-5.5 pinned_only →
    # NOT verified despite visibility; mystery-model = route badge
    research = view["tasks"]["ai_research"]
    assert [m["id"] for m in research["verified"]] == ["gpt-5.4-mini"]
    advanced_ids = {m["id"] for m in research["advanced"]}
    assert {"gpt-5.5", "mystery-model"} <= advanced_ids


def test_effective_view_oauth_blocks_card_tasks_even_when_visible(tmp_path):
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
    view = effective_model_view(cache=cache, routes=_routes_mixed(), credentials=creds)
    assert view["tasks"]["card_synthesis"]["verified"] == []
    assert view["tasks"]["card_synthesis"]["cache_state"] == "seed_only"
    # research on anthropic oauth IS executable, but with seed_only cache nothing
    # is verified — seeds appear in advanced with the seed badge
    assert view["tasks"]["ai_research"]["verified"] == []


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
    from src.model_credentials import resolve_active_credential

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-only")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    cred = resolve_active_credential("openai")
    assert cred is not None
    assert cred.auth_mode == "api_key" and cred.credential_id
    assert cred.secret_fingerprint == _fp("sk-env-only")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-rotated")
    assert resolve_active_credential("openai").secret_fingerprint == _fp("sk-rotated")
```

**Route RED test (handler-direct, house idiom):**

```python
def test_model_catalog_route_gains_additive_effective_block(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setattr(
        cr, "resolve_active_credential",
        lambda provider, **kw: None,   # fail-closed shape is enough for the route pin
    )
    out = cr.get_model_catalog()
    # old fields keep their shape
    for key in ("providers", "tasks", "models", "effort_options", "routes"):
        assert key in out
    # additive per-task effective block
    assert set(out["effective"]["tasks"]) == {"card_synthesis", "card_translation", "ai_research"}
    block = out["effective"]["tasks"]["ai_research"]
    assert {"verified", "advanced", "cache_state", "discovered_at"} <= set(block)
```

(Exact handler name/signature checked against `config_routes.py` at implementation
time — the pinned contract is: same endpoint, additive `effective` key, fail-closed
renders `never_discovered`.)

### Step 2: RED tests (frontend — house harness, extends the existing fixture)

```tsx
it("model picker defaults to verified and reveals advanced with badges", () => {
  const cat = catalog();
  (cat as any).effective = {
    tasks: {
      ai_research: {
        verified: [{ id: "gpt-5.4-mini", label: "GPT-5.4 mini", badge: null }],
        advanced: [
          { id: "gpt-5.5", label: "GPT-5.5", badge: "advanced" },
          { id: "mystery-model", label: "mystery-model", badge: "route" },
        ],
        cache_state: "ok",
        discovered_at: "2026-07-10T06:00:00Z",
      },
      card_synthesis: { verified: [], advanced: [], cache_state: "never_discovered", discovered_at: null },
      card_translation: { verified: [], advanced: [], cache_state: "seed_only", discovered_at: null },
    },
  };
  render(undefined, cat);

  const research = host!.querySelector('[data-testid="route-ai_research"]')!;
  const options = Array.from(research.querySelectorAll("option")).map((o) => o.value);
  expect(options).toContain("gpt-5.4-mini");
  expect(options).not.toContain("gpt-5.5");            // advanced hidden by default

  act(() => {
    (research.querySelector('[aria-label="顯示進階模型"]') as HTMLInputElement).click();
  });
  const expanded = Array.from(research.querySelectorAll("option")).map((o) => o.value);
  expect(expanded).toContain("gpt-5.5");
  expect(research.textContent).toContain("最後驗證可見");

  const synth = host!.querySelector('[data-testid="route-card_synthesis"]')!;
  expect(synth.textContent).toContain("跑一次模型探索以驗證");   // never_discovered nudge
  const trans = host!.querySelector('[data-testid="route-card_translation"]')!;
  expect(trans.textContent).toContain("此通道無法線上列出模型"); // seed_only, no nudge
  expect(trans.textContent).not.toContain("跑一次模型探索以驗證");
});
```

(`render()` gains an optional catalog argument; `data-testid="route-<task>"`
wrappers are part of the implementation contract. The saved-route-selected
invariant reuses the fixture's `mystery-model` route pin: assert the select's value
is `"mystery-model"` after expanding advanced.)

### Step 3: Implement

`resolve_active_credential()` (inventory-based incl. env rows; sha256[:16];
`"oauth"` constant), `task_auth_executable()` + `effective_model_view(cache,
routes, credentials)` in `model_effective.py`; additive API block; picker split in
`ModelRoutingSection`. `PUT /config/model-routes` untouched.

Commit: `feat: verified-first per-task model picker`.

---

## Task 5: New Generation Lands (5 models) + Refusal Handling

**Files:** `src/model_capabilities.py`, `src/agents/anthropic_agent/agent.py`,
`src/card_synthesis.py`, `tests/test_card_synthesis.py`, ledger-swept tests.

### 5A: Registry entries (RED first)

- Entries for the Task 0-verified ids — Fable 5 (`adaptive_always_on`, effort
  tuple per docs, compaction/context per docs), **Sonnet 5**
  (`adaptive_default_on`), Sol/Terra/Luna (`none`, provider effort set) — all
  `picker_visibility="default"`, both view flags set (ruled additions), per-model
  source pages, `verified_at` = Task 0 date.
- Alias tests: `capability_for("gpt-5.6")` → Sol iff docs define it;
  `find_model("fable")`; alias uniqueness sweep.
- `model_provider()` classifies all five.
- Registry-driven thinking: `_build_thinking_param` for `adaptive_always_on`
  never returns a disable/budget shape even when `thinking_enabled=False`
  (always-on models ignore the toggle — assert the exact param per Task 0);
  `adaptive_default_on` omits the param by default and allows explicit disable.

### 5B: Structured refusal handling (RED first — the two named seams)

```python
def test_agent_loop_surfaces_refusal_as_structured_failure(monkeypatch):
    # stop_reason="refusal" (HTTP 200) must NOT become an empty successful answer.
    # Build a fake response shaped like anthropic Message: stop_reason="refusal",
    # content=[] (pre-output refusal per docs).
    from src.agents.anthropic_agent import agent as mod

    fake_response = type("R", (), {
        "stop_reason": "refusal", "content": [],
        "stop_details": {"category": "safety"}, "usage": None,
    })()
    outcome = mod._classify_terminal_response(fake_response)   # new seam, named here
    assert outcome.kind == "refusal"
    assert outcome.final_text == ""
    # and the loop maps it to a refusal event/error, never log_final_answer success
    # (loop-level assertion via the fake-client harness used by existing agent tests)


def test_card_synthesis_raises_structured_refusal(monkeypatch):
    from src import card_synthesis as cs

    fake = type("R", (), {"stop_reason": "refusal", "content": [],
                          "stop_details": {"category": "safety"}})()

    class _FakeClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                return fake

    monkeypatch.setattr(cs, "live_anthropic_client", lambda **kw: _FakeClient())
    with pytest.raises(cs.CardSynthesisRefused) as exc:
        cs.synthesize_card_once_for_test(...)   # exact entry adapted to the module's
                                                # existing test seam at implementation
    assert "refusal" in str(exc.value)
```

(Loop/entry shapes are adapted to the module's existing test seams at
implementation time; the pinned contract: `stop_reason == "refusal"` → typed
outcome at BOTH seams, no fallback call to another model, no empty-success.
Fake shapes re-checked against the Task 0-verified refusal contract fields.)

**Escape hatch** (Decision 10): if 5B reveals depth beyond these seams, Fable
ships `runtime_ready=False` (excluded from `default_picker_models`/`verified`,
badge 「運行支援未接線」), follow-up filed; 5A still lands.

### 5C: Ledger sweep + live smoke

Sweep by NEW ids across `tests/`; smoke = **one minimal live call per provider**:
the cheapest verified gpt-5.6 id (expected Luna per pricing) and Sonnet 5
(promo-priced); Fable smoke user-gated (premium). Non-smoked ids annotated
`runtime-unverified` in notes.

Commit: `feat: land fable-5 sonnet-5 and gpt-5.6 generation`.

---

## Task 6: Gates, Full A/B, Docs Closeout

1. Focused backend: capability/cache/effective/routing/card suites + sweep set.
2. Frontend: full vitest + typecheck + build.
3. Static gates: single-source grep; `rg -n "psycopg2|postgres"` over the three
   new modules → empty.
4. PG smoke `ok:true` `pg_attempts:[]`.
5. Full virgin A/B: sets identical; delta = new tests; warnings accounted.
6. Docs: plan → IMPLEMENTED FOR REVIEW; map §P2.7 + decision-log; MEMORY.md
   Active-Models rewritten from the registry.

Review-ready stop before merge; reviewer reruns focused + final A/B; merge on
explicit approval; live verification = Settings discovery round + per-task picker
+ smoke evidence + one real refusal-path observation if reproducible cheaply.

---

## Expected Commit Sequence

1. `docs: verify new model generation facts` (Task 0)
2. `feat: add model capability registry`
3. `feat: converge model facts onto the registry`
4. `feat: cache per-credential model discovery`
5. `feat: verified-first per-task model picker`
6. `feat: land fable-5 sonnet-5 and gpt-5.6 generation`
7. `docs: close model capability catalog build`
