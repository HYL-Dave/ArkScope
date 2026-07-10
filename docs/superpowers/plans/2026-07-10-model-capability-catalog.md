# Model Capability Registry + Discovery Cache + Effective Picker (P2.7)

> **Status: DRAFT FOR REVIEW (round 7) 2026-07-10.** Round-6 returned 1 must-fix
> (refusal test vs the REAL harness: `mock_deps` yields a dict, collection goes
> through `self._collect_events`, `run_query_stream` imported in-test,
> `dal=MagicMock()` for hermeticity) + 1 should-fix (oauth route test now also
> pins the additive `cache_state`/`cached_at` response fields) — both applied
> verbatim from the review.
> Implements PROJECT_PRIORITY_MAP
> §P2.7. Round-5 review returned 2 must-fix (both test-layer) + 1 should-fix, all
> verified and folded: the Task 5B loop test is now built on the EXISTING
> `tests/test_events.py` harness (`_make_mock_response(stop_reason="refusal",
> content_blocks=[])` — its SimpleNamespace usage keeps the token tracker alive —
> `_make_stream_cm`, the `mock_deps` fixture; the loop's `live_anthropic_client`
> import is function-local at agent.py:220, and `mock_deps`'s `anthropic.Anthropic`
> patch already intercepts the env-fallback client construction), asserts
> `EventType.error` with `data["code"] == "model_refusal"` and ZERO `done` events
> (**no new EventType member** — `test_events.py:18` pins the full enum value set,
> so reusing `error` avoids a needless enum break), and patches
> `Scratchpad.log_final_answer` directly instead of a nonexistent seam; the card
> fixtures use the real `_packet()` helper (`tests/test_card_synthesis.py:22`);
> Task 4 gained a REAL handler-direct `discover_provider_models` test pinning the
> OAuth all-seed → `seed_only` cache write-through (scope + fingerprint + additive
> response); and the Anthropic seed_only effective-view test now also asserts
> pinned_only Claude models do not resurface as seed candidates. Rounds 1-5
> history: three-layer architecture (registry=code / cache=DB / picker=per-task
> intersection), live-helper equivalence gate, exact view-membership pins,
> pool-fail-closed, credential fingerprint, five-mode thinking with implementable
> wire mapping, three-seam refusal handling, membership = official docs +
> ArkScope relevance. Docs-only; no runtime implementation has started. Author:
> Claude (implementer); reviewer: user.

**Goal:** One code-reviewed **capability registry** is the single source for model
facts; a **DB discovery cache** records per-credential visibility; an **effective
picker** shows, per task, only models that are visible to the active credential,
default-visibility, and executable under that task's auth mode. New generation
(Anthropic Fable 5 + Sonnet 5; OpenAI gpt-5.6 Sol/Terra/Luna) lands with
slice-time-verified facts and honest runtime support (structured refusal handling
— no silent fallback, no empty-success).

**Non-goals:** ANY default or recommendation flip; `config/user_profile.yaml`
scoring models; scheduled discovery refresh; Ollama / OpenAI-compatible providers;
pricing display beyond `cost_tier`; removing `model_catalog.py`; run/replay
changes; route-validation authority migration (`model_routing.EFFORT_OPTIONS`
stays); `api_key_pool` wiring; **thinking tri-state migration** (None = provider
default — follow-up; this slice keeps the bool toggle with the Decision-8 wire
mapping).

---

## Current Grounding (verified 2026-07-10, round-5 corrected)

1. **Nine drift sites** (as verified in rounds 1-4): routing `MODEL_CATALOG`
   (exactly 7) + `TASKS` + `EFFORT_OPTIONS` + `model_provider()` +
   `is_seed_model()`; CLI `MODEL_CATALOG` (exactly 8; `find_model("opus") ==
   "claude-opus-4-7"`) + `EFFORT_OPTIONS_BY_MODEL` (opus-4.8 missing = Fix A) +
   `VALID_*_EFFORT`; `_ADAPTIVE_THINKING_MODELS` / `_EFFORT_MODELS` /
   `_MODEL_MAX_OUTPUT` (agent.py:102); `_COMPACTION_MODELS` (agent.py:32;
   opus-4.8 absent — Task 0 item); `_1M_GA_MODELS` / `_1M_BETA_MODELS`
   (subagent.py:25; opus-4.8 in neither — Fix B, wire-verified);
   `_OPENAI_MODEL_MAX_OUTPUT` (agent.py:64); `_MODEL_CONTEXT_LIMITS`
   (context_manager.py:58; opus-4.8 → 200_000 fallback = Fix B);
   `agents/config.py:43` (NOT changed); `ModelRoutingSection` at
   `Settings.tsx:2011` (house createRoot/act harness, local `catalog()` fixture +
   `render()` helper).
2. **Thinking wire reality (values from live runs — pinned)**:
   `_build_thinking_param(model, thinking_enabled, config)` with
   `config.max_tokens=8192`:
   - `("claude-opus-4-8", True)` → `({"type": "adaptive"}, 128000)`
   - `("claude-haiku-4-5", True)` → `({"type": "enabled", "budget_tokens": 55808}, 64000)`
   - `("claude-haiku-4-5", False)` → `(None, 8192)` — **off = OMIT today**, which
     is exactly why `adaptive_default_on` models need explicit
     `{"type":"disabled"}` for off (omit would leave them ON).
   `agents/config.py:80` `anthropic_thinking: bool = False` — the toggle is a
   bool; there is no None/tri-state.
3. **Refusal gap (verified)**: the agent loop is **streaming**
   (`client = live_anthropic_client()` at agent.py:221; `client.messages.stream`
   / `client.beta.messages.stream` at :371/:376; terminal handling at :412 treats
   any non-`tool_use`, non-`compaction` stop as a final answer via
   `pad.log_final_answer`). Public entries: `run_query_stream(question, model=,
   dal=, effort=, thinking=, ...)` (async generator of AgentEvent) and
   `run_query` (:566). Card synthesis (`_synthesize_anthropic`, function-local
   `from src.auth_drivers.live_resolver import live_anthropic_client`;
   `client.messages.create` with a forced tool) AND card translation
   (`_translate_anthropic` at card_synthesis.py:460, same pattern) both need the
   shared refusal error. **The loop's import is ALSO function-local**
   (agent.py:220-221) — there is no `mod.live_anthropic_client` to patch. Card
   seams patch `src.auth_drivers.live_resolver.live_anthropic_client`; the loop
   test reuses `tests/test_events.py`'s `mock_deps` fixture, whose
   `anthropic.Anthropic` patch intercepts the env-fallback client that
   `live_anthropic_client()` constructs (the existing TestAnthropicStream tests
   already drive `run_query_stream` this way). `EventType`
   (src/agents/shared/events.py:19) has NO `refusal` member and
   `test_events.py:18` pins the full enum value set — refusals surface as
   `EventType.error` with `data["code"] == "model_refusal"`; no enum change.
   `tests/test_events.py` helpers: `_make_mock_response(stop_reason=,
   content_blocks=)` (usage is a SimpleNamespace so the token tracker records
   normally — a bare `usage=None` fake would crash the logger before refusal
   classification) and `_make_stream_cm(response)`.
