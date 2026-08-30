# Lifecycle Automation Reliability and Control-Plane Design

Date: 2026-08-30
Status: revised design accepted for RED-first implementation

## 1. Goal

Make security-lifecycle automation observable, recoverable, manually
triggerable, and configurable without weakening its deterministic evidence
policy or allowing an unattended profile mutation by default.

This design repairs verified defects in the existing implementation and adds a
bounded control plane. It does not add an LLM to lifecycle decisions. The
decision policy remains a pure deterministic projection over cited SEC,
listing-authority, and conditional IBKR evidence.

## 2. Verified Findings and Corrections

### 2.1 Refuted original deadline failure

The public SEC producer clears multiple deadline dates and emits
`sec_evidence_insufficient` before the scheduler receives them. The two
`ValueError("source_deadlines")` checks in the scheduler are therefore not
reachable from the real producer contract. Tests that inject multiple deadline
rows directly into the scheduler prove only a bypassed seam.

The clearing behavior is still defective. It removes the date that can trigger
the conditional IBKR check, the non-retryable `not_confirmed_as_of` branch, and
the byte-exact deadline citation. The repair must preserve explicit
supersession semantics instead of turning a resolvable extension into an empty
set.

### 2.2 Orphaned running runs

An interrupted process can leave an automation run in `running` forever.
Reservation then skips it permanently, while the lifecycle projection reports
`automation_running` with no next check. There is no lease or reaper today.

### 2.3 Finalization wedge after attended acceptance

An automation-authored assessment may be accepted by a human. The terminal
finalization path currently accepts only
`acceptance_authority="automation_policy"`, so a valid human acceptance raises
`automation_assessment_not_accepted`. The worker returns a failed counter but
does not change the already-succeeded run. Every later tick repeats the same
failure and consumes a batch slot.

`fail_run` cannot repair this state: it intentionally rejects a succeeded run
that already owns a current assessment. Human acceptance is a valid terminal
authority and must complete the existing finalization idempotently.

### 2.4 False recovery and silent incidents

The current failure witness treats the next empty or blocked batch as recovery,
even when the failed case was merely skipped and its run remains failed. The
same aggregate contract does not identify which selected case produced which
outcome. Repeated identical failures are deduplicated, after which the false
recovery can leave the unresolved incident invisible.

### 2.5 IBKR candidate overflow

The scheduler permits up to 64 aliases and 32 conIds per ticker, while the IBKR
reader accepts at most eight contract queries by default. Seven aliases can
therefore raise `ibkr_identity_candidates_exceed_max_queries`, which is stored
as a permanently parked `source_payload_invalid` run. More than 64 aliases can
raise while loading all cases and fail the entire batch.

Silently truncating the candidates is not allowed. A lookup over an incomplete
identity set cannot produce authoritative `contract_missing` evidence.

### 2.6 Repeated SEC acquisition

Retrying a listing-authority blocker currently deletes all run evidence and
facts and then reacquires SEC first. A complete SEC filing chain becomes stable
after the observation's widened 120-day window has closed; reacquiring it after
that point cannot discover a newly eligible filing. Inside that window, SEC
must still be refreshed because a later filing can change the result.

### 2.7 Retired news adapter

`security_lifecycle_news_evidence.py` is an uncalled, retired publisher-evidence
acquisition adapter. It is not the historical read path. Existing publisher
rows remain readable through the investigation store, but no current
automation path may call this adapter or admit publisher material into the
decision policy.

## 3. Invariants

- No lifecycle decision or transition authority comes from an LLM, publisher
  article, a single quote value, or an unavailable provider.
- `AUTOMATION_POLICY_VERSION` remains semantic authority and is never used as a
  retry button.
- Manual and automatic retries preserve every earlier run, assessment,
  evidence row, fact, blocker, and transition.
- A bounded lookup that omits identity candidates may return ambiguity or
  unavailability, never absence.
- Background decision automation and automatic profile mutation are separate
  authorities.
