**Important 1: Bind or reject ambient authorization overrides before SDK construction.** - **ADDRESSED**, with current-code evidence at `src/auth_drivers/runtime_binding.py:20`, `src/auth_drivers/runtime_binding.py:85`, `src/model_credentials.py:1249`, and `src/model_credentials.py:1274`.

Original finding (verbatim):

> 1. **P1: Bind or reject ambient authorization overrides before SDK construction.** `src/auth_drivers/runtime_binding.py:52` passes only `api_key` to the SDK after capture. The installed OpenAI SDK subsequently reads `OPENAI_CUSTOM_HEADERS`; an `Authorization` entry overrides the generated header, even while `client.api_key` still equals the captured key. A header introduced between capture and dispatch can therefore send the request under another credential while Research records the original credential ID. Pin the effective authorization header, or fail closed on an incompatible ambient override, and cover this at the actual request boundary. SDK evidence: `openai/_client.py:312`, `openai/_client.py:637`, and `openai/_base_client.py:475` in the review virtualenv. The async constructor has the same ambient-header behavior at `openai/_client.py:1060`.

Verification:

- `src/auth_drivers/runtime_binding.py:25` supplies both the captured API key and canonical `Authorization: Bearer <captured key>`. The installed OpenAI SDK's constructors at `openai/_client.py:319` and `openai/_client.py:1067` remove every ambient Authorization spelling when that explicit header is present. Its request builder at `openai/_base_client.py:475` then gives the explicit client header precedence over generated authentication. This closes the original source-to-wire override, not merely the misleading `client.api_key` check.
- `src/auth_drivers/runtime_binding.py:31` pins Anthropic's X-Api-Key and omits bearer Authorization; `src/auth_drivers/runtime_binding.py:38` also overrides ambient case variants of the authentication channels. The installed Anthropic constructors merge explicit options after ambient headers, and `anthropic/_base_client.py:467` / `anthropic/_base_client.py:2480` build headers case-insensitively. Unrelated headers remain available.
- The controller-approved standard destinations are explicit at `src/auth_drivers/runtime_binding.py:25` and `src/auth_drivers/runtime_binding.py:30`. Both SDKs consult their ambient base URL only when no explicit URL is supplied. Sync/async runtime construction and both selected model probes consume these same options, so late ambient host changes cannot redirect these calls.
- `tests/test_task_runtime_binding.py:650`, `test_bound_wire_ignores_late_auth_headers_and_host`, covers both providers across sync, async, and model-probe consumers. It changes ambient host/auth headers after capture and checks one actual MockTransport request, selected wire authentication, standard host, unchanged model, and the retained unrelated header. The original review doctest remains the same contract; its reported GREEN is noted below, not independently rerun.

**Important 2: Sanitize selected-execution failures before any diagnostic or public sink.** - **ADDRESSED**, with current-code evidence at `src/auth_drivers/runtime_binding.py:93`, `src/model_credentials.py:1292`, `src/agents/anthropic_agent/agent.py:612`, `src/agents/openai_agent/agent.py:863`, and `src/api/routes/query.py:561`.

Original finding (verbatim):

> 2. **P1: Sanitize selected-execution failures before any diagnostic or public sink.** `src/model_credentials.py:1291` still returns `str(exc)` directly in the model-test result, whose schema has no redaction validator (`src/model_credentials.py:113`). A provider error that echoes the selected key therefore exposes it through the Settings response. Native Research has the same unmet requirement: `src/agents/anthropic_agent/agent.py:612` logs the raw exception, and `src/agents/openai_agent/agent.py:855` passes it to the scratchpad; both emit raw exception text as error-event data (`src/agents/anthropic_agent/agent.py:626`, `src/agents/openai_agent/agent.py:862`). `src/api/routes/query.py:571` forwards the legacy stream event without a sanitizing boundary. Server-owned Research's later classifier cannot undo an earlier log or legacy SSE disclosure. Use bounded, sanitized failure data before logging, scratchpad writes, model-test serialization, and legacy SSE emission; add a synthetic key-echo rejection case. These are pre-existing sinks left open by a task that explicitly requires secret-free failures, not a claim that this commit introduced each sink. This finding is static; the single permitted focused execution was used for Finding 1.

Verification:

- `src/auth_drivers/runtime_binding.py:101` uses the captured binding or the already-selected client/probe key, without re-resolving Settings. Exact-key replacement at line 108 precedes generic redaction and the 500-character bound at line 109. Constructor failures use this sanitizer and suppress raw exception context at `src/auth_drivers/runtime_binding.py:87`; model-test failures sanitize before constructing their public result at `src/model_credentials.py:1292`.
- Anthropic sanitizes before its logger, scratchpad, and error event at `src/agents/anthropic_agent/agent.py:612`. OpenAI obtains the actual per-agent client's key at `src/agents/openai_agent/agent.py:360`, sanitizes retry diagnostics at lines 469, 628, and 811, and sanitizes terminal diagnostics at lines 519, 678, and 863. The affected scratchpad calls no longer supply raw tracebacks. Nonstream OpenAI errors are bounded, type-prefixed RuntimeErrors with suppressed context at lines 527 and 686; the original error still controls the existing retry predicate privately.
- Child failure handling passes `child_auth` explicitly after parent-context restoration at `src/agents/shared/subagent.py:393`, before logging or returning the tool error. Legacy streaming sanitizes error/message/detail fields before SSE and persistence at `src/api/routes/query.py:561`; exceptions escaping iteration are sanitized with the captured binding before the log and SSE at line 580.
- Managed Research error events are classified inside the active binding at `src/research_run_manager.py:162`; escaped exceptions explicitly retain that binding at line 198. `src/research_errors.py:106` sanitizes the durable/public detail while classification still examines the original type/shape. Scheduling and failed-handoff persistence logs use the captured binding without raw tracebacks at `src/api/routes/research.py:437` and line 446.
- The approved tracing completion is present at all four Runner sites: `src/agents/openai_agent/agent.py:449`, line 608, line 790, and `src/agents/shared/subagent.py:576` explicitly pass `RunConfig(trace_include_sensitive_data=False)`. Main retries reuse those same kwargs. No global tracing disable or exporter policy change is introduced.
- Installed-SDK source confirms why the per-call setting is necessary and effective: `agents/run_config.py:52` defaults sensitive-data tracing on; `agents/models/openai_responses.py:600` gates raw input/response storage, and line 615 substitutes a redacted span error when sensitive data is disabled, before ArkScope's catch. Usage is assigned outside that gate at line 596. The new enabled-tracing test inspects the live span fields and error data before application handlers, rather than relying only on exported dictionaries.

