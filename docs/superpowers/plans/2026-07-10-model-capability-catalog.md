# Model Capability Registry + Discovery Cache + Effective Picker (P2.7)

> **Status: DRAFT FOR REVIEW (round 3) 2026-07-10.** Implements PROJECT_PRIORITY_MAP
> §P2.7. Round-2 review returned 5 must-fix + 2 should-fix; all verified against
> code and folded: the equivalence gate now compares the registry against the LIVE
> old helpers programmatically (executable at Task 1 time, cannot go stale), both
> compat views' exact memberships are pinned, Fix B explicitly covers the opus-4.8
> `ga_1m` semantics (wire-verified: `_use_extended_context_beta` returns False both
> before and after), executability became a real `task_auth_executable()` contract
> grounded in the live-resolver fail-closed behavior, the two effort semantics are
> split (provider wire values vs model-supported options), the cache gained a
> secret-fingerprint axis (same-id key replacement invalidates), and Task 4's RED
> fixtures are now complete executable code. Docs-only; no runtime implementation
> has started. Author: Claude (implementer); reviewer: user.

**Goal:** One code-reviewed **capability registry** becomes the single source for
model facts (context/output limits, thinking/effort/compaction, context mode,
structured-output/tool support, tier); a **DB discovery cache** records which
models each credential actually saw and when; an **effective picker** shows the
per-task, per-auth-mode intersection by default. New-generation models (Anthropic
Fable 5, OpenAI gpt-5.6 family) land with slice-time-verified facts. CLI, discord,
Settings routing, agents, subagent, and context manager all read the registry.

**Non-goals:** ANY default or recommendation flip (`agents/config.py`,
`model_routing.TASKS` — separate slice after live/cost observation);
`config/user_profile.yaml` scoring models; scheduled discovery refresh (v1 manual);
Ollama / OpenAI-compatible providers (schema must not preclude; no entries);
pricing display beyond `cost_tier`; removing `model_catalog.py` (compat shim);
run/replay storage changes; **route-validation authority migration** (route effort
validation keeps reading `model_routing.EFFORT_OPTIONS` — see Decision 7).

---

## Current Grounding (verified against code 2026-07-10, round-3 corrected)

1. **Nine drift sites** hold model facts today (contents as verified):
   - `src/model_routing.py` — `MODEL_CATALOG` (**exactly 7 ids**: claude-opus-4-8,
     claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5, gpt-5.5, gpt-5.4,
     gpt-5.4-mini; carries `supports_structured_output`/`supports_tool_calling`),
     `TASKS`, `EFFORT_OPTIONS` (provider WIRE values incl. `default`; openai:
     default/none/minimal/low/medium/high/xhigh; anthropic:
     default/low/medium/high/xhigh/max), `model_provider()`, `is_seed_model()`.
   - `src/agents/shared/model_catalog.py` — `MODEL_CATALOG` (**exactly 8 ids**:
     claude-opus-4-7, claude-sonnet-4-6, gpt-5.5, gpt-5.4-mini, gpt-5.4-nano,
     gpt-5.4, gpt-5.2, gpt-5.2-codex — note: NO opus-4.8, NO haiku),
     `find_model()` (**`find_model("opus")` resolves to `claude-opus-4-7` exactly**
     — alias on the 4.7 entry), `EFFORT_OPTIONS_BY_MODEL` (**anthropic-only** prefix
     table: opus-4-7 + sonnet-4-6; `get_effort_options` returns None for every
     OpenAI id AND for opus-4.8 — the latter is the ruled Fix A),
     `VALID_ANTHROPIC_EFFORT`, `VALID_REASONING_EFFORT`
     (none/minimal/low/medium/high/xhigh).
   - `src/agents/anthropic_agent/agent.py:102` — `_ADAPTIVE_THINKING_MODELS`,
     `_EFFORT_MODELS` (both `{opus-4-8, opus-4-7, sonnet-4-6}`), `_MODEL_MAX_OUTPUT`
     (128K/128K/64K), fallback 64_000.
   - `src/agents/anthropic_agent/agent.py:32` — `_COMPACTION_BETA`,
     `_COMPACTION_MODELS = {opus-4-7, sonnet-4-6}` (opus-4-8 absent — Task 0 item).
   - `src/agents/shared/subagent.py:25` — `_1M_GA_MODELS = {opus-4-7, sonnet-4-6}`,
     `_1M_BETA_MODELS = {sonnet-4-5, opus-4-5}`, `_EXTENDED_CONTEXT_BETA`.
     **Verified behavior**: `_use_extended_context_beta(model, True)` → opus-4-7
     False (GA), sonnet-4-5 True (beta), **opus-4-8 False** (in NEITHER set — no
     header sent; the model is treated as not-1M by the GA/beta classification even
     though no wire difference results). `cli.py:93` imports both symbols.
   - `src/agents/openai_agent/agent.py:64` — `_OPENAI_MODEL_MAX_OUTPUT` (gpt-5.5,
     gpt-5.4-mini, gpt-5.4-nano, gpt-5.4, gpt-5.2 → all 128_000), default 128_000.
   - `src/agents/shared/context_manager.py:58` — `_MODEL_CONTEXT_LIMITS` (8
     prefixes), fallback 200_000. **`claude-opus-4-8` NOT listed → resolves to
     200_000 today** (ruled Fix B). `gpt-5.2-codex` resolves via the `gpt-5.2`
     prefix (400_000).
   - `src/agents/config.py:43` — stale defaults (**NOT changed in this slice**).
   - Frontend — `ModelRoutingSection` inside `apps/arkscope-web/src/Settings.tsx:2011`;
     test imports from `./Settings`; fixtures are local objects.
