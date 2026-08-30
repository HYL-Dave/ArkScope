# Lifecycle Automation Reliability and Control-Plane Implementation Plan

> **Execution:** Use RED-first development task by task. Do not begin a product
> change until its named failing owner exists and demonstrates the reported
> mechanism through the real function boundary.

**Goal:** Repair lifecycle automation's silent terminal states, add bounded
retry and attended execution authority, expose truthful progress and Settings
controls, and prepare a one-case production canary without enabling unattended
profile mutation.

**Architecture:** Keep the v3 profile schema and deterministic decision policy.
Use an OS execution lock plus persisted owner IDs for orphan recovery, versioned
per-case results for incident truth, predecessor-linked run attempts for retry,
an ephemeral lifecycle runtime registry for stage progress, and existing
`profile_settings`/`scheduler_state` tables for controls and durable terminal
status. Automatic decision analysis remains enabled; automatic profile
transitions default off.

**Spec:**
`docs/superpowers/specs/2026-08-30-lifecycle-automation-control-plane-design.md`

## Global Constraints

- Preserve `AUTOMATION_POLICY_VERSION` and decision provenance semantics.
- Do not add or alter a profile table, column, index, CHECK, or schema version.
- Do not silently truncate IBKR identity candidates.
- Do not copy retry counters into new query context; derive them from the
  persisted predecessor chain.
- Runtime progress is ephemeral and is not a lease. Orphan recovery must work
  with the progress registry empty.
- Scheduled and attended production callers must use the lock-owned
  run-and-record boundary; they may not release ownership between a worker
  result and its incident-state persistence.
- `apply_profile_transitions=false` must stop both new automation approval and
  later scheduler application of an already automation-approved transition.
- Existing human-approved transition scheduling remains unchanged.
- Keep historical publisher evidence readable, but do not reconnect the
  retired publisher acquisition adapter.
- No live provider call, production DB access, App restart, merge, or push is
  authorized by this implementation plan.
- Keep the user-owned untracked live-cutover evidence and review plan on
  `master` untouched.

## Task 1: Own Execution and Reap Orphaned Running Rows

**Files:**
- Add: `src/service/security_lifecycle_automation_runtime.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_runtime.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`

- [ ] Write a real-worker RED: inject a `BaseException` during evidence
  acquisition, restore a healthy loader, and prove the next invocation still
  skips a persisted `running` row.
- [ ] Write a second RED with two independent SQLite connections: one process
  lock owner may reserve, a second returns `already_running`, and releasing the
  first lock enables reconciliation.
- [ ] Add a dedicated cross-process lock and a bounded runtime owner ID.
- [ ] Add `execution_owner_id` to reserved query context without changing run
  identity or provenance.
- [ ] Add a kernel reconciliation entry point that may fail only `running`
  rows, validates owner/context shape, and uses the existing `internal_error`
  failure code.
- [ ] Wrap the whole invocation in `finally` so `BaseException` terminalizes
  rows owned by that invocation before the lock is released.
- [ ] Reconcile pre-existing running rows only after exclusive lock ownership.
- [ ] Add reverse mutations for removal of the lock, owner predicate, startup
  reconciliation, and `BaseException` cleanup.

## Task 2: Complete Human-Accepted Finalization Truthfully

