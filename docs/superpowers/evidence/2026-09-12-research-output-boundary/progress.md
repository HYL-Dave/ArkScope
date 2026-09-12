# SDD ledger - plan: docs/superpowers/plans/2026-09-12-research-output-boundary.md

Base: 18d46062c30da87b30666b1ba0f290872a28fa7f.
Independent worktree: /tmp/arkscope-research-output-boundary.
Older SEC work remains untouched. Planning history is retained below the checkpoint.

## Current Checkpoint (Supersedes Earlier Planning States)

Tasks 1, 2 and 3 are complete with independent task review. Task 4 is in progress.
Product/test freeze: ff7c4d753ab0868aaa07a330841e0dd1de96f72c; source-freeze-04,
1111files collectionSHA 36af98c16502f53a9f96a90e8f86b35921a723b98c4ead5a87bf3ec0c47f86e8.
Complete backend backend-full-04/session19568 finished, exit0:10166P/12S in
1093.18s pytest (1097.131s runner). Session closed; no owned check process remains.
source-freeze-05 agrees with04 on all1111files/runners/runtime. Parsed validation
confirms857newcases and7retained safety-owner families all ran without skips.
The12skipsareunchanged manual live tests (2SEC/9IBKRscanner/1IBKRoptionchain).
JUnitSHA d0c9a9d978603a0c2f7d2fb94cfef345ff41aa03695bf1e1f69f06f8acf170ea.
No further product/test/runner edits. Source is committed and worktree clean.
Complete backend attempt: backend-full-03 was deliberately stopped with SIGINT
before any new product/test edit. Session55701 closed with exit2 and partial
8068P/12S; this is NOT a complete pass. The original logs/JUnit are retained.
Previous backend-full-02/session95591 completed10148P/12S/1F: closed EIR-006
census missed the new test_tool_output_policy.py roster. Commitd42f29ce adds
only that exact _TEST_FIXTURES path; no product, assertion or discovery change.
Focused RED1F/1P, GREEN189P, inverse1F/1P, restored189P. Original failure retained.
Final reviewer received the exact49491831..d42f29ce supplement1060bytes SHA
eee61a258e4c7ff08a62d965473aa6f5f527219846f93fcf04b3ea5e5fbaf037.
Final blind reviewer Gauss01a09589-7a92-7aa1-a5c8-8f91481a6ff2 terminated with a
platform safety error and no verdict; agent closed, no evasive retry. See
whole-branch-review-blocked.md. Final independent gate remains open for external
review, so Task4 cannot be marked fully complete. Keep branch unmerged.
Other task agents are closed. No owned complete-backend/check process remains.
The final review's completed synthetic probe demonstrated a missed compaction
error-log sink (its two passing probes assert the presence/absence of a leak,
NOT safety). It supplied no overall review verdict. Coordinator owns the local
defensive follow-up in compressor/summary_callers.py, compressor/layers.py and
new tests/test_research_output_compaction.py. Built-in summary calls register
only their already-selected client key before use, inherit the execution guard,
sanitize diagnostics inside that scope, and reject credential-bearing summary
text before returning/installing/capping it. Generic caller exceptions use the
same diagnostic boundary. Preserve model/prompt/retry/budget/circuit behavior.
The compaction fix is committed in ff7c4d75: RED10F/7P, three inverse groups
RED2F, 4F/2P and 4F/4P, restored focused1046P/0F/E/S; see compaction-report.md.
A fresh complete backend has passed after this fix;
the unavailable independent final review is not retried or treated as approval.
Frontend1776P/typecheck are done. census-final-04 is complete:1144files read,
4347candidates/3471uncertainties, zero new candidates/reductions/dependency or
untracked drift;11newuncertainties classified6testimports/5literalrelocations.
Baseline1134readablehashes agree with18d46062. exit2/review_required preserved.
Final code-only external-review.diff is363257bytes SHA
2b0909ce9c2abc4651518116503ac23a541ee5ffcca472c8864856b3593c07c8.
It is prepared for user/external review, not another platform review retry.
Final evidence sealing is next. The complete source recheck is done; the final
independent review remains open. Scratch is retained because that gate did not
approve; no integration/merge is performed. Report automated and review gates
separately, not a fully complete security/SEC release.
Task2's final header-context rule supersedes the earlier bare-Bearer planning
note below. Historical RED/fix/invocation-failure records are intentionally kept.

## Preflight

