# SDD ledger - plan: docs/superpowers/plans/2026-09-11-sec-query-settings.md

Base: 483e8f3e2acde8d5ccc81b25eda286789d0ace3e. Linked worktree verified clean.
User approved continuing the SEC spec; no request for merge or live operations.
Skills read: receiving-code-review, brainstorming (approved spec), writing-plans,
using-git-worktrees, test-driven-development, subagent-driven-development.

## Preflight

| Tasks | Shared file/interface | Finding/ruling |
| --- | --- | --- |
| 1/2 | queries.py, receipt/cursor helpers | Task 1 first; task 2 reuses mechanics, distinct fact selection owner. |
| 1/3 | receipt data/service/queries | HTTP reads only bound sources; old status route stays observational. |
| 1/4 | status and bound cursor | UI passes opaque cursor unchanged, resets only for changed filter/CIK. |
| 2/3 | facts interface | Exact strings and all query options remain typed, no float conversion. |
| 2/4 | fact pages | UI is a simple stored browser, does not claim derived metrics. |
| 3/4 | API contracts | Exact routes/request types in plan are authority; update plan if altered. |
| 1 | RED vs code/files | Same owners for schema bindings, page stability and sequence policy. |
| 2 | RED vs code/files | Unknown periods/conflicts must stay visible, immutable ids not latest filtered. |
| 3 | RED vs code/files | Static config routes precede generic CIK; route count collateral included. |
| 4 | RED vs code/files | Real query/refresh/config consumers, no schedule/Research admission claim. |

Ruling: Preserve AUTOINCREMENT and SQLite's shared sqlite_sequence ownership --
committed receipt insertion order is a real current invariant and max-rowid
exhaustion must fail rather than insert a random lower id -- changing this later
would require another explicit ordering design, not a cosmetic schema cleanup.
Official references: https://www.sqlite.org/autoinc.html and
https://www.sqlite.org/fileformat.html#the_sqlite_sequence_table .

Ruling: Settings here is incremental structured-storage administration, not the
spec's complete financial Research workflow -- no model-facing or scheduled
replacement until all complete-first-release requirements pass -- costs one
intermediate UI while ticker resolution/document tools remain open, stated
explicitly instead of pretending this completes the SEC release.

Ruling: CIK-only remains explicit for this batch; no guessed ticker mapping or
new issuer-directory network budget -- retains the prior service's authority --
less ergonomic than final issuer search, but not a silent mapping risk.

## Status

Task 1: e207b3ad implemented, 587 related tests pass; five inverses fail owned
tests and restoration hashes match. Implementer closed, task review in progress.
Review agent: 01a090b3-5783-71f3-ba04-89ea7c4d017b, frozen task-1-diff.txt.
Task 1 fix round1: review verified valid JSON null/int receipt fields escape as
TypeError. Resume original implementer for narrow decoded read-shape validation,
preserve explicit unbound{}; named RED owner before fix. Others cannot commit
until this worker's scoped fix commit completes. No broad exception swallowing.
R1 implementation: 7a1b9d99, store.py and two Task1 tests only; 644 related tests
pass, read-validation inverse caught/restored. Implementer closed; same reviewer
resumed for scoped task-1-r1-diff.txt review. Task1 gate remains pending review.
Task 1: complete (0658ebf0..7a1b9d99, R1 scoped review PASS; no open findings).
Reviewer checked frozen diff, archived tests and restoration hashes; closed.
Task 2: dispatching against landed helpers; Task1 R1 narrowed to store.py/tests,
no overlapping query file edits. Both gates required before final integration.
Task2 agent: 01a090b9-1751-7980-a2da-7697958ab95e; no index writes before parent permission.
Task 3: independent API/config work started; agent
01a090b4-ec29-71a0-8d1e-c53214324822. Facts integration waits for Task2;
commit needs parent permission.
Task3 independent handoff: 261 passing, ten ordinary real-facts cases still RED;
agent closed pending Task2 actual service signal, no index writes.
Task 4: implementing in disjoint frontend scope; agent
01a090b1-933c-7ff0-b668-4cd572249098; task-4-brief.md. Commit needs parent permission.
Task4 handoff: 1729 frontend tests/typecheck/i18n reported; parent read report and
scoped diff. Sole index permission granted for 17 listed frontend paths, then
independent task review. Parent browser checks remain pending.
Whole-change review: pending.
Full verification/evidence: pending.

