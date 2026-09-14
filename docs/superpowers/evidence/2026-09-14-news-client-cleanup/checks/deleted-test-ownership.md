# C12 Deleted-Test Ownership

Base: `8c64f884`, `tests/test_collector_adapters.py`, 13 test functions.
Every old node disappears with its old file; that is not 13 abandoned safety
properties. Reconciliation against the preceding complete JUnit will report
the exact old/new IDs separately. Final identity comparison reports 15 removed
and 69 added IDs: the 13 old-file nodes below plus two renamed parameter IDs
for `test_normalized_news_route_calls_writer_under_market_lock`. Those two
parameters now contain `src.news_clients.finnhub` / `.polygon` instead of old
module paths; their assertions remain and both new IDs pass. Net count is +54.

| Deleted test | Current disposition / behavioral owner |
| --- | --- |
| test_collectors_expose_contract_from_src_package | `test_news_clients.py::test_clients_expose_only_transport_parser_and_credential_contract`, both clients; excludes retired CLI/storage fields. |
| test_import_is_side_effect_free | `test_fresh_client_import_does_not_configure_logging_write_files_or_start_provider`, both clients; now executes a fresh module rather than checking source text. |
| test_paths_are_repo_anchored | Retired archive/checkpoint storage config, physically absent. Current writer paths retain their own direct/normalized writer tests. |
| test_polygon_up_to_date_short_circuit | Retired global-file-cursor shortcut. Per-source/ticker initialization and inclusive cursors remain in `test_news_bootstrap_policy.py`, `test_news_direct.py`, normalized writer/adapter tests. |
| test_finnhub_up_to_date_short_circuit | Same retired global-file-cursor shortcut; no new equivalent completeness claim. |
| test_polygon_missing_key_raises | `test_normalized_client_missing_key_fails_before_constructing_session[polygon-...]`; existing scheduler config-preflight and Massive canonical-key tests retained. |
| test_finnhub_missing_key_raises | Same parametrized current factory owner for Finnhub; current scheduler preflight remains. |
| test_massive_news_transport_builds_requests_on_the_current_api_host | Same named behavioral test in `test_news_clients.py`; plus nonempty two-page/timestamp controls. |
| test_finnhub_incremental_window_capped_at_7_days | Retired CLI clamp and unverified entitlement assumption. New transport test preserves the supplied fourteen-day request; actual coverage/entitlement is not inferred. |
| test_load_tickers_requires_explicit_scope | Current `daily_update` no-scope and explicit ticker tests; clients no longer own scope. |
| test_load_tickers_active_universe | Current CLI real active-universe dispatch, unavailable/empty scope tests; real scope integration through `tests/news_scope_support.py` in active-universe and terminal lifecycle workflows. |
| test_finnhub_unavailable_scope_exits_before_provider_construction | Current CLI unavailable-scope test covers env, provider dispatch and summary telemetry; scheduler unavailable-universe test guards current client/writers/workers. |
| test_polygon_unavailable_scope_exits_before_provider_construction | Same actual CLI/scheduler guards; no forwarding old CLI. |

All existing scheduler tests remain. Their old impossible `run_incremental`
monkeypatch targets are removed from default fixtures or changed to live client
construction guards. The normalized path still asserts its injected client,
provider, writer lock and compatibility projection. News and price history
preservation assertions in terminal lifecycle workflows remain intact.

Three existing `test_job_runs.py` telemetry tests retain their IDs and checks
but call the real `record()` entry directly. The old `timed()` step-wrapper
had no product consumers; its passthrough-return contract is intentionally
removed. Disabled recording, terminal summary rows and recording-failure
isolation stay covered, alongside the real CLI exit/summary tests.
