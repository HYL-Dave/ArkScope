# Model Capability Registry + Discovery Cache + Effective Picker (P2.7)

> **Status: DRAFT FOR REVIEW 2026-07-10.** Implements PROJECT_PRIORITY_MAP §P2.7
> (architecture adopted 2026-07-10 after the gpt-5.6 Sol cross-review). Docs-only;
> no runtime implementation has started. Author: Claude (implementer); reviewer: user.

**Goal:** One code-reviewed **capability registry** becomes the single source for
model facts (context/output limits, thinking/effort support, tier); a **DB discovery
cache** records which models each credential can actually see; an **effective picker**
shows only the intersection by default. New-generation models (Anthropic Fable 5,
OpenAI gpt-5.6 family) land with slice-time-verified facts. CLI, discord, Settings
routing, agents, and context manager all read the registry.

**Non-goals:** `config/user_profile.yaml` scoring-model choices (config values, not
pickers — a validation warning is a later follow-up); scheduled/automatic discovery
refresh (v1 is manual, from the existing Settings discovery button); Ollama /
OpenAI-compatible providers (Vision Tier A scope — the registry schema must not
preclude them, but no entries land now); pricing display beyond the existing
`cost_tier`; retiring the `model_catalog.py` module path (it becomes a compat shim,
removal is a later cleanup); any change to run/replay storage.

---

## Current Grounding (verified against code 2026-07-10)

1. **Seven drift sites** hold model facts today:
   - `src/model_routing.py` — pydantic `ModelOption` seed `MODEL_CATALOG` (7 models,
     newest opus-4.8/gpt-5.5), `TASKS` recommendations, per-provider `EFFORT_OPTIONS`,
     `model_provider()` prefix heuristic, `is_seed_model()`. `CATALOG_VERIFIED_AT =
     "2026-06-06"`.
   - `src/agents/shared/model_catalog.py` — dataclass `ModelEntry` seed
     `MODEL_CATALOG` (8 models, newest **opus-4.7**/gpt-5.5 — already one generation
     behind the routing seed), `find_model()` (id/name/alias/partial match),
     `EFFORT_OPTIONS_BY_MODEL` (prefix; **stale: has opus-4-7 + sonnet-4-6 only, so
     `get_effort_options("claude-opus-4-8") → None` — the CLI offers no effort
     options for opus-4.8 today**), `VALID_ANTHROPIC_EFFORT`/`VALID_REASONING_EFFORT`.
   - `src/agents/anthropic_agent/agent.py:102` — `_ADAPTIVE_THINKING_MODELS`,
     `_EFFORT_MODELS` (both `{opus-4-8, opus-4-7, sonnet-4-6}`), `_MODEL_MAX_OUTPUT`
     (128K/128K/64K) + prefix helpers `_get_model_max_output`,
     `_supports_adaptive_thinking`, `_supports_effort`.
   - `src/agents/openai_agent/agent.py:64` — `_OPENAI_MODEL_MAX_OUTPUT` (5 ids, all
     128000) + `_get_openai_max_output`, `_OPENAI_DEFAULT_MAX_OUTPUT = 128000`.
   - `src/agents/shared/context_manager.py:58` — `_MODEL_CONTEXT_LIMITS` (8 prefixes;
     comment warns "more specific prefixes first"), `_DEFAULT_CONTEXT_LIMIT =
     200_000`, `get_model_context_limit()`.
   - `src/agents/config.py:43` — `openai_model: str = "gpt-5.4"` (stale default),
     `anthropic_model: str = "claude-sonnet-4-6"`.
   - Frontend fixtures pin their own local objects (`ModelRoutingSection.test.ts`
     builds its catalog inline) — backend seed changes do NOT break them as long as
     the `/config/model-catalog` response stays shape-compatible.
2. **Import direction is safe for a top-level registry**: `src/model_credentials.py:26`
   imports from `src.model_routing`; `src/agents/cli.py` and
   `src/monitor/discord_bot.py` import from `src.agents.shared.model_catalog`. A new
   `src/model_capabilities.py` (pure code, zero DAL/DB imports) can be imported by all
   of them without cycles.
