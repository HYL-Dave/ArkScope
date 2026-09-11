# Task 2 Review: Capture Contract

## Verdict

Changes requested. Four load-bearing findings remain: directory-entry durability,
replaceable lease identity, inconsistent status snapshots, and storage-error
classification. None requires a store/schema redesign. Parent owns all proposed
Task 2 fixes; Task 1 remains independently in progress.

Reviewed the current untracked `capture_lock.py`, `captures.py` and their two test
files against approved spec sections 4/10 and plan
`docs/superpowers/plans/2026-09-11-sec-durable-acquisition.md`, Task 2. Included the
requested `_lease`/`issuer_refresh` extension and narrowly inspected/exercised its
service integration. This is not a whole-change or store/schema approval.

## Findings

### R1 [P1] Persist new directory entries before committing object metadata

Location: `src/sec_research/capture_lock.py:15`, especially directory creation at
line 18; creation callers at lines 35-42; publication fsync at line 109.

On a fresh capture root, `_directory` creates the root, `objects`, and `staging`
without fsyncing their parent directories. The later fsyncs cover the body and
entries inside staging/objects, not the root's entry in the DB directory or the
children's entries in the root. Consequently the SQLite object commit can become
durable without the directory ancestry needed to reach its bytes. After a system
crash/power loss, an acknowledged capture may reopen as missing. The issuer lease
can create these same directories before the first capture and does not close
this gap.

Evidence: in-memory pytest probe
`test_review_first_capture_syncs_directory_ancestry` wrapped the real `os.fsync`,
recorded descriptor `(st_dev, st_ino)`, and performed a successful four-byte first
capture. The DB directory and capture-root identities were absent from the capture
fsync calls. The assertion failed for the DB directory. This proves the missing
durability operations, not an experimentally reproduced power outage.

Owner recommendation: **Parent / Task 2**, `CaptureDirectory` initialization.
Durably establish the directory ancestry before object metadata can commit;
retain descriptor-relative safety and handle retry after interrupted creation.
Add `test_first_capture_fsyncs_new_directory_ancestry_before_register` and a
directory-fsync failure/retry owner. Existing process-termination tests do not test
power-loss directory durability.

### R2 [P2] A replaced lease file admits recovery while the original writer lives

Location: `src/sec_research/capture_lock.py:136` through line 146;
`CaptureDirectory.assert_current` at line 58 checks root/children but not the
lease inode. The reservation consequence is in `captures.py:48` through line 62.

The flock protects the opened file inode. Unlinking/replacing `.writer.lock`
while an owner holds it lets the next `_lease` create/open and lock a different
inode. Both owners are admitted for the same unchanged root. Recovery then treats
its new lock as proof that no live writer exists and deletes live reservations.
This invalidates the capacity/exclusive-recovery argument. The same pattern
applies to `.refresh-<normalized-cik>.lock`, potentially reopening same-issuer
receipt interleaving.

Evidence: `test_review_replaced_lock_does_not_admit_recovery` held a real capture
lease, inserted a four-byte live reservation, unlinked only the fixture lock
pathname, then called `recover()`. Recovery succeeded instead of returning busy
or unsafe. No root or child directory replacement was needed.

Precondition/severity: this requires a local actor or cleanup operation able to
mutate the capture-root directory. Ordinary cooperating writers never unlink the
lease file and their exclusion tests pass. This is not a demonstrated remote
exploit or ordinary two-writer overspend. It is relevant to the requested local
path-replacement/TOCTOU contract; explicitly excluding such mutation would narrow
that contract and should be a conscious parent decision.

Owner recommendation: **Parent / Task 2**, shared `_lease` for both lock types.
Bind ownership to a stable synchronization identity, or enforce a trusted,
non-replaceable lease namespace with an explicit threat boundary. Merely checking
the new lock's inode against its own current pathname does not detect the old
unlinked owner. Add
`test_replaced_writer_lock_cannot_reclaim_live_reservation` and
`test_replaced_issuer_lock_cannot_admit_same_cik` with child-process owners.

### R3 [P2] Read the three accounting totals from one SQLite snapshot

Location: `src/sec_research/captures.py:38` through line 46.

