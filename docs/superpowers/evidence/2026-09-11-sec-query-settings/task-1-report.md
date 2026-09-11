# Task 1 Report

Implemented Task 1 only in `/tmp/arkscope-listing-sec-macro-convergence`.

- Commit: `e207b3ad495729958f0f2340cb0a012c6272a521`
- Parent commit: `0658ebf097813875895ecfb7561522860dbfdf69`
- Branch: `codex/listing-sec-macro-convergence`
- Status: implementation, self-review, offline verification, inverse verification,
  and scoped commit complete. Independent task review belongs to the parent.
- No subagent recursion, model override, production data/config/credential access,
  provider calls, dependency installation, merge, push, or activation.
- Parent's working plan edits were not staged, committed, or reverted.

## Committed Files

Only these seven explicitly permitted files are in the commit:

1. `src/sec_research/schema.py`
2. `src/sec_research/store.py`
3. `src/sec_research/service.py`
4. `src/sec_research/queries.py`
5. `tests/test_sec_research_store.py`
6. `tests/test_sec_research_service.py`
7. `tests/test_sec_research_queries.py`

All manual edits used apply_patch. Scratch scripts and evidence are exclusively
under this plan's `task-1/`; this report is at the brief's requested path. No
plan, ledger, route, frontend, facts-query implementation, or other product file
was edited. Existing tests were retained; the service memory double gained the
necessary receipt-shape field. Git hooks and commit signing were disabled for
this local commit to avoid uncontrolled hook/signing side effects.

## Behavior

The canonical receipt has immutable `source_snapshots` JSON. Supplied mappings
must cover completed locators exactly and contain only `snapshot_id` and
`observed_at`. Publication identity, issuer, kind, historical locator, timestamp,
duplicate source states and disjoint pending/completed state are validated.
Omitted mappings persist as explicitly unbound `{}` and cannot authorize queries.
Resuming such a receipt explicitly reacquires its unbound completed sources.

Service checkpoints preserve publication's returned snapshot ID and each source's
capture time. Unchanged bytes retain the same snapshot ID while the new receipt
records the new observation time. Fresh intent is durably unbound before dispatch;
old successful snapshots cannot satisfy it. No schema migration/repair path was
added. AUTOINCREMENT remains, and sqlite_sequence remains SQLite-owned.

Filings queries reopen the receipt named by a strict canonical base64url v1
cursor. Cursor fields are exactly `v`, `cik`, `kind`, `filters_hash`, `receipt_id`,
`bindings_digest`, and `offset`. The token has a 4096-byte ASCII cap, exact scalar
validation, canonical re-encoding, and query/filter/receipt/binding checks. It is
a consistency token, not an authorization credential. Only bound snapshots are
read, including after restart, relocation, and a subsequent refresh.

Forms are stripped, uppercased, deduplicated and sorted; omitted/empty form lists
mean all forms. Base forms include `/A` only when amendments are included. Dates
are inclusive ISO calendar dates. Filtering precedes admission and page limits.
Rows sort by filed date descending, then accession/filing identity and a stable
metadata tie-breaker. Identical selected metadata merges all provenance in
`sources`; conflicting selected variants remain visible with a counted gap.

Every response has exactly status/data/gaps/observed_at/coverage/next_cursor.
Observed empty requires covered catalog traversal. Missing history, receipt gaps,
conflicts, and resource exhaustion remain explicit. Companyfacts-only pending
work does not make a covered catalog query incomplete. Limits are 1..100 whole
rows and 256 KiB of encoded envelope. Sizing uses the actual cursor/envelope;
records fitting that envelope are not discarded for a hypothetical reserve.
Records that cannot fit alone produce `observation_too_large` and advance rather
than repeat indefinitely. Storage failures use a closed unavailable envelope.

## Aggregate Resource Ruling

The parent identified that 100000 rows per snapshot does not bound cumulative
historical snapshots across resumed acquisition. Added, RED-first:

- `MAX_QUERY_ROWS = 100000` admitted matching observations across all sources.
- `MAX_QUERY_BYTES = 64 * 1024 * 1024` encoded admitted metadata plus rows.
- `MAX_QUERY_SOURCES = 1024` admitted source snapshots per query.

Ruling: stream issuer-scoped immutable rows through a pure domain predicate before
admission, rather than materialize entire snapshots or invent a general SQL
filter language. The real SQLite iterator closes on early termination. Metadata
is charged too; sources with no matching rows therefore cannot accumulate without
a bound. Recent submissions are considered first, then historical locators in
deterministic order. Provenance deduplication uses sets, not quadratic list scans.

Exhaustion returns `query_budget_exceeded` with `bound` equal to `rows`, `bytes`,
or `sources`. The query is partial (or unavailable if no source was admitted),
never a false complete/empty result. Coverage exposes `admitted_rows` and
`admitted_bytes`. Pagination covers the admitted selection only; it does not
pretend to traverse omitted observations past an aggregate cap. Narrowing filters
can reduce row/byte admission; the source bound remains independent of filters.

These are encoded working-selection bounds, NOT a measured/hard process-RSS
limit and NOT a claim that output limit alone bounds RAM. Python object overhead,
receipt decoding, and one in-flight SQLite row/source metadata are additional;
the existing publication bounds still govern each immutable source. No 4 GiB
allocation, new dependency, or external acquisition was used for verification.

## Verification

All invocations used the brief's copied `offline_pytest.py`, through
`task-1/run.py`, which constructs a fresh four-key environment for each child,
assigns a separate absolute `ARKSCOPE_OFFLINE_TEST_WORKSPACE` under `task-1/`, and
archives full combined stdout/stderr plus JUnit. No ordinary pytest invocation
with actual HOME/config was used. Example final invocation, from the worktree:

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/task-1/run.py green-final tests/test_sec_*.py tests/test_stored_sec_projection.py tests/test_fundamentals_sec_cache.py tests/test_lifecycle_web_sec_sources.py
```

The runner invokes the harness with `-q` and its own `--junitxml=<label>.xml`.
Artifacts below are relative to `task-1/`; each label has `.log` and `.xml`.

| Label | Result | Coverage |
|---|---:|---|
| baseline | 95 passed | Existing store/service |
| red | 59 failed, 97 passed | Initial binding/query owners plus sequence guards |
| green-initial | 156 passed | Store/service/queries |
| red-edge | 7 failed | Unbound resume, duplicate states, receipt gap, malformed JSON |
| green-sec | 581 passed | All selected SEC and collateral suites at that point |
| red-envelope | 1 failed | Actual-envelope fit versus excessive reserve |
| green-envelope | 49 passed | Query suite before aggregate owners |
| red-aggregate | 5 failed | Aggregate rows/bytes/sources, stream filtering, false empty |
| green-aggregate | 169 passed | Final focused store/service/query suites |
| green-final | 587 passed | All selected SEC and collateral suites after restoration |

Every run had zero collection errors and zero skips. The final focused count is
64 store + 51 service + 54 query = 169, adding 74 cases to the original focused
95. The wider final run adds 418 collateral cases. Full backend/UI verification
is parent-owned and was not claimed here.

Final suite totals: research capture-lock 11, captures 24, catalog 66, common 58,
config 54, facts 54, paths 72, queries 54, routes 12, service 51, store 64;
SEC EDGAR financials 19, SEC tools 13, transport 10, user-agent 5, stored SEC
projection 4, fundamentals SEC cache 8, lifecycle SEC web sources 8 = 587.

### RED Messages

- `Store.record_receipt() got an unexpected keyword argument 'source_snapshots'`.
- `receipts must bind published snapshots` and `new intent must be explicitly unbound`.
- `receipt-bound queries missing` (assertion in test body, not import collection error).
- Unbound resume: no dispatch, or `sec_research_receipt_binding_invalid` at checkpoint.
- Duplicate source states: `DID NOT RAISE ValueError`.
- Receipt gap: actual `empty`, expected `partial`; malformed receipt JSON escaped.
- Envelope boundary: actual `[]`, expected filing `[1]` that fits the actual envelope.
- Aggregate bounds: actual `ok`/`empty`, expected `partial`; the stream guard caught
  `query materialized a whole snapshot before its aggregate budget`.

### Inverse Evidence

All mutants were applied and restored using apply_patch, one at a time, only to
owned files. No mutation was applied while a relevant test subprocess was running.

| Evidence label | Mutant | Named owner and observed failure |
|---|---|---|
| inverse-autoincrement | Remove AUTOINCREMENT | `test_receipt_sequence_does_not_reuse_committed_ids`: failed to raise SQLite full at committed 2**63-1 |
| inverse-latest | Use latest receipt on continuation | `test_cursor_continuation_reopens_pinned_receipt_after_refresh_restart_and_relocation`: cursor mismatch instead of original second filing |
| inverse-filters | Ignore filter hash | `test_cursor_rejects_changed_filters`: all five parameters failed, four admitted the changed filter/limit without error |
| inverse-sequence-owner | Treat sqlite_sequence as SEC-owned schema | `test_sec_schema_leaves_unrelated_autoincrement_sequence_owned_by_sqlite`: schema mismatch during installation alongside unrelated sequence |
| inverse-aggregate | Disable aggregate row guard | `test_aggregate_bound_across_historical_snapshots_is_explicit_partial[rows]`: actual ok instead of partial |

The five inverse runs produced 1, 1, 5, 1, and 1 named failures respectively,
with zero collection errors. `hashes.py` compared all seven file byte hashes with
`hashes-before.json` after EACH restoration. Evidence is
`hashes-after-autoincrement.json`, `hashes-after-latest.json`,
`hashes-after-filters.json`, `hashes-after-sequence-owner.json`, and
`hashes-after-aggregate.json`. `hashes-committed.json` matches the same baseline.
The subsequent 587-case green run includes every inverse owner. Both working and
staged `git diff --check` passed before commit.

## Exact Helper Handoff For Task 2

Public signatures in `src/sec_research/queries.py`:

```python
StoredQueries(store)
StoredQueries.filings(self, cik, *, forms=None, filed_from=None, filed_to=None,
                     include_amendments=True, cursor=None, limit=20)