3. **Discovery is live-only, uncached**: `src/model_credentials.py:901
   discover_models(provider, credential_id, store)` → OpenAI `client.models.list()` /
   Anthropic `GET /v1/models`; on missing credential or error it falls back to
   `_seed_models()` (built from routing `MODEL_CATALOG`). Served by
   `POST /config/model-discovery` (`config_routes.py:589`), which routes
   chatgpt_oauth discovery through the auth driver instead. Nothing persists; the AI
   研究 picker re-merges per fetch (`researchModels.ts` — discovered-first + route
   model always included).
4. **Catalog API**: `GET /config/model-catalog` (`config_routes.py:227`) returns
   `catalog().model_dump()` (providers/tasks/models/effort_options).
   `route_capability_warnings()` already warns that chatgpt_oauth visibility differs
   from the api-key seed — the per-(provider, auth_mode, credential) cache is the
   structural version of that warning.
5. **Test blast radius (backend)**: `tests/test_model_routing.py` (seed membership
   pins `claude-opus-4-8`/`gpt-5.5`, warnings, route store), `test_model_route_store`,
   `test_ai_research_route`, `test_card_synthesis`, `test_monitor` (model refs).
   CLI/discord tests referencing `MODEL_CATALOG` re-exports.
6. **New-generation facts are UNVERIFIED**: user reports Anthropic **Fable 5** and an
   OpenAI **gpt-5.6 family (3 models — "Sol/Terra/Luna" per the Sol review)**. Exact
   model IDs, context/output limits, effort semantics, and account visibility are
   **not** in this plan — Task 0 verifies them live. **No id in this plan's examples
   may be trusted until Task 0 emits the verified table.**

---

## Decisions Locked By This Plan

1. **Registry is code, cache is DB, picker is the intersection** (P2.7 adopted
   architecture). Capability facts (limits/effort/thinking/tier) are code-reviewed
   constants in `src/model_capabilities.py`; the DB holds ONLY discovery observations
   (what a credential saw, when). Neither alone decides the picker.
2. **Behavior-identical consolidation**: for every model id resolvable today, the
   registry-backed helpers must return byte-identical values to the current tables
   (same limits, same booleans, same effort tuples, same prefix-match precedence).
   Divergence = stop-loss, not a silent fix. Known exception, explicitly ruled here:
   `get_effort_options("claude-opus-4-8")` changes `None` → opus-tier effort tuple
   (**bug fix**, recorded in the test as such).
3. **Tier model**: every registry entry carries `tier: "current" | "legacy"`.
   Current = shown by default; legacy = resolvable (configs that pin it keep working,
   `find_model` aliases keep working) but only listed in Advanced. Nothing is deleted.
4. **Effective picker default = verified-usable only** (Sol ruling, user-adopted):
   `verified` = (discovery cache for the ACTIVE credential) ∩ (registry `current` +
   executable for that provider/auth_mode). `advanced` = legacy tier + custom ids +
   unverified seeds. **Empty-cache state**: `verified` is empty and the response says
   so (`cache_state: "never_discovered"`), the UI shows the seed list in Advanced with
   an explicit 「跑一次模型探索以驗證」 nudge — we do NOT silently promote seeds to
   verified.
5. **The saved route model is always selectable** (existing researchModels invariant,
   extended to Settings): whatever a route currently pins appears in the options even
   if unverified/legacy — flagged, never hidden, never auto-changed.
6. **Discovery cache is observational, append-per-run**: keyed by (provider,
   auth_mode, credential_id); a successful discovery REPLACES that key's rows in one
   transaction; a failed discovery NEVER clobbers existing cache. Raw secrets never
   enter the table (credential_id only).
7. **`/config/model-catalog` changes are additive**: existing fields keep their shape
   (frontend fixture tests must not need edits); the effective view rides in new
   fields.
8. **New model entries carry provenance**: `source_url` + `verified_at` (the Task 0
   date), same discipline as `model_routing.ModelOption` today. Values from provider
   docs + live discovery only — never from memory/training data.
9. **Fable 5 / gpt-5.6 are additive entries**: no existing default flips in this slice
   except the two STALE literals ruled here — `agents/config.py:43`
   `openai_model "gpt-5.4"` → the verified current default-tier OpenAI model, and the
   CLI catalog gaining the missing current generation. Task-route recommendations
   (`model_routing.TASKS`) stay unchanged (changing recommendations is a product
   decision for a later ruling once live behavior/cost is observed).
