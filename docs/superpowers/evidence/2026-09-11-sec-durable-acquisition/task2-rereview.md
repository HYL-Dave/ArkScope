# Task 2 Scoped Re-review

## Decision

**APPROVED for the Task 2 review gate.** No remaining blocking finding against
R1-R4 under the parent's explicit R2 trust-boundary ruling. The reviewed Task 2
files may enter the full-freeze candidate. This is not approval of the complete
change, full backend evidence, other agents' store/schema work, or activation.

Reviewed current `src/sec_research/capture_lock.py`, `captures.py`, and their two
test files against `task2-review.md`, `task2-fix-report.md`, approved spec sections
4/10, and Task 2 of the durable-acquisition plan. Narrow service checks cover only
the issuer/capture/market-lock integration affected by R2.

## Finding Disposition

### R1: Closed

`capture_lock.py:27` fsyncs the directory's parent on the create path, including
FileExistsError retry, before opening the directory. Capture-root creation syncs
the DB directory; objects/staging creation syncs the capture root. Body and
publication-entry fsyncs remain before metadata registration.

Verified passing owners in `tests/test_sec_research_captures.py`:
- `test_first_capture_fsyncs_directory_ancestry_before_register`
- `test_directory_sync_failure_then_retry_never_publishes_missing_bytes`

The first checks parent/root descriptor identities before `_register`, not just
after successful completion. The retry owner proves a failed directory sync does
not register an object and a subsequent attempt retains exact readable bytes.
This is syscall-order/fault-injection evidence, not a hardware power-cut test.

### R2: Closed Under The Accepted Ruling

`capture_lock.py:151` uses the existing `src.ibkr_gateway_lock.lock_dir()` authority.
The synchronization filename binds SHA256 of the effective absolute capture root
and a separate writer or normalized-CIK suffix. These are distinct files in the
trusted coordination namespace, not capture-root contents. No root-wide capture
or market lease is held across the issuer's provider waits.

Descriptor walking still uses O_DIRECTORY/O_NOFOLLOW. Coordination file opening
uses O_NOFOLLOW/O_NONBLOCK and fstat regular-file validation; flock remains real,
nonblocking and crash-released. Only the path authority is reused from the IBKR
module, not its permissive FileLock fallback.

Verified passing owners:
- `test_capture_root_lock_replacement_cannot_admit_another_owner` covers ignored
  capture-root writer and issuer names, including normalized CIK.
- `test_live_worker_cannot_be_recovered_but_dead_worker_can` replaces the old
  capture-root pathname while a child owns a live reservation; recovery remains
  busy, preserves six reserved bytes, then charges the orphan after child death.
- `test_trusted_lock_namespace_rejects_symlink` retains namespace safety.
- `test_issuer_refresh_exclusion_does_not_hold_capture_writer` retains distinct
  issuer/capture lock scopes.

Accepted operational preconditions: all cooperating processes use the same
configured coordination authority; its directory and live lock files are not
replaced while the application runs. Capture cleanup does not own that namespace.
This is not an OS sandbox and does not protect against an actor changing every
lock authority. Live store relocation is not granted by the offline move test.

### R3: Closed

`captures.py:49` obtains all three accounting totals in one SQL statement using
scalar subqueries, so SQLite supplies one statement snapshot. No Store connection
default or schema change was required.

Verified passing owners:
- `test_status_uses_one_sqlite_snapshot`
- `test_status_reservation_conversion_uses_one_snapshot`

The second exercises a real normal-put reservation/orphan-to-object conversion
after aggregate fetch, and the returned total remains four rather than becoming
zero. This supplements the SQL-shape test with the reported interleaving.

### R4: Closed For The Reported Failure Paths

`capture_lock.py:15` preserves ENOSPC as `storage_space_insufficient`, distinguishes
path-shape failures, and maps other initialization/lease I/O failures to the closed
write-failure code. `captures.py:21` centralizes OSError/SQLite normalization for
put, preflight, recovery and status. Existing typed busy/platform/validation errors
are not replaced by generic errors.

