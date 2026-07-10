# Model Capability Registry + Discovery Cache + Effective Picker (P2.7)

> **Status: DRAFT FOR REVIEW (round 2) 2026-07-10.** Implements PROJECT_PRIORITY_MAP
> §P2.7. Round-1 review (user + gpt-5.6 Sol) returned 6 must-fix + 3 should-fix —
> all verified against code and folded in: the equivalence table now transcribes
> ACTUAL behavior (opus-4.8 context is 200K-by-fallback today), the drift inventory
> gained the compaction/1M-beta tables, registry membership is decoupled from
> account entitlement, the cache got run-metadata (zero-model + seed_only states),
> the effective view became per-task with a real credential resolver, and **no
> defaults or task recommendations flip in this slice**. Docs-only; no runtime
> implementation has started. Author: Claude (implementer); reviewer: user.

**Goal:** One code-reviewed **capability registry** becomes the single source for
model facts (context/output limits, thinking/effort/compaction support, context
mode, tier); a **DB discovery cache** records which models each credential actually
saw and when; an **effective picker** shows the per-task intersection by default.
New-generation models (Anthropic Fable 5, OpenAI gpt-5.6 family) land with
slice-time-verified facts. CLI, discord, Settings routing, agents, subagent, and
context manager all read the registry.

**Non-goals:** ANY default or recommendation flip (`agents/config.py` model
defaults, `model_routing.TASKS` recommended models — a separate slice after
live/cost observation; ruled in round-1 review); `config/user_profile.yaml`
scoring-model choices; scheduled/automatic discovery refresh (v1 manual);
Ollama / OpenAI-compatible providers (schema must not preclude, no entries);
pricing display beyond `cost_tier`; removing the `model_catalog.py` module path
(compat shim; deletion later); run/replay storage changes.

---

## Current Grounding (verified against code 2026-07-10, round-2 corrected)

1. **Nine drift sites** hold model facts today:
   - `src/model_routing.py` — pydantic `ModelOption` seed `MODEL_CATALOG` (7 models,
     newest opus-4.8/gpt-5.5; carries `supports_structured_output` /
     `supports_tool_calling` — the registry schema must keep both), `TASKS`
     recommendations, per-provider `EFFORT_OPTIONS`, `model_provider()` prefix
     heuristic, `is_seed_model()`. `CATALOG_VERIFIED_AT = "2026-06-06"`.
   - `src/agents/shared/model_catalog.py` — dataclass `ModelEntry` seed (8 models,
     newest **opus-4.7**/gpt-5.5), `find_model()` (id/name/alias/partial),
     `EFFORT_OPTIONS_BY_MODEL` (**stale: stops at opus-4-7, so
     `get_effort_options("claude-opus-4-8") → None`** — CLI offers no effort options
     for opus-4.8), `VALID_ANTHROPIC_EFFORT`/`VALID_REASONING_EFFORT`.
   - `src/agents/anthropic_agent/agent.py:102` — `_ADAPTIVE_THINKING_MODELS`,
     `_EFFORT_MODELS` (both `{opus-4-8, opus-4-7, sonnet-4-6}`), `_MODEL_MAX_OUTPUT`
     (128K/128K/64K) + prefix helpers.
   - `src/agents/anthropic_agent/agent.py:32` — `_COMPACTION_BETA =
     "compact-2026-01-12"`, `_COMPACTION_MODELS = {opus-4-7, sonnet-4-6}`
     (**opus-4-8 absent** — whether that is a real API gap or staleness is a Task 0
     verification item, NOT pre-ruled) + `_supports_compaction()`.
   - `src/agents/shared/subagent.py:25` — `_1M_GA_MODELS = {opus-4-7, sonnet-4-6}`,
     `_1M_BETA_MODELS = {sonnet-4-5, opus-4-5}`, `_EXTENDED_CONTEXT_BETA =
     "context-1m-2025-08-07"`, `_use_extended_context_beta()`; **`cli.py:93` imports
     both** for the `/context` toggle.
   - `src/agents/openai_agent/agent.py:64` — `_OPENAI_MODEL_MAX_OUTPUT` (5 ids, all
     128000), `_OPENAI_DEFAULT_MAX_OUTPUT = 128000`.
   - `src/agents/shared/context_manager.py:58` — `_MODEL_CONTEXT_LIMITS` (8 prefixes,
     specific-first), `_DEFAULT_CONTEXT_LIMIT = 200_000`, `get_model_context_limit()`.
     **REALITY CHECK (round-1 MF1): `claude-opus-4-8` is NOT in this table — it
     resolves to the 200_000 fallback today.** `gpt-5.2-codex` resolves via the
     `gpt-5.2` prefix (400_000 context / 128_000 output).
   - `src/agents/config.py:43` — `openai_model: str = "gpt-5.4"` (stale, but **NOT
     changed in this slice** — see Non-goals).
   - Frontend: the routing picker is `ModelRoutingSection` **inside
     `apps/arkscope-web/src/Settings.tsx:2011`** (exported; the test file
     `ModelRoutingSection.test.ts` imports from `./Settings`). Fixtures are local
     objects — backend seed changes don't break them while responses stay
     shape-compatible.
