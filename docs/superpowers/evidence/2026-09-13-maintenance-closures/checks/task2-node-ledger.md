# C11 Backend Node Ledger

300 before, 329 after; 266 unchanged, 34 removed, 63 added.

## Removed and Replacement Owners

### `tests/test_data_coverage_tools.py::test_ticker_coverage_news_sync_follows_active_writer_only`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_data_coverage_tools.py::test_ticker_coverage_uses_current_news_sync_and_preserves_prices`

### `tests/test_data_scheduler.py::test_run_source_news_direct_when_use_local_news_on`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_data_scheduler.py::test_run_source_news_direct_when_normalized_writes_unset`

### `tests/test_market_data_admin.py::test_status_news_sync_follows_active_writer_only`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_market_data_admin.py::test_status_uses_current_news_sync_and_preserves_price_authority`

### `tests/test_news_normalized_routing.py::test_local_environment_value_overrides_profile_value`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_malformed_stored_exit_marker`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_malformed_current_normalized_setting`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-False-False-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-False-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-False-None-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-False-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-False-True-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-False-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-None-False-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-None-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-None-None-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-None-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-None-True-legacy_local]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-None-legacy_local]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-True-False-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-True-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-True-None-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-True-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[False-True-True-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[False-True-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-False-False-blocked]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-False-blocked]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-False-None-blocked]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-False-blocked]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-False-True-blocked]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-False-blocked]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-None-False-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-None-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-None-None-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-None-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-None-True-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-None-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-True-False-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-True-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-True-None-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-True-normalized]`

### `tests/test_news_normalized_routing.py::test_route_matrix[True-True-True-normalized]`

Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate.

- `tests/test_news_normalized_routing.py::test_route_matrix[True-True-normalized]`

### `tests/test_news_providers.py::test_use_local_news_default_on`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_providers.py::test_use_local_news_env_false_overrides_profile_true`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_providers.py::test_use_local_news_env_override_on`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_providers.py::test_use_local_news_env_true_overrides_profile_false`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_providers.py::test_use_local_news_profile_false_is_rollback`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_providers.py::test_use_local_news_profile_setting_on`

Retire rollback semantics; real stored/environment values are inert and helpers absent.

- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`

### `tests/test_news_settings_route.py::test_put_settings_persists_explicit_rollback`

Retire obsolete write endpoint; retain current permission/write-only-key contract.

- `tests/test_news_routing_cleanup.py::test_normalized_setter_denies_before_writing_and_preserves_old_key`
- `tests/test_news_routing_cleanup.py::test_normalized_setter_writes_only_current_key`
- `tests/test_news_routing_cleanup.py::test_obsolete_put_is_unmounted_and_returns_405_without_writing`

### `tests/test_news_settings_route.py::test_status_and_http_409_after_completed_audit_marker`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_news_settings_route.py::test_status_selects_direct_writer_when_normalized_writes_are_disabled`

### `tests/test_news_settings_route.py::test_status_reports_explicit_and_env_rollback`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_news_settings_route.py::test_status_reports_current_normalized_environment_override`

### `tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors[False-partial-2026-06-10T10:00:00+00:00]`
- `tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors[True-failed-2026-06-10T11:00:00+00:00]`

### `tests/test_stored_sec_projection.py::test_fundamentals_sync_is_null_while_price_and_news_remain_unchanged`

Transfer useful assertions to accurately named current authority/real telemetry owner.

- `tests/test_stored_sec_projection.py::test_fundamentals_sync_is_null_with_price_and_current_news_telemetry`

## Added Nodes

