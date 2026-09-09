# Task 1 Report

Status: DONE

Worktree: `/tmp/arkscope-task-route-authority`

Branch: `codex/task-route-authority`

Starting HEAD: `8512d3aa4464c5f4e6aa115ef6c3ce2bab951472`

Commit subject: `fix(routing): bind task execution and reject silent substitution`

Commit SHA: `f788ef280c245baf0d8a5f55681564603f75dfb5`

## Scope And Changes

- All four task route reads raise `ModelRouteUnavailable("model_route_unavailable")` on a store error. Genuine row absence still resolves the documented defaults. No model, effort, auth eligibility, Spark entitlement, or Fable admission rules changed.
- Research captures auth before persistence, passes an in-memory binding into scheduling, checks its provider/mode/credential ID against the stored selection, and activates it throughout stream construction and iteration. Missing or mismatched bindings terminalize the run without dispatch or recapture. Failed handoffs remain terminal. The legacy `/query/stream` captures before its lazy response iteration. The synchronous `/query` route is unchanged.
- API keys are immutable in-memory snapshots. A same-row secret mutation, a new active row, or a subsequent environment-key change cannot replace a captured key. OAuth carries its original credential ID and token-store authority, so refresh of that same credential keeps working without consulting the replacement active row.
- Main and existing child OpenAI Agents SDK agents use `OpenAIResponsesModel(model=..., openai_client=...)`, not the global client. Intentional cross-provider children have their own explicit auth boundary; same-provider children inherit their parent's captured auth. Parent context and configured child model are preserved. Direct-SDK OAuth rejection remains actionable and does not construct an API client.
- Admitted custom Anthropic models forward their explicit effort through the real messages boundary. The Anthropic access probe has zero SDK retries and no default-effort retry. Invalid explicit probe efforts, including blank/whitespace values, are rejected rather than normalized. Existing OpenAI tiny-budget access-probe semantics and completed-generation validation remain intact.
- Tests use real Research stores, the real scheduler/native agents and real SDK serialization with synthetic HTTP transports, plus focused driver-boundary fakes for OAuth. Existing injected-stream executor fixtures now explicitly supply synthetic bindings. Two legacy expectations for Research DB-error fallback were updated.
- No card/frontend implementation, new tool capabilities, provider access, production stores, credentials, app restart, merge, or push. No subagents/reviewers were spawned. All backend commands used the requested offline wrapper. The controller-owned plan clarification and hand-test document were left unstaged. This ignored SDD report is a local handoff artifact, not staged with implementation.

## Exact Helper Interface For Task 2

Module: `src.auth_drivers.runtime_binding`

```python
capture_runtime_auth(provider: str, *, store=None, token_store=None) -> RuntimeAuthBinding
activate_runtime_auth(binding: RuntimeAuthBinding)  # synchronous context manager, usable around awaits
current_runtime_auth(provider: str) -> RuntimeAuthBinding | None
capture_child_runtime_auth(provider: str, *, store=None, token_store=None) -> RuntimeAuthBinding
```

`RuntimeAuthBinding` is a frozen dataclass with safe public identity fields:

- `provider`: `openai` or `anthropic`.
- `source`: `db_api_key`, `oauth_driver_unwired`, or `env_fallback`, retaining existing resolver vocabulary. The OAuth source label describes the direct-SDK classifier, not subscription-driver availability.
- `auth_mode`: `api_key`, `chatgpt_oauth`, or `claude_code_oauth`.
- `credential_id`: original `local:<id>`, or `None` for genuine env fallback.
- `token_store`: captured controlled OAuth store reference, excluded from repr/comparison. It is not safe execution metadata and must not be serialized.
- Private `_api_key`: immutable captured string, excluded from repr. Never extract or serialize it.

Binding consumers:

```python
binding.api_client(*, asynchronous: bool = False)
binding.credential()  # detached OAuth-only driver metadata; no secret or DB reread
```

`api_client()` constructs an explicitly keyed sync/async SDK client and rejects OAuth or missing keys. `credential()` returns an object with `id`, `provider`, `auth_type`, and `secret=None`; calling it for API-key auth raises `runtime_auth_mode_unsupported`, avoiding a driver that could re-resolve a mutable DB row. OAuth callers should pass `binding.credential_id` and `binding.token_store` to the existing subscription structured-output helper, preserving its controlled refresh authority. No token values are captured or refreshed by `capture_runtime_auth` itself.

