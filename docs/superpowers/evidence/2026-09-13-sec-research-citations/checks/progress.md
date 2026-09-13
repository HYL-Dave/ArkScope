# SDD ledger - plan: docs/superpowers/plans/2026-09-13-sec-research-citations.md

Baseline ca49b454, existing isolated codex/sec-research-integration worktree.
Parent release Task3 and the product spec are approved; this is its execution
decomposition, not a change to the approved product direction.

## Preflight

| Tasks | Shared file/interface | Checked outcome |
| --- | --- | --- |
| 1 / 2 | citation extraction and event projection | Whole admitted output; typed gaps. Task2 consumes Task1 helper. |
| 1 / 3 | references.py | Sequential; Task1 owns market closure, Task3 adds profile iterator. |
| 1 / 4 | GET citation and closed union | Canonical bounded JSON token; typed exact stored result. |
| 2 / 3 | tool event identity and optional fields | Same call_id, no name-based pairing for identified calls. |
| 2 / 4 | event IDs and optional metadata | Backend and frontend retain identical references. |
| 3 / 4 | stored tool_calls JSON | Additive optional fields, no schema/legacy writer. |
| 1-4 / 5 | acceptance source | Frozen only after all writers/reviewers done. |
| 1 | own files/tests | No table change; exact source read/closure covered, GET before CIK. |
| 2 | own files/tests | SDK hooks verified locally; no invented API or raw-before-security refs. |
| 3 | own files/tests | Query-only iterator, message plus event roots, unbounded recovery pagination. |
| 4 | own files/tests | Plain text, old rows still render, real-service browser required. |
| 5 | own files/tests | Accepted baseline is backend-accepted-full, not failed earlier receipt. |

Ruling: complete durable Research references before destructive maintenance -
approved parent Tasks5/6 require this closure and operation leases/export - doing
cleanup now could erase a cited source. No production action is authorized here.

Ruling: use optional sec_citation_gaps alongside sec_citations in events and
stored JSON - malformed owned results must remain an explicit maintenance veto -
otherwise a missing reference could be mistaken for unused content.

Ruling: sequential workers/test runners; final full suite once on reviewed frozen
source - prevents shared store/fixture interference. Use archived offline guards
without weakening filesystem/network/token restrictions.

Task 1: complete
Task 2: complete
Task 3: complete
Task 4: complete
Task 5: acceptance complete; final archive publication pending

Task1 dispatched to Epicurus (01a098c2-a492-7c81-826e-4dcb90234cb2).
Task1 observed receipts: baseline491 passed; initial RED103 failures for missing
citation behavior/route precedence. Implementation in progress; no GREEN claim.
Task1 implementation899b4098; broad focused1534 passed. Scale/unrelated-receipt
RED4 failures then focused GREEN are retained separately. Awaiting task review.
Task1 review (Helmholtz 01a098e2-e620-72c3-904b-6735d55c8022): one P2,
incomplete validation of otherwise complete native observation rows. Fix round1
sent to original implementer; no event/UI task starts until this gate is closed.
Task1 fix89509a31: native-row mutations31 intended RED failures, nullable controls8P;
focused GREEN430P. Scoped re-review sent to the same reviewer, no runner active.
Task1 re-review PASS/APPROVE, no remaining findings (task-1-rereview1.md).
Accepted implementation899b4098+89509a31; upcoming Task2 baseline89509a31.
Task2 dispatched to Pascal (01a098f4-9e5a-76c3-81cd-da4cdbdf4bea), sole
product writer/test runner. Controller prepares browser/acceptance artifacts only.
Task2 ruling: no production post-run compatibility branch solely for old fake
Runner tests. Update fakes to invoke the installed hook contract; retain any
fallback only for a documented actually admitted SDK tool family without hooks.
Controller prepared browser-fixture/, vite-preview.mjs, browser_fixture.py (copied
from tracked document evidence) and browser_check.py. NOT RUN; the latter still
has an explicit pending Task4 selector placeholder. Finish relocation/refresh/
focus/error workflows before running/sealing it. All data is generated temporary
source/store; no provider/prod use. Baseline censusca49b454 completed:4330 candidates,
3463 uncertainties,1148 source files read. No final census verdict yet.

Ruling: Task2 must extend the existing closed output_events tool-end vocabulary
with typed citation metadata and end-only input - source inspection shows unknown
fields otherwise raise OutputBoundaryError - retain exact-secret admission before
any field validation; this is a named schema addition, not a redaction exception.

Ruling: Task3 may move accumulation to research_tool_trace.py, consumed by both
API and store - avoids a domain-to-route import cycle during transactional recovery
- no duplicate implementation or abandoned forwarding function.

