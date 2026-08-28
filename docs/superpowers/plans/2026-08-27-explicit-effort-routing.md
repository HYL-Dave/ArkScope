# Current-Generation Explicit Effort Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit new ArkScope task routes to the approved six current-generation
models, remove ambiguous `default` and quality-disabling `none` choices, and
ship complete built-in defaults: Opus 5/high, Sonnet 5/medium, and Luna/xhigh.

**Architecture:** Preserve legacy capability facts for history and low-level diagnostics, but add a current/retired task-route policy that provider discovery and custom entry cannot bypass. Backend route admission and frontend controls share that model policy and one explicit-effort policy. Existing rows remain readable; retired or ambiguous routes become incomplete until explicitly corrected.

**Tech Stack:** Python 3.10, FastAPI/Pydantic, React 18, TypeScript, Vitest, Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-explicit-effort-routing-design.md`

## Global Constraints

- Do not add an LLM route or model call to security-lifecycle automation.
- `default` and `none` remain provider/catalog/history facts but are not task-route choices.
- The only current task-route models are `claude-fable-5`, `claude-opus-5`,
  `claude-sonnet-5`, `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`.
- Known retired IDs remain capability/history facts but cannot be selected through
  seed, discovery, route pin, or custom-model entry.
- Existing route/history rows are never rewritten automatically.
- Custom/unknown models require an explicit provider effort from the filtered
  provider union; a known retired ID is not custom.
- No provider call, production database access, app restart, merge, or push.
- Use `apply_patch` for all manual edits and TDD for every behavior change.

---

### Task 1: Current-Generation Model Authority

**Files:**
- Modify: `src/model_capabilities.py`
- Modify: `src/model_routing.py`
- Modify: `src/model_effective.py`
- Modify: `src/agents/config.py`
- Modify: `src/agents/shared/subagent.py`
- Modify: `src/agents/shared/compressor/summary_callers.py`
- Modify: `src/investor_profile_calibration_agent.py` only if its runtime path is classified active
- Modify: `src/tools/code_generator.py`
- Modify: `config/.env.template`
- Test: `tests/test_model_capabilities.py`
- Test: `tests/test_model_effective.py`
- Test: `tests/test_model_routing.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_model_tiers.py`
- Test: `tests/test_card_synthesis.py`
- Test: `tests/test_ai_research_route.py`
- Test: `tests/test_subagent.py`
- Test: `tests/test_code_generator.py`
- Test: `tests/test_compressor_layer5.py`
- Test: `tests/test_research_runs.py`
- Test: `tests/test_research_routes.py`
- Test: `tests/test_model_task_test.py`
- Test: `tests/test_investor_profile_calibration.py` only if calibration is active
- Test: every additional runtime-default owner found by the inventory below

**Interfaces:**
- Consumes: official provider model facts and existing capability lookup.
- Produces: one exact current model set, retained retired facts, and
  `model_retired` task-route eligibility.

- [x] **Step 1: Write failing current-lineup tests**

Pin the exact set:

```python
CURRENT_TASK_ROUTE_MODELS = {
    "claude-fable-5", "claude-opus-5", "claude-sonnet-5",
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
}
assert {c.id for c in all_models() if c.in_routing_seed} == CURRENT_TASK_ROUTE_MODELS
```

The pre-change registry has 17 entries. Opus 5 makes 18 total: exactly six are
current and the other 12 existing entries are retired from new task routing.

Add official fact owners for `claude-opus-5`: canonical ID, Anthropic provider,
1M context, 128K output, thinking on by default, all five task effort levels,
and current task-route status. Record the official Anthropic source URL and
`verified_at="2026-08-27"`; that date means documentation verification, not live
entitlement or execution.

Use the verified official sources:

- model identity/specifications:
  `https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5`;
- effort ladder:
  `https://platform.claude.com/docs/en/build-with-claude/effort`.

Set `verified_at="2026-08-28"`; it records this documentation read, not a live
provider or entitlement test.

Pin complete task defaults:

- card synthesis: `anthropic / claude-opus-5 / high`;
- content translation: `anthropic / claude-sonnet-5 / medium`;
- AI Research: `openai / gpt-5.6-luna / xhigh`.

Pin all nine `AgentConfig` task fields, not only the three effort fields:

```python
card_synthesis_provider = "anthropic"
card_synthesis_model = "claude-opus-5"
card_synthesis_effort = "high"
card_translation_provider = "anthropic"
card_translation_model = "claude-sonnet-5"
card_translation_effort = "medium"
ai_research_provider = "openai"
ai_research_model = "gpt-5.6-luna"
ai_research_effort = "xhigh"
```

Add two provider-specific owners for `resolve_research_route`: a fresh OpenAI
request resolves to Luna/`xhigh`, while a fresh Anthropic request resolves to the
current Anthropic default model/`xhigh`. The latter exercises the provider-mismatch
fallback and must fail while the final branch still returns `(model, None)`. A
matching stored legacy route with blank/`default` effort remains ambiguous and is
not repaired by this fallback.

Pin generic runtime tiers to Anthropic Sonnet 5 / Opus 5 and OpenAI Luna / Sol.
Inventory every active runtime hard-code before editing. Move active subagent,
summarizer, and code-generator defaults according to the exact mapping below;
classify calibration, low-level credential probes, compatibility facts,
historical fixtures, and documentation examples explicitly instead of replacing
them by blind text substitution.

For current active defaults, use these exact replacements:

- `code_analyst` and `deep_researcher`: `gpt-5.6-sol`;
- `data_summarizer`: `claude-sonnet-5`;
- `reviewer` and code-generation fallback: `claude-opus-5`;
- Anthropic compression/summary calls: `claude-sonnet-5`;
- `DEFAULT_LLM_MODEL`: `gpt-5.6-luna`.

Give `DEFAULT_ANTHROPIC_MODEL` in `summary_callers.py` a direct owner. Do not rely
on broad compressor integration tests that inject their own caller/model.

If calibration remains unwired, record its literals as dormant rather than
changing them speculatively. Credential probes remain low-level diagnostics and
are not changed merely because their cheap probe model is retired from task
routing.

For every previously known non-current ID, assert capability lookup still works
but task-route eligibility returns `model_retired`. Assert a discovered retired
model is absent from verified/advanced groups; an existing route pin remains
visible only as an ineligible `route` entry with reason `model_retired`.

Keep a positive owner proving a genuinely unknown custom ID remains eligible as
`model_not_in_registry` rather than being conflated with a known retired ID.

Expose one provider-neutral catalog policy with canonical `current_model_ids`
and `retired_model_ids`. This is model-policy data, not discovery entitlement.
It must use the same longest-prefix/canonical-ID semantics as backend lookup.

- [x] **Step 2: Run the focused RED**

```bash
pytest tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_routing.py tests/test_agents.py tests/test_model_tiers.py tests/test_card_synthesis.py tests/test_ai_research_route.py tests/test_subagent.py tests/test_code_generator.py tests/test_compressor_layer5.py tests/test_research_runs.py tests/test_research_routes.py tests/test_model_task_test.py tests/test_investor_profile_calibration.py -q
```

Expected: Opus 5 and retirement-policy assertions fail against the old registry.

- [x] **Step 3: Implement current/retired model policy**

Add an explicit task-route lifecycle fact to `ModelCapability`; do not overload
`runtime_ready`, which remains a provider-adapter fact. Add Opus 5 from official
facts. Mark exactly the approved six current and every other known entry retired.

Current models use default picker visibility and routing-seed membership. Retired
models retain their capability metadata but use pinned-only visibility, no seed
membership, and no recommendations. Update effective-model projection so
discovery cannot promote retired IDs and a route pin receives `model_retired`.
Known retired custom input must resolve to the same rejection.

Update runtime/task defaults:

- card synthesis: `claude-opus-5`;
- content translation and Anthropic summarization: `claude-sonnet-5`;
- AI Research: `gpt-5.6-luna`;
- generic Anthropic advanced fallback: `claude-opus-5`;
- generic Anthropic normal fallback: `claude-sonnet-5`;
- generic OpenAI normal fallback: `gpt-5.6-luna`;
- generic OpenAI advanced fallback: `gpt-5.6-sol`.

Set the three built-in task efforts to `high`, `medium`, and `xhigh`
respectively. A truly fresh install must therefore resolve to a complete route.
An existing stored `default`, `none`, blank, or retired route remains unchanged
and projects as incomplete until the user replaces it.