Verified passing owners:
- `test_directory_enospc_is_capacity_failure` for root, objects and staging.
- `test_lease_creation_enospc_retains_capacity_code` for coordination-file creation.
- `test_public_capture_operations_normalize_raw_failures` for preflight EIO and
  recovery SQLite errors.
- `test_directory_sync_failure_then_retry_never_publishes_missing_bytes` for EIO
  during directory durability work.

These tests assert exact closed codes, excluding injected private-detail text.
Path revalidation in `assert_current` still treats inability to establish current
directory identity as `capture_path_unsafe`; this approval is not a claim that
every filesystem syscall failure has an independently tested errno taxonomy.

## Preservation And Concurrency

The additional partial-stage and post-registration cleanup owners pass:
`test_partial_stage_write_remains_charged_after_recovery` and
`test_post_register_cleanup_failure_preserves_readable_object`. They prove the
reservation protects the attempted allocation, recovery charges actual retained
partial bytes, and cleanup failure does not destroy a committed readable object.

Existing exact-byte/hash reads, duplicate accounting, reduced-budget readability,
missing/corrupt-object rejection, interrupted publication, orphan charging and
relocation controls remain green. The real racing-destination test retains the
existing bytes and rejects registration. No implicit pruning or overwrite path
was introduced. The deliberate POSIX-only, typed-unsupported platform boundary
remains accepted; no Windows readiness is implied.

Fresh targeted service owners also pass:
- `test_real_provider_and_parser_run_outside_sqlite_market_and_capture_write_locks`
- `test_same_issuer_overlap_is_rejected_without_overwriting_receipt`
- `test_different_issuer_refresh_is_allowed_during_provider_wait`

These exercise mocked provider waits and real fixture SQLite/market/capture lock
availability. The same-issuer lease encloses resume/latest receipt reads and writes
without serializing other issuers or holding a capture writer during acquisition.

## Verification

Fresh reviewer executions, both exit code 0:
1. The two Task 2 test files: **35 passed in 0.80s**.
2. The three targeted service owners above: **3 passed in 0.80s**.

Both used this runner prefix from `/tmp/arkscope-listing-sec-macro-convergence`:

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review2-tests /home/hyl/.virtualenvs/llm_app/bin/python .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py -q
```

Run 1 appended `tests/test_sec_research_capture_lock.py` and
`tests/test_sec_research_captures.py`. Run 2 appended the three fully qualified
`tests/test_sec_research_service.py::<owner>` node IDs listed above.

Also inspected the parent's archived XML: `task2-review-red.xml` records 30 cases,
8 failures and no errors/skips (22 passed), with the expected durability,
accounting, ENOSPC/raw-error and lock-replacement failures. The parent's
`task2-fix-complete.xml` records 35 cases and zero failures/errors/skips. These
historical RED results were inspected, not rerun by reverting or mutating source.

No new agents, source/test edits, source mutations, inverse mutations, commits,
production paths or provider requests were used. Test state stayed in the
designated review fixture workspace. This report is the only authored file in
this re-review. The full backend suite was not run here; large-store recovery
lock-duration and hardware crash behavior remain outside this scoped approval.

## Reviewed Fingerprints

The four Task 2 SHA256 values were identical before and after fresh verification:

```text
17aba0183ebad1bbaef1f8be8b21e95850db74a15c58f8d196c05414c1d69b5a  src/sec_research/capture_lock.py
7429b7e12cc1df9645fa2a97d97c0a043f5c80aff7f21f556e5fb136f1981793  src/sec_research/captures.py
ce86211168a75089bd0fdb064bc372ab67b6dcbaeac182dd01a060b47e2f06dc  tests/test_sec_research_capture_lock.py
51151fbb436f0e15d566d948608928ead020f8ead1c784ba22f5936c281d3a6a  tests/test_sec_research_captures.py
```