| Tasks | Producer / consumer or self-consistency | Finding / ruling |
| --- | --- | --- |
| 1 / 2 | OutputGuard.check and context consumed by result admission | Same signatures; no domain imports in guard. |
| 1 / 3 | OutputGuard.stream and scope consumed by event/lifetime integration | Same signatures; Task 1 adds explicit inherit=False scope keyword so unrelated executions default isolated. Child/reentrant adapters may explicitly inherit. |
| 1 / 4 | Primitive tests and inverse evidence consumed by final gate | Actual JUnit and hashes, not remembered counts. |
| 2 / 3 | Both OAuth files; policy then stream integration | Sequential commits/reviews, never concurrent edits. |
| 2 / 4 | Adapter equality and registry policies consumed by census/review | Parked SEC nodes absent in this branch; not counted as fixed. |
| 3 / 4 | Event/persistence boundaries consumed by final audit | Include managed durable events, not only final answer. |
| 1 self | Primitive tests versus new module | No full-context buffering; explicit finish/abort, split owners. |
| 2 self | Registry lacks output contracts today | Inventory names/shapes first; result policy is new work, not presumed infrastructure. |
| 3 self | Drivers differ; native agents persist before yielding | Must guard producer-side scratchpad/replay too. Coordinator will inventory exact paths before dispatch. |
| 4 self | Complete run versus SEC feature checkpoint | Distinct immutable base/dirty feature patch; never combine counts. |

Ruling: create-only new git worktree checkout with per-command git-crypt smudge
passthrough after the standard checkout could not load its key. Encrypted
tracked documentation remains ciphertext. No key access, config modification
or decrypted-file copy; clean status verified. This affects no product path.

Ruling: root guard scopes default isolated, explicit inherit=True shares only
an already-active execution guard. Child credentials registered there remain
available for late callbacks. Registration must precede provider use; no
retroactive secrecy claim for text emitted before a newly introduced secret.

Ruling: use reviewed offline runner copies from tracked SEC document evidence,
not another plan's scratch. The original runner ROOT derivation is correct in
this plan's scratch location. No provider or production access permitted.