**Files:**
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/security_lifecycle_fact_kernel.py`
- Modify: `src/security_lifecycle_disposition.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_disposition.py`
- Test: `tests/test_security_lifecycle_tools.py`

- [ ] Write the exact RED: crash after assessment creation, accept that
  automation assessment with `acceptance_authority="human"`, run again, and
  assert finalization completes without changing the acceptance authority.
- [ ] Add a RED showing that routing the state through `fail_run` raises
  `automation_run_has_current_assessment`; retain this as a regression owner.
- [ ] Admit both valid accepted authorities for an automation-authored
  assessment and preserve proposal idempotency.
- [ ] Add a closed kernel method for
  `terminal_finalization_failure` metadata in query context. Bound code,
  timestamps, count, and total JSON size.
- [ ] Make finalization retries reuse the succeeded run, apply bounded backoff,
  and stop hot-looping every scheduler tick. The closed schedule is 15 minutes,
  1 hour, and 6 hours; after the fourth recorded failure, automatic retries
  stop until an attended Run again.
- [ ] Project unresolved finalization failure to Attention with a closed reason
  code; never call it completed or running.
- [ ] Add mutations for the human-authority branch, metadata validator,
  backoff gate, and projection priority.

## Task 3: Version Per-Case Outcomes and Repair Recovery Witnesses

**Files:**
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/scheduler_state.py` only if a read helper is required
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_scheduler_state.py`

- [ ] Replace the existing synthetic witness RED with the real sequence:
  failed case, next tick skipped, persisted run still failed. Assert no recovery
  witness is written.
- [ ] Add the same owner for a blocked case and assert a blocker is not an
  operational failure witness.
- [ ] Add `result_version=2` and exact `case_outcomes`; prove counters and map
  cannot disagree.
- [ ] Keep version-1 blob parsing. Add fixtures for a v1 case failure, v1
  scheduler failure with no case IDs, and malformed legacy blobs.
- [ ] Determine case recovery from latest per-case run/finalization rows. An
  empty batch may not recover a case incident.
- [ ] Store latest aggregate outcome and active incident under a dedicated
  scheduler-state key; do not use `continuation` as a retry queue.
- [ ] Keep result persistence inside execution ownership for every production
  caller so a newer invocation cannot replace the per-case row being recorded.
- [ ] Deduplicate identical active incidents without periodic restatement.
- [ ] Add mutations for dropping case outcomes, treating blocked as failed,
  trusting an empty batch, and accepting counter/map drift.

## Task 4: Add Predecessor-Linked Retry and Attended Run Authority

**Files:**
- Modify: `src/security_lifecycle_fact_kernel.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `src/api/router.py` only if route registration requires it
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_routes.py`

- [ ] Preserve the three existing no-auto-replay tests as baseline owners.
- [ ] Add REDs for explicit new attempts from failed, nonretryable blocked, and
  completed runs; all prior rows must remain byte-identical.
- [ ] Generalize execution attempt identity to `predecessor_run_id` while
  reading existing `predecessor_failed_run_id` rows unchanged.
- [ ] Add cycle-safe predecessor traversal and derive attempt counts from the
  chain. Prove a new caller context cannot reset the count.
- [ ] Add `allow_due_failed_retry` and `allow_new_attempt`, both default false.
- [ ] Persist closed automatic retry metadata on the failed row without using
  the schema `retry_at` column.
- [ ] Implement the retry matrix: persistence 3 attempts; source-payload 1;
  internal 1; extractor/schema manual only.
- [ ] Add global due-run and exact-case run endpoints. Return 409 for a current
  running owner and a typed started/skipped response otherwise.
- [ ] Add mutations for each default-false authority, chain count, cycle guard,
  and policy-version isolation.

## Task 5: Align IBKR Identity Planning Without False Absence

**Files:**
- Modify: `src/security_lifecycle_ibkr_evidence.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_ibkr_evidence.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_grounded_shadow.py`

- [ ] Add the direct RED where six aliases fit and seven aliases raise.
- [ ] Add REDs for multiple exact conIds and for a 65-alias closure that
  currently fails the entire scheduler batch.
- [ ] Build a deterministic candidate plan: one exact conId, current ticker,
  SEC successor, stable remaining aliases.
- [ ] If complete coverage cannot fit, emit `ibkr_contract_ambiguous` before
  provider access and emit no `contract_missing` evidence.
- [ ] Convert alias/conId over-limit conditions into per-case ambiguity while
  allowing later cases in the same batch to run.
- [ ] Prove a genuine complete bounded lookup can still emit missing and that
  missing remains excluded from automatic decision material.
- [ ] Add mutations for candidate priority, overflow admission, per-case
  containment, and false-missing prevention.

## Task 6: Preserve Resolvable SEC Deadline Supersession

**Files:**
- Modify: `src/security_lifecycle_sec_evidence.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_sec_evidence.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`

- [ ] Add a producer-to-scheduler RED for a termination-by date followed by an
  explicit `extended from OLD to NEW` sentence. It must retain NEW, trigger the
  due IBKR check, and carry NEW's exact citation.
- [ ] Add fail-closed REDs for two extension targets, contradictory current
  dates, extension without a provable predecessor, and reversed chronology.
- [ ] Add transient `kind` and `supersedes_date` metadata to
  `SecSourceDeadline`; do not add a fact or schema field.
- [ ] Resolve only one provable active deadline and retain its original citation
  fields unchanged.
- [ ] Keep defensive scheduler multi-date checks and add a mutation showing the
  public producer owner, not a scheduler stub, kills a broken collapse.

## Task 7: Reuse Closed SEC Chains and Classify Operator Blockers

**Files:**
- Modify: `src/security_lifecycle_fact_kernel.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`

- [ ] Add REDs proving a due listing retry currently deletes regulator
  evidence and reacquires SEC.
- [ ] Preserve prior rows during reservation and pass validated prior material
  into evidence acquisition.
- [ ] Reuse regulator material only for unchanged observation, complete chain,
  valid citations, a closed widened window, and proof that every retained SEC
  row was acquired strictly after that window closed.
- [ ] Add positive controls showing an in-window retry and incomplete chain both
  reacquire SEC.
- [ ] Preserve exact prior rows for a provider family whose current acquisition
  returns a typed unavailable blocker, but exclude those preserved rows from
  evaluation. Replace only successfully refreshed or deliberately unneeded
  families, under an explicit kernel refresh contract.
- [ ] Keep succeeded readiness rechecks append-only because existing accepted
  assessments retain foreign-key citations to the original evidence. Gate the
  exception on the kernel's readiness-recheck claim, require the complete
  persisted evidence/fact set, keep prior rows out of current evaluation, and
  reject the same shape for blocked or ordinary retries.
- [ ] Make `massive_credential_missing` nonretryable/operator-actionable. Saving
  a credential plus attended case run is its recovery path; reject a retryable
  new shape and prevent legacy retryable rows from auto-reserving.
- [ ] Keep `source_payload_invalid` distinct and cover its one automatic retry;
  do not rename malformed content into transport success.
- [ ] Add mutations for each reuse predicate and provider-family refresh gate.

## Task 8: Split Background Analysis From Profile Mutation Authority

**Files:**
- Add: `src/service/security_lifecycle_automation_config.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `src/service/ticker_identity_scheduler.py`
- Modify: `src/profile_state.py`
- Modify: `src/ticker_identity_service.py`
- Modify: `src/ticker_identity_transition.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Test: `tests/test_security_lifecycle_automation_config.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_data_scheduler.py`
- Test: `tests/test_ticker_identity_scheduler.py`
- Test: `tests/test_ticker_identity_transition.py`
- Test: `tests/test_profile_state.py`
- Test: `tests/test_security_lifecycle_routes.py`

- [ ] Add Settings contract REDs for enabled, five-minute default interval,
  batch limit 1/2, and `apply_profile_transitions=false` default.
- [ ] Parse present values strictly: canonical booleans, interval 5-10,080,
  and batch 1/2. Malformed stored config disables background work and mutation
  authority instead of silently applying defaults.
- [ ] Add one snapshot read and one transactional four-key update to the
  profile-settings boundary; validate the complete effective config before
  writing and prove injected failure rolls the whole update back.
- [ ] Add A/B REDs proving propose-only still accepts verified decisions,
  creates notify/remap proposals, and keeps waiting recheck clocks.
- [ ] Gate both new transition approval and transition revalidation in the
  worker. Re-read mutation authority at each approval boundary; a run-start
  snapshot must not outlive an operator toggle.
- [ ] Gate scheduler application of existing
  `approval_authority=automation_policy` transitions while preserving attended
  approvals. Apply the authority predicate in SQL before `ORDER BY/LIMIT` so
  older automation rows cannot starve an attended transition.
- [ ] Move lifecycle invocation behind one shared due calculation over the
  existing durable `scheduler_state.last_attempt` instead of every 30-second
  supervisor pass. Only an invocation that acquires execution ownership
  advances the clock; Task 9 must reuse the same next-scheduled projection.
- [ ] Expose GET/PUT automation config with a complete PUT body and stable
  config/config-status envelope. Manual Run bypasses only enabled/interval,
  retains case limit 1, and still obeys current mutation authority.
- [ ] Add mutations for missing-key defaults, approval gate, due-scheduler gate,
  malformed-value fail-closed behavior, transactional rollback, SQL pre-limit
  filtering, attended-approval preservation, and interval enforcement.

## Task 9: Add Runtime Stage Registry and Status API

**Files:**
- Modify: `src/service/security_lifecycle_automation_runtime.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Test: `tests/test_security_lifecycle_automation_runtime.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_routes.py`

