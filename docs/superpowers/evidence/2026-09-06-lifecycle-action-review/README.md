# Action-Bound Lifecycle Review

## Scope

This is Task 6's structured-provider-backed backend foundation, not the completed
Web investigation or main-screen redesign. New service/API preparation and
confirmation are tested with real temporary SQLite stores. No production store,
credential or provider is used, and no migration, App restart, commit, merge or
push is performed.

The completed portion supports both delisting removal and same-security symbol
continuation. The latter still requires the existing exact event, matching
security identity and active successor evidence; it is not new FIGI-only or
acquisition-as-rename authority. Open positions, stale/contradictory provider
evidence and unavailable source context retain their existing vetoes. Web-backed
findings are intentionally not admitted by substituting a manual/SEC assessment
or an old `accepted` flag. Their persisted validation and positive execution
path remain open, alongside Tasks 7-9. No final hand-test request is warranted.

## Confirmation Contract

- `GET /security-lifecycle/cases/{case_id}/review` prepares an action without
  writing or inventing accepted assessments/proposal IDs. Binding covers the
  selected and latest assessment revisions, finding, citation content integrity
  and source references, provider observation/check, policy/rule versions,
  options, exact target profile effects and currently relevant sources.
- The new review DTO contains the finding, source links/observation time and
  reviewable effects. Internal audit digests, raw membership rows and future
  storage columns are not exported. The packet digest and opaque actionable
  resource IDs identify the exact server reconstruction; a hash is not permission.
- Existing case detail and Research readers also close their nested transition
  preview. The internal reader still verifies the complete stored preview hash;
  the outward hash identifies that receipt, not a hash of the reduced DTO.
  Approve/cancel responses now expose the existing eight-field frontend record;
  retry/reverse expose status, blockers and that record. This intentionally drops
  untyped database columns and raw JSON, not an existing typed frontend field.
  The internal scheduler still receives the full store result. Existing audit
  reads did not export the marker and remain a positive control.
  Legacy retry must not translate a scheduled, cancelled, reversed or
  `applied_state_changed` review into completion. Such responses use the existing
  `transition_preview_changed` conflict; the dedicated read endpoint retains the
  actual state. Successful apply and reverse controls remain green.
- `POST /security-lifecycle/cases/{case_id}/confirm-review` accepts only those
  references, action and strict options. Client-provided facts, effects, actor
  and acceptance flags are rejected. Both existing database/profile write hooks
  are repeated at write boundaries. Their present application-wide audit-only
  implementation is unchanged; injected denials are owned by tests. This slice
  does not claim to introduce a new application authorization system.
- The server rebuilds the packet inside `BEGIN IMMEDIATE`. Acceptance, proposal
  creation and attended approval share that caller-owned transaction. Existing
  accept-only, automation and legacy approval callers retain their contracts;
  they cannot forge the new confirmation marker through their public methods.
  They also cannot overwrite a pending new confirmation with an old preview:
  that would discard the binding and could replace the user's scheduled date.
  Genuine new-command reapproval remains possible; ordinary rows without the
  marker retain both their attended and automation approval paths.
- The existing bounded `approved_preview_json` stores a versioned
  `review_confirmation`: actor, action, timestamp, digest and reviewed material.
  No new table/schema or JSON allowance is introduced. Large material is rejected,
  never truncated. Direct legacy store application cannot bypass new review
  revalidation. Older binaries must not be used to finish these new pending
  approvals; their old rebuilt preview does not contain the new digest binding.
  That mismatch is not a general downgrade guarantee: old reapproval code does
  not own the new marker. A release rollback needs an explicitly verified
  profile-restore plan, not an assumption that unchanged DDL implies compatibility.
- After durable approval, execution rebuilds and checks the reviewed material
  again. Actual profile effects, transition/attempt/activity receipts and
  membership suppression remain atomic. A staging crash rolls back acceptance
  and approval; an application crash retains recoverable approval but rolls back
  all effects. Independent invocations after restart share the durable receipt.