Task 1: executing; Franklin 01a094e1-56e4-7a51-a836-6d53fe2d9342.
Pre-dispatch base e0b0ed4aafd1fce1687ff7fa6b7dc6e391c9a469.
Initial core commit 2f0cedeb; independent review dispatched against immutable
initial commit. Coordinator identified pending shared-thread registration/cache
publication risk and notified implementer. Do not mark complete until resolved.
Concurrency fix committed f2068c75. Reviewer Meitner
01a094f7-5853-74b1-828c-b3584c2f17a3 has the separate scoped fix package;
review gate covers both core commits. New deterministic race RED/GREEN evidence
exists at task1-red-concurrency-22 / green-concurrency-23.
Task 1 fix round 1: reviewer resolves concurrency but finds marker-composition
P2. A registered secret containing the complete marker can be constructed by
replacement across both edges. Franklin assigned RED -> one-condition guard fix
-> GREEN/inverse; f2068c75 is fix-round base. Task2 product GO still withheld.
Fix round 1 implemented 5f22762d747743185b808c7c21cf19d25077c312:
83 primitive tests pass, specific marker inverse reproduces8failures then
restored. Meitner assigned scoped re-review of only outstanding P2.
Task 1: complete. Meitner task-1-rereview.md approves final5f22762d,
all initialreviewfindingsresolved. Final83primitive casespassed; 112previous
focusedcountincluded38oldcontrols and isnotcombinedwith83.
Task 2: RED preparation dispatched only; product edits and commit gated on
Task 1 approval. Disjoint new tests may be authored during core review; they
must not mutate or commit core files. Base for final task diff will be recorded
after core fixes and before Task 2 product GO.
Worker Erdos 01a094f7-e384-7f81-a3b3-56a52d323ce2.
Task 2: implementing. RED preparation 279failed/9passed/0errors/skips.
Explicit GO sent afterTask1gate. RecordedTask2base
a81e4d92b5b9649dafbab6dbf7dee8ded181aa41; onlynewtestsareuntrackedatdispatch,
coordinatorplanupdatesremainunstaged. No core-fileownershiptransfer.
Task2 implementation delivered3e73d2aa8e1fb5925b388178f02e623e291a12df,
exactparenta81e4d92. Coordinatorverifiedcleanindex/11filelist and parsed final
task2-final-green-20260912-17 JUnit716passed/0fail/error/skip. Sixinversegroups
areREDthenrestored aslisted in task-2-report.md. Independentreview nowpending;
Task3 remainsRED-only untilreviewgate. Do not treatTask2ascompleteyet.
Task2 review byDescartes01a09522-57d4-7ee0-b665-3b3c7ca8722b needsfixes.
Important: nakedBearerpatternrejects legitimatefinancialprose (textandJSON),
independentrepro1failed/1skantcontrolpassed. Minor: OpenAIwrapperdropshandled
errorspan annotation while disablingSDKrawerrorcallback. Nootherfinding.
Ruling: narrowunknownBearerrejection toexplicitAuthorization/Proxy-Authorization
headercontext; barefinancialwordsstaypublic. Knownexactbearersremainprotected
andprovider-keyprefix/credentialfieldguardsremainunchanged. Thiscorrectsour
initialoverbroadauthliteralcontract, notanSECexception. Fixedcontent-onlyspan
errorannotation restoresobservabilitywithoutSDKrawargs/errorlogging. Assign
both toTask2fixround1, base857359e3, RED/GREEN +scopedre-reviewrequired.
Fixround1delivered41b9f2b5384881dc0daa04f5c25720b1e9a8660a, exactbase857359e3;
4authorizedfiles,754focusedpassedafter3inverserestorations. Reportandimmutable
fixdiff handedtoDescartesforscopedre-review; nofullTask3GOyet.
Task 2: complete. task-2-rereview.md approves41b9f2b5; bothImportantBearer
andMinorspanfindingsclosed, nootheropenfinding. Coordinatorcheckpoint04
independentlyparsesrestored754P/0F/E/SandmatchingJUnit2c7bc1be55269718b3447817ee2a80b690a96fc00f7255110499bfdd4600963b.
Task3sharediteratornarrowGOdelivereduntrackedoutput_events.py,17primitiveP;
twoinverseownersREDthenrestored, noexistingproductedits. FullTask3GOisnext,
with allassignedexistingproducer/nativeadapter/runtime/persistencesites.
Task 3: implementing fullGO, recordedbase97b02d2b825159b09e88a4df2c51952fa3dffe30.
Hooke01a09508-9333-71d3-a763-22f350cbb409 owns contractlistedpaths. Task2complete,
itsworker/reviewerwillnoteditexistingfiles. Source/testuntrackedfromnarrowphase
areincludedinTask3finalcommit, notmistakenforforeignchanges. No core/resultpolicy
changeswithout concretefinding andcoordinatorownershipruling.
Task3coordinatorcheckpoint06: integration361P; broaderfocused-pre-collateral-19
is1020P/2F (noerrors/skips). Twofailures areexpectedcontractcollateral:
timeoutowner assumesoneSSEtextchunk, cleanupowner assumesdecoratedstream
entrypointis itselfanasyncgeneratorfunction. Statefultrustediteratorchanges
bothshapesintentionally. Ownershipextended ONLY to these two tests in
tests/test_chatgpt_oauth_driver.py and tests/test_openai_sync_surface_cleanup.py.
Ruling: timeoutmustassertsameconcatenatedtext/nontextorder/continuedmodelcall
andnosyntheticterminalerror, notchunkcount; cleanupusesunwrappedgenerator
identityplusrealnewiterator/lifetimeowners, notjustcallability. Do notrelax
timeout,actualentrypointavailability,orunrelatedassertions. KeepREDrecord.
Task3delivered29f18ca7364d04968d3273252b998e2a4fe32780, exactparent97b02d2b;
15authorizedfiles, focused1022P/0F/E/S, all361newowners+3integrationinverses.
IndependentTask3reviewpending. Product/testsnowfrozenforcompletebackendand
read-onlyreview; nofixes/newtestedits untilsuitefinishesorcoordinatorstopsit.
Source inventory complete: 54 definitions, 50 JSON and 4 public text, plus
bridge-only delegation. See inventory-results.json and task-2-contract.md.
Ruling: public tool content retains explicit auth-literal rejection (Bearer /
fixed provider-key prefixes) as a declared content restriction, not generic
entropy-based redaction. Existing unknown sk-ant result owner stays meaningful;
long public words/identifiers are unaffected. Normal prose is exact-guard-only.
Spec records this distinction rather than silently weakening a safety test.
Task 3: RED preparation only, disjoint tests/test_research_output_events.py and
tests/test_research_output_lifetimes.py. Product edits/commit gated on Task2
review and coordinator GO. Must not edit any concurrent Task2-owned file.
RED preparation ready: Hooke01a09508-9333-71d3-a763-22f350cbb409 reports
task3-red-final-04 =339failed/22passed/0errors/skips,361nodes. Events308RED/21pass,
lifetimes31RED/1pass.318failures exercise existing behavior,21missing-wrapper
assertions. No product GO untilTask2 independent review. Interfaces match
task-3-contract.md, including exact-type/same-guard idempotence and per-advance
ContextVar activation. Worker is holding with no staged changes or commit.
Ruling: unblock only Task3's new output_events.py implementation while Task2
review runs. It consumes already-approved Task1 guard interfaces and writes no
Task2-owned file. Worker may refine its two new tests for that primitive only;
no other product edits/staging/commit. OAuth/native/lifetime wiring stays gated
on Task2 approval, and the finalTask3base will be recorded at fullGO. This avoids
idle serialization without allowing concurrent edits or claimingTask2approved.
Ruling: fullTask3GOwillinclude bothnativeagents' tools.py forpre-handlerinput
checks. Concreteowner: OpenAISDKon_invoke dispatchesbeforeagent_extract_tool_info,
so guardingonlylaterproducertracecannotpreventwritesorSDKargumentlogging.
Task2ownershipremainsuntilitsreview; narrowGOdoesnotincludeexistingfiles.
Task 4: pending.