4. **Executability grounding**: `resolve_live_auth()` resolves only DB `api_key`
   or env fallback; OAuth-active → fail-closed for sync clients (cards);
   **`api_key_pool` appears nowhere in live_resolver.py** → False for every task
   until wired. Cards require `supports_tool_calling` (forced tool) and
   `supports_structured_output`. AI 研究 streaming supports api_key + both OAuth
   driver paths on their own provider.
5. **Credential identity mutable under fixed id** (`PUT /config/credentials/{id}`
   replaces `local:` secrets; env ids stable across rotation) → cache
   `secret_fingerprint`.
6. **Discovery**: `discover_models()` live-only; `claude_code_oauth` driver
   returns `status="ok"` with SEED models → `seed_only`. `_active_auth_mode()` is
   DB-only and id-less → replaced by `resolve_active_credential()`.
7. **Catalog API**: real handler = `model_catalog(store: CredentialStore =
   Depends(get_credential_store))` at `config_routes.py:227`, returns
   `{**catalog().model_dump(), "routes": {...}, "credentials": ..., ...}`.
8. **New-generation scope: FIVE models** — Fable 5, Sonnet 5, gpt-5.6
   Sol/Terra/Luna (per-model official pages; reviewer-supplied pricing to
   re-verify in Task 0: Sol $5/$30, Terra $2.50/$15, Luna $1/$6, Sonnet 5 $2/$10
   promo → $3/$15). Contract shapes to verify: Fable `adaptive_always_on` +
   refusal stop_reason (+ stop_details shape); Sonnet 5 `adaptive_default_on`
   (omit = on, explicit disabled allowed).
9. **Model-value rationale (user ruling, drives visibility)**: worth-listing
   OpenAI set = Sol/Terra/Luna/gpt-5.4-mini (Terra ≈ gpt-5.5 at lower price; Luna
   > mini capability at slightly higher price; mini stays relevant under codex
   OAuth costing). Strongest-per-family = Fable 5 / Opus 4.8 / Sonnet 5; Haiku
   4.5 for translation/notes work. Opus 4.7 / Sonnet 4.6 keep an Advanced path
   for now with **future removal expected**.

---

## Decisions Locked By This Plan

1. **Registry is code, cache is DB, picker is the per-task intersection.**
2. **Registry membership = official documentation (necessary) AND ArkScope
   relevance (sufficient)** (round-4 MF6): an entry requires an official
   per-model page PLUS at least one of — (a) named in the Decision-6 picker
   policy, (b) required by a compat view, (c) pinned by an existing
   route/config. Documented-but-irrelevant models (e.g. **Mythos 5**, voice
   models) do NOT enter; the registry must not drift toward a provider-wide
   mirror.
3. **Behavior-identical consolidation, verified against the LIVE old helpers**;
   ruled fixes are the only enumerated exceptions.
4. **Ruled fixes (all user-acked 2026-07-10 post-Task 0)**:
   - Fix A: opus-4.8 CLI effort options None → opus tuple.
   - Fix B: opus-4.8 context 200_000-fallback → 1_000_000 +
     `context_mode="ga_1m"` (`_use_extended_context_beta` wire unchanged).
   - Fix C: opus-4.8 `supports_compaction` False → True (compaction beta list).
   - Fix D: sonnet-4.6 `max_output` 64_000 → 128_000 (models-overview table).
   - Fix E: sonnet-4.6 effort tuple → `("max","high","medium","low")` (effort
     doc; no xhigh).
5. **Compat views keep EXACT current membership** via `in_routing_seed` /
   `in_cli_catalog`; Task 5 additions set both flags (ruled, diff-visible).
6. **`picker_visibility: "default" | "advanced" | "pinned_only"`**:
   - `default`: claude-fable-5, claude-opus-4-8, claude-sonnet-5,
     claude-haiku-4-5, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.4-mini.
   - `advanced`: claude-opus-4-7, claude-sonnet-4-6 (previous generation;
     future-removal note in entry `notes`).
   - `pinned_only`: gpt-5.5, gpt-5.4, gpt-5.4-nano, gpt-5.2, gpt-5.2-codex,
     claude-sonnet-4-5, claude-opus-4-5 — **rendered NOWHERE unless that task's
     saved route pins them** (then they appear in Advanced with badge `route`).
     Discovery visibility alone does NOT surface them (round-4 MF1).
   - Discovery entitlement remains the final gate for `verified`.
   - Visibility is a PICKER axis; compat view flags keep CLI/routing seeds
     unchanged.
7. **Two effort semantics stay split** (wire tuples untouched + pinned; registry
   per-model tuples; CLI helper None-for-OpenAI pinned).