2. **Executability is task × auth_mode, grounded in code** (round-2 MF2):
   `src/auth_drivers/live_resolver.py` — when an OAuth credential is active, the
   sync SDK clients (`live_anthropic_client` / openai counterpart) **FAIL CLOSED**
   (documented: "this sync client path cannot use the subscription token; don't
   silently bill the env key"). Card synthesis/translation run through these sync
   clients → **not executable under an active OAuth credential**. AI 研究 streaming
   supports api_key AND both OAuth driver paths (Track A covered all four run
   paths). `api_key_pool` resolves to a concrete key at call time → api_key
   semantics.
3. **Credential identity is mutable under a fixed id** (round-2 MF4):
   `PUT /config/credentials/{credential_id}` (config_routes.py:537 area) replaces
   the secret of a `local:` credential in place; env-derived credential ids don't
   change when the env var's key changes. A cache keyed only by credential_id can
   serve the previous account's entitlement.
4. **Discovery** (`model_credentials.py:901`) is live-only; oauth driver
   `claude_code_oauth.discover_models()` returns `status="ok"` with SEED models
   (no live listing exists on that channel). `_active_auth_mode()`
   (config_routes.py:77) reads only the DB store and returns only auth_type.
5. **Catalog API**: `GET /config/model-catalog` returns `catalog().model_dump()`.
   Route pins are PER TASK (three `TaskRoute`s).
6. **Test blast radius**: `tests/test_model_routing.py`, `test_model_route_store`,
   `test_ai_research_route`, `test_card_synthesis`, `test_monitor`, CLI tests
   importing `MODEL_CATALOG` re-exports.
7. **New-generation official pages** (Task 0 inputs; nothing trusted from here):
   Fable 5 announcement, effort doc, context-windows doc; gpt-5.6 Sol / Terra /
   Luna per-model pages (URLs in map §P2.7). Known contract shape to VERIFY: Fable
   thinking always-on + effort + compaction + 1M/128K.

---

## Decisions Locked By This Plan

1. **Registry is code, cache is DB, picker is the per-task intersection.**
2. **Registry membership = official documentation; entitlement = cache.** Discovery
   never adds/removes registry entries.
3. **Behavior-identical consolidation, verified against the LIVE old helpers**
   (round-2 MF1): the Task 1 equivalence test CALLS the pre-consolidation helpers
   and tables (still present at Task 1 time) and asserts the registry reproduces
   them id-by-id, with the ruled fixes as enumerated exceptions. Hand-transcribed
   tables are only a secondary cross-check.
4. **Exactly two ruled fixes** (everything else that would change = stop-loss):
   - **Fix A**: `get_effort_options("claude-opus-4-8")` `None` → the opus effort
     tuple `("max","xhigh","high","medium","low")`.
   - **Fix B**: opus-4.8 context facts — `get_model_context_limit` `200_000`
     (missing-entry fallback) → `1_000_000`, AND `context_mode = "ga_1m"` (today it
     is in neither 1M set). **Wire-verified**: `_use_extended_context_beta` returns
     False for opus-4.8 both before and after (GA sends no header), so the beta
     header behavior is unchanged; what changes is the classification (and any
     display derived from it). Both facts confirmed against the official
     context-windows doc in Task 0 before implementation.
   - `_COMPACTION_MODELS` membership for opus-4.8 is a Task 0 verification item →
     explicit Fix C proposal to the reviewer if docs say supported; otherwise
     unchanged.
5. **Compat views keep EXACT current membership** (round-2 MF1): `ModelCapability`
   carries explicit view flags `in_routing_seed: bool` / `in_cli_catalog: bool`,
   seeded to reproduce today's sets verbatim (routing = the 7; CLI = the 8).
   Membership tests pin both sets as literals. `find_model("opus")` stays
   `claude-opus-4-7` (alias placement preserved). Task 5's new models set BOTH
   flags (a ruled, reviewable addition in the diff) — nothing else moves between
   views in this slice.
6. **Tier assignment**: `current` = opus-4.8, sonnet-4.6, haiku-4.5, gpt-5.5,
   gpt-5.4, gpt-5.4-mini, gpt-5.4-nano (+ Task 5 additions); `legacy` = opus-4.7,
   gpt-5.2, gpt-5.2-codex, sonnet-4.5, opus-4.5. Tier drives the PICKER only —
   view flags (Decision 5) drive the compat seeds, so tiering opus-4.7 legacy does
   NOT remove it from the routing view.
7. **Two effort semantics, kept separate** (round-2 MF3):
   - **Provider wire values** = what route validation accepts
     (`model_routing.EFFORT_OPTIONS`, includes `default`) — UNTOUCHED in this
     slice; route validation keeps reading it; pinned by exact-tuple tests.
   - **Model-supported options** = registry `effort_options`: anthropic per-model
     tuples (per `EFFORT_OPTIONS_BY_MODEL` + Fix A; haiku/legacy-claude = empty);
     openai models transcribe today's provider-wide reasoning set
     `("none","minimal","low","medium","high","xhigh")` (recorded per-model; no
     per-model narrowing exists in code today).
   - CLI `get_effort_options()` keeps its exact current contract: anthropic-only
     helper — returns the registry tuple for anthropic ids, **None for every
     OpenAI id** (pinned).
8. **Executability is a named contract** (round-2 MF2):
   `task_auth_executable(task, provider, auth_mode, capability) -> bool` in
   `src/model_effective.py`, rules grounded in §2:
   - `card_synthesis` / `card_translation`: auth_mode ∈ {api_key, api_key_pool}
     only (OAuth fail-closed on sync clients); capability must have
     `supports_structured_output=True`.
   - `ai_research`: auth_mode ∈ {api_key, api_key_pool, claude_code_oauth (anthropic),
     chatgpt_oauth (openai)}; capability must have `supports_tool_calling=True`.
   - provider mismatch (capability.provider ≠ provider) → False.
   - Unknown auth_mode / None → False (fail closed; the UI then shows seeds in
     Advanced, never verified).
9. **Cache scope includes a secret fingerprint** (round-2 MF4): scope =
   (provider, auth_mode, credential_id) + `secret_fingerprint` column.
   Fingerprint = `sha256(secret)[:16]` for api_key/api_key_pool (one-way; the
   secret itself never stored); for OAuth scopes the fingerprint is the constant
   `"oauth"` (OAuth access tokens rotate by design — entitlement follows the
   account, and `local:` secret editing applies to API keys only per
   config_routes). `get()` takes the CURRENT fingerprint; a mismatch reads as
   `never_discovered` (stale rows are superseded on the next successful run).
10. **Cache states**: `ok` (live listing succeeded, zero models representable),
    `seed_only` (channel has no live listing — badge, no nudge),
    `never_discovered` (no run, or fingerprint mismatch). Run metadata separate
    from model rows.
11. **Effective view is per task**; the saved route model is always selectable
    (flagged, never hidden, never auto-changed); every task block carries
    `cache_state` + `discovered_at`, and the UI copy reads 「最後驗證可見 <time>」
    (round-2 SF2) — verified-ness is an observation with a timestamp, not a
    permanent property.
12. **`/config/model-catalog` and `/config/model-discovery` changes are additive.**
13. **Provenance per entry** (per-model official page + verified date); values from
    official docs only.
14. **House store pattern** for the cache.

---

## Files

Create:

- `src/model_capabilities.py`
- `src/model_discovery_cache.py`
- `src/model_effective.py`
- `tests/test_model_capabilities.py`
- `tests/test_model_discovery_cache.py`
- `tests/test_model_effective.py`

Modify:

- `src/model_routing.py` (seed derives from registry via view flags)
- `src/agents/shared/model_catalog.py` (compat shim; exact membership/aliases)
- `src/agents/anthropic_agent/agent.py` (capability + compaction tables → registry)
- `src/agents/openai_agent/agent.py` (output table → registry)
- `src/agents/shared/context_manager.py` (context table → registry)
- `src/agents/shared/subagent.py` (1M GA/beta sets → registry `context_mode`)
- `src/model_credentials.py` (resolver + discovery write-through)
- `src/api/routes/config_routes.py` (additive effective/cached fields)
- `apps/arkscope-web/src/api.ts` (additive DTOs)
- `apps/arkscope-web/src/Settings.tsx` (`ModelRoutingSection` at :2011)
- `apps/arkscope-web/src/ModelRoutingSection.test.ts` (imports `./Settings`)
- `tests/test_model_routing.py`
- `docs/design/PROJECT_PRIORITY_MAP.md`, this plan

NOT modified (ruled): `src/agents/config.py`, `model_routing.TASKS`,
`model_routing.EFFORT_OPTIONS`, `config/user_profile.yaml`.

---

## Stop-Loss Triggers

- A model lacks an official per-model page → it does not enter the registry.
- Consolidation changes any live-helper output beyond ruled Fixes A/B (and a
  reviewer-approved Fix C) — the Task 1 old-vs-new test is the tripwire.
- Compat view membership or alias resolution shifts (beyond Task 5's flagged
  additions).
- The registry needs a DAL/DB/network import.
- API shape changes non-additively.
- A new model requires agent-loop changes beyond registry-driven flags.
- The cache would need secrets/tokens (fingerprints are one-way digests).
- Effective-view logic wants to auto-rewrite a saved route.
- Any default/recommendation flip.

---

## Review Gates

1. **Old-vs-new equivalence (executable)**: Task 1's test calls the LIVE old
   helpers/tables and the registry side-by-side for the full pre-consolidation id
   set (plus prefix-variant probes), asserting equality with ruled fixes as the
   only enumerated exceptions.
2. **View membership pins**: routing view == the exact 7; CLI view == the exact 8;
   `find_model("opus") == "claude-opus-4-7"`.
3. **Single-source grep** (post-Task 2): no model-id fact tables in the four agent
   modules.
4. **Prefix precedence structural**; **alias integrity** (unique, no collision with
   canonical ids, official aliases resolve).
5. **Effort split**: `model_routing.EFFORT_OPTIONS` exact wire tuples unchanged;
   registry per-model tuples exact; CLI helper None-for-OpenAI pinned.
6. **Executability matrix**: `task_auth_executable` tested for every (task,
   auth_mode) pair incl. mixed provider/auth and pool.
7. **Cache contracts**: replace-on-success, preserve-on-failure, zero-model `ok`,
   `seed_only`, fingerprint-mismatch → `never_discovered`, no secret columns.
8. **Effective view**: per-task partition + `discovered_at` surfaced + route-model
   invariant + the three cache states.
9. **Frontend**: full vitest + typecheck + build; picker shows 最後驗證可見 time,
   badges, no seed_only nudge loop.
10. **PG smoke** `ok:true` `pg_attempts:[]`; **full virgin A/B** (sets identical,
    delta = new tests, warnings accounted).

---

## Task 0: Verify New-Generation + Contested Facts (no code)

1. WebFetch per-model pages (Fable 5 + effort + context-windows; Sol/Terra/Luna).
   Extract per model: canonical id, official aliases (does `gpt-5.6` route to
   Sol?), context, max output, thinking contract, effort set, compaction, context
   mode, **supports_structured_output, supports_tool_calling, pricing** (round-2
   SF1).
2. Resolve contested existing facts: opus-4.8 context (expect 1M → confirms Fix B),
   opus-4.8 compaction (→ Fix C proposal or unchanged), legacy 1M-beta story.
3. Run read-only live discovery per configured credential → **separate entitlement
   table keyed by (credential_id, auth_mode)** (round-2 SF1) — informs cache
   expectations + smoke targets only.
4. Emit into this plan:

   | id | provider | context | max output | thinking_mode | effort | compaction | context_mode | structured_output | tool_calling | pricing | source page |
   |----|----------|---------|-----------|---------------|--------|------------|--------------|-------------------|--------------|---------|-------------|
   | *(Task 0)* | | | | | | | | | | | |

   | credential_id | auth_mode | new-generation ids visible |
   |---------------|-----------|----------------------------|
   | *(Task 0)* | | |

Commit: `docs: verify new model generation facts`.
**Gate**: reviewer acks both tables (+ any Fix C) before Task 1.

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
    current_models,
)