Final fix: 5d03c57e, only component and one added panel owner. Worker focused
RED/inverse1F39P, restored45P. Parent real HTTP/store browser RED reproduces2vs1;
post-fix four browsercases pass, fullfrontend1738P/typecheck/i18nexit0. Current
census unchanged at1119/4360/3444. Post-fix certificate proves798backendpaths
unchanged and exactlytwofrontendpaths changed; all1088 finalpaths frozen again.
One scoped final re-review dispatched to original reviewer, no broad loop.
Final integration verification: final-gates.json binds completed frontend1738P,
typecheck/i18nexit0, four actual-route/store browser cases at33HTTP/10generated
dispatches each and zero page/duplicate-key errors. Source-final all1088paths
unchanged. Vite fixture29671 stopped with SIGINT/exit130 after browser completion;
no actual user App process was started or stopped. All required check processes
have completed. Evidence publication awaits the one scoped review result.
Final whole-change gate: complete. Original reviewer approved final-rereview.md
with I1closed and zero residual findings, independently matching all1088final
hashes, two-filefrontenddelta,798unchangedbackendpaths and command/log hashes.
Reviewer and fix worker closed; no active plan agents. Parent retains branch
without integration under the plan's explicit no-merge/push scope. Archive all
verification/review/ruling artifacts, verify manifest against Git index, then
delete only this plan's generated scratch directory. Other plans/worktrees stay.

Final gate checkpoint: backend-full completed 8811 passed / 12 skipped. Parent
verification.py reconcile matched all 8823 collected/executed nodes, +377/-0,
unchanged 12 skip identities and all 1088 frozen paths. Final reviewer reported
one P2: conflicting catalog variants share React keys, leaving stale DOM rows
after pagination. This supported query result must remain intact. Dispatch one
final fix worker, then one scoped re-review; no backend changes permitted.
Ruling: retain the completed backend freeze/reconciliation unchanged and add a
post-fix frontend-only source-delta certificate -- the correction is a renderer
and frontend test change -- any backend delta invalidates backend reuse and
requires a fresh full run. All frontend/browser checks rerun after the fix.

Task4 committed baecc18c, reviewer 01a090c7-33a8-7921-9b9e-1b04099e571c.
Task2 handed off92fact tests/815related tests, three owned inverse failures;
sole index permission granted after Task4 commit. Task3 resumed real HTTPgate.
Parent browser-third: four locale/viewport workflows through actual routes/store
passed. Earlier browser runs assumed newest fact in first page, while deterministic
fact order is oldest first; corrected fixture expectation only. Full-response
fixture records retained. Visual review found pagination descendantspan leaks
64px width into icons, and mobile facts initially show onlyhash column. Sent to
Task4 reviewer; no controller product edits.
Task4 R1: reviewer confirms Important I1 pagination descendant-span width, Minor
M1 nullable query typing, M2 mobile hash-first columns. Resume original implementer
for all three scoped corrections with named RED owners. Parent owns refreshed
geometry verification; no shared Button/global stylesheet change. Task4 gate open.
Task2 committed e07e459a, reviewer 01a090cb-fbd6-7141-bca1-33404f18de4d.
Task 2: complete (baecc18c..e07e459a, independent review approved, no findings).
Reviewer verified named inverse failures/source hashes and all archive counts,
no duplicate suite run; closed. Ordinary and ID anchor separation approved.
Task3 R1: ImportantI1 absentstore earlyreturn skips domain/cursorvalidation;
reviewer's7caseprobe4F3P. ResumeoriginalAPIworker, expandnarrowlytopurevalidation
extractioninqueries/fact_queries(sharedbothentrypaths), noadapterrulesduplicate.
Task2reviewcompletebutTask3'snewquerytouchesmustrecheckcatalog/factsregressions.
Valid absent/brokenstoresstillunavailable; malformedrequests422withoutDBcreation.
Task4 R1 committed c6e2e435,1737frontendpass/typecheck/i18n. Parentbrowser-r1
fourlocale/viewports passed withrealAPI/store, paginationSVGrectanglescontained,
firstfactscolumnsconcept/value, tableheight<=600; screenshotsinspected. Same
reviewer resumed on frozen task-4-r1-diff.txt; workerclosed/indexreleased.
Task 4: complete (7a1b9d99..baecc18c + c6e2e435, R1 scopedreviewapproved,
zeroopenfindings). Reviewerchecked13hashes/RED/GREENandparentscreenshots;closed.
Parentfreshfrontend-final1737P/121files,typecheck/i18nexit0; baselinewarnings
retained. Extra read-only cursor-range check confirmed both anchor/offset already
bounded to signed64bit; suspected unrepresentableSQLiteinteger path is closed.
Task 3: complete (e07e459a..05edf925 +420e4759, R1 scopedreviewapproved,
zeroopenfindings). Same reviewerclosed. Purevalidationnormalizedoutputs/cursor
bindingandabsentvalidunavailabilityremainintact;953PwholeSEC/API, original7probeP.
All taskgatescomplete. Sourcefrozen1088paths; finalcollection8823nodes.
Fullbackendrunning session9856; no product/test edits permitted without invalidating
thatfreeze. Parentbrowser-final fourlocale/viewportgatepassed28localHTTPeach,
including malformedfactsperiodbeforeinstallation422; noexternalproviderdispatch.
Vitefixture session29671 remainsrunning untilfinalbrowser/evidencechecksfinish.
Task3 committed 05edf925 after271pass, reviewer01a090ce-0b5a-7000-9e90-d1a52f46966c.
Parent census first launch lacked Node in explicitly closed PATH and failed before
publishing output. Use run_checks.py's established complete Python+Node PATH,
retain failure as runner-only; no inventory/product expectations changed.

