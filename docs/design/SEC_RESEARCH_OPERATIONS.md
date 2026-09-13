# SEC Research Operations

Operator-only commands for protected export, restore, orphan cleanup and schema
recovery. They are not model tools, startup repair or scheduled deletion. This
runbook does not authorize execution against an actual installation.

## Scope And Admission

The commands resolve the configured market database and its adjacent SEC capture
root. Maintenance also reads retained Research references from the configured
profile and any colocated Research store. Missing, incomplete or corrupt
reference evidence blocks removal; it does not mean zero references. A valid
existing profile without any Research namespace is an observed empty store.

Previews do not repair data, create missing stores or change accounting. SQLite
may still use WAL/SHM coordination files. Preview approval binds relevant SEC
state and references, not unrelated incoming price/news rows or the whole market
database's mtime. Changed relevant state requires a new preview and approval.

Operation leases protect publication, pinned readers, exports and Research
results until their durable citation writes. Exclusive maintenance refuses an
active cooperating owner. Expensive hashing, backups, unlink and audit I/O do
not hold the shared market writer lock; actual database mutations do. SQLite's
own transaction locks still apply, so this is not a fixed latency guarantee.
Protection currently requires supported POSIX/no-follow filesystem semantics;
it does not exclude arbitrary external SQL or filesystem editors.

## Export And Restore

```text
python -m src.sec_research export --destination NEW_BUNDLE_DIRECTORY
python -m src.sec_research restore --bundle BUNDLE_DIRECTORY --destination NEW_DIRECTORY --database-name market_data.db
```

A bundle contains a consistent whole-market SQLite backup and referenced SEC
capture objects with a versioned manifest. It includes colocated prices, news
and cache rows, but excludes independent profile/SA databases and other capture
roots. It is not a complete ArkScope installation backup. Keep private data
bundles outside version control and public evidence.

Restore verifies manifest membership, entry types, hashes, schema and reference
closure before publishing into a new destination. It does not overwrite a live
installation or change its configured paths. Source/destination overlap, unsafe
paths and unsupported atomic publication fail closed. Keep incomplete outputs
for inspection; use a new destination after correcting the cause.

## Orphan Cleanup

```text
python -m src.sec_research cleanup-preview --preview NEW_PREVIEW.json
python -m src.sec_research cleanup-apply --preview PREVIEW.json --approval-sha256 APPROVAL_SHA256 --receipt NEW_RECEIPT.json
```

Inspect the preview's candidates, retained references, charged sizes, blockers
and `approval_sha256`. Apply approves that exact candidate set; there is no
force, age-based sweep or automatic confirmation. Every historical snapshot,
receipt, observation, document, issuer mapping and Research reference is retained.
Unknown directory entries, symlinks or ambiguous identities block cleanup.

Registered but unreferenced objects become orphan charges transactionally before
unlink. Files are counted as removed only after directory durability succeeds.
`freed_bytes` is logical content size, not free disk blocks or SQLite compaction.
After an interruption, retained or unresolved files remain charged. A subsequent
preview can expose an absent unresolved charge; retiring it after directory sync
does not claim newly freed file bytes. Retry requires a fresh preview, approval
and receipt, not reuse of an earlier approval or recursive filesystem deletion.

## Schema Reset And Uninstall

```text
python -m src.sec_research schema-preview --mode reset --preview NEW_PREVIEW.json
python -m src.sec_research schema-preview --mode uninstall --preview NEW_PREVIEW.json
python -m src.sec_research schema-apply --preview PREVIEW.json --approval-sha256 APPROVAL_SHA256 --backup NEW_BACKUP_DIRECTORY --receipt NEW_RECEIPT.json
```

Choose one preview mode. The mode is bound into its approval, not repeated on
apply. Retained references or external schema dependencies block destructive
work. Only exact known SEC-owned objects can be reset or removed, never all
objects matching a prefix. Unrelated rows/settings and shared SQLite state are
preserved.

Admitted schema work first backs up the whole database and every safely
inventoried SEC object/staging file, then rechecks fresh relevant state. The raw
backup is not a canonical export or a byte-for-byte copy of SQLite sidecars.
Its `raw-backup.json` certifies the backup only, not successful schema mutation;
canonical restore deliberately rejects it.

An unknown owned schema can explicitly disclose `apply_effect=raw_backup_only`.
Approving that preview allows only the stated safety backup. The result remains
blocked at `backed_up`, with `inspect_raw_backup` recovery and no DROP fallback.
Missing, unsafe or stale input cannot silently start this backup.

Reset installs the current canonical SEC schema and immediately charges retained
capture files. Uninstall leaves the schema absent, not zero storage usage. Both
preserve capture files. Uninstall is schema administration, not a permanent
feature-disable flag: a later admitted acquisition may install fresh schema.
There is no automatic migration chain, rollback or overwrite of another store.

## Receipts And Recovery

Preview, backup and initial receipt destinations must be new, safe paths outside
the capture root and the market/profile database files and SQLite sidecars.
Preview/receipt JSON uses a closed version1
shape. Detailed receipts can contain local identifiers and paths; routine CLI
output is a scrubbed summary. CLI exits0 for ready/ok,1 for blocked/unavailable,
and2 for argument errors. Read the receipt rather than inferring success from a
created file or a backup alone.

`phase` records resource progress; `receipt_phase` records the last durable audit
stage and can lag after audit I/O failure. `complete` requires the final audit
write. Failure-audit publication retains the original SEC-exclusive lease but
does not hold the market writer lock. Before receipt admission, a refusal may
correctly produce no receipt.

| Last Resource Phase | Meaning And Recovery |
| --- | --- |
| `not_started` | Admission or initial audit failed; no backup or source mutation. |
| `prepared` | Audit admitted; failed schema backup has no complete raw marker. Inspect inputs and use new output paths. |
| `charged` | Orphan charge is retained; unlink or durability may be incomplete. Reobserve before retry. |
| `files_removed` | Durable file changes occurred but later reconciliation/audit may have failed. Do not reuse stale approval. |
| `charges_reconciled` | An already absent file's retained charge was durably retired. No newly removed file bytes are implied. |
| `backed_up` | Raw backup exists; mutation was refused, failed or was never allowed. Inspect backup and source state. |
| `schema_committed` | Schema mutation committed; a later audit may have failed. Inspect current schema before choosing recovery. |
| `complete` | Final audit was written; consult status, counts and accounting for the actual operation result. |

Keep old receipts and backups. A failed audit is not proof that no resource
changed, and a successful backup is not permission to reset. These commands do
not activate a different SQLite engine, prove existing-store integrity or stop
all application writers for a runtime replacement. SQLite deployment remains a
separate attended operation.