_PRE_CONSOLIDATION_IDS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
    "claude-sonnet-4-5", "claude-opus-4-5",
    "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5.2-codex",
}

# Ruled divergences (round-2 review): everything else must match the live helpers.
_RULED_FIXES = {
    ("claude-opus-4-8", "context_limit"),   # Fix B: 200_000 fallback → 1_000_000
    ("claude-opus-4-8", "context_mode"),    # Fix B: neither-set → ga_1m
    ("claude-opus-4-8", "effort_options"),  # Fix A: None → opus tuple (CLI helper)
}


def test_registry_covers_every_pre_consolidation_id():
    missing = {mid for mid in _PRE_CONSOLIDATION_IDS if capability_for(mid) is None}
    assert missing == set()


def test_registry_matches_live_legacy_helpers_except_ruled_fixes():
    """Round-2 MF1: compare against the OLD code paths themselves (they still
    exist untouched in Task 1), not a hand transcription."""
    from src.agents.anthropic_agent.agent import (
        _MODEL_MAX_OUTPUT as OLD_ANTH_OUT,
        _ADAPTIVE_THINKING_MODELS as OLD_ADAPTIVE,
        _EFFORT_MODELS as OLD_EFFORT,
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
            old_out = next(
                (v for k, v in OLD_ANTH_OUT.items() if mid.startswith(k)), 64_000
            )
        else:
            old_out = _get_openai_max_output(mid)
        assert cap.max_output == old_out, mid
        # thinking / effort-support flags
        old_adaptive = any(mid.startswith(m) for m in OLD_ADAPTIVE)
        assert (cap.thinking_mode == "adaptive_opt_in") == old_adaptive, mid
        old_effort_flag = any(mid.startswith(m) for m in OLD_EFFORT)
        # effort tuple (CLI helper contract)
        old_tuple = get_effort_options(mid)
        if (mid, "effort_options") in _RULED_FIXES:
            assert old_tuple is None and cap.effort_options == (
                "max", "xhigh", "high", "medium", "low",
            ), mid
        elif cap.provider == "anthropic":
            assert (cap.effort_options or None) == (
                tuple(old_tuple) if old_tuple else None
            ) or (cap.effort_options == () and old_tuple is None), mid
            assert (cap.effort_options != ()) == old_effort_flag or mid == "claude-opus-4-8", mid
        # compaction
        assert cap.supports_compaction == any(
            mid.startswith(m) for m in OLD_COMPACT
        ), mid
        # context mode
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
    # Round-2 MF3: registry effort_options for OpenAI ids transcribe the provider
    # reasoning set; the CLI helper still returns None for them (separate test in
    # Task 2); route wire validation is NOT driven by this field.
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
    legacy = {c.id for c in all_models() if c.tier == "legacy"}
    assert legacy == {
        "claude-opus-4-7", "gpt-5.2", "gpt-5.2-codex",
        "claude-sonnet-4-5", "claude-opus-4-5",
    }


def test_current_models_excludes_legacy():
    ids = {c.id for c in current_models("openai")}
    assert "gpt-5.2" not in ids and {"gpt-5.5", "gpt-5.4-mini"} <= ids
```

Expected RED: module missing. (The old-vs-new test runs the OLD helpers live —
Task 1 does not touch them, so it is executable immediately.)

### Step 2: Implement

`ModelCapability` frozen dataclass: `id`, `provider`, `label`, `tier`,
`thinking_mode`, `effort_options: tuple[str, ...]`, `supports_compaction`,
`context_mode`, `context_limit`, `max_output`, `supports_structured_output`,
`supports_tool_calling`, `in_routing_seed`, `in_cli_catalog`,
`aliases: tuple[str, ...]`, `quality`, `speed`, `cost_tier`, `recommended_for`,
`source_url`, `verified_at`, `notes`. `capability_for()` = exact alias/id match
first, then longest-prefix. Pure stdlib.

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py -q
python -m compileall -q src/model_capabilities.py
```

Commit: `feat: add model capability registry`.

---

## Task 2: Converge the Nine Sites (behavior-identical + Fixes A/B)

**Files:** agent modules, `context_manager.py`, `subagent.py`, `model_catalog.py`,
`model_routing.py`, tests.

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
    assert _get_model_max_output("unknown-claude") == 64_000
    assert _supports_adaptive_thinking("claude-sonnet-4-6-future") is True
    assert _supports_effort("claude-haiku-4-5") is False
    assert _supports_compaction("claude-sonnet-4-6") is True
    assert _supports_compaction("claude-opus-4-8") is False   # pending Task 0/Fix C
    assert _get_openai_max_output("gpt-5.4-nano") == 128_000
    assert _get_openai_max_output("totally-unknown") == 128_000
    assert get_model_context_limit("gpt-5.4-mini") == 400_000
    assert get_model_context_limit("claude-opus-4-8") == 1_000_000   # Fix B
    assert get_model_context_limit("unknown") == 200_000
    # wire behavior of the beta-header helper is UNCHANGED incl. opus-4.8 (=False)
    assert _use_extended_context_beta("claude-opus-4-8", True) is False
    assert _use_extended_context_beta("claude-opus-4-7", True) is False
    assert _use_extended_context_beta("claude-sonnet-4-5", True) is True


def test_cli_effort_helper_contract_preserved_plus_fix_a():
    from src.agents.shared.model_catalog import get_effort_options
    assert get_effort_options("claude-opus-4-8") == ("max", "xhigh", "high", "medium", "low")  # Fix A
    assert get_effort_options("claude-opus-4-7") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-sonnet-4-6") == ("high", "medium", "low")
    for openai_id in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.2"):
        assert get_effort_options(openai_id) is None     # anthropic-only contract kept


def test_route_wire_effort_values_untouched():
    from src.model_routing import EFFORT_OPTIONS
    assert [o.id for o in EFFORT_OPTIONS["openai"]] == [
        "default", "none", "minimal", "low", "medium", "high", "xhigh",
    ]
    assert [o.id for o in EFFORT_OPTIONS["anthropic"]] == [
        "default", "low", "medium", "high", "xhigh", "max",
    ]


def test_derived_views_keep_exact_membership_and_aliases():
    from src.model_routing import MODEL_CATALOG as ROUTING_VIEW, is_seed_model
    from src.agents.shared.model_catalog import MODEL_CATALOG as CLI_VIEW, find_model

    assert {m.id for m in ROUTING_VIEW} == {
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    }
    assert [m.id for m in CLI_VIEW].__len__() == 8
    assert {m.id for m in CLI_VIEW} == {
        "claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.4-mini",
        "gpt-5.4-nano", "gpt-5.4", "gpt-5.2", "gpt-5.2-codex",
    }
    assert find_model("opus").id == "claude-opus-4-7"    # exact, not startswith
    assert find_model("mini").id == "gpt-5.4-mini"
    assert find_model("codex").id == "gpt-5.2-codex"
    assert is_seed_model("openai", "gpt-5.5")

    for option in ROUTING_VIEW:
        from src.model_capabilities import capability_for
        cap = capability_for(option.id)
        assert option.supports_structured_output == cap.supports_structured_output
        assert option.supports_tool_calling == cap.supports_tool_calling
```

Expected RED: helpers read local tables; opus-4.8 effort None / context 200_000.

### Step 2: Implement

Replace fact tables with registry reads; keep signatures + fallback constants.
Views derive via `in_routing_seed`/`in_cli_catalog` (same output shapes). Beta/wire
header constants stay put.

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py tests/test_card_synthesis.py -q
rg -n "claude-opus-4|claude-sonnet-4|claude-haiku|gpt-5\." \
  src/agents/anthropic_agent/agent.py src/agents/openai_agent/agent.py \
  src/agents/shared/context_manager.py src/agents/shared/subagent.py
```

Commit: `feat: converge model facts onto the registry`.

---

## Task 3: Discovery Cache Store (runs + models + fingerprint)

**Files:** `src/model_discovery_cache.py`, `src/model_credentials.py`,
`tests/test_model_discovery_cache.py`.

### Step 1: RED tests (complete, executable)

```python
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
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-1", status="ok", models=[])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-1")
    assert scope.status == "ok" and scope.models == [] and scope.discovered_at


def test_fingerprint_mismatch_reads_never_discovered(tmp_path):
    # Round-2 MF4: same credential id, replaced secret → previous entitlement must
    # not be served.
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-old", status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-new")
    assert scope.status == "never_discovered" and scope.models == []
    # and a new successful run under the new fingerprint supersedes the stale rows
    cache.record_run(**_SCOPE, secret_fingerprint="fp-new", status="ok",
                     models=[{"id": "gpt-5.6-sol", "label": "Sol", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-new")
    assert [m.model_id for m in scope.models] == ["gpt-5.6-sol"]


def test_seed_only_channel_records_seed_only_state(tmp_path):
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
```

Caller-seam tests (in `tests/test_model_routing.py`): monkeypatched provider call →
success writes `ok` + fingerprint of the resolved secret; raised exception →
`record_run` not called; oauth route path records `seed_only` when all models are
`source="seed"`.

Expected RED: module missing.

### Step 2: Implement

Tables `model_discovery_runs(provider, auth_mode, credential_id,
secret_fingerprint, status, discovered_at, source_url)` PK(provider, auth_mode,
credential_id) and `model_discovery_models(...)` PK(scope, model_id); one
transaction per `record_run` (replace both; fingerprint column updated with the
run). House pattern. Write-through in `discover_models()` + the oauth branch of
`discover_provider_models`. Additive `cached_at`/`cache_state` in the discovery
response.

Commit: `feat: cache per-credential model discovery`.

---

## Task 4: Resolver + Executability + Per-Task Effective View + Picker

**Files:** `src/model_credentials.py` (resolver), `src/model_effective.py`,
`config_routes.py`, `api.ts`, `Settings.tsx`, `ModelRoutingSection.test.ts`,
`tests/test_model_effective.py`.

### Step 1: RED tests (backend — complete, executable)

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


def test_task_auth_executable_matrix():
    opus = capability_for("claude-opus-4-8")
    gpt = capability_for("gpt-5.5")
    # card tasks: sync SDK clients → api_key modes only (live_resolver fail-closed)
    assert task_auth_executable("card_synthesis", "anthropic", "api_key", opus) is True
    assert task_auth_executable("card_synthesis", "anthropic", "api_key_pool", opus) is True
    assert task_auth_executable("card_synthesis", "anthropic", "claude_code_oauth", opus) is False
    assert task_auth_executable("card_translation", "openai", "chatgpt_oauth", gpt) is False
    # ai_research: oauth modes ARE executable on their own provider
    assert task_auth_executable("ai_research", "anthropic", "claude_code_oauth", opus) is True
    assert task_auth_executable("ai_research", "openai", "chatgpt_oauth", gpt) is True
    assert task_auth_executable("ai_research", "openai", "api_key", gpt) is True
    # mixed provider/auth and unknowns fail closed
    assert task_auth_executable("ai_research", "openai", "claude_code_oauth", gpt) is False
    assert task_auth_executable("card_synthesis", "anthropic", None, opus) is False
    assert task_auth_executable("card_synthesis", "openai", "api_key", opus) is False  # provider mismatch


def _fp(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:16]


def _routes() -> dict[str, TaskRoute]:
    return {
        "card_synthesis": TaskRoute(task="card_synthesis", provider="openai",
                                    model="gpt-5.4", effort="default"),
        "card_translation": TaskRoute(task="card_translation", provider="openai",
                                      model="gpt-5.5", effort="default"),
        "ai_research": TaskRoute(task="ai_research", provider="openai",
                                 model="mystery-model", effort="default"),
    }


def _cred() -> ActiveCredential:
    return ActiveCredential(provider="openai", credential_id="c1",
                            auth_mode="api_key", secret_fingerprint=_fp("sk-live"))


def test_effective_view_is_per_task_and_partitions_correctly(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     secret_fingerprint=_fp("sk-live"), status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"},
                             {"id": "gpt-5.2", "label": "GPT-5.2", "source": "provider_api"},
                             {"id": "mystery-model", "label": "?", "source": "provider_api"}])
    view = effective_model_view(cache=cache, routes=_routes(), credential=_cred())

    synth = view["tasks"]["card_synthesis"]
    assert [m["id"] for m in synth["verified"]] == ["gpt-5.5"]     # visible ∩ current ∩ executable
    advanced_ids = {m["id"] for m in synth["advanced"]}
    assert {"gpt-5.2", "mystery-model", "gpt-5.4"} <= advanced_ids  # legacy / unknown / pinned-unverified
    assert synth["cache_state"] == "ok" and synth["discovered_at"]

    research = view["tasks"]["ai_research"]
    assert any(m["id"] == "mystery-model" and m["badge"] == "route"
               for m in research["advanced"])                       # pinned custom always selectable


