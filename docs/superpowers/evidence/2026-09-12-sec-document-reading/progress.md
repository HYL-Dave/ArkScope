# SDD ledger - plan: docs/superpowers/plans/2026-09-12-sec-document-reading.md

## Authority And Isolation

Approved spec: docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md.
Base: 3e98bda264e024b3aa03efafd0ba0abab9a19a5a.
Existing linked worktree /tmp/arkscope-listing-sec-macro-convergence; branch
codex/listing-sec-macro-convergence. No provider data, production DB/config/token,
dependency installation, schema reset/drop, App restart, merge or push. All test
state is disposable under this plan's scratch. Prior sealed evidence is reusable;
other plans' scratch is not. Agents inherit model, per tool dispatch authority.

## Preflight Table

| Tasks | Shared surface | Finding/ruling |
| --- | --- | --- |
| 1 + 2 | DocumentDirectory/extractor/index | Frozen entries and dict section records are consumed by durable owner; record concrete shapes after Task1 before dispatch2. Exact directory body is retained, parser cannot acquire. |
| 1 + 3 | PublicSourceReader callback | Optional callback keeps old extraction unchanged. API injects reviewed SEC policy and new extractor. |
| 1 + 4 | Section IDs/byte ranges | UI treats IDs as opaque and renders text only; backend owns UTF8 slicing. |
| 2 + 3 | Pure validation/query/service/attempt | Validate before filesystem/installation. GET no writes. POST explicitly installs only fresh canonical schema; malformed existing rejects. |
| 2 + 4 | Envelope/index/search/cursor | Define exact types from reviewed Task2, not mock-only UI guesses. Preserve active capture across pagination, offer deliberate latest read. |
| 3 + 4 | GET/POST path and strict body | Same path, selected filing/document. Timeout is unknown and permits GET reread, never automatic POST retry. |
| Task1 self | Named RED vs new modules | Import collection errors alone are not behavior evidence; create empty interfaces if needed, then RED assertions. Parser bounds fail with typed error, never complete truncated text. |
| Task2 self | Empty/no-query/index vs text page | Initial index includes text_start_cursor, text cursor identifies text mode. Separate index cursor if entries overflow; no omitted documents/sections. |
| Task3 self | Existing /{cik} vs static filing path | Segment counts differ; mounted-route tests prove six originals and two new. Exact count adjusted from execution, not assumed 224. |
| Task4 self | Initial GET vs explicit acquisition | Opening missing capture shows action, does not POST. Catalog conflict variants retain independent rows and cannot authorize an arbitrary primary. |

Ruling: this batch implements only the approved document subsystem, not all SEC
first-release work - dependencies and tool atomic replacement remain explicit -
cost if mistaken is delayed full Research admission, not hidden partial admission.
Ruling: SEC-RECOVERY-001/002 are open owners now, not destructive operations -
future citation/export reference closure must be known before removal - cost is
temporary counted orphans and explicit mismatch until the recovery batch lands.
Ruling: dynamic schema shape changes remain deliberate pre-release mismatch,
without asserting a production installation exists - no production read needed.
Cost if wrong is requiring an explicit recovery step for an already installed
older shape; accumulated data is not silently repaired or discarded.
Ruling: independent reviewers/implementers use default inherited model, not a
skill-specified override, because the tool forbids an override absent user choice.
Cost is potentially more model compute than a cheaper override, not broader
provider or filesystem authority.

## Status

- Task1: complete, reviewed through b07eba2b after two fix rounds.169 product
  tests, extractionv3. Implementer Fermat/reviewer Ohm closed; history below.
- Task2: complete, reviewed through1f964efe after one fix round.107 shipped
  Task2 tests; independent invalidation and request-accounting corrections accepted.
- Task3: complete through64a25c34; HTTP spec/quality approved.
- Task4: implementation from64a25c34; Settings reader/browser preflights pass;
  opening focus completion, full frontend and independent review pending.
- Final integration review, full backend/frontend, census, archive: pending.

## Evidence Setup

