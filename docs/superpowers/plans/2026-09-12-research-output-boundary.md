# Shared Research Output Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Track RED, GREEN, inverse checks and review per task.

**Goal:** Preserve research content while enforcing one execution-owned credential boundary across four transports and durable events.

**Architecture:** Separate diagnostic redaction from lossless research admission and stateful prose protection. Registered result policies select structural validation; ephemeral execution guards provide exact-secret enforcement before public or durable sinks.

**Tech Stack:** Python 3.10, contextvars, pytest, existing SDK adapters and SQLite test fixtures; no new dependency.

**Spec:** `docs/superpowers/specs/2026-09-12-research-output-boundary-design.md`

## Global Constraints

- Isolated worktree `/tmp/arkscope-research-output-boundary`; base `18d46062c30da87b30666b1ba0f290872a28fa7f`.
- No SEC feature wiring, SEC-specific exceptions, live providers/credentials/DBs, dependency installs, migrations, merge, push or restart.
- Keep diagnostic `_RULES`, route selection, retries, allowlists, timeouts, compressor budgets and SDK sessions intact.
- Manual edits use apply_patch; synthetic credentials only; run tests with this plan's closed-environment offline runner.
- Preserve raw source/citation identity. Never report a changed structured result as success.
- Four-channel equality means admitted business data, not SDK wrappers or unequal existing result-size budgets.

## Task 1: Ephemeral Guard And Stateful Stream Primitive

**Files:** Create `src/agents/shared/output_boundary.py`, `tests/test_output_boundary.py`.

**Interfaces produced:** `OutputBoundaryError(code)`, `OutputGuard(secrets=())`,
`guard.add_secret(secret)`, `guard.check(value)` (raises on known credential),
`guard.prose(text) -> str`, `guard.stream() -> SecretStream`,
`stream.feed(text) -> str`, `stream.finish() -> str`, `stream.abort() -> None`,
`output_scope(*secrets, inherit=False)` context manager,
`activate_output_guard(guard)` context manager, `current_output_guard()`,
`remember_output_secret(secret)`. Guards are nonserializable and redact repr.
The scope is independent from auth lookup and never reads tokens itself.

- [x] Write tests first for intact public data, exact matches, bounded raw/URL/base64 representations, repr/pickle safety and scope isolation.
- [x] Exhaust all split points and single-character feeds, including overlapping secrets and interleaved unrelated scopes:

```python
for split in range(1, len(secret)):
    stream = OutputGuard([secret]).stream()
    output = stream.feed(secret[:split]) + stream.feed(secret[split:]) + stream.finish()
    assert secret not in output
    assert output == "[REDACTED]"
```

- [x] Run `tests/test_output_boundary.py`; expected RED is a named missing-boundary assertion, then split leakage under an exact-only naive implementation. Record actual nodes and messages.
- [x] Implement bounded raw-offset matching and explicit finish/abort rules. No broad shape regex on prose; no arbitrary repr coercion.
- [x] Run GREEN plus inverse mutations: bypass a known match, emit pending suffix, share scopes. Record each owner turning red, restore and rerun.
- [x] Commit scoped files and independent task review.

Core commits `2f0cedeb`, `f2068c75`, `5f22762d`; final marker-fix check 83 primitive
tests passed. Independent re-review closes both findings and approves Task 1.
The earlier 112-test run included 38 unchanged controls; it is not combined with
the final 83 count. This is not a complete integration or release gate.

## Task 2: Registered Result Policies And Four Tool Adapters

**Files:** Create `src/tools/result_policy.py`, `tests/test_tool_output_policy.py`,
`tests/test_tool_output_channels.py`; modify `src/tools/registry.py`,
`src/agents/openai_agent/tools.py`, `src/agents/anthropic_agent/tools.py`,
`src/auth_drivers/chatgpt_oauth_driver.py`, `src/auth_drivers/claude_code_sdk_driver.py`.
Existing adapter fixture tests may need explicit policy declarations; enumerate
each changed expectation and its replacement owner, do not remove coverage.

**Consumes:** Task 1 `OutputGuard.check`, `output_scope`, `current_output_guard`.
**Produces:** trusted `ResultPolicy` and `ToolDefinition.result_policy`;
`admit_tool_result(result, *, policy, guard=None) -> str` returning canonical
lossless JSON or declared text, or `OutputBoundaryError` with closed codes;
`serialize_tool_result(result, *, tool_name) -> str` for API adapters. Registry
policies must not be selected by result content. Domain validator support has
no SEC import/branch. A source-only inventory decides existing public result
shapes and records every registered name plus bridge-only delegation.