Lifecycle:

1. Admit and capture the selected route tuple once, then call `capture_runtime_auth` before persistence/scheduling. The helper reads one active-row snapshot. Selected unusable credentials or store errors fail closed with a bounded exception; they do not become env fallback.
2. Persist only explicit safe execution metadata, never the binding, its token store, `dataclasses.asdict(binding)`, or raw secrets. Repr omits sensitive fields and pickle serialization is rejected. Research retains its existing null auth metadata convention for the env/no-active-credential case; historical missing values are not inferred from Settings.
3. Carry the binding in memory and use `with activate_runtime_auth(binding):` around both dispatch and the full async stream iteration. Existing `resolve_live_auth`, `live_openai_client`, `live_openai_async_client`, and `live_anthropic_client` honor it. Activation restores the previous context on success, exception, or cancellation, including nested child calls.
4. Release references when execution ends. A restarted/interrupted queued run without its original binding must fail, not call capture again. A separately requested retry is a new execution and can capture a new selection.
5. Only deliberate child delegation calls `capture_child_runtime_auth`. Same-provider children inherit the parent; other-provider children capture independently, then must activate the returned binding. `current_runtime_auth` and ordinary capture still reject a provider mismatch. Do not use the child helper as a generic fallback after task failure.

`RuntimeAuthUnavailable` is a `ValueError` with fixed bounded messages: `runtime_auth_unavailable`, `runtime_auth_binding_missing`, `runtime_auth_binding_mismatch`, or `runtime_auth_mode_unsupported`. Research's existing classifier stores these executor exceptions as `provider_call_failed`; no new frontend error-code vocabulary was introduced. The legacy process-global `apply_openai_live_client` remains for compatibility tests but has no production callers after this repair; Task 2 must use the binding-aware clients instead.

## RED/GREEN Evidence

Every command below ran from the worktree. Every wrapper execution reported loopback-only networking, `external_probe: ENETUNREACH`, and `inherited_credentials: false`. No raw pytest commands were used.

### Baseline

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_model_routing.py tests/test_ai_research_route.py tests/test_live_resolver.py tests/test_research_runs.py tests/test_research_routes.py tests/test_agents.py tests/test_agent_history.py tests/test_replay.py tests/test_replay_openai.py tests/test_model_credentials_characterization.py tests/test_model_task_test.py tests/test_openai_responses_convergence.py tests/test_subscription_structured_output.py
```

Result: **509 passed in 18.31s**, exit 0.

### Initial Behavioral RED

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py tests/test_model_routing.py -k 'runtime or read_failure' --tb=short
```

Corrected-fixture RED: **16 failed, 14 passed, 84 deselected in 7.21s**, exit 1, before production edits. The initial two fixture-development runs had an incorrectly typed local credential ID, a wrong OAuth fixture argument, and an Anthropic transport mismatch (`httpx2` is required by the installed SDK); these were corrected and rerun, not counted as behavioral evidence.

Observed behavioral failures:

- Research persistence/schedule/dispatch switches sent the replacement key.
- Concurrent OpenAI agents both used the second client's key.
- Missing queued binding still reached the stream factory; legacy lazy streaming captured the replacement key.
- Both OAuth paths used the replacement credential ID/token instead of the originally selected ID and its refreshed token.
- Custom Anthropic effort was missing from the messages payload.
- Anthropic effort rejection generated 2 requests for HTTP 400 and 4 for HTTP 429/500, including the default-effort substitution.
- Invalid explicit probe effort was normalized rather than rejected.
- Three older tasks fell back on route-read errors. Lifecycle already rejected the error; all four genuine absent-route controls passed.

First GREEN, same command: **30 passed, 84 deselected in 4.02s**, exit 0.

### Child Consumer RED/GREEN

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k 'delegation' --tb=short
```

RED after the controller's explicit scope addition: **3 failed, 1 passed, 23 deselected in 2.56s**. OpenAI children had no explicitly keyed client, and the cross-provider Anthropic child hit the parent's mismatch guard. The same-provider Anthropic positive control passed.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py tests/test_research_runs.py tests/test_subagent.py --tb=short
```

GREEN: **125 passed in 8.34s**, exit 0. This also verified the limited injected-stream fixture updates. Before those updates, the broader baseline set plus the new file produced **11 failed, 519 passed in 19.09s**; all 11 were direct executor fixtures missing the newly required binding, not provider regressions.

