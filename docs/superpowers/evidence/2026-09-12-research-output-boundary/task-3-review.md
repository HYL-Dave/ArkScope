# Spec Compliance

**Issues found.** Task 3 misses one diagnostic sink and cancellation during
terminal cleanup. **Task quality: Needs fixes.** Both findings below have
focused, offline reproductions against the frozen implementation.

Reviewed `97b02d2b825159b09e88a4df2c51952fa3dffe30` ->
`29f18ca7364d04968d3273252b998e2a4fe32780` using `task-3-review.diff`.
The brief, contract, design and implementer report were compared with code;
the implementer's claims were not treated as proof.

Cannot verify from this task diff: whole-branch security, complete-backend
results, and the separately reviewed Task 1/Task 2 internals. The coordinator
owns those remaining gates. This is not SEC feature completion or merge approval
(`docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:113`).

## Strengths And Scoped Checks

- Selected-client registration precedes response use: `src/auth_drivers/runtime_binding.py:99`, `src/agents/openai_agent/agent.py:343`, `src/agents/anthropic_agent/agent.py:286`. ChatGPT registers the post-refresh bearer at `src/auth_drivers/chatgpt_oauth_driver.py:557`; Claude registers its loaded bearer at `src/auth_drivers/claude_code_sdk_driver.py:535`. Direct-client and refresh owners are `tests/test_research_output_events.py:332` and `tests/test_research_output_events.py:350`.
- Parent/child sharing is deliberate, without helper credential recapture: `src/agents/shared/subagent.py:383`, `src/auth_drivers/runtime_binding.py:143`, and OAuth executor context propagation at `src/auth_drivers/chatgpt_oauth_driver.py:501` / `src/auth_drivers/claude_code_sdk_driver.py:271`. Independent wrapper contexts and late child admission are exercised at `tests/test_research_output_lifetimes.py:34`, `:496`, and `:527`.
- Native arguments are checked before SDK invocation or write handlers: `src/agents/openai_agent/tools.py:53` and `src/agents/anthropic_agent/tools.py:1716`. `tests/test_research_output_events.py:459` checks both rejected credentials and unchanged public input, including SDK argument debug logging. OAuth callback admission is at `src/auth_drivers/chatgpt_oauth_driver.py:490` and `src/auth_drivers/claude_code_sdk_driver.py:251`.
- Complete values precede scratchpad/replay/preview sinks: OpenAI arguments/results/final at `src/agents/openai_agent/agent.py:155`, `:199`, `:516`, `:704`; Anthropic thinking/final/tool values at `src/agents/anthropic_agent/agent.py:448`, `:494`, `:537`, `:549`; Claude tool previews at `src/auth_drivers/claude_code_sdk_driver.py:817`. Real sink assertions are at `tests/test_research_output_events.py:364`, `:384`, `:395`, `:405`, and `:429`.
- Stateful prose protection preserves public text and separates text/thinking state: `src/agents/shared/output_events.py:232`, `:242`; full-value helpers are at `:59` and `:74`. Tests cover encoded splits, small chunks, exact numbers/URLs and final-only answers at `tests/test_research_output_events.py:258`, `:269`, `:279`, `:288`, `:307`.
- Per-operation guard activation resets before consumer resumption, and trusted stream identity avoids a second rolling tail: `src/agents/shared/output_events.py:115`, `:173`, `:259`; `tests/test_research_output_lifetimes.py:34`, `:74`, `:342`, `:427`. Normal terminal closure, reentrancy rejection and borrowed-sibling isolation have owners at `:261`, `:289`, `:322`. Cancellation during cleanup is the missing case, not a reason to discard these controls.
- Both outer sinks protect raw factories: `src/research_run_manager.py:157` precedes append at `:162` / `:204`; `src/api/routes/query.py:566` precedes trace collection and SSE at `:585` / `:590`. Durable split and raw metadata owners are `tests/test_research_output_events.py:534` and `:565`.
- Metadata is checked and typed rather than rewritten into successful identifiers (`src/agents/shared/output_events.py:193`, `:212`, `:215`). Refusal details retain their closed diagnostic projection (`:202`); personalization remains caller-owned (`src/research_run_manager.py:181`). The existing runtime/refusal, card authority, retry/tracing, OAuth, session and route controls are present in the inspected focused-run inventory.
- The 15 changed paths match the authorized integration scope. The two existing-test edits honor the supplied ownership rulings: exact text/terminal/timeout/follow-up assertions remain at `tests/test_chatgpt_oauth_driver.py:679`, and only decorated-generator inspection changes at `tests/test_openai_sync_surface_cleanup.py:34` / `:37`. No Task 1 matcher, Task 2 policy, source capture or SEC feature rewrite is included.

## Important Findings

### I1 [P1]: Captured Bearer Can Reach Cleanup Diagnostic Logs

**Location:** `src/auth_drivers/chatgpt_oauth_driver.py:212`.
The newly protected entry at `:458` closes `_managed_stream` at its terminal;
that generator calls `_close_execution_client` at `:469`. If client close
raises an exception containing the captured bearer, the helper logs it using
`exc_info=True`. Guard activation around close does not sanitize a logging
traceback. The raw exception is therefore emitted before any output projection
can protect this sink, even though the public answer is safe.