Source inventory resolved all 54 definitions: 50 public JSON and four text
tools (`check_data_freshness`, `scan_alerts`, `get_economic_calendar`,
`get_macro_value`); bridge-only `delegate_to_subagent` returns public JSON.
Declare policies explicitly on each registration, leaving unknown policies
unadmitted. The four text functions are not JSON-string producers. Handle
native Pydantic/date/datetime/finite Decimal explicitly; arbitrary object
coercion and raw strings returned under JSON policy are errors. Set progressive
bounds at depth 64, 1,000,000 nodes and 32 MiB serialized output; preserve
existing smaller channel budgets. Closed validators must return literal True;
their exceptions or mutations cannot leak rejected values or bypass validation.

- [x] Inventory return annotations and actual serialization paths without invoking tools or DAL; settle JSON/text/model/datetime/Decimal handling before implementation.
- [x] Write RED tests invoking real four adapters with a registered synthetic public result containing long words, numeric TEXT, accession, URL, hash and cursor. After unwrapping channel envelopes:

```python
assert canonical(openai_data) == canonical(anthropic_data) == canonical(chatgpt_data) == canonical(claude_data)
assert json.loads(admitted)["value"] == "1234567890123456789.123"
```

- [x] Add invalid JSON/NaN/foreign object/cycle/depth/unknown policy/closed-validator-extra-field and secrets in values AND keys; expect typed failure and no rejected value or repr.
- [x] Watch RED, implement shared policy with admission before reducer/preview, retain diagnostic handling for exceptions. Normalize known native date/Decimal/Pydantic values explicitly, not `default=str`.
- [x] Run all adapter/registry/subagent positives and inverse checks for bypassed policy, known-secret and credential-field checks. Unknown registered policy must not silently fall through.
- [x] Commit and independent task review. SEC feature task remains parked and its four failed nodes are listed, not executed as this branch's tests.

Implementation commit `3e73d2aa` had 716 focused tests passing and six inverse
groups caught then restored. The original RED suite was 279 failed/9 passed.
Review found bare-Bearer financial prose rejection and lost safe span metadata.
Fix `41b9f2b5` narrows header context and restores content-free failure spans;
754 focused tests pass after three additional inverse checks were restored.
Independent re-review approves Task 2. Event/lifetime integration is not claimed.

## Task 3: Execution Lifetimes, Prose, Events And Durable Traces

**Files:** Modify `src/auth_drivers/runtime_binding.py`, both OAuth drivers,
`src/agents/openai_agent/agent.py`, `src/agents/anthropic_agent/agent.py`;
create `src/agents/shared/output_events.py`, `tests/test_research_output_events.py`,
`tests/test_research_output_lifetimes.py`. Modify managed/legacy route boundaries
and shared scratchpad/capture consumers only where necessary to protect actual
pre-persistence sinks. Enumerate additional exact paths in the ledger before editing.

The source inventory additionally owns `src/agents/shared/subagent.py`,
`src/research_run_manager.py`, `src/api/routes/query.py` and, only if required,
`src/auth_drivers/live_resolver.py`. Guard complete producer values before
scratchpad/replay/preview truncation. Activate the retained OutputGuard around
each upstream iterator advance/close and reset before public yields; do not
leave a ContextVar token installed in the consumer across generator yields.
Tool arguments must be admitted before handler execution, including write
tools, not repaired after they may have persisted a secret.
After Task 2 review, both native `tools.py` modules also belong to this task's
pre-handler input boundary. OpenAI SDK dispatch precedes run-item extraction,
so producer-side post-call trace checks cannot prevent tool writes or SDK
argument logging. No concurrent edits of those modules are permitted.
Confirmed existing-test collateral also includes the ChatGPT timeout owner in
`tests/test_chatgpt_oauth_driver.py` (safe-prefix/tail chunking, unchanged joined
answer and nontext event order) and retained-entrypoint owner in
`tests/test_openai_sync_surface_cleanup.py` (wrapped generator identity plus
the real iterator/lifetime owners). Preserve their behavioral guarantees;
do not retain representation-only assumptions incompatible with the new iterator.

**Consumes:** Task 1 scope/matcher and Task 2 result admission. Produces common
event protection prior to emission, with selected-client and refreshed-bearer
registration before any response is consumed. Helpers never recapture credentials.

