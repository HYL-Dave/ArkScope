# ArkScope Legacy Scheduler Sources and IV Domain Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: MERGED - PRODUCTION RETIREMENT PENDING**
>
> Independent implementation review returned GREEN after the evidence-index
> corrections in `28b136d1`; `master` fast-forwarded to that exact tip on
> 2026-07-27. Steps 2-9 in the production protocol remain separately gated.

Review packet, created during implementation:
`docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md`.

**Goal:** Remove three dead scheduler identities and the stale legacy IV
history domain without deleting execution history, changing current option
math/live option-chain behavior, or touching production data before a second
post-merge approval.

**Architecture:** Work is split at a named `TRANCHE_1_TIP`. Tranche 1 reduces
the schedule catalog to its four real direct collectors and replaces implicit
news-mode fallthrough with one exhaustive pre-provider classifier. Tranche 2
removes the old SQLite/Parquet IV read domain across API, UI, health, evidence,
and agent surfaces, then adds an audited preview/archive/apply/restore tool.
Production cutover is not part of implementation review and remains separately
approval-gated.

**Tech Stack:** Python 3.10, SQLite, pandas/Parquet, FastAPI/Pydantic, pytest,
React 18, TypeScript 5.9, i18next, Vitest, Playwright/Chromium, shell-based
no-PG smoke, and Git two-point A/B accounting.

---

## 1. Authority And Review State

1. Product and migration authority:
   `docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md`.
2. Future IV authority:
   `docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md` and the still-gated S-D/S-E
   decisions in `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Historical PG-exit authority:
   `docs/design/PG_EXIT_REMAINDER_SCOPING.md`.
4. Broader scripts-retirement authority:
   `docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md`. This plan removes only
   the two scripts that consume the old IV store. It does not expand or close
   the broader scripts-retirement program.
5. Behavioral base: clean `master` tip
   `7bb7cc29f70ca899a5b598f2322ce181daa17ebe`.

If implementation contradicts an authority above, stop and amend the relevant
document before editing product code.

### 1.1 Independent spec-review resolution

Independent review returned GREEN after four corrections. They are binding:

1. no-PG smoke changes from 24 to 23 by removing exactly
   `CheckSpec("iv_history", "GET", "/options/AMD/history", 200,
   _assert_key("points"))` and its direct `options.iv_history(ticker,
   dal=self.dal)` dispatch;
2. `scripts/analysis/compare_bs_vs_american.py` and
   `scripts/analysis/scan_option_mispricing.py` are explicit Tranche 2
   removals, while every unrelated script remains out of scope;
3. removal of the current `sync_flag` fallthrough must be preceded by an
   explicit exhaustive `NewsWriteMode` classifier and mutation-sensitive
   unknown-mode tests; and
4. production IDs are described as 24 non-contiguous rows with `min(id)=1`
   and `max(id)=248`, never as a continuous range.

The plan-review reminder is also binding: Tranche 1's additive classifier tests
are separately identified from retirement and rename nodes. Their additions
must not be hidden inside net `+N/-M` arithmetic.

### 1.2 Independent plan-review resolution

Independent plan review returned substantive GREEN with two required
docs-only corrections. Both were independently verified against current code
and neither changes a target count:

1. The unknown `NewsWriteMode` example now asserts ArkScope's actual scheduler
   failure envelope: `status="failed"`, plus equal stable `code` and
   `reason_code`. It also asserts that no `ok` field is present. The former
   `result["ok"]` example would have raised `KeyError`, producing an
   unattributable RED before testing the classifier contract.
2. Tranche 2 explicitly removes the unreachable in-process market-data job
   poller. `start_bootstrap_job`, `start_update_job`, `_JOBS`, `_JOBS_LOCK`,
   and `get_job` have no current product caller because bootstrap/update/
   validate routes are permanent 409 tombstones. Remove
   `GET /market-data/jobs/{job_id}`, frontend `MarketDataJob`/
   `getMarketDataJob`, and the backend helpers together. The seven owning
   backend tests were already in the reviewed 40-node retirement set, so
   backend/frontend arithmetic is unchanged.

The exact clearance commit containing both corrections is:

```text
PLAN_REVIEW_CLEARANCE_COMMIT=5f528475420c8de407125bceb32d94050cfa8e14
```

This following pointer-only docs commit changes no product authority or
accounting.

## 2. Locked Decisions

1. Active scheduler source IDs after Tranche 1 are exactly:
   `polygon_news`, `finnhub_news`, `ibkr_news`, and `ibkr_prices`.
2. `price_backfill`, `local_incremental`, and `iv_history` are permanently
   retired IDs. Unknown calls return typed 404 before write, provider, worker,
   lock, or telemetry work.
3. Historical `job_runs` rows remain byte- and row-preserved. Removing source
   definitions does not require synthetic Settings rows for historical jobs.
4. The three-state schedule control DTO retires. Every returned schedule row
   is an active, controllable source.
5. Direct-local news and price writers remain. PG mirror controls,
   `skip_sync`, `_local_refresh`, source `sync_flag`, and the old local mirror
   execution path do not.
6. `prices_runtime` keeps ticker, provider, and Gateway-lock inputs, but has no
   scheduler-source selector. `backfill_prices_direct()` remains a reusable
   direct-price primitive.
7. News write-mode classification is explicit for the four current enum
   members. A fifth member cannot silently inherit a route. Classification
   happens before provider lookup, lock acquisition, adapter/worker calls,
   writes, or job telemetry.
8. Tranche 2 removes the legacy ATM-IV snapshot contract, not IV as a research
   concept. Greeks, live option chain, IV skew, pure option-pricing math, and
   current provider-client domain configuration remain.
9. The retired SQLite and Parquet payload is archived before production
   deletion. Production is read-only throughout implementation and review.
10. Production apply requires merged code, stopped writers, a fresh preview,
    exact manifest approval, and a second explicit user authorization.

## 3. Grounded Baselines And Accounting

All counts are dated observations. Task 0 must reproduce their normalized node
lists in the isolated implementation worktree. A mismatch before product edits
is a stop condition, not permission to rewrite the target silently.

### 3.1 Canonical collection recipes

Use `/home/hyl/.virtualenvs/llm_app/bin/python`. The repository has no
authoritative `.venv`.

Backend node IDs are raw pytest `file.py::node` strings:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
  | LC_ALL=C sort > /tmp/legacy-retirement-be-full.nodes
wc -l /tmp/legacy-retirement-be-full.nodes
sha256sum /tmp/legacy-retirement-be-full.nodes
```

Expected base:

```text
4749
e7dc826f33c202789f8ad5f43787d1eedd8f288cc55aa4996d0a100761a21b20
```

The two `scripts/testing/` nodes are part of pytest's full collection. Omitting
them yields `4747` and a different hash even though pytest reports `4749`.

Frontend node IDs use repository-relative `file<TAB>name` fields from Vitest
JSON. Vitest 4 emits `.file`, not `.filepath`:

```bash
cd apps/arkscope-web
npx vitest list --json \
  | jq -r '.[] | [.file, .name] | @tsv' \
  | sed "s#$(pwd)/##" \
  | LC_ALL=C sort > /tmp/legacy-retirement-fe-full.nodes
wc -l /tmp/legacy-retirement-fe-full.nodes
sha256sum /tmp/legacy-retirement-fe-full.nodes
```

Expected base:

```text
96 files / 1072 nodes
d964d330e9d5935aae3b746dfabe353d4ee5efc70671295127fdaccc8ad243e0
```

Do not use absolute full-suite failure counts as acceptance constants. Run base
and tip in equivalent environments and compare normalized non-passing node-ID
sets. Existing environment-dependent failures are not allowlisted; any new or
disappeared node requires explanation.

### 3.2 Focused suites

Backend focused base: 23 files, 663 nodes, hash:

```text
415b51d19cac89cb40bb97fb5fdd39296428da3cac8db11b47f98b9770fe07be
```

The exact per-file census is:

