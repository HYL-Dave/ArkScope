# C10 Preflight And Implementation Receipts

## Scope And Authorization

- Workspace: `/tmp/arkscope-research-output-boundary`.
- Branch: `codex/sec-research-integration`.
- Read-only preflight HEAD: `5d979910c31dc419eb3b3528ec25ea190266b232`.
- Explicit GO received; implementation baseline HEAD: `07bd1d25472d1c0bbdec440bde27396402eb4d73`.
- Controller-authorized scope correction received at observed HEAD `fc3c4668609c18cb3afb4efc9d18159c85bacdd1`: delete the entire orphaned FileBackend, preserve all raw data and current SQLite/SA readers. The revised binding plan supersedes the initial raw-reader-retention premise.
- Binding plan: `docs/superpowers/plans/2026-09-13-file-news-boundary-cleanup.md`; audit C10 in `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md`.
- No product/test writes or test runs occurred before GO. No subordinate agents, index changes, commits, installs, service operations, providers, private configuration, or production stores are part of this work.
- Applicable guidance checks found no AGENTS.md in the workspace, relevant source/test/document ancestors, current SDD ancestors, `/`, or `/tmp`. The explicitly permitted main-root AGENTS.md guidance check also found no file; no main-root source/data/config was opened.
- Skills read: using-superpowers, executing-plans, using-git-worktrees, test-driven-development (including writing-good-tests), verification-before-completion, and requesting-code-review. Existing workspace and the user's no-agent/no-commit restrictions govern execution and self-review.
- The receiving-code-review skill governed the amended scope; finishing-a-development-branch is applied as an uncommitted handoff only. The controller owns integration and independent review.

## Plan Self-Review

- `LocalMarketBackend._files` is only constructed; no scoped Python caller uses it. Prices, normalized news, health, ticker listing, and financial_cache already use `_market`.
- Keep `LocalMarketBackend.query_fundamentals`, both shared protocols, all actual query implementations, and `DataAccessLayer.base_path` unchanged.
- `SACaptureBackend` must keep its Path import: `_sa_recovery_read` uses it for missing-store handling.
- Initial plan required retaining FileBackend construction and raw-reader methods. That requirement is superseded: no live consumer remains after `_files` removal, so the whole module must be deleted after fresh physical/import-absence RED. Initial checks are historical evidence only.
- Constructor/import searches covered Python in `src`, `tests`, `data_sources`, and `apps`, excluding dependency/build directories. No external product constructor collateral was found.
- **Initially missing collateral, now authorized:** `tests/test_sa_routing.py`. `_StubSABackend.__init__` (original line 15) retains base_path, and assertions at original lines 68 and 108 require forwarding. Controller explicitly included this file and its regression scope with the correction.
- Implemented collateral handling preserves routing/settings assertions and moves the two useful path assertions to `DataAccessLayer._base`, instead of preserving the obsolete backend argument or deleting path coverage. The default-path assertion now checks the exact workspace root.
- `tests/test_sa_article_reconciliation_backend.py`, `tests/test_sa_tools.py`, and `tests/test_news_feed_content_route.py` construct the real backends without base_path and need no constructor edits.

## Checklist

- [x] Scoped source/caller/test preflight and plan self-review.
- [x] Explicit GO and clean implementation baseline verified.
- [x] Scoped baseline: 312 collected, 311 passed, 1 skipped, zero failures/errors.
- [x] Confirm missing constructor-collateral authorization.
- [x] Record independent RED failures and passing raw-news controls before product edits.
- [x] Record revised physical/import-absence RED with current SQLite news positives before whole-module deletion.
- [x] Apply only the authorized product and constructor-collateral changes.
- [x] Complete full scoped regression and all authorized supplemental regression.
- [x] Review exact diff, retained-owner hashes, caller census, and all process completion.

## Command Receipts

All runs use `env -i PATH=/usr/bin:/bin /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py NAME backend ...`.