10. **House store pattern** for the cache table (profile_state.db, WAL best-effort,
    busy_timeout 5000, mkdir parents, idempotent schema) — same as PortfolioStore.

---

## Files

Create:

- `src/model_capabilities.py`
- `src/model_discovery_cache.py`
- `tests/test_model_capabilities.py`
- `tests/test_model_discovery_cache.py`

Modify:

- `src/model_routing.py` (seed derives from registry; effective-view helper)
- `src/agents/shared/model_catalog.py` (compat shim over registry)
- `src/agents/anthropic_agent/agent.py` (capability tables → registry reads)
- `src/agents/openai_agent/agent.py` (same)
- `src/agents/shared/context_manager.py` (same)
- `src/agents/config.py` (stale default literal)
- `src/model_credentials.py` (discovery write-through + cached read)
- `src/api/routes/config_routes.py` (catalog response + discovery response additive
  fields)
- `apps/arkscope-web/src/api.ts` (additive DTO fields)
- `apps/arkscope-web/src/ModelRoutingSection.tsx` (verified-first picker + Advanced)
- `apps/arkscope-web/src/ModelRoutingSection.test.ts`
- `tests/test_model_routing.py`
- `docs/design/PROJECT_PRIORITY_MAP.md`, this plan (status flips)

Likely-touched (ledger sweep during Task 5, exact edits determined by RED runs):

- `tests/test_ai_research_route.py`, `tests/test_card_synthesis.py`,
  `tests/test_monitor.py`, CLI tests importing `MODEL_CATALOG` re-exports.

---

## Stop-Loss Triggers

Stop and report before continuing if:

- Task 0 cannot verify a gpt-5.6 model id via provider docs AND live discovery →
  land Fable 5 only, file the gpt-5.6 seed as a pending follow-up. **Never invent an
  id.** Same rule per-model: only verified ids enter the registry.
- Consolidation would CHANGE any existing model's derived value (limit, boolean,
  effort tuple, prefix precedence) other than the ruled opus-4.8 effort-options bug
  fix.
- The registry needs a DAL/DB/network import (it must stay pure code).
- `/config/model-catalog` or `/config/model-discovery` cannot stay shape-compatible
  (frontend fixture tests would need edits for non-additive reasons).
- Supporting a new model requires agent-loop changes beyond registry-driven flags
  (e.g., a provider rejects a parameter the loop always sends) → file a follow-up
  slice; do not widen this one.
- The discovery cache would need to store secrets or raw tokens.
- Effective-view logic wants to auto-rewrite a saved route.

---

## Review Gates

1. **Equivalence table**: `tests/test_model_capabilities.py` pins, for EVERY model id
   resolvable today, that the new helpers return exactly the current values
   (generated from the grounding table in this plan, not re-derived).
2. **Single-source grep**: after Task 2,
   `rg -n "claude-opus-4|claude-sonnet-4|claude-haiku|gpt-5\." src/agents/anthropic_agent/agent.py src/agents/openai_agent/agent.py src/agents/shared/context_manager.py`
   returns **no model-id literals** (imports/comments referencing the registry are
   fine — the gate is: no local fact tables).
3. **Prefix precedence**: `gpt-5.4-mini` resolves before `gpt-5.4`; the registry
   sorts longest-prefix-first internally so ordering bugs are structural, not
   list-order luck.
4. **Provenance**: every registry entry has non-empty `source_url` + `verified_at`;
   new-generation entries carry the Task 0 date.
5. **Cache contracts**: per-key replace, failure-preserves, no-secret columns —
   pinned by tests.
6. **Effective view**: verified/advanced partition rules pinned incl. empty-cache
   state and the saved-route-always-selectable invariant.
7. **Frontend**: full vitest suite + typecheck + build; `ModelRoutingSection.test.ts`
   proves the default list hides legacy/unverified and Advanced reveals them.
8. **PG-unreachable smoke** stays `ok:true`, `pg_attempts:[]`.
9. **Full virgin A/B**: failure sets identical; passed delta = exactly the new tests;
   warnings/errors accounted.

---

## Task 0: Verify New-Generation Model Facts (no code)

**Purpose:** replace "user reports Fable 5 / gpt-5.6 exist" with verified facts.

Steps:

1. WebFetch the three sources from the map entry:
   `https://www.anthropic.com/claude/fable`,
   `https://developers.openai.com/api/docs/models`,
   `https://help.openai.com/en/articles/20001354`.
