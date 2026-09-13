# Task 2 Report

Complete; ready for parent independent review.
Commit: `35f2d7208d12f12fe846f4f453614cfee5eb9656`
Base: approved Task 1 `89509a31`. Existing worktree retained; tracked tree clean.

## Event Shapes

All starts: `{tool, input: object, call_id: string}` when an ID exists.
All completed ends retain input independently of start-event consumption.
`C` below means optional `sec_citations: Citation[]` OR
`sec_citation_gaps: CitationGapCode[]`, projected by Task 1's helper.
Valid results without references and non-SEC tools omit both fields.

| Flow | End data | Identity / projection point |
| --- | --- | --- |
| OpenAI API | `{tool, call_id, input, summary, chars, ...C}` | ToolContext name/arguments; ID `openai:<zero-based-attempt>:<provider-id>`; whole admitted hook result before 200-character preview. |
| Anthropic API | `{tool, call_id, input, summary, chars, ...C}` | ToolUseBlock.id on both events; whole admitted output BEFORE Layer 0 compression and 200-character preview. |
| ChatGPT OAuth | `{tool, call_id, input, summary, chars, is_error, ...C}` | Parsed function-call ID on both events; whole admitted reduced result before existing summary cap. Error flag retained in the shared parser input. |
| Claude OAuth | `{tool, call_id?, input?, summary, chars, is_error?, ...C}` | ToolUseBlock.id / ToolResultBlock.tool_use_id; per-execution name/input maps; actual MCP text-block content admitted before citation parsing or JSON preview conversion. Input present when known from the call map. |

Owned prefixes remain exactly Task 1's `tool_` and `mcp__ark__` normalization.
Malformed owned results produce `sec_citation_gaps: ["sec_citation_result_invalid"]`.
The public event boundary validates references with `validate_citation`, gaps with
`CITATION_GAP_CODES`, and ownership through the narrow new
`validate_citation_event_fields` helper. Exact-secret admission happens first;
unknown event fields and unowned SEC metadata remain rejected.

## OpenAI Lifetime

An attempt-owned queue drains while the real Runner is active, including queued
completions before a later runner error. Cancellation/aclose disables publication,
cancels and awaits the same worker through repeated cancellation. Tests cover
late cleanup publication, real SDK HTTP-followup cancellation, and end-only input.
Completed hook events deduplicate by exact provider call ID within an attempt;
attempt-prefixed public IDs prevent collisions when retries reuse provider IDs.
Retry predicate/count remain `No tool output found`, at most two attempts.

Per the user's refinement, NO production post-run event fallback remains.
Existing raw-response extraction remains unchanged for diagnostic/replay/usage
duties. No hookless tool family was used to justify a fallback. The exploratory
fallback test was replaced by an end-hook owner, including duplicate raw results.

Installed SDK sources verified locally (SHA256s match the supplied context):

| Source under `.../site-packages/agents/` | Contract | SHA256 |
| --- | --- | --- |
| `lifecycle.py:70,85,203` | async start/end hooks; RunHooks is a generic alias | `5bbf13d8390ddad8a2678351919068230b8cdfb943001e387f894500cf94d4bd` |
| `tool_context.py:45-51` | tool_name, tool_call_id, tool_arguments | `bfc613da331f13f9fd58b7dd84c7098bec43d6227e856bedf935f5be680a1303` |
| `run_internal/tool_execution.py:2033,2169` | invokes hooks with ToolContext; end after output commit | `86b91c62df0779e896143e5bc841a962d436099d79365497377dd9a233b02946` |

## Receipts

All commands used this plan's create-only isolated `run_checks.py NAME backend -q ...`.
Each named directory beside this report contains exact argv/environment in
`command.json`, full `output.log`, and JUnit `results.xml`. No overlapping runners.

| Receipt NAME | Result / interpretation |
| --- | --- |
| `task2-red-01` | 27 failed / 12 passed; includes incorrect Anthropic fixture patch target. |
| `task2-red-02` | Corrected RED: 26 failed / 13 passed, missing IDs/refs/live hooks. |
| `task2-fallback-red-01` | 1 failed, missing end input; exploratory fallback owner later superseded per user refinement. |
| `task2-green-01` | 36 passed / 4 failed; fixture incorrectly used isinstance against generic RunHooks alias. |
| `task2-hooks-red-02` | Corrected hook owners: 4 failed with hook installation deliberately disconnected; restored afterward. |
| `task2-green-02` | 40 passed; hook-only implementation. |
| `task2-regression-01` | 1145 passed / 2 failed; existing ChatGPT exact start assertions needed the new call_id. |
| `task2-edge-red-01` | 51 passed / 2 failed; ChatGPT error-marked evidence plus a misplaced test assertion. |
| `task2-edge-red-02` | 3 passed / 2 failed; ChatGPT error evidence and deliberate exact-ID dedup inverse; fixture corrected. |
| `task2-edge-green-01` | 101 passed, trace and ChatGPT owners. |
| `task2-final-green-01` | **1164 passed**, 78.77s; final unmodified code/test source. |

Final selection: trace, citations, native SEC dispatch, SEC adapters/output
integration, output boundary, research output events/lifetimes/compaction, tool
output channels, task runtime binding, events, agents, both OAuth driver owners,
and OpenAI sync-surface cleanup. This is NOT the full backend suite.
`git diff --check` passed before the scoped commit.

## Files And Handoff

Committed: the four producer files, `src/agents/shared/output_events.py`,
`src/sec_research/citations.py`, new `tests/test_sec_research_trace.py` (54 cases),
and `tests/test_chatgpt_oauth_driver.py` (two exact assertions extended, none removed).
Report and receipts remain in the plan's ignored scratch directory for the
controller's evidence archive, consistent with the existing Task 1 handoff.

No unresolved Task 2 test failures found in self-review. SDK/auth/tracing/retry,
security admission, and existing output owners remain green. No subagents,
provider calls, production stores, configuration/credential reads, merge or push.
Independent review, full-backend verification, durable API/store/reducer/UI work,
and browser acceptance remain with the parent and subsequent tasks; none claimed here.