```text
tests/test_data_scheduler.py                 101
tests/test_scheduler_state.py                  8
tests/test_api.py                             32
tests/test_daily_update_wrapper.py             7
tests/test_prices_runtime.py                    4
tests/test_market_data_direct.py               63
tests/test_agents.py                           31
tests/test_compressor_reducers.py              30
tests/test_data_access.py                      31
tests/test_data_coverage_tools.py               5
tests/test_db_backend.py                       24
tests/test_db_backend_retired_prices.py         4
tests/test_evidence_packet.py                  10
tests/test_freshness.py                        24
tests/test_iv_skew_tools.py                    16
tests/test_market_data_admin.py                64
tests/test_news_pg_unreachable.py               4
tests/test_option_chain_tools.py               15
tests/test_option_pricing.py                   60
tests/test_pg_unreachable_e2e.py               13
tests/test_provider_health.py                  20
tests/test_sqlite_backend.py                   68
tests/test_tools.py                            29
```

`tests/test_scheduler_state.py` is included even though its generic node IDs
do not change: its fixture currently advertises `price_backfill` and must move
to a neutral active source without changing generic store behavior.

Frontend focused base: 9 files, 139 nodes, hash:

```text
ccc689302f0a17f89fa2bad12effebcda84819d3bfdbb00a41fde80bcbc0974c
```

```text
SettingsPostPgExitStorage.test.ts             10
SettingsProviderConfig.test.ts                36
TickerDetail.test.tsx                         11
dataSourceSchedulePolling.test.ts              3
dataSourcesPresentation.test.ts                4
explore/explorePresentation.test.tsx          13
i18n/resources.test.ts                        14
marketDataDisplay.test.ts                     36
settings/settingsBackendCopy.test.ts          12
```

Derive this focused list by exact file projection from the canonical frontend
full list. Do not place a file path immediately after Vitest 4's optional
`--json` flag: it is parsed as the JSON output path and will overwrite that
file.

### 3.3 Fixed non-node ledgers

```text
                           Base        TRANCHE_1_TIP       Final
Backend full              4749             4731            4691
Backend focused            663              645             605
Frontend full             1072             1072            1072
Frontend focused           139              139             139
Settings leaves            714              706             704
Explore leaves             401              401             379
Total resource leaves     1814             1806            1782
Central tools               56               56              53
OpenAI bridge tools         57               57              54
Anthropic bridge tools      57               57              54
No-PG checks                24               24              23
Scanner                    36/20/0/20       unchanged       unchanged
Scanner scope              src/**           unchanged       unchanged
```

Backend composition:

```text
Tranche 1: +6/-24 = -18
Tranche 2: +23/-63 = -40
Base -> final: +29/-87 = -58
```

Frontend composition:

```text
Tranche 1: +3/-3 = 0
Tranche 2: +1/-1 = 0
Base -> final: +4/-4 = 0
```

### 3.4 Tranche 1 backend node ledger

`tests/test_data_scheduler.py` changes `101 -> 84`, composition `+4/-21`.

Retire these 19 behavior nodes:

```text
test_run_source_iv_history_retired_before_provider_work
test_local_incremental_has_no_subprocess
test_price_backfill_source_registered
test_coverage_derived_price_backfill_is_deliberate_noop
test_blank_price_backfill_history_is_neutral_and_first_run_succeeds
test_status_or_continuation_only_price_backfill_state_fails_closed
test_error_or_result_only_price_backfill_state_fails_closed
test_local_incremental_retired_after_p0c
test_local_incremental_retirement_does_not_call_local_refresh
test_price_backfill_ignores_gateway_lock_but_keeps_source_lock
test_price_backfill_does_not_resolve_scope_for_deliberate_noop
test_unknown_tickers_and_provider_errors_never_reach_price_executor
test_legacy_unproven_gap_manual_continuation_is_rejected_without_worker
test_legacy_unproven_gap_scheduler_continuation_is_rejected_without_worker
test_status_snapshot_preserves_durable_state_without_planner_metadata
test_post_exit_ibkr_local_refresh_excludes_retired_pg_domains
test_local_refresh_excludes_news_when_pg_exit_audit_cannot_be_read
test_skip_sync_is_true_collect_only
test_skip_sync_message_precedes_legacy_local_news_route
```

Rename these two nodes; each rename is one removal plus one addition:

```text
test_run_source_explicit_tickers_and_skip_sync
  -> test_run_source_explicit_tickers_reaches_active_adapter_without_mirror_controls

test_run_now_choke_point_guards_scheduled_and_rejects_retired_sources
  -> test_schedule_routes_reject_removed_source_ids_before_writes_or_provider_work
```

Add these two NewsWriteMode nodes. They are additive safety work, not
retirement replacements:

```text
test_news_write_mode_classifier_is_exhaustive_for_current_modes
test_unknown_news_write_mode_fails_before_provider_adapter_worker_and_telemetry
```

`tests/test_daily_update_wrapper.py` changes `7 -> 6`, composition `+1/-2`:

```text
retire: test_iv_history_opt_in_only
rename: test_dry_run_without_sync_db_collect_only
     -> test_dry_run_reports_direct_local_collection_without_mirror_controls
```

`tests/test_prices_runtime.py` remains at 4, composition `+1/-1`:

```text
test_prices_worker_requires_source_and_tickers
  -> test_prices_worker_requires_tickers_without_source_selector
```

`test_p0c1_ibkr_prices_runs_prices_worker_subprocess` evolves in place. It must
feed the captured scheduler `argv[3:]` into the real
`src.prices_runtime.parse_args()` and assert exact tickers/provider/Gateway
shape plus absence of `--source`. A mock-only argv assertion is insufficient.

All other focused node IDs are unchanged in Tranche 1. Existing catalog,
status, route, mounted Settings, and resource nodes evolve in place only where
their assertions still describe a live four-source property.

The six spec-named live contracts resolve as follows:

```text
evolve in place, same ID:
  test_no_active_runtime_source_uses_migrate_to_supabase_sync
  test_scheduler_source_defs_have_no_legacy_collector_plumbing
  test_status_snapshot_provider_fetch_tracks_live_fetch_paths

rename with exact successor:
  test_run_now_choke_point_guards_scheduled_and_rejects_retired_sources
    -> test_schedule_routes_reject_removed_source_ids_before_writes_or_provider_work
  maps all seven schedule source ids without backend labels
    -> maps exactly four active schedule source ids without backend labels
  shows_disabled_provider_and_read_only_schedule_states_as_neutral_text
    -> renders_disabled_providers_as_neutral_and_all_four_schedule_rows_as_controllable
```

The first same-ID test must change from a negative migration-script assertion
to the stronger exact no-mirror-field/no-mirror-call boundary; retaining its
old body is not accepted as evolution.

### 3.5 Tranche 1 frontend node ledger

`settingsBackendCopy.test.ts` renames:

```text
maps all seven schedule source ids without backend labels
  -> maps exactly four active schedule source ids without backend labels
```

`SettingsProviderConfig.test.ts` renames:

```text
shows_disabled_provider_and_read_only_schedule_states_as_neutral_text
  -> renders_disabled_providers_as_neutral_and_all_four_schedule_rows_as_controllable

does_not_render_storage_route_source_badges
  -> does_not_render_backend_storage_route_badges_for_active_schedule_rows
```

Every other frontend node ID evolves in place or remains unchanged. Fixtures
must use `finnhub_news`/`ibkr_prices` rather than retired IDs when they need
skipped or historical active-row shapes.

### 3.6 Tranche 2 backend node ledger

Retire exact existing nodes:

```text
tests/test_api.py (-5)
  TestOptionsEndpoints::test_iv_analysis
  TestOptionsEndpoints::test_iv_history
  TestScanEndpoints::test_mispricing_scan
  test_iv_analysis_source_path_mapping
  test_iv_history_source_path_mapping

tests/test_data_access.py (-3)
  all three TestIVHistory nodes

tests/test_db_backend.py (-2)
  both TestIVHistoryDB nodes

tests/test_sqlite_backend.py (-4)
  test_iv_history_local_then_honest_empty_without_pg
  test_provenance_iv_recorded
  test_query_iv_history
  test_query_iv_history_empty

tests/test_market_data_admin.py (-40)
  the reviewed IV/PG mirror bootstrap, incremental, checksum, update,
  validation, retired-mirror route, and unreachable in-process job-poller
  nodes enumerated in Task 6

tests/test_tools.py (-4)
  the three old IV-history-backed tools plus their old catalog assertion

tests/test_compressor_reducers.py (-4)
  the TestIvHistoryReducer class

tests/test_evidence_packet.py (-1)
  test_iv_signal_judgment_is_dropped
```

Add 22 exact nodes:

```text
tests/test_api.py (+1)
  test_retired_market_admin_and_iv_routes_are_absent_while_greeks_remains_reachable

tests/test_evidence_packet.py (+1)
  test_packet_has_no_legacy_iv_environment_or_missing_iv_source

tests/test_legacy_scheduler_iv_retirement.py (+16)
  test_preview_classifies_exact_targets_and_value_multisets
  test_preview_is_read_only_and_deterministic
  test_preview_rejects_schema_or_index_drift
  test_preview_rejects_unknown_view_trigger_or_reference
  test_preview_rejects_sqlite_parquet_value_mismatch
  test_preview_rejects_source_drift_between_classification_and_archive
  test_archive_writes_mode_restricted_restore_complete_artifacts
  test_archive_verification_rejects_tamper_before_apply
  test_apply_removes_only_target_operational_state_and_iv_payload
  test_apply_preserves_job_runs_and_non_target_logical_digests
  test_apply_resumes_after_profile_owner_checkpoint
  test_apply_resumes_after_market_owner_checkpoint
  test_second_apply_is_byte_and_row_idempotent
  test_restore_round_trip_recovers_exact_archived_targets
  test_restore_refuses_nonempty_or_differently_shaped_targets
  test_cli_requires_reviewed_preview_and_exact_pre_retirement_commit

tests/test_legacy_iv_retirement_boundaries.py (+4)
  test_current_runtime_has_no_legacy_iv_storage_or_api_owner
  test_retained_option_capabilities_do_not_import_legacy_iv_store
  test_non_migration_scripts_do_not_read_legacy_iv_store
  test_sql_init_and_current_backends_have_no_legacy_iv_schema
```

The 40 `test_market_data_admin.py` retirements are:

```text
test_bootstrap_and_incremental_keep_fts_via_triggers
test_bootstrap_builds_iv_and_fundamentals
test_bootstrap_builds_prices_and_news
test_bootstrap_carries_over_financial_cache
test_bootstrap_clean_state_after_rebuild_with_stale_sidecars
test_bootstrap_creates_empty_financial_cache
test_bootstrap_done_poll_invalidates_dal_cache
test_bootstrap_job_records_retired_pg_mirror_error
test_bootstrap_market_refuses_retired_pg_mirror_before_pg_connect
test_bootstrap_mismatch_keeps_existing_db
test_bootstrap_route_rejects_retired_pg_mirror
test_bootstrap_with_alias_spellings_validates_then_canonicalizes
test_fundamentals_checksum_catches_id_drift
test_incremental_iv_and_fundamentals_add_new_rows
test_incremental_prices_catches_new_ticker
test_incremental_prices_query_is_group_aware
test_incremental_provider_failure_not_fatal
test_incremental_update_adds_new_rows
test_incremental_update_exclude_news_and_other_omitted_domains_skip_pg_queries
test_incremental_update_exclude_news_domain_skips_pg_news_query
test_incremental_update_idempotent
test_incremental_update_leaves_financial_cache_intact
test_incremental_update_missing_db
test_iv_checksum_catches_id_drift
test_job_not_found_404
test_manual_update_domains_after_p0c_returns_empty_retired_domain_set
test_news_checksum_catches_id_drift
test_p0c_incremental_update_prices_is_retired
test_p0c_manual_update_rejects_retired_mirror
test_p0c_update_route_rejects_retired_mirror
test_update_job_all_domains_fail_is_error
test_update_job_ignores_skipped_domains_when_deciding_success
test_update_job_passes_explicit_domains_to_incremental_update
test_update_job_surfaces_iv_or_fundamentals_failure
test_update_route_rejects_retired_prices_after_news_pg_exit_audit
test_validate_iv_and_fundamentals
test_validate_market
test_validate_market_folds_aliases_so_canon_db_matches_pg
test_validate_market_refuses_retired_pg_mirror_before_pg_connect
test_validate_route_rejects_retired_pg_mirror
```

Tests in agents, freshness, data coverage, provider health, no-PG smoke, and
frontend owners evolve in place. Their count/name assertions must become exact
without node-ID churn.

### 3.7 Tranche 2 frontend and resource ledger

Rename one mounted node:

```text
preserves successful legs while naming IV history fundamentals status and coverage failures
  -> preserves successful price and fundamentals legs while retiring legacy IV requests
```

Remove exactly these Tranche 1 Settings leaves per locale:

```text
dataSources.labels.readOnly
dataSources.labels.retired
dataSources.schedule.sources.ivHistory.label
dataSources.schedule.sources.ivHistory.description
dataSources.schedule.sources.localIncremental.label
dataSources.schedule.sources.localIncremental.description
dataSources.schedule.sources.priceBackfill.label
dataSources.schedule.sources.priceBackfill.description
```

Remove exactly these Tranche 2 Settings leaves per locale:

```text
dataStorage.labels.iv
dataStorage.summary.iv
```

Remove exactly these 22 Explore leaves per locale:

```text
errors.operations.tickerLoadIv
errors.operations.tickerLoadIvHistory
tickerDetail.ivSignalSuffix
tickerDetail.atmIv
tickerDetail.hv30
tickerDetail.ivHistorySummary.one
tickerDetail.ivHistorySummary.other
tickerDetail.quotes
tickerDetail.spot
tickerDetail.vrp
tickerDetail.noIv
tickerDetail.impliedVolatility
tickerDetail.ivLocalCoverage
tickerDetail.ivCurrentSource
tickerDetail.ivHistory
tickerDetail.kvLabels.currentAtmIv
tickerDetail.kvLabels.hv30d
tickerDetail.kvLabels.vrp
tickerDetail.kvLabels.ivRank
tickerDetail.kvLabels.ivPercentile
tickerDetail.kvLabels.spot
tickerDetail.kvLabels.historyDays
```

The existing per-locale resource inventory node evolves in place at both
checkpoints. Key parity, non-empty leaves, scanner arithmetic, and global
`src/**` scope do not change.

## 4. File Ownership Map

### 4.1 Tranche 1 modify set

```text
src/service/data_scheduler.py
src/api/routes/schedule.py
src/daily_update.py
src/prices_runtime.py
tests/test_data_scheduler.py
tests/test_scheduler_state.py
tests/test_daily_update_wrapper.py
tests/test_prices_runtime.py
tests/test_market_data_direct.py
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/settingsBackendCopy.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/settings/settingsBackendCopy.test.ts
apps/arkscope-web/src/dataSourceSchedulePolling.test.ts
apps/arkscope-web/src/dataSourcesPresentation.test.ts
apps/arkscope-web/src/marketDataDisplay.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
```

`src/market_data_direct.py` may receive only a comment/import cleanup if the
retired scheduler identity is referenced there. Its direct price primitive is
otherwise byte-protected.

### 4.2 Tranche 2 remove set

```text
src/api/routes/scan.py
scripts/analysis/compare_bs_vs_american.py
scripts/analysis/scan_option_mispricing.py
```

Removing these two scripts is a scoped exception required by old-store
retirement. No new script is created to replace them, and no unrelated script
is edited or retired.

### 4.3 Tranche 2 modify/create set

```text
src/api/app.py
src/api/routes/options.py
src/api/routes/market_data.py
src/api/routes/health.py
src/service/provider_health.py
src/market_data_admin.py
src/market_data_direct.py
src/evidence_packet.py
src/smoke/pg_unreachable_e2e.py
src/tools/backends/__init__.py
src/tools/backends/db_backend.py
src/tools/backends/file_backend.py
src/tools/backends/local_market_backend.py
src/tools/backends/sqlite_backend.py
src/tools/data_access.py
src/tools/data_coverage_tools.py
src/tools/freshness.py
src/tools/options_tools.py
src/tools/schemas.py
src/tools/registry.py
src/tools/analysis_tools.py
src/agents/openai_agent/tools.py
src/agents/anthropic_agent/tools.py
src/agents/shared/compressor/__init__.py
src/agents/shared/compressor/reducers.py
src/agents/shared/subagent.py
sql/001_init_schema.sql
scripts/migration/retire_legacy_scheduler_iv.py
tests/test_legacy_scheduler_iv_retirement.py
tests/test_legacy_iv_retirement_boundaries.py
tests/test_api.py
tests/test_data_access.py
tests/test_db_backend.py
tests/test_sqlite_backend.py
tests/test_market_data_admin.py
tests/test_tools.py
tests/test_agents.py
tests/test_compressor_reducers.py
tests/test_evidence_packet.py
tests/test_freshness.py
tests/test_data_coverage_tools.py
tests/test_provider_health.py
tests/test_pg_unreachable_e2e.py
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/TickerDetail.tsx
apps/arkscope-web/src/settings/DataStorageSection.tsx
apps/arkscope-web/src/explore/explorePresentation.ts
apps/arkscope-web/src/marketDataDisplay.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/i18n/resources/en/explore.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts
apps/arkscope-web/src/TickerDetail.test.tsx
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/explore/explorePresentation.test.tsx
apps/arkscope-web/src/marketDataDisplay.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
```