### Self-Review RED/GREEN

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py --tb=short
```

RED: **5 failed, 33 passed in 4.65s**. Blank/whitespace probe efforts still normalized, the binding's driver-metadata method could expose API-key input for re-resolution, and bound direct OAuth clients lost the existing actionable rejection type. These were corrected before final verification.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k 'unbound_openai or captures_key' --tb=short
```

RED: **1 failed, 6 passed, 35 deselected in 3.57s**. The unbound per-agent constructor re-read an environment key after capture. The six passing Research cases cover both providers with concurrent route/credential changes at persistence, scheduling, and dispatch. The redundant env reread was removed.

A broader pre-final run of the final command below without `tests/test_openai_transport.py` and before these final added cases produced **1 failed, 780 passed in 22.86s**. The sole failure was an obsolete Lifecycle test expectation that Research still fell back on route-read failure; it was updated to the approved all-task fail-closed contract.

### Final Focused GREEN

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_model_routing.py tests/test_ai_research_route.py tests/test_live_resolver.py tests/test_research_runs.py tests/test_research_routes.py tests/test_agents.py tests/test_agent_history.py tests/test_replay.py tests/test_replay_openai.py tests/test_replay_fixtures.py tests/test_subagent.py tests/test_model_credentials_characterization.py tests/test_model_task_test.py tests/test_openai_responses_convergence.py tests/test_subscription_structured_output.py tests/test_research_runtime_config.py tests/test_model_capabilities.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_lifecycle_investigation_routing.py tests/test_task_runtime_binding.py tests/test_openai_transport.py --tb=short
```

Result: **789 passed in 22.63s**, exit 0, no warnings reported. `git diff --check -- src tests` also exited 0 with no output. The full repository backend suite and UI integration remain controller-owned and were not run.

## Self-Review And Mutation Owners

No known Task 1 blocker remains. Review was performed locally without spawning reviewers. Representative realistic mutations and their owning tests:

| Mutation | Behavioral owner |
| --- | --- |
| Return absent/default on a store exception | `test_task_route_read_failure_never_substitutes_yaml` (four tasks) |
| Capture at schedule/dispatch, use current row/key, or re-resolve the saved route | `test_research_captures_key_before_persistence_and_scheduling` (six native-wire cases) |
| Reuse SDK global instead of the per-agent client | `test_concurrent_openai_agents_never_exchange_clients` |
| Dispatch/re-capture without a queued binding | `test_queued_run_missing_binding_cannot_capture_replacement`, `test_failed_queued_handoff_cannot_be_rescheduled_with_current_settings` |
| Resolve OAuth active row again or freeze away its legitimate refresh authority | `test_research_oauth_switch_keeps_original_id_and_refresh_authority` (both OAuth modes) |
| Strip custom Anthropic effort | `test_anthropic_custom_and_supported_effort_reaches_messages_wire` |
| Retry default effort or leave Anthropic SDK retries enabled | `test_anthropic_probe_rejection_is_one_request_no_substituted_success` (400/429/500) |
| Normalize invalid explicit test effort | `test_model_probe_invalid_explicit_effort_cannot_normalize` |
| Re-read env after capture | `test_genuine_env_fallback_is_snapshotted_not_reselected`, `test_unbound_openai_constructor_does_not_reread_captured_env` |
| Lose parent auth, change child model, or bypass strict mismatch with ambient fallback | `test_delegation_has_explicit_child_auth_and_preserves_parent` (four provider combinations) |
| Send a direct API call for a selected OAuth child | `test_delegated_oauth_cannot_fall_back_to_api` |

These are RED-proven and/or literal positive-control owners, not a claim that a separate mutation-testing harness was executed. No harness migration was introduced.

Integration cautions: activation must include asynchronous iteration, not only generator creation; bindings must stay out of SQLite/JSON/normal execution payloads; Task 2 must explicitly forward the captured OAuth ID and token store to its subscription helper. OAuth token lifecycle is intentionally still owned by that store for the original ID. No live-provider acceptance is claimed.

## Fix Round 1

Base: `f788ef280c245baf0d8a5f55681564603f75dfb5`. Fix commit: `67c4fcffd51bd41b4b391d1ff8d5b5cbd1e0172b` (`fix(auth): pin selected runtime requests and redact failures`). Status: **DONE_WITH_CONCERNS**, for the SDK tracing scope question below.

Read the final `task-1-review.md` Findings 1-2 in full, including the exact SDK-header doctest and its recorded RED result. Checked the installed sync/async OpenAI and Anthropic constructor/header implementations. Followed the receiving-code-review, TDD, systematic-debugging, and verification-before-completion skills locally; no subagents or reviewers were spawned.

### Changes

- Fixed Finding 1 at SDK construction, not merely `client.api_key`: bound sync/async clients and the selected model access probe share `api_key_client_options`. OpenAI requests have one explicitly pinned Authorization header, with all ambient Authorization spellings excluded by the SDK. Anthropic requests have the selected X-Api-Key and omit ambient bearer auth. Overrides also cover case variants of the unused API-key header channel. Unrelated custom headers remain intact.
- Pinned API-key destinations to `https://api.openai.com/v1` and `https://api.anthropic.com`. Late `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` changes cannot redirect the captured key. No model, effort, auth-mode, provider, eligibility, retry, or subscription-policy fallback was added.
- Fixed Finding 2 with exact selected-key redaction before generic token redaction and before the 500-character output bound. Constructor failures, model-test API responses, native main/child diagnostics, scratchpad errors/retries, legacy SSE, and Research error persistence now use safe details. Managed failures and child failures explicitly retain their own binding after activation unwinds.
- Removed raw exception tracebacks from the affected native diagnostic paths. Nonstream OpenAI entrypoints raise a bounded RuntimeError with a safe type-prefixed message and suppressed original context, instead of handing the raw SDK exception to the route. Retry decisions still inspect the original error privately; retry diagnostics are sanitized. Native calls without a Research context use the already-created client key, never a replacement Settings lookup.
- Self-review also closed the Task 1 scheduling and failed-handoff-persistence traceback sinks using their captured binding. The public 503 response and failed-handoff behavior are unchanged.
- Added 38 behavioral cases in `tests/test_task_runtime_binding.py` (80 total in that file). The new transport fixture uses the installed SDKs with `httpx2.MockTransport`; existing fixtures and the repository harness were not migrated. No frontend, card, controller document, production data/config, or SDK installation edits.