8. **Thinking is a five-mode axis with an implementable wire mapping under
   today's bool toggle** (round-4 MF4; tri-state deferred to a follow-up):
   - `none` (OpenAI): never send a thinking param.
   - `manual_budget`: True → `{"type":"enabled","budget_tokens":N}`; False →
     omit (today's exact behavior, pinned values).
   - `adaptive_opt_in` (opus-4.8/4.7, sonnet-4.6): True → `{"type":"adaptive"}`;
     False → omit (today's exact behavior).
   - `adaptive_default_on` (Sonnet 5): True → `{"type":"adaptive"}`; **False →
     explicit `{"type":"disabled"}`** (omit would leave thinking ON, violating
     the user's off intent).
   - `adaptive_always_on` (Fable 5): the toggle is ignored — always send the
     Task 0-verified always-on shape (adaptive or omit per docs); NEVER send
     disabled or budget_tokens.
9. **Executability contract**: `task_auth_executable(task, provider, auth_mode,
   capability)` — cards: auth_mode == `api_key` only (pool False, OAuth False) AND
   `supports_tool_calling` AND `supports_structured_output`; ai_research:
   auth_mode ∈ {api_key, claude_code_oauth→anthropic, chatgpt_oauth→openai}
   (pool False) AND `supports_tool_calling`; provider mismatch / unknown / None →
   False. `effective_model_view(cache, routes, credentials: dict[Provider,
   ActiveCredential | None])` — per-task provider from that task's route.
10. **Structured refusal handling in scope (Task 5B)**: shared
    `AnthropicRefusalError` + `is_refusal(message)` in a new tiny
    `src/anthropic_refusal.py`, consumed by the agent loop (streaming terminal
    classification), `_synthesize_anthropic`, AND `_translate_anthropic`. No
    fallback, no empty-success. **Escape hatch**: depth beyond these three seams
    → Fable ships `runtime_ready=False` (excluded from
    `default_picker_models`/`verified`, badge 「運行支援未接線」) + follow-up
    slice.
11. **Cache**: scope (provider, auth_mode, credential_id) + `secret_fingerprint`
    (`sha256(secret)[:16]`; `"oauth"` constant for OAuth); mismatch →
    `never_discovered`; states `ok` (zero-model representable) / `seed_only`
    (badge, no nudge) / `never_discovered`; replace-on-success,
    preserve-on-failure, no secret columns; house store pattern.
12. **Effective view carries `cache_state` + `discovered_at`** (UI: 「最後驗證可
    見 <time>」); saved route model always selectable; API changes additive;
    provenance per entry.

---

## Files

Create: `src/model_capabilities.py`, `src/model_discovery_cache.py`,
`src/model_effective.py`, `src/anthropic_refusal.py`,
`tests/test_model_capabilities.py`, `tests/test_model_discovery_cache.py`,
`tests/test_model_effective.py`.

Modify: `src/model_routing.py`, `src/agents/shared/model_catalog.py`,
`src/agents/anthropic_agent/agent.py` (tables + streaming refusal branch),
`src/agents/openai_agent/agent.py`, `src/agents/shared/context_manager.py`,
`src/agents/shared/subagent.py`, `src/card_synthesis.py` (synthesis + translation
refusal), `src/model_credentials.py`, `src/api/routes/config_routes.py`,
`apps/arkscope-web/src/api.ts`, `apps/arkscope-web/src/Settings.tsx`,
`apps/arkscope-web/src/ModelRoutingSection.test.ts`, `tests/test_model_routing.py`,
`tests/test_card_synthesis.py`, map + this plan.

NOT modified (ruled): `src/agents/config.py`, `model_routing.TASKS`,
`model_routing.EFFORT_OPTIONS`, `config/user_profile.yaml`, live_resolver pool
behavior.

---

## Stop-Loss Triggers

- A model lacks an official per-model page, or has one but no ArkScope relevance
  per Decision 2 → not in the registry.
- Consolidation changes any live-helper output beyond Fixes A/B (+approved C).
- Compat view membership or alias resolution shifts beyond Task 5's flagged adds.
- Registry needs DAL/DB/network imports; API shape changes non-additively.
- Refusal handling needs more than the three named seams → Fable
  `runtime_ready=False` + follow-up (Decision 10).
- Cache would need secrets; effective view wants to rewrite a route.
- Any default/recommendation flip; any pool wiring; any thinking tri-state
  migration.

---

## Review Gates

1. Old-vs-new equivalence (executable, full id set, ruled-fix exceptions only).
2. View membership pins (7/8 exact; `find_model("opus")` exact).
3. Single-source grep over the four agent modules.
4. Prefix precedence structural; alias integrity.
5. Effort split pins (wire tuples; registry tuples incl. gpt-5.2-codex; CLI
   None-for-OpenAI).
6. Executability matrix (pool-False everywhere, OAuth-cards-False, mixed
   provider, tool_calling requirement).
7. Cache contracts (fingerprint mismatch, zero-model ok, seed_only, no secrets).
8. Effective view: per-task + per-provider credentials; **pinned_only absent
   unless route-pinned (both polarities tested)**; three cache states;
   `discovered_at` surfaced; route-model invariant.
9. Refusal: loop + synthesis + translation produce structured refusals from
   `stop_reason="refusal"` fakes; loop emits no final-answer/done-success and
   `pad.log_final_answer` is not called.
10. Thinking wire mapping pinned (exact tuples from grounding §2) incl.
    default_on→disabled-when-off and always_on-ignores-toggle.
11. Frontend suite + typecheck + build.
12. PG smoke; full virgin A/B.

---

## Task 0: Verify New-Generation + Contested Facts (no code)

1. WebFetch per-model pages: Fable 5 (announcement/effort/context/refusal
   contract incl. stop_details shape), Sonnet 5 (release notes/model page),
   Sol/Terra/Luna. Extract per model: canonical id, official aliases
   (`gpt-5.6` → Sol?), context, max output, thinking contract (five-mode
   mapping + always-on wire shape), effort set, compaction, context mode,
   structured-output, tool-calling, pricing.
2. Contested facts: opus-4.8 context (→ Fix B confirm), opus-4.8 compaction
   (→ Fix C proposal or unchanged), legacy 1M-beta story.
3. Read-only live discovery per configured credential → entitlement table.
4. Emit both tables + pricing lines; re-confirm Decision-6 visibility against
   verified pricing.

Commit: `docs: verify new model generation facts`.
**Gate**: reviewer acks both tables + any Fix C before Task 1.

### Task 0 RESULTS (executed 2026-07-10 — awaiting reviewer ack)

**Verified capability table (new generation — registry seed values for Task 5):**

| id | provider | context | max output | thinking_mode | effort_options | compaction | context_mode | structured_output | tool_calling | pricing (in/out per MTok) | source |
|----|----------|---------|-----------|---------------|----------------|------------|--------------|-------------------|--------------|---------------------------|--------|
| `claude-fable-5` | anthropic | 1,000,000 (default, no beta) | 128,000 | `adaptive_always_on` — "It applies whenever the `thinking` parameter is unset. `thinking: {"type": "disabled"}` is not supported." Wire shape for the toggle-ignored branch: **omit the param** (unset = on) | `("max","xhigh","high","medium","low")` (effort doc lists Fable in all five) | **True** (launch features + compaction beta list) | `ga_1m` | True | True | $10 / $50 | introducing-claude-fable-5 page + effort + context-windows |
| `claude-sonnet-5` | anthropic | 1,000,000 (default, no beta) | 128,000 | `adaptive_default_on` — "adaptive thinking is on by default; pass `thinking: {type: "disabled"}` to turn it off. Manual `{type: "enabled"}` is rejected with a 400" | `("max","xhigh","high","medium","low")` (effort doc: xhigh + max both list Sonnet 5) | True (compaction beta list) | `ga_1m` | True | True | $3 / $15 (**intro $2 / $10 through 2026-08-31**) | models overview (comparison table + footnote 4) + adaptive-thinking |
| `gpt-5.6-sol` | openai | 1,050,000 | 128,000 | `none` | provider six-value set (Decision 7) | False | `standard` | True | True | $5 / $30 (cached in $0.50) | gpt-5.6-sol page; **official alias: "The `gpt-5.6` alias routes requests to GPT-5.6 Sol"** |
| `gpt-5.6-terra` | openai | 1,050,000 | 128,000 | `none` | provider six-value set | False | `standard` | True | True | $2.50 / $15 (cached in $0.25) | gpt-5.6-terra page |
| `gpt-5.6-luna` | openai | 1,050,000 | 128,000 | `none` | provider six-value set | False | `standard` | True | True | $1 / $6 (cached in $0.10) | gpt-5.6-luna page ("cost-sensitive, high-volume… nano model tier") |

Refusal contract (for the Task 5B fakes — verified against refusals-and-fallback):
HTTP 200, `stop_reason: "refusal"`, `stop_details: {"type": "refusal", "category":
<str|null>, "explanation": <str|null>}` (both fields null when uncategorized;
`stop_details` null for every other stop reason); pre-output refusal has
`content: []` and is NOT billed; mid-stream refusal bills what streamed; batch
results may carry `stop_details: null` → **branch on `stop_reason` only** (the
5B fakes and implementation follow this; `data["stop_details"]` passthrough is
display-only). Fable/Sonnet 5/Opus 4.7+ also reject non-default
`temperature/top_p/top_k` with 400 (our config has no temperature field —
verified non-issue).

**Contested existing facts:**

- **Fix B CONFIRMED**: context-windows doc — Opus 4.8 is in the 1M group and
  "For every model with a 1M-token context window, 1M is the default: you don't
  need a beta header." → `context_limit 1_000_000` + `context_mode "ga_1m"`.
- **Fix C ADOPTED (user ack 2026-07-10)**: compaction beta list includes Opus
  4.8 → `supports_compaction("claude-opus-4-8")` flips True in Task 2 (wire
  effect only when the user enables the compaction toggle; same beta header).
  **Standing design concern recorded with the ack (user)**: official server
  compaction is an opt-in convenience, NOT our context-management strategy —
  compacted context can lose retrieval-critical detail on complex problems
  (post-compaction re-search may be needed), and compaction summaries are
  model-bound (a model switch renders them useless). Claude Code / Codex CLI
  pair provider compaction with their OWN context-management logic; adopting
  their compaction does not give us theirs. Whether ArkScope's client-side
  ContextManager + memory layers are coherent WITH server compaction is an open
  audit question → filed as a map backlog item; out of this slice's scope.
- Legacy 1M-beta story: current docs list Sonnet 4.5 as plain 200k and no longer
  advertise `context-1m-2025-08-07` for 4.5 models. Registry keeps the
  `beta_1m` transcription (behavior-identical; the header path is legacy code we
  are not changing).

**Doc-vs-code drift on EXISTING models — user RULED 2026-07-10 (「應參考正式文
件,舊的方式有問題就該改」):**

1. **Fix D ADOPTED** — Sonnet 4.6 max output: docs say 128k, code
   (`_MODEL_MAX_OUTPUT`) says 64,000 → registry records 128,000 and
   `_get_model_max_output("claude-sonnet-4-6")` flips in Task 2. Wire effect:
   thinking-mode requests on sonnet-4.6 get effective max_tokens 128k instead
   of 64k (user flagged: watch that this cannot leak onto new-model behavior —
   it cannot; the value is keyed per model id).
2. **Fix E ADOPTED (via registry; CLI benefits incidentally)** — Sonnet 4.6
   effort tuple gains `max` per the effort doc:
   `("max","high","medium","low")` (docs exclude xhigh for Sonnet 4.6). User
   note recorded: this is a CLI-surface bug and **the CLI is a
   deprioritized/removal-candidate surface** — we fix it only because the
   registry records doc-truth and the CLI helper inherits it for free; no
   CLI-specific investment. CLI-retirement direction filed in the map.
3. Haiku 4.5 canonical dated id is `claude-haiku-4-5-20251001` with dateless
   alias — registry id stays `claude-haiku-4-5` (prefix matching covers dated);
   no change needed. **User proposal recorded (deferred enhancement, not v1)**:
   for seed_only OAuth channels, the picker could BORROW the same provider's
   api_key-scope verified list as an import hint (clearly badged as borrowed —
   entitlements differ per channel, which is exactly why it can only ever be a
   hint). Filed in the map with P2.7 follow-ups.

**Live entitlement table (read-only discovery, 2026-07-10):**

| credential | auth_mode | discovery | new-generation visible |
|------------|-----------|-----------|------------------------|
| anthropic `local:4`/`local:5` (api_key, inactive) | api_key | ok, 10 models | `claude-fable-5`, `claude-sonnet-5` |
| anthropic `local:1` (**ACTIVE**) | claude_code_oauth | seed-only channel (no live listing) | n/a — cache will be `seed_only` |
| openai `local:3` (api_key, **ACTIVE**) | api_key | ok, 129 models | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` |
| openai `local:7` (chatgpt_oauth, inactive) | chatgpt_oauth | not probed (driver dispatch; inactive) | unknown until user runs Settings discovery |

**Live-verification note**: with the CURRENT active anthropic credential
(claude_code_oauth), the effective picker will show `seed_only` + seeds in
Advanced — switching the active anthropic credential to an api_key is what
lights up `verified` for Anthropic models. This is correct behavior, worth
knowing before judging the picker live.

**Smoke targets (5C, per verified pricing)**: OpenAI = `gpt-5.6-luna` ($1/$6 —
cheapest confirmed); Anthropic = `claude-sonnet-5` (intro $2/$10). Fable 5
($10/$50) stays user-gated.

**Decision-6 visibility re-confirmed** against verified pricing: Terra at
$2.50/$15 ≈ gpt-5.5 capability at half its $5/$30 price; Luna $1/$6 above
mini's cost with a bigger capability step; Sol $5/$30 = the frontier pick —
the default set stands as ruled.

---

## Task 1: Capability Registry Module (existing models only)

**Files:** `src/model_capabilities.py`, `tests/test_model_capabilities.py`.

### Step 1: RED tests (complete)

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
    ("claude-opus-4-8", "context_limit"),        # Fix B
    ("claude-opus-4-8", "context_mode"),         # Fix B
    ("claude-opus-4-8", "effort_options"),       # Fix A
    ("claude-opus-4-8", "supports_compaction"),  # Fix C
    ("claude-sonnet-4-6", "max_output"),         # Fix D
    ("claude-sonnet-4-6", "effort_options"),     # Fix E
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
        old_ctx = get_model_context_limit(mid)
        if (mid, "context_limit") in _RULED_FIXES:
            assert cap.context_limit == 1_000_000 and old_ctx == 200_000, mid
        else:
            assert cap.context_limit == old_ctx, mid
        if cap.provider == "anthropic":
            old_out = next((v for k, v in OLD_ANTH_OUT.items() if mid.startswith(k)), 64_000)
        else:
            old_out = _get_openai_max_output(mid)
        if (mid, "max_output") in _RULED_FIXES:               # Fix D
            assert cap.max_output == 128_000 and old_out == 64_000, mid
        else:
            assert cap.max_output == old_out, mid
        if cap.provider == "anthropic":
            expected_mode = (
                "adaptive_opt_in"
                if any(mid.startswith(m) for m in OLD_ADAPTIVE)
                else "manual_budget"
            )
        else:
            expected_mode = "none"
        assert cap.thinking_mode == expected_mode, mid
        old_tuple = get_effort_options(mid)
        if (mid, "effort_options") in _RULED_FIXES:
            if mid == "claude-opus-4-8":                      # Fix A
                assert old_tuple is None
                assert cap.effort_options == ("max", "xhigh", "high", "medium", "low"), mid
            else:                                             # Fix E (sonnet-4-6)
                assert tuple(old_tuple) == ("high", "medium", "low")
                assert cap.effort_options == ("max", "high", "medium", "low"), mid
        elif cap.provider == "anthropic":
            assert cap.effort_options == (tuple(old_tuple) if old_tuple else ()), mid
        old_compact = any(mid.startswith(m) for m in OLD_COMPACT)
        if (mid, "supports_compaction") in _RULED_FIXES:      # Fix C
            assert cap.supports_compaction is True and old_compact is False, mid
        else:
            assert cap.supports_compaction == old_compact, mid
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
    # round-4 SF1: gpt-5.2-codex included
    for mid in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano",
                "gpt-5.2", "gpt-5.2-codex"):
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


def test_picker_visibility_matches_the_ruling():
    vis = {c.id: c.picker_visibility for c in all_models()}
    assert vis["claude-opus-4-8"] == "default"
    assert vis["claude-haiku-4-5"] == "default"
    assert vis["gpt-5.4-mini"] == "default"
    assert vis["claude-opus-4-7"] == "advanced"
    assert vis["claude-sonnet-4-6"] == "advanced"
    for pinned in ("gpt-5.5", "gpt-5.4", "gpt-5.4-nano", "gpt-5.2",
                   "gpt-5.2-codex", "claude-sonnet-4-5", "claude-opus-4-5"):
        assert vis[pinned] == "pinned_only", pinned


def test_default_picker_models_helper():
    assert {c.id for c in default_picker_models("openai")} == {"gpt-5.4-mini"}
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


def test_every_entry_carries_provenance_visibility_and_mode():
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
Pure stdlib. `default_picker_models(provider)` = `picker_visibility == "default"
and runtime_ready`.

### Step 3: Verify + commit

```bash
pytest tests/test_model_capabilities.py -q
python -m compileall -q src/model_capabilities.py
```

Commit: `feat: add model capability registry`.

---

## Task 2: Converge the Nine Sites (behavior-identical + Fixes A/B)

**Files:** `src/agents/anthropic_agent/agent.py`, `src/agents/openai_agent/agent.py`,
`src/agents/shared/context_manager.py`, `src/agents/shared/subagent.py`,
`src/agents/shared/model_catalog.py`, `src/model_routing.py`, their tests.

### Step 1: RED tests (complete — extend `tests/test_model_capabilities.py`)

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
    assert _get_model_max_output("claude-sonnet-4-6") == 128_000   # ruled Fix D
    assert _get_model_max_output("unknown-claude") == 64_000
    assert _supports_adaptive_thinking("claude-sonnet-4-6-future") is True
    assert _supports_effort("claude-haiku-4-5") is False
    assert _supports_compaction("claude-sonnet-4-6") is True
    assert _supports_compaction("claude-opus-4-8") is True    # ruled Fix C
    assert _get_openai_max_output("gpt-5.4-nano") == 128_000
    assert _get_openai_max_output("totally-unknown") == 128_000
    assert get_model_context_limit("gpt-5.4-mini") == 400_000
    assert get_model_context_limit("claude-opus-4-8") == 1_000_000   # Fix B
    assert get_model_context_limit("unknown") == 200_000
    assert _use_extended_context_beta("claude-opus-4-8", True) is False  # wire preserved
    assert _use_extended_context_beta("claude-opus-4-7", True) is False
    assert _use_extended_context_beta("claude-sonnet-4-5", True) is True


def test_build_thinking_param_wire_shapes_pinned():
    # Exact values from live runs (grounding §2) — round-4 SF2.
    from src.agents.anthropic_agent.agent import _build_thinking_param

    class _Cfg:
        max_tokens = 8192
        anthropic_thinking = True

    assert _build_thinking_param("claude-opus-4-8", True, _Cfg()) == (
        {"type": "adaptive"}, 128000,
    )
    assert _build_thinking_param("claude-haiku-4-5", True, _Cfg()) == (
        {"type": "enabled", "budget_tokens": 55808}, 64000,
    )
    assert _build_thinking_param("claude-haiku-4-5", False, _Cfg()) == (None, 8192)


def test_cli_effort_helper_contract_preserved_plus_fix_a():
    from src.agents.shared.model_catalog import get_effort_options
    assert get_effort_options("claude-opus-4-8") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-opus-4-7") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-sonnet-4-6") == ("max", "high", "medium", "low")  # ruled Fix E
    for openai_id in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.2"):
        assert get_effort_options(openai_id) is None


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
    from src.model_capabilities import capability_for

    assert {m.id for m in ROUTING_VIEW} == {
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    }
    assert {m.id for m in CLI_VIEW} == {
        "claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.4-mini",
        "gpt-5.4-nano", "gpt-5.4", "gpt-5.2", "gpt-5.2-codex",
    }
    assert find_model("opus").id == "claude-opus-4-7"
    assert find_model("mini").id == "gpt-5.4-mini"
    assert find_model("codex").id == "gpt-5.2-codex"
    assert is_seed_model("openai", "gpt-5.5")
    for option in ROUTING_VIEW:
        cap = capability_for(option.id)
        assert option.supports_structured_output == cap.supports_structured_output
        assert option.supports_tool_calling == cap.supports_tool_calling
```

Expected RED: helpers still read local tables; opus-4.8 effort None / context
200_000. (`test_build_thinking_param_wire_shapes_pinned` is GREEN before the swap
— it pins the baseline so the registry-driven rewrite cannot drift it.)

### Step 2: Implement

Replace the fact tables with registry reads; keep every signature and fallback
constant (`64_000`, `128_000` default, `200_000` default). `_build_thinking_param`
branches on `capability_for(model).thinking_mode` per Decision 8 (existing modes
produce today's exact outputs; `adaptive_default_on`/`adaptive_always_on` branches
land now but no existing model uses them until Task 5).
`_COMPACTION_MODELS`/`_1M_GA_MODELS`/`_1M_BETA_MODELS` become registry-derived;
wire/beta header constants stay. Both `MODEL_CATALOG`s become derived views via
the view flags (same shapes).

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
`tests/test_model_discovery_cache.py`, `tests/test_model_routing.py`.

### Step 1: RED tests — store (complete)

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
    cache = _mk(tmp_path)
    cache.record_run(**_SCOPE, secret_fingerprint="fp-old", status="ok",
                     models=[{"id": "gpt-5.5", "label": "GPT-5.5", "source": "provider_api"}])
    scope = cache.get(**_SCOPE, secret_fingerprint="fp-new")
    assert scope.status == "never_discovered" and scope.models == []
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

### Step 2: RED tests — caller seam (complete, in `tests/test_model_routing.py`)

```python
def test_discover_models_success_writes_cache(monkeypatch, tmp_path):
    import src.model_credentials as mc

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    recorded = {}

    class _FakeCache:
        def record_run(self, **kw):
            recorded.update(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", lambda *a, **k: _FakeCache())

    class _Cred:  # round-4 MF5: scope needs auth_mode — carry auth_type
        id = "c1"
        secret = "sk-x"
        auth_type = "api_key"

    monkeypatch.setattr(mc, "_resolve_api_credential", lambda *a, **k: _Cred())

    class _FakeModels:
        data = [type("M", (), {"id": "gpt-5.6-luna"})()]

    class _FakeClient:
        def __init__(self, **kw): ...
        class models:  # noqa: N801
            @staticmethod
            def list():
                return _FakeModels()

    monkeypatch.setattr("openai.OpenAI", _FakeClient)

    out = mc.discover_models("openai", "c1")
    assert out.status == "ok"
    assert recorded["status"] == "ok"
    assert recorded["auth_mode"] == "api_key"
    assert recorded["secret_fingerprint"] == mc.secret_fingerprint("sk-x")
    assert [m["id"] for m in recorded["models"]] == ["gpt-5.6-luna"]


def test_discover_models_failure_records_nothing(monkeypatch, tmp_path):
    import src.model_credentials as mc

    calls = []

    class _FakeCache:
        def record_run(self, **kw):
            calls.append(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", lambda *a, **k: _FakeCache())

    class _Cred:
        id = "c1"
        secret = "sk-x"
        auth_type = "api_key"

    monkeypatch.setattr(mc, "_resolve_api_credential", lambda *a, **k: _Cred())

    class _Boom:
        def __init__(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("openai.OpenAI", _Boom)
    out = mc.discover_models("openai", "c1")
    assert out.status == "error" and calls == []
```

(The oauth route branch — all-seed result records `status="seed_only"` — is pinned
handler-direct in Task 4's
`test_discovery_route_records_seed_only_for_oauth_all_seed`, full code there.)

### Step 3: Implement

Tables `model_discovery_runs(provider, auth_mode, credential_id,
secret_fingerprint, status, discovered_at, source_url)` PK(provider, auth_mode,
credential_id) + `model_discovery_models(provider, auth_mode, credential_id,
model_id, label, source)` PK(scope, model_id); one transaction per `record_run`;
house pattern. `secret_fingerprint()` helper in `model_credentials.py`.
Write-through in `discover_models()` (ok + provider_api only) and the oauth
branch of `discover_provider_models` (all-seed → `seed_only`). Additive
`cached_at`/`cache_state` in the discovery response.

Commit: `feat: cache per-credential model discovery`.

---

## Task 4: Resolver + Executability + Per-Task Effective View + Picker

**Files:** `src/model_credentials.py`, `src/model_effective.py`,
`config_routes.py`, `api.ts`, `Settings.tsx`, `ModelRoutingSection.test.ts`,
`tests/test_model_effective.py`.

### Step 1: RED tests — backend (complete)

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
    assert task_auth_executable("card_synthesis", "anthropic", "api_key", opus) is True
    assert task_auth_executable("card_synthesis", "anthropic", "api_key_pool", opus) is False
    assert task_auth_executable("card_synthesis", "anthropic", "claude_code_oauth", opus) is False
    assert task_auth_executable("card_translation", "openai", "chatgpt_oauth", gpt) is False
    assert task_auth_executable("ai_research", "anthropic", "claude_code_oauth", opus) is True
    assert task_auth_executable("ai_research", "openai", "chatgpt_oauth", gpt) is True
    assert task_auth_executable("ai_research", "openai", "api_key", gpt) is True
    assert task_auth_executable("ai_research", "openai", "api_key_pool", gpt) is False
    assert task_auth_executable("ai_research", "openai", "claude_code_oauth", gpt) is False
    assert task_auth_executable("card_synthesis", "anthropic", None, opus) is False
    assert task_auth_executable("card_synthesis", "openai", "api_key", opus) is False


def _routes_mixed() -> dict[str, TaskRoute]:
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
    synth = view["tasks"]["card_synthesis"]
    assert [m["id"] for m in synth["verified"]] == ["claude-opus-4-8"]
    assert any(m["id"] == "claude-opus-4-7" and m["badge"] == "advanced"
               for m in synth["advanced"])   # visible + advanced-visibility
    assert synth["cache_state"] == "ok" and synth["discovered_at"]
    trans = view["tasks"]["card_translation"]
    assert any(m["id"] == "claude-sonnet-4-6" for m in trans["advanced"])  # pinned advanced model
    research = view["tasks"]["ai_research"]
    assert [m["id"] for m in research["verified"]] == ["gpt-5.4-mini"]
    advanced_ids = {m["id"] for m in research["advanced"]}
    # round-4 MF1: pinned_only + visible + NOT route-pinned → absent entirely
    assert "gpt-5.5" not in advanced_ids
    assert "mystery-model" in advanced_ids   # route badge keeps the pin selectable


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

**Route RED tests (handler-direct, real handler names):**

```python
def test_model_catalog_route_gains_additive_effective_block(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr
    from src.model_credentials import CredentialStore

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setattr(cr, "resolve_active_credential", lambda provider, **kw: None)
    out = cr.model_catalog(store=CredentialStore())
    for key in ("providers", "tasks", "models", "effort_options", "routes"):
        assert key in out
    assert set(out["effective"]["tasks"]) == {
        "card_synthesis", "card_translation", "ai_research",
    }
    block = out["effective"]["tasks"]["ai_research"]
    assert {"verified", "advanced", "cache_state", "discovered_at"} <= set(block)
    assert block["cache_state"] == "never_discovered"   # fail-closed shape


def test_discovery_route_records_seed_only_for_oauth_all_seed(monkeypatch, tmp_path):
    # round-5 MF2: the OAuth branch of discover_provider_models
    # (config_routes.py:589) returns the driver result directly; when every model
    # is source="seed" (claude_code_oauth has no live listing) the route must
    # write a seed_only run to the cache — otherwise the discovery nudge loops
    # forever. Handler-direct with the real signature (body, store, token_store).
    from src.api.routes import config_routes as cr
    from src.model_credentials import DiscoveredModel, ModelDiscoveryResult

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    recorded = {}

    class _FakeCache:
        def record_run(self, **kw):
            recorded.update(kw)

    monkeypatch.setattr(cr, "ModelDiscoveryCache", lambda *a, **k: _FakeCache())

    class _OauthCred:
        id = "local:oauth-1"
        provider = "anthropic"
        auth_type = "claude_code_oauth"

    class _FakeStore:
        db_path = str(tmp_path / "profile_state.db")
        def get(self, credential_id):
            return _OauthCred()

    class _FakeDriver:
        async def discover_models(self):
            return ModelDiscoveryResult(
                provider="anthropic", credential_id="local:oauth-1", status="ok",
                models=[DiscoveredModel(id="claude-opus-4-8", provider="anthropic",
                                        label="Opus 4.8", source="seed")],
            )

    monkeypatch.setattr(cr, "_credential_store", lambda store: _FakeStore())
    monkeypatch.setattr("src.auth_drivers.factory.build_driver",
                        lambda **kw: _FakeDriver())

    body = cr.ModelDiscoveryRequest(provider="anthropic", credential_id="local:oauth-1")
    out = cr.discover_provider_models(body, store=_FakeStore(), token_store=object())

    assert recorded["status"] == "seed_only"                      # the write-through
    assert recorded["provider"] == "anthropic"
    assert recorded["auth_mode"] == "claude_code_oauth"
    assert recorded["credential_id"] == "local:oauth-1"
    assert recorded["secret_fingerprint"] == "oauth"
    assert recorded["models"] == []                               # seeds are not entitlement rows
    assert out["status"] == "ok" and "models" in out              # old fields intact
    assert out["cache_state"] == "seed_only"                      # additive fields present
    assert out["cached_at"]
```

(`ModelDiscoveryRequest`/`ModelDiscoveryResult`/`DiscoveredModel` are the
existing pydantic models the route already uses; if `_credential_store` wraps
differently at implementation time the fake moves to the same seam the real
handler calls — the pinned contract is the `record_run` payload.)

### Step 2: RED tests — frontend (house harness; extends the file's `catalog()` fixture)

```tsx
it("model picker defaults to verified and reveals advanced with badges", () => {
  const cat = catalog();
  (cat as any).effective = {
    tasks: {
      ai_research: {
        verified: [{ id: "gpt-5.4-mini", label: "GPT-5.4 mini", badge: null }],
        advanced: [
          { id: "claude-sonnet-4-6", label: "Sonnet 4.6", badge: "advanced" },
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
  expect(options).not.toContain("claude-sonnet-4-6");   // advanced hidden by default

  act(() => {
    (research.querySelector('[aria-label="顯示進階模型"]') as HTMLInputElement).click();
  });
  const expanded = Array.from(research.querySelectorAll("option")).map((o) => o.value);
  expect(expanded).toContain("claude-sonnet-4-6");
  expect(research.textContent).toContain("最後驗證可見");

  const synth = host!.querySelector('[data-testid="route-card_synthesis"]')!;
  expect(synth.textContent).toContain("跑一次模型探索以驗證");
  const trans = host!.querySelector('[data-testid="route-card_translation"]')!;
  expect(trans.textContent).toContain("此通道無法線上列出模型");
  expect(trans.textContent).not.toContain("跑一次模型探索以驗證");
});
```

(`render()` gains an optional catalog argument; `data-testid="route-<task>"`
wrappers are part of the implementation contract; the saved-route-selected
invariant is asserted via the fixture's `mystery-model` pin: after expanding
advanced, the select's value equals `"mystery-model"`.)

### Step 3: Implement

`resolve_active_credential()` (inventory-based incl. env rows; `secret_fingerprint()`
sha256[:16]; `"oauth"` for OAuth modes); `task_auth_executable()` +
`effective_model_view(cache, routes, credentials)`; additive `effective` block in
`model_catalog`; picker split in `ModelRoutingSection`; oauth discovery route
branch records `seed_only`. `PUT /config/model-routes` untouched.

Commit: `feat: verified-first per-task model picker`.

---

## Task 5: New Generation Lands (5 models) + Refusal Handling

**Files:** `src/model_capabilities.py`, `src/anthropic_refusal.py`,
`src/agents/anthropic_agent/agent.py`, `src/card_synthesis.py`,
`tests/test_card_synthesis.py`, **`tests/test_events.py`** (loop refusal test
joins the existing `TestAnthropicStream` class), ledger-swept tests.
**No default flips. No `src/agents/shared/events.py` change** (refusals reuse
`EventType.error`; the enum value-set pin at `test_events.py:18` stays intact).

### 5A: Registry entries (RED first)

Entries for the Task 0-verified ids — Fable 5 (`adaptive_always_on`), Sonnet 5
(`adaptive_default_on`), Sol/Terra/Luna (`none`) — all
`picker_visibility="default"`, both view flags set, per-model source pages,
`verified_at` = Task 0 date. Tests: alias routing (`gpt-5.6` → Sol iff docs
define it; `find_model("fable")`), alias uniqueness sweep, `model_provider()`
classification, and thinking-wire mapping for the two new modes:

```python
def test_thinking_wire_mapping_for_new_modes():
    from src.agents.anthropic_agent.agent import _build_thinking_param

    class _Cfg:
        max_tokens = 8192
        anthropic_thinking = True

    # adaptive_default_on (Sonnet 5): True → adaptive; False → EXPLICIT disabled
    on_param, _ = _build_thinking_param("claude-sonnet-5", True, _Cfg())
    assert on_param == {"type": "adaptive"}
    off_param, _ = _build_thinking_param("claude-sonnet-5", False, _Cfg())
    assert off_param == {"type": "disabled"}
    # adaptive_always_on (Fable): toggle ignored; never disabled/budget
    for toggle in (True, False):
        p, _ = _build_thinking_param("claude-fable-5", toggle, _Cfg())
        assert p is None or p == {"type": "adaptive"}   # exact shape per Task 0
        assert p != {"type": "disabled"}
        assert not (isinstance(p, dict) and "budget_tokens" in p)
```

(The always-on exact shape — omit vs `{"type":"adaptive"}` — is fixed by the Task
0 doc extract; the assertion tightens to `==` once Task 0 lands.)

### 5B: Structured refusal handling (RED first — the three named seams)

New `src/anthropic_refusal.py`: `class AnthropicRefusalError(RuntimeError)`
(carries `stop_details`) + `def is_refusal(message) -> bool`
(`getattr(message, "stop_reason", None) == "refusal"`).

**Card seams (in `tests/test_card_synthesis.py`; `_packet()` is the file's
existing helper at :22):**

```python
def _refusal_response():
    # Match _make_mock_response's discipline: content empty, stop_reason refusal;
    # no MagicMock-usage pitfalls apply here (cards read .content/.stop_reason).
    response = MagicMock()
    response.stop_reason = "refusal"
    response.content = []
    response.stop_details = {"category": "safety"}
    return response


def test_card_synthesis_raises_structured_refusal(monkeypatch):
    from src import card_synthesis as cs
    from src.anthropic_refusal import AnthropicRefusalError

    client = MagicMock()
    client.messages.create.return_value = _refusal_response()
    # Function-local import → patch the SOURCE module (round-4 MF3).
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda **kw: client,
    )
    with pytest.raises(AnthropicRefusalError):
        cs._synthesize_anthropic(_packet(), "claude-fable-5")


def test_card_translation_raises_structured_refusal(monkeypatch):
    # round-4 MF3: _translate_anthropic (card_synthesis.py:460) shares the error.
    from src import card_synthesis as cs
    from src.anthropic_refusal import AnthropicRefusalError

    client = MagicMock()
    client.messages.create.return_value = _refusal_response()
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda **kw: client,
    )
    with pytest.raises(AnthropicRefusalError):
        cs._translate_anthropic("claude-fable-5", "sys", "user", {}, "zh-TW")
```

**Loop seam (round-5 MF1 — extends `tests/test_events.py`'s existing
`TestAnthropicStream` harness verbatim: `_make_mock_response`, `_make_stream_cm`,
`mock_deps`; the fixture's `anthropic.Anthropic` patch intercepts the
env-fallback client that the loop's function-local `live_anthropic_client()`
builds, exactly as the file's existing tests do):**

```python
    def test_refusal_stop_surfaces_error_not_done(self, mock_deps):
        # Today (RED reason): stop_reason="refusal" falls into the generic
        # non-tool_use branch → a successful empty done event + log_final_answer.
        mock_client = mock_deps["client"]          # mock_deps yields a dict
        refusal = _make_mock_response(stop_reason="refusal", content_blocks=[])
        refusal.stop_details = {"category": "safety"}
        mock_client.messages.stream.return_value = _make_stream_cm(refusal)

        from src.agents.anthropic_agent.agent import run_query_stream

        with patch(
            "src.agents.shared.scratchpad.Scratchpad.log_final_answer"
        ) as mock_final:
            events = self._collect_events(         # class helper (asyncio.run)
                run_query_stream("q", dal=MagicMock())   # hermetic: no real DAL
            )

        types = [e.type for e in events]
        assert EventType.done not in types                     # no success event
        error_events = [e for e in events if e.type == EventType.error]
        assert error_events, types
        assert error_events[-1].data["code"] == "model_refusal"
        assert error_events[-1].data["stop_details"] == {"category": "safety"}
        mock_final.assert_not_called()                         # never logged as answer
```

(`_make_mock_response` builds `usage` as a SimpleNamespace so the token tracker
records normally — a hand-rolled `usage=None` fake would crash the logger before
refusal classification. Harness facts verified: `mock_deps` yields a DICT keyed
`client`/`mock_tools`/`mock_exec`/`config`; the class collects via
`self._collect_events(...)` (asyncio.run), not `@pytest.mark.anyio`; `dal` must
be a MagicMock or the loop builds a real DataAccessLayer.
`src.agents.shared.scratchpad.Scratchpad` is the real import path
(agent.py:26). RED reason today: the run yields `done` and calls
`log_final_answer`. If the loop cannot route refusals to `EventType.error`
without refactor depth beyond this branch, the Decision-10 escape hatch fires:
Fable ships `runtime_ready=False`, this test moves to the follow-up slice, and
synthesis/translation refusal handling still lands.)

### 5C: Ledger sweep + live smoke

Sweep by NEW ids across `tests/`; smoke = **one minimal live call per provider**
(cheapest verified gpt-5.6 id — expected Luna; Sonnet 5 promo-priced); Fable
smoke user-gated (premium). Non-smoked ids annotated `runtime-unverified`.

Commit: `feat: land fable-5 sonnet-5 and gpt-5.6 generation`.

---

## Task 6: Gates, Full A/B, Docs Closeout

1. Focused backend: capability/cache/effective/routing/card suites + sweep set.
2. Frontend: full vitest + typecheck + build.
3. Static gates: single-source grep; `rg -n "psycopg2|postgres"
   src/model_capabilities.py src/model_discovery_cache.py src/model_effective.py
   src/anthropic_refusal.py` → empty.
4. PG smoke `ok:true` `pg_attempts:[]`.
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
6. `feat: land fable-5 sonnet-5 and gpt-5.6 generation`
7. `docs: close model capability catalog build`
