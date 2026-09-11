# Task 3: Resumable Structured Acquisition

Status: implemented and verified in the shared linked worktree.

## Scope

Only this worker's files:

- `src/sec_research/service.py`
- `tests/test_sec_research_service.py`
- This report.

No agents, staging, commits, production DB/config/token access, or network calls.
The parent owns captures, issuer locking and routes; another worker owns schema/store.
Their current implementations were consumed, not edited by this worker.

## Implemented Contract

- `ResearchService(store, captures, transport, *, clock=...)` validates explicit
  normalized CIK, exact integer `max_sources` in 1..16, boolean resume and callback.
- `refresh` takes the parent's separate `issuer_refresh(root, cik)` lease before
  loading or writing receipts, retaining ownership through final readback.
  Same-issuer overlap raises `sec_research_refresh_busy` without another receipt;
  different issuers remain independent. No market/capture writer lease or SQLite
  write transaction spans provider requests or parsing.
- Source locators are `submissions`, `companyfacts`, and deduplicated declared
  historical filenames. URLs are generated from normalized CIK and validated
  locators, never accepted as arbitrary user URLs.
- Initial pending intent is durable before dispatch. Each successful source and
  discovered continuation are checkpointed before the next request. Failures and
  cancellation remain pending. Resume never reacquires checkpointed sources.
- Fresh refresh does not borrow old completed sources or their coverage. Retained
  immutable snapshots remain readable after new failures or revisions.
- Closed statuses are `ok`, `partial`, `unavailable`. No completed source in this
  run means unavailable; success with pending work or gaps means partial. Missing
  `historical_files_observed` remains an explicit `historical_files_unobserved`
  gap even when no known pending locator remains. Observed empty sources can be ok.
- Every service dispatch gets capture preflight. The 256 MiB metadata disk margin
  remains CaptureStore's responsibility. Real SecTransport uses `.body` and
  `.raise_for_status()`, retaining its default 16 MiB metadata bound.
- Whole-body parsing precedes capture publication. Exact original bodies are
  captured before publishing valid snapshots. Malformed bodies can be retained,
  but no successful smaller subset of their fact rows is published.
- Provider exception bodies, URLs and arbitrary codes are not propagated into
  gaps. Actual capture/store closed failure codes, including metadata size/row
  admission failures, are preserved. ENOSPC remains typed.
- `ResearchService(store, None, None).stored(cik)` performs stored reads only,
  returning receipt, current-receipt-derived status, retained row counts and
  snapshot counts. It never materializes all catalog/fact rows, installs schema,
  acquires a refresh lease, preflights captures or calls a provider. Counts refer
  to retained observations across snapshots, not unique current facts/filings.

## RED And GREEN Evidence

All runs used the prescribed clean environment and offline runner below.

1. Initial RED: 27 setup assertion errors, explicitly `Task 3 service missing`.
   These were missing-implementation setup errors, not 27 behavioral failures.
2. First implementation: 27 passed.
3. First real integration: 8 failed / 32 passed. Five failures exposed capture
   code loss; three exposed `complete` versus the store's closed `ok` status.
4. Updated status/count/admission contracts: 21 failed / 22 passed before the
   fix; after alignment, 43 passed with real store/capture persistence owners.
5. Issuer overlap RED: same-issuer owner failed because competing refresh did not
   raise; different-issuer positive control passed. Helper wrapper yielded 45
   passing service tests. A misplaced test tail was corrected before this RED.
6. Added nonempty historical/recent rows, retained revisions, pure-read and real
   transport/storage verification: final service run **47 passed in 2.00s**.
7. Final expanded suite: **439 passed in 7.80s**, no skips or failures.

Final expanded command, run from `/tmp/arkscope-listing-sec-macro-convergence`:

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/task3-tests \
  python .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py \
  tests/test_sec_research_common.py tests/test_sec_research_catalog.py \
  tests/test_sec_research_facts.py tests/test_sec_research_paths.py \
  tests/test_sec_research_config.py tests/test_sec_research_store.py \
  tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py \
  tests/test_sec_research_service.py tests/test_sec_research_routes.py \
  tests/test_sec_transport.py -q