2. **Import direction is safe for a top-level registry**: `model_credentials.py:26`
   imports from `src.model_routing`; cli/discord import from
   `src.agents.shared.model_catalog`; `subagent.py`/`context_manager.py` are leaves.
   A new pure-code `src/model_capabilities.py` is importable by all without cycles.
3. **Discovery is live-only, uncached**: `model_credentials.py:901 discover_models()`
   → OpenAI `client.models.list()` / Anthropic `GET /v1/models`; missing-credential
   and error paths fall back to `_seed_models()`. `POST /config/model-discovery`
   (`config_routes.py:589`) routes oauth drivers to `driver.discover_models()` —
   **`claude_code_oauth` returns `status="ok"` with SEED models** (no live listing
   exists for that channel): a cache that only stores provider_api results would
   loop the user on a "never discovered" nudge forever (round-1 MF4).
4. **Active-credential resolution is insufficient for a cache key**:
   `config_routes.py:77 _active_auth_mode()` returns only `auth_type`, reads only
   the DB `CredentialStore.list()` (env-only active keys resolve to None), and never
   returns a credential id. The effective view needs a resolver that returns
   `(credential_id, auth_mode)` from the same inventory `provider_credentials()`
   builds (env-derived rows included).
5. **Catalog API**: `GET /config/model-catalog` (`config_routes.py:227`) returns
   `catalog().model_dump()`. Route model pins are PER TASK (three `TaskRoute`s) —
   an effective view keyed only by provider cannot express three different pinned
   models (round-1 MF3).
6. **Test blast radius (backend)**: `tests/test_model_routing.py` (seed pins,
   warnings, store), `test_model_route_store`, `test_ai_research_route`,
   `test_card_synthesis`, `test_monitor`, CLI tests importing `MODEL_CATALOG`
   re-exports.
7. **New-generation facts are UNVERIFIED here**: Anthropic **Fable 5** and OpenAI
   **gpt-5.6 family** have official per-model pages (round-1 review supplied):
   - Fable 5: https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5
   - Effort: https://platform.claude.com/docs/en/build-with-claude/effort
   - Context windows: https://platform.claude.com/docs/en/build-with-claude/context-windows
   - gpt-5.6 Sol: https://developers.openai.com/api/docs/models/gpt-5.6-sol
   - gpt-5.6 Terra: https://developers.openai.com/api/docs/models/gpt-5.6-terra
   - gpt-5.6 Luna: https://developers.openai.com/api/docs/models/gpt-5.6-luna
   Known contract shape to verify (NOT to trust from this plan): Fable 5 thinking is
   **always-on** (an explicit disable is rejected) with effort control and
   compaction/1M-context support — which is why the registry models thinking as a
   MODE, not a boolean.

---

## Decisions Locked By This Plan

1. **Registry is code, cache is DB, picker is the per-task intersection.**
   Capability facts are code-reviewed constants in `src/model_capabilities.py`; the
   DB holds ONLY discovery observations. Neither alone decides the picker.
2. **Registry membership = official documentation; entitlement = cache** (round-1
   MF5). A model documented on an official per-model page enters the registry
   regardless of whether any local credential can see it; whether THIS user's
   credential sees it lives exclusively in the discovery cache. Discovery results
   never add or remove registry entries.
3. **Behavior-identical consolidation with EXACTLY TWO ruled bug fixes.** For every
   model id resolvable today, registry-backed helpers return byte-identical values —
   the equivalence test transcribes today's ACTUAL outputs (including the opus-4.8
   context fallback), and a completeness assertion proves no id escaped the table.
   The two ruled fixes, asserted as such in tests:
   - **Fix A**: `get_effort_options("claude-opus-4-8")` `None` → opus effort tuple.
   - **Fix B**: `get_model_context_limit("claude-opus-4-8")` `200_000` (missing-entry
     fallback) → `1_000_000` per the official context-windows doc.
   Anything else that would change (including `_COMPACTION_MODELS` membership for
   opus-4.8) is a Task 0 verification item that must come back to the reviewer as an
   explicit additional ruling — not a silent edit.