Change the terminal fallback in `resolve_research_route`, not only the dataclass
defaults. When the requested provider differs from the configured AI Research
route, return that provider's current built-in model with the explicit built-in
AI Research effort `xhigh`; never return `None`. Preserve an ambiguous effort on
a matching stored legacy route so Task 3 can reject it honestly.

Do not rewrite stored routes or historical runs. The approved spec supersedes
the stale Luna rejection and missing-Opus-5 statements; do not edit the
user-owned dirty Priority Map in this slice.

- [x] **Step 4: Run focused GREEN plus stale-default inventory**

```bash
pytest tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_routing.py tests/test_agents.py tests/test_model_tiers.py tests/test_card_synthesis.py tests/test_ai_research_route.py tests/test_subagent.py tests/test_code_generator.py tests/test_compressor_layer5.py tests/test_research_runs.py tests/test_research_routes.py tests/test_model_task_test.py tests/test_investor_profile_calibration.py -q
rg -n 'claude-(opus-4-[578]|sonnet-4-[56]|haiku-4-5)|gpt-5\.(2(-codex)?|4(-mini|-nano)?|5)' src config/.env.template tests
```

Expected: tests pass. Record every remaining match as one of capability/history,
low-level diagnostic, compatibility fixture, or documentation example. No active
task/runtime default or new-route recommendation may remain unclassified.

- [x] **Step 5: Commit Task 1**

```bash
git add src/model_capabilities.py src/model_routing.py src/model_effective.py src/agents/config.py src/agents/shared/subagent.py src/agents/shared/compressor/summary_callers.py src/investor_profile_calibration_agent.py src/tools/code_generator.py config/.env.template tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_routing.py tests/test_agents.py tests/test_model_tiers.py tests/test_card_synthesis.py tests/test_ai_research_route.py tests/test_subagent.py tests/test_code_generator.py tests/test_compressor_layer5.py tests/test_research_runs.py tests/test_research_routes.py tests/test_model_task_test.py tests/test_investor_profile_calibration.py
git commit -m "feat(models): admit current generation routes"
```

### Task 2: Backend Task-Route Effort Authority

**Files:**
- Modify: `src/model_routing.py`
- Test: `tests/test_model_routing.py`

**Interfaces:**
- Consumes: `capability_for(model)` and factual `EFFORT_OPTIONS`.
- Produces: `TASK_ROUTE_EFFORT_ORDER`,
  `selectable_effort_ids_for_model(provider, model) -> tuple[str, ...]`
  and `is_valid_task_route_effort(provider, effort, model) -> bool`.

- [x] **Step 1: Write failing policy tests**

Add tests proving:

```python
assert selectable_effort_ids_for_model("openai", "gpt-5.6-luna") == (
    "low", "medium", "high", "xhigh", "max",
)
assert selectable_effort_ids_for_model("anthropic", "claude-opus-5") == (
    "low", "medium", "high", "xhigh", "max",
)
assert "none" in effort_ids_for_model("openai", "gpt-5.6-luna")
assert is_valid_task_route_effort("openai", "none", "gpt-5.6-luna") is False
assert is_valid_task_route_effort("openai", "default", "gpt-5.6-luna") is False
assert is_valid_task_route_effort("openai", "max", "gpt-5.6-luna") is True
```

Also assert an unknown OpenAI model receives the explicit provider union without
`default` or `none`. Parameterize all six current models and prove they expose
the identical five-value task-route set. A retired model is rejected by the
model authority before its effort value matters.

- [x] **Step 2: Run the focused RED**

Run:

```bash
pytest tests/test_model_routing.py -q
```

Expected: only the new imports/assertions fail because the task-route policy does
not exist.

- [x] **Step 3: Implement the pure policy**

Keep `effort_ids_for_model` and `is_valid_effort` unchanged for provider-native
diagnostics. Add `selectable_effort_ids_for_model(...)` and
`is_valid_task_route_effort(...)`, exporting only the five real task values for
current models and the filtered provider union for genuinely unknown custom IDs.

Define `TASK_ROUTE_EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")`
and project supported values through that order. Do not reorder or rewrite the
provider-native `_OPUS_EFFORTS` capability tuple; task-control order is a product
projection, not a provider fact.

- [x] **Step 4: Run the focused GREEN**

Run:

```bash
pytest tests/test_model_routing.py -q
```

Expected: pass.

- [x] **Step 5: Commit Task 2**

```bash
git add src/model_routing.py tests/test_model_routing.py
git commit -m "fix(models): define explicit task effort policy"
```

### Task 3: Backend Admission Without Silent Defaulting

**Files:**
- Modify: `src/api/routes/config_routes.py`
- Modify: `src/api/routes/research.py`
- Modify: `src/research_runs.py`
- Modify: `src/card_synthesis.py`
- Test: `tests/test_model_routing.py`
- Test: `tests/test_research_routes.py`
- Test: `tests/test_research_runs.py`
- Test: `tests/test_ai_research_route.py`
- Test: `tests/test_model_task_test.py`
- Test: `tests/test_card_synthesis.py`

**Interfaces:**
- Consumes: current-model authority from Task 1 and explicit-effort authority
  from Task 2.
- Produces: fail-closed route save/import/task-test/research-run admission.

- [x] **Step 1: Write failing route tests**

Add exact tests that prove:

```python
with pytest.raises(HTTPException) as exc:
    update_model_routes(ModelRoutesUpdate(routes={
        "ai_research": RouteUpdate(
            provider="openai", model="gpt-5.6-luna", effort="default",
        ),
    }), store=store)
assert exc.value.status_code == 400
```

Repeat for `none`, an unsupported effort, and each known retired model. Change
the import owner so ambiguous effort or a retired model is skipped and no row is
persisted.

Add research-run owners proving `default`/`none` on a current explicit model is
rejected before `create_run_with_user_message`, while a valid explicit effort
reaches the existing scheduling fake.

Add fresh-install owners proving that an absent DB/profile route resolves to the
three approved complete tuples (`high`, `medium`, `xhigh`) and that an implicit
OpenAI or Anthropic Research request reaches persistence with a real effort.
Keep separate legacy-row owners proving stored `default`/`none` values remain
readable but cannot start a new run.

Add a producer/consumer owner for the latest-successful-selection endpoint. A
historical run with SQL `NULL` or blank effort must return nullable/blank
incomplete provenance, never the fabricated string `default`; the frontend must
therefore be able to distinguish a legacy incomplete selection from a real
explicit effort. Keep a positive owner proving a stored real effort is returned
byte-for-byte.

Add `test_model_task_test.py` owners proving a known retired model and an
ambiguous effort return HTTP 400 before `dispatch_task_model_test`. A genuinely
unknown custom model with a real effort must still reach the bounded dispatcher.
Add a separate positive owner using one approved current model so the task-test
route is not proved only by custom or retired fixtures.

Add card synthesis and translation owners for both providers: an effort
rejection causes exactly one attempted task call and propagates through the
existing bounded error surface. It must never call `run_once("default")`.
Also cover provider/model override paths: they use the approved task default
effort (`high` for synthesis, `medium` for translation), never an implicit
cross-provider `default`.

- [x] **Step 2: Run the route RED**

Run:

```bash
pytest tests/test_model_routing.py tests/test_research_routes.py tests/test_research_runs.py tests/test_ai_research_route.py tests/test_model_task_test.py tests/test_card_synthesis.py -q
```

Expected: the new admission tests fail because current code normalizes to
`default` and queues ambiguous research runs.

- [x] **Step 3: Implement fail-closed admission**

In `update_model_routes` and `run_task_model_test`, evaluate model retirement
before effort. Return HTTP 400 with typed, bounded `model_retired`,
`effort_required`, or `effort_not_supported` detail before dispatch. In import,
append the task to `skipped` and continue. Do not change
`run_provider_model_test`, which remains a low-level provider diagnostic.

In `create_research_run`, resolve model/effort first, validate the resulting
task tuple, then reject with HTTP 422 before thread/run persistence. Every
current model requires a real effort; do not exempt any of the approved six.

In `ResearchRunStore.latest_successful_for_thread`, preserve `NULL`/blank effort
as incomplete compatibility data. Change `ResearchSelection` and the route
response type as needed; do not map absence to `default`. This is a read-shape
change only and must not rewrite historical rows.

Remove the task-level effort fallback in all four card synthesis/translation
provider seams. A provider rejection must not silently change the recorded
effort to `default`. Preserve raw diagnostic fallback behavior outside task
execution. Replace the four cross-provider task-entry fallbacks with the
approved explicit task effort; do not add a hidden default argument at another
layer.

