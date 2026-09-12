# Independent C10 Review

## Findings

**None.** No source-visible C10 regression, lost current product consumer, or weakened retained safety/routing/database-query contract was found.

Advisory C10 recommendation: **merge / human_review_required**. This is not integration acceptance or permission to merge; the controller owns the full backend gate and census.

## Scope And Identity

- Workspace: `/tmp/arkscope-research-output-boundary`; branch: `codex/sec-research-integration`.
- Immutable base: `fc3c4668609c18cb3afb4efc9d18159c85bacdd1`.
- Immutable head: `885c2a2d19065e37bfba492c0e6b75b17f30ed06`.
- Exact `git diff --no-ext-diff --no-textconv --binary BASE HEAD` SHA-256: `229fd8fe7aeeae147511a155920a6157e02a5af08b42caad73405677016e32c2`.
- Complete diff inspected: 21 files, 51 insertions, 272 deletions. Requirements: `docs/superpowers/plans/2026-09-13-file-news-boundary-cleanup.md`.
- Used using-superpowers, assess-patch-risk (including rubric), and verification-before-completion guidance. No applicable AGENTS.md was found in the checked workspace/ancestor paths.
- Product/test source matched the immutable head before and after the focused run. Concurrent plan title/checklist/status edits were observed, left untouched, and excluded from the reviewed patch; the substantive C10 requirements were unchanged.

## Consumer Provenance

The no-consumer conclusion is independently supported by source, not merely the checkpoint's claim or a green test count:

- At BASE, the only non-test import/construction is `src/tools/backends/local_market_backend.py:14` and `:31`. The entire base class contains no read of `self._files`; news/search/stats/feed, prices, ticker enumeration, and financial-cache methods already delegate to `self._market`.
- `git log -S 'self._files'` identifies `693cf7af` and `3fef138d`. The former's class source shows the historical field consumer was `query_sec_filings`, not a raw-news import/repair path. That delegation is already absent at BASE. This history was examined only to establish ownership provenance, not to re-review prior SEC work.
- Scoped base/head searches across tracked production roots found no raw-reader consumer, hidden constructor caller, or `_load_raw_news` caller outside the deleted class. `src/tools/backends/__init__.py:82` exports only `DataBackend` and `LocalDataCapabilities`, not FileBackend.
- Current roots construct DAL: `src/api/dependencies.py:27`, `src/sa_native_host.py:112`, and the agent constructors. DAL explicitly constructs SACaptureBackend at `src/tools/data_access.py:199`; it has no backend-name/configuration selector. The dynamic imports at `src/service/data_scheduler.py:1430` select the fixed collector adapters at `:134` and `:142`, not backends.
- Current API/news-tool consumers reach DAL methods, then the retained SQLite implementation: `src/api/routes/news.py:122`, `src/tools/news_tools.py:97`, `src/tools/data_access.py:327`, and `src/tools/backends/local_market_backend.py:40`. Historical docs mentions do not establish a current FileBackend contract.

Deleting the whole module therefore removes an unused implementation, not a live fallback. No supported off-repository Python consumer was evidenced; this review does not claim an external-client census.

## Retained Contracts

