# Lifecycle Population Reconciliation

## Scope

Task 5 is an offline, read-only prerequisite for the new lifecycle workflow.
`SecurityLifecycleReadService.population_manifest()` uses explicit market/profile
paths; it does not resolve global source configuration, credentials or SA capture
data. The internal manifest is not the future UI/Research DTO and is never
approval authority. No action executor or deletion command consumes it.

The snapshot includes all market observations, persisted profile cases, complete
provider-check history, the actual existing composition, and lifecycle/identity
dependencies. SEC key intersection and both directional differences are measured
independently. Provider virtual cases, persisted cases and source-missing cases
are reconciled separately. Raw, latest, projected, composed, old-screen-visible,
new-current and historical counts are not interchangeable. No production count
such as 36, 37 or 39 is built into this reader.

## Consistency And Classification

- Open existing files with `mode=ro`. Do not create missing stores, migrate,
  acquire a profile write lock, or invoke a provider. Existing component schema
  and foreign-key integrity checks remain in force.
- Encode literal filesystem paths before appending SQLite URI options, including
  the existing nested market and profile composition readers. Otherwise a `#`
  or percent sequence can redirect a read to a different file, and a literal
  query suffix can be interpreted as a writable/create mode. Temporary-store
  controls cover both databases, decoy files, ordinary spaces and no unintended
  file creation. Query-character filename cases are not applicable on Windows.
- Keep independent SQLite monitors in autocommit; compare each connection's
  `data_version` and each file's device/inode across the entire capture. This
  verifies a shared stable read interval, including WAL changes and composition's
  nested reads. It is not a transaction spanning databases. A concurrent write,
  even an unrelated profile write, invalidates this one inventory, not the
  writer. There is no implicit retry or requirement to pause SA synchronization.
- Seal selected material, schema descriptions and the observation clock. The
  pure builder validates shape and digest and can replay without opening stores.
  Digests bind content; they are not signatures or permission to apply anything.
- Account for each raw input exactly once. A recovered-active provider case
  remains historical; an always-active security normally belongs in coverage.
  A stale active snapshot cannot claim current health. Source-missing questions
  remain unresolved even if an older assessment was accepted.
- Consolidation requires exact ticker, FIGI, market, venue, security type and
  issuer identity. SEC additionally needs a successful run bound to that exact
  observation, same-document regulator identity facts, and contemporaneous
  listing evidence. This implementation admits common-stock binding only.
  Its conservative joining window is filing date through three days afterwards;
  it is not an event-retention limit or permission to discard older notices.
  Incomplete, conflicting or noncontemporaneous identity stays unmerged.
- Current trading does not cancel a future regulator event or an unresolved
  successor/venue question. Those retain an explicit current reason.
- Provider case IDs themselves are ticker-based. When historical checks prove
  a different listing identity, separate the historical material and flag the
  current identity question. Old checks and receipts must not follow that reused
  string onto a new security. Virtual-to-persisted case identity remains stable.

## Actual Dependencies And Receipts

Inventory all retained assessments, observation/evidence citations, extracted
fact dependencies, translation cache dependencies, proposals and actual transition
receipts. Validate cited content and receipt-preview digests. Include actual
attempt/activity IDs; do not invent hypothetical receipts. The manifest exposes
only closed audit metadata, not excerpts, translation text, private credentials
or database paths. Unreferenced evidence is identified, not declared disposable.

Bind a transition to its reviewed observation or proven same listing identity.
If that binding no longer survives, retain the action in separate history; do
not claim it applies to the current security. Applied removal and unresolved
continuation are independent: an unresolved replacement stays in current review
after removal, while a resolved removal belongs in history. Expiry alone does
not forget an already-applied, identity-bound old-listing fact: its basis is
explicitly `applied_receipt`, with the original observation time and staleness
diagnostics. New or contradictory observations cannot be overridden by that
receipt. Freshness gates for new actions are unchanged. Approval or a blocked
attempt is not application. A previous accepted assessment is not fresh consent.

The inventory intentionally reports `collection_state=not_observed`. It does not
read current holdings/watchlist membership and cannot equate a historical receipt
with the current collection scope. Task 7 must use the shared current source
projection for that separate value.

## Verification

The final unchanged-source campaign measured:

| Gate | Result |
| --- | --- |
| New population tests | 63 passed |
| Full 21-file focus, baseline and restored | 701 passed each |
| Independent mutations, each running the whole focus | 22/22 fail named owners; no test errors |
| 74-file integration | 1869 passed |
| Full backend | 6106 passed, 12 skipped; three existing edgartools warnings |
| Integration/backend node changes from Task 4 | Each adds 63 population tests; removes zero |

