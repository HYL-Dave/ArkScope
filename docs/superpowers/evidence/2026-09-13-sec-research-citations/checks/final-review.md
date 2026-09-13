# Final Whole-Change Review

## Findings

**P1 - Cancellation can discard an already completed SEC result.**
`src/agents/openai_agent/agent.py:725` and `:737`.
The end hook admits the whole result and enqueues its references at `:705`,
but persistence depends on the consumer subsequently draining that queue.
If cancellation reaches the executor after enqueue and before its pending
`hooks.ready.wait()` resumes, that await raises `CancelledError` even though
the completion is queued. The `finally` disables publication and awaits the
worker, but neither drains nor durably hands off the already admitted events.
The active cancel path calls `task.cancel()` (`src/research_run_manager.py:301`);
only yielded events reach `append_event` (`:162`). Cancellation terminalization
and restart recovery therefore have no end event/reference to reconstruct.
The completed source disappears from the message and maintenance roots without
even a citation gap. This violates the completed-result retention contract.

Preserve already admitted queued completions across cancellation before terminal
persistence, while still rejecting late worker publication and retaining the
security boundary. Add a deterministic producer-to-executor/store regression:
enqueue an end, cancel before consumption, then assert the exact call ID and
references survive in durable events, the cancelled message and reopened roots.
Existing owners at `tests/test_sec_research_trace.py:513` and `:656` first consume
the end event before cancelling; they cannot detect this ordering. This finding
is established by source tracing, not a test executed during this review.

**Decision: REVISE** (`revise`); whole-change approval withheld for the finding.

## Scope And Identity

- Worktree: `/tmp/arkscope-research-output-boundary`.
- Base: `ca49b454025e19e661a70ccb76832f23d0fc3365`.
- Head: `bc8c86d5122f5c01221d023a2719673dd226936e`; identities checked read-only.
- Artifact: own `final-review.diff`, 32 changed files; SHA-256:
  `b0d571954e1278d4cfc2efe773edf3fd18ee59bb19e552b369d449d731da1170`.
- Read the focused plan and supplied diff once, task reports/approvals and
  relevant receipts; supplemented truncated display and concrete integration
  questions with scoped source reads. Reviewed source paths had no HEAD drift.

## Other Boundaries

- Four producer projections follow whole-result security admission and precede
  citation previews; native Anthropic projection precedes Layer 0 compression.
  Closed event validation rejects unknown fields/unowned or malformed references.
- Exact IDs, first-completion replay and isolated anonymous pairing agree across
  backend/UI. Delivered events retain optional JSON fields through messages,
  archive and transactional all-event recovery, including beyond event 500.
- Query-only profile enumeration includes messages and event-only roots; malformed
  present JSON/references and recorded gaps veto closure. Prose is not authority.
- Exact reads bind stored identities, hashes, pointers and UTF-8 ranges, compare
  observations with parsed source bytes, and never substitute latest data or
  fetch a supplied URL. Closure includes receipt members and catalog provenance.
- Existing source/object caps remain; traversal retains compact identities rather
  than cumulative parsed payloads. No new small whole-store ceiling was found.
- UI keeps reference identity through reload/pin, guards selected owners/stale
  reads, renders plain text and Decimal strings, and uses canonical query tokens.
  No additional actionable auth/tracing/retry/model-routing regression found.

## Evidence And Limits

- Read logs confirm focused backend 772 passed, Task 2 scope 1164 passed and
  frontend 1824 passed; these overlapping selections are not additive coverage.
- Parent confirms typecheck/build/i18n exit 0. Read inverse validation records
  all five named inverses killed, restored 16 passed; setup failure is excluded.
- Final browser receipt records four en/zh-Hant desktop/mobile workflows, zero
  page errors/overflow/clipped buttons, exact Unicode passage and 21-digit fact,
  refresh/root relocation, persisted reload, missing-object retry and focus.
- Test collateral is scoped: HTTP routes 222 to 223; research i18n keys +17 per
  locale. These counts do not replace full-suite collection/source accounting.
- Full backend has NOT run. Accepted baseline remains 10311 passed/12 skipped;
  final census, collection reconciliation and evidence sealing remain parent work.
- Risk: high impact for lost durable evidence; protection partial for cancellation
  ordering. Recovery cannot reconstruct an event that never reached persistence.
  No schema migration is added, but rollback must retain existing JSON and captures.
- This is the published SEC-reference plan, not whole-SEC release approval.
  Leases/export/cleanup/reset/scheduling/SQLite activation remain deliberately open.
- No tests, subagents, provider/product processes, production/config/token access,
  or source/git mutations. This report is the reviewer's only write.
