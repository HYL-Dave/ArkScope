# Task 3 Fix Round 1 Report

Date: 2026-09-12
Workspace: /tmp/arkscope-research-output-boundary
Base: 29f18ca7364d04968d3273252b998e2a4fe32780
Fix commit: fdc947d22991703594715210eed917232cc38c55

Status: I1 and I2 are remediated in focused verification. Task 3 is NOT COMPLETE
until independent rereview. Full-backend verification remains the coordinator's
gate; no full-backend run was started by this worker.

## Scope And Diff

Only these four tracked files are part of this fix:

| Path | Added | Removed | Change |
| --- | ---: | ---: | --- |
| src/agents/shared/output_events.py | 26 | 5 | Own and await one close task through cancellation |
| src/auth_drivers/chatgpt_oauth_driver.py | 1 | 1 | Remove raw cleanup traceback from fixed warning |
| tests/test_research_output_events.py | 36 | 0 | Actual ChatGPT diagnostic regression |
| tests/test_research_output_lifetimes.py | 86 | 0 | Actual ChatGPT normal/single/repeated-cancel cleanup owners |

Total: four files, 149 insertions, six deletions. No existing test expectations
were replaced in this round. Task 1 core, Task 2 result policies, auth selection,
capture sources, retry, timeout, model, session and transport options are unchanged.
The public OutputGuard/protect_events/ProtectedEventStream interfaces are unchanged.

Exact unified diff: [task-3-fix1.diff](task-3-fix1.diff), generated from:

```sh
git diff --binary -- src/auth_drivers/chatgpt_oauth_driver.py src/agents/shared/output_events.py tests/test_research_output_events.py tests/test_research_output_lifetimes.py
```

Diff SHA-256: cad7911487726102148ec03c976405c3d2802e7cb1272fce3bd79fd78fbf1f14

Foreign work was neither edited nor staged: the coordinator's two tracked design/
plan documents, codex_account_usage.py, new test_model_catalog_output_boundary.py,
and the diagnostic-only _redact_bridge docstring in claude_code_sdk_driver.py.
The coordinator's frontend JUnit artifact was not touched. This scratch report,
the diff artifact and runner artifacts are not included in the four-file commit.

## Findings And Owners

Read Newton's task-3-review.md and test_task_3_review_probe.py. Reproductions use
the existing make_producer fixture, real ChatGPT adapter, synthetic selected bearer
and disposable isolated DB. Only the fixture client's close behavior is changed.
Both owned tests were added before either product fix.

### I1: Raw Cleanup Diagnostic

Source-to-sink: ChatGPT _managed_stream finalization calls _close_execution_client;
a close exception containing the selected bearer reached logger.warning through
exc_info=True. The current output guard cannot sanitize a Python traceback.

At src/auth_drivers/chatgpt_oauth_driver.py:205, the helper still swallows ordinary
cleanup exceptions to preserve the successful answer, but emits only its existing
fixed warning. It neither formats the exception nor attaches traceback data.
CancelledError is not converted to an ordinary cleanup warning.

Owner: tests/test_research_output_events.py:363
test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer.
It checks one successful terminal with the exact public answer, client closure,
the retained guard during close, caller scope restoration, no synthetic bearer
in logs, exactly one fixed warning, and no exc_info or exc_text.

### I2: In-Flight Close Ownership

At src/agents/shared/output_events.py:167, _close_upstream previously dropped its
source and marked itself closed before directly awaiting the generator finalizer.
Consumer cancellation could interrupt that finalizer; later aclose could not
resume it.

The fix starts one strongly retained local close task. That task activates and
resets the retained output guard around the actual upstream aclose. The consumer
awaits it through asyncio.shield. If cancelled, the same consumer keeps shielding
and awaiting that same task until it settles, including repeated cancellation,
retrieves its outcome and re-raises the original cancellation. No close retry,
detached cleanup, new timeout, uncancel, or public cancellation translation is added.
The upstream reference is cleared only after settlement. The existing busy gate
remains set throughout, preventing another anext/aclose from stealing ownership.
The existing __anext__ abort path drops pending text/thinking tails after failure.
Normal completion still flushes unmatched tails and emits exactly one terminal.

