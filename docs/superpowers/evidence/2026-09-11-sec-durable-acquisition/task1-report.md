# Task 1 Report

Status: Task 1 implemented; P2 clock-rollback review fix verified and ready for
parent re-review. No staging or commit. Other agents' changes were neither edited
nor reverted.

Files: `src/sec_research/schema.py`, `src/sec_research/store.py`,
`tests/test_sec_research_store.py`, and this report only. Test-generated logs/XML
are retained in this plan workspace; fixtures use the unique task1-tests root.

## Interfaces

- `schema.install(conn)` / `schema.verify(conn)` preserve plan signatures.
  Store.install holds existing market_write_lock; schema.install owns BEGIN IMMEDIATE.
- Capture shared tables exactly as plan: objects(sha256, object_key, size_bytes),
  reservations(reservation_id, size_bytes), orphans(object_key, size_bytes).
- `Store(paths)` has no constructor effects. `connect(readonly=False)` yields a
  sqlite3.Connection with Row, foreign_keys ON, closes explicitly; readonly is
  mode=ro plus query_only (not immutable). isolation_level=None means no implicit
  BEGIN; callers issue BEGIN/commit explicitly. No constructor I/O.
- `publish(snapshot, *, object_sha256, observed_at, source_url) -> str` stable ID.
- `snapshots(cik, kind) -> list[dict]`, kind `catalog` or `facts`; metadata keys:
  snapshot_id, cik, kind, object_sha256, observed_at, source_url, historical_name,
  historical_files_observed, historical_files, row_count.
  historical_files is a decoded list of parser-shaped dictionaries.
- `catalog(cik)` / `facts(cik) -> list[dict]`: parser field names, nested
  source={sha256, pointer}, plus snapshot_id, observed_at, source_url,
  object_sha256. Facts.value remains exact str. All retained observations returned.
- `record_receipt(cik, *, status, completed, pending, gaps, observed_at) -> dict`;
  `latest_receipt(cik) -> dict | None`. Keys receipt_id (integer), cik, status,
  completed (list[str]), pending (list[str]), gaps (list[dict]), observed_at,
  recorded_at (current UTC, fixed-width microseconds). Latest is receipt_id
  descending only. Both observed_at and recorded_at are diagnostic metadata,
  never continuation-order authorities. Status is closed to ok/partial/unavailable.
  Receipts append on every call.

## Evidence

Actual runs, with matching `.log` and `.xml` stems in this directory:

- `task1-red`: exit 1, 34 setup errors from the intended missing-schema assertion.
  This is initial missing-module RED, not 34 executed assertion failures.
- First implementation run: 33 passed / 1 failed. Isolated an interpreter behavior
  where set_authorizer(None) still rejects subsequent SQL; an in-memory SQLite
  probe reproduced it. Reset the test callback explicitly to SQLITE_OK instead.
- `task1-transaction-red`: exit 1, 1 failed / 33 passed, asserting the parent-requested
  explicit-transaction connection mode. GREEN set isolation_level=None.
- `task1-replace-red`: exit 1, 5 failed / 38 passed. INSERT OR REPLACE bypassed
  UPDATE/DELETE triggers. Added canonical insert-conflict triggers on immutable
  tables, including unique object-key and explicit rowid conflicts. No triggers
  or new columns on mutable reservations/orphans.
- `task1-time-red`: exit 1, 1 failed. Variable-width ISO timestamps incorrectly
  ordered zero-microsecond receipts after later fractional timestamps. Initial
  GREEN used fixed-width microseconds. The P2 fix below supersedes timestamp
  ordering entirely; this test now proves clock samples/format cannot displace
  the latest append, including equal recording timestamps.
- `task1-final-store`: exit 0, **44 passed**, 0.77s.
- `task1-final-focused`: exit 0, **348 passed** (store + existing catalog, facts,
  common, paths and config owners).
- `task1-final-integration`: exit 1, **411 passed / 1 failed**, 5.31s, including
  concurrent capture/service tests. Failure outside this task's write set:
  `test_issuer_refresh_exclusion_does_not_hold_capture_writer` could not import
  `issuer_refresh` from the concurrently developing capture_lock module. Parent
  notified; no unrelated edits made and no full-integration success claimed.

Required inverse mutations were run in memory after the offline runner installed
its audit fence and fixture environment; no shared source was changed. Each log
prints the exact injected mutation. Each targeted owner failed by assertion:

- `task1-inverse-shape`: schema.verify bypassed; shape-mismatch owner killed all
  3 parameter cases (wrong CHECK, unexpected owned table, owned view).
- `task1-inverse-float`: publication coerced exact value to float; precision owner
  failed on `1234567890.12346` versus `1234567890.123456789012345678900`.
- `task1-inverse-overwrite`: deleted the issuer's old source rows/snapshots before
  publishing (with corresponding deletion guards removed in the mutated schema);
  retention/idempotency owner failed because only 1 snapshot remained instead of 2.