Copied unchanged offline_pytest.py/offline_node.cjs/preview_node.cjs and mechanical
check/review helpers from sealed 2026-09-11-sec-query-settings evidence. The runner
is an audit-hook plus isolated environment, not an OS containment claim. Retains
installed Node PATH and Asia/Taipei timezone; test plugin autoload disabled.

Initial baseline-sec exited4 due to nonexistent test_sec_research_schema.py,
no tests executed. Corrected glob inventory:884P, baseline-sec-corrected, no source
changes. Documentation plan/recovery-owner commit98499d65.

Official task-brief default output wrapper exits126 because its internal
sdd-workspace has no executable permission. Explicit output parameter succeeds;
task-1/2-requirements.md extracted without modifying installed scripts/permissions.
Execution notes remain task-N-brief.md. No product behavior affected.

Task1 original behavior RED: task1-red-core-01,87F/1P after minimal importable
interfaces. Failures are assertions, not import/collection failures. Implementation
in progress; no passing claim yet. Parent prepared generated browser transport
bodies and source/node/archive helpers in scratch only.

Task1 intermediate evidence: initial core88P; parser resource probe10P; expanded
relevant SEC/public reader regression1130P. Inverses:unsafe entry13F/3P,
nesting2F/3P, ambiguous heading1F. Awaiting worker self-review/report/commit,
independent review not yet performed. Task1 owns sole Git index window.

Ruling: pending unrelated catalog history alone does not veto reading an exact
observed filing - retain its coverage gap, only observed metadata conflicts block
authority - cost if wrong is a partial catalog context, never fabricated coverage.
This is explicit in Task2 execution notes.

Ruling: I1 is required hidden-content semantics, not optional prefix support;
scoped namespace resolution must preserve unrelated namespaces/default lifecycle.
Cost if wrong is extra parser complexity/rework, without relaxing hidden-content
or default-reader preservation requirements.
Ruling: conservative omission of uncertain TOC entries is allowed by section7;
no body-recovery heuristic is required. Cost is fewer selectable sections, with
explicit gaps and whole-text access, never fabricated section identities.

Task1 fix-round1 intermediate: core152P; resource probe12P. Additional scope-work
RED4F retained for explicit namespace unbinding, declaration work budget/cancel.
Fix not yet committed/re-reviewed. Namespace primary documentation in
primary-source-notes.md; only public technical documentation was browsed.

Task1 fix-round1 committed6cad56cf; extraction version nowv2. Report corrects
core152 count to149 product tests+3 independent probes. Relevant1181P,12resourceP,
five new inverse runs with exact hash restoration. Re-review Ohm resumed;
task-1-fix-r1-diff.txt immutable195a486e..6cad56cf. Index window closed.

Re-review R1: I1/I2 addressed, newImportant R1-1 reproduced2F: HTMLParser folds
XHTML prefix/attribute names, conflating distinct ix/IX bindings (leak/false reject).
Parent independently inspected new namespace code after cancelling only its wait
cell; no source changes. Fix round2 sent to original Fermat, explicit resume;
case-preserving QName identity required before resolver, not a case special-case.
Sole Task1 index window reopened; re-review report task-1-rereview-r1.md.

Task1 fix-round2 intermediate:174 core/probeP,1201 relevant regressionP,
19resourceP; five new inverse runs. Pending worker final report/commit and scoped
re-review. Do not mark Task1 complete yet. No Task2/3/4 implementation dispatched.

Task1 fix-round2 committed b07eba2b. Task1 product169 nodes,174 core/probeP,
182 precommitP,1201 relevantP; extraction versionv3, signatures unchanged.
Index window closed. Ohm resumed for scoped R1-1 re-review using immutable
6cad56cf..b07eba2b task-1-fix-r2-diff.txt. No production/provider reads.

Task 1: fix round 2/5 (R1-1 addressed,0 open; commits6cad56cf..b07eba2b).
Task 1: complete (commits98499d65..b07eba2b, review clean).
Scoped review task-1-rereview-r2.md approved. No API/type changes beyond extraction
versionv3. Task2 base b07eba2b, requirements and execution notes preflighted;
all Task1 index ownership closed, Task2 will have its own grant.

