# Task 2: Four-Channel Call-Bound Evidence Events

Read focused plan Task2/global constraints and task-2-context.md beside this file.
Work directly in /tmp/arkscope-research-output-boundary. No subagents.
Only write the four producer files, output_events.py and focused event/channel/
security tests. Task1 citation_event_fields helper is your input contract. Do not
edit API/store/reducer/UI modules (next tasks). Coordinate any helper issue with
controller; do not widen your write scope silently.

RED-first via this plan's run_checks.py NAME backend -q tests/... with unique
create-only names. No plain pytest, provider calls, credential reads or production
stores. Whole backend is controller-owned once at final. During your task you are
sole writer/test runner; controller does only unrelated source/acceptance reads.

Task1 provides validated whole result citations and typed gaps. Derive from
post-security pre-preview output. Add optional same call_id/start-end, end-only
input. Strict output_events vocabulary must explicitly admit/validate new fields;
exact-secret checking remains before every structured output. Invalid refs/gaps
cannot be passed as arbitrary metadata. Unknown event fields still fail closed.
Citation fields belong only to the three owned SEC tool names (with the exact
owned prefix normalization). A non-SEC tool cannot attach arbitrary SEC metadata.
Task1's CITATION_GAP_CODES and validate_citation are the field-shape authority;
sec_citation_gaps is a list of closed code strings, not free-form error objects.

OpenAI use real installed RunHooks + ToolContext metadata and execution-owned
queue while Runner.run is active. Completed SEC calls must reach parent before
a later cancel/error. SDK workers must be stopped and awaited, no late events after
aclose, no duplicate post-run calls. Preserve current retry criteria/count; call
identity must not collide if provider reuses an ID on a retry. Existing fake SDK
fixtures which do not exercise hooks may need raw-response fallback but production
completed hooks must not be silently deferred until final result.

Tests exercise actual producer loops with fake provider messages, not just helper
output. Include all four channels with equal full refs; actual Claude MCP text
blocks; source beyond preview length; completed OpenAI call then cancellation;
duplicate same-name calls; retained inputs; malformed evidence gaps; cancellation
and aclose suppress/await workers. Existing output boundary/selected auth/retry/
tracing owners remain green or must have a named transfer, not deleted assertions.

Commit owned files only; write task-2-report.md with RED/GREEN command receipts,
SDK contract references, exact event shapes, files, SHA and concerns. Controller
performs independent review. Return short status/SHA after self-review.