- [x] **Step 4: Run the route GREEN**

Run:

```bash
pytest tests/test_model_routing.py tests/test_research_routes.py tests/test_research_runs.py tests/test_ai_research_route.py tests/test_model_task_test.py tests/test_card_synthesis.py -q
```

Expected: pass.

- [x] **Step 5: Commit Task 3**

```bash
git add src/api/routes/config_routes.py src/api/routes/research.py src/research_runs.py src/card_synthesis.py tests/test_model_routing.py tests/test_research_routes.py tests/test_research_runs.py tests/test_ai_research_route.py tests/test_model_task_test.py tests/test_card_synthesis.py
git commit -m "fix(models): reject ambiguous task efforts"
```

### Task 4: Shared Frontend Model/Effort Projection and Settings

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/researchModels.ts`
- Modify: `apps/arkscope-web/src/modelRoutingUx.ts`
- Modify: `apps/arkscope-web/src/settings/ModelRoutingSection.tsx`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Test: `apps/arkscope-web/src/researchModels.test.ts`
- Test: `apps/arkscope-web/src/modelRoutingUx.test.ts`
- Test: `apps/arkscope-web/src/ModelRoutingSection.test.ts`
- Test: `apps/arkscope-web/src/SettingsModelRouting.test.ts`

**Interfaces:**
- Consumes: catalog `model.effort_options` plus the provider-neutral task-route
  model policy.
- Produces: updated `effortOptionsForModel(...)`, current-model projection,
  and typed `model_retired` / `effort_required` save blockers.

- [x] **Step 1: Write failing helper and Settings tests**

Require these outcomes:

```ts
expect(effortOptionsForModel(catalog, "openai", "gpt-5.6-luna")
  .map((item) => item.id)).toEqual(["low", "medium", "high", "xhigh", "max"]);
expect(effortOptionsForModel(catalog, "anthropic", "claude-opus-5")
  .map((item) => item.id)).toEqual(["low", "medium", "high", "xhigh", "max"]);
expect(effortOptionsForModel(catalog, "openai", "gpt-future-custom")
  .map((item) => item.id)).toEqual(["low", "medium", "high", "xhigh", "max"]);