query_date(value)
open_query(store, cik, *, kind, filters, cursor=None)
read_bound_sources(store, context, *, kind, row_filter=None)
page_envelope(context, rows, *, limit, gaps, available, coverage=None)
unavailable_envelope()
```

- `query_date` returns None or a validated ISO date, otherwise
  `ValueError('sec_research_query_invalid')`.
- `open_query` returns frozen `QueryContext(cik: str, kind: str,
  filters_hash: str, receipt: dict | None, bindings_digest: str, offset: int = 0)`.
  Use kind `facts` for receipt-bound facts queries. Pass a normalized JSON-safe
  filters dict including the exact integer page limit; domain validation belongs
  to the caller. Cursor errors are `sec_research_cursor_invalid` or
  `sec_research_cursor_mismatch`. Storage errors propagate to the domain adapter.
- `read_bound_sources` accepts kind `facts` or `catalog` and a pure optional
  `row_filter(row) -> bool`. It returns frozen `BoundSources(sources: dict,
  gaps: list, row_count: int, encoded_bytes: int)`. `sources` maps each locator to
  `(snapshot_metadata: dict, admitted_rows: list[dict])`. Preserve `gaps` in the
  final result. It does NOT infer domain coverage or request concepts.
- Bound rows include snapshot_id, source_url, object_sha256, source
  `{sha256, pointer}`, and receipt-specific observed_at, plus the original stored
  observation fields. Facts retain exact string values, without float conversion.
- `page_envelope` consumes already admitted, domain-filtered, deterministically
  sorted rows, bounded typed gaps, availability, and optional bounded coverage.
  It owns offset validation, whole-row/byte limits, next cursors and the closed
  envelope. Do not discard resource gaps or reapply latest selection to a page.
- `unavailable_envelope()` is the shared sanitized storage-error result. The
  filings adapter catches sqlite3.Error, OSError, JSONDecodeError, schema mismatch
  and binding mismatch while preserving caller/cursor validation exceptions.

Public read/store signatures added in `src/sec_research/store.py`:

```python
Store.record_receipt(self, cik, *, status, completed, pending, gaps, observed_at,
                     source_snapshots=None)