- [ ] Add REDs for exact stage order with and without conditional IBKR and
  conditional approval.
- [ ] Implement a lifecycle-only locked registry keyed by request and case.
- [ ] Emit stages at real SEC/listing/IBKR/evaluate/persist/approve/finalize
  boundaries; never infer them from elapsed time.
- [ ] GET status combines ephemeral current progress with durable config, last
  result, active incident, latest failed runs, and next scheduled time.
- [ ] Simulate restart with an empty registry and orphaned DB row. The endpoint
  must show interrupted failure after reconciliation, not a reconstructed
  stage.
- [ ] Add mutations for conditional-stage omission, request/case identity, and
  registry/durable-state separation.

## Task 10: Build the Settings and Lifecycle Controls

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/settings/DataStorageSection.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Test: `apps/arkscope-web/src/settings/DataStorageSection.test.tsx` or nearest
  existing owner
- Test: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`

- [ ] Add typed API REDs for config/status/run responses and unknown enum
  rejection.
- [ ] Add Settings controls using a toggle, interval menu, batch segmented
  control, mutation toggle, and Run due now command.
- [ ] Show current real stage, last result, active incident, next scheduled
  time, and a concise provider-family summary. Do not render raw evidence here.
- [ ] Add Run this case to the drawer and bind completion refresh to the latest
  selected case/request keys.
- [ ] Render no IBKR stage when it was skipped and no success state while an
  incident remains active.
- [ ] Add bilingual visible-behavior tests, rapid request-order tests, disabled
  states, and narrow/mobile layout owners.

## Task 11: Make Canary Budgets Injectable and Retire Publisher Acquisition

**Files:**
- Modify: `data_sources/listing_authority_transport.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_news_evidence.py`
- Modify: current lifecycle design documents that still prescribe publisher
  acquisition
- Test: `tests/test_listing_authority_transport.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_news_evidence.py`
- Test: add/extend a product import tripwire

- [ ] Add a RED proving Massive request limit cannot currently be injected per
  budget instance.
- [ ] Add bounded instance maximums to `ListingRequestBudget`; lifecycle
  defaults remain 2 Nasdaq and 4 Massive.
- [ ] Add an internal canary limits object and thread it through SEC, listing,
  IBKR, and case-limit boundaries.
- [ ] Prove the tighter offline canary limits stop excess calls and have
  positive controls that consume each allowed request.
- [ ] Mark the publisher module as a retired acquisition adapter and add a
  tripwire proving no production import/call path exists.
- [ ] Keep the historical investigation read owner and decision-material news
  exclusion owner.
- [ ] Mark the older publisher-acquisition design section superseded without
  rewriting historical decision records.

## Task 12: Offline Admission and Evidence Packet

**Files:**
- Add: `docs/superpowers/evidence/2026-08-30-lifecycle-automation-control-plane/`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md` only in the isolated branch and
  only after product gates are green