### RED Evidence

All commands below ran from `/tmp/arkscope-task-route-authority`. Every backend invocation used the offline wrapper and reported `interfaces: [lo]`, `external_probe: ENETUNREACH`, and `inherited_credentials: false`. All credentials and responses were synthetic; all stores were test-local.

Initial test-authoring check, before production edits:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k 'bound_wire or key_echo or runtime_error_redacts' --tb=short
```

Result: **22 failed, 42 deselected in 4.28s**, exit 1. Nineteen reached the expected contract failures; three were test-authoring errors (Anthropic's async generator was iterated synchronously; two managed cases treated the ResearchRun dataclass as a Pydantic model). Corrected those test-only mistakes and completed the native unbound, constructor-error, and retry owners before writing production code.

Corrected, complete RED:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k 'bound_wire or key_echo or runtime_error_redacts' --tb=no
```

Result: **36 failed, 42 deselected in 4.11s**, exit 1. The six SDK-wire consumers used the late alternate host/auth headers. Probe, constructor, native, child, legacy, and managed failures exposed the synthetic selected key; the boundary-length case retained a key prefix because truncation happened without exact-key redaction. The retry owners still executed exactly two attempts while exposing the key in diagnostics.

Behavioral owners and realistic mutations:

| Owner | Cases | Failure caught |
| --- | --- | --- |
| `test_bound_wire_ignores_late_auth_headers_and_host` | 6 | Omit pinned header/host options in either provider's sync, async, or model-test construction; actual wire tuple, one request, model, and unrelated header are asserted |
| `test_model_probe_key_echo_is_redacted_before_api_serialization` | 2 | Serialize raw selected-key provider errors or remove the output bound |
| `test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors` | 10 | Raw errors in OpenAI async/sync/stream or Anthropic stream/wrapper, with and without a Research context |
| `test_child_key_echo_is_redacted_after_parent_context_restoration` | 4 | Sanitize with a replacement or restored parent credential instead of the child's original binding |
| `test_research_key_echo_redacted_before_sse_and_persistence` | 4 | Raw legacy SSE/SQLite data, or loss of captured-key redaction after managed activation exits; timeout classification remains asserted |
| `test_runtime_error_redacts_exact_key_before_length_bound` | 1 | Truncate before redacting, leaking a partial selected key |
| `test_client_construction_key_echo_is_private` | 6 | Leak selected-key constructor errors from sync/async bindings or probes |
| `test_openai_retry_key_echo_is_private_without_changing_retry_policy` | 3 | Raw retry logs/scratchpad, or change the two-attempt retry rule |
| `test_schedule_key_echo_never_logs_raw_exception_context` | 2 | Raw traceback on scheduling or failed-handoff persistence failure |