Task4 executing: backend-full-01 ended before tests because invocation omitted
the tests/ path and collected historical evidence modules. Eight collection
errors are runner invocation failures, not product regressions. No backend
session remains running. Correct full retry requires explicit tests/.
Confirmed sibling: codex_account_usage._model_identifier uses redact as an ID
validator. Coordinator owns only that module and new
tests/test_model_catalog_output_boundary.py for a local RED/GREEN/inverse fix.
Register the supplied record's already-captured access/refresh/ID tokens inside
the authenticated callback, before model/list, so prior auth failure order is
unchanged. Shared local guard scans complete pages before cursor reuse and the
returned plan string; no token store access or ambient guard borrowing. Keep
lexical ID limits and explicit JWT algorithm-header syntax rejection, not
generic entropy. Existing subscription JWT owner stays unchanged. Task3 review
remains immutable97b02d2b..29f18ca7 and its files are not edited by coordinator.

Task3 review Newton task-3-review.md: I1/P1 raw exc_info cleanup logging can
expose captured bearer; I2/P2 cancellation during terminal close interrupts the
finalizer and loses cleanup ownership. Both demonstrated by owned offline
probes, not production disclosure claims. Fix round1 assigned to Hooke with
base29f18ca7 and only chatgpt_oauth_driver.py/output_events.py plus the two
Task3 test files. Preserve success answer, cancellation propagation, scope
reset, non-reentrancy and pending-tail discard. Close work must be owned and
awaited after cancellation, never just a detached shielded task. Do not change
timeouts/retry/session or diagnostic shared rules. Independent scoped re-review
required. Coordinator catalog work is disjoint and must not enter worker commit.
Coordinator also corrects only _redact_bridge's obsolete zero-false-positive
docstring in claude_code_sdk_driver.py to diagnostic-only use. No behavior change
or overlap with Hooke's four-file fix scope. Include it in coordinator commit.
Frontend-full-01: npm reporter initially wrote its new JUnit file under the web
worktree because outputFile was relative. After successful process completion,
coordinator moved only that new generated file (mv -n) into
frontend-full-01/results.xml. command.json/output.log retain the original path;
no source or test expectation changed. Future runs should pass an absolute
path under their own run directory. Frontend sources have no diff from base.
Task3fixround1 delivered fdc947d22991703594715210eed917232cc38c55, exactparent29f18ca7,
four authorized files only. Restored focused1026P, newownersplusreviewprobes7P;
I1/I2 inverses all RED then restored. No hung run or active mutation; worker
delay included installed SDK/direct-caller task-affinity inspection, which found
no blocker for the admitted 0.2.152 runtime. Newton scoped rereview is pending.
Coordinator catalog/docstring/spec/plan commit49491831523abd181f19430754329a8e544a92aa
now follows fdc947d2. Source-freeze-02 pins1110files, collectionSHA
c8d6cbd42f301fadca4797a0f5e560c2341f51609c5841ddb859a85037012daa.
backend-full-02 (-q tests) is running against this frozen source; census-final-02
and final AST call inventory are read-only. No product/test changes until the
run completes or is explicitly stopped and recorded. Frontend1776P/123files and
typecheck passed against unchanged frontend sources; no UI behavior claim beyond
automated regression coverage. Whole-branch independent review remains required.
Task 3: complete. Newton task-3-rereview.md approves fdc947d2; I1/I2 resolved,
six fresh cleanup-outcome probes passed, no remaining scoped finding or SDK
task-affinity blocker. Whole-branch review will be a fresh blind security seat,
base18d46062..candidate49491831, with code/test patch only and no prior result
claims or implementation rationale. backend-full-02 continues frozen.
Final reviewer Gauss01a09589-7a92-7aa1-a5c8-8f91481a6ff2 dispatched fresh without
history/model override. Patchfinal-review.diff343634bytes SHA
9c4fc4a430259fce4ecfd3153ffe572e002ac56b05fc795ebce557d658f9b15b.
Task3 worker/reviewer closed after approval; no associated test sessions running.
Final census/read-only AST scan complete. Baseline1134source hashes verified,
final1143read, 0newcandidates/0reductions/0dependency/untracked drift;
11newuncertainty IDs classified6testdynamicimports+5identicalrelocatedliterals.
Report still exit2/review_required; this is no deletion waiver. Final AST40calls
across364modules, all remaining contexts classified in residual-classification.md.