- [x] Add real-adapter synthetic text/thinking/final-answer split tests and disposable managed-run replay tests; final-only redaction must fail the durable-event assertion.
- [x] Test parent/child, refresh, cancellation, completion and exception lifetime, direct API-key entry without ambient runtime binding, plus SDK trace/scratchpad guards.
- [x] Run RED; expected failures are damaged public prose, reconstructed fake secrets or unsafe durable event data, not provider/network/setup failures.
- [x] Wire common output scopes across async iteration and tool callbacks. Register captured client secrets/OAuth bearers, sanitize before public/durable yields, redact full values before preview truncation. Always close upstream on cancellation; no retry/session changes.
- [x] Verify existing owners including `test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors`, runtime binding, card execution authority, retry/tracing, OAuth cancellation/environment and session continuity.
- [x] Inverse: replace matcher by per-fragment replace; skip active client capture; move protection after durable append. Each has a named RED owner; restore GREEN.
- [x] Commit and independent task review.

RED preparation `task3-red-final-04`: 339 failed/22 passed, no errors/skips.
318 failures exercise existing behavior; 21 are named missing-wrapper assertions.
Existing-file integration is gated on Task 2 review because both tasks own the
OAuth files. The new shared event iterator may be implemented independently
against the already-approved core, without modifying any Task 2-owned file.

Implementation `29f18ca7` passed 1,022 focused tests. Independent review found
raw cleanup traceback logging and lost cleanup ownership when cancelled during
terminal close. Fix `fdc947d2` has 1,026 focused tests passing, three additional
inverse checks restored, and a scoped independent approval with six fresh
cleanup-outcome probes. The admitted SDK's task/cleanup compatibility was
inspected separately. Task 3 is complete; the full-backend/whole-branch gate is
still separate from these focused counts.

## Task 4: Frozen Verification And Integration Record

**Files:** This plan, matching evidence directory, security design and priority map;
tests only for findings discovered by final verification with a separate RED cycle.
**Consumes:** All preceding commits and task review records.

Confirmed residual scope: coordinator owns
`src/auth_drivers/codex_account_usage.py` and new
`tests/test_model_catalog_output_boundary.py`. Model IDs currently use the
diagnostic heuristic as a validator. Write RED public-ID and captured-secret
page/cursor owners, replace that use with lexical/JWT-domain validation plus the
shared local exact guard, retain the existing JWT rejection test unchanged, then
run inverse checks and subscription controls. This is separate from the immutable
Task 3 review and must finish before the final source freeze.

Runner correction: `backend-full-01` omitted the explicit `tests` path and
collected archived evidence test modules. It stopped with eight collection
errors before test execution. Retain this invocation failure; retry the complete
backend as `backend -q tests`, not as a product failure or baseline waiver.

Full-run collateral: `backend-full-02` reached 10,148 passed/12 skipped/1 failed.
The closed EIR-006 consumer census has no category for the new tool-policy test's
tool-name roster. Coordinator owns the exact `_TEST_FIXTURES` addition in
`tests/test_eir006_retired_data_boundaries.py`; preserve all search roots,
patterns and unknown-reference rejection. Watch the existing owner RED, add the
specific classification, rerun GREEN/inverse and then the complete backend.
This is missing test-manifest maintenance in this slice, not a pre-existing
failure or permission to exempt all tests.

Final-verification finding: the completed synthetic compaction probe showed a
raw credential echo in `compressor/summary_callers.py` diagnostics. Its probe
passes demonstrate the unsafe behavior, not a clean review. A second concrete
sink exists in `compressor/layers.py` (caller exceptions and summary installation).
Coordinator owns these two modules plus `tests/test_research_output_compaction.py`:
inherit the execution guard, capture the actual summary client's key before use,
sanitize errors in-scope, and reject credential-bearing summaries before any
cap or context replacement. No changes to model, prompts, retry, budgets or
failure/circuit semantics. Add RED/GREEN/inverse owners and unchanged compressor
controls. `backend-full-03` was stopped before editing (partial 8,068 passed,
12 skipped, exit 2); a fresh complete run is required. The fresh final reviewer
terminated with a platform safety error and no verdict; keep that independent
gate open for external review rather than treating the probe as approval.

- [ ] Freeze code identity; run all new tests and complete backend under the offline runner. Parse JUnit exact pass/skip/fail/error totals; no inferred aggregate counts.
- [x] Run repository census comparison and unbounded residual scans for generic redaction on successful research outputs. Classify diagnostic exceptions, not grep-count assertions.
- [ ] Dispatch whole-branch independent review with explicit base SHA, not `HEAD~1`; resolve findings with fresh tests and reverify changed surfaces.
- [ ] Archive commands, RED/GREEN/inverse results and source digests; mark task statuses incrementally.
- [ ] State independent security-slice status and parked SEC integration status separately. Do not merge or claim complete SEC delivery.