These are RED-first mutation owners, not a claim of running a separate mutation-testing harness.

### GREEN And Self-Review

First implementation verification:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py --tb=short
```

Result: **10 failed, 68 passed in 6.27s**, exit 1. Wire assertions caught duplicate selected OpenAI Authorization headers, caused by adding noncanonical header spellings alongside the SDK's generated canonical header. Corrected the options to emit only canonical OpenAI Authorization; the SDK already strips every ambient spelling. Rerunning the exact command gave **78 passed in 5.97s**, exit 0.

The first focused regression invocation (the full final command below, before the two additional scheduling tests) gave **825 passed in 24.52s**, exit 0.

Self-review scheduling RED:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k schedule_key_echo --tb=no
```

Result: **2 failed, 78 deselected in 1.80s**, exit 1. Both failed because `logger.exception` included the raw selected-key exception/context. Applied the captured-binding sanitizer before those log calls and removed traceback emission. Both cases are included in the final GREEN below.

Reviewer SDK-header evidence rerun, without editing the review document:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q --noconftest --assert=plain -p no:cacheprovider --doctest-glob=task-1-review.md .superpowers/sdd/2026-09-09-task-route-authority-repair/task-1-review.md --tb=short
```

Result: **1 passed in 0.99s**, exit 0. The unchanged expected tuple `(1, True, True, False)` now holds: one mock request, selected client key, selected wire key, no alternate wire key. This resolves the review's recorded `(1, True, False, True)` RED.

Final focused regression:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_model_routing.py tests/test_ai_research_route.py tests/test_live_resolver.py tests/test_research_runs.py tests/test_research_routes.py tests/test_agents.py tests/test_agent_history.py tests/test_replay.py tests/test_replay_openai.py tests/test_replay_fixtures.py tests/test_subagent.py tests/test_model_credentials_characterization.py tests/test_model_task_test.py tests/test_openai_responses_convergence.py tests/test_subscription_structured_output.py tests/test_research_runtime_config.py tests/test_model_capabilities.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_lifecycle_investigation_routing.py tests/test_task_runtime_binding.py tests/test_openai_transport.py --tb=short
```

Result: **827 passed in 27.34s**, exit 0, no warnings reported. Includes the existing exact-route/credential-switch, absent-route, concurrent-client, supported/custom-effort, OAuth refresh/rejection, model-task probe, Research classification/routes/runs, native/replay, and same/cross-provider child controls. `git diff --check -- src tests` exited 0 with no output. The full repository backend and UI suites remain controller-owned and were not run.

### Helper Contract For Task 2

The capture/activation/child interfaces from the original report are unchanged. The binding is still immutable, in-memory only, repr-safe for its API key, and non-pickleable. Its OAuth ID and token store still allow refresh of that same credential only.

New exports in `src.auth_drivers.runtime_binding`:

```python
api_key_client_options(provider: str, api_key: str) -> dict[str, Any]
sanitize_runtime_error(
    value: Any, *,
    binding: RuntimeAuthBinding | None = None,
    api_key: str | None = None,
) -> str
```

- Prefer `binding.api_client(asynchronous=False)` (or `True`) for runtime SDK clients. It applies the options and sanitizes constructor failures as bounded `RuntimeAuthUnavailable`, suppressing raw context. The options helper exists for the model-test constructor's timeout/retry options; its returned dictionary contains the selected secret and must remain ephemeral, never logged or serialized.
- `sanitize_runtime_error(exc)` uses the active binding. When catching outside `with activate_runtime_auth(binding)`, pass `binding=binding` explicitly, especially after a child has restored its parent's context. No store, env key, token store, or replacement credential is read by this sanitizer.
- Direct probes or already-built native clients may supply `api_key=selected_key` for exact redaction without a Research context. Exact replacement happens before existing generic redaction and the 500-character output bound. Log/serialize only the returned detail, never the original exception/traceback afterward.
- `sanitize_research_detail` and `classify_research_failure` also accept optional keyword-only `binding`; classification still uses the original reviewed type/shape before sanitizing detail. Main provider mismatch remains strict; intentional cross-provider child capture remains explicit.
- Task 2 continues to pass the original OAuth `credential_id` and controlled `token_store` into `subscription_structured_output`; no card or subscription implementation was changed in this round.