## Runner Observation

Frontend baseline before any frontend edits: 1688 pass/4 fail, all four fixed
Asia/Taipei timestamp expectations when this new runner incorrectly set TZ=UTC.
No network-guard failure. Correct runner timezone to the declared local
Asia/Taipei environment; do not edit product timestamp behavior or test assertions.
Original output/command retained under frontend-baseline. i18next debug stdout
is existing baseline noise, not newly clean-output evidence.
Corrected baseline: 119 files /1692 passed, 13.24 seconds, no frontend edits;
frontend-baseline-taipei retains command/log. This isolates TZ as the variable.

Ruling: immutable fact-id queries anchor ids + retained source snapshot identities,
not current receipt authority -- historical explicit references are valid even if
a new receipt fails, and no latest pointer should control reopening -- costs a
distinct cursor query kind, which Task 2 must share through the same strict codec.

Public technical docs consulted (no SEC data API or issuer acquisition):
https://www.sec.gov/search-filings/edgar-application-programming-interfaces .
Calendar-frame periods are not guaranteed fiscal periods. Task 2 brief records
this distinction to prevent applying current filing fp to comparative rows.

Ruling: Add aggregate selected-query bounds100000 rows/64MiB encoded metadata and
rows with streamed filter-before-retain, separate from the identical per-source
publication ceilings -- per-source bounds cannot constrain many historical
snapshots combined -- large selections may require narrower filters, with explicit
typed unavailability; no 4GiB whole-process measurement claim.

Ruling refinement after Task1: allow explicitly partial admitted selections on
aggregate exhaustion (unavailable only if none admitted); gap names exhausted
rows/bytes/sources, source count cap1024. This matches spec's partial envelope
rather than throwing away already bounded useful observations. Cursor does not
claim it can walk omitted sources. Parent plan wording corrected before Task2.

Ruling: Dispatch independent Task 4 frontend work against fixed plan API contracts
while Task 1 closes its backend guard tests -- write sets are disjoint and
frontend baseline is already frozen/passing -- Task 3 and final real-API browser
integration must reconcile the interface before completion. Agent must report
ready-to-commit; parent serializes index/commit operations. This avoids holding
actual frontend consumers until after all query mechanics are done.

Ruling: Task3 configuration, catalog and input adapters can also execute against
fixed query signatures in disjoint route/test files; its real facts integration
tests remain an explicit dependency on Task2, not mocked-away completion. Parent
will signal query readiness and serialize route commit. No source/query worker
may edit API files, and no API worker may create a stub query implementation.