The migration script is a reviewed migration-namespace owner. It does not
reverse the broader decision to retire ad hoc operational scripts.

### 4.4 Protected files and behavior

```text
src/options_math/**
tests/test_option_pricing.py
tests/test_option_chain_tools.py
tests/test_iv_skew_tools.py
scripts/migration/n9_* and tests/test_n9_batch1_pg_drop.py
all current news/price/fundamentals payload rows
all job_runs rows
Coverage v2 classifier/session/calendar behavior
```

The current Settings provider-client domain key `iv` remains because live
option work may use it. Historical N9 evidence may contain old names and stays
byte-identical.

## 5. Stop Conditions

Stop and amend before proceeding if any of these occurs:

1. Task 0 node/resource/tool/no-PG baselines differ without an explained
   docs-only change.
2. A current non-test caller still depends on a retired scheduler identity.
3. The four Parquet files and 24 SQLite rows are not exact value multisets.
4. A retained live/pure option capability imports the old DAL/table/path.
5. `iv_history` has an unknown trigger, view, foreign key, schema, or active
   runtime dependency.
6. Retirement requires any `job_runs` mutation.
7. Retirement requires deleting prices/news/fundamentals/financial-cache rows
   or inferring which rows `local_incremental` once wrote.
8. Any implementation or test contacts PG, Gateway, or a provider.
9. A future IV provider/schema decision is needed.
10. A resource deletion falls outside the exact 8/2/22 ledgers.
11. Tool counts change by anything other than the three named removals.
12. A Tranche 2 edit changes a frozen Tranche 1 product owner without a
    reviewed correction.
13. Production changes between preview and apply.

## 6. Task Sequence

### Task 0: Establish The Isolated Base And Clearance Ledger

**Files:**
- Create: `docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md`
- Modify: this plan only if independently reviewed accounting requires a
  docs-only correction

- [x] **Step 1: Create an isolated worktree and branch.**

Use `superpowers:using-git-worktrees`. Start from exact base:

```bash
git rev-parse HEAD
# expected Task 0 authorization tip:
# 0bdd526112f7975ecf13064a96e2e8672fa16667
git merge-base --is-ancestor \
  7bb7cc29f70ca899a5b598f2322ce181daa17ebe HEAD
# expected: exit 0; 7bb7cc29 remains the behavioral A/B base
git status --short
# expected: no output
```

Do not copy `data/`, `config/.env`, browser profiles, or production database
files into the worktree.

- [x] **Step 2: Reproduce full and focused node lists.**

Run the recipes in Sections 3.1 and 3.2. Store normalized lists and SHA-256 in
the evidence file. Expected exact collections are `4749`, `663`, `1072`, and
`139` with the hashes stated above.

- [x] **Step 3: Reproduce non-node baselines.**

Run:

```bash
cd apps/arkscope-web
npm test -- --run src/i18n/resources.test.ts \
  src/i18n/visibleLiteralScanner.test.ts \
  src/i18n/foundationBoundaries.test.ts

cd ../../
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_tools.py::TestRegistry::test_register_all \
  tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
  tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count

/home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
from src.smoke.pg_unreachable_e2e import REQUIRED_CHECKS
from src.tools.registry import create_default_registry

central = set(create_default_registry().list_names())
assert len(central) == 56
for name in ("get_iv_analysis", "get_iv_history_data", "scan_mispricing"):
    assert name in central
for name in ("calculate_greeks", "get_option_chain", "get_iv_skew_analysis"):
    assert name in central
assert len(REQUIRED_CHECKS) == 24
PY
```

Expected resources are Settings `714`, Explore `401`, total `1814`, scanner
`36/20/0/20`, tool counts `56/57/57`, and no-PG inventory `24`.

- [x] **Step 4: Capture a read-only production-shaped observation.**

Use SQLite URI `mode=ro`; do not use the migration script yet. Record paths,
sizes, mtimes, integrity/FK state, and:

```text
iv_history rows: 24
tickers: 4
min(id): 1
max(id): 248
IDs are non-contiguous
Parquet files: AMD/NVDA/PLTR/PYPL, exact SQLite value multisets
job_runs: collect.local_incremental=1350, collect.price_backfill=2,
          collect.iv_history=0
```

These numbers are dated observations, not acceptance constants. Any changed
shape is handled by the stop conditions.

- [x] **Step 5: Create and commit the clearance evidence.**

The evidence header must say `IMPLEMENTATION IN PROGRESS - NO PRODUCTION
WRITE`, include both normalized node lists/hashes, and distinguish environment
failure observations from acceptance invariants.

```bash
git add docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md
git commit -m "docs: record legacy retirement implementation baseline"
```

### Task 1: Write Tranche 1 RED Contracts

**Files:**
- Modify: `tests/test_data_scheduler.py`
- Modify: `tests/test_daily_update_wrapper.py`
- Modify: `tests/test_prices_runtime.py`
- Modify: `tests/test_scheduler_state.py`
- Modify: `tests/test_market_data_direct.py`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.test.ts`
- Modify: `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts`
- Modify: `apps/arkscope-web/src/dataSourcesPresentation.test.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

- [x] **Step 1: Replace retired behavior tests with exact four-source contracts.**

The central assertion shape is:

```python
ACTIVE_SOURCE_IDS = {
    "polygon_news",
    "finnhub_news",
    "ibkr_news",
    "ibkr_prices",
}
RETIRED_SOURCE_IDS = {"price_backfill", "local_incremental", "iv_history"}

def test_scheduler_source_defs_have_no_legacy_collector_plumbing():
    assert set(ds.SOURCES) == ACTIVE_SOURCE_IDS
    for source_def in ds.SOURCES.values():
        assert not hasattr(source_def, "sync_flag")
        assert not hasattr(source_def, "coverage_repair_disabled")
```

Evolve the existing catalog/status assertions in place. Delete the 19 retired
nodes and apply the two exact renames in Section 3.4.

- [x] **Step 2: Add the additive NewsWriteMode classifier tests.**

Use the real current enum members and a foreign enum value/object to prove
future values do not fall through:

```python
def test_news_write_mode_classifier_is_exhaustive_for_current_modes():
    assert {
        mode: ds._classify_news_write_mode(mode)
        for mode in routing.NewsWriteMode
    } == {
        routing.NewsWriteMode.NORMALIZED: "direct_local",
        routing.NewsWriteMode.LEGACY_LOCAL: "direct_local",
        routing.NewsWriteMode.LEGACY_PG: "reject",
        routing.NewsWriteMode.BLOCKED: "reject",
    }

def test_unknown_news_write_mode_fails_before_provider_adapter_worker_and_telemetry(
    monkeypatch,
):
    # Patch every downstream seam to raise AssertionError if reached.
    # Inject a route whose mode is not one of the four reviewed enum members.
    result = ds.run_source("polygon_news", trigger_source="manual")
    assert result["status"] == "failed"
    assert result["code"] == "unsupported_news_write_mode"
    assert result["reason_code"] == "unsupported_news_write_mode"
    assert "ok" not in result
```

The second test must patch provider config, adapter, worker subprocess, DB
write, source locks, and job telemetry. It must fail RED because current code
falls through or reaches a patched seam, not because fixture setup is invalid.

- [x] **Step 3: Make the prices-worker argv contract consume the real parser.**

Evolve `test_p0c1_ibkr_prices_runs_prices_worker_subprocess`:

```python
captured: list[str] = []

def fake_worker(argv: list[str]) -> dict[str, object]:
    captured[:] = argv
    parsed = prices_runtime.parse_args(argv[3:])
    assert parsed.provider == "ibkr"
    assert parsed.tickers == "AAPL,MSFT"
    assert "--source" not in argv
    return {"ok": True, "written": 0}
```

This is the required real-shape parser/argv seam. Rename the parser test as
specified in Section 3.4 and require ticker/provider arguments without source.