### Concerns And Scope

- No blocker remains for the two named review findings at the repaired application boundaries. Standard API-key hosts are deliberately pinned as requested; gateway/alternate-host support is not inferred or added.
- For native OpenAI calls without an active Research context, exact-key sanitization reads the already-bound `OpenAIResponsesModel._client.api_key`. This SDK-private attribute is exercised by the installed-SDK tests; no credential is recaptured. An SDK migration must preserve that local relationship or provide an equivalent explicit selected-key path.
- A scope question was sent to the controller: Agents SDK sensitive-data trace spans can record a provider exception before ArkScope's catch. This round does not change third-party logging/tracing policy, consistent with the instruction against policy changes. The offline native tests disable tracing and exercise the SDK's default redacted model logging. Opt-in SDK diagnostics/trace export and unrelated repository logging are not certified by this fix.
- No provider/prod access, production credential/config edits, main-branch changes, merge/push, App restart, frontend work, or harness migration occurred. Controller changes to the repair plan, hand-test document, and priority map remain untouched and unstaged. This report stays local in the ignored SDD directory; only scoped code/tests are committed.
- Post-commit `git status --short` shows only those three controller-owned documents. The commit contains exactly nine scoped source files and `tests/test_task_runtime_binding.py`; `git diff --cached --check` was clean before committing. All test sessions completed before handoff.

## Fix Round 1: Tracing Completion

Base for this separate commit: `67c4fcffd51bd41b4b391d1ff8d5b5cbd1e0172b`. Commit: `af3f06c4ea6c44779d61d5a0800f4db8c747f348` (`fix(agents): omit sensitive native trace payloads`). Status: **DONE**, with the installed-SDK metadata limitation documented below. Re-review should include both fix commits after `f788ef280c245baf0d8a5f55681564603f75dfb5`.

### Ruling And Correction

The controller resolved the prior tracing question: explicitly use `RunConfig(trace_include_sensitive_data=False)` in the directly affected native OpenAI main async/sync/stream and child executions, retaining ordinary traces and ArkScope diagnostics. No global trace-export policy change or SDK patch.

Correction to the preceding concern: SDK sensitive-data tracing is **default-enabled**, not merely opt-in. The installed `agents/run_config.py:52-55` returns true when `OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA` is absent. `agents/models/openai_responses.py:610-619` records `str(exception)` in response-span error data before ArkScope's handlers. The previous 827-case run disabled tracing in its native fixtures, so it did not prove this boundary safe.

### Scoped Implementation

- `src/agents/openai_agent/agent.py`: all three native entrypoints pass an explicit `RunConfig(trace_include_sensitive_data=False)` through their existing Runner kwargs. The setting also remains in effect for their existing retries.
- `src/agents/shared/subagent.py`: the existing `_run_openai_subagent` Runner call passes the same explicit setting, including same-provider and deliberate cross-provider delegation.
- No global tracing disable, exporter configuration, SDK installation, model/credential selection, route/admission, token refresh, error classifier, or ArkScope diagnostic behavior was changed. No new runtime binding interface was needed; Task 2's documented helper contract is unchanged.

### Enabled-Tracing RED/GREEN Owner

Named owner: `test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata` in `tests/test_task_runtime_binding.py`. Ten parameterized cases cover key-echo failures and successful results for main async, main sync, main stream, same-provider OpenAI child, and Anthropic-parent/OpenAI-child dispatch.

The fixture deliberately enables tracing in a real SDK `DefaultTraceProvider` with an in-memory `TracingProcessor`, then restores the previous provider. It removes the sensitive-data environment flag to exercise the real default, not a test-only privacy override. It snapshots span data in `on_span_end`, before the application's outer exception handlers can sanitize their diagnostics. In addition to the SDK span export it inspects `ResponseSpanData.input` and `.response`: those raw fields are not included in `ResponseSpanData.export()`, so checking exports alone would miss a payload leak.

