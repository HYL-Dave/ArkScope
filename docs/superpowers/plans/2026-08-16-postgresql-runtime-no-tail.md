# PostgreSQL Runtime No-Tail Implementation Plan

> **Status:** PLAN REVIEW GREEN AT `05e15926`; TASKS 0-3 COMPLETE THROUGH
> PRODUCT TIP `ac2d3395`; SECTIONS 0.7D-0.7E CLASS A COMPLETE;
> SECTIONS 0.7F-0.7G FOCUSED REVIEW GREEN; TASK 4 COMPLETE AT PRODUCT TIP
> `c6bafd07`; TASK 5 STOPPED AT SECTION 0.7H CLASS B LOOPBACK-OWNER
> ADMISSION AMENDMENT REVIEW; TASK 6 REMAINS THE COMBINED
> IMPLEMENTATION-REVIEW GATE; TASK 7, MERGE, PUSH, LIVE TRAFFIC, AND PRIVATE
> OR REMOTE MUTATION NOT AUTHORIZED
>
> **Date:** 2026-08-16
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md`
> (user-approved and Fable-reviewed GREEN).
>
> **Inventory authority:** exact merged-master tip
> `d4677c3d5b8579f95621a62ed056620a083ad1c8`; the canonical inventory is
> `docs/design/pg_runtime_inventory/` and its closeout review is GREEN.
>
> **Required execution skills:** use `superpowers:test-driven-development`
> for every product change, `superpowers:systematic-debugging` for every
> unexpected result, `superpowers:verification-before-completion` before any
> GREEN claim, and `superpowers:requesting-code-review` at the review gates.
>
> **Roles:** Codex authors and implements RED-first only after independent plan
> review. Fable independently reconstructs the literal ledgers and staged
> identities, then reviews implementation and merge readiness. The user owns
> product scope, batching, merge, push, private configuration, remote tables,
> and destructive-data rulings.

**Goal:** remove every tracked PostgreSQL runtime, test, dependency, route,
fallback, archive, name, and narrative from ArkScope while preserving current
local product behavior and fixing scheduler restart continuity to use only its
two local durable authorities.

**Architecture:** `DataAccessLayer` receives one explicit, structurally typed
`LocalDataCapabilities` object whose 36 methods are exactly the inventory rows
assigned to that owner. The normal constructor builds the existing local
market and SA composition directly; it never reads a DSN or infers authority
from a nominal backend class. Existing domain-local stores remain separate
owners.
Application startup uses only local SQLite state, and the scheduler seeds from
`scheduler_state` followed by `JobRunsLocalStore`, with no network probe.

**Stack:** Python 3.10.12, pytest 8.4.1, FastAPI lifespan, local SQLite stores,
Node 22.14.0, Vitest 4.1.8, TypeScript 5.9.3, Vite 5.4.21.

---

## 0. Authority, boundaries, and exact ledgers

### 0.1 Binding implementation decisions

1. This plan consumes the reviewed inventory. It does not run another general
   discovery pass or generally reclassify inventoried surfaces. Sections 0.7f
   and 0.7g are the exact bounded corrections discovered while executing the
   reviewed deletions: they keep the inventory inputs immutable, admit the
   literal complete-bundle and deleted-backlink lists, and protect nine
   collection-only test paths that require no rewrite.
2. The four inventory path sets remain byte authorities:

   ```text
   delete     161  8f343f354e61d34f4b0fd27b04ff0ff2a849c7fc05de422035d3b2feaf067916
   modify     174  cf53aee5a8e93617b8253cfe8b9b8685e61fbc8eaeb2cb607cc8e51954f7317e
   add          1  7a7752d11fc47ec553e85e85099e24582e0ccbc610758b2381b4ca3a3b0b1e48
   protected   22  debc51e928c3606b49e7306eac1dd5ecb8ec668039bcc2ab0a7c61f81da35d5e
   ```

   They are respectively
   `no_tail_delete.paths`, `no_tail_modify.paths`, `no_tail_add.paths`, and
   `protected.paths`. Task 0 byte-compares all four. A changed member or count
   is a stop-and-amend event. These files remain immutable inventory inputs;
   Section 0.7f does not rewrite them. The exact Class B closure supplement in
   Sections 0.7f-0.7g are separately reviewable final-path authorities from
   Task 4 onward, yielding `183 delete / 182 modify / 1 add / 26 protected`.
3. The only capability addition is
   `src/tools/backends/local_capabilities.py`. It is not permission to add a
   second adapter, compatibility module, or generic repository layer.
4. Two inventory `modify` paths contain a retired term in the path itself and
   therefore cannot survive under their old names. They are exact
   ownership-preserving renames, not additions to the capability add set:

   ```text
   apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts -> apps/arkscope-web/src/SettingsLocalStorage.test.ts
   tests/test_news_pg_unreachable.py                       -> tests/test_news_local_authority.py
   ```

   The source paths remain the inventory-owned modify surfaces; the two
   destinations are admitted only as their one-for-one rename targets. A copy
   that leaves the source present, a third rename, or treating either target
   as a second capability addition is a stop. This bounded schema supplement
   must be accepted explicitly in plan review; it is not hidden inside an
   implementation diff.
5. `LocalMarketDatabaseBackend` becomes `LocalMarketBackend` in its existing
   module, and `SACaptureDatabaseBackend` becomes `SACaptureBackend` in its
   existing module. No alias, re-export, tombstone, ignored DSN argument, or
   compatibility subclass remains.
6. `LocalDataCapabilities` is a non-runtime `typing.Protocol`. Product code
   does not call `isinstance`/`issubclass` against it and does not inspect
   method presence to choose an authority. Default construction and explicit
   injection are separate, direct paths.
7. The default DAL builds the current local composition directly from the
   resolved local market and SA paths. Missing local files retain each
   reviewed domain's honest-empty/typed-unavailable behavior. It never falls
   back to `FileBackend`, a remote backend, or a generic alternate authority
   because local state is missing.
8. Pure SA comment helpers currently embedded in the retiring backend move
   into the already-owned `src/tools/backends/sa_capture_backend.py`; no
   second helper module is added. Their current behavior tests remain GREEN.
9. News routing has only current local choices. The two matrix rows whose
   final input previously selected an unavailable route now resolve to the
   existing local writer. Profile/audit markers, status metadata, messages,
   and toggle branches that exist only to describe the retired route leave in
   the same phase.
10. Scheduler seeding reads local `scheduler_state`, then unconditionally
    fills only missing sources from `JobRunsLocalStore`. It performs no socket
    probe and does not create an early run when local history already proves a
    recent attempt.
11. The mounted migration router, migrator, old smoke, connection helpers,
    dependency declaration, Docker/SQL support, archive/history documents,
    and all `183` final admitted delete paths leave with `git rm`: the original
    `161` plus Section 0.7f's exact `22`-path net supplement.
12. All `182` final admitted modify paths are rewritten only as required to
    preserve current local behavior and remove obsolete imports, branches,
    fixtures, names, prose, or backlinks to deleted support: the original
    `174`, minus Section 0.7g's exact nine protected paths, plus Section
    0.7f's exact `17`-path supplement. Any product redesign beyond the
    measured 36-method protocol and the inventory's existing domain owners is
    a stop; it belongs to the later runtime-owner line.
13. The final tracked tree also retires the temporary governance listed in
    Section 0.9. That self-retirement is separate from the immutable product
    path sets because the inventory could not include its own later plan and
    closeout evidence.
14. No remote database, private dump, provider, or production SQLite asset is
    opened. The private `config/.env` is unchanged during implementation.
    Removing its `DATABASE_URL` key is a post-merge operator step that records
    only key absence, never its value.
15. Remote archive-table deletion remains a separately authorized future
    operation.
16. The inventory's 12 direct `psycopg2` importer paths have this exact phase
    partition; dependency removal cannot precede it:

    ```text
    Task 1  data_sources/financial_datasets_client.py
    Task 1  src/sa/comment_signal_backfill.py
    Task 1  src/tools/sa_digest_tools.py
    Task 1  src/tools/sa_tools.py
    Task 1  tests/test_sa_local_readers.py
    Task 2  src/app_records_migrate.py
    Task 2  src/service/data_scheduler.py
    Task 2  src/smoke/pg_unreachable_e2e.py
    Task 3  src/macro_calendar/store.py
    Task 3  src/service/job_runs_store.py
    Task 3  src/service/macro_calendar_health.py
    Task 3  src/tools/backends/db_backend.py
    ```

    Task 1 removes the test import by retiring its already-listed historical
    node; Tasks 2-3 delete the whole-file owners where specified. Task 3 must
    prove all 12 imports absent before deleting the requirement declaration.

### 0.2 Canonical bases

Every backend stream is globally UTF-8 byte-sorted, unique, and terminated by
one newline. Frontend streams use
`path<TAB>normalized Vitest display name`, the same ordering, and one newline.

| Identity | Count | SHA-256 / outcome |
|---|---:|---|
| Backend full | 4,394 | `b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb` |
| Backend native | 4,394 seen | `4,382 passed / 12 skipped / 0 failed`; report `0a58d493ab6b406a2a69fa4cc7b25670373d7a16fd74b85c2b60c9452e07c030` |
| Frontend full | 1,177 / 101 files | `90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b` |
| Inventory-focused union | 1,897 | `57c1b5145529ae0b36f4068406c67d40a7610f5cd0b3472ec0bd9e88dfeefbf9` |
| Dynamic route census | 175 | `488231c63e8c9bb0a28a6baf5e972c959c7eeddf9cc5fa10cdffc3330bc95aea` |

Task 0 freshly reconstructs all five at the reviewed plan tip. The inherited
native result is dated grounding only; this line must run its final native
target after the test retirements.

Pinned inputs:

```text
/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
  09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
/tmp/eir006_vitest_list_normalizer.py
  955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
requirements.txt
  23c8fdf89a6eea4ba242c0ce5f23097626d24e91349420778d223bd488ddeb26
package-lock.json
  5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
apps/arkscope-web/package.json
  dbaecc3792419d833af4ef6659cfee42977f6c43e4066c16d3cc8df9b9912ffa