Store.receipt(self, cik, receipt_id)
Store.snapshot(self, cik, snapshot_id)
Store.bound_snapshot(self, cik, locator, binding)
Store.snapshot_observations(self, cik, snapshot_id)
Store.iter_snapshot_observations(self, cik, snapshot_id)
```

`receipt` and `snapshot` return dict/None scoped to CIK. `bound_snapshot` validates
issuer/kind/historical locator and returns metadata, or raises the closed binding
error. `snapshot_observations` returns a list and is NOT the aggregate-query
loader. `iter_snapshot_observations` yields rows through a read-only SQLite
connection; use `contextlib.closing` when traversal can stop early. The shared
bounded loader already does so. Missing/foreign snapshots yield no observations.

Task 2's explicit immutable `fact_ids` mode, per the parent's amended plan, must
bind requested IDs plus retained snapshot identities independently of a current
receipt. That mode is not implemented by Task 1's receipt opener; extend the
shared cursor/context mechanics for that alternate identity rather than invent a
fake current receipt or duplicate envelope/pagination logic. No `.facts` entry
point or concept/revision/period selection is claimed in this commit.

## Self-Review And Remaining Work

Self-review traced source publication through fresh intent, unchanged capture,
resume, receipt reopening, history coverage, filter normalization, provenance
merging, cursor validation, and both resource bounds. It found and fixed the
unbound-resume, receipt-gap, JSON-error, exact-byte-reserve, and aggregate-memory
issues above, with additional RED evidence. No known Task 1 blocker remains.

Independent review was not recursively dispatched, as explicitly instructed.
The parent should review this commit and report before proceeding with Task 2;
full backend, endpoint/UI integration, and broader release completeness remain
outside this task. The linked worktree and all ignored evidence are preserved.

## Fix Round 1: Decoded Receipt Validation

Review finding: Important P2 in `task-1-review.md`, independently reproduced by
`task-1-review-probe/test_receipt_shape.py`. Valid JSON with an invalid receipt
shape escaped the stored-query unavailable boundary. The original review probe
was read, then its named owner was promoted into the allowed real-code tests;
the frozen probe and review artifacts were not modified.

**Scoped fix commit:** `7a1b9d9933919e327701c3ed713272a6e1da0348`, parent
`e207b3ad495729958f0f2340cb0a012c6272a521`.

Exactly three files were staged and committed:

- `src/sec_research/store.py`
- `tests/test_sec_research_store.py`
- `tests/test_sec_research_queries.py`

No edits to `queries.py`, schema, service, API, frontend, Task 2 files, or the
plan/ledger. Other workers' unstaged work was preserved. No production reads,
provider/network calls, agents, installation, merge, push, or activation.

### Fix Semantics

`Store.latest_receipt` and `Store.receipt` now validate decoded values in their
shared `_receipt` boundary before returning any row. The checks cover a canonical
positive receipt ID and CIK, JSON TEXT inputs, completed/pending lists of valid
issuer-specific locators, uniqueness/disjointness, gaps as a list of dictionaries,
receipt timestamps, mapping type, nonempty mapping keys equal to completed
locators, and each binding's exact keys/snapshot-ID/timestamp shape.

The explicitly permitted unbound `{}` mapping remains readable with either no
completed locators or completed unbound locators, and still cannot authorize a
query. Existing permissive gap dictionary contents remain unchanged; this fix
does not invent a new gap-key schema or rewrite retained values. Valid bound
receipts and observation/append-time semantics retain their previous behavior.

The existing writer's locator/state checks were extracted into `_receipt_fields`
and reused by the read boundary, avoiding separate read/write rules. Malformed
decoded state and invalid JSON syntax raise exactly
`ValueError('sec_research_receipt_binding_invalid')`, already handled by the
existing filings query adapter. Validation catches ValueError/RecursionError,
not broad TypeError/AttributeError. No schema repair, coercion or mutation on read
was added. All public helper signatures from Task 1 remain unchanged.

### Round 1 Evidence

All evidence is under this plan's own `task-1/`, using the unchanged offline
harness and runner with fresh isolated HOME/config/database/lock paths and the
brief's environment. Each label below has full raw `.log` and JUnit `.xml`:

| Label | Result | Scope |
|---|---:|---|
| r1-red | 52 failed, 17 passed | All 69 new regression/positive-control cases |
| r1-green | 238 passed | Store/service/query suites, including the 69 new cases |
| r1-inverse | 2 failed | Direct Store and query owners with decoded validation bypassed |
| r1-green-final | 644 passed | Stable SEC and collateral suites after exact restoration |

All four runs had zero collection errors and zero skips. Final focused counts
are store 115, service 51, queries 72 = 238. The final stable run includes 406
additional cases. In-progress HTTP route/API and Task 2 tests were deliberately
excluded; no full-backend or frontend verification claim is made for this fix.

Named new owners:

- `test_receipt_reads_validate_decoded_field_types` (32 cases, including valid controls)
- `test_receipt_reads_reject_invalid_canonical_relationships` (10 cases)
- `test_receipt_reads_validate_inner_snapshot_binding` (7 cases)
- `test_receipt_reads_preserve_explicit_unbound_mapping` (2 cases)
- `test_invalid_stored_binding_shape_has_closed_envelope` (6 cases, promoted probe)
- `test_invalid_stored_receipt_fields_have_closed_envelope` (12 cases)

RED showed missing ValueError rejection at direct Store reads, plus the verified
`'NoneType' object is not iterable`, `'int' object is not iterable`, and related
wrong-field TypeError/AttributeError exceptions at the query consumer. Controls
covered explicit `{}`, valid list fields, and invalid JSON syntax already closed
by the original query adapter. The direct-read cases prevent accidental reliance
on an unavailable result caused merely by missing snapshots.

The inverse inserted an early return immediately after JSON decoding, bypassing
the new decoded-value validation. Both named owners failed:
`test_receipt_reads_validate_decoded_field_types[null-source_snapshots]` failed to
raise the closed ValueError, and
`test_invalid_stored_binding_shape_has_closed_envelope[null]` reproduced the
uncaught NoneType iteration failure. The mutant and restoration used apply_patch.
`r1_hashes.py` checked only the three owned files, so other workers' changing
files were neither included nor restored. `r1-hashes-before.json`,
`r1-hashes-restored.json`, and `r1-hashes-committed.json` have identical SHA-256
values. The subsequent 644-case GREEN includes both owners. Scoped working and
staged `git diff --check` passed before committing.

Final raw GREEN command from the named worktree:

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/task-1/run.py r1-green-final tests/test_sec_research_store.py tests/test_sec_research_service.py tests/test_sec_research_queries.py tests/test_sec_research_capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_catalog.py tests/test_sec_research_common.py tests/test_sec_research_config.py tests/test_sec_research_facts.py tests/test_sec_research_paths.py tests/test_sec_edgar_financials.py tests/test_sec_tools.py tests/test_sec_transport.py tests/test_sec_user_agent.py tests/test_stored_sec_projection.py tests/test_fundamentals_sec_cache.py tests/test_lifecycle_web_sec_sources.py
```

Self-review verified the requested read-boundary correction, unbound controls,
unchanged writer validation codes, no broad exception suppression, and the scoped
commit contents. Ready for the parent's scoped re-review; no agents were spawned.