Only the HTTP boundary is mocked, using the existing real-SDK `httpx2.MockTransport` fixture and synthetic keys/responses. The default backend exporter is guarded with a network-free recorder, and every case asserts zero export attempts. No default/exporter or provider traffic occurred. No tracing harness or global test fixture migration was introduced.

Command, run before any production change:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py -k enabled_sdk_tracing --tb=short
```

RED: **10 failed, 80 deselected in 3.59s**, exit 1. Five failure cases contained the synthetic selected key in the processor's span-error snapshots. Five success cases retained raw prompt/response payloads. Trace names, IDs, grouping, timestamps, and agent metadata were already present; no fixture errors or default-export attempts occurred.

After adding the four explicit per-run settings, the exact same command produced GREEN: **10 passed, 80 deselected in 2.97s**, exit 0, no warnings reported.

The owner asserts:

- One actual mock SDK request under the selected key and configured main/child model; no replacement credential or fallback call.
- A real trace with preserved workflow name, group ID, metadata and trace ID; real agent/response spans with parent linkage and start/end timestamps. Disabling tracing entirely would fail these assertions.
- No selected key in any captured trace/span error or data, and no raw response/input object available to the response-span processor.
- On failure, the response span still carries the SDK's error marker with `Error details are redacted.`, while the previously fixed ArkScope public/log/scratchpad diagnostics remain safely redacted.
- On success, the answer remains `OK`, provider/model remain exact, and both the application result and response-span usage retain the synthetic 2-input/1-output/3-total token counts.

Removing the explicit setting at any of the four Runner sites is a RED-proven mutation owner. Same-provider and cross-provider child cases also verify parent auth-context restoration. No separate mutation harness was run.

### Focused Regression

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_model_routing.py tests/test_ai_research_route.py tests/test_live_resolver.py tests/test_research_runs.py tests/test_research_routes.py tests/test_agents.py tests/test_agent_history.py tests/test_replay.py tests/test_replay_openai.py tests/test_replay_fixtures.py tests/test_subagent.py tests/test_model_credentials_characterization.py tests/test_model_task_test.py tests/test_openai_responses_convergence.py tests/test_subscription_structured_output.py tests/test_research_runtime_config.py tests/test_model_capabilities.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_lifecycle_investigation_routing.py tests/test_task_runtime_binding.py tests/test_openai_transport.py --tb=short
```

Result: **837 passed in 25.06s**, exit 0, no warnings reported. This is the previous 827-case focused set plus ten enabled-tracing cases (90 total in `test_task_runtime_binding.py`). Native, replay, subagent, Research, model-task probe, auth-binding and subscription regressions remain green.

Unchanged reviewer SDK-header evidence:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q --noconftest --assert=plain -p no:cacheprovider --doctest-glob=task-1-review.md .superpowers/sdd/2026-09-09-task-route-authority-repair/task-1-review.md --tb=short
```

Result: **1 passed in 0.95s**, exit 0. `git diff --check -- src tests` also exited 0 without output. All test invocations ran from the isolated worktree via the offline wrapper and reported only loopback, external-route `ENETUNREACH`, and no inherited credentials. The controller-owned full repository/backend and UI runs were not executed.

### Self-Review And SDK Limitation

The production diff is limited to importing RunConfig and providing its explicit sensitive-data setting at four existing Runner sites in two source files. The test adds a locally enabled tracing fixture and one parameterized behavioral owner; controller docs, frontend/cards and unrelated logging are untouched. The disclosed default-enabled SDK error-span leak is closed at the required main/child boundaries, before application catches.

The installed SDK does not independently retain a provider response ID when sensitive response data is omitted: `ResponseSpanData.export()` derives `response_id` from `.response.id`, so that field becomes null along with the suppressed raw response object. Ordinary trace/span IDs, grouping, timing, agent identity, error status and token usage remain, as the enabled-tracing tests demonstrate. This is a documented SDK limitation, not an unresolved proposal to patch the SDK or retain raw payloads. No broader audit or logging/export policy change was made.

Commit verification: staged names were exactly the two source files above and `tests/test_task_runtime_binding.py`; `git diff --cached --check` exited 0 without output. After commit, `git status --short` lists only the controller-owned repair plan, hand-test document and priority map, all unstaged. The local ignored report is not part of the implementation commit. All test sessions completed before handoff.