- `c10-impl-baseline-01`: exact 13-file regression list in the binding plan; exit 0; 311 passed, 1 skipped in 13.12s. `command.json`, `output.log`, and `results.xml` are in the same-named current-plan directory. No test changes preceded this run.
- `c10-impl-red-01`: `backend -q tests/test_data_access.py::TestBackendProtocol tests/test_data_access.py::test_file_backend_reads_retained_raw_news tests/test_data_access.py::test_runtime_backend_module_graph_matches_current_local_modules`; exit 1; 6 collected, 4 failed, 2 passed in 0.93s. The two current-month Parquet controls pass with and without dedup_hash, exercising exact nonempty contents, ticker/source/date filtering, both deduplication modes, and ticker listing.
- After RED completed and before product edits, `git --no-optional-locks diff --exit-code --no-ext-diff --` on all four authorized product paths exited 0 with no diff.
- `c10-impl-green-01` (historical intermediate implementation): the original 13-file scope, exit 0; 316 collected, 315 passed, 1 skipped in 13.58s. This did not finish the revised task.
- `c10-cosmetic-green-01`: `backend -q tests/test_sec_transport_cancellation.py`; exit 0; 5 collected/passed in 0.35s. Static comparison to the implementation baseline proves only the final extra newline was removed and its AST is identical.
- `c10-revised-baseline-01`: `backend -q tests/test_sa_routing.py tests/test_abandoned_surface_cleanup.py tests/test_legacy_iv_retirement_boundaries.py`; exit 1; 33 collected, 31 passed, 2 failed in 1.21s. The two failures are exactly `test_both_on_one_instance_serves_both` and `test_baseless_dal_constructs_current_local_owner`, whose obsolete backend.base_path assertions were reported in preflight. This ran before editing any of these three files.
- `c10-revised-red-01`: `backend -q tests/test_abandoned_surface_cleanup.py::test_file_backend_is_physically_absent tests/test_abandoned_surface_cleanup.py::test_file_backend_is_not_importable tests/test_sqlite_backend.py::test_query_news_unscored tests/test_sqlite_backend.py::test_local_market_serves_local_rows`; exit 1; 4 collected, 2 failed, 2 passed in 0.58s. Both absence assertions failed because the source file and import spec still existed; both current SQLite news/price fixture controls passed. This run finished before whole-module deletion.
- `c10-revised-green-01`: original 13-file regression scope plus `tests/test_sa_routing.py`, `tests/test_abandoned_surface_cleanup.py`, `tests/test_legacy_iv_retirement_boundaries.py`, and `tests/test_sec_transport_cancellation.py`; exit 0; **351 collected, 350 passed, 1 skipped, zero failures/errors** in 14.21s. Full argv, sanitized runner environment, output, and JUnit cases are in `c10-revised-green-01/command.json`, `output.log`, and `results.xml`.

The single skip in both original 13-file runs is the existing manual live-SEC test `tests/test_detailed_financials.py::TestLiveTechMetrics::test_nvda_tech_metrics`; no provider test was enabled.

Expected RED IDs, all observed before product edits:

1. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_has_no_price_authority`: query_prices is present.
2. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_has_no_fundamentals_authority`: query_fundamentals is present.
3. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_is_not_data_backend`: nominal conformance is still true.
4. `tests/test_data_access.py::test_runtime_backend_module_graph_matches_current_local_modules`: subprocess reaches its loaded-module assertion and reports exactly `src.tools.backends.file_backend` as the unexpected module.

## Final Test Accounting

Counts and node differences were parsed from the runner's JUnit XML with `xml.etree.ElementTree`, not inferred from source-function counts.

- Original 13-file baseline: 312 nodes. Initial leaf-only implementation: 316 nodes (+4 net: replaced one nominal protocol case with three cases, and added two parameterized raw-Parquet cases).
- The amended implementation supersedes all five unshipped FileBackend cases listed below and adds two named whole-module absence owners. The runtime module-graph owner remains and excludes FileBackend.
- Final original 13-file scope: 311 collected, 310 passed, 1 skipped. Supplemental files: routing 11 passed; abandoned surfaces 20 passed; IV boundaries 4 passed; cancellation 5 passed. Combined: 351 collected, 350 passed, 1 skipped.
- Across the same final 17-file scope, the original baseline union had 350 nodes. Final delta is **+2 named absence cases, -1 obsolete nominal conformance case = +1 net node**. No other original test node disappeared.
- Original removed node: `tests/test_data_access.py::TestBackendProtocol::test_file_backend_is_data_backend`.
- Added nodes: `tests/test_abandoned_surface_cleanup.py::test_file_backend_is_physically_absent` and `tests/test_abandoned_surface_cleanup.py::test_file_backend_is_not_importable`.

Superseded intermediate nodes (not shipped, receipts preserved):

1. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_has_no_price_authority`
2. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_has_no_fundamentals_authority`
3. `tests/test_data_access.py::TestBackendProtocol::test_file_backend_is_not_data_backend`
4. `tests/test_data_access.py::test_file_backend_reads_retained_raw_news[article-key]`
5. `tests/test_data_access.py::test_file_backend_reads_retained_raw_news[dedup-hash]`

## Final Self-Review

- Deleted the complete 210-line FileBackend module, without aliases or replacements. No actual raw-Parquet data was read, changed, or removed; intermediate test Parquets were only disposable current-plan fixtures.
- `rg -n --glob '!**/node_modules/**' --glob '!**/dist/**' 'FileBackend|file_backend' src data_sources apps` returned no matches (exit 1). The two authorized product prose references are removed.
- AST caller scan of matching Python source/tests in the same roots found 24 direct LocalMarketBackend/SACaptureBackend constructions, zero base_path keywords, and zero unresolved `**kwargs` at those call sites. Exact keyword-only signatures are `LocalMarketBackend(*, market_db)`, `SACaptureBackend(*, sa_db, market_db)`, and matching routing stub. The DAL's useful base_path argument remains.
- Read-only AST/source comparisons against `07bd1d25472d1c0bbdec440bde27396402eb4d73` verified **126 live product function source segments byte-for-byte unchanged**, excluding the three intentionally changed constructors. This includes LocalMarketBackend.query_fundamentals, actual prices/news/financial_cache methods, and SA methods.
- Normalizing only the removed base_path keyword makes each of the eight original mechanical collateral files' full AST equal to baseline. All other assertions are retained. The complete DAL module AST likewise matches baseline after that one keyword removal.
- Removing docstrings for comparison makes the complete news_tools and job_runs_store ASTs equal to baseline; both changes are prose-only.
- The IV boundary AST differs only by the deleted module's two source-list entries. EIR006 differs only by its deleted module classification and obsolete compatibility-docstring assertion/setup. All preexisting abandoned-surface code is unchanged; only two named tests are added.
- In test_data_access, 21 other function source segments are unchanged. The SEC-catalog owner differs only by removing the deleted class's import/tuple membership; its real catalog assertions remain. The module-graph owner differs only by removing the deleted module from its expected set.
- In test_sa_routing, all 11 functions outside the stub constructor, construction helper, and two explicitly moved path owners are unchanged. All 11 routing test nodes remain and pass.
- Cancellation file comparison is exact: current source equals baseline minus one trailing newline, with equal ASTs.
- `git --no-optional-locks diff --check` passed. Diff is limited to the revised plan's 20 product/test paths; no runtime data, dependency manifest, C11 implementation, or other task's source was changed. No new dependencies.
- Every worker-started runner returned and was reaped. A narrow `pgrep -af '[r]un_checks.py c10-'` check found no C10 runner. No worker index write, commit, merge, provider call, installation, restart, or subordinate agent occurred.
- **Remaining blockers: none.** Changes are uncommitted for controller review and integration; the workspace is preserved.

### Retained-Owner Hashes

For live source functions, hashes cover JSON-serialized sorted mappings of qualified function names to exact `ast.get_source_segment` strings. Each before/after mapping was asserted equal. AST hashes use `ast.dump(..., include_attributes=False)` after the narrow normalization described above.

| Retained Source | Function Count | SHA-256 |
|---|---:|---|
| src/tools/backends/local_market_backend.py | 11 | `6bbef64ab5fffb10135b699133a92263a8653dcc85b566c6875041408fbdd5a3` |
| src/tools/backends/sa_capture_backend.py | 56 | `10a5f8584df720e1ce82c90b1a7b4eb3c672d3cd1bf65920f7af5cb3f094d031` |
| src/tools/data_access.py | 59 | `2472552aaaa8746aa9ccfeb6ac77ea45a085d0c7fbafb3c67d1834750f60587a` |
| tests/test_data_access.py (unchanged functions) | 21 | `9c01947664a0eb1a54c2e93479c39fdcf716c259791dccdb106ff9f065d62d4c` |
| tests/test_sa_routing.py (unchanged functions) | 11 | `4451946c520c2ba8c62e742cd57cce25dcdd96b2c02271002bcea715833ea3bc` |

```text
Normalized mechanical-test AST hashes:
b0a40735174055d4f33808e8063a28c476545ecd8f67ec4e9dcb289b5782f19f  tests/test_detailed_financials.py
8f97544076570fd3336ca8ce1842d6cc951bae262350a6a3a30fbbe3a383f1e4  tests/test_stored_sec_projection.py
86ba913d66cb3bb557cbd44cbcd1c3ef69b5b2898e85c6d088a45978f4bdf294  tests/test_active_universe.py
7cdc25cc998be3fc8d8acb23e01d20293e9b9e5773df7ec77514fd928a5d826d  tests/test_sa_local_readers.py
0cb5448485800ad03336cc7b43ca9a6fd01b11ce3af7844f26db8c47e364983d  tests/test_sqlite_backend.py
9da6935b54175bda2fcd548abbebbaaeebde6764c4a2058a8bacb40e471cf9d0  tests/test_security_lifecycle_terminal_workflow.py
aa792bc2e2abd3c952186c0479961e6df195893788d5df85ee536ef07f10aaf3  tests/test_sa_capture_backend.py
fdcebff41c981d0d17a5acb6951ab7fae0d946ed884fd6f58779d6591079fe9f  tests/test_sa_reconciliation_native_host.py

