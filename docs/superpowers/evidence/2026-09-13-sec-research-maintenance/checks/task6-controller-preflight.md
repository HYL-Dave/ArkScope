# Task6 Controller Preflight

Initial source preflight: 01ca7c58; refined after Task5 acceptance at b49e09c4.
No production data or settings read.

## Approved Dependency

Task5's operation lease and canonical export must pass their review before
Task6 implementation. Capture writer exclusion does not span source publication
or pinned reads. Citation roots are available in `references.py`; neither their
availability nor this note authorizes actual-store deletion.

## Scope Constraints For The Implementation Brief

- `schema._DDL` names the current owned tables, indexes and immutable triggers.
  `_owned` additionally detects unknown prefix/owner objects. A mismatched shape
  may be inspected, but an unknown name or external dependency must block DROP.
  Do not reuse old lifecycle disposal's `app_stopped` assertion flag; that is
  not the approved exclusion mechanism for the new SEC feature.
  External-dependency protection also applies to object cleanup: an unmodeled
  external FK with ON DELETE CASCADE must not turn a selected object DELETE
  into deletion of unrelated rows. Include a populated external-reference
  positive protection test, not just PRAGMA foreign_key_check after deletion.
  SQLite identifier comparisons here must respect its case-insensitive table
  lookup; quoted/mixed-case FK targets still refer to the same owned table.
- `sec_research_receipts`, issuer maps and document attempts use AUTOINCREMENT.
  `sqlite_sequence` is SQLite-owned shared state, not a SEC-owned drop target.
  Preserve unrelated sequences and all unrelated DB rows, including news,
  prices and financial_cache. No dynamic dependency on a hypothetical old
  schema or profile population is introduced.
- Approval must bind relevant SEC schema/data/file identities and Research roots,
  not the whole shared market DB's byte hash/mtime or unrelated row counts.
  Independently arriving SA/news/price rows must not alone invalidate a preview.
  SEC candidate/reference changes must invalidate it. Include a positive control.
  Fingerprint relevant table contents with ordered cursor iteration and bounded
  hash/count state, not a full in-memory copy of all historical financial rows.
  Large retained stores are legitimate; preview size need not scale with every
  fact value when only the exact digest and counts are needed for approval.
  SEC-exclusive protection spans maintenance, but the shared market writer lock
  must not span full capture/reference hashing, backups, unlink or audit fsync.
  Use short writer-lock transactions for DB mutation/account reconciliation.
  Fresh full verification remains under SEC exclusion; cheap write-point checks
  preserve admission. Prove independent normal market writes can proceed during
  the long FS/read phases but not during mutation. No new generation framework.
- `iter_research_sec_citations` requires an explicitly query-only connection and
  reads all retained message/event roots. Do not construct ProfileStateStore
  merely to inspect it (its constructor creates schema). Malformed references,
  incomplete existing Research schema or unknown reference closure fail closed,
  never become zero references. An existing valid profile with no Research
  namespace objects at all is an observed empty Research store, not a missing
  profile. This first-use state must not require creating tables just to preview
  cleanup. Missing profile files and partially installed roots still block.
  Preview owns no repair or recovery writes.
  Apply must not reuse a caller's older pinned SQLite read transaction as a
  supposedly fresh reference recheck. Own a new read snapshot under the exclusive
  operation lease, or reject a pre-existing caller transaction explicitly without
  committing/rolling it back behind the caller's back. Cover a connection that
  saw the preview state before a second connection published a new citation.
- Candidate accounting must distinguish unregistered objects/staging, registered
  unreferenced objects and multiple directory entries sharing an inode. Never
  claim bytes freed until unlink + directory durability succeeds. All reference
  classes survive, not just current/latest observations. No age-based deletion.
  Cover unlink/fsync failure followed by ordinary CaptureStore recovery: recovery
  must not erase an unresolved charge and imply durable deletion without checking
  directory durability. Keep any change scoped to write/recovery paths; stored
  reads remain observational.
- The schema-reset backup contains the SQLite backup and capture files before
  destructive action. Mismatch backups must be labeled raw and must not pass as
  canonical portable exports. Exact preview admission and a fresh recheck after
  backup are necessary. Interrupted phase receipts live outside the removed
  schema. The reset/uninstall operation must not delete capture files.
  After reset, retained files must still be charged (for example as known
  filesystem orphans in the new accounting tables), not reported as zero
  capacity usage until a later acquisition happens to recover them. Uninstall
  may instead report the intentionally absent schema; it is not zero usage.
- Closed preview/receipt JSON and explicit paths are operator-only. No new
  model-facing filesystem tool, startup repair, force confirmation or recursive
  cleanup command. CLI validation must precede DB opening; no source contents,
  credentials or URLs in routine reports.

## Existing Interfaces

`src/sec_research/references.py` owns `iter_research_sec_citations(connection)`
and `sec_reference_closure(store, citations=...)`. The latter verifies stored
raw source/row identity, receipt JSON, full document catalog sources and UTF-8
range bindings; it retains compact identity closure between bounded source
reads. Do not replace it with a SELECT-only FK scan.

`src/market_data_direct.py::backup_market_db` is the existing WAL-safe path
backup; use overwrite=False. `src/sqlite_backup.py::backup_connection` is the
existing caller-owned connection variant. Do not add a third generic primitive.

The original source-only SQLite admission preflight is tracked at
`docs/superpowers/evidence/2026-09-13-maintenance-closures/checks/sqlite-admission-preflight.md`.
Task6 is not SQLite runtime activation or an integrity claim about actual stores.