`status()` issues three separate SELECTs. `Store.connect` uses
`isolation_level=None`, so these do not share a read transaction. A legal atomic
reservation/orphan-to-object commit between SELECTs can disappear from all three
reported totals: the object sum was read before registration, but the orphan and
reservation sums are read after their removal. Recovery conversion can also be
observed inconsistently. The returned remaining/over-budget state can therefore
contradict the actual charged bytes.

Evidence: `test_review_status_uses_one_snapshot` created a published-but-uncommitted
four-byte capture, then interposed its normal `put(b"data")` recovery/registration
after the first status aggregate was fetched. `status()` returned all charges
zero and remaining capacity 100 although a four-byte object was now registered.
The probe failed its expected charge of four. The normal registration/recovery
methods, not a synthetic incompatible schema, performed the conversion.

This is a reporting/contract bug, not by itself proof of quota overspending:
`_admit` is normally protected by the writer lease. Public concurrent status
readers are not.

Owner recommendation: **Parent / Task 2**, `CaptureStore.status`. Use a single
aggregate SQL statement with scalar subqueries or an explicit read transaction.
Add `test_status_reservation_conversion_uses_one_snapshot` and a recovery
orphan-conversion counterpart. No Task 1 connection-default change is needed.

### R4 [P2] Normalize failures consistently and preserve ENOSPC classification

Locations: `src/sec_research/capture_lock.py:43` and line 143;
`src/sec_research/captures.py:64`, line 78, and lines 148-152.

The directory/lease setup handlers turn every OSError into
`capture_path_unsafe`, including ENOSPC. Thus `put` cannot recognize a genuinely
full destination during root/child/lock creation. Separately, the public
`preflight`/`recover` paths lack `put`'s OSError/SQLite normalization; disk usage,
enumeration or DB failure can escape as raw implementation exceptions instead
of the specified closed capture errors.

Evidence:
- `test_review_initial_enospc_is_capacity_error` injected ENOSPC only at creation
  of the fixture capture root. `put` raised `capture_path_unsafe`, not
  `storage_space_insufficient`.
- `test_review_preflight_normalizes_disk_error` injected EIO at `free_bytes`.
  `preflight` leaked the raw OSError and injected private-detail text rather than
  raising `ValueError("capture_store_write_failed")`.

The current service broadly sanitizes unexpected exceptions, so this is not a
claim of demonstrated HTTP detail leakage. However, it preserves the already
misclassified `capture_path_unsafe`, and direct capture consumers still see the
inconsistent contract.

Owner recommendation: **Parent / Task 2**, shared capture error boundary.
Distinguish unsafe shape/symlink failures from resource/I/O failures before
discarding errno; normalize public mutation/preflight/recovery methods, preserving
busy/platform/validation codes. Add named root/child/lease ENOSPC tests plus
`test_preflight_and_recover_return_closed_io_and_sqlite_errors`. **Task 3 owner**
should retain service redaction tests as integration coverage, not compensate
for incorrect capture-layer classification.

## Contract Checks And Coverage

- Ordinary cross-process capture exclusion and crash release pass the existing
  live/dead-worker test. Recovery retains actual staged/unpublished files,
  deduplicates hard-link inode charges and releases reservations under its lease.
- Exact original bytes, SHA256/length verification, missing/corrupt rejection,
  duplicate charging, budget reduction with pinned reads, quota rejection and
  disk-headroom rejection pass. There is no refresh/latest substitution in read.
- Stage uses O_EXCL/O_NOFOLLOW; publication uses a no-replace hard link. The new
  racing-destination test passes and proves an existing destination is preserved.
- Descriptor-relative directory walking and O_NOFOLLOW reject the tested root,
  objects, staging and lock symlinks. Object reads require a regular file and
  use O_NONBLOCK to avoid FIFO blocking. Root replacement is detected by the
  existing test. These controls do not resolve R2's separate lease identity issue.
- Hashing, staged writes, fsync, object verification, and directory enumeration
  occur outside the market DB write transaction. No provider acquisition exists
  in the capture layer. Recovery still scans registered metadata and rebuilds
  all orphan rows under BEGIN IMMEDIATE: large-store lock-duration/performance
  remains unmeasured, not a demonstrated regression in this fixture review.
- No implicit pruning was found. Recovery deletes/rebuilds accounting rows, not
  object or orphan files. Successful put removes only its own stage. Old failed
  stages remain on disk; registered hard-link aliases are not charged twice.