```

Render Settings with legacy `default` and `none` routes. Assert neither appears
as an `<option>`, the effort-capable rows show an empty required selector, Save
and task Test are disabled, and the localized explicit-effort warning names the
affected task. Render a retired route and assert it is retained as the current
read-only identity, receives the localized retirement warning, and cannot save
or task-test until a current model is selected. Assert retired models discovered
by a credential do not appear as new choices.

Populate both provider effort fixtures and the Opus 5 model fixture before
asserting Anthropic behavior. Replace the existing unknown-custom expectation of
`["default"]`; it is a RED owner for the new explicit provider union.

Rebuild every catalog fixture used by `researchModels.test.ts`,
`ModelRoutingSection.test.ts`, and `SettingsModelRouting.test.ts` from the same
closed test roster: all six current model IDs and provider effort lists in
`low`, `medium`, `high`, `xhigh`, `max` order. Fixtures may use a shared test
builder or explicit invariant assertions; they must not import mutable production
registry objects at runtime. Retired-model cases stay as deliberately named
compatibility fixtures rather than accidental defaults/recommendations.

Add a model-change owner: retain the selected effort across current-model
changes because all six approved models expose the exact same five values.
Legacy `default`/`none` selections become empty and incomplete.

Add line-owning Settings tests for each current coercion point:

- route hydration must preserve an invalid legacy value for diagnosis while the
  selector projects an empty required choice;
- Save and task Test send the selected real effort exactly and never use
  `row.effort || "default"`;
- task Test is disabled when effort is incomplete;
- provider, model, and custom-model changes retain a supported real effort or
  produce `""`, never `default`;
- snapshot-current comparison uses the exact effort rather than a synthetic
  default.

Add a pure-policy owner proving completeness is checked before semantic equality:
an unchanged baseline/draft pair containing `default`, `none`, blank effort, or a
retired model still yields its typed blocker. Also prove blank and `default` are
not semantically equal.

- [x] **Step 2: Run the frontend RED**

Run:

```bash
npm test -- --run src/researchModels.test.ts src/modelRoutingUx.test.ts src/ModelRoutingSection.test.ts src/SettingsModelRouting.test.ts
rg -n 'default|none' src/researchModels.ts src/modelRoutingUx.ts src/settings/ModelRoutingSection.tsx src/Settings.tsx
```

Working directory: `apps/arkscope-web`.

Expected: new tests fail because `default`/`none` remain options and save
blocking only understands credentials. The pre-change grep must return at least
one match; record the exact active task-effort coercion sites so the closeout
scan is a real tripwire rather than a pattern that never matched the old code.

- [x] **Step 3: Implement shared projection and Settings behavior**

Keep the existing exported name `effortOptionsForModel`; change its task-route
semantics without creating a rename-only break across `Research.tsx`,
`researchSelection.ts`, and Settings. Filter `default`/`none`, distinguish
current, retired, and genuinely unknown custom IDs, and add a pure completeness
helper used by both Settings and Research.

Add the catalog task-route policy to `api.ts`. Change `blockedRouteSaves` to
consume that policy (or the full catalog) so `model_retired` is derived from
data, not a duplicated frontend constant. Extend it with `model_retired` and
`effort_required`, then update every caller and owner. Render separate localized
messages by blocker reason. Remove the translated effort-description line from
the task card. Show only the six current catalog models, plus the existing
genuinely unknown custom-model flow.

Run route completeness/retirement validation before the unchanged-row
`routesSemanticallyEqual` early return. Compare trimmed effort values exactly;
do not coerce blank and `default` into equality. In `Settings.tsx` and
`ModelRoutingSection.tsx`, remove every task-effort fallback used by hydration,
Save, Test, provider change, model change, and custom entry. An invalid stored
value may remain visible in warning/provenance text, but the selector value is
empty and both Save and that row's Test remain disabled until a real effort is
chosen.

- [x] **Step 4: Run the frontend GREEN**

Run:

```bash
npm test -- --run src/researchModels.test.ts src/modelRoutingUx.test.ts src/ModelRoutingSection.test.ts src/SettingsModelRouting.test.ts
npm run typecheck
```

Expected: pass.

- [x] **Step 5: Commit Task 4**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/researchModels.ts apps/arkscope-web/src/modelRoutingUx.ts apps/arkscope-web/src/settings/ModelRoutingSection.tsx apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/i18n/resources/en/settings.ts apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts apps/arkscope-web/src/researchModels.test.ts apps/arkscope-web/src/modelRoutingUx.test.ts apps/arkscope-web/src/ModelRoutingSection.test.ts apps/arkscope-web/src/SettingsModelRouting.test.ts
git commit -m "fix(web): require explicit task effort"
```

