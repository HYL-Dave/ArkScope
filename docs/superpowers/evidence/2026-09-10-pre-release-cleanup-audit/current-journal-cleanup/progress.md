# SDD ledger - plan: docs/superpowers/plans/2026-09-11-current-journal-and-sec-foundation.md

Base: 2842c497dabfdb0b13c315e22b206128eba9f57d.
Spec: docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md.
No production/provider/install/merge/push side effects authorized in this plan.

## Preflight

| Tasks | Shared interface or self-check | Resolution |
| --- | --- | --- |
| 1 / 2 | Old schema is imported by old store and current population | Different files; remove all callers before integrated collection; intermediate collection failures are not product evidence. |
| 1 / 2 | Old projection called by current detail | Task 1 deletes projection, Task 2 removes that call; retain live get_current_review tool. |
| 1 / 2 | Current typed journal errors | Task 1 owns store.JournalError; Task 2 does not define another class. |
| 1 / 2 | Old journal tests vs migration/retirement tests | Task 1 owns old store/review/source/history tests; Task 2 owns old migration/population/current/retirement tests. |
| 1 / 3 | No shared product files | Independent; no premature tool registry edits. |
| 2 / 3 | SQLite backup vs SEC path/config foundation | No dependency; no fabricated SEC export integration. |
| 1 | Absent old code vs retained current contracts | Keep stored IDs/packet keys and useful behavioral tests, not abandoned writer copies. |
| 2 | Removing old schema vs retaining actual data | Code/fixture work only; unknown child references block disposal; actual data cleanup remains gated. |
| 3 | Foundation vs full spec | Exact approved config/path semantics only; feature explicitly not yet user-ready. |
| 4 | Full suite vs concurrent edits | Freeze runtime/tests before integration verification, exact node accounting and scoped independent reviews. |

Task 1: implemented, R4 frozen; independent final review passed (Banach).
Task 2: implemented/frozen; independent R1 review passed (McClintock).
Task 3: implemented/frozen; independent review passed (Halley).
Task 4: independent R4 integration review and complete backend passed; archival
and publication closeout in progress.

Local ignored src/audit directory inspected: only three known Python bytecode
files, no tracked entries; removed with non-force scoped rm -r. No source data.
SQLite read-only research agent: 01a08e00-8618-71e2-a690-136473ab693a (Pasteur).

Baseline controls: 85 passed in 18.02s, baseline.xml (current review/history,
current details and retirement). Full node baseline reuses the archived exact
2842c497 collection, 7978 node IDs. No source/test changes predated these checks.

Task 1 RED: 4 assertion failures in task1-red.xml before runtime edits: three
old modules present, new review owner absent. Runtime moved and old modules
deleted; current source/history tests are being transferred, not assumed green.

Tooling note: installed SDD scripts are not executable. bash sdd-workspace
succeeded; task-brief internally executes sdd-workspace and therefore failed.
Agents receive the exact plan/task/constraints as a file handoff instead; no
plugin permissions or installation files changed.

SQLite read-only finding: upstream UPSERT defect reproduced in isolated memory
on Python SQLite 3.37.2. No matching app SQL or actual-store corruption established.
Distinct WAL-reset fixes require a later reviewed runtime, not merely 3.45.2.

Task 1 additional RED: parent-binding-red.xml proves adding a model_request step
after prevalidation escaped the current in-transaction binding (1 failure).
The header/result/source/schema-only binding omitted the journal steps actually
consumed by as_adoption. Adding ordered step hashes fixes that narrow gap.
Ruling: Include current model steps in the ephemeral validated-read binding -
the transferred approval-integrity owner demonstrated stale-authority reuse -
cost if wrong is an extra safe refusal, not a changed persisted schema/receipt.

Parent unchanged-current controls: parent-positive.xml 122 passed in 16.94s.
Retained helper AST comparison: assessment_id_for, _adoption_values,
_provider_veto and _freshness identical to immutable base.

Task 1 second behavioral RED: task1-tests-call-decode-red.xml, 6 failed/15 passed.
Five failures hold owned source JSON decoding under a rollback-journal read
transaction (prepare/confirm/execute/generic prepare/generic confirm); one adds
an unbound remote call after prevalidation. Existing WAL counterparts pass.
Parent fixed raw capture followed by post-connection decoding for owned reads;
caller-owned reads retain their transaction. Binding now includes ordered calls
as well as steps. Parent-concurrency-green.xml: 46 passed in 14.81s.
Ruling: Transfer the old reader's writer-availability property to current owned
reads, and bind remote-call records as well as steps - RED tests exposed both
gaps in current source adoption - cost if wrong is read latency or a safe
refusal; no schema or live database change is introduced.

Current schema.py docstring no longer promises preservation of an obsolete v1
journal; SQL definitions and schema digest remain unchanged.

Task 2 restored focused result: 149 passed; exclusive backup, connection closure,
external FK dependency and removed web_runs behavior have inverse owners.
Task 3 final result: 128 passed including two unchanged profile controls, with
126 new SEC config/path nodes. No actual capture I/O or registration exists yet.

Task 1 further transfers: four malformed-gap cases and six usage binding/shape/
aggregate cases fail in current reads despite valid payload digests. One malformed
supplied-passages case raises TypeError rather than a typed integrity refusal.
Parent added current read validation using existing URL, source-read and token
observation contracts, plus explicit supplied-passages list checking.
Parent-observations-green.xml: 105 passed, includes current controller/store,
known/unknown/lost-call totals and measured source failures.
Ruling: Preserve old useful diagnostic integrity in the current read owner rather
than deleting its tests with the old journal. Current saved records must have
bound, completed, unique call observations and correctly typed gaps. Bad data is
refused without changing its rows; a digest alone is not proof of valid content.