## New Breakage In The Fix Diff

None identified at Critical, Important, or Minor severity within the supplied findings and fix diff. The approved host pinning is intentional, not an alternate-host compatibility regression to reopen here. The changed retry handlers retain the same predicate and two-attempt limit; the trace setting remains attached to retries. Public Research error classification still uses original error types/shapes before redaction.

Non-blocking SDK limitation confirmed: `agents/tracing/span_data.py:239` derives the trace's provider `response_id` from the raw response object, so suppressing that object makes this field null. Trace/span identity, grouping, timing, agent metadata, error status, and usage remain; the ordinary application ModelResponse still receives `response.id` at `agents/models/openai_responses.py:630`. This does not justify retaining sensitive payloads or expanding this round into an SDK change. The unbound native sanitizer's reliance on `OpenAIResponsesModel._client` at `src/agents/openai_agent/agent.py:362` is also an installed-SDK compatibility dependency, exercised by the focused tests, not an observed regression.

## Out-of-Scope Observations

None raised. Untouched SDK tracing/logging policies and pending Tasks 2/3 were not audited or reopened. This is not a fresh Task 1 or repository-wide review.

## Review Checks

- Used the requested scoped re-review template and task brief; verified Important 1 and 2 against current code after reading the appended Fix Round 1 and Tracing Completion reports. Applied the static fix-verification method to the original ambient-header source/wire boundary and selected-key error/sink boundary.
- Read `task-1-fix-1-complete-review.diff` once for the supplied range `f788ef280c245baf0d8a5f55681564603f75dfb5..af3f06c4ea6c44779d61d5a0800f4db8c747f348`, containing both fix commits. Completed bounded tool-output context with targeted line-numbered worktree reads, without rereading the diff or running git commands. SDK references above are under `/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/` and were checked by reading source only.
- Inspected the changed behavioral owners below. The new fixture at `tests/test_task_runtime_binding.py:599` replaces only the HTTP boundary with synthetic MockTransport responses. The enabled-tracing fixture at line 924 installs an in-memory processor, enables its provider, removes the sensitive-data environment override, restores the previous provider, and guards default exports.

| Behavioral owner in `tests/test_task_runtime_binding.py` | Cases | Evidence checked |
| --- | ---: | --- |
| `test_bound_wire_ignores_late_auth_headers_and_host`:650 | 6 | Selected wire auth/host/model and unrelated header preservation |
| `test_model_probe_key_echo_is_redacted_before_api_serialization`:701 | 2 | Bounded Settings errors, one request, no fallback effort |
| `test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors`:718 | 10 | Bound/unbound main entrypoints, public/log/durable output and exception context |
| `test_child_key_echo_is_redacted_after_parent_context_restoration`:761 | 4 | Same/cross-provider child failures and restored parent binding |
| `test_research_key_echo_redacted_before_sse_and_persistence`:785 | 4 | Legacy/managed event and exception failures, persisted data, timeout classification |
| `test_runtime_error_redacts_exact_key_before_length_bound`:823 | 1 | Exact redaction precedes a bound that would otherwise split the key |
| `test_client_construction_key_echo_is_private`:835 | 6 | Both providers' sync/async/probe constructor failures |
| `test_openai_retry_key_echo_is_private_without_changing_retry_policy`:863 | 3 | Sanitized retry diagnostics and exactly two attempts |
| `test_schedule_key_echo_never_logs_raw_exception_context`:900 | 2 | Scheduling and failed-handoff persistence logs |
| `test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata`:979 | 10 | Five main/child paths, failure/success, pre-catch span snapshots, preserved metadata/results/usage |

- The implementer's final report names the focused suite command and records `837 passed in 25.06s`, exit 0, with no warnings reported. It separately records the unchanged original reviewer doctest as `1 passed in 0.95s`, exit 0. Its tracing owner records RED `10 failed, 80 deselected in 3.59s` and GREEN `10 passed, 80 deselected in 2.97s`. These are reported execution results, not new reviewer runs; the test code and production controls were independently inspected.
- No tests were run during this re-review: static inspection left no named new focused doubt requiring execution. Neither reported suites nor the original doctest were rerun. The report's backend commands use this worktree's `docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py` wrapper; no raw pytest or backend runtime command was invoked here.
- No subagents, provider/prod/credential access, code/index/HEAD changes, merge, push, or restart. The sole authored file is `.superpowers/sdd/2026-09-09-task-route-authority-repair/task-1-fix-1-review.md`, written with apply_patch.

## Verdict

**Fix round: All findings addressed, no new Critical/Important breakage.** Important 1: ADDRESSED. Important 2: ADDRESSED. Open findings: none within this scoped re-review.