- [x] **Step 4: Make CLI and mounted frontend tests assert absence.**

The daily parser must reject `--iv-history` and `--sync-db`; `--all` must still
select current news/prices collectors. Mounted Settings must render exactly
four active rows, four toggles/run controls, and no retired ID/copy/control
mode. Resource tests must expect Settings `706` and total `1806` after product
implementation.

- [x] **Step 5: Run the RED set.**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_data_scheduler.py \
  tests/test_scheduler_state.py \
  tests/test_daily_update_wrapper.py \
  tests/test_prices_runtime.py \
  tests/test_market_data_direct.py

cd apps/arkscope-web
npm test -- --run \
  src/SettingsProviderConfig.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/marketDataDisplay.test.ts \
  src/i18n/resources.test.ts
```

Expected: RED only on removed catalog/CLI/control/resource contracts and the
new unknown-mode boundary. A parser fixture error or unrelated failure is the
wrong RED and must be fixed before product edits.

- [x] **Step 6: Commit the RED contracts.**

```bash
git add tests/test_data_scheduler.py tests/test_scheduler_state.py \
  tests/test_daily_update_wrapper.py tests/test_prices_runtime.py \
  tests/test_market_data_direct.py \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts \
  apps/arkscope-web/src/settings/settingsBackendCopy.test.ts \
  apps/arkscope-web/src/dataSourceSchedulePolling.test.ts \
  apps/arkscope-web/src/dataSourcesPresentation.test.ts \
  apps/arkscope-web/src/marketDataDisplay.test.ts \
  apps/arkscope-web/src/i18n/resources.test.ts
git commit -m "test: define active scheduler retirement contract"
```

### Task 2: Implement Tranche 1 Scheduler And CLI Retirement

**Files:**
- Modify: `src/service/data_scheduler.py`
- Modify: `src/api/routes/schedule.py`
- Modify: `src/daily_update.py`
- Modify: `src/prices_runtime.py`
- Byte gate: `src/market_data_direct.py`

- [x] **Step 1: Reduce `SourceDef` and `SOURCES`.**

Remove the three dead definitions and fields used only by them. The surviving
shape must be equivalent to:

```python
@dataclass(frozen=True)
class SourceDef:
    name: str
    label: str
    default_interval_min: int = 60
    ibkr: bool = False
    needs_price_scope: bool = False
    description: str = ""
    universe_tickers: bool = False
    adapter: Optional[tuple] = None
    prices_worker: bool = False
    writes_market_db: bool = False
    news_direct_source: Optional[str] = None
    source_mode: str = "provider_fetch"
    write_target: str = "market_data.db"
    source_badges: tuple[str, ...] = ()
```

Keep this exact surviving field set; field order may preserve the existing
dataclass's required-before-default ordering. Remove `_N9_RETIRED_SOURCES`, `ScheduleControlMode`,
`source_control_mode`, coverage no-op helpers, `_local_refresh`, and
source-specific operational branches only after their callers are gone.

- [x] **Step 2: Add the exhaustive pre-provider classifier.**

Implement explicit identity branches, not enum membership:

```python
NewsExecutionMode = Literal["direct_local", "reject"]

class UnsupportedNewsWriteMode(RuntimeError):
    pass

def _classify_news_write_mode(mode: object) -> NewsExecutionMode:
    if mode is NewsWriteMode.NORMALIZED:
        return "direct_local"
    if mode is NewsWriteMode.LEGACY_LOCAL:
        return "direct_local"
    if mode is NewsWriteMode.LEGACY_PG:
        return "reject"
    if mode is NewsWriteMode.BLOCKED:
        return "reject"
    raise UnsupportedNewsWriteMode("unsupported_news_write_mode")
```

Call it immediately after reading the news route and before provider config,
locks, adapter/worker construction, write permission, or `_record_result`.
Catch `UnsupportedNewsWriteMode` at that boundary and return the fixed envelope
`{"source": source, "status": "failed", "code":
"unsupported_news_write_mode", "reason_code":
"unsupported_news_write_mode"}` without an `ok` field or durable telemetry.
Keep direct-local routing behavior for the two accepted modes. Do not retain a
post-collect `sync_flag` guard.

- [x] **Step 3: Collapse route/status behavior to active rows.**

`GET /schedule` projects only the four catalog entries. Mutation and run-now
routes use ordinary source membership; the three old IDs are indistinguishable
from other unknown IDs and return typed 404 before `require_db_write()` and
before provider readiness checks.

- [x] **Step 4: Remove daily mirror flags and source selector.**

Delete `--iv-history` and `--sync-db` parsing/dispatch. Remove `skip_sync` from
`run_source()` and callers. Remove `--source` from `prices_runtime.parse_args`,
the scheduler argv, and `_run_worker` parameters. Preserve `--tickers`,
`--provider`, and Gateway lock semantics.

- [x] **Step 5: Run Tranche 1 backend tests and mutation probes.**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_data_scheduler.py \
  tests/test_scheduler_state.py \
  tests/test_daily_update_wrapper.py \
  tests/test_prices_runtime.py \
  tests/test_market_data_direct.py
```

Then temporarily remove each explicit classifier branch one at a time. Its
corresponding current-mode test must fail. Add a fifth enum member in a copied
fixture or substitute the unknown object; the downstream-seam test must fail
if the classifier is changed to permissive fallthrough. Restore source bytes
and rerun GREEN.

- [x] **Step 6: Commit backend Tranche 1.**

```bash
git add src/service/data_scheduler.py src/api/routes/schedule.py \
  src/daily_update.py src/prices_runtime.py src/market_data_direct.py
git commit -m "refactor: retire legacy scheduler source identities"
```

### Task 3: Implement Tranche 1 Settings And Resource Retirement

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`

- [x] **Step 1: Remove dead DTO and presenter branches.**

Delete `ScheduleControlMode`, `control_mode`, retired reason, and read-only
presentation branches. Keep the generic unknown source-label fallback, but no
literal branch for any of the three retired IDs.

- [x] **Step 2: Render every returned row as an active schedule row.**

Remove read-only/retired chips and conditional control suppression. Preserve
the current toggle, interval, run, busy, and error behavior for the four real
rows.

- [x] **Step 3: Delete the exact eight resource leaves.**

Delete only the eight paths in Section 3.7 from both locale bundles. Do not
rewrite unrelated copy.

- [x] **Step 4: Run focused frontend and resource gates.**

```bash
cd apps/arkscope-web
npm test -- --run \
  src/SettingsProviderConfig.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/marketDataDisplay.test.ts \
  src/i18n/resources.test.ts
npm run typecheck
npm run build
```

Expected Settings `706`, Explore `401`, total `1806`, parity zero, empty leaves
zero, and exactly four mounted rows in both locales.

- [x] **Step 5: Commit frontend Tranche 1.**

```bash
git add apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/settings/DataSourcesSection.tsx \
  apps/arkscope-web/src/settings/settingsBackendCopy.ts \
  apps/arkscope-web/src/i18n/resources/en/settings.ts \
  apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
git commit -m "feat: expose only active schedule controls"
```

### Task 4: Freeze And Review `TRANCHE_1_TIP`

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md`

- [x] **Step 1: Recompute the exact Tranche 1 ledger.**

Expected:

```text
backend full:    4749 -> 4731, +6/-24
backend focused:  663 -> 645
frontend full:   1072 -> 1072, +3/-3
frontend focused: 139 -> 139
resources: Settings 706 / Explore 401 / total 1806
tools: 56 / 57 / 57
no-PG: 24
scanner: 36/20/0/20
```

List the two additive classifier IDs separately from all retirements and
renames.

- [x] **Step 2: Run full equivalent-environment A/B gates.**

Run backend/full frontend, typecheck, build, scanner twice, resources, no-PG,
and retained price/news tests. Compare normalized non-passing node sets rather
than absolute environment failure counts.

- [x] **Step 3: Verify removed concepts mechanically.**

```bash
rg -n 'price_backfill|local_incremental|iv_history|ScheduleControlMode|source_control_mode|skip_sync|sync_flag|_local_refresh' \
  src/service/data_scheduler.py src/api/routes/schedule.py src/daily_update.py \
  src/prices_runtime.py apps/arkscope-web/src/settings apps/arkscope-web/src/api.ts
```

Expected: no retired scheduler/control implementation. Historical docs/tests
outside the active-owner set are not blanket-deleted.

