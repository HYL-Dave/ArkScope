# Claude Fable 5.1 Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Fable 5.1 ArkScope's only current Fable model while preserving Fable 5 history, rejecting unverified OAuth execution, and adapting the two direct Anthropic structured-output requests safely.

**Architecture:** Keep model lifecycle and auth compatibility in the central capability registry, then enforce the resulting admission at picker, task-test, route, and provider boundaries. Isolate the Fable 5.1 request-shape change behind small helpers, and keep provider-side compaction separate from ArkScope client-side message rewriting.

**Tech Stack:** Python 3, FastAPI, Pydantic, Anthropic Python SDK, React/TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-fable-5-1-cutover.md`

## Global Constraints

- Use RED-first tests before every production-code change.
- Do not change built-in task defaults or reorder provider-native `_OPUS_EFFORTS`.
- Preserve raw historical `claude-fable-5` provider/model/effort values.
- Do not make a provider call until all offline gates pass.
- The only authorized live credential is the configured `TD_MRL` Anthropic API key.
- Do not merge or push.

---

### Task 1: Model Lifecycle And Auth Admission

**Files:**
- Modify: `tests/test_model_capabilities.py`
- Modify: `tests/test_model_effective.py`
- Modify: `tests/test_model_task_test.py`
- Modify: `tests/test_research_runs.py`
- Modify: `tests/test_research_routes.py`
- Modify: `tests/test_card_synthesis.py`
- Modify: `src/model_capabilities.py`
- Modify: `src/model_effective.py`
- Modify: `src/model_task_canary.py`
- Modify: `src/card_synthesis.py`
- Modify: `src/api/routes/query.py`
- Modify: `src/api/routes/research.py`

**Interfaces:**
- Produces: `model_auth_admission_detail(model: str, auth_mode: str | None) -> dict[str, str] | None`.
- Produces: Fable 5.1 as current/default/seed and Fable 5 as retired/pinned/history-only.
- Consumes: existing `task_route_admission_detail` for lifecycle and effort admission.

- [x] **Step 1: Write failing registry and picker tests**

```python
def test_fable_5_1_is_current_and_fable_5_is_history_only():
    current = capability_for("claude-fable-5-1")
    retired = capability_for("claude-fable-5")
    assert current.task_route_status == "current"
    assert current.in_routing_seed is True
    assert retired.task_route_status == "retired"
    assert retired.in_routing_seed is False

def test_fable_5_1_oauth_is_visible_but_not_eligible():
    entry = oauth_effective_entry("claude-fable-5-1")
    assert entry["eligible"] is False
    assert entry["reason_code"] == "model_auth_unverified"
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `pytest -q tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_task_test.py`

Expected: failures because Fable 5.1 and `model_auth_unverified` are absent.

- [x] **Step 3: Implement the registry and pure auth admission**

Add Fable 5.1 with the official model facts and `unverified_auth_modes=("claude_code_oauth",)`. Retire Fable 5 without deleting its capability record. Make `task_auth_executable`, effective picker entries, and the task-test dispatcher consume `model_auth_admission_detail`.

- [x] **Step 4: Write failing real-boundary tests**

```python
def test_research_create_rejects_unverified_fable_oauth_before_persistence(...):
    ...
    assert exc.value.detail == {"code": "model_auth_unverified", "field": "model"}
    assert persisted == []
    assert scheduled == []

def test_fable_oauth_card_task_never_calls_subscription_adapter(...):
    ...
    with pytest.raises(ValueError, match="model_auth_unverified"):
        _synthesize_anthropic(...)
```

- [x] **Step 5: Run the real-boundary tests and verify RED**

Run: `pytest -q tests/test_research_runs.py tests/test_research_routes.py tests/test_card_synthesis.py tests/test_model_task_test.py`

Expected: the current code dispatches OAuth Fable 5.1 or lacks the model.

- [x] **Step 6: Enforce auth admission before persistence and provider dispatch**

Apply the pure admission function in research-run creation, legacy query routes, the shared research stream dispatcher, card subscription dispatch, and task-model canary. Preserve an API-key positive control and existing OAuth models.

- [x] **Step 7: Run Task 1 focused tests**

Run: `pytest -q tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_task_test.py tests/test_research_runs.py tests/test_research_routes.py tests/test_card_synthesis.py`

Expected: PASS.

### Task 2: Fable 5.1 Structured Output And Compaction

**Files:**
- Modify: `tests/test_card_synthesis.py`
- Modify: `tests/test_model_capabilities.py`
- Modify: `tests/test_research_routes.py`
- Modify: `src/model_capabilities.py`
- Modify: `src/card_synthesis.py`
- Modify: `src/agents/anthropic_agent/agent.py`
- Modify: `src/api/routes/query.py`
- Modify: `src/api/routes/research.py`

**Interfaces:**
- Produces: model-specific Anthropic tool definitions and choices for direct API-key fixed tasks.
- Produces: `client_compaction_admission_detail(model: str, enabled: bool) -> dict[str, object] | None`.
- Consumes: the Fable 5.1 capability added in Task 1.