All actual test runs used:

```text
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/task1-tests /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py tests/test_sec_research_store.py -q
```

Runs append named test files/owner selectors and `--junitxml` as described above,
with stdout/stderr redirected to the matching log. Inverses wrap the same runner
via runpy and inject into pytest.main after runner initialization.

## Review And Boundaries

- No schema migration/repair: an existing incomplete or differently defined owned
  schema is rejected, before creating anything. Unrelated populated tables remain.
- No lifecycle imports, financial_cache mutations, network/provider calls, config,
  token or production DB reads. Existing market_write_lock is the only shared
  write-lock dependency. No dependencies, installation, agents, merge or push.
- Object metadata must exist, source SHA must match throughout parsed observations,
  and object keys must be portable. CaptureStore remains responsible for actual
  original-byte length/hash verification; publish receives no original body.
- Publication and receipts reject oversized normalized JSON/row inputs before
  writer lock/BEGIN. Hard constants are 67108864 bytes and 100000 rows.
- Snapshots retain first observation metadata when re-published; every receipt
  append records the new attempt/time. No current-source overwrite or pagination.
- New insert-conflict triggers mean a fixture created before this final schema
  must be recreated, not silently upgraded. This is canonical pre-release DDL.
- Parent re-review is still required. The historical concurrent issuer_refresh
  failure above was assigned to its owner; the capture suite was not re-audited
  in this P2 follow-up. No independently spawned reviewer per user instruction.

## P2 Review Fix

Finding verified from `task1-review.md`: wall-clock rollback could hide a newer
pending receipt behind an older complete receipt, incorrectly short-circuiting
service resume. `latest_receipt()` now selects `ORDER BY receipt_id DESC LIMIT 1`.
The canonical lookup index is `(cik, receipt_id DESC)`. AUTOINCREMENT IDs advance
for committed appends under the existing short BEGIN IMMEDIATE transaction;
within serialized issuer refresh, a later committed checkpoint has a greater ID.
Neither caller observation time nor adjustable wall-clock recording time controls
continuation. No timestamp, return shape, capture table, or lock contract changed.

The existing canonical receipt index changed in place in source, not through a
migration or deployed DB operation. Old disposable fixtures need fresh creation.

Actual follow-up runs (same isolated offline environment, matching log/XML stems):

- `task1-review-fix-red`: exit 1, **2 failed / 46 passed**, 0.93s. The new
  `test_latest_receipt_survives_clock_rollback_and_reopening` selected the old
  complete receipt after an hour-long rollback; the canonical index owner also
  failed because recorded_at was still an index key.
- `task1-review-fix-green`: exit 0, **352 passed**, 3.38s. Store plus existing
  catalog/facts/common/paths/config tests; 48 store cases now included.
- `task1-review-fix-inverse-order`: exit 1, **1 failed**, 0.30s. Restoring only
  `ORDER BY recorded_at DESC, receipt_id DESC LIMIT 1` in memory made the new
  rollback/reopening owner fail, selecting receipt 1 instead of receipt 2. The
  log prints the exact injected code. Shared source never contained the mutation.
- `task1-review-fix-final`: exit 0, **95 passed**, 2.70s. Fresh store plus actual
  service tests after the inverse run; no production or provider access.

The rollback owner also verifies both diagnostic timestamps remain unchanged,
both receipts are retained, and a new Store instance reopens the latest pending
state. Existing backdated-observation and equal/fractional-clock owners remain.

### Independent R4 Input-Limit Self-Check

Input admission is separate from P2 receipt ordering. No runtime limit changed.
Added persisted receipt row/byte-limit owners corresponding to the independent
reviewer's earlier in-memory probes, with forbidden-writer-lock assertions and
an admitted-write positive control after restoring normal limits.

`task1-review-fix-r4-limits`: exit 0, **5 passed / 43 deselected**, 0.27s,
using the store test file with `-k limits`. Owners check:

- Constants remain 67108864 UTF-8 JSON bytes and 100000 normalized rows; a real
  100001-row snapshot is rejected with the typed row-limit code.
- Snapshot row and byte rejection happens before the market writer lock/BEGIN.
- Receipt row and byte rejection independently happens before that lock/BEGIN,
  preserves no failed receipt, and returns the exact typed ValueError argument.
- Valid receipts still append and reopen after rejected input.

The byte-limit tests inject a small ceiling instead of allocating 64 MiB; they
exercise the same production UTF-8 JSON size gate. This is focused input-limit
verification, not an exhaustive memory or WAL bound claim.

## Source Hashes

```text
a51a61c18dd49dfba8853a619ed6e747e1638eef4dd74c74f3c26bf76d081e7c  src/sec_research/schema.py
b38f3466883611f9822eba62179d6870af953dab27991542b6ba72f2513d5c80  src/sec_research/store.py
27ae01a2cf490e4b7cba835aacc5d7f338c7184ce5940dd7da1cc63ebf502525  tests/test_sec_research_store.py
```