- Repetition does not create a second effect or audit event. Readback compares
  actual affected state to the receipt before reporting applied. Response or
  readback loss can be resolved with the same action reference and
  `GET /security-lifecycle/review-confirmations/{transition_id}`. An applied row
  whose effects were later edited reports `applied_state_changed`; cancellation
  or reversal cannot be undone by replaying the old confirmation.
- Future actions are scheduled using New York's date, including UTC-midnight
  and daylight-saving boundaries. The existing due runner receives the old
  execution-result envelope, including actual transition status when blocked.
- Existing required-proposal dismissal is reflected during preparation, rather
  than presenting a confirmation that can never finish. Missing recommendations
  are created only on confirmation. After a target profile change blocks an
  approval, an explicitly reviewed fresh packet can reapprove that action.
- Unrelated tickers and SA capture-time-only updates are not packet dependencies.
  The command does not require pausing unrelated SA synchronization. SQLite's
  short profile write transaction remains, with no provider dispatch inside it.

## Verification Results

The final unchanged-source campaign is complete:

| Gate | Measured result |
| --- | --- |
| 27-file baseline focus | 1111 passed |
| Independent mutants, each against the complete focus | 23/23 fail their named owners; no collection errors |
| Restored focus | 1111 passed |
| 76-file integration | 1955 passed |
| Complete backend, actual worktree | 6192 passed / 12 skipped / three existing edgartools deprecation warnings |
| Complete frontend | 1432 passed |

Both integration and backend add exactly 86 new service/API nodes and remove
none against Task 5. The frontend node list is identical to Task 4's list.
`source-manifest.json` binds the tested source and current implementation records;
`verification.json`, `node-changes.json` and `mutation-results.json` preserve the
measured counts, exact owners and restored hashes. Successful typecheck, production
build and i18n-literal checks are mandatory before the sealer publishes the packet;
their command results are retained in `typecheck.json`, `build.json` and `i18n.json`.
The preceding population and price-window packets are verified unchanged.

The latest local service/API and existing transition-route/read-tool regression
has 118 passes. The first wider run had 1091 passes and one expected route-inventory
failure (201 versus 204), resolved by recording the three exact new routes and
updating both existing count owners.

An earlier mutation campaign had a green 1092-node baseline and four named
mutation failures. It was stopped after source review identified the missing
preparation-time proposal veto. Its incomplete report is not final admission.
A second campaign had a green 1096-node baseline and 16 owned mutants before it
was deliberately stopped: review found that the existing case/Research and
legacy action APIs still exported the new private confirmation. Six new RED
controls reproduced these exports; the audit read was a retained positive
control. The third campaign had a green 1103-node baseline and four owned mutants
before a final consumer review identified the legacy completion-status mismatch.
Four real-route RED controls reproduced the false-success envelopes without
extra writes. A fourth campaign had 1107 baseline passes and 15 owned mutants,
then stopped when the final write-path inventory found legacy reapproval could
erase a new confirmation and change its schedule. Real attended and automation
commands reproduce that defect; unreviewed rows are positive controls.
All four incomplete reports are retained, not used as final admission. The fresh
final campaign includes proposal-dismissal, independent case/Research/legacy-response
projection, completion-status and reapproval-downgrade mutants, for 23 total.

Early fixtures needed two corrections: append a fresh immutable provider check
instead of deleting check history, and import `observation_fingerprint` in the
rename fixture. Those setup failures are not counted as product RED evidence.

The final campaign runs in a source-only copy with credentials, production data
and ambient development harness files excluded. Temporary stores use a separate
tmpfs filesystem to avoid the observed local-disk journal waits; they still run
the real SQLite transactions, locking, triggers and schema. These are crash/fault
injection tests, not a physical power-loss durability experiment. The full
backend runs against the actual worktree with temporary database overrides.

No frontend source changed in this slice; the complete frontend test run above
is new. The preceding price-window packet's 18 bilingual desktop/mobile browser
scenarios were not rerun and are not claimed as new browser evidence. No App or
dev server was started.