Task 1 independent review exposed a real producer/validator asymmetry in this
patch: cancellation or deadline after remote completion prevented model_result
recording while already counting its tokens. Parent reproduced 3 failing arms
(including recording failure) with one legitimate success control. The first
parent RED additionally had an incorrect fixture remote-id expectation; corrected
RED is parent-completed-interruption-red-corrected.xml (3F/1P).
Fix: persist the completed observation before counting its usage, without the
pre-dispatch stop check; then check stop/deadline before any further reasoning.
Failed recording keeps totals unknown. Focused restored result:65P.
Ruling: Include the current agent's result-recording producer in Task 1 because
the moved read guarantee otherwise rejects a legitimate interrupted task. This
records already completed work only, never another request, retry or fallback.
Task1 r1 independent review uses task1r1-review-package.md.

Task 2 independent review identified pre-existing case-sensitive FK matching,
contradicting the explicitly required generic external-reference retention. The
implementer is adding canonical SQLite target lookup and upper/mixed-case CASCADE
controls for profile and market, including dependencies introduced after preview.
Ruling: Fix this owned deletion boundary before accepting cleanup; do not restore
abandoned schemas or infer that any production rows were actually affected.

Task 3 independent review passed, foundation only. Parent integration focus at
the preceding snapshot passed684; later final full collection/run will supersede
that bounded count. No frontend result is being claimed for this backend batch.

R1 full run explicitly interrupted before source changes:5299P/12S, exit2,
385.06s. It is not a complete suite. Its XML/root/source hashes are retained with
the before-reservation-fix/r1 names. Independent r1 review found a second
producer mismatch: an in-memory reservation increments before a durable call
exists, so cancellation or failed local recording left saved count1/callrows0.
R2 RED2F/2P includes successful and committed-but-unacknowledged reservations.
Ruling: Add a recorded_model_requests property (local default, current journal
override reading durable calls) used only for stats/completeness. Preserve local
budget enforcement and strict reader checks. Zero durable calls/no replies means
zero tokens; one unresolved durable reservation means unknown tokens. Do not
erase a possibly committed reservation by rolling back the in-memory counter.
R2 focused155P, task1r2 and integrationr2 packages frozen for final review.
Task2 r1 independently passed: canonical SQLite FK identity closes original P1;
164 scoped tests and both inverse mutations remain valid. Actual stores untouched.

R2 review identified final statistics failure entering recoverable action feedback
and a completed observation committed before acknowledgement failure. Parent
promoted both through real controller/store tests; source and agent-action writes
share the same host boundary. RED8F/25P, restored192P including shared contracts,
agent/controller/store/usage and execution cancellation. The local record-failure
owner now deliberately expects result=None with projection's unknown usage;
strict read validation is unchanged. Successful/cancelled/deadline observations
retain their known usage. No-result records retain committed steps and sources.
Ruling: Host journal callback/count-read failure is terminal, not model feedback.
Nested journal_call stops and raises AgentFailure(code,None), preserved through
the agent handler; the existing controller owns conservative final recording.
Uncertain commit acknowledgement is not evidence of rollback and must never
produce inconsistent aggregates or another model call. Failed final recording
still falls back to the existing expired-lease interruption readback, not success.

Final helper fallout: three obsolete fixed two-phase usage-report functions and
their coverage constant had no consumers after the old store was removed. Four
new absence owners RED4F, restored73P. Remaining current usage helpers unchanged.
Frozen R3 task/integration packages and 51 source/test hashes identify the final
attempt at that checkpoint, not completed verification. Review reports preserve
all earlier findings and partial results.

R3 reviewer followed the fatal host failure through read_url.finally and found
record's stop check masked it as cancellation. Parent promoted six real web-source
before/after-commit/normal owners: RED4F/2P, restored206P including current
source-read reports and execution cleanup. R4 changes that one finally call to
journal_call(on_step,...), persisting already-performed I/O without a dispatch
check. The worker is still stopped and awaited; no new remote work occurs.
Ruling: Completed source-read observations follow the same recording policy as
completed model responses; cleanup must not replace the primary persistence
failure with stop_requested. Four negative arms retain failed/code/None and the
source-read report; normal controls succeed. No reader loosened or data repaired.
R3 full explicitly interrupted before editing:4724P/12S320.78s,exit2. Its XML,
fixture root, collection and source hashes carry before-source-cleanup-fix/r3
names. Only a reviewed final snapshot will be used for complete verification.

Task1R4 independent55P/13.683s, 35taskpaths verified; no remaining blocker.
IntegrationR4 independently verifies51frozenpaths and freshR4census/hash/collection;
no remaining source correction requested. Both keep full acceptance pending the
parent run. R4collection8128vsbaseline7978:191removed341added net150. Earlier
stopped runs are never added together to manufacture a complete suite.

Final R4 complete backend8116P/12S772.31s,exit0. Exact8128collection/execution
equality,191removed341added, same12skipIDs; verification-summary.json records all
IDs and file deltas. All51source/testhashes unchanged after execution and local
source commits e2f77cb7(cleanup) /3095e1ad(SECfoundation). No frontend claim,
production operation, runtime upgrade, provider request, merge or push.