- [x] **Step 1: Write failing request-shape tests**

```python
@pytest.mark.parametrize("seam", ["synthesis", "translation"])
def test_fable_5_1_uses_auto_strict_tool(seam, ...):
    kwargs = invoke_and_capture(seam, model="claude-fable-5-1")
    assert kwargs["tool_choice"] == {"type": "auto"}
    assert kwargs["tools"][0]["strict"] is True

def test_other_anthropic_models_keep_forced_named_tool(...):
    assert kwargs["tool_choice"]["type"] == "tool"
    assert "strict" not in kwargs["tools"][0]
```

- [x] **Step 2: Run request-shape tests and verify RED**

Run: `pytest -q tests/test_card_synthesis.py -k 'fable_5_1 or forced_named_tool'`

Expected: Fable 5.1 still sends forced named-tool requests.

- [x] **Step 3: Implement minimal model-specific request helpers**

For Fable 5.1 only, add top-level `strict=True` and use `tool_choice={"type":"auto"}`. Keep the one-tool-only prompt and existing no-tool failure. Do not alter OpenAI or subscription-adapter payloads.

- [x] **Step 4: Write failing client-compaction admission tests**

```python
def test_fable_5_1_client_compaction_fails_before_client_creation(...):
    ...
    assert detail["code"] == "model_client_compaction_incompatible"
    assert provider_calls == []

def test_fable_5_1_without_client_compaction_is_allowed(): ...
def test_fable_5_client_compaction_guard_is_not_model_wide(): ...
```

- [x] **Step 5: Run compaction tests and verify RED**

Run: `pytest -q tests/test_model_capabilities.py tests/test_research_routes.py -k compaction`

Expected: no Fable 5.1 client-compaction guard exists.

- [x] **Step 6: Implement fail-closed client-compaction admission**

Add a capability flag that describes ArkScope client-side compaction separately from provider-side `supports_compaction`. Reject at HTTP/run creation and again inside the Anthropic agent before client construction. Include guidance to disable client compaction or select another model.

- [x] **Step 7: Run Task 2 focused tests**

Run: `pytest -q tests/test_card_synthesis.py tests/test_model_capabilities.py tests/test_research_routes.py tests/test_research_runs.py tests/test_compressor_integration.py`

Expected: PASS.

### Task 3: Historical Provenance And Content Translation Language

**Files:**
- Modify: `tests/test_research_runs.py`
- Modify: `apps/arkscope-web/src/ResearchWorkspace.test.tsx`
- Modify: `apps/arkscope-web/src/Dashboard.test.tsx`
- Modify: `apps/arkscope-web/src/Dashboard.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/system.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/system.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/common.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/common.ts`
- Modify: `apps/arkscope-web/src/modelRoutingUx.ts`
- Modify: `apps/arkscope-web/src/modelRoutingUx.test.ts`
- Modify: `docs/design/ARKSCOPE_TERMINOLOGY.md`

**Interfaces:**
- Consumes: `model_auth_unverified` from Task 1.
- Produces: exact historical Fable 5 round-trip/display owner and localized auth reason.

- [x] **Step 1: Write failing history, reason-copy, and terminology tests**

```python
def test_retired_fable_5_run_remains_readable():
    run = round_trip_run(model="claude-fable-5", effort="max")
    assert (run.model, run.effort) == ("claude-fable-5", "max")
```

```tsx
expect(historicalBubble.textContent).toContain("anthropic/claude-fable-5");
expect(historicalBubble.textContent).toContain("max");
expect(modelReasonLabel("model_auth_unverified", t)).toBe(localizedGuidance);
```

- [x] **Step 2: Run focused backend/frontend tests and verify RED**

Run: `pytest -q tests/test_research_runs.py -k fable`

Run: `npm test --workspace apps/arkscope-web -- ResearchWorkspace.test.tsx Dashboard.test.tsx modelRoutingUx.test.ts`

Expected: missing explicit owners and stale Dashboard wording.

- [x] **Step 3: Implement the minimal copy and display changes**

Keep `card_translation` and invisible search aliases unchanged. Change visible Dashboard copy to `Content translation` / `內容翻譯`, add localized OAuth-unverified guidance, and add the canonical terminology row. Do not transform historical model IDs.

- [x] **Step 4: Run Task 3 focused tests**

Run the two focused commands from Step 2.

Expected: PASS.

### Task 4: Inventory, Decision Record, And Offline Gates

**Files:**
- Modify: current-model fixtures found by `rg 'claude-fable-5' tests apps/arkscope-web/src`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: synchronized current/retired inventories and the durable product ruling.

- [x] **Step 1: Update every current-model fixture**

Replace Fable 5 with Fable 5.1 only where the fixture represents current routing. Retain explicit Fable 5 values in retirement, compatibility, provenance, and historical-display tests.

- [x] **Step 2: Add the decision-log entry**

Record the maintenance rationale, current/retired split, unchanged defaults, OAuth-not-live-verified status, and client-versus-provider compaction boundary. Mark API-key canary as pending until Task 5 succeeds.