```

The implementation worktree links only root `node_modules`. Every frontend
command uses `../../node_modules/.bin/vitest` from `apps/arkscope-web`, first
proves exactly Vitest `4.1.8`, and never invokes `npx`, `npm exec`, install, or
download fallback.

### 0.3 Exact local capability ceiling

The inventory has 18 `rewrite_to_local_capability` surfaces. Seven keep their
measured methods on four existing domain owners:
`LocalMarketDatabaseBackend` (including financial cache),
`SACaptureDatabaseBackend`, `MacroCalendarLocalStore`, and
`JobRunsLocalStore`. The remaining 11 surfaces name
`src/tools/backends/local_capabilities.py:LocalDataCapabilities` as their
owner. Their exact UTF-8 byte-sorted method union is 36 rows at SHA-256
`df4f84a6bb8c9eefaf9adeb630a4e7a374c427f5bdc3c9d1915755c99a662370`:

```text
accept_sa_article_link
apply_sa_refresh
audit_unresolved_symbols
get_available_tickers
get_sa_article_with_comments
get_sa_pick_detail
get_sa_refresh_meta
invalidate_dirty_sa_market_news_detail
query_fundamentals
query_health_stats
query_news
query_news_feed
query_news_search
query_news_stats
query_prices
query_sa_article_review_queue
query_sa_articles
query_sa_market_news
query_sa_market_news_body_presence
query_sa_market_news_missing_detail_interval
query_sa_market_news_need_detail
query_sa_market_news_recent_ids
query_sa_market_news_recovery_rows
query_sa_picks
query_sec_filings
reconcile_sa_articles
record_sa_refresh_failure
reject_sa_article_candidate
resolve_sa_reconciliation_event
sanitize_corrupted_sa_comments_counts
save_article_with_comments
save_sa_market_news_detail
update_article_comments
update_sa_pick_detail
upsert_sa_articles_meta
upsert_sa_market_news
```

This is a bounded reconciliation of the committed inventory, not a new
discovery pass. Its evidence prose counted only the 35-method direct
`DataAccessLayer._backend` row, while the canonical `surfaces.jsonl` and
`consumer_methods.tsv` additionally assign measured `query_health_stats` to
the same proposed owner. Conversely, taking the union of all 18 surfaces
would incorrectly produce 58 methods by absorbing existing FRED, job-runs,
financial-cache, and other domain-owner APIs. Plan review must explicitly
accept this `35 + query_health_stats = 36` reconciliation; changing a surface
owner or adding any other method is a stop-and-amend event.

The protocol may use precise existing signatures and imported schema types,
but it may not add lifecycle, connection, configuration, financial-cache,
macro, job-run, or future methods. Those remain with their measured domain
owners. Task 1 includes a structural test that compares the protocol's public
callable names to these literal rows and independently proves the other seven
surface owners retain only their own measured sets.

### 0.4 Whole-file backend retirement ledger

These six test paths are members of the 161-path delete authority. Their
canonical base nodes all pass under the old `.env`-symlink admission. The
migrator and old smoke owners leave with their executable surfaces in Task 2;
the four foundation owners leave in Task 3:

```text
tests/test_app_records_migrate.py              17
tests/test_db_backend.py                       21
tests/test_db_backend_retired_pg_sa.py          1
tests/test_db_backend_retired_prices.py         5
tests/test_macro_calendar_store.py             44
tests/test_pg_unreachable_e2e.py               13
```

Task 2 removes `tests/test_app_records_migrate.py` and
`tests/test_pg_unreachable_e2e.py`, exactly 30 nodes. Task 3 removes the other
four files, exactly 71 nodes. The sum is exactly 101. A partial deletion,
retained test-only import, renamed compatibility copy, or removal of a seventh
test file is a stop.

### 0.5 Backend historical-contract retirements

These 22 retained-file IDs are inventory-classified
`historical_compatibility`. They retire without replacement. Task 1 owns every
row except the five `tests/test_data_scheduler.py` rows, which Task 2 owns.

```text
tests/test_data_scheduler.py::test_default_ibkr_legacy_news_route_fails_before_pg_sync
tests/test_data_scheduler.py::test_legacy_news_route_pg_fails_before_collector_sync_and_mirror
tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync
tests/test_data_scheduler.py::test_pg_reachable_probe_is_bounded
tests/test_data_scheduler.py::test_stale_legacy_pg_news_route_is_retired_before_sync
tests/test_detailed_financials.py::TestFinancialCache::test_pg_cache_hit_path_is_retired
tests/test_market_coverage_boundaries.py::test_market_coverage_package_has_no_provider_gateway_or_pg_runtime_dependency
tests/test_market_data_direct.py::test_normalize_utc_format_matches_pg_literal
tests/test_news_settings_route.py::test_post_exit_profile_marker_rejects_pg_selecting_toggles
tests/test_sa_capture_backend.py::test_read_shapes_match_pg_key_sets
tests/test_sa_comment_focus.py::test_focus_pg_mode_requires_local
tests/test_sa_feed.py::test_feed_pg_mode_requires_local
tests/test_sa_local_readers.py::TestBackfillRouting::test_pg_mode_proceeds
tests/test_sa_local_readers.py::TestDigestLocal::test_pg_dispatch_without_sa_db
tests/test_sa_local_readers.py::TestHealthSplit::test_local_with_pg_up_uses_extension_signal
tests/test_sa_local_readers.py::TestHighValueCommentsLocal::test_pg_dispatch_without_sa_db
tests/test_sa_local_readers.py::TestUnresolvedSymbols::test_local_branch_matches_pg_semantics
tests/test_sa_local_readers.py::TestUnresolvedSymbols::test_pg_dispatch_without_sa_db
tests/test_sa_local_readers.py::test_provider_health_sa_meta_never_touches_pg_on_fresh_profile
tests/test_sa_reconciliation_native_host.py::test_retired_pg_reconciliation_methods_never_connect
tests/test_sqlite_backend.py::test_is_databasebackend_subclass
tests/test_sqlite_backend.py::test_strict_uses_fast_pg_connect_timeout
```

### 0.6 Backend positive replacements

Each row is `old ID<TAB>new ID`. Task 2 owns the 12 rows whose old path is
`tests/test_data_scheduler.py`, `tests/test_news_normalized_routing.py`, or
`tests/test_news_pg_unreachable.py`; Task 1 owns the other 34. Every old ID
occurs exactly once in the canonical base, and every new ID is absent.

```text
tests/test_app_records_store.py::test_no_pg_dependency	tests/test_app_records_store.py::test_imports_with_declared_local_dependencies
tests/test_data_scheduler.py::test_ibkr_news_fails_closed_when_pg_exit_audit_cannot_be_read	tests/test_data_scheduler.py::test_ibkr_news_fails_closed_when_local_route_state_cannot_be_read
tests/test_data_scheduler.py::test_legacy_news_route_local_keeps_direct_writer_without_pg_or_mirror	tests/test_data_scheduler.py::test_local_news_route_keeps_single_direct_writer
tests/test_data_scheduler.py::test_normalized_ibkr_news_route_launches_isolated_worker_without_pg_or_mirror	tests/test_data_scheduler.py::test_normalized_ibkr_news_route_launches_isolated_worker
tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_worker_without_pg_or_mirror	tests/test_data_scheduler.py::test_current_news_route_launches_normalized_worker
tests/test_data_scheduler.py::test_schedule_status_exposes_post_pg_exit_presentation_metadata	tests/test_data_scheduler.py::test_schedule_status_exposes_current_news_route_metadata
tests/test_data_scheduler.py::test_seed_skipped_fast_when_pg_unreachable	tests/test_data_scheduler.py::test_missing_scheduler_state_uses_local_job_history_without_early_fire
tests/test_financial_datasets.py::TestCacheBackendMode::test_backend_without_cache_methods_is_ignored	tests/test_financial_datasets.py::TestCacheBackendMode::test_explicit_cache_capability_is_not_shape_probed
tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_uses_local_market_store_without_pg_fallback	tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_uses_local_market_store
tests/test_fundamentals_sec_cache.py::test_sec_cache_hit_with_local_market_backend_does_not_pg_fallback	tests/test_fundamentals_sec_cache.py::test_sec_cache_hit_uses_local_market_backend
tests/test_macro_calendar_local_store.py::test_no_pg_dependency	tests/test_macro_calendar_local_store.py::test_imports_with_declared_local_dependencies
tests/test_macro_calendar_local_store.py::test_not_null_parity_with_pg	tests/test_macro_calendar_local_store.py::test_rejects_null_required_fields
tests/test_macro_calendar_local_wiring.py::test_health_local_first_without_pg	tests/test_macro_calendar_local_wiring.py::test_health_reads_local_calendar_store
tests/test_market_data_admin.py::test_fresh_profile_without_market_db_uses_local_backend_not_pg	tests/test_market_data_admin.py::test_fresh_profile_uses_local_market_backend
tests/test_market_data_direct.py::test_preflight_touches_no_pg	tests/test_market_data_direct.py::test_preflight_reads_only_local_state
tests/test_news_direct.py::test_no_pg_dependency	tests/test_news_direct.py::test_imports_with_declared_local_dependencies
tests/test_news_feed_content_route.py::test_local_backend_propagates_content_without_postgres_fallback	tests/test_news_feed_content_route.py::test_local_backend_propagates_content_filter
tests/test_news_normalized_routing.py::test_route_matrix[False-False-False-legacy_pg]	tests/test_news_normalized_routing.py::test_route_matrix[False-False-False-legacy_local]
tests/test_news_normalized_routing.py::test_route_matrix[False-None-False-legacy_pg]	tests/test_news_normalized_routing.py::test_route_matrix[False-None-False-legacy_local]
tests/test_news_pg_unreachable.py::test_completed_audit_marker_forces_news_hard_local_without_profile_exit_setting	tests/test_news_local_authority.py::test_local_news_authority_is_default_without_profile_toggle
tests/test_news_pg_unreachable.py::test_news_hard_local_no_dsn_never_calls_pg_for_empty_reads	tests/test_news_local_authority.py::test_local_news_empty_reads_are_honest
tests/test_news_pg_unreachable.py::test_no_dsn_completed_news_exit_selects_local_backend_with_market_strict	tests/test_news_local_authority.py::test_local_news_authority_uses_strict_market_store
tests/test_news_pg_unreachable.py::test_no_dsn_get_conn_fails_before_psycopg	tests/test_news_local_authority.py::test_local_news_authority_initializes_with_declared_dependencies
tests/test_research_threads.py::test_local_only_no_pg	tests/test_research_threads.py::test_local_storage_round_trip
tests/test_sa_capture_backend.py::test_no_pg_fallback_even_on_empty_results	tests/test_sa_capture_backend.py::test_empty_results_are_honest_local_results
tests/test_sa_local_readers.py::TestBackfillRouting::test_routes_to_sqlite_not_pg	tests/test_sa_local_readers.py::TestBackfillRouting::test_routes_to_sqlite
tests/test_sa_local_readers.py::TestHealthSplit::test_non_local_sa_backend_does_not_query_pg	tests/test_sa_local_readers.py::TestHealthSplit::test_local_backend_uses_extension_signal
tests/test_sa_routing.py::test_baseless_dal_gets_no_implicit_local_routing	tests/test_sa_routing.py::test_baseless_dal_constructs_current_local_owner
tests/test_sa_routing.py::test_env_override_flips_without_setting	tests/test_sa_routing.py::test_legacy_environment_overrides_do_not_change_local_owner
tests/test_sa_routing.py::test_market_strict_threads_to_selected_backend	tests/test_sa_routing.py::test_legacy_market_strict_setting_does_not_change_local_owner
tests/test_sa_routing.py::test_news_exit_threads_news_strict_to_sa_backend_without_market_strict	tests/test_sa_routing.py::test_legacy_news_exit_setting_does_not_change_local_owner
tests/test_sa_routing.py::test_sa_plus_market_strict_threads_to_single_backend	tests/test_sa_routing.py::test_legacy_strict_settings_keep_single_local_owner
tests/test_scheduler_state.py::test_no_pg_dependency	tests/test_scheduler_state.py::test_imports_with_declared_local_dependencies
tests/test_sqlite_backend.py::test_financial_cache_miss_is_honest_empty_without_pg	tests/test_sqlite_backend.py::test_financial_cache_miss_is_honest_empty
tests/test_sqlite_backend.py::test_fundamentals_mirror_table_retired_no_pg_fallback	tests/test_sqlite_backend.py::test_fundamentals_query_is_honest_empty_without_a_current_snapshot
tests/test_sqlite_backend.py::test_news_stats_local_empty_does_not_fallback_to_pg	tests/test_sqlite_backend.py::test_news_stats_local_empty_is_honest_empty
tests/test_sqlite_backend.py::test_news_stats_local_when_present_does_not_hit_pg	tests/test_sqlite_backend.py::test_news_stats_reads_local_rows_when_present
tests/test_sqlite_backend.py::test_news_strict_available_news_tickers_empty_does_not_hit_pg	tests/test_sqlite_backend.py::test_news_available_tickers_empty_is_honest_empty
tests/test_sqlite_backend.py::test_news_strict_feed_local_exception_does_not_hit_pg	tests/test_sqlite_backend.py::test_news_feed_local_exception_returns_typed_unavailable
tests/test_sqlite_backend.py::test_p0c_available_price_tickers_empty_is_honest_empty_no_pg	tests/test_sqlite_backend.py::test_available_price_tickers_empty_is_honest_empty
tests/test_sqlite_backend.py::test_p0c_non_strict_prices_still_do_not_fallback_to_pg	tests/test_sqlite_backend.py::test_price_reads_are_local_regardless_of_provenance_toggle
tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg	tests/test_sqlite_backend.py::test_prices_miss_is_honest_empty
tests/test_sqlite_backend.py::test_strict_market_local_miss_is_honest_empty_not_pg	tests/test_sqlite_backend.py::test_local_market_miss_is_honest_empty
tests/test_sqlite_backend.py::test_strict_market_serves_local_without_pg	tests/test_sqlite_backend.py::test_local_market_serves_local_rows
tests/test_trading_day_coverage.py::test_route_coverage_path_is_pure_read_without_provider_scheduler_or_pg	tests/test_trading_day_coverage.py::test_route_coverage_path_is_pure_local_read_without_provider_or_scheduler
tests/test_universe_summaries_local.py::test_summaries_read_local_db_never_pg	tests/test_universe_summaries_local.py::test_summaries_read_local_database
```

These seven backend nodes are genuinely new RED contracts. The four
`tests/test_data_access.py` rows and one `tests/test_tools.py` row belong to
Task 1; the two `tests/test_api.py` rows belong to Task 2:

```text
tests/test_data_access.py::test_local_capability_protocol_matches_inventory_method_set
tests/test_data_access.py::test_default_data_access_constructs_current_local_authority
tests/test_data_access.py::test_explicit_capability_injection_needs_no_nominal_type_routing
tests/test_data_access.py::test_runtime_backend_module_graph_matches_current_local_modules
tests/test_tools.py::test_cli_save_command_uses_injected_local_capability
tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes
tests/test_api.py::test_local_runtime_gate_rejects_external_network_and_cleans_owners
```

Each task adds only its own rows before the matching product change. Task 1
must therefore make all five Task 1 additions GREEN; Task 2 must make both API
additions and all earlier additions GREEN.

### 0.7 Frontend positive replacements

Each row is `old path<TAB>old display name<TAB>new path<TAB>new display name`.
All 18 replacements land together in Task 4. They change no frontend behavior
and keep full collection count and file count constant.

```text
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > does not show the completed App Records migration panel in normal settings navigation	src/SettingsLocalStorage.test.ts	local storage panels > renders only current local storage panels in normal settings navigation
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > ignores retired sync errors and scopes coverage diagnostics to Developer Mode	src/SettingsLocalStorage.test.ts	local storage panels > scopes coverage diagnostics to Developer Mode
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > keeps calendar degradation separate from reviewed-day coverage	src/SettingsLocalStorage.test.ts	local storage panels > keeps calendar degradation separate from reviewed-day coverage
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > keeps corrected single-locale headings without migration narration	src/SettingsLocalStorage.test.ts	local storage panels > keeps corrected single-locale headings
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > keeps unmatched rows and provider issues separate from coverage state	src/SettingsLocalStorage.test.ts	local storage panels > keeps unmatched rows and provider issues separate from coverage state
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > keys_trading_day_coverage_by_lookback_and_forces_only_storage_reads	src/SettingsLocalStorage.test.ts	local storage panels > keys_trading_day_coverage_by_lookback_and_forces_only_storage_reads
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > lists_the_active_data_group_and_its_stable_subsections	src/SettingsLocalStorage.test.ts	local storage panels > lists_the_active_data_group_and_its_stable_subsections
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > offers explicit local confirmation only for listing-status events	src/SettingsLocalStorage.test.ts	local storage panels > offers explicit local confirmation only for listing-status events
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > reloads_mounted_market_and_coverage_status_after_price_invalidation	src/SettingsLocalStorage.test.ts	local storage panels > reloads_mounted_market_and_coverage_status_after_price_invalidation
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > renders English market data and storage outcomes	src/SettingsLocalStorage.test.ts	local storage panels > renders English market data and storage outcomes
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > renders_market_empty_and_macro_partial_failures_as_user_outcomes	src/SettingsLocalStorage.test.ts	local storage panels > renders_market_empty_and_macro_partial_failures_as_user_outcomes
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > shows SEC lifecycle evidence as review material and reloads it after its source runs	src/SettingsLocalStorage.test.ts	local storage panels > shows SEC lifecycle evidence as review material and reloads it after its source runs
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > shows current market data status without projecting retired sync metadata	src/SettingsLocalStorage.test.ts	local storage panels > shows current market data status from current local facts
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > shows_macro_data_with_manual_and_scheduled_refresh_boundaries	src/SettingsLocalStorage.test.ts	local storage panels > shows_macro_data_with_manual_and_scheduled_refresh_boundaries
src/marketDataDisplay.test.ts	macroRoutingLabel > never suggests PG fallback when local macro is inactive	src/marketDataDisplay.test.ts	macroRoutingLabel > labels inactive local macro state without an alternate authority
src/marketDataDisplay.test.ts	macroRoutingLabel > toggle-on but DB not built → local-first, pending ingestion (NOT PG fallback)	src/marketDataDisplay.test.ts	macroRoutingLabel > labels enabled macro with missing local database as pending collection
src/marketDataDisplay.test.ts	marketRoutingLabel > keeps pending-db distinct while disabled setting is no longer PG fallback	src/marketDataDisplay.test.ts	marketRoutingLabel > keeps pending local database distinct from a disabled setting
src/marketDataDisplay.test.ts	news cutover labels > keeps normalized writes visibly pre-exit/test while PG remains available	src/marketDataDisplay.test.ts	news routing labels > renders normalized writes as the current local authority
```

### 0.7a Retained test-evolution boundary

The collection ledgers above account for node retirement, replacement, and
addition, but zero tracked residue also requires bounded edits inside retained
test bodies and shared fixtures. Those edits do not change collection IDs.
They are admitted only through this deterministic projection of the frozen
inventory; a test path's presence in `no_tail_modify.paths` is not by itself
permission to edit every node in that file.

Task 0 rebuilds five UTF-8 byte-sorted, unique, one-final-newline streams from
exact `CANDIDATE_SOURCE_TIP`
`4c6b8d44ce2e768e95b822b11f618cc40f4bb9f0` and the canonical base
collections:

```text
backend retained node bodies  192  32d437fb14b93a6b1e083b5a28b054628f97f135918fcd2fe0f5a3ee944dd9de
backend shared helper scopes    41  0dd3a8c15d575e43294e77fdd9789cd6b01695b362294ff147f9c5328e7f81b8
backend module-level scopes     34  75be6faa2a3bcd491cfbe7ed2e6e4b423d4e1f265375c9c965c9b973a569c42a
frontend retained node bodies   10  7ee29bcb1568b80b43eef59297368b92b46d7b2decefcab4a31506aef7e6d290
frontend shared-fixture paths    9  549232197f4f34673f010573559e88a25d51ac4b6a9efa5fa8ee4e35a5fd6426
```

Before using inventory line coordinates, require zero product/test/dependency
path diff between that candidate source and the plan base. The current
grounding has zero such paths; a later non-doc difference invalidates this
projection and is a stop rather than permission to reuse stale coordinates.

The backend projection consumes exactly 1,029 unique candidate IDs across 57
paths. It uses only candidate rows whose path is a Python test
path in `no_tail_modify.paths`, whose line is present, and which satisfy this
closed relevance predicate:

1. `source_family == text_search`; or
2. `source_family == ast` and `symbol` contains `DatabaseBackend`, equals
   `JobRunsStore` or ends in `.JobRunsStore`, contains
   `MacroCalendarStore`, ends in `._get_conn` or `._make_db_backend`, contains
   `_prepare_comments_for_upsert` or `_plan_comment_duplicate_cleanup`, or is
   exactly one of `db_dsn`, `database_url`, `postgresql://`, `psycopg2`, and
   `postgres_schema`.