- Buffered blocking regular-file writes flush and fsync before publication.
  The baseline ENOSPC injection is at publish, not an actual partial stage write;
  there is no focused partial-write or post-metadata-commit cleanup-failure owner.
  Recommend `test_partial_stage_write_remains_charged_after_recovery` and
  `test_post_register_cleanup_failure_preserves_readable_object` to Parent.
- The relocation test verifies relative-key reopening on its closed fixture DB.
  Its raw SQLite copy is not evidence of a live WAL-safe export implementation.
- Deliberately POSIX-only descriptor I/O with typed unsupported rejection is
  accepted. This review makes no Windows-readiness claim.

## Issuer Refresh Extension

`issuer_refresh` normalizes CIK before deriving a fixed-prefix lock leaf and uses
a distinct per-root/per-CIK lease. The current `ResearchService.refresh` holds it
around `_refresh`, including the initial resume read, all receipts, provider waits
and final latest-receipt read. It does not hold the capture writer or market DB
lock across network waits. This is the requested long-lived issuer-only lock,
not a violation of the short capture/DB-lock rule.

Existing `test_issuer_refresh_exclusion_does_not_hold_capture_writer` passes.
Two additional in-memory fixture probes passed:
- `test_review_issuer_is_crossprocess_and_not_market_or_capture_lock`: a child
  rejects the same normalized CIK but enters a different CIK lease, capture
  writer and market write lock while the parent's issuer lease remains held.
- `test_review_dead_issuer_owner_is_released`: child termination releases the
  same-CIK lease and permits subsequent ownership.

The two real service owners also pass:
`test_same_issuer_overlap_is_rejected_without_overwriting_receipt` and
`test_different_issuer_refresh_is_allowed_during_provider_wait`.
R2 and R4 also apply to the shared lease implementation. No additional
issuer-specific blocking defect was found within this scope.

## Verification And Boundaries

All executions used an empty environment plus explicit interpreter/PATH,
`PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the specified
offline runner, and
`ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review2-tests`.
All DB, capture and lock operations were fixture-only. No provider calls,
production-store access, new agents, commits, product edits or test-file edits.
Review probes were supplied as in-memory pytest plugin functions and left no
test source file. This report is the only authored file.

Observed runs, not projected counts:
1. Initial requested two-file baseline: **20 passed in 0.49s**.
2. First four in-memory negative probes: **21 passed, 4 failed in 0.60s**.
   The parent-added issuer test was present by this run; failures reproduced R2,
   R3 and both branches of R4.
3. Directory durability plus two issuer-process probes: **24 passed, 1 failed
   in 0.65s**. The parent-added racing-destination test was now present; only R1's
   durability assertion failed.
4. Final clean focused run: **24 passed in 1.06s**, comprising the current 22
   capture/lock cases and the two issuer service cases.

Final clean command, from `/tmp/arkscope-listing-sec-macro-convergence`:

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review2-tests /home/hyl/.virtualenvs/llm_app/bin/python .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py -q tests/test_sec_research_capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_service.py::test_same_issuer_overlap_is_rejected_without_overwriting_receipt tests/test_sec_research_service.py::test_different_issuer_refresh_is_allowed_during_provider_wait
```

The initial parent run's interruption in test-only `multiprocessing.Event.set`
after terminating its waiter is not a product defect. The removed meaningless
cleanup notification is accepted; no runner/product workaround was introduced.
No quota/overwrite inverse mutations or full backend suite were run by this
reviewer. None of the negative probes is a completed fix or a new committed
regression owner.

Reviewed final Task 2 SHA256 fingerprints (stable across final focused run):

```text
7b10002126d9f6ed94d65b973cb838ac522ffe33bc56acea0e590c67180723ff  src/sec_research/capture_lock.py
01d4f91da3b8b4ff0117f05e8b794b1d699ba699fd2864f6c3d9f20423cc5837  src/sec_research/captures.py
a73ebbce2aa8ed23b5dabe69f49a37942a91e5598315825e21e02857d839e53e  tests/test_sec_research_capture_lock.py
25e625cfb509d3bd01bd78d2cf52421266038455e286a283745dd0a042f36897  tests/test_sec_research_captures.py
```