2. Run live discovery against the user's real credentials (existing
   `discover_models()` via a scratch script — read-only, no DB writes yet):
   confirm which new ids are actually VISIBLE to this account (gpt-5.6 family ids,
   `claude-fable-5`).
3. Emit the **verified facts table** into this plan (id, provider, context, max
   output, thinking/effort semantics, tier assignment, source URL, verified date):

   | id | provider | context | max output | thinking/effort | visible to account? |
   |----|----------|---------|-----------|-----------------|--------------------|
   | *(filled by Task 0 — empty until then)* | | | | | |

4. Per-model cost sanity line (pricing from docs) so the user can veto expensive
   defaults.

Commit: `docs: verify new model generation facts` (plan-only edit).

**Gate**: user acks the table before Task 1 seeds from it (a one-line 確認 is
enough; this is the "never from memory" boundary).

---

## Task 1: Capability Registry Module

**Files:** `src/model_capabilities.py`, `tests/test_model_capabilities.py`.

### Step 1: RED tests

```python
from src.model_capabilities import (
    ModelCapability,
    all_models,
    capability_for,
    current_models,
)


def test_equivalence_with_legacy_tables_for_every_known_id():
    # Values transcribed from the pre-consolidation tables (grounding §1) — NOT
    # re-derived. If consolidation changes any of these, that is a stop-loss.
    expected = {
        # id: (context_limit, max_output, adaptive_thinking, supports_effort)
        "claude-opus-4-8": (1_000_000, 128_000, True, True),
        "claude-opus-4-7": (1_000_000, 128_000, True, True),
        "claude-sonnet-4-6": (1_000_000, 64_000, True, True),
        "claude-haiku-4-5": (200_000, 64_000, False, False),
        "gpt-5.5": (1_050_000, 128_000, False, False),
        "gpt-5.4": (1_050_000, 128_000, False, False),
        "gpt-5.4-mini": (400_000, 128_000, False, False),
        "gpt-5.4-nano": (400_000, 128_000, False, False),
        "gpt-5.2": (400_000, 128_000, False, False),
    }
    for model_id, (ctx, out, adaptive, effort) in expected.items():
        cap = capability_for(model_id)
        assert cap is not None, model_id
        assert cap.context_limit == ctx, model_id
        assert cap.max_output == out, model_id
        assert cap.adaptive_thinking is adaptive, model_id
        assert (cap.effort_options != ()) is effort, model_id


def test_prefix_precedence_is_structural_not_list_order():
    assert capability_for("gpt-5.4-mini-2026-x").id == "gpt-5.4-mini"
    assert capability_for("gpt-5.4-2026-x").id == "gpt-5.4"
    assert capability_for("claude-haiku-4-5-20251001").id == "claude-haiku-4-5"


def test_unknown_model_returns_none_and_helpers_keep_fallbacks():
    assert capability_for("mystery-model") is None


def test_every_entry_carries_provenance():
    for cap in all_models():
        assert cap.source_url, cap.id
        assert cap.verified_at, cap.id
        assert cap.tier in ("current", "legacy"), cap.id


def test_new_generation_entries_present_and_current():
    # Ids/values come from the Task 0 verified table; this test is written AFTER
    # Task 0 lands and pins whatever it verified (Fable 5 mandatory; gpt-5.6 family
    # only if verified — see stop-loss).
    fable = capability_for("claude-fable-5")
    assert fable is not None and fable.tier == "current"
    assert fable.provider == "anthropic"


def test_legacy_tier_membership():
    for legacy_id in ("gpt-5.2", "gpt-5.2-codex", "gpt-5.4", "claude-opus-4-7"):
        cap = capability_for(legacy_id)
        assert cap is not None and cap.tier == "legacy", legacy_id


def test_current_models_excludes_legacy():
    ids = {cap.id for cap in current_models("openai")}
    assert "gpt-5.2" not in ids and "gpt-5.5" in ids
```

Expected RED: module missing.

### Step 2: Implement