- **Paths and routing:** `src/tools/data_access.py:167` still accepts `base_path` and structural `backend` injection. Its root, configuration path, and environment/default market/SA paths are unchanged. Only the unused downstream argument disappears. `tests/test_sa_routing.py:41` still checks both exact DB paths; `:66` and `:106` now check the useful DAL-owned root rather than an obsolete stub field. All 11 routing tests passed.
- **Actual data:** All retained LocalMarketBackend method bodies are unchanged. SACaptureBackend changes only constructor forwarding; its SA read/write and Path-dependent recovery logic remain at `src/tools/backends/sa_capture_backend.py:350`. No raw files, current DBs, schemas, migrations, or dependencies appear in this patch.
- **Non-vacuous controls:** Unchanged SQLite fixtures insert real rows and rebuild FTS5. Passed assertions require two AAPL news rows (`tests/test_sqlite_backend.py:139`), exact NVDA/Apple FTS matches (`:148`), eight price bars (`:576`, `:649`), cache readback (`:347`, `:354`), and exact feed counts/facets/pagination (`:430`, `:451`). SA tests require exact IDs/tickers and preservation of stored body/detail fields (`tests/test_sa_capture_backend.py:259`, `:288`). The stored SEC control requires the positive AAPL annual projection through real cache and API consumers (`tests/test_stored_sec_projection.py:216`).
- **Safety and misses:** FTS special-character handling, honest unknown-ticker/search results, and complete typed unavailable feed shape remain unchanged and passed. Existing schema-only/conditional DAL tests were not treated as proof that live data survives.
- **Test collateral:** Removed nominal FileBackend conformance and references to its retired empty methods are superseded by physical/import absence owners at `tests/test_abandoned_surface_cleanup.py:25` and `:29`. The module-graph test still demands exact set equality at `tests/test_data_access.py:112`, with only FileBackend removed; it was inspected, not independently executed. Remaining IV/authority assertions are unchanged. The transport-test hunk removes only the extra EOF blank; Task2/security changes were not re-reviewed.

## Commands And Results

- `git rev-parse`: branch/base/head resolved as above; HEAD remained `885c2a2d19065e37bfba492c0e6b75b17f30ed06` at final verification.
- Exact binary diff, name/status/stat, surrounding base/head source, scoped `git grep`, export/dynamic-loader inspection, and the bounded `git log -S` provenance check completed.
- `git diff --no-ext-diff --no-textconv --check fc3c4668609c18cb3afb4efc9d18159c85bacdd1 885c2a2d`: exit 0, no output.
- Independent focused command below: **32 passed, 0 failed, 0 skipped, 125.24s**; runner exit 0 after 125.666s. It used the prescribed closed-environment runner and disposable fixture stores only.
- Receipts: [command.json](c10-independent-review-885c2a2d-focused-a1/command.json), [output.log](c10-independent-review-885c2a2d-focused-a1/output.log), [results.xml](c10-independent-review-885c2a2d-focused-a1/results.xml).
- The controller's reported 467 passed / 1 existing live-SEC skip was not independently rerun or claimed as this review's result. No full suite, census, provider/network call, private-store read, service operation, source/test/index edit, or git mutation was performed. All sessions started by this reviewer finished.

```sh
python3 -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py \
  c10-independent-review-885c2a2d-focused-a1 backend -q \
  tests/test_abandoned_surface_cleanup.py::test_file_backend_is_physically_absent \
  tests/test_abandoned_surface_cleanup.py::test_file_backend_is_not_importable \
  tests/test_data_access.py::test_local_capability_protocol_matches_inventory_method_set \
  tests/test_data_access.py::test_default_data_access_constructs_current_local_authority \
  tests/test_data_access.py::test_explicit_capability_injection_needs_no_nominal_type_routing \
  tests/test_sa_routing.py \
  tests/test_sqlite_backend.py::test_query_news_unscored \
  tests/test_sqlite_backend.py::test_query_news_search_fts5 \
  tests/test_sqlite_backend.py::test_query_news_search_like_fallback_short_query \
  tests/test_sqlite_backend.py::test_query_news_search_malicious_fts_query_is_safe \
  tests/test_sqlite_backend.py::test_available_tickers_routing \
  tests/test_sqlite_backend.py::test_financial_cache_set_is_local_only \
  tests/test_sqlite_backend.py::test_financial_cache_get_local_first \
  tests/test_sqlite_backend.py::test_news_feed_browse_and_facets \
  tests/test_sqlite_backend.py::test_news_feed_filters_and_pagination \
  tests/test_sqlite_backend.py::test_local_market_serves_local_rows \
  tests/test_sqlite_backend.py::test_news_hard_local_does_not_make_market_strict \
  tests/test_sqlite_backend.py::test_news_feed_local_exception_returns_typed_unavailable \
  tests/test_sqlite_backend.py::test_sa_capture_backend_threads_strict \
  tests/test_sa_capture_backend.py::test_market_news_upsert_conflict_semantics \
  tests/test_sa_capture_backend.py::test_market_news_query_by_ticker_and_fts_keyword \
  tests/test_stored_sec_projection.py::test_positive_annual_sec_cache_is_the_shared_projection_authority
```

