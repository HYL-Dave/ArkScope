# Durable SEC Research Citations

> Execution: subagent-driven development, sequential writers and test runners.

Status: implementation and acceptance complete through `5235705c`. This completes Task 3 of
`2026-09-12-sec-research-release-integration.md`; it does not reopen the accepted
tool wiring, output boundary or TOC work. Authority is
`../specs/2026-09-10-sec-research-substrate-design.md` and that plan's complete
Task 3 contract. Source baseline: `ca49b454` on
`codex/sec-research-integration` in the existing isolated worktree.

## Outcome And Constraints

A completed SEC tool result must remain a reproducible source after cancellation,
restart, another refresh and relocation of the market DB/capture directory.
Research shows concise saved references and reopens the exact retained fact,
filing observation or UTF-8 passage. A preview is never a citation authority.

- Preserve the six-field SEC envelopes, current security admission, authentication,
  model routing, tool limits, Decimal TEXT and immutable source bindings.
- Persist optional trace fields in existing JSON; no new Research table or schema
  upgrade chain. Legacy rows without citations remain readable.
- No production DB, configuration, token or provider access; no real cleanup,
  restart, installation, merge or push. Test with temporary stores and offline
  provider messages. Do not change the system SQLite installation.
- Cleanup/reset still require parent Tasks 5/6 (operation leases and export).
  These tasks gain a concrete reference-closure interface here, not permission to
  delete. SQLite activation retains its separate admission/preflight checkpoint.
- Run one writer/test program at a time. Full-suite source is frozen; no concurrent
  pytest, census, mutation, browser or source writes during that run.

## Task 1: Validated References And Exact Reopening

Create `src/sec_research/citations.py` and `references.py`; modify only the thin
`src/api/routes/sec_research.py` adapter and relevant route-count collateral.
Tests: new `tests/test_sec_research_citations.py`,
`tests/test_sec_research_references.py`, existing SEC route owners as necessary.

Implement the parent plan's closed document/fact/filing unions and interfaces:
`validate_citation`, `sec_citations_from_envelope`, `sec_citations_from_result`,
`read_sec_citation`, `sec_reference_closure`. Parse whole admitted SEC outputs,
owned wrappers, plain JSON and actual MCP text blocks, never prose/preview.
Only normalize the owned `tool_` and `mcp__ark__` name prefixes. Unknown tools
produce no references. Malformed owned evidence raises a closed typed citation
error; provide a shared event projection helper which records the error in
optional `sec_citation_gaps` rather than silently returning no evidence.

Exact read verifies every retained binding against the original bytes and stored
metadata, not a latest query or supplied URL. A bounded canonical encoded JSON
reference drives GET `/sec-research/citation`, declared before the CIK route.
No source acquisition or arbitrary file/URL parameters. Return the standard
six-field envelope, with typed unavailable for missing/corrupt retained evidence.

Closure returns deterministic sorted capture/directory/snapshot/receipt/fact/
filing and object identities. Traverse receipt source_snapshots and all document
catalog sources. Missing or corrupt closure nodes fail explicitly. No deletions.
Process one bounded source at a time and retain compact identities, not all parsed
payloads. The approved adjustable100GiB store must not encounter a new small
cumulative byte/row ceiling. Exact reads verify their own binding, without
expanding unrelated receipt members; maintenance closure verifies all members.

RED owners include exact reopen after refresh/relocation, bound hash/pointer/
range tampering, invalid/extra fields, duplicate catalog provenance, MCP parsing,
canonical query rejection and retained directory/catalog/fact object closure.
Use actual stores and generated raw source bytes. Expected RED: missing validated
reference/reopen behavior, not a fixture/import accident. GREEN includes existing
document, query, capture and route suites. Review and commit this task.

## Task 2: Four-Channel Call-Bound Evidence Events

Modify `src/agents/openai_agent/agent.py`,
`src/agents/anthropic_agent/agent.py`,
`src/auth_drivers/chatgpt_oauth_driver.py`,
`src/auth_drivers/claude_code_sdk_driver.py`; focused tests in
`tests/test_sec_research_trace.py` and adapter/stream owners.
Extend `src/agents/shared/output_events.py`'s closed tool-end vocabulary with
input and the two citation fields, with explicit typed validation. Exact-secret
checks still precede projection; unknown fields still fail closed. Include its
existing security owners in focused verification.

Each start/end carries the same optional call_id; completed events include
references/gaps from whole post-security output before preview/Layer0 reduction.
Preserve end-only input. Claude handles actual MCP text blocks, not repr strings.
Do not move security admission after citation extraction.

Use the installed OpenAI SDK RunHooks.on_tool_start/on_tool_end contract and
ToolContext call metadata, verified from local SDK sources. Drain an execution-
owned queue while Runner.run is active; completed tools survive a later error or
cancel. No global collector, no late abandoned-worker publication, no duplicate
post-run events for already observed calls. Keep existing final summaries, retry,
tracing, structured output and selected-auth contracts intact.

RED owners: `test_completed_openai_sec_tool_survives_later_cancel`,
`test_four_channels_keep_whole_refs_and_call_inputs` (including actual Claude MCP
text blocks), four-channel whole
results with identical reference values, duplicate names and retained inputs,
typed malformed evidence. Test real producer loops with fake provider messages.
GREEN relevant native/OAuth research, output boundary, task authority and adapter
tests. Review and commit before proceeding.

## Task 3: Durable Trace, Recovery And Maintenance Roots