Parse the frozen Python source with the pinned Python `ast` implementation and
map each candidate line to its innermost function scope. If that scope is
nested under a `test*` function, map it to the enclosing test function and
expand parameterized instances by exact canonical-base prefix (`node ==
prefix` or `node` starts with `prefix + "["`). Otherwise emit the exact
`path::qualname` helper scope, joining every class/function component with
literal `::`; with no enclosing function emit the path as a module-level
scope. Remove the 22 historical IDs and the old side of all 46 backend
replacements before hashing. The three backend streams together, prefixed
respectively with `body<TAB>`, `helper<TAB>`, and `module<TAB>`, are 267 rows
at
`59113f371937f32c63c8e9a09a79b8b8706640a38e8aa1ec7fd44dfb287c0524`.

The frontend projection consumes exactly 74 unique candidate IDs across 11
paths. It uses TypeScript `5.9.3` to parse only `text_search` candidates in
test paths from `no_tail_modify.paths`. Map a candidate line to
the innermost literal `it`/`test` call and its literal `describe` ancestry,
then join it to the canonical frontend base row. A line outside a test call
emits its full repository path as a shared-fixture path. Remove the old side
of all 18 frontend replacements before hashing. The two frontend streams,
prefixed respectively with `body<TAB>` and `module<TAB>`, are 19 rows at
`778eff1d137fea932ca1f78f0319586632bbeb62e3e92058fe0adecfb10606ed`.

Every input candidate ID must map to exactly one body/helper/module scope key
before parameterized-node expansion and stream deduplication; an unassigned or
multiply assigned candidate is a stop. A single body scope may then expand to
multiple canonical parameterized node rows by the rule above. This is an edit
ceiling, not a requirement to touch every row. A retained node body may only
replace a frozen candidate reference or assertion with the equivalent current
local contract; its node ID and non-retired behavior remain unchanged.
Helper/module/fixture edits are limited to the projected scope and must serve
the same local contract. Any body or shared scope outside these streams, the
explicit replacements, retirements, and seven additions is a stop-and-amend
event. Task 0 stores all five literal streams in its packet so review never
depends on an executor's prose summary.

### 0.7b Task 1 shared-fixture stop amendment

Task 1's first exact owner run collected the pinned `4,382 / c7b9a77a...`
stream, then finished `438 passed / 1 skipped / 5 failed`. Four failures are
inside existing Section 0.7a body/module authority: three assertions still
call removed routing-toggle helpers, and the reviewed SEC-cache fixture must
return its local cached value from the direct capability rather than raising
into a provider fallback. The fifth failure exposed an unlisted shared test
fixture:

```text
tests/test_tools.py::_HermeticMarketBackend
```

`DataAccessLayer.search_news()` now correctly calls the measured
`query_news_search` capability directly. The hermetic backend predates that
direct contract and implements only `query_news`; changing product code to
inspect method presence or retain a compatibility fallback would violate
Sections 0.1.6 and 0.3. Stop condition 19 therefore halted Task 1 before any
product commit.

This amendment authorizes exactly one addition inside the named helper class:
`query_news_search(self, query="", ticker=None, days=30, limit=20)`. It must
derive a fresh frame from the helper's existing `query_news` rows, match the
case-folded query against title and description, preserve the optional ticker
filter, clamp the returned frame to `limit`, reset its index, and perform no
I/O. It may not add another backend method, edit an existing test body, change
the `hermetic_dal` fixture, or weaken the existing two news-tool assertions.
Because this is an absent helper method rather than a test node, all Section
0.11 collection identities and the five Task 0 AST/source streams remain
unchanged; this paragraph is the sole bounded supplement to their edit
ceiling.

The pre-amendment native run also proved that the stale SEC fixture could
reach the real SEC fallback: it returned current AAPL data instead of the
fixture's `roe=0.33`. That unexpected read-only provider request is rejected
evidence and does not authorize another request. Before any resumed runtime
suite, the already-authorized module fixture must return the cached value
directly. The five new nodes and 444-node owner suite then run under the
packet socket guard. The `1,885` inventory-focused projection runs every
backend node except
`tests/test_data_scheduler.py::test_pg_reachable_probe_is_bounded` under the
same guard; that one existing bounded loopback-refusal node runs separately
and is recombined only by exact node-ID accounting. Any other socket attempt
is a new stop.

The sandboxed FastAPI/AnyIO execution of
`test_positive_annual_sec_cache_is_the_shared_projection_authority` stalled
after dependency resolution on both unchanged merged-master and Task 1 bytes,
while the Task 1 node passed outside the sandbox. The stalled transcript is
rejected environment evidence. Native execution is admitted for that owner
only with the socket guard active; it is not a product deadlock waiver.

The unchanged identities and 444/1,885 runtime instructions in this section
are dated first-stop authority only; Section 0.7c supersedes them for resumed
execution without changing the facts recorded here.

### 0.7c Task 1 intermediate-runtime and fixture-ceiling stop amendment

After Section 0.7b was applied, all five new contracts passed and the exact
Task 1 owner set finished `443 passed / 1 skipped`. The next guarded backend
partition of the literal 1,885-node inventory-focused collection then finished
`1,639 passed / 19 skipped / 45 failed / 11 errors` across its 1,714 nodes;
the one reviewed loopback node was not part of that command. The shell wrapper
used `tee` without `pipefail`, so its shell status is rejected. The pytest
summary and complete transcript are retained as failure evidence only.

The result exposed two distinct plan defects. First, the Task 1 runtime gate
still required all 101 nodes from the six whole-file owners in Section 0.4,
even though Task 1 has already removed helpers those obsolete contracts call
and Tasks 2-3 delete the files atomically. Adding temporary compatibility code
or editing tests that are about to retire would contradict the no-tail design.
The 1,885-node stream remains the Task 1 **collection identity**, but its
runtime GREEN set is the exact set difference from all 101 whole-file nodes:

```text
Task 1 runtime survivors           1,784  5bc41848aec5327b042c25248f1d6da46cb28c5e8a21faaf7e681d11bc1db0c5
Task 1 backend survivors           1,614  a8be4827bb1f4234f96e0b7ad2696c55abc867e0f667b035479221dd8a334dec
Task 1 frontend survivors            170  0111c3e448596d4387d84173eb14c1900a7ef77e56294bd69d2ee183c8f90c21
Task 2 runtime survivors           1,781  19443b6f2665d5f1ec677de6430687e8f5a41d39bfe54dcbaba9d748fb46b2d5
Task 2 backend survivors           1,611  a8122f8de84f6b65834e7515db660fad770f5b017ca64d8a76c5470280684642
Task 2 frontend survivors            170  0111c3e448596d4387d84173eb14c1900a7ef77e56294bd69d2ee183c8f90c21
```

Task 2's survivor set analogously subtracts the 71 whole-file nodes that Task
3 has not yet deleted. The full 1,885 and 1,852 streams remain mandatory
collect-only identities; no whole-file node may be copied, renamed, or made a
runtime admission substitute. Task 3 deletes the remaining files and restores
identity between collection and runtime at 1,781 nodes.

Second, the surviving failures found exact gaps in the edit ceiling. This
amendment authorizes only these supplements:

1. `tests/test_api.py::_HermeticMarketBackend` receives the same pure
   `query_news_search` contract specified for the helper in Section 0.7b.
2. `tests/test_freshness.py::TestCheckDataFreshness::test_no_backend_attr` may
   replace its obsolete message assertion with the current typed-unavailable
   local-authority result; its node ID and missing-capability setup stay fixed.
3. `tests/test_sa_digest.py::_stub_fetch_dicts` may patch the current
   `_fetch_dicts_local` choke point instead of the removed helper. The already
   authorized `_fake_backend` exposes only a scratch `_sa_db` path. The exact
   five direct-patch bodies below may make the same choke-point/signature
   replacement without changing their behavior assertions:

   ```text
   tests/test_sa_digest.py::TestCommentsSqlShape::test_comments_sql_uses_layered_cte_with_per_article_cap
   tests/test_sa_digest.py::TestParamClamping::test_max_clamps
   tests/test_sa_digest.py::TestParamClamping::test_min_comment_score_clamped
   tests/test_sa_digest.py::TestParamClamping::test_window_days_clamped
   tests/test_sa_digest.py::TestTickerUppercase::test_lowercase_input_passes_uppercase_to_sql
   ```

The FRED module fixture, EIR-006 module census, SA-comment backfill body,
web-tools body, SA-routing module, and remaining SA-digest helper/body edits
were already inside Section 0.7a. They receive no wider authority. In
particular, product method-presence inference, a compatibility fallback, a
provider request, or a second helper method is still a stop.

