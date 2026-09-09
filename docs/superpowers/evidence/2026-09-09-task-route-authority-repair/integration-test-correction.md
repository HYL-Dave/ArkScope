# Task 4 Integration-Test Correction Report

## Status

The bounded test correction is complete and committed. Awaiting controller
review; final integration, review, mutation verification, and evidence assembly
remain controller-owned.

- Worktree: `/tmp/arkscope-task-route-authority`
- Branch: `codex/task-route-authority`
- Base/commit parent: `c5146a9a581f7e81ee5890a109e3f9ae81047ce9`
- Commit: `090a72258e76f84367c886da0e41ae79e181d2c0`
- Commit subject: `test(events): align custom Anthropic effort forwarding`
- Committed scope: only `tests/test_events.py`, 21 insertions and 3 deletions.
- This report is not staged or committed. The existing
  `.superpowers/sdd/.gitignore` excludes it; it remains an untracked local file.

The integration-fix brief was read first. Tasks 1-3 were not reimplemented or
re-reviewed.

## Exact Contract Correction

Replaced `TestAnthropicStream.test_no_effort_for_unsupported_model` with
`test_custom_model_forwards_exact_requested_effort`. The obsolete owner treated
the unregistered synthetic ID `claude-nova-1-20260501` as known not to support
effort and required omission of `output_config`.

The corrected owner exercises the existing `run_query_stream` implementation
with the selected custom model and `effort="medium"`, then asserts:

- Exactly one `client.messages.stream` request.
- Literal request model `claude-nova-1-20260501`.
- Exact `output_config == {"effort": "medium"}`.

The supported-model positive control `test_effort_kwarg_passed` remains
unchanged. The existing real-SDK wire owner
`tests/test_task_runtime_binding.py::test_anthropic_custom_and_supported_effort_reaches_messages_wire`
also remains unchanged and passed in the focused set for both parameter cases.

Preserved distinct known-model/no-effort behavior in
`test_no_effort_for_known_model_without_effort_support`, using the real registry
entry `claude-haiku-4-5`, whose `effort_options` is empty. It asserts one stream
request, that literal model, and absence of `output_config`. No synthetic
capability entry, registry patch, or runtime guard mutation was used. This is
direct-agent coverage, not a relaxation of task admission.

No runtime contract changed: custom requests retain their requested effort;
provider rejection remains possible, and known retired/unsupported task
combinations retain their existing admission behavior.

## RED Before Editing

Ran from the worktree before any manual file edit:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_events.py --tb=short
```

Exit 1: **1 failed, 19 passed, 1 error in 3.23s**.

- Expected failure: `TestAnthropicStream.test_no_effort_for_unsupported_model`,
  at the assertion requiring `output_config` to be absent. The actual request
  contained model `claude-nova-1-20260501` and
  `output_config={"effort": "medium"}`.
- Separate pre-existing error: setup of
  `TestSSEEndpoint.test_stream_bad_provider` raised
  `RuntimeError: There is no current event loop in thread 'MainThread'.`
  The stack passed through `create_app`, portfolio/IBKR imports, and
  `eventkit.util` calling `asyncio.get_event_loop_policy().get_event_loop()`.

## GREEN Focused Set

Ran the complete required set together, with no `-k`, skips, or deselection:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_events.py tests/test_task_runtime_binding.py tests/test_model_routing.py tests/test_model_task_test.py tests/test_lifecycle_investigation_routing.py --tb=short
```

- First post-edit run: exit 0, **289 passed in 9.97s**.
- Final pre-commit run: exit 0, **289 passed in 10.08s**.
- No failures, errors, skips, deselections, or warnings were reported in either
  focused run. The SSE endpoint test passed in this combined set.
- `git diff --check -- tests/test_events.py` and
  `git diff --cached --check` both passed before commit.
- Commit inspection confirmed only `tests/test_events.py` was committed and
  the commit parent is the specified base.

Every backend invocation used the mandated offline wrapper. Each reported only
loopback networking, `external_probe: ENETUNREACH`, and
`inherited_credentials: false`.

## Concrete Concerns and Boundaries

A supplemental post-edit run of the same standalone `tests/test_events.py`
command exited 1 with **21 passed, 1 error in 3.28s**. The obsolete effort
failure is gone, but the same SSE/eventkit event-loop setup error persists when
this file is run alone. Its absence from both combined runs suggests an
import-order dependency; that cause was not fully investigated. No out-of-scope
fixture, dependency, or implementation changes were made to conceal it.

All manual edits used `apply_patch`. Runtime implementation, capability
registry, and runtime guards were untouched. No test was deleted or skipped.
No provider calls, production stores, production tokens/keys, config/.env,
credential inspection, App restart, subagents, reviewers, merge, or push were
used. Tests used the existing synthetic fixtures under the offline wrapper.

Controller-owned docs, README, plan, evidence, and other task artifacts were
not edited, staged, or restored, including additional controller work observed
during execution. No new whole-backend run or mutation verification was
performed; those remain controller-owned.
