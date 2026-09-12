# Task 3: Research Events And Execution Lifetimes

## Status And Authority

- Recorded base: `97b02d2b825159b09e88a4df2c51952fa3dffe30`.
- Scoped Task 3 commit: `29f18ca7364d04968d3273252b998e2a4fe32780`
  (`feat: protect research events and execution lifetimes`), direct parent is
  the recorded base. Exactly 15 authorized product/test files committed.
- Consumes independently approved Task 1 guard and Task 2 result policies,
  including Task 2 fixes `41b9f2b5`. No core or result-policy interface gap found.
- Full Task 3 GO received after Task 2 independent approval. No other worker
  owns these product edits. Coordinator's tracked plan edit was left unstaged;
  no docs or scratch evidence were included in the commit.
- Implementation and all 361 prepared owners pass. Combined focused check:
  **1,022 passed, 0 failed/errors/skips** in `task3-focused-green-20`.
- The two failures from run 19 were existing assertions incompatible
  with the approved iterator/chunk contract. Coordinator explicitly granted
  ownership for only these two test scopes after independently reading run 19.
  Both were refined exactly as ruled and pass in the same focused selection.
- Task 3 is **not complete**: ready for independent task review. Coordinator
  full-suite verification and whole-branch review remain gates. No full backend
  suite was run here.

## Scope

New owned files:

- `src/agents/shared/output_events.py`
- `tests/test_research_output_events.py` (329 nodes)
- `tests/test_research_output_lifetimes.py` (32 nodes, including 17 primitive owners)

Existing owned product files changed:

- `src/auth_drivers/runtime_binding.py`
- `src/auth_drivers/chatgpt_oauth_driver.py`
- `src/auth_drivers/claude_code_sdk_driver.py`
- `src/agents/openai_agent/agent.py`
- `src/agents/anthropic_agent/agent.py`
- `src/agents/openai_agent/tools.py` (pre-SDK argument admission only)
- `src/agents/anthropic_agent/tools.py` (pre-handler admission only)
- `src/agents/shared/subagent.py`
- `src/research_run_manager.py`
- `src/api/routes/query.py`

No edits to `output_boundary.py`, registry, result policy, live resolver,
scratchpad/replay implementations, credential stores, model selection or SDK
dependencies. Source producers protect their complete values before those
existing storage helpers. This report is scratch evidence, not staged docs.

## Exact Integration Interfaces

`src.agents.shared.output_events` exports:

```python
class ProtectedEventStream(AsyncIterator[AgentEvent]):
    def __init__(self, stream: AsyncIterator[AgentEvent], *, guard: OutputGuard): ...
    @property
    def guard(self) -> OutputGuard: ...
    def __aiter__(self) -> ProtectedEventStream: ...
    async def __anext__(self) -> AgentEvent: ...
    async def aclose(self) -> None: ...

def protect_events(stream, *, guard: OutputGuard | None = None) -> ProtectedEventStream: ...
def protect_event_stream(function): ...  # native async-generator decorator, wraps metadata
def check_output_value(value, *, guard: OutputGuard | None = None): ...
def protect_output_text(text: str) -> str: ...
```

`check_output_value` checks the complete strict JSON value and its canonical
JSON spelling, validates UTF-8, and returns a detached JSON value. Thus numeric
metadata keeps its type but cannot encode a known numeric credential unnoticed.
It is used before input callbacks, full tool trace extraction and preview sinks.
`protect_output_text` is exact full-value prose projection, not diagnostic
entropy filtering. Neither helper resolves credentials.

`runtime_binding.register_output_api_key(client)` remembers only a concrete
string key from the already-selected client, in the active execution guard.
No ambient key or account enumeration is added. `activate_runtime_auth` adds
the already-captured API binding to an existing guard, without recapture.
The diagnostic sanitizer additionally uses that guard's known representations
before the existing heuristic and 500-character bound.

### Iterator Contract

- Factory idempotence is by `type(stream) is ProtectedEventStream` and guard
  identity. A different explicit/active guard fails with `invalid_value`.
  Subclasses and payload booleans do not establish trust.
- With no explicit/current guard, a protected iterator retains its guard; a raw
  iterator gets a new guard. Native decorators and OAuth factories return the
  trusted iterator immediately, preserving normal `async for`/`aclose` use.
- Guard activation surrounds each upstream `__anext__` and `aclose`, never a
  public yield. The consumer's context is restored before returning an event.