Task1 integration review concern during interface preparation: provisional
256MiB/200k-node cumulative reader budget conflicts with the approved100GiB
capture store when closure is called for all Research roots. Sent to implementer
before commit. Ruling: retain per-object bounds and compact traversal state, not
an arbitrary small whole-store ceiling. Exact reopening and full maintenance
closure need distinct traversal scope; unrelated later refreshes cannot invalidate
an already pinned observation.
Task2 commit35f2d720: focused1164P; source-only review by James
(01a09908-09e2-7a10-914a-de2d36fcc181). Implementer closed, no runner active.
Controller fixture setup citations-fixture-setup-01: actual temporary service/store
refresh,3 references persisted and read back;176 UTF8 passage bytes. Setup only,
browser_exercised=false. No production/provider access.
Task2 independent review APPROVE; no actionable findings. task-2-review.md.
Task3 starts from35f2d720, no event producer/security/UI changes planned.
Controller fixture setup02 also verifies distinct later capture and exact old
176-byte passage after relocating generated market DB and capture root. Pass;
still not browser acceptance. Test processes complete before Task3 starts.
Task3 implementation8c9ee301: corrected RED46F/70P; lifecycle RED4F;
final focused772P. Implementer closed. Hume01a09916-917d-79d3-9914-72aef0cdfc9f
reviews immutable task3 package source-only. Parent runs acceptance inverses in
separate processes; only function.__code__ is temporarily changed and restored,
not tracked source files. Recipes/diffs/function hashes are recorded per run.
First500 inverse01 failed in launcher setup (TYPE_CHECKING-only annotation name
evaluated during compile), not its owner. Harness now compiles postponed
annotations; product/test source unchanged. Retain failed setup, rerun02.
Task3 independent source review PASS/APPROVE, no actionable findings.
Five inverses now have intended assertion failures: hash1F11P, projection1F,
wrongID1F, missingeventroots1F, recovery500rerun02 2F (restart/no-task-cancel).
All in-memory functions restored; no tracked source write. Restored owner GREEN
is running before Task4 takes test-runner ownership.
Restored inverse owners16P; all16selectednodes passed on unchanged8c9ee301.
Task4 starts from8c9ee301; sole frontend writer/test runner, parent owns scratch
browser/evidence only. No parent test program runs during that task.
Task4 controller usability finding during browser preparation: multiple financial
facts under one CIK otherwise render identical source buttons. Request ordinal
labels with a two-fact owner; no invented concept/period or eager all-source reads.
Browser fixture now uses real persisted event->assistant projection and a
Unicode/escaped taxonomy pointer, in addition to update/relocation/retry/focus.
Those additional fixture edits are not yet executed; await Task4 handoff.
Task4 commitbc8c86d5, final frontend1824P/126files, typecheck/build/i18n03 exit0.
Peirce01a0992e-a92f-7193-aa8b-f500f255abc8 performs source-only task review.
Browser01 failed before navigation because controller supplied the unit-test
network guard to Vite: it intentionally blocks even loopback listener DNS lookup.
Preview-only wrapper now permits numeric127.0.0.1 lookup/listen and preserves all
outbound TCP/DNS/UDP prohibitions. Base offline guards and product code unchanged.
Task4 independent review APPROVE, no actionable findings. Browser02 and final
each pass four actualAPI/store en/zhHant 1280/390 workflows, zero overflow,
clippedbuttons or pageerrors. Controller inspected desktop/mobile screenshots;
176byte oldUTF8 passage and21digitfactvalue unchanged, actualUnicodepointerGET,
refresh/relocation/retry/reload/focus verified. No acquisition fromopeningrefs.
Five inverse receipts verified against current function source hashes; restored16P.
Only preview PID3749585 (verified exact plan config) terminated; session54425 ends.
All task agents closed. Next: broad final review, frozen-source fullbackend, census,
exact accounting and evidence seal. Not yet fullbackendverified or entireSECdone.
Final whole-change review REVISE: one P1, OpenAI completion admitted to queue but
cancellation before consumer wake can lose references before persistence. Parent
owns deterministic producer/executor/store RED and narrow repair; no full suite
starts until original reviewer rechecks. Other task contracts approved unchanged.
Fixdbc8f7e5: deterministic queued-end cancellation2F (including repeatedcancel),
then scoped709P. An earlierGREEN command named nonexistent test paths, exit4/
no tests; corrected command02, no product changes to accommodate that typo.
Original reviewer receives exact11-line fix plus71-line integration owner.
Scoped final re-review APPROVE atdbc8f7e5, no remaining findings. Reviewer closed.
Collection02 owns10595nodes. Freeze dbc8f7e5 and run completebackend alone; no
source writes, secondpytest, browser, census or source agents during that run.
Full backend10583P/12 unchanged S;10595collected=executed,272added/zero removed,
1142 unchanged source hashes/runtime/SDK/runner. Exact closure validation passes.
Final census found one true ineffective CSS rule.5235705c deletes it; backend
source/tests unchanged. Fresh frontend1824P/typecheck/build/i18n and final four
actualAPI/store browser workflows pass. PreviewPID3800600 verified and stopped,
session41572 closed; initial launch's wrong nested node_modules path had no listener.
Final census4330/3469/1158read, zero new candidates/reductions/dependency/untracked
drift.151uncertaintyIDs=145positionchanges+6reviewed statements. Rawexit2retained.
78 command receipts inventoried,36nonzero checkpoints classified, no uncovered
failure; overlapping scopes never summed. Evidence seal/Gitverification pending.
Handoff/collateral review APPROVE at61bb853b. Reviewer closed. All product and
acceptance work complete; only archive publication, Git-object verification and
own scratch removal remain. The final archive-verification.json outside checks
records that later step, avoiding a self-referential sealed progress claim.
Keep codex/sec-research-integration and its host-owned worktree. No merge/push.