**Evidence:** `test_task_3_review_probe.py:64` uses the real ChatGPT adapter and
existing synthetic producer fixture, changing only the fake client's close to
raise an echo of its already-captured bearer. The public-answer and client-close
assertions pass; the no-secret-in-log assertion at `:86` fails.
`task3-review-cleanup-log-02/output.log:13` identifies the production logger;
`:28` contains the synthetic bearer in its traceback. Run result: **1 failed**,
no setup/provider failure (`:37`). No production disclosure is claimed.

**Requirement:** `task-3-contract.md:87` and design
`docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:82`.
This is a missed Task 3 integration sink in an existing helper, not a claim
that Task 3 introduced the logging statement or that Task 1/Task 2 need redesign.

**Fix:** Emit a bounded diagnostic using the retained guard and omit the raw
exception traceback. Adding sanitized message text while retaining
`exc_info=True` would still leak. Preserve the successful public answer.

### I2 [P2]: Cancellation During Terminal Close Loses Cleanup Ownership

**Location:** `src/agents/shared/output_events.py:169`.
`_close_upstream` marks the iterator closed and drops its upstream reference
before awaiting `aclose()` at `:174`. A cancellation during that await can
interrupt client teardown. The exception path's retry at `:148` and all later
public `aclose()` calls stop at the already-closed check at `:167`. With the
actual ChatGPT `_managed_stream`, cancellation while awaiting client close at
`src/auth_drivers/chatgpt_oauth_driver.py:469` leaves the client unclosed and
the wrapper unable to finish cleanup.

**Evidence:** `test_task_3_review_probe.py:17` pauses only the synthetic client's
close, cancels once after close begins, releases it, and calls wrapper
`aclose()` again. The normal-close control passes; cancelled cleanup fails the
closed-client assertion at `:51`. The probe tears down its fake client itself
after recording the failure. `task3-review-close-cancel-01/output.log:10` and
`:20`: **1 failed, 1 passed**, no setup/provider failure.

**Requirement:** `task-3-brief.md:26`, `task-3-contract.md:72`, and design
`docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:83`.
Existing tests cancel during response advancement, not during terminal cleanup
(`tests/test_research_output_lifetimes.py:389`).

**Fix:** Retain ownership of in-flight close and make cleanup survive consumer
cancellation, for example with an explicitly awaited/shielded close task.
Do not just retry a generator whose interrupted finalizer has already exited.
Keep cancellation semantics, pending-tail discard, non-reentrancy and
per-operation ContextVar restoration intact.

## Verification Evidence

- Inspected, not rerun: `task3-focused-green-20/output.log:17` and `task3-focused-green-20/results.xml:1` report **1,022 passed**, zero failures/errors/skips. Parsed JUnit counts confirm **329 + 32 = 361** new owners. The inspected output contains no warnings.
- Inspected initial RED: `task3-red-final-04/results.xml:1` reports **339 failed, 22 passed**, zero errors/skips. Required inverse artifacts show **1 failed/1 passed** for stateless streaming, **2 failed/2 passed** for missing direct-client registration, and **3 failed/1 passed** for missing manager pre-append protection. Failure nodes and positive controls match the report and diff. All five inspected JUnit SHA-256 values match the implementer report.
- Executed only reviewer-owned probes through `run_checks.py` backend mode: `task3-review-close-cancel-01/command.json:1` and `task3-review-cleanup-log-02/command.json:1`. No existing suite was rerun. Probe source and all results are confined to this owned scratch directory.
- Coordinator status, not independently inspected: the first backend invocation collected archived documentation tests and stopped with eight collection errors and zero test execution; the corrected `-q tests` invocation remains a separate verification gate. That aborted invocation is not backend pass evidence and does not change this immutable Task 3 review.

## Named Outside Checks And Read Limits

- SDK pre-handler logging/tracing risk: checked installed `agents/tool.py:1949` / `:2728`, `agents/run_internal/tool_execution.py:1818` / `:2072`, and the model debug gate in `agents/models/openai_responses.py:596` / `agents/_debug.py:12`. Callback admission precedes the inspected tool-argument logs; native RunConfig still excludes sensitive trace data. The isolated fixture and local trace processor were checked at `tests/test_task_runtime_binding.py:23` / `:1073`.
- Pre-persistence compressor/session risk: checked `src/agents/shared/context_manager.py:223` for the Layer 0 overflow boundary and `src/agents/openai_agent/agent.py:87` for the existing in-memory compaction-session factory. The native entry hunks omit their middle, so the Runner/session blocks in `run_query` and `run_query_stream` were read only to resolve this concrete sink/configuration question.
- Borrowed child scope risk: checked only unchanged scope/activation contracts at `src/agents/shared/output_boundary.py:408` / `:424`; no matcher or result-policy re-review.
- Terminal cancellation/diagnostic sink risk: the `_managed_stream` hunk stops in the client cleanup loop, so its remaining close statements and `_close_execution_client` at `src/auth_drivers/chatgpt_oauth_driver.py:205` were inspected. These checks produced I1/I2 and the focused probes, rather than a whole-branch crawl.
- Read the diff once. Tool-output truncation required recovering only its omitted Claude `:623` through `:811` segment. Product/test source, index and HEAD were not modified; only this report, the new owned probe and offline-run artifacts were written. No agents, live provider, production credentials/data, network, install, merge or push.

## Assessment

**Spec compliance: Issues found. Task quality: Needs fixes.** The shared
projection, admission ordering and tests preserve legitimate research content
without broad heuristic redaction. Fix the demonstrated cleanup log leak and
cancellation ownership gap before approving Task 3; retain the separate
complete-backend and blind whole-branch review gates.