Six surviving tests also state contracts that the reviewed architecture
explicitly removed. Their exact truthful replacements are the six added rows
in Section 0.6. This changes no count but re-pins the replacement stream to
`46 / f7ac08c4000baddaa9969d7895054ade3024ea224536bdb68286737891cf36ad`.
The Task 1 owner set is therefore `472` nodes across `26` final paths at
`cb454b785b7fdfc645a4c5f3765cb8a70dc280ad5f63a76c4dcf0fbd8d246578`.
Editing a seventh existing node ID, a second body in the freshness test, or a
second out-of-projection helper is a new stop-and-amend event.

### 0.7d Task 3 live-FRED alias-seam stop amendment

Task 3 removed the seven exact foundation paths, then reproduced backend
collection `4,278 / 80037a1b...`, backend runtime `1,609 passed / 2 skipped`,
frontend runtime `170 passed`, the protected aggregate, the declared
dependency closure, and the packet-local foundation gate. An independent AST
projection then found one executable alias that the Task 3 retained-owner
list had assigned too late:

```text
tests/live/smoke_fred.py:123  real_store_factory = ing.MacroCalendarStore
```

The same reviewed inventory surface already classifies this path
`retain_operator_remove_pg_branch`, places it in `no_tail_modify.paths`, and
enumerates the three stale attribute uses at lines 123, 124, and 144. The
current ingestion module constructs `MacroCalendarLocalStore()` directly and
does not expose `MacroCalendarStore`; therefore the tracked live smoke is not
merely historical prose. Its dry-run injection seam is currently broken.

Task 3's retained mixed-owner list is extended by exactly
`tests/live/smoke_fred.py`. Its only admitted Task 3 product hunk is this
three-line current-owner rewrite:

```python
real_store_factory = ing.MacroCalendarLocalStore
ing.MacroCalendarLocalStore = lambda: store
# ... existing dry-run body remains byte-identical ...
ing.MacroCalendarLocalStore = real_store_factory
```

The lambda takes no argument because the current ingestion call site invokes
`MacroCalendarLocalStore()` with no DAL parameter. No provider request,
prose cleanup, output change, second product hunk, compatibility alias, or
alternate factory is authorized here. Task 4 still owns the remaining
tracked-vocabulary rewrite in this file.

The Task 3 AST projection is closed over direct driver/foundation imports,
retired-symbol imports, class definitions, inheritance, construction calls,
`isinstance`/`issubclass` gates, executable aliases, and type annotations. An
arbitrary attribute reference is not itself a Task 3 failure because Task 4
still owns reviewed current-authority rewrites, but assignment of a retired
attribute to an alias is. The pre-amendment overbroad projection and the
alias-specific RED are both retained; after the exact rewrite the alias gate
must be GREEN.

This body-only operator-script correction changes no pytest/Vitest node ID,
staged collection, route identity, runtime-survivor stream, protected byte,
or final native arithmetic. Resume order is: apply the exact three-line
rewrite, rerun the AST gate and current FRED ingestion owner tests under the
socket guard, rerun Task 3's already-pinned gates, then complete the Task 3
commit pair. Any fourth line in the product hunk or any identity drift is a
new stop.

### 0.7e Task 4 presenter fallback Class A amendment

Task 4 reached exact backend collection `4,278 / 80037a1b...`, frontend
collection `1,177 / 101 / c570a551...`, frontend owners `54/54`, and zero
product residue. The first sequential frontend full run then produced exactly
one failure: the visible-literal scanner traced the presenter return value
`normalized` to `marketDataDisplay.ts`. Direct scanner replay found two
inventory-owned presenter-boundary defects in the Task 4 rewrite: the raw
fallback in `newsWriteRouteLabel` and a machine-value comparison placed inside
the return expression in `newsReadSurfaceLabel`:

```typescript
default:
  return status.write_route;

return status.write_route === "normalized" ? translatedA : translatedB;
```

`apps/arkscope-web/src/marketDataDisplay.ts` is an exact member of
`no_tail_modify.paths`; the inventory surface enumerates the write-route
fallback in the same current-authority rewrite. Returning a raw backend value
as UI text violates the existing localized presenter boundary. The only
admitted correction keeps the existing default branch, passes its closed-union
value to `unreachableCoverageValue`, and returns the existing localized
`newsStorage.routing.write.blocked` label. It also moves the existing
`write_route === "normalized"` predicate from the return expression into an
equivalent preceding `if`; both translated returns remain unchanged. These two
hunks add no translation key, method, semantic branch, parameter, request, or
capability.

This is Class A under Section 1.1: the path and coordinate are reviewed,
collection/focused/survivor/route/protected identities do not change, the diff
only closes an already-owned raw fallback, and no other stop or external
contact occurred. The complete `1F/1176P` transcript remains rejected RED
evidence. Apply the exact fallback correction, rerun the two-file owner suite,
the visible-literal scanner, and the sequential full frontend suite, then
continue Task 4. A translation addition, third product hunk, changed return
value, test-ID change, or identity drift is a new stop.

### 0.7f Task 4 retained-owner and closed-bundle Class B amendment

After Section 0.7e reached frontend `1,177/1,177`, Task 4 ran the exact
backend half of the final inventory-focused projection. The run is rejected
RED evidence at
`/tmp/arkscope-pg-no-tail-task4-1499d827/inventory-focused-backend.txt`:

```text
1,605 passed / 2 skipped / 4 failed
```

All four failures are deterministic retained-owner defects caused by Task 4's
reviewed deletions, not environment failures:

1. `tests/test_legacy_iv_retirement_boundaries.py` opens deleted
   `sql/001_init_schema.sql`;
2. `tests/test_legacy_score_retirement.py` opens deleted
   `docs/design/AGENT_EVOLUTION_TRACKER.md`;
3. `tests/test_sa_tools.py` opens deleted SQL migrations `007`, `014`, and
   `015`; and
4. `tests/test_sqlite_backend.py` asserts the removed inherited `_connect`
   seam even though the reviewed implementation now uses direct composition.

Three names therefore become false if preserved. This Class B amendment adds
exactly these one-for-one truthful replacements to the 46 historical pairs:

```text
tests/test_legacy_iv_retirement_boundaries.py::test_sql_init_and_current_backends_have_no_legacy_iv_schema	tests/test_legacy_iv_retirement_boundaries.py::test_current_backends_have_no_legacy_iv_schema
tests/test_sa_tools.py::TestSAAlphaPicksStorageContract::test_sql_schema_preserves_dual_tab_membership_and_closed_date	tests/test_sa_tools.py::TestSAAlphaPicksStorageContract::test_local_schema_preserves_dual_tab_membership_and_closed_date
tests/test_sqlite_backend.py::test_inherited_vs_overridden_methods	tests/test_sqlite_backend.py::test_local_backend_exposes_required_methods
```

The first replacement inspects only current backend owners. The second reads
the current local `src.sa_capture_store._SCHEMA` authority and preserves the
closed-date plus current/closed partial-unique-index assertions. The third
asserts the reviewed public local methods and direct-composition shape without
resurrecting `_connect`, inheritance, nominal routing, or a compatibility
surface. The existing legacy-score node keeps its ID and behavior assertions;
its only admitted body change removes the deleted tracker from the authority
tuple. A fourth ID change, weaker behavior assertion, new method/branch/
parameter, or second body change in any of these nodes is a new stop.

This re-pins only Task 4 and later authority. Task 1 and Task 3 streams remain
immutable dated facts. The final exact identities are:

```text
backend replacements, final         49  (46 historical + 3 above)
backend collection, Task 4-final  4,278  ecafdab7a1cee8d6f64dd6763f017d2ef15dd414b80065950f949d8b471a09ce
inventory-focused final           1,781  6220cb4e985dd3e2bc58b6fa369fe6a6fe7a456528089d9ce6c84134a7335a30
Task 1 owner projection, final      472  483b65663a382e7ab03b73f3774acafbdf38e6fb21cbc4544fbc88733dcca6a1
```

The native target remains `4,266 passed / 12 skipped / 0 failed` because the
three changes are one-for-one passing replacements.

The same stop exposed a path-ledger closure defect. The inventory scheduled
only `consumer-census.tsv` for deletion from the closed EIR-006 evidence
bundle, while that bundle's `README.md`, `SHA256SUMS`, and
`census-result.json` all name that payload. Partial deletion would leave a
tracked evidence package whose manifest cannot pass. The line was already
closed on 2026-08-08, has no current runtime owner, and the user ruled that
unrelated retired support leaves through `git rm` with Git history as
recovery. Task 4 therefore deletes this exact complete 23-path bundle; its
UTF-8 byte-sorted, one-final-newline path stream is
`8171c42c61de9b3be2d235bd55ba23d48da8bf1e7538c11c2267e186dd792838`:

```text
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/README.md
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/SHA256SUMS
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/authority-input.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/behavior-propagation.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/cache-classification.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/canonical-db-differences.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/census-result.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/db-result.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/legacy-fundamentals-rows.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/legacy-price-files.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/legacy-sync-rows.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/old-cache-rows.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/operational-state.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/packet-summary.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/price-result.json
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/raw-db-differences.tsv
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py
docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/ticker-aliases.tsv
```

Of these, one path was already in `no_tail_delete.paths`, five were in
`protected.paths`, and 17 were previously unclassified. The net semantic
delete supplement is therefore 22, and the five protected members move to
the delete authority rather than being edited.

An exact deleted-reference census also found 17 current application,
configuration, and current-authority documentation paths outside all four
inventory sets. They require only removal or positive-local rewriting of
backlinks/comments to files Task 4 deletes. Their UTF-8 byte-sorted,
one-final-newline path stream is
`814ef7466c73e6f7f2e51bd8220fcc4404ed27d4593da1dedf98179d1a36caa6`:

```text
PROJECT_STRUCTURE.md
config/macro_calendar_series.yaml
data_sources/fred_client.py
docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
docs/design/ARKSCOPE_PROVIDER_CATALOG.md
docs/design/COVERAGE_V2_GROUND_TRUTH_INVENTORY.md
docs/design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md
docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md
docs/design/SA_COMMENT_INTELLIGENCE_PLAN.md
docs/design/SA_EXTENSION_ROADMAP.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
docs/design/SKILL_PLUGINS_RESEARCH.md
src/agents/config.py
src/api/routes/jobs.py
src/macro_calendar/finnhub_ingestion.py
src/service/jobs.py
src/tools/sec_tools.py
```

These paths add no capability and may receive no behavior change. Product
edits are comment/docstring/link-only; configuration values are unchanged;
current documents replace stale links with current owners or remove the link
when no current owner exists. A path outside this literal list and the prior
174 modify paths, an 18th supplement, or a behavior hunk is a new Class B
stop.

At the Section 0.7f amendment generation, the predicted semantic path
authority was:

```text
delete     183  (161 inventory + 22 net bundle supplement)
modify     191  (174 inventory + 17 current-authority supplement)
add          1
protected   17
```

Those 17 protected paths were the original set minus the five retired
bundle producers. Their UTF-8 byte-sorted path stream is
`52944cdb212217833d0124f3b4e109b1314fc50c729816b430b69474b91c4993`;
the Section 0.10 `sha256sum`-row aggregate is
`0bfdd977f0d060075a21a9530e3b31be72ad0a22781cffd3ebd17e05759eb9fd`:

```text
apps/arkscope-web/package.json
data_sources/financial_metrics_calculator.py
data_sources/sec_earnings_releases.py
data_sources/sec_insider_trades.py
extensions/sa_alpha_picks/build_firefox.py
package.json
src/api/__main__.py
src/audit/ibkr_news_catchup_audit.py
src/collectors/finnhub_news.py
src/collectors/polygon_news.py
src/news_normalized/ibkr_cli.py
src/options_math/option_pricing.py
src/prices_runtime.py
tests/live/sdk_driver_smoke.py
tests/live/sdk_route_smoke.py
tests/test_ibkr_scanner.py
tests/test_option_pricing.py
```

With rename detection disabled, Section 0.7f therefore predicted
`185 D / 189 M / 3 A`: 183 semantic deletes plus two rename-source deletes,
191 semantic modify paths minus those two sources, and the capability plus two
rename destinations. Task 4 deletes 171 paths after the 12 Task 2-3 deletions.

Before Section 0.7f could resume, focused review had to independently rebuild all three
replacement identities, both supplement path streams, the 23-path bundle
split (`1 delete / 5 protected / 17 unclassified`), the final protected
aggregate, and the final D/M/A algebra. Resume then applies the four bounded
test-owner corrections, deletes the complete bundle, rewrites the 17 exact
supplement paths plus already-owned current references, and runs a
packet-local retained-path backlink scanner over product/config/current
authority. That scanner must report zero reference to any final deleted path;
it does not authorize a general historical-doc sweep. A fourth changed node
ID, 24th bundle path, 18th supplement path, changed final identity, provider/
network/private/production contact, or incomplete manifest deletion is a new
hard stop.

### 0.7g Task 4 collection-only path-account Class B amendment

After Section 0.7f focused review returned GREEN, Task 4 completed the exact
deletions, rewrites, backlink cleanup, and tracked-tree zero-residue scan. The
semantic path preflight then produced `185 D / 180 M / 3 A`, not Section
0.7f's predicted `185 D / 189 M / 3 A`. No product edit is authorized merely
to make a count match.

The difference is exactly these nine paths. Each was classified
`rewrite_current_authority` solely because the broad inventory
`test_collection` family included its current local tests. Each surface has
no line reference, no measured method, no text/path/import candidate, and no
Task 1-4 behavior or fixture change. All nine files are byte-identical to
`d4677c3d` and the zero-residue scanner reports no row for them:

```text
tests/test_agents.py
tests/test_analyst_tools.py
tests/test_chatgpt_oauth_driver.py
tests/test_compressor_layer5.py
tests/test_macro_scheduler_integration.py
tests/test_peer_comparison.py
tests/test_sa_extension_diagnostics.py
tests/test_sa_market_news_recovery.py
tests/test_sec_tools.py
```

Their UTF-8 byte-sorted, one-final-newline path stream is
`ea149566cee184fcd2251459afba93a8332c4b7efd6f9ab90b9353ded3cf0dd4`.
Task 4 protects those bytes instead of manufacturing no-op or unrelated test
changes. The immutable inventory files remain dated inputs; this amendment
changes only their final implementation disposition.

The final semantic authority is therefore:

```text
delete     183
modify     182  (174 inventory - 9 collection-only + 17 backlink supplement)
add          1
protected   26  (17 after bundle retirement + 9 collection-only)
```

The 182-row final modify stream is
`cde0cb8efe180dfe05a1c246a23563716e133b2a1459f294d00d5d0431902f48`.
The 26-row final protected path stream is
`d36eecf544a4ad184729c9637e7202a49cc1db3f93934f98ad173efa0090e317`;
its path-ordered `sha256sum`-row aggregate is
`d567da56ede0dd49a9e9865be308fabcb1cd0bc7ca059bb21864c49c01dae0c3`.
With the two ownership-preserving rename sources counted as deletes, the
final product-path `--no-renames` algebra is exactly `185 D / 180 M / 3 A`.
Temporary governance additions/modifications are excluded from that semantic
product ledger and retire in Task 5 as already planned.

This changes a reviewed path ledger and is Class B. Product/test/dependency
bytes remain frozen while focused review independently verifies that the nine
surfaces have only `test_collection` candidates, are byte-identical to base,
and reproduce all three new hashes. A tenth reclassification, any test-body
edit in these files, identity drift, or zero-residue row is a new stop.

### 0.7h Task 5 loopback-owner admission Class B amendment

The first Task 5 canonical runtime installed the packet socket guard across
all 4,278 nodes. It completed the whole suite at `4,265 passed / 12 skipped /
1 failed`; the sole nonpassing node was
`tests/test_chatgpt_oauth_callback_server.py::test_captures_code_and_state`,
and the guard recorded ten calls across `socket.connect` and
`socket.create_connection`. This run is rejected admission evidence.

The failure is not a product network regression. The existing callback test
module says it is the one contract that binds a real ephemeral loopback port,
uses only `127.0.0.1`, and never reaches an external network. An isolated
control without the blanket guard passed all six unchanged nodes. Their exact
stream is `6 /
b6c3c71819ca38a61ea6f969316b847836fa6f4a9e15cdb0ac73d47bc313a58b`;
the exact complement is `4,272 /
805ed70c3a9861bd84cb6969ee93901d08f95223c340f02009de406eb42a536d`.
The test and product owner bytes remain respectively
`9004abe4cd6c36edb092977eca7b2b0de73900ee00fc3877a6424448a23175ed`
and
`7c5738d5306d62f6f311fb000f74bb63a13b0495a6d31e0f57ff49988cdcd459`.

Resume uses an owner split, not a broad localhost allowlist:

1. run the exact six-node callback stream without the process-wide guard and
   require `6 passed / 0 failed`; any seventh node or owner-byte drift stops;
2. run the exact 4,272-node complement under the zero-exception socket guard
   and require `4,260 passed / 12 skipped / 0 failed`, zero recorded socket
   attempts, and exact reporter collection/seen sets;
3. mechanically prove the two streams are disjoint and their union is the
   exact 4,278-node final collection;
4. run the full canonical suite twice from independent exact-tip runtime
   roots without the blanket guard, still with no provider credentials,
   `.env`, production path, or remote configuration, and require deterministic
   reporter JSON at `4,266 passed / 12 skipped / 0 failed`; and
5. keep the socket guard unchanged on sanitized app lifespan, scheduler,
   route, focused runtime, and complement gates.

No product, test, dependency, collection identity, skip identity, or staged
hash changes. This is nevertheless Class B because the reviewed admission
protocol had more than one reasonable correction shape and its blanket
network-exception wording must change. A destination-based loopback bypass,
general localhost allowance, test-body edit, owner-ID edit, or guard weakening
outside the exact complement is a new stop.

The amendment packet is
`/tmp/arkscope-pg-no-tail-task5-d4677c3d/amendment-0.7h`; its 12 payload rows
pass `sha256sum -c`, and its manifest is
`ddb8a88cba2a886a7d7cfa7546709d792fb270e98ba2a6e064ba0d01a0bf4793`.

### 0.8 Dynamic-route target

Final route identity is the canonical 175-row inventory route stream with
exactly these rows removed:

```text
GET	/app-records/migration/preview	src.api.routes.app_records	migration_preview
POST	/app-records/migration/apply	src.api.routes.app_records	migration_apply
```

The final stream is 173 rows at
`e0d8bf3c01e57bfb5403c68c16aac376be225db56eb638ca44d7eb218acfb37e`.
It is generated from the real `app.routes` after real lifespan startup, never
from a route allowlist. Any other added or removed route is a stop.

### 0.9 Temporary governance and final self-retirement

The final tracked tree removes these entire temporary authority surfaces:

```text
docs/design/pg_runtime_inventory/
docs/design/PG_RUNTIME_CONSUMER_INVENTORY.md
docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md
docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md
docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md
docs/superpowers/plans/2026-08-16-postgresql-runtime-no-tail.md
docs/superpowers/evidence/2026-08-16-postgresql-runtime-no-tail.md
```

It also removes only the obsolete program entries from
`docs/design/PROJECT_PRIORITY_MAP.md` and leaves a neutral newest-first handoff
stating that the legacy-agent CLI census is next. That retained entry must not
name or narrate the removed storage technology. Deleting unrelated map history
or retaining this plan/evidence as a tracked archive is a stop.

Before each product/evidence commit, append packet-only
`last-containing.tsv` rows of
`tracked_path<TAB>pre_commit_tip<TAB>retirement_commit`. At final admission,
every removed or rewritten surface must have an exact last-containing commit,
and `git show <pre_commit_tip>:<tracked_path>` must recover the old blob without
checking it out. The packet is the review record; no tracked recovery catalog
survives.

### 0.10 Protected boundary

The 22 literal inventory paths are the immutable Task 0 through Task 3
grounding boundary. Sort the paths themselves with `LC_ALL=C`, run GNU
`sha256sum` from repository root in that order, and SHA-256 the complete
22-row standard-output stream including its final newline. At the grounding
tip the aggregate is
`7e9fa65847e86c9296c541b546ce472d1a7d467b6392a089c116dc02563e5cb6`.
Task 0 records individual hashes and the aggregate.

Section 0.7f moves exactly five members into the complete EIR-006 bundle
deletion. From Task 4 onward, the exact 17 surviving paths and aggregate in
Section 0.7f are the protected boundary. The other 17 blobs remain
byte-identical to grounding; editing a protected blob or moving a sixth path
is a stop rather than permission to widen scope.

### 0.11 Staged collection identities

The literal ledgers above mechanically determine these counts. Full SHA-256
values are filled only from the same literal extraction recipe and are
review-admission identities, not comments:

| Stage | Backend | Frontend | Inventory-focused union |
|---|---|---|---|
| Base | `4,394` / `b0285ee3...` | `1,177` / 101 / `90f56093...` | `1,897` / `57c1b514...` |
| Task 1 | `4,382` / `ce7c045fab7b4fde2598660e98c5e67964ac0c8871b8d8aca7d3d150c3e90cc8` | unchanged | `1,885` / `19ff8f6027ed399b0701fb2840cb3e0658cee860f5de8334f68a6522f826bcca` |
| Task 2 | `4,349` / `04e93190119d1134903182a61f6ea495d1445ebd5784878196bca2baa49bebc6` | unchanged | `1,852` / `1c7f9a06d9518b48355ac952f4e09352862c6628dfaf0c5ff35cd7ae53ad73e0` |
| Task 3 | `4,278` / `80037a1bd0d82270eeef633b0b2640c0a7fd2680b51de906811b85d87755f5e3` | unchanged | `1,781` / `19443b6f2665d5f1ec677de6430687e8f5a41d39bfe54dcbaba9d748fb46b2d5` |
| Task 4-final | `4,278` / `ecafdab7a1cee8d6f64dd6763f017d2ef15dd414b80065950f949d8b471a09ce` | `1,177` / 101 / `c570a551b64ed95155c02f83499e78eb3409f2cba66ea9d46862dffad0ea239b` | `1,781` / `6220cb4e985dd3e2bc58b6fa369fe6a6fe7a456528089d9ce6c84134a7335a30` |

The final native target is `4,266 passed / 12 skipped / 0 failed`: canonical
base `4,382P/12S`, minus 101 whole-file passing nodes, minus 22 passing
historical nodes, minus 49 passing old IDs plus their 49 passing replacements,
plus seven new passing contracts. The old `.env` symlink is forbidden.

Task 0 independently reproduced the immutable rows through Task 3 from
Sections 0.4-0.7c and the three canonical base streams. Section 0.7f
mechanically supersedes only Task 4-final and later identities. Focused review
must reconstruct that delta from the three literal replacement rows before
Task 4 resumes. A count-only match is insufficient.

---

## 1. Execution protocol

### 1.1 Review and commit discipline

The default is a hard independent review stop after every task. A later user
batch ruling may replace selected waits, but it cannot relax any stop
condition, commit pair, RED artifact, staged identity, or final review gate.
No task is authorized by the existence of this draft; independent plan review
must first return GREEN.

The user has superseded the blanket per-amendment wait with this mechanically
checkable A/B classification. An amendment is **Class A** only when all four
conditions hold:

1. every corrected path and coordinate already exists in the reviewed
   inventory;
2. collection, focused, survivor, route, protected, and other pinned
   identities remain byte-identical;
3. the diff adds no method, branch, parameter, product capability, or new
   authority and only replaces a dead reference with its reviewed current
   owner or makes a fixture follow an already-pinned protocol; and
4. no other hard stop in Section 2 is triggered.

A Class A amendment is still numbered, committed, included in its evidence
packet, and replayed during Task 6 review, but implementation resumes without
an intervening focused-review wait. A mistaken Class A classification causes
that segment to be reverted and reviewed at Task 6.

An amendment is **Class B** and stops for focused review when any identity,
pair, ledger, or staged hash changes; more than one reasonable correction
shape exists; a surface absent from inventory is needed; or any unexpected
provider, network, production, private, or remote contact occurs. External
contact is always Class B even when its code fix is mechanical. Section 0.7d
is the accepted reference Class A case. Section 0.7c is Class B; Section 0.7b
would be Class A on its fixture shape alone but remained Class B because its
rejected run contacted the provider.

Task 0 has one docs/evidence commit. Tasks 1-4 each have exactly one product
commit followed by one evidence/status commit. Task 5 has one evidence commit
followed by the governance-retirement commit. Commits are linear and are never
squashed. Task 6 is the combined implementation-review stop. Task 7 is
fast-forward merge only after Task 6 GREEN. Push is never authorized here.

All packet roots use `/tmp/arkscope-pg-no-tail-task<N>-<plan-base>` and contain
a complete `SHA256SUMS`. Generated scripts, RED/GREEN transcripts, node
streams, manifests, mutation patches, owner hashes, rejected attempts, and
cleanup receipts are packet artifacts. Evidence cites their full hashes and
does not copy secret values or private paths.

### Task 0: Re-ground the exact inventory handoff

**Tracked changes**

- Create:
  `docs/superpowers/evidence/2026-08-16-postgresql-runtime-no-tail.md`
- Modify status only:
  `docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md`
- Modify newest-first decision log only:
  `docs/design/PROJECT_PRIORITY_MAP.md`
- Product/test/dependency bytes: none.

**Step 1: create the isolated exact-tip worktree and packet**

Start from the independently reviewed plan commit, prove that it descends
linearly from `d4677c3d5b8579f95621a62ed056620a083ad1c8`, and require clean main and
implementation trees. Copy the two pinned helper bytes into the packet and
verify their full hashes.

Before every Python or Node command, use one controlling shell:

```bash
export PACKET=/tmp/arkscope-pg-no-tail-task0-d4677c3d
export SCRATCH_ROOT="$PACKET/runtime"
mkdir -p "$SCRATCH_ROOT/data" "$SCRATCH_ROOT/locks" "$SCRATCH_ROOT/home" data
unset DATABASE_URL
export HOME="$SCRATCH_ROOT/home"
export ARKSCOPE_PROFILE_DB="$SCRATCH_ROOT/profile_state.db"
export ARKSCOPE_MARKET_DB="$SCRATCH_ROOT/market_data.db"
export ARKSCOPE_SA_DB="$SCRATCH_ROOT/sa_capture.db"
export ARKSCOPE_MACRO_CALENDAR_DB="$SCRATCH_ROOT/macro_calendar.db"
export ARKSCOPE_CONSENSUS_DB="$SCRATCH_ROOT/consensus.db"
export ARKSCOPE_TOKEN_STORE_PATH="$SCRATCH_ROOT/token_store.json"
export ARKSCOPE_LOCK_DIR="$SCRATCH_ROOT/locks"
```