```

For the 47-test service-only run, retain the same prefix and select only
`tests/test_sec_research_service.py -q`.

## Named Inverse Owners

Executed through the same offline runner using a pytest session-start plugin
that modifies only the loaded service module in memory. No worktree mutation
was written. Each inverse exited 1; the final unmodified service run exited 0.

| Inverse | Owner in `tests/test_sec_research_service.py` | Observed result |
|---|---|---|
| Replace `self.captures.preflight()` with `None` | `test_preflight_blocks_first_and_each_later_request` | 2 failed: forbidden provider calls occurred |
| Force `_status` to return ok after any completion | `test_unobserved_history_is_explicit_gap_even_after_noop_resume` | 1 failed: ok instead of partial |
| Drop successful-source checkpoint | `test_real_crash_then_reopen_preserves_checkpoint` | 1 failed: reopened completed list lost submissions |
| Replace `issuer_refresh` with `nullcontext` | `test_same_issuer_overlap_is_rejected_without_overwriting_receipt` | 1 failed: competing refresh did not raise |

## Real Persistence Evidence

- `test_real_sec_transport_body_status_and_default_metadata_bound`: actual
  SecTransport/governor, Store/SQLite and CaptureStore/filesystem; only HTTP session
  responses are fake. Original decimal precision survives; oversize and non-2xx
  responses stay typed and pending. No `response.json()` use.
- `test_real_persistence_reopens_bytes_precision_receipts_and_resume`: new Store
  and CaptureStore instances reopen exact bytes, facts and pending receipts;
  repeated resume makes no completed-source provider calls.
- `test_real_provider_and_parser_run_outside_sqlite_market_and_capture_write_locks`:
  actual nonblocking market/capture locks and `BEGIN IMMEDIATE` succeed at every
  provider and parser boundary.
- `test_real_crash_then_reopen_preserves_checkpoint`: injected SystemExit after
  committed submissions, then reopened SQLite and resumed remaining sources.
- `test_real_malformed_body_is_retained_without_partial_fact_rows`: exact invalid
  source retained, no partial fact rows persisted.
- `test_real_recent_and_historical_rows_and_fresh_failure_keep_old_observations`:
  actual historical/recent rows and amendments, distinct filing/report dates,
  two immutable numeric revisions, and truthful fresh partial coverage.
- `test_real_stored_only_does_not_create_capture_root_or_change_database`:
  installed empty store remains unavailable; DB bytes unchanged and capture root
  absent after a service constructed with no captures or transport.
- Same/different issuer service overlap owners exercise the real lease helper
  from inside fake provider dispatch, with actual SQLite receipts.

## Explicit Limits And Handoff

- Snapshot publication and receipt checkpoint are separate store transactions.
  A crash between them leaves a retained snapshot but a pending source, which
  may be reacquired. This is not exactly-once provider dispatch; completed receipt
  sources do skip provider work. Eliminating that window requires a joint store
  transaction or durable run/source identities beyond the supplied interface.
- Receipts do not link completed locators to particular snapshot IDs. Receipt
  checkpoint time is not a claim that immutable snapshot observation timestamps
  were advanced, nor that the newest historical row is authoritative current state.
- Callback cancellation is checked between service requests, not in flight or
  between SecTransport's internal bounded 429 retry attempts. `max_sources`
  bounds service source dispatches, not raw HTTP attempt count.
- Service crash tests inject SystemExit and reopen real storage; this worker did
  not add a subprocess SIGKILL service test. Process-level lease/capture recovery
  owners remain with the parent and were included in the expanded suite.
- Stored metadata reads still use `Store.snapshots`; no paged query API or
  streaming metadata aggregate was added. Parent GET uses SQL snapshot counts.
- No routes/tools registration, document reader, query paging, source-to-receipt
  linkage, full backend run, production/live validation or independent agent review
  is claimed by Task 3. Parent owns whole-change integration and review.

Final source SHA256:

```text
f0ef5b8c25cc2572930ea171e8504c50af18354a2bc23e8b819d99dbc8356f36  src/sec_research/service.py
0bfed3aafa0ae40c4ffb6131f746d56737e8885efa88555396b3ff7c7fdd8d6b  tests/test_sec_research_service.py
```