Ruling: final census uses the archived 2026-09-12 document-reading final-fixed
checkpoint, not the older 2026-09-11 query checkpoint. The final interpretation
must verify scanned product hashes against base18d46062 and report any mismatch.
The source scanner currently opens a tracked historical .superpowers report.
Our launcher classifies all .superpowers paths as excluded_plan_workspace before
read_sources opens files, honoring per-plan isolation without changing the
product scanner or deletion candidates. Report this coverage change explicitly;
it is not evidence of source removal or a candidate waiver.
Baseline identity probe found9archived-source mismatches against18d46062,
all recorded in census-baseline-check.json. That older archive is not an exact
baseline. Superseding ruling: generate census-base-01 directly from reviewed
base git blobs with the same scanner (all3scanner source hashes verified), no
checkout or private/scratch read. Final census compares this exact-base report;
both scans apply the same excluded_plan_workspace classification. Node modules
are reused by an ignored worktree-local symlink to existing main dependencies,
not installed or modified. This fixes evidence attribution, not product code.
Census-base-01 exited1 before publication: TypeScript is in main root
node_modules, not its web-specific node_modules. Added the same ignored
root dependency symlink (no install); corrected attempt named census-base-02.
Final comparison points to -02, while -01 failure record remains intact.

Baseline existing-output-01: 308 passed, 0 failed, 0 errors; probe/runtime
binding/card execution/ChatGPT OAuth/Claude OAuth files. Offline runner finished
successfully before any adapter implementation, 15.229s command duration.
Producer/sink inventory complete for Task 3: task-3-contract.md. Required extra
paths and generator context-lifetime decision copied into tracked plan.

Ruling: correct our spec's over-broad normal-finish tail policy. A known JWT
starting ey... must not corrupt the complete word source merely because its
last letter is a credential prefix. Normal finish flushes unmatched suffix;
abnormal abort/cancellation drops pending undecided suffix. Every complete
credential remains blocked across every split. Task 1 notified before commit;
separate positive/negative owners required. No claim to suppress every possible
partial credential substring, which is incompatible with ordinary content.

Baseline-tool-channels-01: command error (nonexistent test filename), no tests
ran; not a product failure. Corrected -02 ran real agents/subagent/tools files:
120 passed, 0 failed/errors, 5.423s. Evidence retained for both commands.

Task 1 implementer report received, final f2068c75: 112 passed (74 new primitive,
27 unchanged probe, 11 unchanged security wrapper), no fail/error/skip. Five
inverse groups were RED then restored; concurrency two-case RED fixed separately.
Not combined with coordinator baseline totals. Independent gate still pending.

Coordinator synthetic stream-cost observation (core-stream-cost-01): one test
passed, 2051-char synthetic bearer / 10400 public chars / 3-char deltas, 0.9406s
matching and first emission after2736 inputchars. No provider/token read. Ruling:
Task 3 must use idempotent trusted iterator protection, not double rolling buffers
at producer and manager. Exact interface and closure rules in task-3-contract.md.