The worktree's `data/` is an empty real directory. Link only root
`node_modules` to the main tree's root `node_modules`. Do not link app-local
`node_modules`, main `data/`, private `config/.env`, or any runtime asset.
Record that `config/.env` was neither present nor linked; do not inspect its
value in this line.

Install a packet-local socket guard before runtime tests. It rejects
`socket.connect`, `socket.connect_ex`, and `socket.create_connection`. Task 0
has no loopback exception because the obsolete bounded probe is not a current
contract of this implementation line.

**Step 2: verify every inventory authority**

Run the tracked `MANIFEST.sha256` recipe from repository root and require a
byte-identical manifest. Verify the exact four path-set counts/hashes in
Section 0.1, the five base identities in Section 0.2, the 36-row method set in
Section 0.3, all 101 whole-file node IDs, the 22 historical IDs, all 46
replacement pairs, all seven new IDs, all 18 frontend pairs, all five Section
0.7a edit-boundary streams, every exact Section 0.7c supplement, and both
rename source blobs.
Also require zero product/test/dependency path diff from exact candidate source
`4c6b8d44ce2e768e95b822b11f618cc40f4bb9f0` to the plan base before trusting
candidate line coordinates.

For every old ID, require exactly one base occurrence. For every new ID and
rename destination, require absence. Verify the six deleted-file per-file
counts and the 17/5, 34/12, 5/2 task partitions. Verify the four path sets are
pairwise disjoint and that the only `add` member is the capability module.

**Step 3: freshly recollect both canonical bases**

Backend collect-only, with zero test bodies:

```bash
PYTHONPATH="$PACKET/tools:$PWD" \
PRICE_TRUTH_TIER_REPORT="$PACKET/backend-base.json" \
python -m pytest --collect-only -q -p arkscope_eir002_reporter
jq -r '.collected_node_ids[]' "$PACKET/backend-base.json" \
  | LC_ALL=C sort -u > "$PACKET/backend_base.nodes"
```

Require 4,394 rows and the exact Section 0.2 hash; reporter fields must say
zero seen and zero nonpassing.

Frontend list, using only the explicit local binary:

```bash
cd apps/arkscope-web
../../node_modules/.bin/vitest --version
../../node_modules/.bin/vitest list --json="$PACKET/frontend-base.json"
python "$PACKET/tools/eir006_vitest_list_normalizer.py" \
  --input "$PACKET/frontend-base.json" --web-root "$PWD" \
  --output "$PACKET/frontend_base.nodes"
```

Require `vitest/4.1.8`, 1,177 rows, 101 distinct paths, and the exact hash.
Any package-manager request or tracked-file rewrite rejects the entire run.

**Step 4: rebuild every staged stream from this plan's literal rows**

Write a packet-local parser that extracts Sections 0.4-0.7 from the committed
plan itself. It must not contain a hand-copied node list. Apply each task delta
as set algebra to the freshly collected bases and inventory-focused union,
then require exact byte equality to every Section 0.11 identity. Independently
implement Section 0.7a's AST/source projection and require all five streams and
both aggregates to match, then apply Section 0.7c's exact supplements. Include
negative self-tests for a missing row,
duplicate row, wrong task assignment, unauthorized eighth addition, a third
rename, an unlisted test-body edit, and a shared fixture outside its projected
scope.

Independently derive and pin the focused projections:

```text
Task 1 owners at Task 1 tip      472  cb454b785b7fdfc645a4c5f3765cb8a70dc280ad5f63a76c4dcf0fbd8d246578
Task 1 owners at final tip       472  483b65663a382e7ab03b73f3774acafbdf38e6fb21cbc4544fbc88733dcca6a1
Task 2 owners, 4 final paths     147  7b719fcb09769d6d09b6bb260389092416a2af7c6469f517565aa15229cae5d0
Task 4 frontend, 2 final paths    54  83d681a7893416f1340d9dcb7eb1064ae664e8fbd0bf98d76b642105ee5590a3
```

The Task 1 path set is the distinct paths owning its 17 retirements, 34
Task-1 replacement pairs, and five additions. Its first hash is the immutable
Task 1 runtime identity; Section 0.7f's three later replacements produce the
second final-tip hash without changing count or paths. The Task 2 final paths are
`tests/test_api.py`, `tests/test_data_scheduler.py`,
`tests/test_news_normalized_routing.py`, and
`tests/test_news_local_authority.py`. The Task 4 paths are
`src/SettingsLocalStorage.test.ts` and `src/marketDataDisplay.test.ts`.

**Step 5: protect bytes and record boundaries**

Rebuild the 22-row grounding protected aggregate using Section 0.10's exact
command shape. Record individual rows and require the aggregate. Verify the three
git-crypt blobs at the implementation tip equal unlocked main by Git blob ID;
do not treat locked ciphertext grep as absence evidence and do not copy
plaintext into the packet.

Record no Python/product/test/dependency delta from the plan base, no runtime
asset open, no process, no network attempt, no private link, and clean trees.

**Step 6: commit Task 0 evidence and stop**

The decision-log entry states: inventory is merged and closed; this plan is
under independent review/then implementation; per-task review is the default;
legacy-agent CLI census remains the binding next analysis line; remote table,
private dump, and private `.env` actions remain excluded.

Commit only the three docs paths:

```bash
git commit -m "docs: ground local runtime no-tail implementation"
```

Stop for independent Task 0 review unless a later user batch ruling is already
recorded newest-first in the map and Task 0 evidence.

### Task 1: Cut retained consumers to measured local capabilities

**Creates**

- `src/tools/backends/local_capabilities.py`

**Primary product owners**

```text
data_sources/financial_datasets_client.py
src/agents/anthropic_agent/agent.py
src/agents/cli.py
src/agents/openai_agent/agent.py
src/audit/sa_article_reconciliation.py
src/fundamentals/cache.py
src/macro_calendar/fred_ingestion.py
src/sa/comment_signal_backfill.py
src/service/job_runs_store.py
src/service/provider_health.py
src/tools/analysis_tools.py
src/tools/backends/__init__.py
src/tools/backends/local_market_backend.py
src/tools/backends/provenance.py
src/tools/backends/sa_capture_backend.py
src/tools/backends/sqlite_backend.py
src/tools/data_access.py
src/tools/freshness.py
src/tools/price_tools.py
src/tools/sa_digest_tools.py
src/tools/sa_tools.py
```

The exact Task 1 collection owners are the 26 paths derived in Task 0. Retained
body/helper/module edits, including necessary updates in other test paths, are
limited by Sections 0.7a-0.7c. A path's inventory membership never grants a whole
test file for unrestricted editing; changing behavior outside the current
local contract is a stop.

**Step 1: establish RED without breaking collection**

Apply Task 1's 17 historical removals, 34 positive replacements, and five new
nodes. New tests import the absent protocol dynamically inside test bodies so
collection succeeds. Recollect first and require the Task 1 full/focused
identities from Sections 0.11 and Task 0.

Run the five new nodes against the old product. They must fail for these exact
missing contracts:

1. capability module/protocol absent;
2. default DAL still selects through old configuration;
3. explicit local capability still depends on nominal routing;
4. runtime backend graph still imports an unreviewed backend module; and
5. CLI save handling does not consume the injected local capability directly.

A syntax/import failure before the test body, a failure in an unrelated
existing node, or a fake product object that bypasses `DataAccessLayer` is
rejected RED evidence.

**Step 2: create the exact protocol and direct local composition**

Implement `LocalDataCapabilities` as a non-runtime Protocol with exactly the
36 Section 0.3 callables. Use current schema/signature types; do not expose a
connection, DSN, close/factory method, or domain method outside the list.

Refactor `LocalMarketDatabaseBackend` to `LocalMarketBackend` without base
class inheritance or DSN/SSL arguments. It owns only current market/news/
fundamental/financial-cache behavior. Delegate the retained SEC filing read to
the existing local/file implementation explicitly; do not inherit it from a
retiring class and do not modify `file_backend.py` (it is outside all four
inventory sets).

Refactor `SACaptureDatabaseBackend` to `SACaptureBackend`, inheriting only the
current local market composition. Move the two proven comment preparation
helpers into this existing module and update their existing test imports.
Every SA method in the 36-method protocol remains local and preserves its
reviewed shape.

Make `DataAccessLayer` default construction instantiate the local composition
directly. An explicit `backend=` value is treated as the supplied structural
capability; there is no inference from class identity, method presence,
configuration, or environment. Remove `_make_db_backend`, DSN parameters,
alternate-authority selection, nominal gates, and inherited fallback paths.

**Step 3: cut every measured retained consumer**

Update the exact inventory consumers, including agents, provider health,
freshness, financial cache, SA reconciliation/tools, and local data tools, to
call their measured current local owner directly. In particular:

- `get_job_runs_store` becomes an unconditional `JobRunsLocalStore` factory;
- FRED ingestion constructs/receives `MacroCalendarLocalStore`, never the
  still-present retiring twin;
- financial cache stays with the local market store;
- agent/CLI freshness/save paths use explicit structural capability injection;
  their only protocol method outside the direct DAL set is the measured
  `query_health_stats` row;
- `financial_datasets_client.py` and `sa_digest_tools.py` lose their direct
  driver branches and use their reviewed local owners; and
- no product module other than the not-yet-deleted foundation files can import
  or name the retiring backend class after this task.

The old foundation modules may remain on disk only because Task 3 owns their
deletion. A packet-local import/reachability projection must prove no current
product entrypoint reaches them.

**Step 4: prove Task 1 GREEN**

Run in order:

1. five new owner nodes;
2. the 472-node/26-path Task 1 focused suite;
3. the 1,784-node inventory-focused Task 1 runtime-survivor projection while
   retaining the full 1,885-node stream as collect-only identity;
4. backend collect-only `4,382 / ce7c045f...`;
5. socket-guarded import controls for app, agents, CLI, scheduler, native host,
   and all four local stores; and
6. protected 22-path hashes.

Apply Sections 0.7b-0.7c's socket split to steps 1-3. The 472-node owner result
must be exactly `471 passed / 1 skipped`. The runtime-survivor backend and
frontend partitions must recombine to the literal `1,784` node set, while the
collect-only stream remains exactly `1,885`, without a retry, omission, or
unguarded provider-capable run.

No native full-suite claim is made at this intermediate stage. Store complete
transcripts and exact owner pre/post hashes.

**Step 5: commit product and evidence**

```bash
git commit -m "refactor: cut runtime consumers to local capabilities"
git commit -m "docs: record local capability cutover evidence"
```

The evidence commit updates only the temporary plan/evidence/map status. Stop
for review unless a recorded batch ruling applies.

### Task 2: Retire executable routes, alternate news routing, and network probe

**Deletes, exact five-path subset of `no_tail_delete.paths`**

```text
src/api/routes/app_records.py
src/app_records_migrate.py
src/smoke/pg_unreachable_e2e.py
tests/test_app_records_migrate.py
tests/test_pg_unreachable_e2e.py
```

**Primary retained owners**

```text
src/api/app.py
src/news_normalized/routing.py
src/news_providers.py
src/news_sync_status.py
src/service/data_scheduler.py
src/service/provider_health.py
tests/test_api.py
tests/test_data_scheduler.py
tests/test_news_normalized_routing.py
tests/test_news_local_authority.py
```

Every path is already in `no_tail_modify.paths` except the exact rename target.

**Step 1: establish the Task 2 RED surface**

Apply Task 2's five historical removals, 12 replacements, and two API
additions; rename the backend test path exactly. Before deleting products,
recollect the pre-delete stage and then run the discriminating nodes:

- both route-matrix rows must fail because the old resolver selects the
  unavailable route rather than the local writer;
- `test_missing_scheduler_state_uses_local_job_history_without_early_fire`
  must fail because the probe suppresses a valid local-history supplement;
- the lifespan/route node must fail on the two mounted migration routes and/or
  disabled scheduler behavior; and
- the cleanup/network node must fail if startup requires an undeclared
  external dependency or leaves an owner behind.

The scheduler test uses real scratch `SchedulerStateStore` and
`JobRunsLocalStore`, a sealed provider registry, and a deterministic clock. A
mocked `_pg_reachable`-style seam is forbidden.

**Step 2: simplify current news authority**

Remove the unavailable write mode, completion marker, audit-table lookup,
status/copy metadata, and selector branch. Existing normalized and direct
local modes remain only where a current consumer uses them. For the two
matrix inputs that formerly selected the removed mode, resolve to the existing
local writer. Malformed current local configuration remains fail-closed; do
not turn a genuine local read failure into success.

**Step 3: remove migration execution and mount**

Remove the router import/include from `src/api/app.py`, then `git rm` the route,
migrator, and their 17-node test file. No replacement endpoint, hidden CLI,
compatibility function, or manual allowlist remains. Dynamic route projection
must be exactly 173 rows at the Section 0.8 hash.

**Step 4: fix scheduler restart continuity and remove the old smoke**

Delete the reachability helper and every caller. Seed current local
`scheduler_state` first; pass only missing source IDs to an unconditional
`JobRunsLocalStore` supplement; admit the same last-attempt/result facts as
today; leave due only sources absent from both stores. Then `git rm` the old
smoke and its 13-node test.

Implement the two positive local-runtime nodes in `tests/test_api.py`. The
gate starts real FastAPI lifespan and the real scheduler, does not set
`ARKSCOPE_DISABLE_SCHEDULER`, dynamically enumerates `app.routes`, advances one
provider-free tick, denies every socket, and proves complete cleanup. It uses
scratch stores and sealed provider fakes, not a hand-built app or scheduler.