`ModelCapability` frozen dataclass: `id` (canonical prefix), `provider`
(`"anthropic" | "openai"`), `label`, `tier`, `context_limit`, `max_output`,
`adaptive_thinking: bool`, `effort_options: tuple[str, ...]` (empty = unsupported;
anthropic tuples reuse today's `EFFORT_OPTIONS_BY_MODEL` semantics), `aliases:
tuple[str, ...]`, `quality`/`speed`/`cost_tier`/`recommended_for` (routing-UI facts,
carried over from `model_routing.ModelOption`), `source_url`, `verified_at`, `notes`.

- `_REGISTRY: tuple[ModelCapability, ...]` — union of today's two seeds + capability
  tables + Task 0 additions. One entry per canonical id; legacy ids get
  `tier="legacy"`.
- `capability_for(model)`: longest-prefix match over canonical ids (sorted by
  `len(id)` desc at module import — structural precedence).
- `current_models(provider)` / `all_models(provider=None, include_legacy=True)`.
- Pure code: stdlib imports only.

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py -q
python -m compileall -q src/model_capabilities.py
```

Commit: `feat: add model capability registry`.

---

## Task 2: Converge the Capability Tables (behavior-identical)

**Files:** both agent modules, `context_manager.py`,
`src/agents/shared/model_catalog.py`, `src/model_routing.py`, their test files.

### Step 1: RED tests

Extend `tests/test_model_capabilities.py` with cross-module equivalence:

```python
def test_agent_helpers_now_read_the_registry():
    from src.agents.anthropic_agent.agent import (
        _get_model_max_output,
        _supports_adaptive_thinking,
        _supports_effort,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit

    assert _get_model_max_output("claude-opus-4-8") == 128_000
    assert _get_model_max_output("unknown-claude") == 64_000        # legacy fallback kept
    assert _supports_adaptive_thinking("claude-sonnet-4-6-future") is True
    assert _supports_effort("claude-haiku-4-5") is False
    assert _get_openai_max_output("gpt-5.4-nano") == 128_000
    assert _get_openai_max_output("totally-unknown") == 128_000     # legacy default kept
    assert get_model_context_limit("gpt-5.4-mini") == 400_000
    assert get_model_context_limit("unknown") == 200_000            # legacy default kept


def test_cli_effort_options_fixed_for_opus_48():
    # BUG FIX ruled by the plan: the old prefix table stopped at opus-4-7.
    from src.agents.shared.model_catalog import get_effort_options

    assert get_effort_options("claude-opus-4-8") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-opus-4-7") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-sonnet-4-6") == ("high", "medium", "low")
    assert get_effort_options("gpt-5.5") is None                    # OpenAI path unchanged


def test_model_routing_seed_derived_from_registry():
    from src.model_routing import MODEL_CATALOG, is_seed_model
    from src.model_capabilities import capability_for

    for option in MODEL_CATALOG:
        cap = capability_for(option.id)
        assert cap is not None and cap.provider == option.provider
    assert is_seed_model("openai", "gpt-5.5")


def test_find_model_aliases_still_resolve():
    from src.agents.shared.model_catalog import find_model

    assert find_model("opus").id.startswith("claude-opus")
    assert find_model("mini").id == "gpt-5.4-mini"
    assert find_model("codex").id == "gpt-5.2-codex"                # legacy stays resolvable
```

Expected RED: helpers still read local tables; opus-4.8 effort returns None.

### Step 2: Implement

- Replace the five fact tables with registry reads; **keep every public/module
  function signature and every fallback constant** (`64000`, `_OPENAI_DEFAULT_MAX_OUTPUT`,
  `_DEFAULT_CONTEXT_LIMIT`) exactly as today.
- `model_catalog.MODEL_CATALOG` / `model_routing.MODEL_CATALOG` become derived views
  (same shapes: `ModelEntry` / `ModelOption`) built from the registry at import time —
  consumers (cli/discord/config_routes/model_credentials) untouched in this task.
- `model_routing.model_provider()` gains nothing (prefixes still match new ids).

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py tests/test_card_synthesis.py -q
rg -n "claude-opus-4|claude-sonnet-4|claude-haiku|gpt-5\." src/agents/anthropic_agent/agent.py src/agents/openai_agent/agent.py src/agents/shared/context_manager.py
```

The `rg` gate must show no local fact tables (see Review Gate 2).

Commit: `feat: converge model facts onto the registry`.

---

## Task 3: Discovery Cache Store

**Files:** `src/model_discovery_cache.py`, `src/model_credentials.py`,
`tests/test_model_discovery_cache.py`.

### Step 1: RED tests

```python
from src.model_discovery_cache import ModelDiscoveryCache


def test_successful_discovery_replaces_the_credential_scope(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record(
        provider="openai", auth_mode="api_key", credential_id="cred-1",
        models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}],
    )
    cache.record(
        provider="openai", auth_mode="api_key", credential_id="cred-1",
        models=[{"id": "gpt-5.6-x", "label": "x", "source": "provider_api"}],
    )
    rows = cache.get(provider="openai", auth_mode="api_key", credential_id="cred-1")
    assert [r.model_id for r in rows.models] == ["gpt-5.6-x"]       # replaced, not appended
    assert rows.discovered_at is not None


