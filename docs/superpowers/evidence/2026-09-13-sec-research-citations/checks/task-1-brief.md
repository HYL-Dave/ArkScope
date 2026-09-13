# Task 1: Validated References And Exact Reopening

Read focused plan Task1 and global constraints at
docs/superpowers/plans/2026-09-13-sec-research-citations.md and parent Task3 at
docs/superpowers/plans/2026-09-12-sec-research-release-integration.md:374.
Implement precisely those interfaces/closed union and exact closure/read rules.
Do not implement the profile iterator yet (Task3 owns it).

Workspace /tmp/arkscope-research-output-boundary. Only write citations.py,
references.py, sec_research API route and focused citation/reference/route-count
tests; do not change event producers or UI. No subagents. No actual providers,
credentials or production DB. Manual edits use apply_patch. Existing source
fixtures/stores are the test authority; no mocked exact-read verification.

Use RED-first; record commands and expected failures, then focused GREEN. Test
launcher (unique create-only NAME):
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py NAME backend -q tests/...
This supplies isolated DB paths, blocks network/credentials, and captures JUnit.
Do not invoke plain pytest. No other test runner will run while you own this task.
Do not run complete backend (controller runs once at end), broad SEC suites okay.

Shared event helper: citation_event_fields(tool_name,result) -> dict with optional
sec_citations list or sec_citation_gaps list of closed codes. Whole valid no-ref
SEC unavailable/empty envelopes are legitimate. Unknown tools yield {}. Invalid
owned evidence must be a typed gap, not swallowed. Derivation must consume actual
query shapes and pin every conflicting filing source variant. Bound source hashes,
JSON pointers, captured object bytes and document half-open UTF8 boundaries all
need verification on reopen. No arbitrary fetches. Consistent bounded canonical
query encoding functions should be reusable by route/frontend tests.

After self-review and focused tests, commit only owned files (not parent plan),
write full report with RED/GREEN receipts, public interfaces, closure format,
files and concerns to this task's task-1-report.md. Return short status + SHA.