Owner: tests/test_research_output_lifetimes.py:389
test_chatgpt_terminal_cleanup_is_owned_until_settled, with normal-close,
cancel-during-close and cancel-again-during-close parameters.
It pauses actual adapter client teardown while a credential prefix is pending.
Cancellation must not return before release; cleanup must start/finish once under
the retained guard. It checks cancellation propagation, no cancelled terminal or
tail emission, unchanged normal answer/EOF tail, non-reentrancy, scope reset,
idempotent later close and no repeated terminal.

## Task And Context Compatibility

This was a read of the actual locally installed implementation, not an inference
from fake-client tests. Installed claude-agent-sdk is 0.2.152, confirmed from
_version.py and package METADATA. Existing runtime admission tests enforce that
reviewed version. No SDK source or runtime admission setting was changed.

SDK paths below are relative to:
/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/claude_agent_sdk/

- _internal/client.py:33 / :73: process_query and _process_query_inner use try/finally;
  connect, receive and close do not manually enter a task group across a public yield.
- _internal/query.py:285 / :290: start and child spawning use spawn_detached task
  handles. receive_messages at :894 has no caller-owned cancellation scope.
- _internal/_task_compat.py:1 / :54 / :157 explicitly supports cancellation from
  another task, including async-generator finalizers. Its asyncio implementation
  uses loop.create_task; TaskHandle.wait does not exit a caller-entered task group.
- _internal/transport/subprocess_cli.py:787 / :870: connect starts the stderr
  reader with the same task-handle approach, not a manually entered TaskGroup.
  close at :942 opens its own shield/deadline scopes locally within close.
- _internal/sdk_mcp_bridge.py:109 / :145: each MCP session's _run task owns the
  in-memory streams and enters/exits its own AnyIO task group. External aclose
  at :289 signals the stream and waits on that task handle. Its deadline scopes
  are entered and exited inside aclose, not borrowed from connect/receive.
- _internal/query.py:908 / :940: Query.close opens a local shield scope, closes
  bridges, cancels/waits its reader handle, then closes the transport.

Result: the current installed Claude path does not require connect/receive/close
to execute in one asyncio Task. The close task does not exit scopes or reset tokens
created in the iterator-advance task. No execution-task ownership redesign is needed.
This conclusion is specific to the admitted local SDK, not a promise about arbitrary
custom iterators or unreviewed SDK versions.

Other actual transport checks:

- Native OpenAI run_query_stream completes await Runner.run (agent.py:672) before
  yielding its later tool/final events. Its streaming generator has no ContextVar
  reset token or task-bound context manager held across public yields.
- Native Anthropic exits the synchronous response context (agent.py:436) before
  thinking/tool/final yields. Its finally aborts its own thinking stream and
  closes scratchpad without a cross-task token reset.
- ChatGPT _managed_stream (chatgpt_oauth_driver.py:460) and _stream use generator
  try/finally, without a caller-entered ContextVar scope spanning public yields.
  Installed openai/_streaming.py:166 / :234 closes its HTTP response; HTTPX's
  request_context annotates RequestError, not ContextVar state. HTTPcore's Trace
  does not hold a reset token; cancellation shields are entered locally in close.
- Claude's driver _stream uses the inspected query path and has no caller-owned
  scope spanning yields. Its existing deadline path already advances agen using
  asyncio.wait_for; neither this nor its timeout/session behavior was changed.

The unchanged four-transport guard/lifetime controls, both OAuth normal-terminal
and cancellation controls, and all nine reviewed Claude runtime controls passed.
No live provider session, authenticated SDK query, or network check was attempted.

## RED, Inverses And Restores

Initial run task3-fix1-red-01: 3 failed / 1 passed / 0 errors / 0 skips.
Failures were exactly the new diagnostic owner and both cancellation parameters.
The normal-close control passed. These were assertion failures at the real adapter
boundary, not import/setup errors.

- I1 inverse (04): restore only exc_info=True. Diagnostic owner fails, normal close
  passes (1F/1P). Restore run (05): 2P.
- I2 unshielded inverse (06): restore the old direct-await close body while keeping
  I1 fixed. Both cancellation owners fail; I1 and normal close pass (2F/2P).
  Restore run (07): 4P.
- I2 detached-shield inverse (08): retain task creation and initial shield but remove
  the cancellation drain. Both cancellation owners fail because the consumer
  returns before cleanup settles; I1 and normal close pass (2F/2P).
  Restore run (09): all four owners plus Newton's three unchanged probe nodes pass (7P).