- `tests/test_data_coverage_tools.py::test_ticker_coverage_uses_current_news_sync_and_preserves_prices`
- `tests/test_data_scheduler.py::test_run_source_news_direct_when_normalized_writes_unset`
- `tests/test_market_data_admin.py::test_status_uses_current_news_sync_and_preserves_price_authority`
- `tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_malformed_current_normalized_setting`
- `tests/test_news_normalized_routing.py::test_route_matrix[False-False-legacy_local]`
- `tests/test_news_normalized_routing.py::test_route_matrix[False-None-legacy_local]`
- `tests/test_news_normalized_routing.py::test_route_matrix[False-True-normalized]`
- `tests/test_news_normalized_routing.py::test_route_matrix[True-False-blocked]`
- `tests/test_news_normalized_routing.py::test_route_matrix[True-None-normalized]`
- `tests/test_news_normalized_routing.py::test_route_matrix[True-True-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[env-true-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-false-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-false-legacy_local]`
- `tests/test_news_routing_cleanup.py::test_current_writer_ignores_obsolete_profile_and_environment[stored-malformed-true-normalized]`
- `tests/test_news_routing_cleanup.py::test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings[env-false]`
- `tests/test_news_routing_cleanup.py::test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings[env-malformed]`
- `tests/test_news_routing_cleanup.py::test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings[env-true]`
- `tests/test_news_routing_cleanup.py::test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings[stored-false]`
- `tests/test_news_routing_cleanup.py::test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings[stored-malformed]`
- `tests/test_news_routing_cleanup.py::test_malformed_current_normalized_setting_still_blocks[malformed-None]`
- `tests/test_news_routing_cleanup.py::test_malformed_current_normalized_setting_still_blocks[true-malformed]`
- `tests/test_news_routing_cleanup.py::test_normalized_setter_denies_before_writing_and_preserves_old_key`
- `tests/test_news_routing_cleanup.py::test_normalized_setter_writes_only_current_key`
- `tests/test_news_routing_cleanup.py::test_obsolete_helpers_and_resolver_parameters_are_physically_removed`
- `tests/test_news_routing_cleanup.py::test_obsolete_put_is_unmounted_and_returns_405_without_writing`
- `tests/test_news_routing_cleanup.py::test_overlay_clears_stale_news_when_current_store_is_absent[env-false]`
- `tests/test_news_routing_cleanup.py::test_overlay_clears_stale_news_when_current_store_is_absent[env-malformed]`
- `tests/test_news_routing_cleanup.py::test_overlay_clears_stale_news_when_current_store_is_absent[env-true]`
- `tests/test_news_routing_cleanup.py::test_overlay_clears_stale_news_when_current_store_is_absent[stored-false]`
- `tests/test_news_routing_cleanup.py::test_overlay_clears_stale_news_when_current_store_is_absent[stored-malformed]`
- `tests/test_news_routing_cleanup.py::test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings[env-false]`
- `tests/test_news_routing_cleanup.py::test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings[env-malformed]`
- `tests/test_news_routing_cleanup.py::test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings[env-true]`
- `tests/test_news_routing_cleanup.py::test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings[stored-false]`
- `tests/test_news_routing_cleanup.py::test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings[stored-malformed]`
- `tests/test_news_routing_cleanup.py::test_overlay_propagates_corrupt_telemetry_without_mutation`
- `tests/test_news_routing_cleanup.py::test_status_has_only_current_routing_fields[env-false]`
- `tests/test_news_routing_cleanup.py::test_status_has_only_current_routing_fields[env-malformed]`
- `tests/test_news_routing_cleanup.py::test_status_has_only_current_routing_fields[env-true]`
- `tests/test_news_routing_cleanup.py::test_status_has_only_current_routing_fields[stored-false]`
- `tests/test_news_routing_cleanup.py::test_status_has_only_current_routing_fields[stored-malformed]`
- `tests/test_news_routing_cleanup.py::test_status_keeps_actual_ingest_telemetry_with_obsolete_settings[env-false]`
- `tests/test_news_routing_cleanup.py::test_status_keeps_actual_ingest_telemetry_with_obsolete_settings[env-malformed]`
- `tests/test_news_routing_cleanup.py::test_status_keeps_actual_ingest_telemetry_with_obsolete_settings[env-true]`
- `tests/test_news_routing_cleanup.py::test_status_keeps_actual_ingest_telemetry_with_obsolete_settings[stored-false]`
- `tests/test_news_routing_cleanup.py::test_status_keeps_actual_ingest_telemetry_with_obsolete_settings[stored-malformed]`
- `tests/test_news_settings_route.py::test_status_reports_current_normalized_environment_override`
- `tests/test_news_settings_route.py::test_status_selects_direct_writer_when_normalized_writes_are_disabled`
- `tests/test_news_sync_status.py::test_missing_sync_store_with_uri_metacharacters_stays_uncreated[market#data.db]`
- `tests/test_news_sync_status.py::test_missing_sync_store_with_uri_metacharacters_stays_uncreated[market?data.db]`
- `tests/test_news_sync_status.py::test_sync_reader_encodes_sqlite_uri_metacharacters[market#data.db]`
- `tests/test_news_sync_status.py::test_sync_reader_encodes_sqlite_uri_metacharacters[market?data.db]`
- `tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors[False-partial-2026-06-10T10:00:00+00:00]`
- `tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors[True-failed-2026-06-10T11:00:00+00:00]`
- `tests/test_provider_health.py::test_recent_publication_without_ingest_telemetry_is_no_signal[finnhub-finnhub-FINNHUB_API_KEY]`
- `tests/test_provider_health.py::test_recent_publication_without_ingest_telemetry_is_no_signal[massive-polygon-MASSIVE_API_KEY]`
- `tests/test_stored_sec_projection.py::test_fundamentals_sync_is_null_with_price_and_current_news_telemetry`