- Automatic profile mutation is disabled by default.
- No profile schema migration is introduced in this slice.
- Runtime stage progress is explicitly ephemeral. Durable terminal state and
  interrupted-run reconciliation are separate mechanisms.
- No provider call, production database operation, App restart, merge, or push
  is authorized by this design.

## 4. Execution Ownership and Orphan Recovery

### 4.1 Cross-process ownership

Lifecycle automation owns a dedicated non-blocking file lock under the existing
ArkScope lock directory. Scheduled and attended triggers use the same lock. A
second process receives a typed `already_running` result and does not reserve a
run.

Each reservation writes a bounded `execution_owner_id` into
`query_context_json`. The owner is an opaque random process-run identifier; it
does not enter semantic run identity, decision provenance, assessment
authority, or transition authority.

### 4.2 Reconciliation

After acquiring the cross-process lock and before selecting new work, the
runner reconciles any persisted `running` rows. Exclusive ownership proves
that no other automation runner still owns them. Each orphan is terminalized
as `failed/internal_error` with a safe `interrupted_execution` diagnostic.

The runner also uses a `finally` block that covers `BaseException`. Before
releasing the lock, it finds any still-running rows bearing its owner ID and
terminalizes them. A hard process death releases the OS lock; the next process
performs the same reconciliation.

This is a single-scheduler-owner contract. It does not pretend that an
in-memory stage callback is a lease.

## 5. Terminal Finalization

For an automation-authored assessment, both of these accepted shapes are valid:

```text
status = accepted, acceptance_authority = automation_policy
status = accepted, acceptance_authority = human
```

Finalization reuses the existing assessment and idempotently generates any
missing action proposals. It must never rewrite a human acceptance back to
automation authority.

When finalization fails after an assessment exists, the kernel cannot call
`fail_run`. It instead records bounded finalization metadata in the same run's
query context:

```text
terminal_finalization_failure = {
  code,
  failed_at,
  attempt_count,
  retry_not_before
}
```

Only closed, user-safe codes are allowed. The lifecycle projection treats an
unresolved finalization failure as Attention, not as a completed case. A due
finalization retry reuses the same succeeded run because its assessment and
decision provenance are already durable. Retries are bounded; an attended
Run-again action may explicitly resume the pending finalization.

The automatic retry schedule is closed: after the initial recorded failure,
retry after 15 minutes, then 1 hour, then 6 hours. A fourth recorded failure
has no automatic retry time and remains Attention until an attended Run again.

## 6. Per-Case Results and Recovery Witnesses

The worker result gains a versioned per-case outcome map:

```text
result_version = 2
case_outcomes = {
  <case_id>: accepted | drafted | blocked | failed | skipped_current
}
```

Existing counters remain and must equal the map. The reader continues to
accept version-1 stored blobs. No row backfill is required.

A blocked case is a completed automation attempt with an explicit blocker; it
is not an operational scheduler failure. It remains visible in lifecycle and
automation status surfaces, but does not create a failed `job_runs` witness.

A case-processing recovery is written only when every failed case from the
active incident has a newer non-failed attempt or its pending finalization has
completed. The decision is derived from per-case automation-run rows, not an
empty tick summary. Scheduler-level failures with no case IDs recover only
after a real successful scheduler invocation.

Identical unresolved incidents are not appended every 30 seconds. The latest
failure witness remains authoritative, and the status endpoint exposes it as
an active incident until genuine recovery.

Scheduled and attended production callers persist the bounded result before
releasing the shared execution lock. This binds each result to the run rows
created by that invocation without widening the public result DTO with an
internal run identifier. A blocked attempt is a completed, non-operational
invocation: it may clear a scheduler-level operational failure while its
policy blocker remains visible on the case.

## 7. Retry and Manual New-Attempt Authority

### 7.1 Default reservation remains unchanged

The existing no-replay behavior remains the default. `reserve_run` receives
explicit opt-ins used only by controlled callers:

```text
allow_due_failed_retry = false
allow_new_attempt = false
```

The scheduled runner sets only `allow_due_failed_retry`. The attended case
endpoint sets `allow_new_attempt`. Neither flag changes semantic policy or
decision provenance.

### 7.2 Attempt chains

A new attempt stores `predecessor_run_id` and derives a distinct execution key
from the semantic key, execution revision, and predecessor. Existing
`predecessor_failed_run_id` rows remain readable.

Retry counts are computed by following the persisted predecessor chain with a
visited set and a small hard traversal bound. Counts are not copied into the
new attempt's context, because reservation constructs new context from the
current caller input and does not inherit the predecessor context.

### 7.3 Automatic retry classes

Automatic retries are deliberately narrow:

- `persistence_failed`: at most three new attempts after 15 minutes, 1 hour,
  and 6 hours;
- `source_payload_invalid`: at most one new attempt after 1 hour, covering a
  transient invalid SEC response without creating an infinite parser loop;
- `internal_error`: at most one new attempt after 1 hour;
- `extractor_failed` and `profile_schema_mismatch`: attended retry only.

The failed row stores only the closed retry class and `retry_not_before` in its
query context. The schema `retry_at` column remains NULL for failed rows, so its
existing `status='blocked'` CHECK remains unchanged.

### 7.4 Attended endpoints

```text
GET  /security-lifecycle/automation
PUT  /security-lifecycle/automation
POST /security-lifecycle/automation/run
POST /security-lifecycle/cases/{case_id}/automation/run
```

The global run processes only due work. The case route explicitly creates a
new attempt for failed, blocked, or completed cases, or resumes pending
finalization. A currently running case returns HTTP 409. Both POST routes are
fire-and-return and use the shared execution lock.

## 8. Evidence Acquisition Repairs

### 8.1 Deadline supersession

`SecSourceDeadline` gains transient, non-persisted extraction metadata:

```text
kind = current | termination_condition | extension
supersedes_date = YYYY-MM-DD | null
```

An explicit `extended from OLD to NEW` row supersedes exactly `OLD`. An
explicit `outside date was extended to NEW` may supersede one earlier current
deadline from the same ordered filing chain. One unambiguous extension target
becomes the active deadline. Multiple extension targets, contradictory current
dates, or an unprovable sequence emit `sec_evidence_insufficient` and no active
deadline.

The selected active deadline retains its original byte span, digest, rule ID,
and rule version. Scheduler checks over multiple dates remain as defensive
tripwires, but real producer tests must prove the resolved extension crosses
the producer-to-scheduler seam.

### 8.2 IBKR candidate planning

Candidate planning is deterministic:

1. one exact known conId;
2. the current ticker;
3. a regulator-provided successor ticker;
4. remaining aliases in stable order.

Multiple known conIds or any candidate set that cannot fit the active request
budget yields `ibkr_contract_ambiguous` before a query is sent. It never emits
`ibkr_contract_missing`. Alias-closure and conId overflow become per-case typed
ambiguity rather than exceptions from `_load_cases` that fail the whole batch.

### 8.3 Selective SEC reuse

Due blocked retries preserve existing evidence and facts until the worker
chooses what to refresh. SEC material may be reused only when all conditions
hold:

- observation fingerprint is unchanged;
- the persisted regulator locator says `filing_chain_complete=true`;
- every persisted citation still validates; and
- the current date is later than the observation's widened 120-day end.

Inside the window or with an incomplete chain, SEC is reacquired. Listing and
conditional IBKR evidence are refreshed according to the blocker and current
decision need. `massive_credential_missing` is operator-actionable and
non-retryable; saving the credential plus attended Run again is the recovery
path.

## 9. Settings and Mutation Authority

Settings are stored in the existing `profile_settings` table:

```text
security_lifecycle.automation.enabled
security_lifecycle.automation.interval_minutes
security_lifecycle.automation.batch_limit
security_lifecycle.automation.apply_profile_transitions
```