- [ ] Run every focused owner after its RED and again after the fix.
- [ ] Run reverse mutations one at a time, record the named failing node, and
  restore every product file byte-identically.
- [ ] Run the full backend suite twice and compare complete node manifests.
- [ ] Run frontend tests twice, TypeScript, production build, and i18n scanner.
- [ ] Run Playwright desktop/mobile checks for Settings and lifecycle drawer;
  include rapid selection and in-flight command refresh cases.
- [ ] Capture schema hashes proving no DDL drift.
- [ ] Build a secret-safe packet with measured and declared values explicitly
  separated, then verify manifest/disk equality and all hashes.
- [ ] Add a dated GREEN/RED decision entry without altering prior history.

## Task 13: Separately Authorized Production Validation

- [ ] Request production read-only inventory authority. Inspect only aggregate
  run states, failure codes, transition approval authorities, and simple-case
  candidates; do not read evidence bodies or secrets.
- [ ] Select one simple case whose identity candidate set fits the canary
  budget. Record the preflight case ID and expected provider families.
- [ ] Request separate provider-call authority.
- [ ] Trigger the exact case with the canary limits and
  `apply_profile_transitions=false`.
- [ ] Verify stage order, request counts, cited evidence admission, terminal
  outcome, zero transition approvals, and zero profile mutations.
- [ ] Request App restart, merge, and push as separate decisions only after the
  production result is reviewed.
