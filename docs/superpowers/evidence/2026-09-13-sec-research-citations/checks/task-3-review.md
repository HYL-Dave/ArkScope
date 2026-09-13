# Task 3 Independent Spec And Code Quality Review

Verdict: **PASS / APPROVE** for focused Task 3. No actionable findings.

## Scope And Evidence
- Immutable range: `35f2d720..8c9ee301`; HEAD verified as `8c9ee301e6fabcc02105be0eb2b4f2ad30ba81a7`.
- Read `task3-review.diff` once, focused plan/global constraints, parent Task 3 contract, and completed `task-3-report.md`.
- Reviewed affected source, direct lifecycle callers, and focused test source. The six changed files match HEAD with no working-tree differences.
- Source-only: no tests, mutations, subagents, production/configuration/token/provider access, or source/git writes. This report is the only write.

## Contract Review
- `src/research_tool_trace.py:27`: exact call-ID lookup isolates identified calls from the anonymous last-open stack. Reversed same-name completions retain their own input/reference rows.
- `src/research_tool_trace.py:40`: first completion wins for repeated identified starts/ends; duplicate replay neither adds completed rows nor exchanges references. Anonymous legacy pairing deliberately has no invented replay identity.
- `src/research_tool_trace.py:33`: retains start/end-only input, call ID, preview and present citation/gap fields; owned-prefix normalization is bounded, and returned nested data is copied (`:53`).
- `src/research_tool_trace.py:56`: partial caller traces supplement missing fields and caller-only rows. Present durable references prevail; anonymous occurrence matching cannot consume identified rows.
- `src/research_runs.py:441`: recovery reads all durable tool events in sequence on the existing terminal transaction, including uncommitted events and events after 500. It does so even with caller-supplied traces.
- `src/research_runs.py:454`: terminal status, error event and linked message remain under the caller-owned commit/rollback boundary (`:514`). Public replay remains paginated (`:765`).
- `src/research_runs.py:799` and `src/api/routes/research.py:500`: restart and no-task cancellation use that boundary. Active cancellation supplies its trace through the same path (`src/research_run_manager.py:211`).
- `src/api/routes/query.py:288` and `:319`: success/error message persistence uses the shared projection. Executor collection retains durable events before terminal handling (`src/research_run_manager.py:162`).
- `src/research_threads.py:362` and `src/api/routes/research.py:151`: optional metadata remains in existing JSON and message responses; archive does not rewrite traces. History still constructs role/content-only dictionaries (`src/research_threads.py:105`).
- `src/sec_research/references.py:44`: requires explicit query_only, scans all message and event roots without active-thread filtering, and does not mine prose/previews. Caller ownership of the read snapshot is documented.
- `src/sec_research/references.py:48` and `:61`: strict JSON parsing, root shape checks, present-field validation and nonempty-gap rejection cover malformed/event-only/archived roots. SQL NULL trace and absent optional fields remain compatible.
- Store and route import one pure accumulator; no store-to-route dependency, duplicate projection, schema change or deletion was introduced.

## Corruption And Verification Limits
- Invalid present references, malformed retained roots (including duplicate keys/nonfinite constants), and recorded citation gaps blocking maintenance are approved fail-closed behavior, not Task 3 defects.
- Malformed durable tool JSON can abort recovery before terminal writes; this is not evidence of lost valid admitted events or a reason to silently discard corrupt evidence.
- Focused test source covers pairing/replay, lifecycle/archive retention, 602-event recovery, same-transaction visibility/rollback, partial reconciliation and strict iterator roots.
- The parent reports verifying the final 772-pass focused log; the implementer report agrees. I did not execute or independently certify that run.
- Parent-owned mutation/full-suite acceptance remains separate and pending for this review. Deferred UI/export/leases/subagent features are not treated as focused Task 3 defects.