**Step 5: prove Task 2 GREEN**

Run in order:

1. the dedicated scheduler continuity node with mutation-style removal of its
   local-history supplement as a discriminacy check;
2. the 147-node/four-final-path Task 2 focused suite;
3. the 1,781-node inventory-focused Task 2 runtime-survivor projection while
   retaining the full 1,852-node stream as collect-only identity;
4. dynamic routes `173 / e0d8bf3c...`;
5. backend collect-only `4,349 / 04e93190...`;
6. real lifespan/scheduler gate under the socket guard; and
7. protected hashes and a zero-production-open receipt.

**Step 6: commit product and evidence**

```bash
git commit -m "refactor: retire migration and alternate-route execution"
git commit -m "docs: record local runtime route and scheduler evidence"
```

Stop for review unless a recorded batch ruling applies.

### Task 3: Delete backend foundations and dependency declarations

**Deletes, exact seven-path subset of `no_tail_delete.paths`**

```text
src/macro_calendar/store.py
src/tools/backends/db_backend.py
src/tools/db_config.py
tests/test_db_backend.py
tests/test_db_backend_retired_pg_sa.py
tests/test_db_backend_retired_prices.py
tests/test_macro_calendar_store.py
```

**Retained mixed owners**

```text
requirements.txt
src/macro_calendar/__init__.py
src/macro_calendar/local_store.py
src/service/job_runs_store.py
src/service/macro_calendar_health.py
src/tools/backends/__init__.py
src/tools/backends/local_market_backend.py
src/tools/backends/sa_capture_backend.py
tests/conftest.py
tests/test_job_runs.py
tests/test_macro_calendar_local_store.py
tests/test_macro_calendar_local_wiring.py
tests/test_sa_tools.py
```

All retained owners are already members of `no_tail_modify.paths`.

**Step 1: run an ephemeral foundation-absence RED gate**

Create a packet-local test, not a tracked source file. It reads the exact seven
paths above plus the reviewed Python import/dependency symbols from the
inventory. On the Task 2 tip it must fail because every foundation path and
the direct requirement still exist. Negative self-tests prove the gate also
fails when one path, one import, or the dependency row is omitted from its
fixture. Keep the script/hash/transcript in the packet; do not encode the
retired vocabulary into a surviving tracked test.

**Step 2: remove dead foundations and mixed-file halves**

Use `git rm` for the seven paths. In `job_runs_store.py`, delete the remote
store class/imports/serializers and leave `JobRunsLocalStore` plus its current
factory/API behavior. In macro health and local store modules, remove imports,
twin comparisons, SQL-dialect narration, and unavailable-store branches while
preserving current local DTOs and formulas. Remove the direct driver line and
its comment from `requirements.txt`.

Immediately after that edit, normalize the final requirements using pip
requirements-file comment rules: ignore blank/full-line comments and remove
only whitespace-prefixed inline comments. Parse each remaining entry with
`packaging.Requirement` and resolve its installed dependency metadata under
the active environment markers and explicitly requested extras. The declared
closure must contain none of `news-please`, `psycopg`, `psycopg-binary`,
`psycopg2`, or `psycopg2-binary`. This is a declaration/provenance gate, not
permission to uninstall or otherwise mutate the shared developer
environment: its currently installed `news-please` and `psycopg2-binary`
remain dated inventory witnesses. Task 5 still owns the stronger scratch
`site-packages` runtime proof.

Delete every remaining Python import of the retired driver packages and every
class import/re-export/alias/type gate tied to the removed backend. Before the
requirements edit, prove Section 0.1's exact `5/3/4` direct-import partition
has reached zero. A direct import is not converted to a lazy import. An
optional `try/except ImportError` tail is still residue and fails the gate.

Task 3 removes the four foundation test files, exactly 71 passing nodes. It
does not rename or preserve their tests elsewhere. Retained helper behavior is
covered by the existing current local tests already updated in Task 1.

**Step 3: prove foundation GREEN**

Run:

1. the same ephemeral foundation gate, now GREEN;
2. its negative self-tests;
3. inventory-focused `1,781 / 19443b6f...`;
4. backend collect-only `4,278 / 80037a1b...`;
5. Task 1 and Task 2 focused suites;
6. an AST import/inheritance/type-gate projection over every tracked `.py`;
7. the declared-dependency closure projection, with all five retired
   distributions absent;
8. an isolated `python -S` import probe that rejects the removed provider
   names before any module import; and
9. protected hashes.

This stage still contains historical/docs/governance prose, so it does not
claim final zero tracked vocabulary.

**Step 4: commit product and evidence**

```bash
git commit -m "refactor: remove obsolete backend foundations"
git commit -m "docs: record backend foundation retirement evidence"
```

Stop for review unless a recorded batch ruling applies.

### Task 4: Rewrite current authority and retire tracked residue

**Scope**

- `git rm` the exact 171 final admitted delete paths not already removed by
  Tasks 2-3: 149 remaining inventory members plus Section 0.7f's 22-path net
  bundle supplement;
- finish the exact 182 semantic modify surfaces: 174 inventory members minus
  Section 0.7g's nine collection-only protected paths, plus Section 0.7f's
  literal 17-path current-authority supplement;
- add only `src/tools/backends/local_capabilities.py`, already created in
  Task 1;
- perform only the two exact ownership-preserving path renames; and
- keep all 26 final protected paths byte-identical.

With rename detection disabled, the product-path base-to-Task-4 name status
must be exactly `185 D / 180 M / 3 A`: the semantic 183 deletes plus two
modify-source rename deletions, 180 retained modify paths, the one capability
addition, and two rename destinations. Temporary governance paths are
excluded from this semantic ledger. With rename detection enabled, Git may
report the two pairs as renames; admission uses `--no-renames` for
deterministic accounting.

**Step 1: establish the zero-residue RED gate**

Copy the reviewed inventory scanner algorithm into the packet, not the
tracked tree. Its fixed case-insensitive terms are exactly:

```text
DATABASE_URL
DatabaseBackend
PostgreSQL
_get_conn
app_records_migrate
app-records/migration
asyncpg
database backend
database server
db_dsn
db_backend
migration_apply
migration_preview
pg8000
pg_
postgres
postgresql+
psycopg
psycopg2
sqlalchemy.dialects.postgresql
sslmode
use_local_records
```

It also applies the inventory's exact standalone ASCII `PG`, identifier
morphology, and semantic-path rules. It parses Python AST imports, classes,
base classes, calls, and string constants; structured requirements; tracked
paths; comments/docstrings/test IDs/fixtures; current docs; Docker/SQL; and
the three git-crypt plaintext files through the reviewed blob-equality
dual-tree boundary. It skips only the five inventory-named PNG binaries and
opaque integrity values in exact `package-lock.json`; there is no archive,
history, generated-doc, or filename exemption.

Before Task 4 edits, run the gate and require RED with the current reviewed
remaining surfaces. A scanner that returns GREEN, silently skips a tracked
text file, or cannot detect injected fixture terms is rejected. Its negative
self-tests inject one example from every source family.

**Step 2: delete the remaining 171 admitted paths**

Compute the set difference mechanically from `no_tail_delete.paths` and the
12 exact paths already removed, then union Section 0.7f's exact 22 net-new
bundle paths. Use `git rm --` with that generated 171-row file. The complete
23-path EIR-006 bundle must be absent together; retaining its README,
SHA256SUMS, controller scripts, or payloads while deleting only
`consumer-census.tsv` is rejected. Do not preserve Docker, SQL,
dump/manifest, archive, migration, historical plan/spec/evidence, or old test
material under another tracked directory. Any missing path or 172nd deletion
is a stop.

**Step 3: rewrite every retained semantic modify surface**

Remove old imports, branches, names, fixtures, status/copy fields, comments,
docstrings, and contrastive prose while preserving current behavior. Specific
required closures include:

- `README.md` and every current authority describe the app positively as a
  local application without mentioning an absent database server;
- `config/.env.template` has no obsolete key or explanatory line;
- current agents/tools/operator commands retain supported local behavior and
  lose only their retired branch;
- frontend DTOs/copy/tests lose migration/fallback/cutover narration without
  changing current requests, statuses, controls, or layout;
- `SettingsPostPgExitStorage.test.ts` and
  `test_news_pg_unreachable.py` move to their exact Section 0.1 destinations;
  and
- the 18 frontend IDs become exactly Section 0.7's positive IDs;
- the three Section 0.7f backend IDs become their truthful replacements, the
  retained legacy-score owner drops only the deleted tracker path, the SA
  storage owner reads current `_SCHEMA`, and the local backend owner asserts
  public direct-composition methods rather than inherited `_connect`; and
- all 17 Section 0.7f supplement paths receive only the exact
  comment/docstring/link cleanup needed to point at current owners or remove a
  dead backlink.

Every retained test edit must also belong to Section 0.7a's exact body or
shared-fixture projection, an exact Section 0.7c supplement, or Section
0.7f's four exact owner bodies. The executor
records pre/post AST scope hashes and
proves that every other retained node body in the same files is byte-identical.

Generate a packet-local backlink projection from all 183 final deleted paths.
Scan retained product, configuration, and current-authority documents for
literal full paths, relative-link targets, and deleted basenames. Every
admitted hit must be owned by the original 174 modify paths or Section 0.7f's
exact 17-path supplement, and the post-rewrite result must be empty. This gate
does not authorize changing unrelated historical prose outside the already
owned sets.

Do not translate technical terms into unnatural Traditional Chinese merely
to avoid English. Current user-facing copy should use established terms such
as `擷取` where applicable; value-only copy edits must preserve i18n structure.

The three encrypted docs are not implicitly editable. If their unlocked
plaintext has no match, their blobs remain unchanged. A match would be an
unowned-path stop-and-amend event because none belongs to the reviewed modify
set; ciphertext grep is never absence evidence.

**Step 4: run product zero-residue GREEN with exact governance exclusions**

Before temporary governance retires, rerun the scanner over every tracked path
except this exact list:

```text
docs/design/PG_RUNTIME_CONSUMER_INVENTORY.md
docs/design/PROJECT_PRIORITY_MAP.md
docs/design/pg_runtime_inventory/MANIFEST.sha256
docs/design/pg_runtime_inventory/* (the exact 23 payload paths listed by that manifest)
docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md
docs/superpowers/evidence/2026-08-16-postgresql-runtime-no-tail.md
docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md
docs/superpowers/plans/2026-08-16-postgresql-runtime-no-tail.md
docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md
```

The result must contain zero rows. Globs are forbidden in the executable
exclusion file: list and hash `MANIFEST.sha256` itself plus the exact 23
payload paths from its contents. Those 24 files must equal the complete
tracked directory; a 25th path is a stop.

**Step 5: prove frontend and final staged identities**

Run:

1. frontend two-file focused `54 / 83d681a7...`;
2. frontend full collection `1,177 / 101 / c570a551...`;
3. frontend full runtime sequential `1,177/1,177`;
4. TypeScript typecheck, production build, and i18n visible-literal scanner;
5. inventory-focused final `1,781 / 6220cb4e...`;
6. backend collect-only `4,278 / ecafdab7...`;
7. final Task 1 owners `472 / 483b6566...` and unchanged Task 2 owners;
8. the complete-bundle and retained-path backlink gates; and
9. exact `185 D / 180 M / 3 A` product-path algebra plus the 26-path protected
   aggregate `d567da56...`.

The visible-literal scanner's counts are outputs because this task removes
reviewed value text, but debt must remain zero. Do not edit its scanner or
allowlist to manufacture a target.

**Step 6: commit product and evidence**

The product commit body must state:

- semantic path ledger `183 delete / 182 modify / 1 capability add / 26
  protected`, identifying the exact EIR-006 bundle and backlink supplements;
- two bounded ownership-preserving renames;
- node ledger `101 whole-file + 22 historical` removed, `49` positive
  replacements, and `7` new contracts;
- remote tables/private dump/private `.env` untouched; and
- Git history plus the external packet are the recovery record.

```bash
git commit -m "refactor: retire PostgreSQL runtime and tracked support"
git commit -m "docs: record tracked residue retirement evidence"
```

Stop for review unless a recorded batch ruling applies.

### Task 5: Mutations, final admission, and governance self-retirement

Task 5 starts from a clean exact Task 4 tip. It performs no product design or
new cleanup. Any required product change is a stop-and-amend event.

**Step 1: replay M1-M8 independently**

Each mutation starts from a fresh clean copy of the Task 4 tip, changes real
semantics, records the exact patch, makes the named owner RED, then restores
every affected file byte-for-byte before the next mutation.

| Mutation | Exact active change | Required RED owner |
|---|---|---|
| M1 | restore configuration-selected alternate DAL construction | `tests/test_data_access.py::test_default_data_access_constructs_current_local_authority` |
| M2 | remount one migration route | `tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes` |
| M3 | add nominal inheritance or a runtime type gate to a local capability | `tests/test_data_access.py::test_explicit_capability_injection_needs_no_nominal_type_routing` plus module-graph owner |
| M4 | restore a network reachability probe before scheduler history seeding | continuity owner plus local-runtime socket owner |
| M5 | restore a driver import and direct requirement | `tests/test_data_access.py::test_runtime_backend_module_graph_matches_current_local_modules` plus isolated local-runtime gate |
| M6 | restore the retired branch in `handle_save_command` | `tests/test_tools.py::test_cli_save_command_uses_injected_local_capability` |
| M7 | restore one deleted file, one old comment/docstring/test name, and one archive instruction in separate subcases | packet-local zero-residue gate |
| M8 | remove the local job-history supplement while keeping scheduler state reads | `tests/test_data_scheduler.py::test_missing_scheduler_state_uses_local_job_history_without_early_fire` |