### Task 5: AI Research Current Model and Explicit Selection

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/researchSelection.ts`
- Modify: `apps/arkscope-web/src/Research.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/research.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts`
- Test: `apps/arkscope-web/src/researchSelection.test.ts`
- Test: `apps/arkscope-web/src/ResearchWorkspace.test.tsx`

**Interfaces:**
- Consumes: Task 4 selectable options/completeness helper.
- Produces: global sticky AI Research tuples containing a real effort, or a blocked/incomplete selection that cannot submit.

- [x] **Step 1: Write failing selection and workspace tests**

Change the legacy-default owner to expect the typed explicit-effort reason for a
current model. Add the same owner for `none`, plus a retired-model owner that
cannot submit even with a syntactically valid effort.

In the browserless workspace render, assert provider/model changes requiring a
new effort display the disabled placeholder, do not persist a tuple, and keep
Submit disabled. Assert selecting `low` persists exactly `low`, survives a new
conversation, and is sent unchanged to `createResearchRun`. Assert no visible
`default`, `none`, or retired model option exists. Pin the default new AI
Research selection to `openai / gpt-5.6-luna / xhigh`.

Add line-owning controls for every current default path: absent selection must
not synthesize `default`; the supported-effort check cannot special-case
`default`; the option list cannot inject a synthetic default row; and provider
or model changes cannot persist `{ effort: "default" }`. A retired stored tuple
stays visible as blocked provenance but never appears as a new picker option.

Add the server-read compatibility owner: `getResearchSelection` may return a
nullable effort for a historical run, and the selection resolver retains that
thread provenance as `effort_required`. It must not discard the incomplete
thread tuple and fall through to the Settings route. Likewise, a completed run
whose DTO has null/blank effort must not be installed into state as `default`
(`Research.tsx` currently does this in the polling success branch).

Rebuild `researchSelection.test.ts` and `ResearchWorkspace.test.tsx` catalog
fixtures with the same six-current-model roster and ascending five-value effort
lists used by Task 4. In particular, Luna must include `xhigh`, and no fixture
may make a retired model the recommended/default route except in an explicitly
named legacy case.

- [x] **Step 2: Run the Research RED**

Run:

```bash
npm test -- --run src/researchSelection.test.ts src/ResearchWorkspace.test.tsx
```

Working directory: `apps/arkscope-web`.

Expected: the legacy default remains ready and provider changes still persist
`default`.

- [x] **Step 3: Implement Research selection behavior**

Remove the synthetic default option. A model/provider change with selectable
efforts enters `incompleteSelection`; choosing a real effort commits the sticky
tuple. Retired stored selections require a current replacement. Do not rewrite
historical message/run model or effort labels.

Separate raw compatibility reads from writable explicit preferences. A thread
selection may carry missing effort long enough to project `effort_required`, but
`writeExplicitResearchSelection` and `createResearchRun` accept only a complete
real tuple. Replace every `?? "default"`, `|| "default"`, default special-case,
and `{ effort: "default" }` in the Research selection paths with either the
actual stored effort or the explicit incomplete state.

When there is no stored or thread selection, initialize the current global
preference from `openai / gpt-5.6-luna / xhigh`. This initialization is a new
preference only; it does not rewrite a historical route or run.

- [x] **Step 4: Run the Research GREEN**

Run the same two-file Vitest command. Expected: pass.

- [x] **Step 5: Commit Task 5**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/researchSelection.ts apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/i18n/resources/en/research.ts apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts apps/arkscope-web/src/researchSelection.test.ts apps/arkscope-web/src/ResearchWorkspace.test.tsx
git commit -m "fix(research): persist only explicit effort"
```

### Task 6: Cross-Layer Verification and Closeout

**Files:**
- Modify: `docs/superpowers/specs/2026-08-27-explicit-effort-routing-design.md` only if verification exposes a factual correction.
- Modify: `docs/superpowers/plans/2026-08-27-explicit-effort-routing.md` checkbox statuses.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: a reviewable, unmerged branch with no provider or production authority crossed.

- [x] **Step 1: Run focused backend and frontend gates**

```bash
pytest tests/test_model_capabilities.py tests/test_model_routing.py tests/test_research_routes.py tests/test_research_runs.py tests/test_model_effective.py tests/test_ai_research_route.py tests/test_model_task_test.py tests/test_agents.py tests/test_model_tiers.py tests/test_card_synthesis.py tests/test_subagent.py tests/test_code_generator.py tests/test_compressor_layer5.py tests/test_investor_profile_calibration.py -q
cd apps/arkscope-web && npm test -- --run src/researchModels.test.ts src/modelRoutingUx.test.ts src/ModelRoutingSection.test.ts src/SettingsModelRouting.test.ts src/researchSelection.test.ts src/ResearchWorkspace.test.tsx
```

Expected: pass.

- [x] **Step 2: Run complete frontend gates**

```bash
cd apps/arkscope-web
npm test -- --run
npm run typecheck
npm run build
```

Expected: pass with no translated effort option IDs and no visible
`default`/`none` controls or retired model choices.

- [x] **Step 3: Run complete backend gate**

```bash
pytest -q
```

Expected: pass with only the repository's known skips/warnings.

- [x] **Step 4: Run static scope checks**

```bash
git diff --check
git status --short
rg -n 'default|none' apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/researchSelection.ts apps/arkscope-web/src/researchModels.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/modelRoutingUx.ts apps/arkscope-web/src/settings/ModelRoutingSection.tsx
rg -n 'return model, None|else "default"|effort.*(\|\||\?\?).*"default"|effort: "default"' src/agents/config.py src/research_runs.py src/api/routes src/card_synthesis.py apps/arkscope-web/src
rg -n 'claude-(opus-4-[578]|sonnet-4-[56]|haiku-4-5)|gpt-5\.(2(-codex)?|4(-mini|-nano)?|5)' src config/.env.template tests
rg -n "run_once\\(\"default\"\\)|fallback_effort[\"']?: [\"']default|else [\"']default[\"']" src/card_synthesis.py
```