## Risk And Limits

Impact if a hidden shared-composition caller were missed: **high**. Regression likelihood: **low**. Protection: **partial**, because this is focused verification, not the controller's full backend/census gate. Recoverability: **easy**, with a code/test revert and no persisted-state conversion. Confidence: **high within the repository-owned C10 scope**.

The principal counterexamples were a real raw-file importer, a DB-path dependency on downstream base_path, and an empty replacement passing superficial tests. Source tracing and the unchanged nonempty controls reject each. Actual private stored-data bytes were deliberately not read; retention here is established from the patch, not from a new data census. Keeping the orphan has low operational risk but retains needless construction/root discovery and misleading compatibility code.

## Validated Assessment

The following object passed `validate_patch_risk_assessment.py -` via stdin with exit 0. No separate JSON file was created.

```json
{
  "schemaVersion": 1,
  "patch": {"repository":"/tmp/arkscope-research-output-boundary","sourceType":"commit_range","base":"fc3c4668609c18cb3afb4efc9d18159c85bacdd1","head":"885c2a2d19065e37bfba492c0e6b75b17f30ed06","changedFiles":["docs/superpowers/evidence/2026-09-12-sec-integration/README.md","src/service/job_runs_store.py","src/tools/backends/file_backend.py","src/tools/backends/local_market_backend.py","src/tools/backends/sa_capture_backend.py","src/tools/data_access.py","src/tools/news_tools.py","tests/test_abandoned_surface_cleanup.py","tests/test_active_universe.py","tests/test_data_access.py","tests/test_detailed_financials.py","tests/test_eir006_retired_data_boundaries.py","tests/test_legacy_iv_retirement_boundaries.py","tests/test_sa_capture_backend.py","tests/test_sa_local_readers.py","tests/test_sa_reconciliation_native_host.py","tests/test_sa_routing.py","tests/test_sec_transport_cancellation.py","tests/test_security_lifecycle_terminal_workflow.py","tests/test_sqlite_backend.py","tests/test_stored_sec_projection.py"],"sha256":"229fd8fe7aeeae147511a155920a6157e02a5af08b42caad73405677016e32c2"},
  "recommendation": "merge",
  "workflowLabel": "human_review_required",
  "impact": {"rating":"high","rationale":"A missed constructor or backend consumer could interrupt the shared local data composition used by API, native host, and agents; passing tests do not reduce this potential impact."},
  "regressionLikelihood": {"rating":"low","rationale":"The exact base has only an unused FileBackend construction, no raw-reader consumer or dynamic backend selector. Retained method bodies are unchanged; 32 focused exact-head tests passed."},
  "regressionProtection": {"rating":"partial","rationale":"32 focused fixture-only checks cover absence, routing, real SQLite news/search/feed/prices/cache, SA persistence, and stored SEC projection. The module-graph subprocess assertion was inspected, not rerun. Full backend and data census remain controller-owned.","exactHeadChecksPassed":true},
  "recoverability": {"rating":"easy","rationale":"Code/test-only revert restores the deleted module and constructor arguments. No migration, stored-data deletion, serialization change, or state recovery is introduced."},
  "confidence": {"rating":"high","rationale":"Exact patch bytes, unchanged checkout source, direct callers, exports, dynamic loading, provenance, and retained test assertions were inspected. Scope is repository-owned consumers, not hypothetical off-repo Python imports."},
  "applicability": {"status":"confirmed","rationale":"The requested cleanup removes an actually imported and constructed orphan from the current local composition; deleting the unused reader fulfills the explicit C10 requirement without removing a retained product query path."},
  "statusQuoRisk": {"rating":"low","rationale":"Keeping the orphan preserves unused constructor/root-discovery work and a misleading raw-file compatibility surface, contrary to the explicit cleanup requirement."},
  "autoMergeExclusions": ["other"],
  "affectedRuntimeRoots": ["src/api/dependencies.py:27 get_dal","src/sa_native_host.py:112 default DAL","src/agents/anthropic_agent/agent.py:264 default DAL","src/agents/openai_agent/agent.py:426 and :599 default DAL"],
  "importantCallers": ["src/api/routes/news.py:122, :141, :153","src/api/routes/prices.py:21","src/tools/registry.py:192 and :217","src/tools/data_access.py:199"],
  "riskDrivers": ["Deletion of a Python module and downstream constructor keyword","Shared runtime composition would amplify an overlooked caller"],
  "protectiveFactors": ["Base LocalMarketBackend methods already use only SQLite for market/news/cache","FileBackend is not exported from the backend package","DAL base_path and explicit structural injection remain intact","No current data authority, stored file, migration, or dependency changed"],
  "materialBoundaries": [{"id":"consumer-reachability","invariant":"Delete only code without a current repository-owned product consumer.","runtimeRoot":"DAL -> SACaptureBackend -> LocalMarketBackend","counterexample":"A raw-news importer, dynamic selector, or retained _files read would lose its implementation. Base searches and caller/export inspection found none; the sole historical delegation was retired SEC filings, already absent at base.","legitimateControl":"Base local_market_backend.py delegates news/prices/cache to _market; head preserves all those bodies. src/tools/backends/__init__.py exports only DataBackend and LocalDataCapabilities; scheduler dynamic imports select collector functions, not backends.","result":"supported"},{"id":"routing-paths","invariant":"Keep actual market/SA DB selection and DAL.base_path behavior.","runtimeRoot":"src/tools/data_access.py:167","counterexample":"Removing downstream base_path might redirect the DB or remove DAL configuration-root capability.","legitimateControl":"Head still resolves DAL._base and both environment/default DB paths before constructing SACaptureBackend. test_sa_routing.py retains both exact DB-path assertions and asserts explicit/default DAL._base; all 11 routing tests passed.","result":"supported"},{"id":"retained-data-contracts","invariant":"Keep nonempty current news/prices/SA/cache results and honest misses without deleting stored data.","runtimeRoot":"LocalMarketBackend -> SqliteBackend; SACaptureBackend -> sa_capture_store","counterexample":"An empty replacement could pass superficial schema assertions while dropping real rows or FTS behavior.","legitimateControl":"No replacement was introduced. Passed unchanged fixture-backed tests assert two AAPL news rows, exact NVDA/Apple FTS hits, eight price bars, cache readback, SA IDs/body preservation, and stored AAPL annual SEC projection; error/empty controls also passed. Patch contains no stored-data or migration changes.","result":"supported"}],
  "validation": [{"name":"git diff --no-ext-diff --no-textconv --binary fc3c4668609c18cb3afb4efc9d18159c85bacdd1 885c2a2d","status":"passed","protects":"Complete immutable diff inspected; 21 files, 51 insertions, 272 deletions; SHA-256 bound above."},{"name":"git diff --no-ext-diff --no-textconv --check fc3c4668609c18cb3afb4efc9d18159c85bacdd1 885c2a2d","status":"passed","protects":"No whitespace errors; unrelated transport-test hunk is EOF-only."},{"name":"run_checks.py c10-independent-review-885c2a2d-focused-a1 backend -q [exact arguments in command.json]","status":"passed","protects":"32 passed, 0 failures, 0 skips in 125.24s; runner exit 0 after 125.666s. No full suite or provider call was run."}],
  "unknowns": [{"summary":"Off-repository Python clients and actual private stored-data bytes were not inspected. No supported external FileBackend consumer was found in the permitted source/docs; controller owns full backend monitoring and census. Advisory recommendation applies to C10 only.","decisionCritical":false}],
  "evidencePlan": []
}
```