Modify `src/api/routes/query.py`, `src/research_runs.py`,
`src/api/routes/research.py`, `src/research_run_manager.py` only as needed;
use a focused `src/research_tool_trace.py` shared accumulator if needed to avoid
making the store import an API route;
extend `src/sec_research/references.py` with
`iter_research_sec_citations(profile_connection)`.
Tests: `test_sec_research_trace.py`, `test_sec_research_references.py`, research
route/run/thread owners. No profile schema change for optional JSON.

Pair call IDs exactly. ID-less legacy events retain legacy pairing without
capturing ID-bearing calls. Repeated names/reversed completions cannot exchange
refs; duplicate durable events cannot append another completed call. Retain
optional call_id/sec_citations/sec_citation_gaps through event, message, error,
cancel, interruption and archive paths. Recovery reconstructs all events rather
than the first page of 500. Prompt history remains role/content-only.

The iterator requires an explicitly query-only connection and enumerates retained
messages AND events, including cancelled/archived/event-only roots. Absent optional
fields are valid; malformed present references or recorded citation gaps fail
maintenance closed. No scanning assistant prose or preview.

RED owners: `test_sec_citations_roundtrip_event_message_and_legacy_rows`,
`test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls`,
`test_sec_tool_end_preserves_whole_citations_by_call_id`, duplicate names with
reversed completion, event-only roots and malformed retained JSON. GREEN existing
persistence/cancellation/history owners. Review and commit.

## Task 4: Research Source Reopening UI

Modify `apps/arkscope-web/src/api.ts`, `researchReducer.ts`,
`ResearchEvidenceDrawer.tsx`; add focused `SecCitationView.tsx` and tests;
update only owned styles and en/zh-Hant resources.

Expose typed optional trace references/gaps and `getSecResearchCitation(ref)`.
Match exact call IDs as on the backend and retain fields through finalization,
reload and cancellation. Evidence drawer presents concise source references and
plain-text exact observations/passages. Never render remote HTML. Show form/period
when actually available from stored evidence. Preserve existing legacy previews.
Provide close/focus restoration, selected-message guards, stale async-result
guards and actionable typed unavailable state. No nested decorative cards or
feature-explanation copy. Use existing icons/panel patterns.

RED reducer/drawer/view tests: reversed completions, reloaded refs, stale response,
message switch, text rendering, errors and focus restoration. GREEN frontend full,
typecheck, production build and `check:i18n-literals`. Browser verification uses a
real temporary API/store, not a stub citation response, across desktop/mobile:
open a retained UTF-8 passage after refresh and capture-root relocation.
Review and commit.

## Task 5: Acceptance And Handoff

Use the archived offline harness from `2026-09-13-maintenance-closures`; create
this plan's own scratch directory. Do not read another plan's scratch. Preserve
RED, GREEN, mutation failures and command receipts with exact source hashes.

Run inverses for lost optional fields, wrong call-ID matching, missing event-only
roots, ignored bound hashes and first-500 recovery. Each must fail its owner,
then restore source exactly. Broad independent review precedes frozen-source full
backend execution. Prior accepted baseline is **10311 passed / 12 skipped** from
`checks/backend-accepted-full/results.xml.gz`, not the prior rejected full run.
Reconcile actual collection IDs and source changes; do not predict totals.

Run census against ca49b454 after tests, classify new findings rather than claiming
exit 2 means clean. Record actual HTTP count collateral. Update the parent plan,
spec status and priority/cleanup owners to mark Task 3 complete only when its
entire chain passes. Explicitly retain Tasks 5/6 and SQLite activation as open.
Seal a tracked evidence archive, verify every manifest object from Git, commit
only this work, leave the integration branch and master separate. Delete only
this plan's disposable scratch after verification and retain the archive.

## Accepted Checkpoint

- [x] Tasks 1-4 implemented, committed and independently reviewed.
- [x] Final review's queued-completion cancellation P1 reproduced with two
  deterministic producer/executor/store failures, repaired in `dbc8f7e5` and
  independently approved. `test_queued_openai_completions_survive_executor_cancellation`
  covers ordinary and repeated cancellation before queue consumption; no late
  worker publication or security bypass. Focused709P.
- [x] Five named inverse modes kill their owners; restored16P. The first500
  inverse's initial launcher failure is retained separately, not called RED proof.
- [x] Full backend at `dbc8f7e5`:10583P/12 unchanged S, exact10595 collected and
  executed IDs,272added/zero removed. All1142 source paths, SDK/runtime and runner
  hashes remain unchanged through the single full run.
- [x] Final source differs only by removal of one ineffective CSS rule in
  `5235705c`; backend source/tests unchanged. Fresh frontend1824P/126files,
  typecheck/build/i18n pass. Existing act/build-size warnings remain disclosed.
- [x] Final actual temporary API/store browser: en/zh-Hant at1280/390, old UTF-8
  passage after refresh/root relocation, exact21digit fact, canonical Unicode
  pointer, missing-source retry, persisted reload and keyboard focus pass.
- [x] Final census:4330candidates/3469uncertainties/1158readfiles. Zero new
  candidates or coverage/dependency/untracked drift;151 new uncertainty IDs
  comprise145 mechanically matched position changes and6 reviewed new statements.
  Raw exit2/review_required remains; wider queues are not closed.
- [x] Handoff/collateral review approved; archive committed at `e20632e7` and
  verified from Git:278files, zero missing/extra/hash errors. Only this plan's
  disposable scratch removed after verification; branch/worktree retained.

Evidence and exact receipts:
`../evidence/2026-09-13-sec-research-citations/README.md`.
Task 3 now supplies the concrete retained-reference boundary required by parent
Tasks5/6. Operation leases/export, cleanup/reset, scheduling and SQLite activation
remain open; none was performed. Keep the integration branch, without merge/push.