def test_scopes_are_independent(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record(provider="openai", auth_mode="api_key", credential_id="a",
                 models=[{"id": "m1", "label": "m1", "source": "provider_api"}])
    cache.record(provider="openai", auth_mode="chatgpt_oauth", credential_id="b",
                 models=[{"id": "m2", "label": "m2", "source": "provider_api"}])
    assert [r.model_id for r in cache.get(provider="openai", auth_mode="api_key",
                                          credential_id="a").models] == ["m1"]


def test_empty_scope_reports_never_discovered(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    out = cache.get(provider="anthropic", auth_mode="api_key", credential_id="none")
    assert out.models == [] and out.discovered_at is None


def test_schema_has_no_secret_columns(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    with cache._connect() as conn:
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(model_discovery_cache)")}
    assert not (cols & {"secret", "api_key", "token"})
```

And in `tests/test_model_routing.py` (or a new credentials test): monkeypatch the
provider call inside `discover_models` to (a) succeed → cache written; (b) raise →
**pre-existing cache rows survive** (Decision 6).

Expected RED: module missing; `discover_models` has no cache seam.

### Step 2: Implement

- House store pattern (PortfolioStore-style `_connect`), table
  `model_discovery_cache(provider, auth_mode, credential_id, model_id, label,
  source, discovered_at)`, PK `(provider, auth_mode, credential_id, model_id)`;
  single-transaction delete+insert per `record()`.
- `discover_models()` write-through: only on `status == "ok"` with
  `source == "provider_api"` results; the chatgpt_oauth driver path in
  `config_routes.discover_provider_models` records under `auth_mode="chatgpt_oauth"`.
  Failure/missing-credential paths return exactly what they do today and leave the
  cache untouched.
- `POST /config/model-discovery` response gains additive `cached_at`.

### Step 3: Verify + commit

```bash
pytest tests/test_model_discovery_cache.py tests/test_model_routing.py -q
```

Commit: `feat: cache per-credential model discovery`.

---

## Task 4: Effective View + Settings Picker

**Files:** `src/model_routing.py` (or a sibling `src/model_effective.py` if routing
would need cache imports — keep routing pure; decide at implementation, the API is
what's pinned), `src/api/routes/config_routes.py`, `apps/arkscope-web/src/api.ts`,
`ModelRoutingSection.tsx` + its test, `tests/test_model_routing.py`.

### Step 1: RED tests (backend)

```python
def test_effective_view_partitions_verified_and_advanced(tmp_path):
    # cache: gpt-5.5 (current) + gpt-5.2 (legacy) + mystery-model (not in registry)
    # registry current for openai: gpt-5.5 (+ Task 0 additions)
    view = effective_model_view(
        provider="openai", auth_mode="api_key", credential_id="cred-1",
        route_model="gpt-5.4", cache=populated_cache,
    )
    verified_ids = [m["id"] for m in view["verified"]]
    advanced_ids = [m["id"] for m in view["advanced"]]
    assert "gpt-5.5" in verified_ids                 # visible ∩ current
    assert "gpt-5.2" in advanced_ids                 # visible but legacy
    assert "mystery-model" in advanced_ids           # visible but unknown → custom
    assert "gpt-5.4" in advanced_ids                 # saved route model always selectable
    assert view["cache_state"] == "ok"


def test_effective_view_never_discovered_keeps_verified_empty(tmp_path):
    view = effective_model_view(
        provider="anthropic", auth_mode="api_key", credential_id="none",
        route_model="claude-opus-4-8", cache=empty_cache,
    )
    assert view["verified"] == []
    assert view["cache_state"] == "never_discovered"
    assert any(m["id"] == "claude-opus-4-8" for m in view["advanced"])
    # seeds surface in advanced, explicitly flagged
    assert all(m["badge"] in ("seed", "legacy", "custom", "route") for m in view["advanced"])
```

Route test: `GET /config/model-catalog` still contains the OLD top-level fields
byte-shape-compatible AND a new `effective` block per provider (handler-direct,
fake cache; auth-mode resolution reuses whatever the route already uses for
`route_capability_warnings`).

### Step 2: RED tests (frontend, house harness — createRoot/act/stubFetch)

- default dropdown lists only `verified` entries;
- an「進階」toggle reveals `advanced` with per-entry badge text (舊版/未驗證/自訂);
- `cache_state: "never_discovered"` renders the 「跑一次模型探索以驗證」 nudge
  wired to the EXISTING discovery button;
- the saved route model renders selected even when it sits in `advanced`.

### Step 3: Implement

Backend partition function + additive API block; frontend picker split. No changes
to how routes are saved (`PUT /config/model-routes` untouched — Decision 5 means the
picker never blocks a custom id; the existing custom-model escape hatch stays).

### Step 4: Verify + commit

```bash
pytest tests/test_model_routing.py -q
cd apps/arkscope-web && npm test && npm run typecheck && npm run build
```

Commit: `feat: verified-first model picker`.

---

## Task 5: New Models Land + CLI/Discord/Defaults Sweep

**Files:** `src/model_capabilities.py` (Task 0 facts), `src/agents/config.py`,
ledger-swept test files.

### Step 1: RED tests

- Registry entries for the Task 0-verified ids (extend
  `test_new_generation_entries_present_and_current` with exact verified values —
  context/output/effort per the Task 0 table).
- `capability_for` drives the agent helpers for new ids (e.g. Fable adaptive
  thinking True, effort tuple per docs; gpt-5.6 output limit per docs — **values
  from Task 0, not from this plan**).
- `model_provider()` classifies every new id.
- `find_model("fable")` resolves via alias.
- `agents/config.py` default: assert the dataclass default equals the verified
  current default-tier id (exact id from Task 0).

### Step 2: Implement + ledger sweep

Add entries; update `agents/config.py:43`; run the full model-referencing test set
and fix count/membership pins the additions legitimately move (sweep by NEW ids
across `tests/`, not just counts — enum-family lesson):

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py \
  tests/test_model_route_store.py tests/test_ai_research_route.py \
  tests/test_card_synthesis.py tests/test_monitor.py -q
rg -n "claude-fable|gpt-5\.6" tests/ src/ --stats
```

### Step 3: Optional live smoke (user-gated, cost note)

One minimal live call per newly-landed model id (cheapest gpt-5.6 family member;
Fable 5 only with explicit user OK — premium pricing) to prove the registry's
effort/thinking flags produce an accepted request. Skippable; if skipped, the plan
records `runtime-unverified` next to the entry.

Commit: `feat: land fable-5 and gpt-5.6 generation`.

---

## Task 6: Gates, Full A/B, Docs Closeout

1. Focused backend: all files from Task 5's sweep + capability/cache/routing suites.
2. Frontend: full vitest + typecheck + build.
3. Static gates: Review Gate 2 grep; `rg -n "psycopg2|postgres" src/model_capabilities.py src/model_discovery_cache.py` → empty.
4. `python src/smoke/pg_unreachable_e2e.py` → `ok:true`, `pg_attempts:[]`.
5. Full virgin A/B (base = plan-merge commit, head = tip): failure sets identical,
   passed delta = exactly the new tests, warnings/errors accounted.
6. Docs: this plan → IMPLEMENTED FOR REVIEW; map §P2.7 status + decision-log entry;
   MEMORY.md Active Models section rewritten from the registry (kills the STALE
   banner).

Implementation stops review-ready before merge; reviewer (user) reruns focused
suites and the final A/B; merge on explicit approval; live verification = Settings
discovery round + picker inspection + (optional) Task 5 smoke.

---

## Expected Commit Sequence

1. `docs: verify new model generation facts` (Task 0, plan-only)
2. `feat: add model capability registry`
3. `feat: converge model facts onto the registry`
4. `feat: cache per-credential model discovery`
5. `feat: verified-first model picker`
6. `feat: land fable-5 and gpt-5.6 generation`
7. `docs: close model capability catalog build`