All mutations were applied/restored with apply_patch, one run at a time. Every run
finished; none hung or required termination. No source mutation was left active.
All four file hashes after the final restore match the pre-inverse green state:

```text
fd581df03074f46c37ffc3809b3917c3084108ec8b6adf8c4a87a4fb71ae4eb5  src/auth_drivers/chatgpt_oauth_driver.py
5bf21ae27621bfd1a199f64f17b79b97b1499c4a29c8e4424207f8e1484a1cc7  src/agents/shared/output_events.py
6b94c7e60f6de89cbcb8613c1c1aeb6531d488016e87f00743a5d09ca71f866a  tests/test_research_output_events.py
b562ff59858138cc39be61b6be6f2914b8d040881fba5e59f8767aa31955172c  tests/test_research_output_lifetimes.py
```

## Focused Verification

Final run task3-fix1-focused-final-10: 1026 passed, zero failures/errors/skips.
The earlier focused-green-03 run also passed 1026. Final pytest elapsed time:
51.97 seconds; closed-runner wall time: 53.387 seconds. No warning summary.
Task 3 owner counts are now 330 events + 35 lifetimes = 365 (four added nodes).
The remaining 661 nodes are the unchanged focused regression list.

That list includes tool-output policy, runtime binding/key echo, ChatGPT and Claude
drivers, Claude runtime admission, card authority, managed runs/routes/threads,
subagent propagation, compaction/session behavior, replay, OpenAI transport and
decorated-entrypoint identity. The original Task 3 integration inverses remain
historical evidence in task-3-report.md; this fix round adds the independent
I1/I2 inverses above without reworking those integration paths.

git diff --check on the four scoped files passed before and after inverses.
Final source/diff review traced normal close, close failure, consumer cancellation,
repeated cancellation, scope restoration and exact terminal/tail behavior.
No confirmed bypass or compatibility regression required another product path.

After the coordinator's interruption/status request, read-only process inspection
found no owned runner/pytest process. Last owned session 13263 had already completed
with exit 0. The index was empty; the four restored hashes were reconfirmed. No
process termination or additional product edit was necessary.

## Exact Test Commands And Artifacts

Every test invocation used the mandatory closed runner from the workspace above.
Each named directory contains command.json (expanded child command and closed
environment), output.log and results.xml. Counts below were parsed from JUnit XML
using standard-library ElementTree, not inferred from progress dots.

| Run | Passed | Failed | Errors | Skips | Exit | Runner Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| task3-fix1-red-01 | 1 | 3 | 0 | 0 | 1 | 3.392 |
| task3-fix1-owners-green-02 | 36 | 0 | 0 | 0 | 0 | 14.263 |
| task3-fix1-focused-green-03 | 1026 | 0 | 0 | 0 | 0 | 53.548 |
| task3-fix1-inverse-i1-04 | 1 | 1 | 0 | 0 | 1 | 3.206 |
| task3-fix1-restore-i1-05 | 2 | 0 | 0 | 0 | 0 | 3.151 |
| task3-fix1-inverse-i2-unshielded-06 | 2 | 2 | 0 | 0 | 1 | 3.356 |
| task3-fix1-restore-i2-07 | 4 | 0 | 0 | 0 | 0 | 3.106 |
| task3-fix1-inverse-i2-detached-08 | 2 | 2 | 0 | 0 | 1 | 3.329 |
| task3-fix1-restore-review-probes-09 | 7 | 0 | 0 | 0 | 0 | 3.203 |
| task3-fix1-focused-final-10 | 1026 | 0 | 0 | 0 | 0 | 53.387 |

### task3-fix1-red-01

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-red-01 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled --tb=short
```

JUnit SHA-256: 0979f740cd03b33d9d49a1ec1e22370cb6428fd54550ce45d829ff1a2aa0ed17

### task3-fix1-owners-green-02

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-owners-green-02 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py --tb=short
```

JUnit SHA-256: e6af4cb58e80a7e95abe6a307baeea802d108e82b3c8cac9eef1026532769501