- Independent text/thinking streams retain bounded undecidable tails. Normal
  EOF/done flushes; errors, exceptions, cancellation and explicit close drop.
- Upstream closure precedes the public terminal. Only one terminal can escape;
  later upstream events are not consumed. Reentrant advance/close is rejected.
- A borrowed wrapper closes only its own matchers. It does not abort sibling
  matchers retained by a shared parent guard.
- Manager and legacy SSE protect raw injected streams but reuse trusted producer
  streams. The actual producer/manager benchmark still first appends after
  **2,736 input characters** for the 2,051-character synthetic bearer, not after
  a second rolling tail. This is a content-length assertion, not a time SLA.

### Inspected Event Inventory

The projection follows actual producers and existing public fixtures:

| Event | Fields |
| --- | --- |
| thinking | turn, model, provider |
| text | content |
| thinking_content | thinking |
| tool_start | tool, input, call_id |
| tool_end | tool, summary, chars, is_error, call_id |
| done | answer, tools_used, provider, model, token_usage |
| error | error, message, detail, code, provider, model, turn, tools_used, token_usage, scratchpad, stop_details |

Typed metadata is checked before emission; unknown root fields fail closed.
Required content/input fields, integer counters, bool flags and string tool/ID
fields are enforced. Model/provider/scratchpad may be null as actual fixtures
require. Personalization remains caller-added trusted metadata after provider
projection, as in the existing route/manager contract.

Refusal `stop_details` has its pre-existing closed diagnostic projection:
`type`, `category`, `explanation` string fields only, sanitized before the
existing 500-character bound. Null/malformed/nested/unknown details are dropped
without replacing `model_refusal` by a generic boundary error. The 54 existing
refusal nodes, including raw injected adapters and real SDK parsing, pass.
Other errors retain their producer/caller diagnostic handling; the wrapper
does not newly heuristic-filter static protocol errors or successful prose.

## Wiring And Preserved Contracts

- Native OpenAI registers the client in `_build_agent`; both asynchronous
  nonstream and stream entries share the guard. Complete final answers are
  projected before scratchpad/replay. `_extract_tool_info` checks full raw and
  parsed arguments, IDs and complete results before logging or slicing.
- OpenAI tool admission precedes SDK `on_invoke_tool`, whose implementation
  parses/logs arguments before calling the Python handler. The existing owned
  callback test now also enables actual SDK argument debug logging and verifies
  that rejected credentials never reach it. Task 2 handled-error sanitization
  and constant error-span annotations remain unchanged.
- Anthropic registers the selected client before provider use; tool metadata,
  arguments and complete results are checked before callback/compressor/storage.
  Final answers are projected before storage. A parallel thinking sink matcher
  protects across blocks/turns before the 500-character preview. This is not a
  serial second buffer in the public producer/manager path. Successful close
  flushes it; abnormal close aborts it. Public block whitespace is preserved.
- Direct Anthropic tool dispatch keeps Task 2's constant unknown-tool veto and
  error envelope. Known-input admission follows that veto and precedes handlers,
  returning bounded codes rather than logging a rejected name/value.
- ChatGPT registers the actual post-refresh bearer before constructing/using
  the execution client. Old/unselected bearers are not additionally registered.
  Text and final answers no longer pass through the diagnostic heuristic.
  Existing manual Responses history, deadline, retry/auth classification and
  client cleanup remain. GeneratorExit is not converted into another yield.
- Claude registers its loaded bearer before SDK query/MCP use. Text/thinking
  keep whitespace and are projected by the shared wrapper; full tool results
  are admitted before preview slicing. Boundary failure during mapping becomes
  one bounded `provider_call_failed` event, with SDK/config-dir cleanup before
  consumer resumption. Runtime admission, auth evidence, isolated environment,
  tool allowlist and timeout/cancellation handling remain.
- OAuth dedicated worker pools use `copy_context().run` for synchronous calls.
  Pool ownership, timeout and non-blocking shutdown are unchanged. Threads share
  the parent guard object; deliberately captured child secrets remain available
  to later parent callbacks after runtime-auth restoration.
- Subagent delegation borrows the active guard, adds only actual child auth,
  and admits/project results before returning. Same-provider inheritance and
  deliberate cross-provider capture remain the existing selection policy.
- Managed execution owns an inherited-or-new output scope and uses `aclosing`
  around the idempotently protected iterator before *any* durable event append.
  Cancellation keeps the atomic typed terminal/message contract.
