# Task 3: Durable Trace, Recovery And Maintenance Roots

Read focused plan Task3/global constraints and parent release Task3 contract.
Work directly in /tmp/arkscope-research-output-boundary. No subagents. Only write
query.py/research_runs.py/research route/run manager as needed, shared
research_tool_trace.py if needed, references.py profile iterator, and focused
trace/reference/research persistence tests. No event-producer/UI edits.

Use RED-first via this plan's run_checks.py NAME backend -q tests/..., create-only
run names. No plain pytest, live provider/credential/production store access.
Whole suite is controller-owned. Only you run tests during this task.

Optional metadata is call_id,sec_citations,sec_citation_gaps, plus end-only input.
ID-bearing completions match exact ID and cannot consume anonymous legacy calls.
ID-less events retain old behavior only with other ID-less calls. Repeated IDs
must not duplicate completed calls or exchange refs, repeated names/reversed ends
must pair correctly. Preserve known owned name normalization only.

Keep trace fields in existing JSON across success/error/cancel/restart/archive.
ResearchRunStore._terminalize_error_on_connection is the existing atomic terminal
boundary shared by restart and cancellation without task. When trace not supplied,
reconstruct all durable tool events on that SAME connection/transaction, not the
500-event public API page. Do not make public event responses unbounded. Explicit
caller-supplied partial trace must not silently overwrite durable completed refs.
Store/route should share one pure accumulator, not import each other or duplicate
logic. Existing prompt-history role/content-only contract must remain.

iter_research_sec_citations takes an explicitly query_only connection, enumerates
all message AND event roots (including archived/interrupted/event-only) and checks
strict JSON/reference/gap presence. No joins filtering to active threads. Absent
optional fields valid; malformed present data and nonempty citation gaps fail
maintenance closed. Never recover a ref from prose or preview. No deletions.

Named tests include full event-message-legacy roundtrip, >500 event restart and
no-task cancellation with cited last tool, reversed same-name IDs, ID-less mix,
duplicate event replay, error/cancel/archive persistence, query-only enforcement,
malformed roots and event-only roots. Use real temporary stores not mocked methods.
Commit owned files only, report RED/GREEN receipts and interfaces in task-3-report.md.
