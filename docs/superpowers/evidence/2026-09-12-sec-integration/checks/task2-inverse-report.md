# Task 2 Bounded Inverse Verification

Workspace: `/tmp/arkscope-research-output-boundary`

Branch: `codex/sec-research-integration`

Frozen HEAD, checked before and after: `885c2a2d19065e37bfba492c0e6b75b17f30ed06`

Supplemental status: **eight inverse runs, 24 expected failures, 25 passes,
zero skips or setup/teardown failures**. Latest fresh unmutated union GREEN:
**30 passed**, exit 0. See the [supplemental required-tool addendum](#supplemental-required-tool-inverse).
The original seven-mode batch below is preserved without relabeling its runs.

Scope: the seven process-local inverses required by
`docs/superpowers/plans/2026-09-12-sec-research-release-integration.md:354`.
No product, test, index, central runner, plan, or other report edits. No complete
backend rerun, census, C10 review, agents, provider calls, installs, or service
actions. The controller's active full-backend process was not touched.

## Result

All seven mutants were detected by the existing named behavioral owners. Across
seven inverse runs: **22 failed, 20 passed, 0 skipped, 0 setup/teardown failures**.
All 42 selected items were called with their original bodies and assertions.
There is no missing named failure to waive for these seven modes.

Fresh unmutated restored GREEN: **30 passed, 0 failed, 0 skipped**, exit 0,
5.25 seconds pytest time / 6.235 seconds runner time. This is the complete union
of the selected inverse owners and controls, not the full Task 2 collateral
suite or complete backend acceptance.

Initial unmutated baseline: **27 passed, 0 failed, 0 skipped**, exit 0,
31.11 seconds pytest time / 31.938 seconds runner time. The restored run also
included the three existing actual-subagent inventory/registry controls.

## Mutation Boundaries

`task2_inverse.py` follows the admitted `c09_inverse.py` pattern: a pytest plugin
launched by `runpy.run_path(offline_pytest.py, run_name="__main__")`. All product
imports and injections occur in `pytest_runtest_call`, after the unchanged
offline launcher has installed its audit hook and configured disposable paths.
No product module is imported by the plugin before that hook is installed.

AST mutations compile inspected function source and replace only its `__code__`
in this process. They preserve existing function identities, imported aliases,
globals, defaults, annotations, and the original future-annotations flag. Each
rewrite requires exactly one matching boundary. No source module is re-executed.

| Mode | Actual boundary mutation | Actual failures | Passing controls |
| --- | --- | ---: | ---: |
| `omit-openai` | Remove only `sec_function_tool(list_sec_filings)` from `src/agents/openai_agent/tools.py::create_openai_tools`'s tool list. | 1 | 3 |
| `omit-anthropic` | Exclude only `list_sec_filings` from the actual SEC registry schemas appended by `src/agents/anthropic_agent/tools.py::get_anthropic_tools`. | 1 | 3 |
| `omit-chatgpt` | Remove only `list_sec_filings` from `src/auth_drivers/chatgpt_oauth_driver.py::_RESEARCH_READONLY_TOOLS`. | 1 | 3 |
| `omit-claude` | Remove only `list_sec_filings` from `src/auth_drivers/claude_code_sdk_driver.py::_RESEARCH_READONLY_TOOLS`. | 1 | 3 |
| `generic-truncation` | In `src/agents/shared/compressor/reducers.py::get_reducer`, select the existing `truncate_with_marker` for SEC names instead of `sec_result_reducer`. | 12 | 2 |
| `omit-worker-join` | In `src/sec_research/tool_execution.py::invoke_sec_tool`, remove the cancellation handler's `while not future.done()` wait and following `future.result()`. Keep stop signalling, worker/service execution, cancellation propagation, timeout result, and executor shutdown unchanged. | 5 | 0 |
| `omit-subagent-guard` | Remove only the `require_sec_inventory(...)` call from `src/agents/shared/subagent.py::_filter_openai_tools`. Leave filtering, the Anthropic guard, shared inventory validator, and actual subagent specifications intact. | 1 | 6 |

Actual dispatch/acquisition fixtures were retained. The plugin never replaces
test helpers, expected results, ToolService, stores, serialization, or readers.
OpenAI and Anthropic omissions are caught at their real inventory boundaries;
the OAuth omissions are caught by real dispatch vetoes. The generic reducer is
the existing product implementation, not a fabricated malformed response.

## Exact Failing Owners

In `tests/test_sec_research_tool_adapters.py`:

| Mode | Existing owner | Observed failure |
| --- | --- | --- |
| `omit-openai` | `test_each_research_transport_dispatches_three_real_sec_tools[openai]` | Line 41: `AssertionError: OpenAI inventory missing list_sec_filings`. |
| `omit-anthropic` | `test_each_research_transport_dispatches_three_real_sec_tools[anthropic]` | Line 48: `AssertionError: Anthropic inventory missing list_sec_filings`. |
| `omit-chatgpt` | `test_each_research_transport_dispatches_three_real_sec_tools[chatgpt]` | Line 54: `assert ok, result`; actual result is `invalid_value: tool is not allowed (allowlist veto)`. |
| `omit-claude` | `test_each_research_transport_dispatches_three_real_sec_tools[claude]` | Line 59: `assert not result["is_error"], result`; actual result has `is_error=True` and the allowlist veto. |
| `omit-subagent-guard` | `test_required_sec_omission_is_explicit[openai]` | Line 111: `Failed: DID NOT RAISE <class 'ValueError'>`. |

Each transport run selects all four channel parameters. Exactly the named
channel fails; the other three run the original real service and pass.

`generic-truncation` has these **12** failures:

- `tests/test_sec_research_tool_results.py::test_sec_pages_remain_complete_json_through_bridge_reduction`: all six existing parameters, `[malformed-list_sec_filings]`, `[malformed-get_sec_financial_facts]`, `[malformed-read_sec_filing]`, `[oversized-list_sec_filings]`, `[oversized-get_sec_financial_facts]`, `[oversized-read_sec_filing]`. All fail in the existing `unwrap`/`json.loads` boundary with `JSONDecodeError`; oversized input contains an invalid control character after head/tail truncation.
- `tests/test_sec_research_tool_results.py::test_sec_layers_select_whole_envelope_reduction`: `[oversized-layer0]`, `[oversized-layer5]`, `[malformed-layer5]` fail with `JSONDecodeError`; `[malformed-layer0]` fails the existing line 129 `assert record is not None`. Both `[complete-layer0]` and `[complete-layer5]` pass over real stored SEC envelopes.
- `tests/test_sec_research_tool_adapters.py::test_oauth_sec_boundary_rejects_serialization_corruption[chatgpt]` and `[claude]`: both fail with `JSONDecodeError` at the existing whole-envelope decode after actual service invocation and bridge reduction. The existing serialization-corruption fixture is unchanged.

These are actual JSON-boundary failures, not all `AssertionError`s. No assertion
was injected or altered to force them.

`omit-worker-join` has these **5** failures in
`tests/test_sec_research_tool_results.py`:

- `test_sec_cancel_awaits_worker_and_prevents_later_dispatch[cancel]` and `[timeout]`: line 99, `AssertionError: SEC returned before its owned worker completed`.
- `test_sec_cancel_stops_actual_document_reader_before_next_source[cancel]`, `[timeout]`, and `[repeat_cancel]`: line 180, `AssertionError: returned before document worker completed`.

The subagent run also passes the unchanged Anthropic required-omission owner,
both optional non-SEC omission parameters,
`tests/test_subagent.py::test_all_subagent_tool_names_exist_in_registry`, and
both parameters of `test_required_sec_tools_survive_actual_subagent_inventory`.

## Restoration And Admission

The call-hook `finally` restores every changed process attribute by original
object identity after each item, before fixture teardown. All seven evidence
files report `all_items_restored=true`, `all_collected_called=true`,
`pytest_main_restored=true`, zero remaining patches/pools, and zero skipped
reports. Every setup and teardown report passed. The plugin does not deselect,
skip, xfail, replace, or reclassify any test or its outcome.

For the join inverse, a transparent factory records the actual single-worker
SEC executors. After the original behavioral assertion has run, teardown calls
their real `shutdown(wait=True, cancel_futures=True)` before fixture cleanup.
All **five actual worker pools and five threads were reaped**, one per item;
each item records **zero owned threads alive**. Both the worker function code
and executor factory are restored per item. This cleanup is outside the
assertion and does not hide the early-return fault.

Only the specified interpreter and `run_checks.py` modes were used for Python
execution. The central runner's exact closed environment, original
`offline_pytest.py`, audit hook, `-B`, disabled pytest autoload/cache, explicit
AnyIO plugin, disposable fixture paths, and network/private-data restrictions
were retained. The audit hook remains installed throughout each process.

A scoped `git diff --exit-code HEAD --` check of the eight inspected runtime
boundary files and five selected test/fixture files exited 0 with no diff.
HEAD remained frozen. No on-disk source mutation or index write occurred.

## Run Evidence

All folders below are siblings of this report. Each contains the central
runner's exact `command.json` (command, environment, exit status, duration),
`output.log`, and `results.xml`. Each inverse also contains
`task2-inverse.json` with all collected node IDs, unchanged call failures,
per-item restoration, worker cleanup, and setup/call/teardown outcomes.

| Run folder | Launcher mode / fault mode | Result |
| --- | --- | --- |
| [task2-inv-885c2a2d-baseline-01](task2-inv-885c2a2d-baseline-01/command.json) | `backend` | 27 passed; exit 0 |
| [task2-inv-885c2a2d-openai-01](task2-inv-885c2a2d-openai-01/command.json) | `backend-task2-inverse omit-openai` | 1 failed, 3 passed; exit 1 |
| [task2-inv-885c2a2d-anthropic-01](task2-inv-885c2a2d-anthropic-01/command.json) | `backend-task2-inverse omit-anthropic` | 1 failed, 3 passed; exit 1 |
| [task2-inv-885c2a2d-chatgpt-01](task2-inv-885c2a2d-chatgpt-01/command.json) | `backend-task2-inverse omit-chatgpt` | 1 failed, 3 passed; exit 1 |
| [task2-inv-885c2a2d-claude-01](task2-inv-885c2a2d-claude-01/command.json) | `backend-task2-inverse omit-claude` | 1 failed, 3 passed; exit 1 |
| [task2-inv-885c2a2d-truncation-01](task2-inv-885c2a2d-truncation-01/command.json) | `backend-task2-inverse generic-truncation` | 12 failed, 2 passed; exit 1 |
| [task2-inv-885c2a2d-join-01](task2-inv-885c2a2d-join-01/command.json) | `backend-task2-inverse omit-worker-join` | 5 failed; exit 1 |
| [task2-inv-885c2a2d-subagent-01](task2-inv-885c2a2d-subagent-01/command.json) | `backend-task2-inverse omit-subagent-guard` | 1 failed, 6 passed; exit 1 |
| [task2-inv-885c2a2d-restored-green-01](task2-inv-885c2a2d-restored-green-01/command.json) | `backend` | 30 passed; exit 0 |

Exact invocation form used, with fresh run names and existing node IDs:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py UNIQUE backend-task2-inverse MODE -q EXISTING_NODE...
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py UNIQUE backend -q EXISTING_NODE...
```

The exact node arguments for every invocation are preserved in its linked
`command.json`; the restored GREEN has all ten selected owner functions and
their 30 original parameterized items.

All nine runner invocations and all tool sessions owned by this worker have
finished. Full-backend acceptance and census remain with the controller; C10
remains with the independent reviewer.

## Supplemental Required-Tool Inverse

Controller follow-up distinguishes the plan's literal removal of a required
subagent tool from the original `omit-subagent-guard` mode, which removed a
filter's validation call. This supplement checks the actual specification;
it does not rename, rerun, or reinterpret the original seven inverse runs.

New mode: `omit-subagent-required-tool`.

Mutation: in the existing pytest call hook, replace only
`src.agents.shared.subagent.SUBAGENT_REGISTRY["deep_researcher"].tool_names`
with a new list excluding `list_sec_filings`. Require exactly one occurrence
before injection. The original list is never modified, and the existing
identity-checked restoration reattaches that exact original list after each
item. Both filter guards, provider inventories, test bodies, and fixtures remain
unchanged. Product imports still occur only after the admitted offline audit
hook is installed.

Actual result: **2 failed, 5 passed, 0 skipped**, exit 1, 0.85 seconds pytest
time / 1.255 seconds runner time.

| Existing failing owner | Actual behavioral assertion | Failures |
| --- | --- | ---: |
| `tests/test_subagent.py::test_required_sec_tools_survive_actual_subagent_inventory[openai]` | Line 59: `assert set(NAMES) <= set(spec.tool_names)`; missing member is `list_sec_filings`. | 1 |
| `tests/test_subagent.py::test_required_sec_tools_survive_actual_subagent_inventory[anthropic]` | Line 59: the same required-subset assertion, also naming `list_sec_filings`. | 1 |

Both failures occur at the original specification-subset assertion before
channel filtering, exactly the boundary this supplemental mutation targets.
Neither failure is a plugin assertion or inventory mock.

Five unchanged controls pass under the same mutation:

- `tests/test_sec_research_tool_adapters.py::test_non_sec_optional_omission_keeps_existing_semantics[openai]` and `[anthropic]`.
- `tests/test_subagent.py::test_all_subagent_tool_names_exist_in_registry`.
- `tests/test_sec_research_tool_adapters.py::test_required_sec_omission_is_explicit[openai]` and `[anthropic]`, confirming both required-tool guards remain active.

All seven collected items were called. Per-item `restored_attributes=1` and
`restored=true` verify the original list identity after every item. The evidence
also records `all_items_restored=true`, `all_collected_called=true`,
`pytest_main_restored=true`, zero remaining patches/pools, zero live owned
threads, and no setup/teardown failures. No cancellation workers were created
by this supplemental mode.

Fresh unmutated `backend` union GREEN afterward: **30 passed, 0 failed,
0 skipped**, exit 0, 5.65 seconds pytest time / 6.516 seconds runner time.
The supplemental owners and controls already belong to the previous 30-item
union, so its ten owner functions and all original parameters were run again
without loading the mutation plugin.

| Supplemental run folder | Launcher mode / fault mode | Result |
| --- | --- | --- |
| [task2-inv-885c2a2d-subagent-required-tool-01](task2-inv-885c2a2d-subagent-required-tool-01/command.json) | `backend-task2-inverse omit-subagent-required-tool` | 2 failed, 5 passed; exit 1 |
| [task2-inv-885c2a2d-supplement-restored-green-01](task2-inv-885c2a2d-supplement-restored-green-01/command.json) | `backend` | 30 passed; exit 0 |

Both new run folders retain `command.json`, `output.log`, and `results.xml`.
The supplemental inverse's [task2-inverse.json](task2-inv-885c2a2d-subagent-required-tool-01/task2-inverse.json)
contains exact node IDs, original failure text, all phase outcomes, and identity
restoration evidence for the controller's archiver.

Cumulative inverse total, keeping the original seven-run batch separate:
**8 modes/runs, 49 test-item calls, 24 expected failures, 25 passes, zero skips
or setup/teardown failures**. All eight modes have their named behavioral
failures; no missing failure was waived.

The scoped runtime/test `git diff --exit-code HEAD --` check remained empty and
HEAD remained `885c2a2d19065e37bfba492c0e6b75b17f30ed06`. Only the same scratch
plugin/report and two new owned run folders were written for this supplement.
No product/test/index, central runner, full-backend process, census, C10, or
other report changes occurred. All **11** runner invocations, including these
two supplemental invocations, and every session owned by this worker have
finished. Archiving and complete-backend acceptance remain with the controller.