def test_effective_view_oauth_credential_blocks_card_tasks(tmp_path):
    # Round-2 MF2 regression shape: an OAuth credential must NOT mark card-task
    # models verified even when discovery listed them.
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    cache.record_run(provider="openai", auth_mode="chatgpt_oauth", credential_id="o1",
                     secret_fingerprint="oauth", status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    cred = ActiveCredential(provider="openai", credential_id="o1",
                            auth_mode="chatgpt_oauth", secret_fingerprint="oauth")
    view = effective_model_view(cache=cache, routes=_routes(), credential=cred)
    assert view["tasks"]["card_synthesis"]["verified"] == []        # fail-closed
    assert [m["id"] for m in view["tasks"]["ai_research"]["verified"]] == ["gpt-5.5"]


def test_effective_view_never_discovered_and_seed_only_states(tmp_path):
    cache = ModelDiscoveryCache(tmp_path / "profile_state.db")
    view = effective_model_view(cache=cache, routes=_routes(), credential=_cred())
    t = view["tasks"]["card_synthesis"]
    assert t["verified"] == [] and t["cache_state"] == "never_discovered"
    assert all(m["badge"] in ("seed", "legacy", "custom", "route") for m in t["advanced"])

    cache.record_run(provider="openai", auth_mode="api_key", credential_id="c1",
                     secret_fingerprint=_fp("sk-live"), status="seed_only", models=[])
    view2 = effective_model_view(cache=cache, routes=_routes(), credential=_cred())
    assert view2["tasks"]["card_synthesis"]["cache_state"] == "seed_only"


def test_resolver_covers_env_only_keys(monkeypatch, tmp_path):
    # Round-2 MF3/MF4: env-only active key must resolve to a stable synthetic
    # credential id + auth_mode api_key + a fingerprint of the CURRENT env secret.
    from src.model_credentials import resolve_active_credential

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-only")
    # point the credential store at an empty tmp DB (no local rows)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    cred = resolve_active_credential("openai")
    assert cred is not None
    assert cred.auth_mode == "api_key" and cred.credential_id
    assert cred.secret_fingerprint == _fp("sk-env-only")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-rotated")
    assert resolve_active_credential("openai").secret_fingerprint == _fp("sk-rotated")
```

Route test: `GET /config/model-catalog` keeps old top-level fields shape-identical
AND gains additive `effective.tasks` (handler-direct with a fake cache + stub
resolver via monkeypatching module references — house route-test idiom).

### Step 2: RED tests (frontend — house harness; component from `./Settings`)

- per-task dropdown lists only that task's `verified`;
- 「進階」 reveals `advanced` with badges (舊版/未驗證/自訂/目前路由);
- header shows 「最後驗證可見 <time>」 from `discovered_at` (round-2 SF2);
- `never_discovered` → nudge wired to the existing discovery button; `seed_only`
  → 「此通道無法線上列出模型」, no nudge;
- saved route model renders selected from `advanced`.

### Step 3: Implement

`ActiveCredential` dataclass + `resolve_active_credential()` (inventory-based, env
rows included, sha256[:16] fingerprint, `"oauth"` constant for oauth modes);
`task_auth_executable()` + `effective_model_view()` in `model_effective.py`;
additive API block; picker split. `PUT /config/model-routes` untouched.

Commit: `feat: verified-first per-task model picker`.

---

## Task 5: New-Generation Models Land (registry + aliases + ledger)

Registry entries for every Task 0-verified id (`tier="current"`, both view flags
set — the ruled additions), alias routing per official docs
(`capability_for("gpt-5.6")` → Sol iff documented), alias-integrity sweep,
`thinking_mode="adaptive_always_on"` driving the anthropic agent (RED: never emits
a disable/budget for always-on models), `model_provider()` classification,
`find_model("fable")`. Ledger sweep by NEW ids across `tests/`. **No default
flips.** Live smoke: exactly one call against the cheapest Task 0-verified gpt-5.6
id; all other new ids annotated `runtime-unverified`; Fable smoke user-gated.

Commit: `feat: land fable-5 and gpt-5.6 generation`.

---

## Task 6: Gates, Full A/B, Docs Closeout

1. Focused backend: capability/cache/effective/routing + sweep set.
2. Frontend: full vitest + typecheck + build.
3. Static gates: Review Gate 3 grep; `rg -n "psycopg2|postgres"` over the three new
   modules → empty.
4. PG smoke `ok:true`, `pg_attempts:[]`.
5. Full virgin A/B: sets identical; delta = new tests; warnings accounted.
6. Docs: plan → IMPLEMENTED FOR REVIEW; map §P2.7 + decision-log; MEMORY.md
   Active-Models rewritten from the registry.

Review-ready stop before merge; reviewer reruns focused + final A/B; merge on
explicit approval; live verification = Settings discovery round + per-task picker
+ smoke evidence.

---

## Expected Commit Sequence

1. `docs: verify new model generation facts` (Task 0)
2. `feat: add model capability registry`
3. `feat: converge model facts onto the registry`
4. `feat: cache per-credential model discovery`
5. `feat: verified-first per-task model picker`
6. `feat: land fable-5 and gpt-5.6 generation`
7. `docs: close model capability catalog build`