Expected: clean diff. Review every `default`/`none` match; only provider
capability/history, route-source authority labels, and explicitly documented
low-level diagnostics may remain. No task save, test, hydration, selection, or
execution path may synthesize a default effort. Every old-model match is an
explicitly reviewed capability/history, low-level diagnostic, compatibility
fixture, or documentation example; no active runtime/task default or new-route
recommendation remains. Card task execution has no effort fallback to provider
default. Each grep was proven non-empty against the pre-change tree or is paired
with a named RED owner; a zero-match baseline is not accepted as a tripwire.

- [x] **Step 5: Commit plan/spec closeout if changed**

```bash
git add docs/superpowers/specs/2026-08-27-explicit-effort-routing-design.md docs/superpowers/plans/2026-08-27-explicit-effort-routing.md
git commit -m "docs: close explicit effort routing slice"
```

Do not merge or push. Report the exact branch tip, test counts, and remaining
legacy compatibility behavior for independent review.

Closeout note (2026-08-28, after test commit `7937c406`): all Task 1-6
checkboxes are complete. Focused backend: 505 passed. Focused frontend: 6
files, 121 tests passed. Full frontend: 106 files, 1,283 tests passed;
typecheck and build passed, with the existing Vite large-chunk warning. Full
backend: 4,593 passed, 12 skipped, 3 known `edgartools` deprecation warnings.
The three named same-provider recovery owners all pass: blocked legacy effort,
retired historical model, and active incomplete model/effort edit. With the
provider guard temporarily mutated to unconditional same-provider return, all
three owners failed; after restoring the shipped guard, all three passed again.
The explicit `gpt-5.4-mini` calibration owner asserts the supplied model is
preserved. Static inventories and `git diff --check` passed; remaining legacy
matches are capability/history, diagnostics, UI/source labels, documentation,
or explicit compatibility fixtures, and card task execution has no
default-effort fallback. After the docs commit, `git status --short` was empty;
ignored SDD reports do not appear in status.

#### Post-review contract amendment (2026-08-28)

An independent review correctly identified that provider effort fixtures did
not exercise the real wire shape: provider lists contain `default`/`none`, and
the Opus 5 model capability uses provider-native descending order. It
incorrectly classified a matching stored legacy Research route as a resolver
bug; the approved design intentionally preserves that route as incomplete so
admission can reject it without rewriting user authority. It also correctly
identified that the registered `/query` compatibility endpoints were missing
from this plan even though their fail-closed behavior is desirable.

The bounded follow-up is:

- [x] add `task_route_effort_order` to the backend catalog and consume it in the
  frontend, retaining the local closed tuple only for older sidecars;
- [x] make the frontend owner use real provider-list sentinels and Opus 5's
  provider-native descending capability order, with a separate owner for an old
  sidecar that omits the additive catalog-order field;
- [x] add a real `ModelRouteStore -> resolve_research_route ->
  create_research_run` owner proving retired/default rows reject before
  persistence and a corrected current/explicit row succeeds;
- [x] add exact sync and stream owners for an explicit current model with omitted
  effort, and formally admit `/query` plus `/query/stream` in the design;
- [x] distinguish current-shaped fixtures from deliberate history fixtures and
  remove stale model IDs only from the former.

The `default`/`none` type guard was already owned: temporarily adding those two
values to `TASK_ROUTE_EFFORT_IDS` produced two named failures in
`researchModels.test.ts`. The missing RED was catalog-order consumption; before
the implementation, its owner returned the local five-value order instead of
the catalog-supplied `high, low` probe.

Final follow-up verification: backend `4651 passed / 12 skipped` with the three
known edgartools deprecation warnings; frontend `106 files / 1300 passed`;
TypeScript typecheck and production build passed with the existing Vite large
chunk warning. Three contract mutations were killed by their named owners:
silently repairing a matching legacy route, accepting an explicit `/query`
model without effort, and ignoring catalog task-route order. The independent
review found no blocker and one P2 old-sidecar fallback gap; its added owner
failed when the compatibility fallback was removed and passed after restoration.
