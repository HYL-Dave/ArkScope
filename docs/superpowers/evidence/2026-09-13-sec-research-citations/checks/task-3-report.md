# Task 3 Report

Complete; ready for parent independent review and acceptance.
Commit: `8c9ee301e6fabcc02105be0eb2b4f2ad30ba81a7`
Base: approved Task 2 `35f2d7208d12f12fe846f4f453614cfee5eb9656`.
Worktree: `/tmp/arkscope-research-output-boundary`, branch `codex/sec-research-integration`.

## Interfaces

`src.research_tool_trace.accumulate_tool_calls(events, *, tool_calls=None)` accepts
an iterable of `(type, data)` events; `query.accumulate_tool_calls` re-exports it.
Rows retain `name`, `input`, `result_preview` and present optional `call_id`,
`sec_citations`, `sec_citation_gaps`. Returned nested data is copied.
Only one owned `mcp__ark__` then `tool_` prefix is removed from names.
Exact IDs pair starts/ends; first completion wins on replay. ID-less calls retain
last-open legacy pairing only with other ID-less calls. End-only input survives.
Recovery supplements durable rows with caller-only/missing fields, never replaces
present durable evidence. Anonymous reconciliation matches name/input occurrences
once each, never an ID-bearing row; missing caller IDs are not guessed.

`ResearchRunStore._terminalize_error_on_connection` reads every durable tool event
using its existing connection/transaction, including when a partial trace is
supplied. Restart and no-task cancellation use this same atomic boundary.
The public replay API remains bounded; its default 500-event page is unchanged.
All fields stay in existing event/message JSON. Prompt history remains strictly
role/content-only. No Research schema, producer, UI, research route or manager edits.

`references.iter_research_sec_citations(profile_connection) -> Iterator[dict]`
requires explicit `PRAGMA query_only=ON`, even for a read-only URI. The caller owns
the connection/read snapshot. It scans all message and event roots without joins
to active threads, including archived/interrupted/event-only evidence.
SQL NULL optional trace and absent citation fields are valid; malformed present
JSON/refs/gaps raise `CitationError`. Nonempty citation gaps fail closed.
Duplicate JSON keys and nonfinite JSON constants are rejected. Prose/preview is
never parsed. The iterator composes with Task 1's unchanged reference closure.

## Actual Receipts

Every run used this plan's create-only `run_checks.py NAME backend -q tests/...`.
Each NAME directory contains exact argv/environment in `command.json`, complete
`output.log`, and `results.xml`. One runner at a time; no mutation runs performed.

| NAME | Actual result |
| --- | --- |
| `task3-baseline-01` | 160 passed; existing persistence/history/reference owners. |
| `task3-red-01` | 46 failed / 70 passed; lost metadata, wrong pairing, missing recovery/iterator. |
| `task3-lifecycle-red-01` | 4 failed; conflicting partial trace and executor success/error/cancel metadata loss. |
| `task3-green-01` | 264 passed; all new owners plus existing persistence/history owners. |
| `task3-final-green-01` | **772 passed**, pytest 76.00s, runner 77.371s; exact committed product/test source. |

Final selection: `test_sec_research_trace.py`, `test_sec_research_references.py`,
`test_sec_research_citations.py`, `test_research_routes.py`, `test_research_runs.py`,
`test_research_threads.py`, `test_research_history.py`, `test_research_output_events.py`,
`test_research_output_lifetimes.py`. This is not the full backend suite.
`git diff --check` and staged diff check passed; tracked worktree is clean.

## Parent Inverse Owners

| Inverse | Exact node ID | Implementation location |
| --- | --- | --- |
| Optional projection | `tests/test_sec_research_trace.py::test_sec_citations_roundtrip_event_message_and_legacy_rows` | `src/research_tool_trace.py:36`, `:46` optional field projection. |
| Wrong call_id | `tests/test_sec_research_trace.py::test_sec_tool_end_preserves_whole_citations_by_call_id` | `src/research_tool_trace.py:27` exact lookup; `:40` replay guard. |
| Event-only roots | `tests/test_sec_research_references.py::test_profile_iterator_enumerates_message_and_event_only_roots` | `src/sec_research/references.py:53` event-root enumeration. |
| First 500 / restart | `tests/test_sec_research_trace.py::test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls[restart]` | `src/research_runs.py:442` transaction-local unbounded cursor. |
| First 500 / cancellation | `tests/test_sec_research_trace.py::test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls[no-task-cancel]` | Same atomic boundary, 602 durable events with the only ref in event 602. |

Additional new owners cover ID-less mixing/replay, partial caller reconciliation,
uncommitted-event visibility and rollback, real executor terminal/archive paths,
query-only enforcement, malformed roots and gaps. 50 new cases across the two
focused test files; existing Task 1/2 test bodies were not changed.

## Handoff

Committed only query.py, research_runs.py, new research_tool_trace.py,
references.py and the two focused test files. Report/receipts remain in this
ignored scratch directory for the parent's evidence archive, matching Tasks 1/2.
No unresolved findings or test failures identified in self-review. Parent-owned
independent review, five inverses, full suite and browser acceptance remain open;
the parent's fixture_setup02 relocation result is not claimed as this task's run.
No subagents, live provider/configuration/credential/production-store access,
deletion, merge or push. Product/index/test-runner ownership is handed back now.