Prose-only normalized AST hashes:
ba725a766ba1e62bd4afd8eaf0fd4034d70011dbc5f077e22f0b9c8bd3ebbb8b  src/tools/news_tools.py
2185c4554d0575775e028aa4e4bc3ff9c9d7b4646d6770b2c75335b2c2a9fd2b  src/service/job_runs_store.py

Unchanged whole-file SHA-256 (before equals after):
e65f6a052871a8b58ac75bf1c6ce0062e642b030f928d53cc483a9089fa7bd32  src/tools/backends/__init__.py
1f368a75bd487d0af46570fe4d88ec650376969166ed69cc784cc5c13a370f27  src/tools/backends/local_capabilities.py
cecf420f4616a60a42852b0abb474264c83cee2c12fd8a778554477188e61484  src/tools/backends/sqlite_backend.py
d55f1fd507e6995b24960acef3ebdd22af672dfc79011b1ab53512f9cd5f4bdb  src/tools/analysis_tools.py
8893a611a0034b4dc9c29e22393cb82bf2f8efd7aab679dea1fa80e46533aec0  tests/test_fundamentals_sec_cache.py
74b3df5ad3e8fe5dfb93d8d2819907f98328b40eb733cce528cb30e1b4390097  tests/test_sa_article_reconciliation_backend.py
5ccfd6c81566a9118ea1b7d819a27554058f038650c26129cdd583f163b88015  tests/test_sa_tools.py
```

## Pre-Edit SHA-256

```text
d043d06868128100bab1707dcea3830fb5d99c2da62214f0d2e61dcd4776ef63  src/tools/backends/file_backend.py
db4fbf1e512188932b83b40ba80a5c968c72a7e8aee1b769e114029c76acbe91  src/tools/backends/local_market_backend.py
926739e43262a48a4f48b39a73e32f17213f87806400deed950571787d1dd24c  src/tools/backends/sa_capture_backend.py
8943123f0cd07d99d70dde92c17b264bf5e853a67c29299612e9055f83e2ba0b  src/tools/data_access.py
daa6a3705337df36e032148c7302ff5b13720de20328738f47f1d6ec04b7db7c  tests/test_data_access.py
3b5e554646b73c684ab5ad813928d898e7ee2049f698dc2887058340daa23e2c  tests/test_eir006_retired_data_boundaries.py
5d11532b7376a1463adfb7de069d7a57d8c9a55ae14a45db7875a561cf4ac0a7  tests/test_sqlite_backend.py
199c6d8bcb7290be503fdb20d11410b31cd2e3c6037977145f92b1ac9095032f  tests/test_detailed_financials.py
3041e1751b61e6cc0754f13698bce224d6208747c2de08d7aef12b691e8d7ee2  tests/test_stored_sec_projection.py
8893a611a0034b4dc9c29e22393cb82bf2f8efd7aab679dea1fa80e46533aec0  tests/test_fundamentals_sec_cache.py
8e9bb82af38c4ef1ca789d1916344963639ec50b81d1f4c6568124b49ce639a8  tests/test_active_universe.py
89712a20b92b4286bf4cabc31320448d7d75960c70ede5fa0f91dd45d3355d7d  tests/test_sa_local_readers.py
8174ffd310fead881074ef5acd3564add364d97a8b71f1dfdfb5af9508122187  tests/test_security_lifecycle_terminal_workflow.py
5dfc0f8098e70d8a913bbfd2c39a7b8bbe4f837141c21d4eef37cbaf0a882d36  tests/test_sa_capture_backend.py
8b4f912542abab3c2948efed8386c698ddae7c5287f4210f940ab0784d27089d  tests/test_sa_reconciliation_native_host.py
74b3df5ad3e8fe5dfb93d8d2819907f98328b40eb733cce528cb30e1b4390097  tests/test_sa_article_reconciliation_backend.py
5ccfd6c81566a9118ea1b7d819a27554058f038650c26129cdd583f163b88015  tests/test_sa_tools.py
ba9b1454dce0377d9f7c026e56f119de0f34fb8e379072458c0d4e4529def5af  tests/test_sa_routing.py
```