Deterministic background automation remains enabled by default to preserve the
current decision and monitoring behavior. The configurable interval prevents a
full case composition every 30 seconds; its default is five minutes. Batch
limit remains bounded to 1 or 2 and defaults to 2.

`apply_profile_transitions` defaults to false. With that value:

- verified-automatic decisions may still be accepted by automation policy;
- proposals are still generated;
- waiting-effective and waiting-market recheck clocks still operate;
- no automation transition is approved; and
- the due-transition scheduler refuses to apply any existing transition whose
  `approval_authority` is `automation_policy`.

Attended approvals keep their existing scheduling behavior. Enabling automatic
profile transitions is an explicit operator action and never follows merely
from enabling background analysis.

## 10. Runtime Progress and Durable Status

A new lifecycle-specific in-memory registry owns current progress. It is not
added to the generic provider `_PROGRESS` map. A snapshot includes trigger,
request ID, case ID, started time, current stage, and completed/skipped stages.

Actual stages are emitted from the real boundaries:

```text
preparing
sec
listing
ibkr (conditional)
evaluate
persist
approve (conditional and authority-gated)
finalize
```

The registry is protected by a lock and read through
`GET /security-lifecycle/automation`. It is lost on restart by design. On
restart, orphan reconciliation and durable run rows provide the terminal truth;
the UI must not reconstruct a fictitious in-flight stage.

The latest aggregate outcome and active incident are also written under a
dedicated key in the existing `scheduler_state` table. That durable state is
for status display only; it is not a retry queue or execution authority.

## 11. Frontend

The existing Settings security-lifecycle panel gains compact controls and
status:

- background-analysis toggle;
- interval selector;
- batch limit segmented control;
- automatic-profile-transition toggle, off by default;
- Run due now command;
- last run, active incident, next scheduled time, and current real stage.

The lifecycle case drawer gains a Run this case command and shows the current
stage only when the runtime registry reports that exact case ID. A command
refreshes the current queue and detail using the existing request-key guards.

The UI does not render provider payloads, raw exceptions, secret-bearing
diagnostics, or an unconditional IBKR stage.

## 12. Bounded End-to-End Verification

The same production service accepts an internal execution-limits object. It is
not a public arbitrary-budget API. Production defaults remain unchanged.

The canary profile is:

```text
case limit: 1
SEC: 8 attempts, 4 documents, 1 MiB/document, 4 MiB total
Nasdaq: the existing two complete-directory requests
Massive: 2 requests
IBKR: 3 contract queries and at most 1 quote
automatic profile transitions: false
```

`ListingRequestBudget` gains instance maximums so the Massive cap is injected
without monkeypatching a module constant or lowering the production default.

Offline tests first prove the budget can fail and that all provider adapters
cross their real parser boundaries. A production canary then requires separate
authorization for a read-only inventory and for provider calls. It selects one
simple case during preflight, records only bounded counts and typed outcomes,
and proves zero transition approvals and zero profile mutations.

## 13. Retired Publisher Adapter and Documents

The publisher acquisition module remains in place but is marked retired. A
tripwire proves no production module imports or calls it and that publisher
evidence cannot change the current decision material. Historical evidence
continues to render through the investigation store.

The 2026-08-24 design's publisher-acquisition section is explicitly superseded
by the 2026-08-28 listing-authority design and this document. Historical
decision records are not rewritten.

## 14. Verification and Operational Stops

Every repair starts with a RED that crosses the real producer/consumer seam.
Every new guard receives a reverse mutation with a named owner. Negative
results require positive controls.

Offline admission requires focused backend tests, the full backend suite twice
with identical node manifests, frontend tests twice, typecheck, production
build, i18n scan, browser desktop/mobile coverage, and a rebuilt evidence
packet.

Production database reads, provider calls, App restart, merge, and push remain
separate explicit authorizations after offline admission.