- [x] **Step 3: Run inventory and formatting gates**

Run: `rg -n 'claude-fable-5' src tests apps/arkscope-web/src docs/design`

Run: `git diff --check`

Inspect every match and classify it as current 5.1, explicit retired 5, historical provenance, or source documentation.

- [x] **Step 4: Run complete offline gates**

Run: `pytest -q tests`

Repository-root collection also executes the sealed 2026-08-28 listing-authority
packet against today's kernel. At base `e67c8332`, its shadow runner fails because
it predates the required `execution_owner_id` argument added on 2026-08-30. Do not
rewrite that sealed packet or weaken the current owner contract in this slice;
classify the identical base/branch failure separately from the product test gate.

Run: `npm test --workspace apps/arkscope-web`

Run: `npm run typecheck --workspace apps/arkscope-web`

Run: `npm run build --workspace apps/arkscope-web`

Run the repository i18n/visible-literal scanner command owned by the frontend package.

Expected: all pass before any provider request.

### Task 5: Bounded API-Key Live Canary And Branch Closeout

**Files:**
- Modify after success: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: production `_synthesize_anthropic` and `_translate_anthropic` seams.
- Produces: a bounded live-verification result without retaining secrets or response content.

- [x] **Step 1: Resolve the exact credential without printing it**

Read `CredentialStore`, require exactly one Anthropic API-key credential whose operator label is `TD_MRL`, and keep its secret in memory only. Do not change the active credential.

- [x] **Step 2: Run one card-synthesis canary**

Invoke the production seam with `claude-fable-5-1`, `effort=low`, a minimal evidence packet, a bounded timeout, zero SDK retries, and no fallback. Record only success/failure, latency, and schema/tool validation.

- [x] **Step 3: Run one Content-translation canary**

Invoke the production seam with a minimal one-field schema under the same model, effort, timeout, retry, and retention constraints. Stop instead of switching credentials after an auth/quota/contract failure.

- [x] **Step 4: Update the decision record with the exact result**

On success, state that the API-key card synthesis and Content-translation seams were live-verified, with timestamp and bounded-call counts. Keep OAuth explicitly not live-verified. On failure, record the typed failure without claiming support.

- [x] **Step 5: Re-run secret and repository checks**

Run the repository secret scanner against the branch diff and inspect `git diff --stat`, `git diff --check`, and `git status --short`.

- [ ] **Step 6: Commit without merge or push**

Commit the reviewed cutover and report the branch commit, exact gate counts, canary result, OAuth boundary, and remaining separate Spark slice.

### Task 6: Post-Canary Execution-Boundary Review Repair

**Files:**
- Modify: `src/model_capabilities.py`
- Modify: `src/model_routing.py`
- Modify: `src/model_credentials.py`
- Modify: `src/api/routes/config_routes.py`
- Modify: `src/investor_profile_calibration.py`
- Modify: `src/investor_profile_calibration_agent.py`
- Modify: `src/api/routes/investor_profile_calibration.py`
- Modify: `src/agents/anthropic_agent/agent.py`
- Modify: `src/agents/shared/subagent.py`
- Modify: `src/agents/shared/compressor/summary_callers.py`
- Modify: `src/tools/code_generator.py`
- Modify: focused tests for each boundary

**Interfaces:**
- Produces: a product-wide history-only execution admission distinct from the
  narrower task-route status.
- Produces: generation-safe capability matching that retains reviewed snapshot
  suffixes without treating `5.2` or `5.10` as Fable 5 / 5.1.
- Consumes: the existing auth admission and typed `model_retired` response.

- [x] **Step 1: Add RED tests for bypassed execution seams**

Pin zero provider dispatch for generic model-test, calibration message/proposal/
retry, direct agent, subagent, code generation, and Layer-5 summary calls. For
calibration, also assert zero turn/message persistence before `model_retired` or
`model_auth_unverified` is returned.

- [x] **Step 2: Add RED tests for generation-safe matching**

Retain exact and reviewed dated snapshot matches. Assert `claude-fable-5-2` and
`claude-fable-5-10` remain unknown instead of inheriting Fable 5 or 5.1 facts.

- [x] **Step 3: Implement central history-only admission and consume it at every seam**

Keep older Advanced models independently usable where existing non-task tools
permit them; only entries explicitly marked history-only are blocked across all
new executions. Keep unknown custom IDs forward-compatible.

- [x] **Step 4: Add compaction and fixed-task positive controls**

Prove Fable 5.1 provider-side `context_management` still reaches the beta wire
when ArkScope client compaction is off. Prove both synthesis and Content
translation reject text-only/no-tool responses.

- [x] **Step 5: Re-run focused and complete offline gates**

Do not repeat the live canary: the reviewed exact Fable 5.1 fixed-task wire was
already exercised, and this repair must not change that exact request shape.
Repeat backend product tests, frontend tests, typecheck, build, i18n scan,
inventory, secret scan, and diff checks before Step 6 of Task 5.