Task2: active, Mill01a09189-643c-7612-8a73-b701098db4fc, baseb07eba2b.
Sole index permission for exact Task2 source/test files; parent owns only disjoint
scratch/browser/evidence helpers. Task1 implementer/reviewer closed.

Task2 initial preflight65F asserts missing modules; this is NOT behavioral RED.
Worker has separately scheduled callable-stub task2-red-behavior-01 before product
implementation. Concrete sync refresh attempt/query/citation shapes are recorded
in task-2-report.md. Parent browser fixture now verifies every returned passage
against actual CaptureStore bytes/hash/source identity. Current Task1 inverse
summary covers5runs/21behavioral failures and exact restored source hashes.

Task2 interrupted by agent usage-limit response, not a product/test failure.
User explicitly resumed. HEAD remains b07eba2b; all8 scoped source/test changes
are retained uncommitted. Original Mill resumed with same ownership; subsequent
wait returned running, no duplicate implementer or rollback dispatched. Query
owner has263lines (not the earlier stub); final GREEN/review still pending.

Task2 progress:13 behavioral RED failures (module preflight excluded). Core73P
after fixes for pre-dispatch directory capacity and primary/resolved-ID latest
alias handling. Two test-fixture corrections explicitly reported (exhibit heading,
catalog JSON pointer), not counted as product defects. Further error-boundary
REDs retained; full Task2 report/inverse/regression/review pending.

Task2 committed eeffb971 (baseb07eba2b),8 owned files; index window closed.
87 final focusedP;1292 earlier relevantP;4 final restored ownerP. Four planned
inverses fail, affected query inverses rerun on finalsource after oversized-index
fix. Independent task2 review dispatched against task-2-diff.txt; no Task3 source
changes until gate. Concrete examples appended task-2-report.md.
Task2 reviewer Hypatia01a091a6-9528-7a10-862f-b426eb52e696 active; immutable
package75KiB. Parent archive selector explicitly includes real interface examples.

Task2 review2Important, reproduced5F/1provenanceP. I1 early conflict/cancel omits
known alias, alternate spelling serves older success. I2 report validation erases
real dispatch evidence and can claim no_dispatch. Both accepted against explicit
contracts; original Mill resumed fix round1 with full report/probes, sole index.
Old-commit reviewer hash probe remains historical; behavioral probes run separately.
No Task3 implementation yet. Cannot-verify whole-App/four-channel/browser items
map to unchanged surfaces and planned final fullsuite/Task3/4 gates, not extra work.

Ruling: I2 may refine request-record shape to separate independently observed
dispatch/count from unavailable validated report - the old probe's report.requests
shape is not the contract - cost is updating API/UI types before their first wiring,
not fabricating a complete report to satisfy a historical reproduction assertion.

Task2 fix1:16 ownerRED/2positive,5 prior-review behavioralRED (historical provenance
probe deselected, unchanged). Source fixes and new inverses in progress; no API/UI
changes. Prior task2-current-inverse-evidence.json is a pre-fix checkpoint, not final
current-source evidence after this review fix.

Task2 fix1 committed1f964efe,4 scoped files; index window closed.111 focusedP,
338 relevantP,20 restored-ownerP;6 inverse runs with hashes in fix-r1-inverse-hashes.
New request records:operation/url/request_count/dispatch_state/report/gaps; nullable
count/report, dispatch state dispatched/not_dispatched/unknown. Attempt's nullable
invalidation_primary_document is observational invalidation only, never authority.
Hypatia resumed scoped eeffb971..1f964efe review; task-2-fix-r1-diff.txt.

Task 2: fix round 1/5 (I1/I2 addressed,0 open; commitseeffb971..1f964efe).
Task 2: complete (commitsb07eba2b..1f964efe, review clean).
Report task-2-rereview-r1.md approved; both Task2 agents closed, index released.
Task3 base1f964efe, concrete fixed request-record shapes in execution notes.