- Legacy SSE protects raw injected streams, classifies boundary rejection as
  `provider_call_failed`, closes upstream and retains existing unresolved
  disconnect persistence behavior. No output guard stays installed across SSE
  yields. No schema/migration or durable auth state was added.
- Native OpenAI remains final-only, using the existing `Runner.run`, session,
  two-attempt transient retry policy, `auto_previous_response_id` and
  `RunConfig(trace_include_sensitive_data=False)`. No streaming SDK rewrite,
  auth fallback, extra capture, retry or model/effort substitution was introduced.

## Evidence

All product tests used the mandatory closed runner. Run directories below are
relative to this report and contain `command.json`, `output.log`, `results.xml`.

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py \
  task3-UNIQUE backend ...
```

| Run | Result | Purpose |
| --- | --- | --- |
| task3-red-final-04 | 339 failed, 22 passed | Prepared 361-node baseline; no collection/setup errors |
| task3-primitive-red-05 | 17 failed, 15 deselected | Named missing-wrapper assertions |
| task3-primitive-restored-09 | 17 passed, 15 deselected | Narrow-GO primitive after its two inverses |
| task3-integration-first-10 | 361 passed | First full-GO producer/lifetime integration |
| task3-compatibility-11 | 500 passed, 15 failed | Revealed refusal projection, Claude in-band failure, two collateral assertions |
| task3-compatibility-repair-12 | 552 passed, 1 failed | Found newly applied heuristic damaged static subscription error |
| task3-compatibility-repaired-13 | 192 passed | All runtime-binding and Claude SDK driver controls restored |
| task3-inverse-stateless-14 | 1 failed, 1 passed, 327 deselected | Real ChatGPT split negative and public-prose positive |
| task3-inverse-client-capture-15 | 2 failed, 2 passed, 325 deselected | Both unbound real SDK entries and public controls |
| task3-inverse-preappend-16 | 3 failed, 1 passed, 357 deselected | Raw durable split leaks; real protected producer still works |
| task3-restored-owners-policy-17 | 506 passed, 1 failed | Restored 361 owners plus Task 2 adapter controls; found unknown-tool envelope regression |
| task3-admission-compatibility-18 | 15 passed, 460 deselected | Unknown-tool, write admission, SDK parsing/logging and safe span controls restored |
| task3-focused-pre-collateral-19 | 1,020 passed, 2 failed | Complete focused set, no skips/deselection; only requested collateral assertions remain |
| task3-focused-green-20 | 1,022 passed, 0 failed/errors/skips | Same focused set after only the two explicitly approved expectation replacements |

The final prepared baseline split is 318 behavioral failures plus 21 named
missing-wrapper assertions, not ImportError. Earlier fixture setup corrections
were made only in the two owned files: allowlisted OAuth acquisition callbacks,
current supported route model, and actual local SDK tracing fixture.

### Required Integration Inverses

1. Changed stream `feed` to fragment-local `guard.prose`.
   `test_incremental_producers_protect_known_secret_at_every_split[raw-3-chatgpt]`
   reconstructs the synthetic credential; its public-content control passes.
2. Disabled `register_output_api_key` registration.
   `test_unbound_api_entry_registers_only_selected_client_before_response`
   fails for both OpenAI and Anthropic because request-time registration is
   absent. Both public-content controls pass.
3. Removed manager `protect_events` before append while retaining normal close.
   `test_managed_injected_stream_is_protected_before_event_append_and_replay`
   fails at all three chunk widths with raw credential reconstruction despite
   a safe final answer. The already-protected real producer/manager control
   still passes, including the 2,736-character first emission assertion.

All mutations were restored via apply_patch. Pre-inverse/restored SHA-256:

```text
703b1caea0107a72db281fb58fc033f5e7c181d2c75569addd6abd716bc74b2c output_events.py
02f538a84c62b39fd0b107fa67ba1bb0b4aa6bc13b22ef32deb8152497183595 runtime_binding.py
64ac32228a2eb259ace5817779ecf25d3b62ab503d78fe0a2271bb6a18db2316 research_run_manager.py
```

### Focused Coverage Counts

Run 20 executes the identical node inventory below with **zero failures in
every row**. Historical run 19 failures are retained to identify the precise
collateral replaced, rather than hiding them as baseline failures.

| File | Nodes | Failures in run 19 |
| --- | ---: | ---: |
| test_research_output_events.py | 329 | 0 |
| test_research_output_lifetimes.py | 32 | 0 |
| test_tool_output_channels.py | 146 | 0 |
| test_task_runtime_binding.py | 141 | 0 |
| test_chatgpt_oauth_driver.py | 46 | 1 |
| test_claude_code_sdk_driver.py | 51 | 0 |
| test_claude_agent_sdk_runtime.py | 9 | 0 |
| test_card_execution_authority.py | 44 | 0 |
| test_research_runs.py | 37 | 0 |
| test_research_routes.py | 69 | 0 |
| test_research_threads.py | 28 | 0 |
| test_subagent.py | 61 | 0 |
| test_server_compaction.py | 16 | 0 |
| test_replay_openai.py | 6 | 0 |
| test_openai_transport.py | 4 | 0 |
| test_openai_sync_surface_cleanup.py | 3 | 1 |

JUnit SHA-256 for decisive evidence:

```text
2553eb06165b98ae34d912c8d8dfa5653b5e49549883ceb074c179252f84c351 task3-red-final-04/results.xml
45f8114ff4196b578affd0089c79f9515498b27ea80870c38ab05f2e814e72aa task3-integration-first-10/results.xml
ecdffe4cb5e11700a1d2e9163e944d50a2d06b1cd6f2fb70c0f678fcd4afc073 task3-inverse-stateless-14/results.xml
46375c2e7b69a63fdfcbdcace209acf862bb229751ee01f355c77cadb08953d1 task3-inverse-client-capture-15/results.xml
b5f79b28e9e807c7c74e215db172436cc516fd37a24782fd6dc793b31b63388f task3-inverse-preappend-16/results.xml
29341486cd6d3754c19b0f72fd4afa224f23652c2280408d6178848a7306e6cb task3-focused-pre-collateral-19/results.xml
0009481ed4f2bf007bebabe133f3764c426cc2c1798596a7a65cf22217bf3f80 task3-focused-green-20/results.xml
```

## Approved Narrow Collateral Ownership

Explicit coordinator GO was received after independent inspection of run 19.
Only the following existing test scopes were edited:

1. `tests/test_chatgpt_oauth_driver.py::test_stream_llm_returns_tool_timeout_to_model_instead_of_terminal_error`:
   the assertion assumes one text event for one SDK delta. The required rolling
   tail emits an initial safe prefix and a final EOF/done tail instead. The
   assertion now preserves non-text event order and exactly one terminal,
   concatenates text and checks equality with the exact done answer, and keeps
   the timeout result/error flag and follow-up input checks. Exactly two model
   calls are asserted. Timeout, handler, fixture credential, session and retry
   were not altered.
2. `tests/test_openai_sync_surface_cleanup.py::test_retained_research_entrypoints_are_available`:
   `inspect.isasyncgenfunction` on a synchronous iterator factory is false.
   Both native generator checks now use `inspect.unwrap`; coroutine/callable
   and removed-sync-surface assertions are preserved. Exact iterator type, identity,
   active-guard restoration and closure already have the prepared lifetime
   owners, including all four actual producers.

These are planned async-iterator interface collateral, not baseline failures
to waive. No other existing test expectations were changed. The same complete
focused selection passed before the scoped commit; independent review remains.

## Safety And Remaining Gates

- `git diff --check` passed; targeted base diff confirmed Task 1 core, registry,
  Task 2 result policy, live resolver and scratchpad/replay helpers unchanged.
  Only the explicitly authorized two existing test scopes were refined.
- Test environment is the closed runner, with synthetic HTTP/SDK messages,
  synthetic credentials, local trace processors and disposable databases.
- No provider calls, live credentials, .env reads, production data, dependency
  installation, network, migrations, worker subagents, restart, merge or push.
- Ordinary exact-public content, all known-secret splits, callbacks, real
  managed persistence/replay and lifecycle owners are covered. No generic fuzz
  framework or speculative feature work was added.
- Precommit worktree/index whitespace checks passed. The staged paths matched
  the 15 authorized files and the tested worktree. The postcommit comparison
  confirms core, registry, result policy and downstream storage helpers are
  unchanged from the recorded base. The remaining worktree diff is only the
  coordinator-owned tracked plan edit, intentionally preserved.
- Pending: independent Task 3 review, coordinator full backend and final branch
  review. No Task 3 completion claim or review approval is made in this report.