M7's owner is deliberately ephemeral: permanently storing the forbidden term
fixture would violate the final-tree contract. The packet-local gate has a
stable artifact ID
`packet://tracked-vocabulary-gate::all_tracked_paths_are_current_authority`,
its own negative self-tests, and a pinned SHA. A textual mutation in ignored
or dead packet text is rejected. M6 must mutate the real command branch; a
fake helper or comment-only edit is rejected.

Require for every product owner:

```text
mutated SHA != pre SHA
restored SHA == pre SHA == exact Task 4 tip SHA
```

An owner that stays GREEN, a second mutation layered on dirty bytes, partial
restoration, or a patch outside the reviewed paths rejects the cycle.

**Step 2: build the final declared-dependency runtime environment**

Do not use the old `.env` symlink. Do not install or download packages. Build
a packet-local import root from current installed distribution files as
follows:

1. normalize final `requirements.txt` with the Task 3 pip-comment rule and
   parse every remaining entry with `packaging.Requirement`;
2. resolve its installed transitive dependency closure under
   `packaging.markers.default_environment()` and the explicitly requested
   extras;
3. hard-link/copy only files owned by that closure into scratch
   `site-packages`, rejecting unowned/shared-path ambiguity;
4. run the gate interpreter with `-S`, repository root plus only that scratch
   directory on `PYTHONPATH`, and no original site-packages path;
5. verify import names `newsplease`, `psycopg`, and `psycopg2` resolve to
   `None`; distribution metadata for `news-please`, `psycopg`,
   `psycopg-binary`, `psycopg2`, and `psycopg2-binary` is absent; and every
   imported third-party module maps to an admitted distribution; and
6. remove the complete scratch import root after the run.

Pytest is the outer test tool, not an application dependency. The tracked
local-runtime node launches a standalone packet gate under this sanitized
interpreter. The builder has negative self-tests for an injected undeclared
distribution, a marker-false dependency, an absolute `.pth`, a missing file,
and each retired distribution/import family. The ordinary developer
environment is not mutated: its currently installed `news-please 1.6.15` and
`psycopg2-binary 2.9.10` are dated inventory witnesses, not declared ArkScope
runtime dependencies. A meta-path blocker over that shared environment is
insufficient evidence.

**Step 3: run final backend admission without `.env`**

In fresh exact Task 4 worktrees with empty real `data/`, scratch local DBs,
sealed providers, Section 0.7h's exact socket-guard owner split, and no
`config/.env` link, run:

1. collect-only `4,278 / ecafdab7...`;
2. native canonical `4,278 seen / 4,266 passed / 12 skipped / 0 failed` twice
   with the pinned reporter and without the blanket socket guard;
3. final Task 1 focused `472 / 483b6566...`, with `471 passed / 1 skipped`;
4. Task 2 focused `147/147`;
5. inventory-focused `1,781 / 6220cb4e...`, with `1,781/1,781` runtime;
6. real local-runtime lifespan/scheduler gate under the sanitized dependency
   environment and unchanged socket guard;
7. routes `173 / e0d8bf3c...`;
8. scheduler continuity owner and its discriminacy mutation;
9. AST/import/dependency/final-path/backlink/complete-bundle gates plus the
   26-path protected aggregate; and
10. the exact six-node callback control plus zero-socket 4,272-node guarded
    complement from Section 0.7h.

The reporter JSON must be deterministic across two independent exact-tip runs
apart from timing fields excluded by the pinned reporter. Any skipped node not
in the exact final 12-row skip stream is a stop. Any need for a private link,
driver import, scheduler disable flag, external network exception, broader
loopback allowance, or production DB is a failed admission, not an
environment workaround.

**Step 4: run final frontend and safety admission**

Run explicit Vitest 4.1.8 sequential full `1,177/1,177`, the 54-node frontend
owner projection, typecheck, build, and i18n scanner. Prove Python product
bytes are unchanged since Task 4, frontend identity is the Section 0.11 final,
all 26 protected bytes match, no production opener appears, no provider request is
made, and all scratch processes/files/links are cleaned.

**Step 5: commit admitted evidence, then retire governance**

Commit the complete Task 5 evidence/status update first:

```bash
git commit -m "docs: record local runtime final admission"
```

Copy every tracked temporary authority at that evidence tip plus the complete
packet into an external review packet and checksum it. Populate
`last-containing.tsv` for every deleted/rewritten path and prove sampled plus
category-complete `git show` recovery.

Then, in one final tracked commit:

1. `git rm` every full path/directory in Section 0.9;
2. remove every obsolete program entry from `PROJECT_PRIORITY_MAP.md`;
3. add only a neutral newest-first handoff to the legacy-agent CLI census;
4. do not add a tracked closeout/evidence replacement; and
5. use a commit body that identifies the Task 5 evidence tip and external
   packet manifest without putting secret/path values into Git.

```bash
git commit -m "docs: close retired runtime program authorities"
```

On that exact final tip, rerun the packet-local zero-residue scanner over all
tracked files with **zero exclusions**. Require zero rows, rerun collection
identities, and verify the governance-only commit changed no product/test/
dependency bytes. Store these final-tip results only in the external packet.

### Task 6: Combined implementation review gate

Stop. Task 6 is not a code task. Provide Fable with:

1. linear commit ancestry and every per-task product/evidence pair;
2. literal base/staged/final streams and reconstruction helper;
3. exact augmented semantic path algebra, both Section 0.7f supplement
   streams, complete-bundle proof, and `--no-renames` name-status;
4. the 36-method interface projection, seven retained domain-owner
   projections, and all 18 consumer-surface call-site witnesses;
5. RED/GREEN transcripts and rejected attempts;
6. M1-M8 patches, owner REDs, and byte restoration hashes;
7. final native/local-runtime/frontend/route/scheduler reports;
8. zero-residue scanner plus negative self-tests and zero-row final output;
9. historical 22-path plus final 26-path protected aggregates and
   production/no-network/no-secret witnesses;
10. complete last-containing/recovery ledger; and
11. external packet `SHA256SUMS` and cleanup receipt.

Task 7 remains unauthorized until this review is GREEN.

### Task 7: Fast-forward merge and exact-master closeout

After Task 6 GREEN only:

1. prove master is still an ancestor of the reviewed final tip;
2. `git merge --ff-only <reviewed-tip>` without push;
3. create a fresh detached exact-master worktree;
4. rerun final backend/frontend collections, native 4,266P/12S/0F, focused
   suites, sanitized local-runtime gate, dynamic routes, scheduler continuity,
   final protected bytes, complete-bundle/backlink gates, and zero-exclusion
   tracked-tree scanner with new artifact names;
5. require exact product bytes and canonical reports to equal the reviewed
   branch tip;
6. clean every worktree/runtime/link/process; and
7. publish no tracked closeout document, because doing so would recreate the
   retired narrative surface.

Stop for focused exact-master closeout review. Do not push. After that review,
the separate private `.env` key-removal operation may be requested from the
user; it checks only key absence and requires an App/sidecar restart. Remote
tables and private dumps remain untouched.

The next product-analysis slice starts the docs-only legacy-agent CLI census
from exact merged master. CLI retirement still requires a later user ruling.

---

## 2. Hard stop conditions

Stop immediately and write a bounded docs-only amendment if any of these is
true:

1. master, plan base, inventory authority tip, or merge-base differs;
2. any of the four immutable inventory path sets differs in bytes, count, or
   membership, either Section 0.7f supplement differs, or Section 0.7g's
   nine-path disposition supplement differs;
3. an implementation path falls outside the inventory sets, Section 0.7f's
   exact bundle/backlink supplements, the two exact rename destinations, and
   temporary governance; Section 0.7g protects bytes and grants no edit path;
4. the two rename destinations are treated as general additions, their source
   survives, or a third rename is needed;
5. a staged collection count/hash or literal add/remove row differs;
6. a base old ID is missing/duplicated or a planned new ID already exists;
7. a new capability method exceeds or omits the exact 36-row set, or one of
   the seven existing domain-owner surfaces is absorbed into the protocol;
8. a retained consumer requires a method not measured by inventory;
9. a local class still inherits, imports, aliases, re-exports, or type-routes
   through the retired backend;
10. DAL construction reads a DSN/config key, accepts an ignored DSN, infers
    authority from type/method presence, or falls back to a different backend;
11. a missing/corrupt local store changes an existing honest-empty or typed
    failure contract;
12. a current product entrypoint can reach a foundation left temporarily on
    disk after Task 1;
13. scheduler local history is consulted before durable scheduler state, or a
    present state row is overwritten by supplement data;
14. the continuity test uses a mocked probe/store rather than real scratch
    local stores;
15. any scheduler probe, external socket attempt, provider call, remote DB
    attempt, or loopback call outside Section 0.7h's exact six-node owner
    occurs;
16. dynamic route census removes/adds any route other than the exact two rows;
17. the real lifespan/scheduler gate disables scheduler, uses a hand-built
    route list/app, or does not complete one provider-free tick;
18. any whole-file test retirement is partial, copied, or expanded past the
    exact 101-node/six-file ledger;
19. an existing test node name/body or shared test scope outside Sections
    0.4-0.7f must change, or an in-place evolution changes behavior beyond
    replacing the inventoried obsolete reference with its current local
    contract;
20. a historical node is preserved under a renamed compatibility assertion;
21. one of the final 26 protected bytes changes, a Section 0.7g path is edited,
    or a protected path other than Section 0.7f's exact five bundle producers
    moves to deletion;
22. `file_backend.py`, package lockfiles, app package manifest, remote-table
    state, private dump, production SQLite, or private `.env` changes;
23. an encrypted-path absence claim comes from ciphertext grep or a blob ID
    differs between implementation tip and unlocked main;
24. the final dependency environment contains an undeclared distribution,
    original site-packages path, absolute `.pth`, `news-please`, or a retired
    driver provider;
25. `npx`, `npm exec`, installation, download, wrong Vitest, or app-local
    `node_modules` resolution occurs;
26. final native requires the old `.env` symlink or produces anything other
    than 4,266P/12S/0F;
27. any M1-M8 owner stays GREEN, mutation is fake/dead text, or restoration is
    not byte-identical;
28. zero-residue scanner skips an unlisted tracked file/source family, fails a
    negative self-test, or reports any final-tip row;
29. Task 4 needs a git-crypt path not present in the reviewed modify set;
30. final `183/182/1/26` semantic path algebra or `185 D / 180 M / 3 A`
    `--no-renames` count differs;
31. temporary governance or obsolete map entries survive final tip;
32. a tracked closeout document reintroduces the retired program narrative;
33. last-containing ledger cannot recover a changed/deleted blob via
    `git show`;
34. a packet contains a secret value, private home path, DSN, email, arbitrary
    encrypted plaintext, or unsanitized runtime error payload;
35. cleanup leaves a process, FD, port, symlink, scratch DB, site-packages
    copy, worktree, or ignored generated artifact;
36. merge is not fast-forward, master drift is ignored, or any push occurs;
37. a later runtime-owner, CLI-retirement, provider, CSS, remote-table, or
    product redesign is pulled into this line; or
38. any failure is reclassified as environmental without a discriminating
    control and retained rejected transcript; or
39. the EIR-006 bundle is only partly removed, the retained-path backlink
    gate reports a final row, a fourth Task 4 backend ID changes, or a path is
    added to either Section 0.7f literal supplement without another Class B
    amendment.

---

## 3. Independent review handoff

Plan review must reconstruct, without trusting executor-generated helpers:

1. all four immutable inventory path sets, both Section 0.7f supplements,
   Section 0.7g's nine-path disposition correction, the complete-bundle split,
   and historical/final protected aggregates;
2. the exact 36-method union assigned to `LocalDataCapabilities`, the seven
   existing domain-owner projections, and all 18 measured surface rows;
3. 101 whole-file nodes, 22 historical IDs, 46 historical plus three final
   Task 4 replacement pairs, seven new IDs, 18 frontend pairs, and the five
   retained-test evolution streams;
4. the 17/5, 34/12, 5/2, and 30/71 task partitions, plus the exact Task 1 and
   Task 2 runtime-survivor projections;
5. every backend/frontend/focused staged identity in Section 0.11, preserving
   Task 3 as dated truth while applying the Section 0.7f final delta;
6. final native arithmetic and skip inheritance;
7. the 173-row dynamic route target;
8. the two ownership-preserving rename exceptions and why they do not alter the
   capability add set;
9. phase ordering, exact per-phase delete subsets, final `185 D / 180 M / 3 A`
   algebra, and deleted-reference closure;
10. M1-M8 owner discriminacy, especially M6's real CLI branch and M7's
    ephemeral owner;
11. final declared-dependency environment construction;
12. governance self-retirement and zero-exclusion final census; and
13. remote/private/destructive exclusions and the legacy-agent census handoff.

Only a fully reconstructable GREEN plan authorizes Task 0. Product code,
merge, push, private configuration, remote tables, private dump, and CLI
retirement remain unauthorized at plan handoff.