Full-backend subprocess duration was 551.803 seconds; pytest reported 549.04
seconds. The backend ran against the unchanged implementation worktree; focus
and integration ran in the isolated source copy. This slice does not rerun the
frontend: its product/UI files have not changed since the preceding packet's
1432-pass frontend and 18 bilingual browser scenarios. Both copies' recorded
product/test hashes are checked at sealing, as is the prior 48-file evidence
packet. No production population count is asserted by these temporary-store runs.

`scripts/verify.py` performs the complete 21-file case-read/receipt focus for the
baseline, each of 22 independent mutations, and the restored source. The broader
74-file lifecycle/price/maintenance integration and full backend (`pytest -q
tests`) follow. Tests use real temporary SQLite stores, including applied and
blocked transitions, with network-denied population fixtures. The mutation copy
contains version-controlled/admitted local source, excludes live data, `.env`
and development Claude configuration, and never edits the operator worktree.

`verification.json` and the node manifests are the measured results, not forecasts.
The new owners cover all input populations, key-vs-count equality, healthy and
recovered controls, stale observations, share classes/venues/reused symbols,
observation-bound identity, surviving regulator questions, actual dependency
retention, altered receipts, snapshot tampering, WAL writes, file replacement,
read-only/global-source isolation and typed malformed input failure.

The initial fixture used two nonexistent lifecycle enum values; it was corrected
before the clean seven-test missing-service RED. Another helper initially called
keyword-only `fail_run` incorrectly. A dangling FK is rejected by the existing
schema verifier before composition; the pure builder has a separate dependency
owner. These harness corrections are not counted as product RED evidence.
The later reused-provider-symbol probe did expose a real draft implementation
error: receipts were following `case_id` rather than their bound observation.
Its two genuine RED owners now cover the corrected behavior.

The first isolated campaign was stopped after three killed mutants (a fourth run
was interrupted) to add an exact provider source-key owner. A matching ticker
under a different source reference is not recovery of a source-missing case.
The completed campaign must be restarted on the final source, not combined with
those earlier results.
A second campaign was stopped after its baseline and first mutant to add the
applied-receipt expiry control. Neither interrupted campaign is admission.
A third campaign completed all 20 then-current mutations, restored 691-test
focus and 1859-test integration, but its backend run was interrupted after a
temporary-store probe proved the nested readers' literal-path bug. Its results
are not combined with the final 22-mutation campaign. The first path fixture
also recreated an existing schema; only the corrected eight-failure/two-pass RED
is retained as path evidence, not that fixture setup failure.

The final source-copy campaign stopped after its 21st owned mutation because the
harness had not enrolled the two newly edited nested readers in its hash ledger.
This was a `KeyError` after the market-reader mutant had failed four tests and
its source had been restored, not a product-test failure. No product or test
source changed. The bounded `--resume` correction verifies all 105 code inputs
against the original restored copy, all 103 previously recorded hashes, every
completed XML result, mutation order and named owners before continuing. It
preserves the original report and records when the two missing hashes were added;
it does not pretend they were in the initial ledger. A changed-source v3 resume
was rejected without changing its report. Fresh campaigns now enroll every
mutation target and check every dirty product/test file before their first test.
`interrupted-harness-report.json` and `harness_resume` retain this accounting
correction; all final results still come from one unchanged product-code version.

### Reproduction

Run from the implementation worktree with its declared Python environment:

```sh
/home/hyl/.virtualenvs/llm_app/bin/python \
  docs/superpowers/evidence/2026-09-06-lifecycle-population-reconciliation/scripts/verify.py \
  --repo /tmp/arkscope-lifecycle-terminal-membership \
  --staging /tmp/arkscope-population-admission-v4 \
  --temp-root /mnt/md0/arkscope-population-admission-tmp-v4
```

These are the recorded final-run paths, not reusable output directories. A new
run must select new staging and temporary paths. The command records each full
focus result, named mutation failure and restored source hash; it marks the run
complete only after integration, full backend and unchanged-source checks pass.
`scripts/seal.py --results <staging>/results` refuses incomplete admission and
verifies the previous price-window packet before sealing the new evidence.
The recorded v4 campaign used `--resume` once for the specific 21-mutation hash
ledger checkpoint above. It is not a general retry mechanism and refuses changed
source, changed scope, altered XML or a different checkpoint. A fresh reproduction
uses new paths and does not need that flag.

## Boundaries

This slice performs zero production reads/writes, provider calls, migrations,
App restarts, commits, merges or pushes. Earlier live price/retirement packets
remain unchanged. The fifteen-day default and repair UI remain the previous,
separately verified offline slice.

Task 5 does not complete Tasks 6-9: one-command confirmation, compact UI/API/
Research projection, explicit restricted web investigation and final cutover.
No final user hand-test or production cleanup is requested on this basis.