4. **Registry schema carries the full existing capability surface** (round-1 MF2):
   `thinking_mode: "none" | "adaptive_opt_in" | "adaptive_always_on"` (Fable is
   always-on; today's opus/sonnet are opt-in; OpenAI ids are none),
   `effort_options: tuple[str, ...]`, `supports_compaction: bool`,
   `context_mode: "standard" | "ga_1m" | "beta_1m"`, `context_limit`, `max_output`,
   `supports_structured_output: bool`, `supports_tool_calling: bool`, plus
   `tier`/`aliases`/`quality`/`speed`/`cost_tier`/`recommended_for`/`source_url`/
   `verified_at`/`notes`.
5. **Tier assignment (explicit, reviewable)**: `current` = claude-opus-4-8,
   claude-sonnet-4-6, claude-haiku-4-5, gpt-5.5, gpt-5.4, gpt-5.4-mini, gpt-5.4-nano
   (+ Task 5 verified additions). `legacy` = claude-opus-4-7, gpt-5.2,
   gpt-5.2-codex. Rationale: the gpt-5.4 family is actively routed/recommended
   today (flipping it out of the default picker while `TASKS` still recommends
   gpt-5.4-mini would contradict Non-goals); opus-4.7's own routing note already
   says legacy. Nothing is deleted; legacy stays resolvable.
6. **Effective picker is PER TASK and default = verified-usable only**: for each
   `TaskId`, `verified` = (discovery cache for the resolved active credential) ∩
   (registry `current` + executable under the resolved auth_mode); `advanced` =
   legacy tier + custom ids + unverified seeds + that task's pinned route model
   when it isn't verified. The saved route model is always selectable — flagged,
   never hidden, never auto-changed.
7. **Cache states are explicit** (round-1 MF4): `ok` (live listing succeeded — even
   with zero models), `never_discovered` (no run recorded for the scope),
   `seed_only` (the channel has no live listing — e.g. claude_code_oauth; the UI
   shows seed candidates with a 「此通道無法線上列出模型」 badge and NO re-run
   nudge loop). Run metadata is stored separately from model rows so
   zero-model success is representable.
8. **Discovery cache is observational**: keyed by (provider, auth_mode,
   credential_id); a successful run REPLACES that scope's rows + run metadata in one
   transaction; a failed run records nothing and clobbers nothing. No secret
   columns; credential ids only.
9. **`/config/model-catalog` and `/config/model-discovery` changes are additive**
   (frontend fixture tests must not need edits for shape reasons).
10. **New model entries carry provenance** (`source_url` = the per-model official
    page, `verified_at` = Task 0 date). Values from official docs only — never from
    memory/training data. Live discovery informs the CACHE, not the registry.
11. **House store pattern** for the cache (profile_state.db, WAL best-effort,
    busy_timeout 5000, idempotent schema).

---

## Files

Create:

- `src/model_capabilities.py`
- `src/model_discovery_cache.py`
- `tests/test_model_capabilities.py`
- `tests/test_model_discovery_cache.py`

Modify:

- `src/model_routing.py` (seed derives from registry)
- `src/agents/shared/model_catalog.py` (compat shim over registry)
- `src/agents/anthropic_agent/agent.py` (capability + compaction tables → registry)
- `src/agents/openai_agent/agent.py` (output table → registry)
- `src/agents/shared/context_manager.py` (context table → registry)
- `src/agents/shared/subagent.py` (1M GA/beta sets → registry `context_mode`)
- `src/model_credentials.py` (discovery write-through + cached read + resolver)
- `src/api/routes/config_routes.py` (active-credential resolver use; additive
  effective/cached fields)
- `apps/arkscope-web/src/api.ts` (additive DTOs)
- `apps/arkscope-web/src/Settings.tsx` (`ModelRoutingSection` — verified-first
  picker + Advanced; component lives at `Settings.tsx:2011`)
- `apps/arkscope-web/src/ModelRoutingSection.test.ts` (imports from `./Settings`)
- `tests/test_model_routing.py`
- `docs/design/PROJECT_PRIORITY_MAP.md`, this plan (status flips)

NOT modified (ruled): `src/agents/config.py`, `model_routing.TASKS`,
`config/user_profile.yaml`.

Likely-touched (Task 5 ledger sweep, determined by RED runs):
`tests/test_ai_research_route.py`, `tests/test_card_synthesis.py`,
`tests/test_monitor.py`, CLI tests importing `MODEL_CATALOG` re-exports.

---

## Stop-Loss Triggers

Stop and report before continuing if:

- A model lacks an official per-model documentation page → it does NOT enter the
  registry (regardless of discovery visibility). **Never invent an id.**
- Consolidation would change any existing model's derived value beyond ruled Fixes
  A/B — including `_COMPACTION_MODELS` membership — without an explicit new ruling.
- The registry needs a DAL/DB/network import.
- `/config/model-catalog` or `/config/model-discovery` cannot stay shape-compatible.
- A new model requires agent-loop changes beyond registry-driven flags → follow-up
  slice, do not widen.
- The discovery cache would need secrets/tokens.
- Effective-view logic wants to auto-rewrite a saved route.
- Any default or recommendation flip sneaks in (Non-goals).

---

## Review Gates

1. **ID-set completeness THEN equivalence**: the test first asserts the registry id
   set ⊇ the union of every pre-consolidation source (both catalogs' ids + every
   key of `_MODEL_MAX_OUTPUT` / `_OPENAI_MODEL_MAX_OUTPUT` / `_MODEL_CONTEXT_LIMITS`
   / `_ADAPTIVE_THINKING_MODELS` / `_EFFORT_MODELS` / `_COMPACTION_MODELS` /
   `_1M_GA_MODELS` / `_1M_BETA_MODELS` / `EFFORT_OPTIONS_BY_MODEL`, enumerated
   literally in the test), then compares values per id. A model missing from the
   hand-written expected table fails loudly instead of passing silently.
2. **Single-source grep**: after Task 2,
   `rg -n "claude-opus-4|claude-sonnet-4|claude-haiku|gpt-5\." src/agents/anthropic_agent/agent.py src/agents/openai_agent/agent.py src/agents/shared/context_manager.py src/agents/shared/subagent.py`
   shows no local fact tables.
3. **Prefix precedence structural** (`gpt-5.4-mini` before `gpt-5.4`; date-suffixed
   ids resolve to their family).
4. **Alias integrity**: `capability_for` resolves official aliases; no alias maps to
   two entries; no alias collides with another entry's canonical id.
5. **Provenance**: every entry has non-empty per-model `source_url` + `verified_at`.
6. **Cache contracts**: replace-on-success, preserve-on-failure, zero-model-success
   representable, `seed_only` state, no secret columns.
7. **Effective view**: per-task partition rules pinned incl. `never_discovered`,
   `seed_only`, and route-model-always-selectable.
8. **Frontend**: full vitest + typecheck + build; picker test proves default hides
   legacy/unverified, Advanced reveals with badges, `seed_only` shows no nudge loop.
9. **PG-unreachable smoke** `ok:true`, `pg_attempts:[]`.
10. **Full virgin A/B**: failure sets identical; passed delta = exactly the new
    tests; warnings/errors accounted.

---

## Task 0: Verify New-Generation + Contested Facts (no code)

**Purpose:** replace claims with verified facts; separate registry facts (docs)
from entitlement observations (discovery).

Steps:

1. WebFetch the per-model official pages (grounding §7): Fable 5 announcement +
   effort doc + context-windows doc; gpt-5.6 Sol / Terra / Luna model pages.
   Extract per model: canonical id, official aliases (e.g. whether `gpt-5.6`
   routes to Sol), context window, max output, thinking contract
   (always-on/opt-in/none), effort set, compaction support, context mode,
   structured-output/tool support, pricing line.
2. Resolve the **contested existing facts** from official docs:
   - opus-4.8 context limit (expected 1M per docs → confirms ruled Fix B);
   - opus-4.8 compaction support (today's `_COMPACTION_MODELS` omits it — if docs
     say supported, come back for an explicit Fix C ruling; if unsupported/unclear,
     keep behavior);
   - whether the `context-1m-2025-08-07` beta header story still matches docs for
     the legacy `_1M_BETA_MODELS`.
3. Run live discovery once per configured credential (read-only scratch script) —
   this informs **cache expectations and Task 5 smoke targets only**, never
   registry membership.
4. Emit the verified facts table into this plan + a pricing sanity line per model:

   | id | provider | context | max output | thinking_mode | effort | compaction | context_mode | source page | account-visible? |
   |----|----------|---------|-----------|---------------|--------|------------|--------------|-------------|------------------|
   | *(filled by Task 0)* | | | | | | | | | |

Commit: `docs: verify new model generation facts`.

**Gate**: user acks the table (and any Fix C proposal) before Task 1 seeds from it.

---

## Task 1: Capability Registry Module (existing models only)

**Files:** `src/model_capabilities.py`, `tests/test_model_capabilities.py`.

New-generation entries are **NOT** in this task (round-1 MF5 TDD-order fix) — Task 1
covers exactly today's models so the equivalence/completeness gates are meaningful.

### Step 1: RED tests

```python
from src.model_capabilities import (
    ModelCapability,
    all_models,
    capability_for,
    current_models,
)

# Every id named by ANY pre-consolidation source (grounding §1) — enumerated
# literally so a registry omission fails here, not in a downstream prefix match.
_PRE_CONSOLIDATION_IDS = {
    # routing seed
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
    "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    # cli seed extras
    "gpt-5.4-nano", "gpt-5.2", "gpt-5.2-codex",
    # capability-table extras
    "claude-sonnet-4-5", "claude-opus-4-5",   # _1M_BETA_MODELS
}


def test_registry_covers_every_pre_consolidation_id():
    missing = {mid for mid in _PRE_CONSOLIDATION_IDS if capability_for(mid) is None}
    assert missing == set()


def test_equivalence_transcribes_actual_current_behavior():
    # Values are today's ACTUAL helper outputs (round-1 MF1) — including the
    # opus-4.8 context fallback. Ruled fixes A/B are asserted separately in Task 2
    # AFTER convergence; here the registry documents pre-fix reality via
    # `capability_for(...).context_limit` EXCEPT where the ruled fix applies at
    # registry level — so this test pins the REGISTRY (post-fix) values and the
    # separate `test_ruled_fixes_are_the_only_divergences` pins the delta.
    expected = {
        # id: (context_limit, max_output, thinking_mode, effort?, compaction, context_mode)
        "claude-opus-4-8": (1_000_000, 128_000, "adaptive_opt_in", True, False, "ga_1m"),  # Fix B: was 200_000 fallback; compaction stays False pending Task 0
        "claude-opus-4-7": (1_000_000, 128_000, "adaptive_opt_in", True, True, "ga_1m"),
        "claude-sonnet-4-6": (1_000_000, 64_000, "adaptive_opt_in", True, True, "ga_1m"),
        "claude-haiku-4-5": (200_000, 64_000, "none", False, False, "standard"),
        "claude-sonnet-4-5": (200_000, 64_000, "none", False, False, "beta_1m"),
        "claude-opus-4-5": (200_000, 64_000, "none", False, False, "beta_1m"),
        "gpt-5.5": (1_050_000, 128_000, "none", False, False, "standard"),
        "gpt-5.4": (1_050_000, 128_000, "none", False, False, "standard"),
        "gpt-5.4-mini": (400_000, 128_000, "none", False, False, "standard"),
        "gpt-5.4-nano": (400_000, 128_000, "none", False, False, "standard"),
        "gpt-5.2": (400_000, 128_000, "none", False, False, "standard"),
        "gpt-5.2-codex": (400_000, 128_000, "none", False, False, "standard"),
    }
    assert set(expected) == _PRE_CONSOLIDATION_IDS  # table covers the full id set — a new id fails HERE, not silently
    for model_id, (ctx, out, tmode, effort, compact, cmode) in expected.items():
        cap = capability_for(model_id)
        assert cap.context_limit == ctx, model_id
        assert cap.max_output == out, model_id
        assert cap.thinking_mode == tmode, model_id
        assert (cap.effort_options != ()) is effort, model_id
        assert cap.supports_compaction is compact, model_id
        assert cap.context_mode == cmode, model_id


def test_ruled_fixes_are_the_only_divergences():
    """Documents round-1 ruling: exactly two behavior deltas vs pre-consolidation.
    Fix A: opus-4.8 CLI effort options (was None — prefix table stopped at 4-7).
    Fix B: opus-4.8 context limit (was 200_000 missing-entry fallback)."""
    cap = capability_for("claude-opus-4-8")
    assert cap.effort_options == ("max", "xhigh", "high", "medium", "low")  # Fix A
    assert cap.context_limit == 1_000_000                                    # Fix B


def test_prefix_precedence_is_structural_not_list_order():
    assert capability_for("gpt-5.4-mini-2026-x").id == "gpt-5.4-mini"
    assert capability_for("gpt-5.4-2026-x").id == "gpt-5.4"
    assert capability_for("gpt-5.2-codex-x").id == "gpt-5.2-codex"
    assert capability_for("claude-haiku-4-5-20251001").id == "claude-haiku-4-5"


def test_unknown_model_returns_none():
    assert capability_for("mystery-model") is None


def test_every_entry_carries_provenance_and_tier():
    for cap in all_models():
        assert cap.source_url and cap.verified_at, cap.id
        assert cap.tier in ("current", "legacy"), cap.id


def test_tier_assignment_matches_the_ruling():
    legacy = {cap.id for cap in all_models() if cap.tier == "legacy"}
    assert legacy == {"claude-opus-4-7", "gpt-5.2", "gpt-5.2-codex",
                      "claude-sonnet-4-5", "claude-opus-4-5"}


def test_current_models_excludes_legacy():
    ids = {cap.id for cap in current_models("openai")}
    assert "gpt-5.2" not in ids and {"gpt-5.5", "gpt-5.4-mini"} <= ids
```

(Note for reviewer: `claude-sonnet-4-5`/`claude-opus-4-5` enter as legacy `beta_1m`
entries because `_1M_BETA_MODELS` names them; their limits transcribe today's
fallback behavior — 200_000/64_000 — since no current table lists them.)

Expected RED: module missing.

### Step 2: Implement

`ModelCapability` frozen dataclass per Decision 4; `_REGISTRY` seeded from the
grounding tables; `capability_for()` = exact-alias match first, then
longest-prefix match (sorted by `len(id)` desc at import); `current_models()` /
`all_models()`. Pure stdlib.

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py -q
python -m compileall -q src/model_capabilities.py
```

Commit: `feat: add model capability registry`.

---

## Task 2: Converge the Nine Sites (behavior-identical + Fixes A/B)

**Files:** both agent modules, `context_manager.py`, `subagent.py`,
`model_catalog.py`, `model_routing.py`, their tests.

### Step 1: RED tests

```python
def test_agent_helpers_now_read_the_registry():
    from src.agents.anthropic_agent.agent import (
        _get_model_max_output, _supports_adaptive_thinking, _supports_effort,
        _supports_compaction,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit
    from src.agents.shared.subagent import _use_extended_context_beta

    assert _get_model_max_output("claude-opus-4-8") == 128_000
    assert _get_model_max_output("unknown-claude") == 64_000          # fallback kept
    assert _supports_adaptive_thinking("claude-sonnet-4-6-future") is True
    assert _supports_effort("claude-haiku-4-5") is False
    assert _supports_compaction("claude-sonnet-4-6") is True
    assert _supports_compaction("claude-opus-4-8") is False           # unchanged pending Task 0 ruling
    assert _get_openai_max_output("gpt-5.4-nano") == 128_000
    assert _get_openai_max_output("totally-unknown") == 128_000       # default kept
    assert get_model_context_limit("gpt-5.4-mini") == 400_000
    assert get_model_context_limit("claude-opus-4-8") == 1_000_000    # ruled Fix B
    assert get_model_context_limit("unknown") == 200_000              # fallback kept
    # 1M GA models need no beta header; legacy beta models do (when enabled)
    assert _use_extended_context_beta("claude-opus-4-7", True) is False
    assert _use_extended_context_beta("claude-sonnet-4-5", True) is True


def test_cli_effort_options_fixed_for_opus_48():
    from src.agents.shared.model_catalog import get_effort_options
    assert get_effort_options("claude-opus-4-8") == ("max", "xhigh", "high", "medium", "low")  # ruled Fix A
    assert get_effort_options("claude-sonnet-4-6") == ("high", "medium", "low")
    assert get_effort_options("gpt-5.5") is None


def test_derived_seeds_match_registry():
    from src.model_routing import MODEL_CATALOG, is_seed_model
    from src.model_capabilities import capability_for
    for option in MODEL_CATALOG:
        cap = capability_for(option.id)
        assert cap is not None and cap.provider == option.provider
        assert option.supports_structured_output == cap.supports_structured_output
        assert option.supports_tool_calling == cap.supports_tool_calling
    assert is_seed_model("openai", "gpt-5.5")


def test_find_model_aliases_still_resolve():
    from src.agents.shared.model_catalog import find_model
    assert find_model("opus").id.startswith("claude-opus")
    assert find_model("mini").id == "gpt-5.4-mini"
    assert find_model("codex").id == "gpt-5.2-codex"
```

Expected RED: helpers read local tables; opus-4.8 effort None; opus-4.8 context
200_000.

### Step 2: Implement

Replace the fact tables with registry reads; keep every function signature and
fallback constant. `_COMPACTION_MODELS`/`_1M_GA_MODELS`/`_1M_BETA_MODELS` become
registry-derived (`supports_compaction`, `context_mode`); beta-header constants
(`_COMPACTION_BETA`, `_EXTENDED_CONTEXT_BETA`) stay where they are (wire strings,
not model facts). Both `MODEL_CATALOG`s become derived views (same shapes).

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py tests/test_card_synthesis.py -q
rg -n "claude-opus-4|claude-sonnet-4|claude-haiku|gpt-5\." \
  src/agents/anthropic_agent/agent.py src/agents/openai_agent/agent.py \
  src/agents/shared/context_manager.py src/agents/shared/subagent.py
```

Commit: `feat: converge model facts onto the registry`.

---

## Task 3: Discovery Cache Store (run metadata + model rows)

**Files:** `src/model_discovery_cache.py`, `src/model_credentials.py`,
`tests/test_model_discovery_cache.py`.

### Step 1: RED tests

```python
from src.model_discovery_cache import ModelDiscoveryCache


def test_successful_run_replaces_scope_rows_and_metadata(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     status="ok",
                     models=[{"id": "gpt-5.6-luna", "label": "Luna", "source": "provider_api"}])
    scope = cache.get(provider="openai", auth_mode="api_key", credential_id="c1")
    assert scope.status == "ok" and scope.discovered_at is not None
    assert [m.model_id for m in scope.models] == ["gpt-5.6-luna"]


def test_zero_model_success_is_not_never_discovered(tmp_path):
    # round-1 MF4: a live listing that returns an empty set must still read back
    # as a completed run, not as "never discovered".
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     status="ok", models=[])
    scope = cache.get(provider="openai", auth_mode="api_key", credential_id="c1")
    assert scope.status == "ok" and scope.models == [] and scope.discovered_at


def test_seed_only_channel_records_seed_only_state(tmp_path):
    # claude_code_oauth has no live listing; its "discovery" returns seeds. The
    # cache stores the RUN as seed_only with no model rows — the UI then shows
    # seed candidates with a badge instead of an endless "run discovery" nudge.
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="anthropic", auth_mode="claude_code_oauth",
                     credential_id="oauth-1", status="seed_only", models=[])
    scope = cache.get(provider="anthropic", auth_mode="claude_code_oauth",
                      credential_id="oauth-1")
    assert scope.status == "seed_only"


def test_unknown_scope_reads_never_discovered(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    scope = cache.get(provider="anthropic", auth_mode="api_key", credential_id="x")
    assert scope.status == "never_discovered" and scope.models == []


def test_failed_run_preserves_previous_cache(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    # error runs are not recorded at all (caller contract) — simulate by NOT calling
    # record_run; the seam test below pins the caller side.
    scope = cache.get(provider="openai", auth_mode="api_key", credential_id="c1")
    assert [m.model_id for m in scope.models] == ["gpt-5.5"]


def test_schema_has_no_secret_columns(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    with cache._connect() as conn:
        for table in ("model_discovery_runs", "model_discovery_models"):
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            assert not (cols & {"secret", "api_key", "token"}), table
```

Caller-seam tests (in `tests/test_model_routing.py` or credentials tests):
`discover_models()` monkeypatched provider call → (a) success writes an `ok` run;
(b) raised exception → `record_run` NOT called (fake cache asserts untouched);
(c) the oauth-driver route path records `seed_only` when the result's models are
all `source="seed"`.

Expected RED: module missing; no cache seam.

### Step 2: Implement

Two tables: `model_discovery_runs(provider, auth_mode, credential_id, status,
discovered_at, source_url)` PK(scope) and `model_discovery_models(provider,
auth_mode, credential_id, model_id, label, source)` PK(scope, model_id); one
transaction per `record_run` (replace both). House store pattern. Write-through in
`discover_models()` (status ok + provider_api) and in the oauth-driver branch of
`config_routes.discover_provider_models` (all-seed result → `seed_only`).
`POST /config/model-discovery` response gains additive `cached_at` + `cache_state`.

### Step 3: Verify + commit

```bash
pytest tests/test_model_discovery_cache.py tests/test_model_routing.py -q
```

Commit: `feat: cache per-credential model discovery`.

---

## Task 4: Active-Credential Resolver + Per-Task Effective View + Picker

**Files:** `src/model_credentials.py` (resolver), `src/model_effective.py` (new —
keeps `model_routing.py` free of cache imports), `config_routes.py`, `api.ts`,
`Settings.tsx` (`ModelRoutingSection`), `ModelRoutingSection.test.ts`,
`tests/test_model_routing.py`.

### Step 1: RED tests (backend)

```python
def test_active_credential_resolver_covers_env_only_keys(tmp_path, monkeypatch):
    # round-1 MF3: _active_auth_mode() reads only the DB store, so an env-only
    # active key resolves to None and has no credential id. The resolver uses the
    # same inventory provider_credentials() builds (env rows included) and returns
    # (credential_id, auth_mode) — the cache scope key.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-only")
    ...  # fake empty CredentialStore
    cred = resolve_active_credential("openai", store=empty_store)
    assert cred is not None and cred.auth_mode == "api_key" and cred.credential_id


def test_effective_view_is_per_task_and_partitions_correctly(tmp_path):
    # cache: gpt-5.5 (current) + gpt-5.2 (legacy) + mystery-model (unknown)
    # routes: card_synthesis pins gpt-5.4 (current, NOT in cache);
    #         ai_research pins mystery-model (custom)
    view = effective_model_view(cache=populated_cache, routes=fake_routes,
                                resolver=fake_resolver)
    synth = view["tasks"]["card_synthesis"]
    assert [m["id"] for m in synth["verified"]] == ["gpt-5.5"]      # visible ∩ current
    advanced_ids = {m["id"] for m in synth["advanced"]}
    assert {"gpt-5.2", "mystery-model", "gpt-5.4"} <= advanced_ids  # legacy / unknown / pinned-but-unverified
    research = view["tasks"]["ai_research"]
    assert any(m["id"] == "mystery-model" and m["badge"] == "route"
               for m in research["advanced"])                        # pinned custom always selectable
    assert synth["cache_state"] == "ok"


def test_effective_view_never_discovered_and_seed_only_states(tmp_path):
    v1 = effective_model_view(cache=empty_cache, routes=fake_routes, resolver=fake_resolver)
    t = v1["tasks"]["card_synthesis"]
    assert t["verified"] == [] and t["cache_state"] == "never_discovered"
    assert all(m["badge"] in ("seed", "legacy", "custom", "route") for m in t["advanced"])

    v2 = effective_model_view(cache=seed_only_cache, routes=fake_routes, resolver=oauth_resolver)
    t2 = v2["tasks"]["card_synthesis"]
    assert t2["cache_state"] == "seed_only"
    assert any(m["badge"] == "seed" for m in t2["advanced"])         # seeds offered, badged
```

Route test: `GET /config/model-catalog` keeps all old top-level fields
shape-identical AND gains an additive `effective` block (`tasks` keyed by TaskId).

### Step 2: RED tests (frontend — house harness; component imported from `./Settings`)

- default dropdown per task lists only that task's `verified`;
- 「進階」 toggle reveals `advanced` with badges (舊版/未驗證/自訂/目前路由);
- `cache_state: "never_discovered"` renders the 「跑一次模型探索以驗證」 nudge wired
  to the existing discovery button; `"seed_only"` renders 「此通道無法線上列出模型」
  and NO nudge;
- the saved route model renders selected even from `advanced`.

### Step 3: Implement

`resolve_active_credential()` on the `provider_credentials()` inventory;
`src/model_effective.py` partition logic (registry + cache + routes in, per-task
blocks out); additive API block; picker split in `ModelRoutingSection`.
`PUT /config/model-routes` untouched.

### Step 4: Verify + commit

```bash
pytest tests/test_model_routing.py -q
cd apps/arkscope-web && npm test && npm run typecheck && npm run build
```

Commit: `feat: verified-first per-task model picker`.

---

## Task 5: New-Generation Models Land (registry + aliases + ledger)

**Files:** `src/model_capabilities.py`, ledger-swept tests. **No default flips.**

### Step 1: RED tests

- Registry entries for every Task 0-verified id (exact values from the Task 0
  table; Fable mandatory, gpt-5.6 family per verification), `tier="current"`,
  per-model `source_url`, `verified_at` = Task 0 date.
- `thinking_mode == "adaptive_always_on"` drives the anthropic agent: RED test that
  `_build_thinking_param` (or its registry-driven equivalent) never emits a
  disable/budget for an always-on model.
- **Official alias routing** (round-1 SF2): `capability_for("gpt-5.6")` resolves to
  the Sol entry iff the official docs define that alias (Task 0 confirms);
  `find_model("fable")` resolves.
- **Alias integrity**: no alias appears twice across the registry; no alias equals
  another entry's canonical id (loop over `all_models()`).
- `model_provider()` classifies every new id.

### Step 2: Implement + ledger sweep

Add entries; sweep model-referencing tests by NEW ids (`rg "claude-fable|gpt-5\.6"
tests/ src/`), fixing membership/count pins the additions legitimately move:

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py \
  tests/test_model_route_store.py tests/test_ai_research_route.py \
  tests/test_card_synthesis.py tests/test_monitor.py -q
```

### Step 3: Live smoke (scoped, user-gated where paid)

**Exactly one** minimal live call against the **cheapest Task 0-verified gpt-5.6
id** (expected Luna; pricing per Task 0 decides) to prove the registry's flags
produce an accepted request; the other gpt-5.6 ids and Fable 5 are marked
`runtime-unverified` in entry notes unless the user explicitly opts into per-id
smokes (Fable = premium pricing, always user-gated).

Commit: `feat: land fable-5 and gpt-5.6 generation`.

---

## Task 6: Gates, Full A/B, Docs Closeout

1. Focused backend: capability/cache/effective/routing suites + Task 5 sweep set.
2. Frontend: full vitest + typecheck + build.
3. Static gates: Review Gate 2 grep (now incl. `subagent.py`);
   `rg -n "psycopg2|postgres" src/model_capabilities.py src/model_discovery_cache.py src/model_effective.py` → empty.
4. `python src/smoke/pg_unreachable_e2e.py` → `ok:true`, `pg_attempts:[]`.
5. Full virgin A/B: failure sets identical; passed delta = exactly the new tests;
   warnings/errors accounted.
6. Docs: this plan → IMPLEMENTED FOR REVIEW; map §P2.7 status + decision-log;
   MEMORY.md Active-Models section rewritten from the registry.

Implementation stops review-ready before merge; reviewer reruns focused suites +
final A/B; merge on explicit approval; live verification = Settings discovery round
+ per-task picker inspection + the Task 5 smoke evidence.

---

## Expected Commit Sequence

1. `docs: verify new model generation facts` (Task 0, plan-only)
2. `feat: add model capability registry`
3. `feat: converge model facts onto the registry`
4. `feat: cache per-credential model discovery`
5. `feat: verified-first per-task model picker`
6. `feat: land fable-5 and gpt-5.6 generation`
7. `docs: close model capability catalog build`