Task3 implementer Godel01a091c8-e3bc-75c3-8648-08a59a48b9f5 active; sole index
grant for scoped API/tests only. Parent inverse_mutation.py compiles named query
mutants only into its own test process, never edits product files or affects the
worker's API tests. It saves exact executed mutant source and disk-before/after
hashes, restores module globals after each run, and uses the same offline runner.

Parent current query inverses: pin1F and filter1F, each its exact named owner;
ordinary controls2P after process-local restoration. Both disk source/test hashes
unchanged. Evidence parent-query-current-inverse-evidence.json; no fixture/API
worker interference. This rechecks the two query guards against post-fix1 tests,
rather than treating their earlier checkpoints as identical current-source evidence.

Task3 progress:63 document-routeP,83 boundary/controlP,1627 relevant regressionP
(72.76s). Two route inverses retained. Worker report/commit and independent gate
pending; no Task4 implementation yet. No source changes from parent.

Task3 committed2f84d2de (base1f964efe), actual224routes, six prior SEC routes
preserved. Final234focusedP;1627 relevantP;4 inverse runs. Sole index closed;
independent task-3-diff.txt review dispatched. Report task-3-report.md includes
actual generated examples and production reader hooks for parent browser fixture.

Task3 reviewer01a091d7-783d-7ed3-a0c0-13c1380b2249: spec PASS, quality approved
with one minor diagnostics finding. Four deliberate inverses have correct primary
failures, but pytest.fail crossing TestClient adds teardown errors. Original Godel
fix round1 owns test_sec_research_document_routes.py only; no product changes.
Ruling: repair this minor now rather than waive final inverse errors==0; clean
failure attribution is part of reproducible evidence. Cost if wrong is test-only
rework; ordinary expected route behavior remains unchanged.

Parent fixture HTTP smoke parent-browser-fixture-01:1P using real mounted API,
service, PublicSourceReader, capture objects. Verified original UTF8 citation,
two dispatches per acquire, changed latest with unchanged pin, failed newer read
unavailable while old pin survives. Only generated transport used. Browser fixture
can add long directory entries to exercise index pagination/mobile navigation.

Task3 fix1 committed64a25c34, test-only; sole index closed.234focusedP. Four
process-local inverse runs now22 intended failures/0errors, no disk source edits.
Structured hashes/mutants/task3-fix1-current-inverse-evidence.json retained.
Original reviewer resumed scoped task-3-fix-r1-diff.txt; no Task4 edits yet.

Current combined inverse manifest:17runs/63 intended failures; exact current
source/test hashes and all zero-error JUnit failures rechecked by inverse_summary.py.
Fixture-only Vite started127.0.0.1:8457/session54743 with preview_node guard and
isolated vite-home; real App untouched. Must stop before final/scratch removal.
Parent browser baseline runs existing catalog/facts workflows before Task4; it
does not yet claim document-reader browser acceptance.

Task 3: fix round1/5 (minor diagnostics addressed,0open;2f84d2de..64a25c34).
Task 3: complete (1f964efe..64a25c34;specPASS/qualityApproved).
Scoped review task-3-rereview-r1.md approved; both Task3 agents closed.
Task4 nowactive from64a25c34, sole-index grant limited to Task4 frontendfiles.
Parent remains owner of fixture/browser/evidencehelpers; no backend edits.

Task4 implementer Archimedes01a091e6-b082-75c1-be6b-e442ff9e2a62.
Parent-browser-baseline-01 passes4 locale/viewport combinations, each33 HTTP
requests/10 generatedmetadata dispatches/0 pageerrors. Existing catalog/facts,
conflict pagination/lostPOSTreread/budgetcontrols intact; newreader notyettested.

Task4 selectors documented before implementation completed, enabling parent
browser_documents.py integration now. Early parent-reader-browser-01 is a probe
while frontend is changing, not final frozen-source acceptance. Its section-gap
case rewrites one selected section operand to item_999 then renders the real API
envelope; no canned JSON. Late-response case holds a real response across closing.

