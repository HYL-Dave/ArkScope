# SEC Research Release Integration

Checkpoint evidence for the September 13-14 continuation of the
[approved plan](../../plans/2026-09-12-sec-research-release-integration.md).
**Release acceptance is blocked by ImportantN1.** Publication recovery and
Task7 scheduling are complete and independently reviewed; Task8 is incomplete.
This is not a complete-regression, merge or actual-store rollout approval.

## Publication Recovery

The reported post-publish/pre-register hardlink defect was reproduced on
disposable stores, repaired at `d2f491c1`, and independently approved. Writer
recovery commits accounting before removing only a proven redundant staging
alias. Strict administrative inventory remains unchanged. The
[separate repair packet](../2026-09-13-sec-publication-recovery/README.md)
retains the original failed probe, negative controls and restoration proof.

## Scheduled Acquisition

Task7 adds default-disabled current-universe acquisition of recent submissions
and Company Facts, using shared scheduler controls and source exclusion.
Unresolved members, deferred issuers, source attempts and successful acquisitions
have distinct accounting. Fixed document versions and Research references are
not replaced by scheduled refreshes.

Initial source `936ede10` passed its focused tests, but independent review found
three additional defects: mixed-gap terminal publication, moving-map resolution
and terminal membership accounting. These were repaired in `883b0185` and the
scoped re-review approved them with2493 backend/449 frontend focused passes.
The initial passing runs and failed review remain checkpoints, not final
acceptance. Task7 source implementation is complete; actual activation is not.

## Final Review Repair

The two combined release workflows at `a77a7c2e` pass along with seven existing
owners and have a clean scoped review. Whole-change review then found a nested
event-loop error in delegated SEC execution. `911d69a2` repairs that execution,
SDK cleanup ownership and missing child citation forwarding, while retaining
public sync dispatch and removing test-only private sync wrappers. Existing
citation validators/event formats remain unchanged. No citation authority is
taken from delegate-answer JSON.

Final focused covering: **1349 passed in19 files**; restored focused194passed;
three final-source inverses kill their behavioral owners. All36 attempts and
intermediate fixture, cleanup and SDK-lifetime failures are preserved. The
independent scoped re-review accepts the three named repairs, but finds **N1**:
changing the OpenAI delegate to async moves the Anthropic child's still-blocking
SDK stream onto its parent's event loop. This is high-confidence static source
evidence, not an executed held-stream heartbeat test. It can stall cancellation
and other work sharing the loop during child model I/O.

The controller accepts N1 as a blocking regression. The proposed next repair is
an awaitable Anthropic child client preserving captured auth/model/effort and
joined cleanup. That client-factory scope was put to the user; it is not silently
included in this fix wave. The branch remains unmerged. See the
[complete scoped review](checks/task8-final-rereview-01.md),
[fix report](checks/task8-final-fix-report.md), and
[all rulings and costs](RULINGS.md).

## Current Verification

| Check | Observed result |
| --- | --- |
| Frontend at911d69a2 |1833passed /126files |
| Typecheck/build/i18n literal check |Passed; raw act and bundle-size warnings retained |
| Complete backend collection |11023nodes; not executed as a complete suite |
| Final complete backend |**NOT RUN**, deferred until blocking N1 is repaired |
| Source/runtime/runner comparison |1158files unchanged; same source digest and SDK/runtime identities |
| Current proof readback |13schedule proofs, publication repair, three final-fix inverses and140 final-fix artifact hashes verified |
| Receipt accounting |168runs /81nonzero, all classified, none unfinished; overlapping runs are not summed |
| Census |4400candidates/3579uncertainties; review_required remains |

The full census comparison is identical to the previous workflow checkpoint:
70new candidates (68consumed locale leaves, two intentional entrypoints),
671uncertainty IDs and five already-reviewed removed source files. Reconciliation
maps541 positional records and retains130 substantive/unresolved records under
their current owners. Dependency metadata and main-worktree untracked-name drift
are zero. Exact records are retained in
[current census adjudication](checks/task8-census-adjudication.md).

Task7's actual-service browser proof covers both locales at1280x960 and390x844,
including pinned content, dirty budget and shared schedule controls. Its source
anchor is883b0185, not a claimed fresh browser run at911d69a2; the relevant UI,
SEC-service/API and scheduler paths are byte-unchanged between those anchors.
The new delegated-reference behavior is exercised by actual native-loop and
durable-readback backend owners. No live SEC or LLM behavior is inferred.

The sealed `checks/manifest.json` binds640 selected files /13565877 stored bytes,
including original and archive hashes. It
excludes generated databases, HOME/credentials, binaries and unrelated scratch.
The active plan workspace is retained for the blocked follow-up, not deleted
under a false completion claim.

## Verification Scope

Only generated SEC bytes, disposable databases, injected failures and local
browser fixtures are admitted. No actual provider/model call, production
DB/config/credential access, package install, App restart, cleanup/reset,
export/restore, merge or push is performed by this continuation.

Portable SEC bundles contain the whole market database and SEC objects, not a
separate profile or SA database. Moved-root reopening on the tested filesystem
is not a whole-installation or Windows deployment claim. Maintenance remains an
operator command, not a browser/model capability. See the
[operations guide](../../../design/SEC_RESEARCH_OPERATIONS.md).

SQLite3.53.4 candidate validation is not activation. The unchanged application
test runtime still uses3.37.2. App-private deployment direction, packaging and
the stopped-writer backup/integrity/switch window remain separately admitted
work. Wider C12/C15/C20 cleanup and the i18n/SQL census queues also remain open;
source candidates alone never authorize deletion of retained data.