- [x] **Step 4: Record and commit the named checkpoint.**

```bash
git add docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md
git commit -m "docs: record scheduler retirement tranche checkpoint"
TRANCHE_1_TIP=$(git rev-parse HEAD)
test "$(printf %s "$TRANCHE_1_TIP" | wc -c)" -eq 40
printf 'TRANCHE_1_TIP=%s\n' "$TRANCHE_1_TIP"
```

Write the full 40-character hash into evidence. Tranche 2 may start only after
an independent checkpoint read confirms the node/resource arithmetic.

### Task 5: Write Tranche 2 Runtime And Boundary RED Contracts

**Files:**
- Create: `tests/test_legacy_iv_retirement_boundaries.py`
- Modify: all Tranche 2 existing test owners listed in Sections 3.6 and 4.3

- [x] **Step 1: Replace old API contracts with absence plus retained Greeks.**

```python
def test_retired_market_admin_and_iv_routes_are_absent_while_greeks_remains_reachable(
    client,
):
    paths = client.app.openapi()["paths"]
    assert "/options/{ticker}" not in paths
    assert "/options/{ticker}/history" not in paths
    assert "/scan/mispricing" not in paths
    assert "/market-data/jobs/{job_id}" not in paths
    assert "/options/greeks/calculate" in paths
    assert client.get(
        "/options/greeks/calculate",
        params={"S": 100, "K": 100, "T": 0.25, "sigma": 0.2},
    ).status_code == 200
```

Use the actual Greeks method/query contract from the current test fixture; do
not weaken it to route registration alone.

- [x] **Step 2: Add runtime boundary tests.**

The new boundary file must parse/import current owners and assert exact old
storage/API symbols are absent while retained option owners remain:

```python
LEGACY_RUNTIME_TOKENS = {
    "query_iv_history",
    "get_iv_history",
    "get_iv_history_df",
    "IVAnalysisResult",
    "IVHistoryPoint",
    'data_type == "iv_history"',
}
```

Do not reject generic variable names such as `iv_history` inside pure math or
historical N9 migration evidence.
`test_non_migration_scripts_do_not_read_legacy_iv_store` scans all current
scripts except the reviewed migration namespace and must prove both analysis
scripts are gone. The same boundary suite reads the three job-poller owners and
asserts that `_JOBS`, `_JOBS_LOCK`, `start_bootstrap_job`, `start_update_job`,
`get_job`, `MarketDataJob`, `getMarketDataJob`, and
`/market-data/jobs/` are absent from their exact former files; it does not ban
generic `get_job` names elsewhere in the application.

- [x] **Step 3: Evolve tool, bridge, health, evidence, and reducer contracts.**

Name-set tests must assert:

```python
retired = {"get_iv_analysis", "get_iv_history_data", "scan_mispricing"}
retained = {"calculate_greeks", "get_option_chain", "get_iv_skew_analysis"}
assert retired.isdisjoint(tool_names)
assert retained <= tool_names
assert len(central_tools) == 53
assert len(openai_tools) == 54
assert len(anthropic_tools) == 54
```

Evidence tests assert no `iv_environment` and no missing/error entry invented
for retired IV. Provider health/freshness/data coverage tests must preserve
their existing non-IV facts and stop querying the old store.

- [x] **Step 4: Evolve frontend RED contracts.**

Ticker Detail must make no old IV request, render no old IV section/column, and
preserve surviving price/fundamentals results when another surviving leg
fails. Settings Data Storage must omit the old IV row. Both locales remain
covered. Resource inventory expects final `704/379/1782` only after code lands.

- [x] **Step 5: Evolve no-PG inventory.**

Remove exactly the IV-history CheckSpec and direct dispatch. Assert inventory
23 and every remaining check name/path unchanged.

- [x] **Step 6: Run RED tests.**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_api.py tests/test_data_access.py tests/test_db_backend.py \
  tests/test_sqlite_backend.py tests/test_market_data_admin.py \
  tests/test_tools.py tests/test_agents.py tests/test_compressor_reducers.py \
  tests/test_evidence_packet.py tests/test_freshness.py \
  tests/test_data_coverage_tools.py tests/test_provider_health.py \
  tests/test_pg_unreachable_e2e.py \
  tests/test_legacy_iv_retirement_boundaries.py

cd apps/arkscope-web
npm test -- --run src/TickerDetail.test.tsx \
  src/SettingsPostPgExitStorage.test.ts \
  src/explore/explorePresentation.test.tsx \
  src/marketDataDisplay.test.ts src/i18n/resources.test.ts
```

Expected: RED on active old owners/counts/routes/resources. Retained Greeks,
option-chain, IV-skew, and pure option-pricing tests must remain GREEN.

- [x] **Step 7: Commit Tranche 2 RED contracts.**

```bash
git add tests apps/arkscope-web/src
git commit -m "test: define legacy IV domain retirement contract"
```

### Task 6: Remove The Legacy IV Runtime Domain

**Files:**
- Remove/modify the Tranche 2 runtime owners in Sections 4.2 and 4.3

- [x] **Step 1: Remove storage and DAL ownership.**

Delete old schema/protocol/backend methods and SQL initialization. Preserve
all non-IV backend methods and historical N9 migrations. Remove
`market_sync_meta` IV handling only from current runtime owners; production row
deletion remains Task 9/post-merge.

- [x] **Step 2: Remove API/DTO/status ownership.**

Delete the two old options routes and the sole scan router/module. Remove the
scan router include from `src/api/app.py`. Keep the Greeks route and actual
calculation assertions. Remove old IV members from market status, health, and
coverage DTOs atomically. Also remove
`GET /market-data/jobs/{job_id}` and its `get_job`/`start_bootstrap_job`
imports from `src/api/routes/market_data.py`; all routes that once created such
jobs are permanent 409 tombstones.

- [x] **Step 3: Remove tool, bridge, evidence, and health ownership.**

Delete exactly the three old tools from central/OpenAI/Anthropic registries and
dispatch. Delete the dedicated history reducer. Remove `iv_environment`,
`ARKSCOPE_OVERVIEW_INCLUDE_IV`, `latest_iv`, and `latest_vrp`. Keep live chain,
skew, Greeks, and generic volatility/math helpers.

- [x] **Step 4: Remove the shared PG mirror implementation.**

Delete current bootstrap/update/validate mirror endpoints and implementation
that only serve retired PG domains. Keep current direct-local market coverage
and active data paths. Remove the 40 exact obsolete test nodes listed in
Section 3.6; if any listed node still proves a live direct-local property, stop
instead of deleting it. Delete `_JOBS`, `_JOBS_LOCK`, `start_bootstrap_job`,
`start_update_job`, and `get_job` as one unreachable product subsystem; delete
the test-only `_drain_update_job` helper with its owning nodes. Those seven
nodes are already among the reviewed 40:

```text
test_bootstrap_job_records_retired_pg_mirror_error
test_update_job_surfaces_iv_or_fundamentals_failure
test_update_job_all_domains_fail_is_error
test_update_job_passes_explicit_domains_to_incremental_update
test_update_job_ignores_skipped_domains_when_deciding_success
test_job_not_found_404
test_bootstrap_done_poll_invalidates_dal_cache
```

- [x] **Step 5: Remove the two old-store analysis scripts.**

```bash
git rm scripts/analysis/compare_bs_vs_american.py \
  scripts/analysis/scan_option_mispricing.py
```

Do not replace them, edit unrelated scripts, or claim broader scripts
retirement complete.

- [x] **Step 6: Run backend and protected-capability tests.**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_api.py tests/test_data_access.py tests/test_db_backend.py \
  tests/test_sqlite_backend.py tests/test_market_data_admin.py \
  tests/test_tools.py tests/test_agents.py tests/test_compressor_reducers.py \
  tests/test_evidence_packet.py tests/test_freshness.py \
  tests/test_data_coverage_tools.py tests/test_provider_health.py \
  tests/test_pg_unreachable_e2e.py \
  tests/test_legacy_iv_retirement_boundaries.py \
  tests/test_option_pricing.py tests/test_option_chain_tools.py \
  tests/test_iv_skew_tools.py
```

Expected: GREEN, tool counts `53/54/54`, no-PG `23`, and no old runtime owner.

- [x] **Step 7: Commit backend Tranche 2.**

```bash
git add src sql scripts/analysis tests
git commit -m "refactor: retire legacy IV runtime domain"
```

