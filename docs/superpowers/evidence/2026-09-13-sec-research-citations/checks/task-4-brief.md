# Task 4: Research Source Reopening UI

Read focused plan Task4 and parent release Task3 UI contract. Work directly in
/tmp/arkscope-research-output-boundary, no subagents. Own frontend api.ts,
researchReducer.ts, ResearchEvidenceDrawer.tsx, new SecCitationView.tsx, their
focused tests, owned CSS and en/zh-Hant resources. Do not edit backend.
Backend Tasks1-3 supply closed SecCitation fields, GET canonical reference API,
and optional call_id/sec_citations/sec_citation_gaps in events/stored messages.
Read the Task1 report for exact encoding/envelope instead of guessing.
The shared Python queries._canonical uses sorted ASCII JSON; frontend must
preserve canonical escaping for non-ASCII JSON-pointer strings as well, not just
the typical ASCII fixtures. No hand-reconstructed URL or latest query fallback.

RED-first via this plan's run_checks.py NAME frontend test -- --run <files> (check
package.json actual command). Unique names, no plain provider/app process. During
your task only you run tests. Run full frontend, typecheck, build and
check:i18n-literals after focused GREEN. No browser yet; controller runs real-store
browser after your source is reviewed.

researchEvidenceRows currently projects name/input/preview only; every projection
must preserve refs. Likewise reducer toolCalls() drops other metadata today.
Implement backend-equivalent ID pairing, duplicates, end-only input and genuinely
ID-less fallback. Keep legacy tests valid and retain old preview display.

Evidence drawer needs a concise source-open control per retained reference, plain
text observations/passages, and typed citation gaps. Use existing drawer/panel
patterns and icons, not remote HTML or nested cards. Show form/period when known,
not invented labels. Source text must wrap at mobile widths. Add loading/error/
retry/close states, correct focus restoration, selected-message and stale response
guards. If evidence drawer closes or selected message changes, old async results
must not reappear. Toggling pinned state must not silently switch evidence owner.
getResearchRun failure must not prevent opening already persisted citations.

Tests must cover real reducer state transitions and component fetch completion,
including switch-then-resolve, close-then-resolve, mixed legacy/current calls,
literal remote HTML displayed only as text and keyboard focus restoration. Add
getSecResearchCitation test for exact canonical encoded query and invalid input.

Self-review, commit only owned files, write task-4-report.md with RED/GREEN receipts,
exact accessible names and selectors for browser verification. Return status/SHA.