Early browser01 stopped before reader on obsolete parent selector: primary cell
accessible name now includes the new read button. Existing filename text remained.
Parent selectors now locate exact visible filename text; no product/testexpectation
changed and no claim of product regression from this fixture-adaptation failure.

Early browser02 exposed unknownPOST reread with an old pin in the served changing
UI; worker had concurrently corrected that action to a latest GET. Originalpin
case sent to worker for dedicated owner. Parent-reader-browser-03 passes4locale/
viewport combinations, each70HTTP/13metadata plus8documentdispatches. Verifies
longindex, actualUTF8/hashes, pin/current, failedlatest, unknownPOSTlatestGET,
missingsecondary and lateGETafterclose. This is precommit integration, not final
sourcefreeze. Parent inspecting screenshots and opening focus next.

Browser04 all existing/new workflows stillpass;13passages verified perviewport.
Opening geometry before parent scrolling: headingtop1235>desktop960,929>mobile844,
bothlocales. Ruling: per-row Open must focus/scroll the reader and Close restore
the still-connected opener; otherwise command creates an offscreen result with no
usable handoff. This is the existing open/close workflow's ergonomic completion;
cost if wrong is narrow focus/scroll behavior/test rework. Sent to Task4 owner.

Task4 committedf53a87a4(base64a25c34), soleindexclosed; frontend1765P,
typecheck/i18npassed. Focus+close and unknownPOSTfrompin owner included.
Independent task-4-diff.txt review dispatched; parent-reader-browser-final now
checks exact committed product including openingheadinginviewport and focusreturn.

Parent-reader-browser-final passedall4 onf53a87a4:70HTTP/13metadata/8document
dispatches each,13exactcitationchecks each; openingheadingvisible/focusreturn pass.
Parent inspected en-desktop/zh-mobile reader-only screenshots: wrappedIDs, bounded
plaintext, containedcontrols, nooverlap. Normalizedfrontenddiagnostics compares
1016warnings(930act-env+86otheract) tosealedbaseline: exactsamemultiset,0new.
Sourcefreeze created for current product/tests; finalcollect/backend-full running.
If review requires sourcechanges, this frozen run cannot be claimed for that new
tree; retain checkpoint and repeat the affected final gates with new identities.

Finalcollect9180nodes; parentfullfrontend1765P/type/i18npass. Fresh warning-line
comparison1016==1016 incl930act-env,0new. Complete backend is stillrunning.
Initial census-final launcher failed before publication: wrong sealedbaselinepath
census-final.json.gz. Prior sealedREADME identifies census-post-fix/census.json.gz
as1119/4360/3444 finalsource, and that exact fileexists. Corrected only parent
runner/summaryhelper; rerun census-final-corrected, preserve failedcommand/log.

Task4 review Russell01a091f8-9c50-7513-bf93-a4cef2d5a0db finds3Important:
knownPOSTcompletion afterpendingclose/reopen notreactive; primaryaliasselector
dropspin; indexBack removes selectedsectionoption withoutclearingactivefilter.
Accepted all3; originalArchimedes fixround1 ownsTask4source/tests. Initialcomplete
backend interrupted by SIGINT to verified ownpytestPID2401881 beforefrontendfix;
this partial run is NOT final evidence. Sourcefreeze retained under
source-before-task4-fix1.json. Finalgates willrepeat on repaired source.

Resume checkpoint: Task4 fix1 committed02a0fff4, only3frontendfiles changed;
8 intended RED/83focusedP/1776fullfrontendP/type+i18npass. Soleindexclosed.
OriginalRussell reviewing scopedtask-4-fix-r1-diff.txt. Parent browser
parent-reader-compositions-red failed I3 actualselectvalue empty on IndexBack,
matching review. parent-reader-browser-fixed nowtests all3 compositions against
realstore. Initialbackend-full finished interrupted5008P/12S, no finalclaim.
Parent verification accepts explicit collect-run so fresh artifacts never overwrite
the initial9180-node checkpoint. Archive includes originalTSXreviewprobe.