### Task 7: Remove Legacy IV Frontend And Resource Surfaces

**Files:**
- Modify the Tranche 2 frontend owners in Section 4.3

- [x] **Step 1: Remove frontend DTOs and requests.**

Delete `IVAnalysis`, `IVHistoryPoint`, `IVHistoryResult`, old request helpers,
`MarketDataStatus.iv`, sync IV, and ticker-coverage IV members. Do not alter
live option-chain/Greeks DTOs. Delete the unconsumed `MarketDataJob` interface
and `getMarketDataJob()` helper with `/market-data/jobs/{job_id}`; do not add a
replacement poller.

- [x] **Step 2: Simplify Ticker Detail and Data Storage.**

Remove old request effects and IV UI sections. Preserve independent surviving
request results/errors and reflow the Data tab without an empty shell. Remove
only the old IV storage row/status phrase from Settings.

- [x] **Step 3: Remove exact resource leaves.**

Delete the 2 Settings and 22 Explore leaves from Section 3.7 in both locales.
Rewrite the three existing Settings leaves authorized by the spec without
changing their count:

```text
registry.sections.dataStorage.description
registry.sections.dataStorage.searchAliases
dataStorage.update.succeeded
```

- [x] **Step 4: Run frontend tests and visual contracts.**

```bash
cd apps/arkscope-web
npm test -- --run src/TickerDetail.test.tsx \
  src/SettingsPostPgExitStorage.test.ts \
  src/explore/explorePresentation.test.tsx \
  src/marketDataDisplay.test.ts src/i18n/resources.test.ts
npm run typecheck
npm run build
```

Expected resources: Settings `704`, Explore `379`, total `1782`; parity zero;
empty leaves zero; frontend collection still 1072/139.

- [x] **Step 5: Commit frontend Tranche 2.**

```bash
git add apps/arkscope-web/src
git commit -m "feat: remove legacy IV product surfaces"
```

### Task 8: Build The Audited Retirement Migration RED-First

**Files:**
- Create: `scripts/migration/retire_legacy_scheduler_iv.py`
- Create: `tests/test_legacy_scheduler_iv_retirement.py`

- [x] **Step 1: Write all 16 planned migration tests before the tool.**

Build synthetic profile/market DBs and four small Parquet fixtures matching the
reviewed schema. Include unrelated tables/rows and target `job_runs`. The five
required lifecycle operations have distinct mutation-sensitive tests:

```text
preview       -> read-only, deterministic, exact classification
archive       -> complete 0600 artifacts under a 0700 directory
apply         -> exact target removal, non-target/job_runs preservation
idempotence   -> second apply byte/row stable and already_applied=true
restore       -> exact round trip and refusal on nonempty/different targets
```

Each test must fail for its own missing phase, not because the module cannot be
imported. Start with a minimal module exposing the planned names and raising a
phase-specific `NotImplementedError` so all REDs are attributable.

- [x] **Step 2: Define structured types and CLI.**

Use these dataclasses for the public migration boundary:

```python
@dataclass(frozen=True)
class RetirementPaths:
    profile_db: Path
    market_db: Path
    iv_parquet_dir: Path
    backup_root: Path

@dataclass(frozen=True)
class PreviewReport:
    preview_sha256: str
    pre_retirement_commit: str
    profile_targets: Mapping[str, object]
    market_targets: Mapping[str, object]
    parquet_targets: tuple[Mapping[str, object], ...]
    preserved_job_runs_sha256: str
    non_target_digests: Mapping[str, str]
```

CLI modes are `preview`, `apply`, and `restore`. `apply` requires an exact
reviewed preview SHA and pre-retirement commit. `restore` requires an archive
manifest and exact old code commit. The exact CLI options are:

```text
preview --profile-db PATH --market-db PATH --iv-parquet-dir PATH
        --backup-root PATH --output PATH
apply   --profile-db PATH --market-db PATH --iv-parquet-dir PATH
        --backup-root PATH --expected-preview-sha256 SHA256
        --expected-pre-retirement-commit COMMIT --output PATH
restore --archive-dir PATH --profile-db PATH --market-db PATH
        --iv-parquet-dir PATH --repo-root PATH
        --expected-current-commit COMMIT --output PATH
```

- [x] **Step 3: Implement read-only preview.**

Open both DBs with `path.resolve().as_uri() + "?mode=ro"`. Inspect exact table/index SQL plus
`sqlite_master` trigger/view references. Record integrity/FK, sizes/mtimes,
target and non-target logical digests, operational rows, preferences, sync
metadata, and target job history. Compare SQLite and Parquet using normalized
value tuples, not just row counts.

Preview performs no mkdir/write and contacts no provider, PG, or Gateway.

- [x] **Step 4: Implement archive creation and verification.**

Create:

```text
data/backups/legacy_scheduler_iv_retirement_YYYYMMDDTHHMMSSZ/
  manifest.json
  legacy_iv.sqlite3
  profile_state.json
  market_sync_state.json
  parquet/AMD.parquet
  parquet/NVDA.parquet
  parquet/PLTR.parquet
  parquet/PYPL.parquet
  RESTORE.txt
```

Directory mode is 0700; every file is 0600. The mini DB contains exact table,
index, and rows. Manifest artifact hashes are verified before apply can start.
Use atomic temp-file replacement plus fsync for manifest state.

- [x] **Step 5: Implement resumable apply.**

Manifest phases are:

```text
archived -> profile_applied -> market_applied -> files_applied -> complete
```

Profile transaction removes only the three exact scheduler state IDs and
matching `schedule.<id>.%` keys. Market transaction removes only
`market_sync_meta.domain='iv'` and drops the reviewed table/index. Parquet files
are removed only after archive verification. Re-read source mtime/digests
between preview, archive, and each owner; drift aborts.

- [x] **Step 6: Implement idempotence and restore.**

Second apply verifies the same archive/non-target/job history and returns
`already_applied=true`. Restore refuses a present nonempty or differently
shaped target. Under exact old commit, it restores table/index/rows/files/state
and verifies archive hashes plus integrity/FK.

- [x] **Step 7: Run tests and mutation probes.**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_legacy_scheduler_iv_retirement.py
```

Mutation requirements:

1. allow preview writes -> read-only test RED;
2. omit one archive artifact/hash -> archive test RED;
3. delete/update `job_runs` -> preserve test RED;
4. skip one phase checkpoint -> resume test RED;
5. make second apply rewrite manifest/data -> idempotence test RED;
6. allow restore over a nonempty target -> restore-refusal test RED.

Restore product bytes after each mutation and rerun the full migration suite
GREEN. Copied-production proof added one reviewed, RED-first memory-bound node,
so the final suite contains 17 tests without changing migration semantics.

- [x] **Step 8: Commit the migration tool.**

```bash
git add scripts/migration/retire_legacy_scheduler_iv.py \
  tests/test_legacy_scheduler_iv_retirement.py
git commit -m "feat: add audited legacy IV retirement migration"
```

### Task 9: Run Copied-Data Proof, Visual Gates, And Documentation Closeout

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md`
- Modify: current-state sections in the design documents listed below

- [x] **Step 1: Prove migration on copies, never production.**

Use SQLite online backups or byte copies made while no copied test process is
writing. Copy the four Parquets into a temporary fixture root. Set concrete
paths, then run the exact CLI:

```bash
PROOF_ROOT=$(mktemp -d)
IMPLEMENTATION_ROOT=$(pwd)
PRODUCTION_ROOT=/mnt/md0/PycharmProjects/ArkScope
PROFILE_DB="$PROOF_ROOT/profile_state.db"
MARKET_DB="$PROOF_ROOT/market_data.db"
IV_DIR="$PROOF_ROOT/iv_history"
BACKUP_ROOT="$PROOF_ROOT/backups"
OLD_CODE_ROOT="$PROOF_ROOT/pre-retirement-code"
PREVIEW_JSON="$PROOF_ROOT/preview.json"
APPLY_JSON="$PROOF_ROOT/apply.json"
SECOND_APPLY_JSON="$PROOF_ROOT/second-apply.json"
RESTORE_JSON="$PROOF_ROOT/restore.json"

mkdir -p "$IV_DIR" "$BACKUP_ROOT"
/home/hyl/.virtualenvs/llm_app/bin/python - \
  "$PRODUCTION_ROOT/data/profile_state.db" "$PROFILE_DB" \
  "$PRODUCTION_ROOT/data/market_data.db" "$MARKET_DB" <<'PY'
import sqlite3
import sys
from pathlib import Path

for source_arg, target_arg in zip(sys.argv[1::2], sys.argv[2::2]):
    source = Path(source_arg).resolve()
    target = Path(target_arg).resolve()
    with sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)
PY
cp "$PRODUCTION_ROOT"/data/options/iv_history/*.parquet "$IV_DIR"/

/home/hyl/.virtualenvs/llm_app/bin/python \
  scripts/migration/retire_legacy_scheduler_iv.py preview \
  --profile-db "$PROFILE_DB" --market-db "$MARKET_DB" \
  --iv-parquet-dir "$IV_DIR" --backup-root "$BACKUP_ROOT" \
  --output "$PREVIEW_JSON"

PREVIEW_SHA=$(/home/hyl/.virtualenvs/llm_app/bin/python -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["preview_sha256"])' \
  "$PREVIEW_JSON")

/home/hyl/.virtualenvs/llm_app/bin/python \
  scripts/migration/retire_legacy_scheduler_iv.py apply \
  --profile-db "$PROFILE_DB" --market-db "$MARKET_DB" \
  --iv-parquet-dir "$IV_DIR" --backup-root "$BACKUP_ROOT" \
  --expected-preview-sha256 "$PREVIEW_SHA" \
  --expected-pre-retirement-commit \
  7bb7cc29f70ca899a5b598f2322ce181daa17ebe \
  --output "$APPLY_JSON"

/home/hyl/.virtualenvs/llm_app/bin/python \
  scripts/migration/retire_legacy_scheduler_iv.py apply \
  --profile-db "$PROFILE_DB" --market-db "$MARKET_DB" \
  --iv-parquet-dir "$IV_DIR" --backup-root "$BACKUP_ROOT" \
  --expected-preview-sha256 "$PREVIEW_SHA" \
  --expected-pre-retirement-commit \
  7bb7cc29f70ca899a5b598f2322ce181daa17ebe \
  --output "$SECOND_APPLY_JSON"

ARCHIVE_DIR=$(/home/hyl/.virtualenvs/llm_app/bin/python -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["archive_dir"])' \
  "$APPLY_JSON")

git worktree add --detach "$OLD_CODE_ROOT" \
  7bb7cc29f70ca899a5b598f2322ce181daa17ebe

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$IMPLEMENTATION_ROOT/scripts/migration/retire_legacy_scheduler_iv.py" restore \
  --archive-dir "$ARCHIVE_DIR" --profile-db "$PROFILE_DB" \
  --market-db "$MARKET_DB" --iv-parquet-dir "$IV_DIR" \
  --repo-root "$OLD_CODE_ROOT" \
  --expected-current-commit \
  7bb7cc29f70ca899a5b598f2322ce181daa17ebe \
  --output "$RESTORE_JSON"

git worktree remove "$OLD_CODE_ROOT"
```

Record commands with paths redacted to repository-relative fixture roots,
manifest SHA, artifact hashes, row/digest comparisons, idempotent result, and
restore round trip. Do not place production secrets or arbitrary exception
text in evidence.

- [x] **Step 2: Run canonical final A/B accounting.**

Expected final:

```text
backend full 4691, base composition +29/-87
backend focused 605
frontend full 1072, base composition +4/-4
frontend focused 139
resources 704/379/1782
tools 53/54/54
no-PG 23
scanner 36/20/0/20 twice
```

The one-node backend deviation is
`test_logical_database_digest_is_memory_bounded`. The original digest
materialized an entire logical table and reached about 6 GiB RSS against the
production-shaped market database. The replacement is a length-framed,
streaming SHA-256 digest. This changes no product or migration result; it adds
one mutation-sensitive resource-bound contract.

Also compare base -> `TRANCHE_1_TIP` and `TRANCHE_1_TIP` -> final. Rerun the
Tranche 1 focused suites at final tip so Tranche 2 cannot hide a regression.

- [x] **Step 3: Run full technical gates.**

Run backend/full frontend, typecheck, build, resource/scanner gates, no-PG,
retained option suites, `git diff --check`, skip/only/todo census, and exact
byte gates for protected N9 and option-math owners. Compare normalized
non-passing sets against equivalent base runs.

- [x] **Step 4: Run bilingual visual/runtime gates.**

Use isolated API/Vite and copied/fake data. Verify Settings Data Sources,
Settings Data Storage, and Ticker Detail Data tab in `zh-Hant` and `en` at
1440, 960, and 390 px:

```text
exactly four schedule rows
no retired schedule identity/chip/control copy
no old IV row, request, heading, empty shell, or stale column
surviving price/fundamentals content and errors remain
no horizontal page overflow
locale switch preserves tab, focus, drafts, and reading position
```

No CSS change is expected. If real geometry proves one necessary, stop and use
the reviewed CSS-deviation protocol with a named RED test.

- [x] **Step 5: Update current documentation without rewriting history.**

Update current-state references in:

```text
docs/design/ARKSCOPE_TOOL_CATALOG.md
docs/data/DATA_SUBSCRIPTION_GUIDE.md
docs/data/OPTIONS_PRICING_THEORY.md
docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md
docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md
docs/design/PG_EXIT_REMAINDER_SCOPING.md
docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md
docs/design/PROJECT_PRIORITY_MAP.md
```

State that the old snapshot contract is retired while future provider-neutral
IV remains gated. Record that only two old-store-coupled scripts were removed;
the broader scripts retirement remains open. Preserve dated historical entries
that were true at their time.

- [x] **Step 6: Commit review-ready evidence and stop.**

```bash
git add docs
git commit -m "docs: record legacy scheduler and IV retirement evidence"
git status --short
```

Expected: clean worktree. Mark spec/plan/evidence
`IMPLEMENTED - INDEPENDENT REVIEW PENDING`, not LIVE. Do not merge, preview
production with the migration tool, archive production, or apply production
deletion yet.

## 7. Reviewer Focus

Independent implementation review must verify at least:

1. canonical base -> `TRANCHE_1_TIP` -> final ancestry and exact two-segment
   node/resource arithmetic;
2. the two NewsWriteMode additive nodes are real additions and mutation
   sensitive, not relabeled retirements;
3. all 19 retired Tranche 1 behavior nodes and all six spec-named evolved live
   contracts match actual code behavior;
4. scheduler-captured price argv parses through real `prices_runtime.parse_args`
   with no source selector;
5. old IDs fail before DB write, provider, worker, lock, and telemetry;
6. Tranche 2 removes exactly three tools and preserves exactly three named
   option capabilities;
7. the two removed analysis scripts have no surviving replacement/direct path,
   while unrelated scripts are untouched;
8. the dead market-data job poller is absent end to end while the separate
   durable `/jobs` and `job_runs` systems remain unchanged;
9. no-PG changes exactly 24 -> 23 through the named IV check/dispatch;
10. migration preview/archive/apply/idempotence/restore tests each fail under an
   independent mutation;
11. copied-data archive contains exact value-level SQLite/Parquet duplicates
    and restore material;
12. `job_runs` and all non-target logical digests are unchanged;
13. product resources change exactly `1814 -> 1806 -> 1782` with no scanner
    debt/allowlist change;
14. production remains byte/mtime unchanged throughout review; and
15. evidence distinguishes dated observations from acceptance invariants.

## 8. Post-Review Integration And Production Protocol

These steps are unauthorized until independent implementation review is GREEN.

1. Fast-forward merge only; rerun focused/full/scanner/resources/no-PG gates on
   the merged tree.
2. Keep ArkScope, sidecar, scheduler, desktop, and CLI writers stopped.
3. Run merged-code `preview` against production read-only.
4. Present exact fresh target rows/files, manifest input SHA, integrity/FK,
   non-target digests, and job-history digest to the user.
5. Obtain a second explicit approval for that exact preview.
6. Run archive, verify all artifact hashes/modes, then apply.
7. Run second apply, integrity/FK, non-target/job-history digests, absence
   checks, exact four-source schedule smoke, and retained option gates.
8. Restart ArkScope and run bilingual Settings/Ticker Detail smoke.
9. Only then mark spec/plan/evidence/priority map `LIVE COMPLETE`, recording
   archive path/digest and restore command.

The production archive remains rollback material only. Future IV code must not
import it automatically or reuse the retired semantic IDs.
