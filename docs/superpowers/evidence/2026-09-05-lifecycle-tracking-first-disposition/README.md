# Tracking-First Attended Three-Case Disposition

## Authority

The user authorized a consistent private backup, a private rehearsal, then only
the exact ARCH/LTHM/TA retirement effects if the evidence, positions and preview
remain valid. This grant excludes provider calls, price backfill, migration,
merge, App restart and push. The source branch remains based on `0b66732b`.

The preceding read-only inventory is the approved input, not an execution
receipt. Each target was Former-only with one accepted membership, six required
listing evidence records and no open position. No manual/Current/legacy source
removal or acquirer alias was proposed. The expected universe changes from 186
to 183; historical data and all other tracking intent must remain.

## Execution Contract

`scripts/disposition.py` is a detached maintenance command, not a new application
endpoint or replacement for the planned one-confirmation workflow. It uses the
existing assessment, proposal, attended approval and atomic profile-effect /
receipt transaction. It creates fresh human-authorized assessments bound to the
stored observations; it does not reuse an old accepted assessment as new consent.

- Validate the installed schema, disabled automation controls, source/effect
  digests, exact target dates, current required listing evidence and no position.
- Reserve SQLite writers while backing up all three databases. Use SQLite's
  backup API rather than copying a live main file without its WAL.
- Keep backups and private plans in a create-only `0700` directory with `0600`
  files. Whole-database backups contain the original database contents, including
  opaque credential storage; credential/token fields are never selected, logged
  or included in repository artifacts.
- Bind backup checksums to the main file plus nonempty WAL/journal contents.
  Checking only the main file was rejected by an actual WAL-tampering test.
- Rehearse with the private profile and private market/SA backups. Real service
  calls must produce all three applied receipts and exactly the expected effects.
- Reconcile the observed SA inputs through the existing writer. The known 105
  timestamp-only binding updates may refresh observation metadata, but must not
  change membership intent or create admission events. Only the three terminal
  applications may remove memberships.
- Bind the production command to the backup, exact database paths, runtime
  source hashes, deterministic command identities and each complete rehearsed
  preview. Recheck before writes; do not refresh evidence timestamps.
- During application, market and SA remain writer-reserved and SQL read-only.
  Profile SQL is restricted to the necessary receipt/intent tables; credential
  reads, provider-evidence writes, price writes, DDL and other writes are denied.
  Network, subprocess and ambient credential-file access are also denied.
- Record intent before approval, approval before application, and the applied
  receipt after commit. The existing transactions are separate, not falsely
  advertised as one batch transaction. A stopped command can have partial durable
  progress; read back actual statuses and do not blindly replay the batch.
- Verify exact remaining source edges, unchanged protected profile rows,
  unchanged market/SA database content, unchanged historical provider snapshots,
  post-reconciliation non-resurrection, receipt status and reverse readiness.

Continuation remains unavailable; independently confirmed old-listing inactivity
does not prove that no successor exists. There is no acquisition-to-buyer alias,
history transfer or portfolio rewrite. Current reverse readiness is state-bound,
not a promise that later unrelated edits can always be reversed.

## Version And Recovery Boundary

`scripts/readback.py` can run with the main tree on `PYTHONPATH` against the
private applied rehearsal before production application. It checks actual
read-service projections and transition receipts, not merely whether JSON parses.
No new provider snapshot is written by this operation. The separate V2 snapshot
reader compatibility boundary still applies to future provider-check writes;
passing this readback does not permit an old binary to read arbitrary V2 data.

Keep the create-only backup and per-stage receipts. Prefer a separately reviewed
governed reversal when appropriate. Never replace the live database with an old
backup or discard subsequent changes without fresh authorization. An existing
`apply-started.json` requires status readback, not removal of that marker to retry.

## Status

Offline maintenance verification is complete: 1,333 passed, six independent
mutations failed their named owners, all six copied files were restored
byte-for-byte, and the restored 1,333-test focus passed. See
`verification.json`. The prior 5,978-pass full backend result was not rerun for
this maintenance-only turn; no product source changed.

The authorized production preflight stopped at
`2026-09-05T16:20:37+00:00` with `disposition_inputs_changed`, before backup,
rehearsal, reconciliation, assessment, approval or application. A restricted
read-only comparison found only the SA observation digest changed. Its 105
lineages still match the unchanged binding content/anchors; all differences are
timestamps. Current observation times are `16:13:13Z` and `16:13:25Z` (September
6 at 00:13 in Asia/Taipei). The actor responsible for that capture was not
investigated or inferred.

Universe count/digest (186), target effect digest and all three provider-check
digests still match the sealed inventory. No open position or new target
transition was found. No guard was relaxed and the old packet was not re-sealed
with the new timestamps. See `preflight-stopped.json`.

A private `0700` diagnostics directory exists under
`data/backups/2026-09-06-lifecycle-attended.bGKFa1/`, containing only a
`0600` SA diagnosis. It is **not a database backup**. No database backup,
production-backed rehearsal, main-tree compatibility readback, production
disposition, provider request, migration, restart, merge or push occurred.
Fresh authorization to bind the updated SA observation times is required before
resuming the same three-target operation.

The complete Lifecycle UI, old-case population mapping, web investigation and
live price repair remain open. This is not feature completion or hand-test
readiness.