Task 4: fix round1/5 (3 addressed,0open;f53a87a4..02a0fff4).
Task 4: complete (64a25c34..02a0fff4;specPASS/qualityApproved).
task-4-rereview-r1.md resolves I1/I2/I3 with no new breakage. Parent browser
all4locale/viewports passed84HTTP/13metadata/10documentdispatches each, noerrors;
knowncompletion, primaryalias and indexBack compositions included. Desktop/mobile
reader-only screenshots inspected; controls/text remain bounded without overlap.
Whole-batch review and fresh frozen-source verification next. No parked product
findings; pre-existing frontend act warnings remain byte-normalized baseline debt.

Final reviewer Helmholtz01a09209-42af-7a00-ab6a-d267b36ec014, immutable
final-diff.txt covers3e98bda2..02a0fff4 (10commits/284581bytes). No product changes
allowed during review/gates. Current source-before.json freezes1102paths and
patchc55d413b9ab97c565110e0ea81866a617783b1e0279e2b2280c3f5aaba9ad334.
Fresh sessions: backend-final-fixed87174; final-collect-fixed29484;
frontend-final-fixed62390; typecheck-final-fixed13825; i18n-final-fixed60848;
census-final-fixed15369; browser-final-fixed34018. Vite54743 remains fixture-only.
If final review changes source, retain this checkpoint and rerun final gates.

Parent launcher correction: final-collect-fixed/backend-final-fixed omitted the
explicit tests operand used by prior complete runs. Pytest scanned historical
docs/evidence test copies and aborted during collection with8import errors.
No product/test change or execution-based success claim. Both failed records
retained. Reissued exact prior scope as final-collect-scoped collect tests and
backend-final-scoped backend -q tests. Sourcefreeze remains unchanged.
Other fresh gates complete: frontend1776P/123files, typecheck/i18npass;
browser4compositionspass84HTTP each. Census4346candidates/3460uncertainties,
1133sourcefilesread; review_requiredexit2 retained, not a clean-tree claim.

final-collect-scoped29650 complete9180nodes/exit0. backend-final-scoped25891
running with correctscope. Fresh frontend diagnostic comparison again1016==1016,
zero newwarnings. Freshbrowser19citations percombination verified, not prior13;
both currentandpreviouscensus have identical4newcandidates/166uncertainties,
0coverage/dep/untrackeddrift. No product changes afterfreeze.

Final integrated review complete: specPASS/qualityAPPROVED,0findings in
final-review.md. Reviewed exact3e98bda2..02a0fff4; no source fixes/probes requested.
Reviewer independently checked inverse/source hashes and desktop/mobile images;
no duplicated suite execution. Reviewer closed. Backend stillrunning near47%;
no backendpasscount claim yet. Docs now distinguish implemented document reader
from unfinished Research tool integration and pending final backend/archive gates.

Fixture Vite54743 stopped viaCtrl-C after browserfinal/visualinspection (exit130).
No real App process was controlled. All agentsclosed; only backend25891 remains.
Parent owns threeuncommitteddocs and scratch, indexempty, productsourceunchanged.

Backend now90% with no observed failures. A parent process-inspection command
used an unnecessarily broad ps listing rather than an exact owned PID filter;
that listing was not used for a finding or added to repository evidence. No
process was controlled from it. Further process checks, if needed, must target
only this plan's known command/PID. Test progress comes from its own run log.

Final backend25891 completed:9168P/12S in928.22s (runner931.828s),exit0.
verification.py reconcile --run backend-final-scoped --collect-run final-collect-scoped
passed:9180collected/executed,357added/zero removed, same12skipidentities,
1102source/testhashes unchanged,17currentinverses/63intendedfailuresverified.
All product tasks/reviews/finalgates passed; noexecsessionsremain. Current docs
and evidenceREADME now record completed subsystem versus remainingfirstrelease.
Next seal archive, verify every artifact/index byte, mark final archive checkbox,
commit only own docs/evidence, verify again, remove only this plan's scratch.
Sourceworktree/branch are retained under the explicit no-merge/no-push scope.