### task3-fix1-focused-green-03

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-focused-green-03 backend -q tests/test_research_output_events.py tests/test_research_output_lifetimes.py tests/test_tool_output_channels.py tests/test_task_runtime_binding.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_claude_agent_sdk_runtime.py tests/test_card_execution_authority.py tests/test_research_runs.py tests/test_research_routes.py tests/test_research_threads.py tests/test_subagent.py tests/test_server_compaction.py tests/test_replay_openai.py tests/test_openai_transport.py tests/test_openai_sync_surface_cleanup.py --tb=short
```

JUnit SHA-256: 4c3f8331cca59c8fae9d3486d7f8d65331854b572fd933c43885441fdaa78b3c

### task3-fix1-inverse-i1-04

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-inverse-i1-04 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer 'tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled[normal-close]' --tb=short
```

JUnit SHA-256: 23e4ea5b62ccfce4098a768c7e28afa23aee7deecd17ec9d0a94481c3ad23ca5

### task3-fix1-restore-i1-05

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-restore-i1-05 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer 'tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled[normal-close]' --tb=short
```

JUnit SHA-256: 0ce39f7d573c4ec80401461693767d6227a639c28b5b6a5acbc5e296bda92793

### task3-fix1-inverse-i2-unshielded-06

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-inverse-i2-unshielded-06 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled --tb=short
```

JUnit SHA-256: 7ec5fefd3a8743259f75cd50ae8c935bc8dfa33619557df3019de1c200722d06

### task3-fix1-restore-i2-07

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-restore-i2-07 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled --tb=short
```

JUnit SHA-256: 45001577d103b4b7b4828e89a6ffb1e9b96cab6e844e2407fbf400ed0bc8e734

### task3-fix1-inverse-i2-detached-08

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-inverse-i2-detached-08 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled --tb=short
```

JUnit SHA-256: fedcf0e0b354b536e05f49233463b889f8c098f2d47f1ac6eaa54963803dcbd2

### task3-fix1-restore-review-probes-09

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-restore-review-probes-09 backend -q tests/test_research_output_events.py::test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer tests/test_research_output_lifetimes.py::test_chatgpt_terminal_cleanup_is_owned_until_settled .superpowers/sdd/2026-09-12-research-output-boundary/test_task_3_review_probe.py --tb=short
```

JUnit SHA-256: 1258ad4b2090b38d13b5397c4e7de8283bc3d0605065d0b7028bec480e570544

### task3-fix1-focused-final-10

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task3-fix1-focused-final-10 backend -q tests/test_research_output_events.py tests/test_research_output_lifetimes.py tests/test_tool_output_channels.py tests/test_task_runtime_binding.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_claude_agent_sdk_runtime.py tests/test_card_execution_authority.py tests/test_research_runs.py tests/test_research_routes.py tests/test_research_threads.py tests/test_subagent.py tests/test_server_compaction.py tests/test_replay_openai.py tests/test_openai_transport.py tests/test_openai_sync_surface_cleanup.py --tb=short
```

JUnit SHA-256: 2c5db9f944cfe46baa8a3b3fb28c03bcfe0c58fcb5ff72a0fdf8ea84d89c02e7

## Commit And Remaining Gates

Commit fdc947d22991703594715210eed917232cc38c55 contains only the four scoped files
listed above. Its parent is 29f18ca7364d04968d3273252b998e2a4fe32780. No docs,
coordinator catalog code/tests, Claude docstring, frontend artifacts or scratch
reports were staged. Only those unrelated coordinator changes remain dirty.

Exact staging/commit and verification commands:

```sh
git add -- src/auth_drivers/chatgpt_oauth_driver.py src/agents/shared/output_events.py tests/test_research_output_events.py tests/test_research_output_lifetimes.py
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git commit --only -m 'fix: own research cleanup through cancellation' -- src/auth_drivers/chatgpt_oauth_driver.py src/agents/shared/output_events.py tests/test_research_output_events.py tests/test_research_output_lifetimes.py
git log -1 --format='%H%n%P%n%s' --name-only
git status --short
```

All commands exited 0. The staged check showed exactly four authorized paths;
the commit reported 149 insertions and six deletions. No active git hooks were
present, and no test process remained running at handoff.

Independent Task 3 rereview and the coordinator's full-backend/final review remain
required. This report is not branch completion, merge approval, or a live-provider
validation claim. No providers, live credentials, production data, installation,
network, migration, merge, push, restart or subagents were used.
