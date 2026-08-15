# PostgreSQL Runtime Consumer Inventory

> **Status:** INVENTORY CLOSED ON TASK 3; INDEPENDENT ADMISSION PENDING
>
> **Candidate source tip:** `4c6b8d44ce2e768e95b822b11f618cc40f4bb9f0`
>
> This is a docs-only classification authority. It does not authorize product edits,
> no-tail deletion, CLI retirement, secret/config mutation, archive mutation, or remote access.

## 1. Authority Boundary

`surfaces.jsonl` is the sole disposition authority and
`candidate_adjudications.jsonl` is the sole candidate-closure authority. All TSV and
path projections below are generated from those files. Source coordinates refer only to
the frozen candidate source tip.

## 2. Candidate Sources and Closure

| Source family | Rows |
|---|---|
| archive_manifest | 16 |
| ast | 1200 |
| cli_registry | 47 |
| documentation | 272 |
| dynamic_route | 2 |
| environment_metadata | 2 |
| package_manifest | 2 |
| test_collection | 1966 |
| text_search | 6939 |

Candidate authority: `10446/d1ab1f1a1c7001799bde2dcedcc2e4424af670e1ec1f2f38737f8a5fb671f8e9`.
Adjudication authority: `10446/75c39f535b5ec9f72476e98d61cc664a95d4a1d9adc23eca787d242838ba7041`.
Classified: `9368`; excluded: `1078`.

### Exact exclusions

| Candidate ID | Reason | CLI class | Evidence |
|---|---|---|---|
| ast:data_sources/financial_metrics_calculator.py:1253:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:data_sources/sec_earnings_releases.py:297:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:data_sources/sec_insider_trades.py:372:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py:181:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py:188:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1089:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1137:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py:183:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py:190:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py:296:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py:303:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py:661:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py:668:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:extensions/sa_alpha_picks/build_firefox.py:618:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:extensions/sa_alpha_picks/build_firefox.py:651:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/api/__main__.py:15:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/audit/ibkr_news_catchup_audit.py:259:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/audit/ibkr_news_catchup_audit.py:287:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/collectors/finnhub_news.py:684:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/collectors/finnhub_news.py:786:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/collectors/polygon_news.py:1104:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/collectors/polygon_news.py:965:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/news_normalized/ibkr_cli.py:380:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/news_normalized/ibkr_cli.py:44:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/options_math/option_pricing.py:1335:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/prices_runtime.py:153:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:src/prices_runtime.py:23:13:cli_entrypoint:argparse.ArgumentParser | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:tests/test_ibkr_scanner.py:296:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| ast:tests/test_option_pricing.py:696:0:cli_entrypoint:__main__ | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:build | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:check:i18n-literals | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:dev | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:preview | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:test | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:test:watch | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:typecheck | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:data_sources/financial_metrics_calculator.py:1253:0:cli_entrypoint:python -m data_sources.financial_metrics_calculator | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:data_sources/sec_earnings_releases.py:297:0:cli_entrypoint:python -m data_sources.sec_earnings_releases | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:data_sources/sec_insider_trades.py:372:0:cli_entrypoint:python -m data_sources.sec_insider_trades | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py:181:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.controller_probe | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1089:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.destructive_controller | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1137:0:cli_entrypoint:python docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py:183:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_consumer_census | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py:296:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_db_row_manifest | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py:661:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_price_manifest | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:618:0:cli_entrypoint:python -m extensions.sa_alpha_picks.build_firefox | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:651:0:cli_entrypoint:extensions/sa_alpha_picks/build_firefox.py | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:651:0:cli_entrypoint:python extensions/sa_alpha_picks/build_firefox.py | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:package.json:-:-:cli_entrypoint:npm:build | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:package.json:-:-:cli_entrypoint:npm:dev:desktop | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:package.json:-:-:cli_entrypoint:npm:dev:web | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:package.json:-:-:cli_entrypoint:npm:start | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/api/__main__.py:15:0:cli_entrypoint:python -m src.api.__main__ | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/audit/ibkr_news_catchup_audit.py:259:0:cli_entrypoint:python -m src.audit.ibkr_news_catchup_audit | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/collectors/finnhub_news.py:684:0:cli_entrypoint:python -m src.collectors.finnhub_news | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/collectors/polygon_news.py:1104:0:cli_entrypoint:python -m src.collectors.polygon_news | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/news_normalized/ibkr_cli.py:380:0:cli_entrypoint:python -m src.news_normalized.ibkr_cli | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/options_math/option_pricing.py:1335:0:cli_entrypoint:python -m src.options_math.option_pricing | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:src/prices_runtime.py:153:0:cli_entrypoint:python -m src.prices_runtime | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:tests/live/sdk_driver_smoke.py:-:-:cli_entrypoint:python tests/live/sdk_driver_smoke.py | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:tests/live/sdk_route_smoke.py:-:-:cli_entrypoint:python tests/live/sdk_route_smoke.py | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:tests/test_ibkr_scanner.py:296:0:cli_entrypoint:python -m tests.test_ibkr_scanner | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| cli_registry:tests/test_option_pricing.py:696:0:cli_entrypoint:python -m tests.test_option_pricing | cli_handoff_only | operator | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| documentation:docs/design/PROJECT_PRIORITY_MAP.md:-:-:documentation_claim:backend_implementation | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/design/PROJECT_PRIORITY_MAP.md:-:-:documentation_claim:driver_dependency | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/design/PROJECT_PRIORITY_MAP.md:-:-:documentation_claim:postgres_runtime_or_archive | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/design/PROJECT_PRIORITY_MAP.md:-:-:documentation_claim:runtime_configuration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:driver_dependency | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:postgres_runtime_or_archive | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:runtime_configuration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:app_records_migration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:backend_implementation | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:driver_dependency | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:postgres_runtime_or_archive | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:runtime_configuration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:-:-:documentation_claim:backend_implementation | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:-:-:documentation_claim:driver_dependency | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:-:-:documentation_claim:postgres_runtime_or_archive | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| documentation:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:-:-:documentation_claim:runtime_configuration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_basic_stock_scan | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_connection | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_iv_scan | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_option_filter | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_option_quote | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_option_volume_scan | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_put_call_ratio_scan | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_scanner_parameters | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_ibkr_scanner.py:-:-:test_contract:tests/test_ibkr_scanner.py::test_unusual_activity | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_atm_call_delta_near_half | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_call_delta_range | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_gamma_positive | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_greeks_close_to_bs_for_call_no_div | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_greeks_with_dividends | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_put_delta_range | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_theta_negative | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanGreeks::test_vega_positive | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_american_iv_lower_for_put | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_iv_invalid_price | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_iv_recovery_call | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_iv_recovery_put | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_iv_recovery_with_dividend | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestAmericanIV::test_iv_various_strikes | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_at_expiration_call | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_at_expiration_put | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_call_no_dividend_equals_european | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_call_with_dividend_differs | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_call_with_high_dividend_has_premium | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_deep_itm_put_significant_premium | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_extreme_volatility | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_otm_call_positive | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_otm_put_positive | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_price_increases_with_time | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_price_increases_with_volatility | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_put_call_symmetry | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_put_early_exercise_premium_meaningful | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_put_higher_than_european | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBjerksundStensland2002::test_zero_rate | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_atm_call_price | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_atm_put_price | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_deep_itm_call | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_deep_otm_call | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_expired_option | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_greeks_atm_delta | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestBlackScholes::test_greeks_delta_range | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestEdgeCases::test_negative_price_iv | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestEdgeCases::test_very_high_volatility | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestEdgeCases::test_zero_time_to_expiry | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestHistoricalVolatility::test_close_to_close_hv | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestHistoricalVolatility::test_hv_empty_input | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestHistoricalVolatility::test_hv_with_ohlc | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestHistoricalVolatility::test_parkinson_vs_close_to_close | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestImpliedVolatility::test_iv_put | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestImpliedVolatility::test_iv_recovery | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestImpliedVolatility::test_iv_various_strikes | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingAnalysis::test_fair_priced_option | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingAnalysis::test_overpriced_option | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingAnalysis::test_scan_multiple_options | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingAnalysis::test_underpriced_option | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingWithAmerican::test_american_less_mispricing_for_puts | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingWithAmerican::test_mispricing_bs_model | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestMispricingWithAmerican::test_mispricing_uses_american_by_default | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestUnifiedPricing::test_american_model | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestUnifiedPricing::test_american_put_higher_than_bs | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestUnifiedPricing::test_bs_model | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestUnifiedPricing::test_default_is_american | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestUnifiedPricing::test_dividend_yield_parameter | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestVolatilitySmile::test_atm_no_adjustment | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| test_collection:tests/test_option_pricing.py:-:-:test_contract:tests/test_option_pricing.py::TestVolatilitySmile::test_otm_put_skew | cli_handoff_only | - | No PostgreSQL capability is present; retain command identity for the post-no-tail CLI census. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1001:1302:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1007:640:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1009:593:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:100:814:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1035:1008:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1035:1022:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1037:642:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1037:659:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1047:343:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1047:357:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1059:601:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1059:618:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1061:1217:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1071:1249:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1071:1253:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1087:887:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1087:904:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1089:1018:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1103:759:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1103:773:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1105:958:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1105:972:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1107:1076:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1115:468:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1117:835:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1125:883:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1125:887:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1133:464:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1133:468:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1133:503:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1135:598:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1135:602:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1135:661:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1143:705:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1143:722:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1145:1229:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1145:1246:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1151:504:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1151:551:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1153:1114:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1163:382:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1163:399:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1167:1005:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1167:1026:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1173:537:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1173:558:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1175:1425:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1175:1446:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1177:655:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1177:676:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1189:1605:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1190:1640:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1190:1672:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1191:1132:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1195:1989:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1195:2133:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1196:1072:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1196:1088:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1196:1125:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1197:1123:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1197:1150:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1197:1195:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1198:1145:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1198:1155:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1201:1594:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1201:1626:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1204:1535:documentation_claim:sslmode | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1204:1580:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1209:42:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1209:464:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1209:506:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1209:967:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:1529:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:207:documentation_claim:ARKSCOPE_ARCHIVE_PG_PASSWORD | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:224:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:450:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:531:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:658:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1210:658:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1211:1508:documentation_claim:ARKSCOPE_ARCHIVE_PG_PASSWORD | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1211:1525:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1211:620:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1213:1445:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1215:2466:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1216:381:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1218:203:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:1308:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:1342:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:194:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:230:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:252:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:320:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:366:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1219:52:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1220:274:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1220:316:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1220:56:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1221:744:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1222:1482:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1222:1482:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1223:1484:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1223:539:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1223:768:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1223:816:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1223:892:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1224:1131:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1225:1310:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1225:133:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1225:1351:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:1044:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:153:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:16:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:290:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:393:documentation_claim:use_local_records | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:573:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:63:documentation_claim:use_local_records | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:790:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:890:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:959:documentation_claim:PG_EXIT_COMPLETION_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:959:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1226:997:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1000:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1064:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1325:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:150:documentation_claim:PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:150:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1583:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1633:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1687:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1827:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:1925:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:2042:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:211:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:50:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1227:89:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:188:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:228:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:247:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:390:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:507:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:553:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:700:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:95:documentation_claim:PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1228:95:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:1023:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:1023:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:1091:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:1173:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:1204:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:162:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:16:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:216:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:255:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:277:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:277:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:372:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:58:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:611:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:692:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1229:886:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:1138:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:143:documentation_claim:PG_EXIT_N9_BATCH2_CLEANUP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:143:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:1463:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:1528:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:1561:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:319:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:345:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:50:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:651:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:814:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1230:81:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:1031:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:1112:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:115:documentation_claim:PG_EXIT_N9_BATCH2_CLEANUP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:115:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:1246:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:1367:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:1409:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:356:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:382:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:473:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:549:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:702:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1231:912:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1232:875:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1232:916:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1233:1012:documentation_claim:PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1233:1012:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1233:1369:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1233:172:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:100:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1150:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1173:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1457:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1533:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1598:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1660:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:1871:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1234:412:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:1223:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:1258:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:1284:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:1542:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:237:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:466:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1235:770:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:1077:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:1265:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:138:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:1453:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:1728:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:1788:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:50:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1236:722:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:109:documentation_claim:PG_EXIT_N9_BATCH1_DROP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:109:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:202:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:485:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:559:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:618:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1237:903:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1238:183:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1238:439:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1238:547:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1238:97:documentation_claim:PG_EXIT_N9_BATCH1_DROP_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1238:97:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:148:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:175:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:285:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:628:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:647:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1239:861:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:1093:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:1295:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:1414:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:150:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:1612:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:229:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:408:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:659:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1240:976:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1241:1045:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1241:123:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1241:567:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1009:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1276:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:128:documentation_claim:PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:128:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1356:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1755:documentation_claim:PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1755:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:1852:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:268:documentation_claim:use_local_records | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:369:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1242:878:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1243:102:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1243:1063:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1243:1088:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1243:374:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1243:683:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:122:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:1731:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:1773:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:1934:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:2011:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:2273:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:318:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:31:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:598:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1245:932:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:1074:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:136:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:16:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:231:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:464:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:680:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1247:80:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1249:686:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1249:686:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1249:739:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1251:2266:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1251:2266:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1251:2930:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1251:2983:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1251:3824:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1255:240:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1255:240:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:1256:260:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:13:245:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:13:245:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:222:41:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:238:41:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:246:68:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:15:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:165:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:340:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:398:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:439:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:537:documentation_claim:use_local_records | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:55:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:622:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:645:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:26:704:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:270:32:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:27:2119:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:27:2333:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:27:2417:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:27:516:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:284:56:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:29:170:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:304:70:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:317:43:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:369:296:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:484:1424:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:484:1485:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:484:698:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:487:155:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:487:4:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:487:74:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:1086:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:16:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:16:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:528:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:528:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:540:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:540:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:641:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:523:672:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:525:16:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:525:16:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:1219:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:1290:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:1315:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:16:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:16:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:234:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:401:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:401:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:460:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:492:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:630:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:718:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:718:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:744:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:527:744:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:1043:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:1445:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:16:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:16:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:329:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:329:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:423:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:423:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:533:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:533:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:529:886:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:545:1220:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:547:1139:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:549:1239:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:577:703:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:579:152:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:585:240:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:591:920:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:597:243:documentation_claim:SettingsPostPgExitStorage | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:653:152:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:653:152:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:655:49:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:655:49:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:659:999:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:659:999:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:689:505:documentation_claim:SettingsPostPgExitStorage | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:762:1150:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:764:815:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:766:1271:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:768:1057:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:772:1208:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:772:523:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:790:453:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:790:616:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:800:537:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:814:1289:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:826:349:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:828:544:documentation_claim:PGID | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:830:1120:documentation_claim:PGID | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:832:308:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:836:780:documentation_claim:PGID | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:838:282:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:838:846:documentation_claim:PGID | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:850:394:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:864:327:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:874:409:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:876:1214:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:876:305:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:878:880:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:880:308:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:884:1034:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:892:568:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:892:718:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:892:742:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:894:1329:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:894:845:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:896:225:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:898:1163:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:898:880:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:900:1680:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:902:452:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:906:874:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:908:950:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:912:1339:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:918:338:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:918:352:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:920:929:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:920:945:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:928:266:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:935:297:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:935:628:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:935:642:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:936:883:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:938:497:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:943:677:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:943:696:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:948:431:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:948:447:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:953:964:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:953:980:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:954:910:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:954:935:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:959:429:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:959:445:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:960:442:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:960:458:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:999:618:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/design/PROJECT_PRIORITY_MAP.md:999:637:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md:1072:42:documentation_claim:PGID | lexical_non_surface | - | Line 1072 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md:737:36:documentation_claim:PGID | lexical_non_surface | - | Line 737 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md:767:39:documentation_claim:PGID | lexical_non_surface | - | Line 767 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md:778:61:documentation_claim:PGID | lexical_non_surface | - | Line 778 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:100:6:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:1:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:1:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:46:1:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:103:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:103:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:164:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:164:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:22:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:233:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:35:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:35:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:47:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:73:47:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md:80:3:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md:1169:45:documentation_claim:PGID | lexical_non_surface | - | Line 1169 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md:543:56:documentation_claim:PGID | lexical_non_surface | - | Line 543 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md:457:95:documentation_claim:PGID | lexical_non_surface | - | Line 457 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md:664:19:documentation_claim:PGID | lexical_non_surface | - | Line 664 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:-:-:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1008:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1008:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:100:12:documentation_claim:PG_RUNTIME_CONSUMER_INVENTORY | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:100:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1017:23:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1018:29:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1018:73:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1019:31:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:101:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1020:8:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1023:62:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:102:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1033:60:documentation_claim:negative_no_pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1033:77:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1034:31:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1034:31:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1034:58:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:103:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1042:19:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1047:32:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:104:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:105:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:106:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1079:29:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:107:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1089:6:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:108:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:109:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1100:20:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1101:14:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1102:14:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1103:39:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1105:30:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1105:30:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:110:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1116:15:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1117:23:documentation_claim:PG_RUNTIME_CONSUMER_INVENTORY | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1117:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1118:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:111:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1125:39:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:112:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1139:32:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:113:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1143:7:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:114:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:115:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1166:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1167:63:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:116:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1172:40:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1176:12:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:117:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1183:1:documentation_claim:PG_RUNTIME_CONSUMER_INVENTORY | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1183:1:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:118:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:119:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1205:13:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:120:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:121:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1222:20:documentation_claim:PG_RUNTIME_CONSUMER_INVENTORY | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1222:20:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1223:14:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1224:39:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1226:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1226:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:122:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1236:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1237:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1238:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:123:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:123:33:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:124:12:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:125:37:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1301:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1302:0:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:131:34:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1327:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1328:36:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1329:36:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:132:34:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1331:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1331:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1346:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1347:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1348:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1355:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1355:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1378:52:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1378:52:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1382:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1383:36:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1384:36:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1386:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1386:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1439:9:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1439:9:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1455:19:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:14:37:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:151:75:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:153:25:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:156:22:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:158:45:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:163:3:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:165:74:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:167:13:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:170:22:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:172:22:documentation_claim:app_records_migrate | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:190:1:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:192:36:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:192:36:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:1:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:227:8:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:251:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:252:7:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:25:19:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:25:19:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:261:0:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:268:38:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:268:7:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:269:38:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:270:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:270:38:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:278:46:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:278:46:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:280:31:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:293:0:documentation_claim:negative_no_pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:294:0:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:306:121:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:306:248:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:306:30:documentation_claim:app-records/migration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:340:272:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:340:71:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:357:8:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:357:8:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:358:24:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:358:24:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:387:17:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:400:35:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:401:34:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:403:3:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:466:23:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:466:23:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:469:23:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:470:24:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:475:5:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:480:15:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:480:15:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:484:4:documentation_claim:app_records_migrate | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:490:10:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:491:19:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:504:25:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:505:9:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:505:9:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:511:5:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:512:18:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:512:18:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:512:5:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:512:5:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:516:5:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:516:5:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:519:5:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:519:5:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:521:38:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:528:55:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:528:55:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:556:0:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:601:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:602:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:617:7:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:630:5:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:642:19:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:645:6:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:670:17:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:671:29:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:688:14:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:689:12:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:690:15:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:692:16:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:713:2:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:746:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:747:36:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:749:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:749:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:764:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:765:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:782:12:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:787:23:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:787:32:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:787:32:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:787:45:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:787:45:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:788:26:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:788:45:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:788:45:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:789:24:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:789:51:documentation_claim:db_dsn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:790:38:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:791:22:documentation_claim:_get_conn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:791:46:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:792:51:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:793:22:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:793:36:documentation_claim:sslmode | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:793:48:documentation_claim:db_dsn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:799:70:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:848:0:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:849:0:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:850:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:850:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:851:0:documentation_claim:_get_conn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:852:0:documentation_claim:app_records_migrate | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:853:0:documentation_claim:app-records/migration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:854:0:documentation_claim:asyncpg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:855:0:documentation_claim:database backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:856:0:documentation_claim:database server | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:857:0:documentation_claim:db_dsn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:858:0:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:859:0:documentation_claim:migration_apply | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:860:0:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:861:0:documentation_claim:pg8000 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:862:0:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:863:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:864:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:864:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:864:0:documentation_claim:postgresql+ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:865:0:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:866:0:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:866:0:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:867:0:documentation_claim:sqlalchemy.dialects.postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:867:20:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:867:20:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:868:0:documentation_claim:sslmode | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:869:0:documentation_claim:use_local_records | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:878:33:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:878:48:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:878:48:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:901:74:documentation_claim:migration_preview | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:901:9:documentation_claim:app-records/migration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:902:10:documentation_claim:app-records/migration | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:902:73:documentation_claim:migration_apply | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:911:46:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:911:46:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:918:10:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:91:50:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:91:50:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:927:41:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:930:12:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:946:1:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:950:34:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:967:20:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:968:39:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:970:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:970:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:980:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:981:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:982:23:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:983:48:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md:998:31:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:1038:47:documentation_claim:PGID | lexical_non_surface | - | Line 1038 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:1071:61:documentation_claim:PGID | lexical_non_surface | - | Line 1071 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:1097:6:documentation_claim:PGID | lexical_non_surface | - | Line 1097 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:1131:64:documentation_claim:PGID | lexical_non_surface | - | Line 1131 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:838:34:documentation_claim:PGID | lexical_non_surface | - | Line 838 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:915:5:documentation_claim:PGID | lexical_non_surface | - | Line 915 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md:918:7:documentation_claim:PGID | lexical_non_surface | - | Line 918 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md:514:14:documentation_claim:PGID | lexical_non_surface | - | Line 514 uses PGID as the Unix process-group identifier, not PostgreSQL. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:-:-:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:106:42:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:109:42:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:109:60:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:109:60:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:119:46:documentation_claim:database server | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:120:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:120:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:123:34:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:123:34:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:124:57:documentation_claim:db_dsn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:125:26:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:125:58:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:125:58:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:126:26:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:126:26:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:129:29:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:129:29:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:134:3:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:134:3:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:136:63:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:136:63:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:138:39:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:138:39:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:142:15:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:142:62:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:142:62:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:146:17:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:14:46:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:14:46:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:150:10:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:156:13:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:156:13:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:158:46:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:158:46:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:15:11:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:15:11:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:169:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:169:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:16:20:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:16:20:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:183:6:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:183:6:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:18:53:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:192:66:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:19:5:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:1:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:1:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:203:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:203:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:20:42:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:20:42:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:219:11:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:219:58:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:219:58:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:222:3:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:222:3:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:224:27:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:225:13:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:225:13:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:22:31:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:22:31:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:233:1:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:234:24:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:235:45:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:23:14:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:242:10:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:242:21:documentation_claim:psycopg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:242:21:documentation_claim:psycopg2 | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:242:43:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:242:43:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:244:9:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:244:9:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:246:10:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:248:10:documentation_claim:_get_conn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:248:23:documentation_claim:db_dsn | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:248:33:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:249:7:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:24:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:24:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:251:35:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:251:35:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:252:9:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:252:9:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:254:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:254:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:255:25:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:256:63:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:258:38:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:258:38:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:260:22:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:262:15:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:262:15:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:263:50:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:263:50:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:26:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:26:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:26:60:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:279:6:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:279:6:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:28:17:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:321:6:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:321:6:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:327:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:327:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:32:41:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:32:41:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:333:37:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:333:37:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:33:29:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:33:29:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:340:3:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:342:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:342:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:343:39:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:348:38:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:348:38:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:358:35:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:358:7:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:358:7:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:359:25:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:359:25:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:359:4:documentation_claim:databasebackend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:361:3:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:363:8:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:364:3:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:364:3:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:366:50:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:375:4:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:375:4:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:389:15:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:391:19:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:392:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:392:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:401:15:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:401:15:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:413:9:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:413:9:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:420:5:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:420:5:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:430:29:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:430:29:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:433:9:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:442:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:442:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:448:48:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:466:62:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:466:62:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:469:15:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:46:5:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:46:5:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:470:12:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:470:12:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:471:29:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:474:65:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:478:63:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:478:63:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:49:54:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:49:54:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:49:5:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:49:5:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:500:0:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:500:55:documentation_claim:db_backend | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:502:43:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:502:43:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:511:12:documentation_claim:database_url | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:513:27:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:513:27:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:514:25:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:514:25:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:515:13:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:515:13:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:516:13:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:516:13:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:531:62:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:534:31:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:536:54:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:536:6:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:536:6:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:540:18:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:552:28:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:552:28:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:559:54:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:559:54:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:561:2:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:561:2:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:596:21:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:597:9:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:597:9:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:605:47:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:605:47:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:608:60:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:608:60:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:611:13:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:624:0:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:624:0:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:625:12:documentation_claim:pg | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:633:39:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:633:39:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:637:7:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:637:7:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:92:0:documentation_claim:pg_ | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:92:36:documentation_claim:postgres | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |
| text_search:docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md:92:36:documentation_claim:postgresql | generated_inventory_authority | - | Frozen source-tip program authority is excluded to prevent recursive self-classification. |

## 3. Package Provenance

The repository declares `psycopg[binary]>=3.1`, but no installed distribution provides
the imported `psycopg` module. The active environment provides `psycopg2` through
`psycopg2-binary 2.9.10`; marker-admitted metadata names `news-please 1.6.15` as the
sole observed reverse requirement. This is current metadata, not installation-history proof.
The complete sanitized witness is `pg_runtime_inventory/environment_packages.json`.

## 4. Complete Surface Map

| ID | Path | Symbol | Kind | Reachability | Disposition | Owner | Stop condition |
|---|---|---|---|---|---|---|---|
| archive:docker/README.md | docker/README.md | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:docker/docker-compose.yml | docker/docker-compose.yml | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/001_init_schema.sql | sql/001_init_schema.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/003_add_reports.sql | sql/003_add_reports.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/004_add_memories.sql | sql/004_add_memories.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/005_add_financial_cache.sql | sql/005_add_financial_cache.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/006_add_news_search.sql | sql/006_add_news_search.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/007_add_sa_alpha_picks.sql | sql/007_add_sa_alpha_picks.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/008_add_sa_articles.sql | sql/008_add_sa_articles.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/009_add_sa_market_news.sql | sql/009_add_sa_market_news.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/010_add_sa_market_news_detail.sql | sql/010_add_sa_market_news_detail.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/011_add_job_runs.sql | sql/011_add_job_runs.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/012_add_sa_comment_signals.sql | sql/012_add_sa_comment_signals.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/013_add_p1_2_macro_calendar.sql | sql/013_add_p1_2_macro_calendar.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/014_sa_alpha_picks_closed_date_and_dual_membership.sql | sql/014_sa_alpha_picks_closed_date_and_dual_membership.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| archive:sql/015_sa_alpha_picks_closed_event_identity.sql | sql/015_sa_alpha_picks_closed_event_identity.sql | - | archive_asset | archive_only | retire_pg_only | pg_no_tail | A reviewed current product runtime requires this tracked archive asset. |
| cli:extensions/sa_alpha_picks/install.sh:extensions_sa_alpha_picks_install.sh | extensions/sa_alpha_picks/install.sh | extensions/sa_alpha_picks/install.sh | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:extensions/sa_alpha_picks/install_firefox.sh:extensions_sa_alpha_picks_install_firefox.sh | extensions/sa_alpha_picks/install_firefox.sh | extensions/sa_alpha_picks/install_firefox.sh | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:src/agents/cli.py:legacy-agent | src/agents/cli.py | __main__ | cli_entrypoint | legacy_agent | defer_to_legacy_agent_cli_census | legacy_agent_cli_census | The later CLI census proves this entrypoint is not legacy-agent or Track-B-adjacent. |
| cli:src/agents/openai_agent/agent.py:legacy-agent | src/agents/openai_agent/agent.py | python -m src.agents.openai_agent.agent | cli_entrypoint | legacy_agent | defer_to_legacy_agent_cli_census | legacy_agent_cli_census | The later CLI census proves this entrypoint is not legacy-agent or Track-B-adjacent. |
| cli:src/audit/sa_article_reconciliation.py:argparse.ArgumentParser | src/audit/sa_article_reconciliation.py | argparse.ArgumentParser | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:src/audit/universe_retirement.py:argparse.ArgumentParser | src/audit/universe_retirement.py | argparse.ArgumentParser | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:src/daily_update.py:argparse.ArgumentParser | src/daily_update.py | argparse.ArgumentParser | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:src/sa_native_host.py:main | src/sa_native_host.py | __main__ | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| cli:src/smoke/pg_unreachable_e2e.py:argparse.ArgumentParser | src/smoke/pg_unreachable_e2e.py | argparse.ArgumentParser | cli_entrypoint | operator | retire_pg_only | pg_no_tail | A positive startup, scheduler, or dynamic-route-census contract is found in the current PG-named command. |
| cli:tests/live/smoke_fred.py:main | tests/live/smoke_fred.py | __main__ | cli_entrypoint | operator | retain_operator_remove_pg_branch | pg_no_tail | Removing the PG branch would remove the command's measured non-PG operator behavior. |
| dependency:requirements.txt:postgres-drivers | requirements.txt | psycopg[binary]>=3.1 | dependency | startup | rewrite_current_authority | pg_no_tail | A final source import requires a PostgreSQL driver after all PG branches are removed. |
| documentation:README.md | README.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:data_sources/DATA_SOURCE_QUIRKS.md | data_sources/DATA_SOURCE_QUIRKS.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docker/README.md | docker/README.md | - | documentation_claim | archive_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/PROJECT_HISTORY.md | docs/PROJECT_HISTORY.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/PUBLICATION_REVIEW.md | docs/PUBLICATION_REVIEW.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/data/DATA_INVENTORY.md | docs/data/DATA_INVENTORY.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md | docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/data/OPTIONS_PRICING_THEORY.md | docs/data/OPTIONS_PRICING_THEORY.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/AGENT_EVOLUTION_TRACKER.md | docs/design/AGENT_EVOLUTION_TRACKER.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md | docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md | docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/CONFIG_AUTHORITY_PLAN.md | docs/design/CONFIG_AUTHORITY_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/CREDENTIAL_MANAGEMENT_PLAN.md | docs/design/CREDENTIAL_MANAGEMENT_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/CURRENT_PROJECT_CONTEXT.md | docs/design/CURRENT_PROJECT_CONTEXT.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md | docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md | docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/DESKTOP_APP_VISION_DRAFT.md | docs/design/DESKTOP_APP_VISION_DRAFT.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md | docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/ENGINEERING_ISSUE_REGISTER.md | docs/design/ENGINEERING_ISSUE_REGISTER.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md | docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md | docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md | docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md | docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/LOCAL_STORAGE_TOPOLOGY.md | docs/design/LOCAL_STORAGE_TOPOLOGY.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md | docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/NEWS_DIRECT_LOCAL_PLAN.md | docs/design/NEWS_DIRECT_LOCAL_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/P1_2_PROVIDER_DISCOVERY.md | docs/design/P1_2_PROVIDER_DISCOVERY.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/P1_2_SPEC.md | docs/design/P1_2_SPEC.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/P1_3_SPEC.md | docs/design/P1_3_SPEC.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/P1_5_S3_OSS_SPIKE_DECISION.md | docs/design/P1_5_S3_OSS_SPIKE_DECISION.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/PG_EXIT_COMPLETION_PLAN.md | docs/design/PG_EXIT_COMPLETION_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md | docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md | docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md | docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md | docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md | docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md | docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_REMAINDER_SCOPING.md | docs/design/PG_EXIT_REMAINDER_SCOPING.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md | docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md | docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md | docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/README.md | docs/design/README.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md | docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/REPO_HYGIENE_AUDIT_2026_07.md | docs/design/REPO_HYGIENE_AUDIT_2026_07.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/RL_COLLAPSE_FINDINGS.md | docs/design/RL_COLLAPSE_FINDINGS.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md | docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/SA_CUTOVER_3D_RUNBOOK.md | docs/design/SA_CUTOVER_3D_RUNBOOK.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/SA_EVIDENCE_FEED_C1_SPEC.md | docs/design/SA_EVIDENCE_FEED_C1_SPEC.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md | docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/SCHEDULER_HARDENING_PLAN.md | docs/design/SCHEDULER_HARDENING_PLAN.md | - | documentation_claim | documentation_only | rewrite_current_authority | pg_no_tail | Deleting this file would remove still-current non-PostgreSQL authority. |
| documentation:docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md | docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/design/archive/README.md | docs/design/archive/README.md | - | documentation_claim | archive_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md | docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md | docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md | docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md | docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md | docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md | docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md | docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md | docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md | docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md | docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md | docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md | docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-06-27-news-direct-cutover.md | docs/superpowers/plans/2026-06-27-news-direct-cutover.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-06-27-news-identity-repair.md | docs/superpowers/plans/2026-06-27-news-identity-repair.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md | docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md | docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md | docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md | docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md | docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md | docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md | docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md | docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-05-macro-snapshot-display.md | docs/superpowers/plans/2026-07-05-macro-snapshot-display.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-05-news-burst-hardening.md | docs/superpowers/plans/2026-07-05-news-burst-hardening.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md | docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md | docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md | docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md | docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-investor-profile-track-a.md | docs/superpowers/plans/2026-07-06-investor-profile-track-a.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md | docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md | docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md | docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-07-current-quote-tool.md | docs/superpowers/plans/2026-07-07-current-quote-tool.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md | docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md | docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-10-holdings-row-actions.md | docs/superpowers/plans/2026-07-10-holdings-row-actions.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-10-model-capability-catalog.md | docs/superpowers/plans/2026-07-10-model-capability-catalog.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-11-models-ux-implementation.md | docs/superpowers/plans/2026-07-11-models-ux-implementation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md | docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md | docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md | docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md | docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-12-subscription-card-routing.md | docs/superpowers/plans/2026-07-12-subscription-card-routing.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md | docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md | docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md | docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md | docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md | docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md | docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md | docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md | docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md | docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md | docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md | docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md | docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-20-i18n-0-foundation.md | docs/superpowers/plans/2026-07-20-i18n-0-foundation.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md | docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-20-i18n-2-settings.md | docs/superpowers/plans/2026-07-20-i18n-2-settings.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md | docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-23-i18n-3-explore.md | docs/superpowers/plans/2026-07-23-i18n-3-explore.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md | docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md | docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-25-i18n-6-release.md | docs/superpowers/plans/2026-07-25-i18n-6-release.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md | docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md | docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md | docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md | docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md | docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-29-query-route-harness-termination.md | docs/superpowers/plans/2026-07-29-query-route-harness-termination.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md | docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md | docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md | docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md | docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md | docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md | docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md | docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md | docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md | docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md | docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-06-27-news-identity-repair-design.md | docs/superpowers/specs/2026-06-27-news-identity-repair-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-06-28-news-article-normalization-design.md | docs/superpowers/specs/2026-06-28-news-article-normalization-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md | docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md | docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md | docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md | docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md | docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md | docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md | docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md | docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md | docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-17-news-content-availability-design.md | docs/superpowers/specs/2026-07-17-news-content-availability-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md | docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md | docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-25-i18n-6-release-design.md | docs/superpowers/specs/2026-07-25-i18n-6-release-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md | docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md | docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md | docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md | docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md | docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md | docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md | docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md | docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md | docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| documentation:docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md | docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md | - | documentation_claim | documentation_only | retire_pg_only | pg_no_tail | A reviewed current authority still depends on this dated PostgreSQL narrative. |
| environment-dependency:news-please | <environment> | news-please | environment_dependency | startup | retire_pg_only | pg_no_tail | Final no-tail import census still requires the environment-provided psycopg2 family. |
| environment-dependency:psycopg2 | <environment> | psycopg2 | environment_dependency | startup | retire_pg_only | pg_no_tail | Final no-tail import census still requires the environment-provided psycopg2 family. |
| inheritance:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py | LocalMarketDatabaseBackend | inheritance | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| inheritance:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py | SACaptureDatabaseBackend | inheritance | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| inheritance:tests/test_db_backend_retired_pg_sa.py:NoPGSA | tests/test_db_backend_retired_pg_sa.py | _NoPGSA | inheritance | test_only | retire_pg_only | pg_no_tail | A current consumer reaches this PG-only nominal contract outside the classified caller set. |
| inheritance:tests/test_db_backend_retired_prices.py:NoPgDatabaseBackend | tests/test_db_backend_retired_prices.py | NoPgDatabaseBackend | inheritance | test_only | retire_pg_only | pg_no_tail | A current consumer reaches this PG-only nominal contract outside the classified caller set. |
| inheritance:tests/test_pg_unreachable_e2e.py:FakePoison | tests/test_pg_unreachable_e2e.py | FakePoison | inheritance | test_only | retire_pg_only | pg_no_tail | A current consumer reaches this PG-only nominal contract outside the classified caller set. |
| inheritance:tests/test_sa_reconciliation_native_host.py:Backend | tests/test_sa_reconciliation_native_host.py | Backend | inheritance | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| inheritance:tests/test_sa_reconciliation_native_host.py:MetaBackend | tests/test_sa_reconciliation_native_host.py | MetaBackend | inheritance | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| inheritance:tests/test_sa_reconciliation_native_host.py:NoPG | tests/test_sa_reconciliation_native_host.py | NoPG | inheritance | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| local-capability:src/tools/data_access.py:backend-contract | src/tools/data_access.py | DataAccessLayer._backend | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained call site uses a backend method outside the exact measured method set. |
| module_import:data_sources/financial_datasets_client.py:psycopg | data_sources/financial_datasets_client.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:data_sources/financial_datasets_client.py:psycopg2 | data_sources/financial_datasets_client.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:data_sources/financial_datasets_client.py:psycopg2.extras | data_sources/financial_datasets_client.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:extensions/sa_alpha_picks/install.sh:psycopg | extensions/sa_alpha_picks/install.sh | psycopg | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:extensions/sa_alpha_picks/install.sh:psycopg2 | extensions/sa_alpha_picks/install.sh | psycopg2 | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:extensions/sa_alpha_picks/install_firefox.sh:psycopg | extensions/sa_alpha_picks/install_firefox.sh | psycopg | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:extensions/sa_alpha_picks/install_firefox.sh:psycopg2 | extensions/sa_alpha_picks/install_firefox.sh | psycopg2 | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/anthropic_agent/agent.py:src.tools.backends.db_backend.DatabaseBackend | src/agents/anthropic_agent/agent.py | src.tools.backends.db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/anthropic_agent/agent.py:src.tools.data_access.DataAccessLayer | src/agents/anthropic_agent/agent.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/cli.py:src.tools.backends.db_backend.DatabaseBackend | src/agents/cli.py | src.tools.backends.db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/cli.py:src.tools.data_access.DataAccessLayer | src/agents/cli.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/openai_agent/agent.py:src.tools.backends.db_backend.DatabaseBackend | src/agents/openai_agent/agent.py | src.tools.backends.db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/agents/openai_agent/agent.py:src.tools.data_access.DataAccessLayer | src/agents/openai_agent/agent.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/api/dependencies.py:src.tools.data_access.DataAccessLayer | src/api/dependencies.py | src.tools.data_access.DataAccessLayer | module_import | startup | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.PgAppRecordsSource | src/api/routes/app_records.py | src.app_records_migrate.PgAppRecordsSource | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.apply_migration | src/api/routes/app_records.py | src.app_records_migrate.apply_migration | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.preview_migration | src/api/routes/app_records.py | src.app_records_migrate.preview_migration | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/api/routes/fundamentals.py:src.tools.data_access.DataAccessLayer | src/api/routes/fundamentals.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/api/routes/news.py:src.tools.data_access.DataAccessLayer | src/api/routes/news.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/api/routes/profile.py:src.tools.data_access.DataAccessLayer | src/api/routes/profile.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/app_records_migrate.py:psycopg | src/app_records_migrate.py | psycopg | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/app_records_migrate.py:psycopg2 | src/app_records_migrate.py | psycopg2 | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/app_records_migrate.py:psycopg2.extras.RealDictCursor | src/app_records_migrate.py | psycopg2.extras.RealDictCursor | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/app_records_store.py:psycopg | src/app_records_store.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/app_records_store.py:psycopg2 | src/app_records_store.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/audit/sa_article_reconciliation.py:src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend | src/audit/sa_article_reconciliation.py | src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/audit/universe_retirement.py:src.tools.data_access.DataAccessLayer | src/audit/universe_retirement.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/daily_update.py:src.tools.data_access.DataAccessLayer | src/daily_update.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/macro_calendar/store.py:psycopg | src/macro_calendar/store.py | psycopg | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/macro_calendar/store.py:psycopg2 | src/macro_calendar/store.py | psycopg2 | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/macro_calendar/store.py:psycopg2.extras | src/macro_calendar/store.py | psycopg2.extras | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/monitor/scheduler.py:psycopg | src/monitor/scheduler.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/monitor/scheduler.py:psycopg2 | src/monitor/scheduler.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa/comment_signal_backfill.py:psycopg | src/sa/comment_signal_backfill.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa/comment_signal_backfill.py:psycopg2 | src/sa/comment_signal_backfill.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa/comment_signal_backfill.py:psycopg2.extras | src/sa/comment_signal_backfill.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa_capture_store.py:psycopg | src/sa_capture_store.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa_capture_store.py:psycopg2 | src/sa_capture_store.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/sa_native_host.py:src.tools.data_access.DataAccessLayer | src/sa_native_host.py | src.tools.data_access.DataAccessLayer | module_import | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/data_scheduler.py:psycopg | src/service/data_scheduler.py | psycopg | module_import | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/data_scheduler.py:psycopg2 | src/service/data_scheduler.py | psycopg2 | module_import | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/data_scheduler.py:psycopg2.extensions.parse_dsn | src/service/data_scheduler.py | psycopg2.extensions.parse_dsn | module_import | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/job_runs_store.py:psycopg | src/service/job_runs_store.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/job_runs_store.py:psycopg2 | src/service/job_runs_store.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/job_runs_store.py:psycopg2.extras | src/service/job_runs_store.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/macro_calendar_health.py:psycopg | src/service/macro_calendar_health.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/macro_calendar_health.py:psycopg2 | src/service/macro_calendar_health.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/macro_calendar_health.py:psycopg2.extras | src/service/macro_calendar_health.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/provider_health.py:psycopg | src/service/provider_health.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/provider_health.py:psycopg2 | src/service/provider_health.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/sa_market_news_health.py:psycopg | src/service/sa_market_news_health.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/service/sa_market_news_health.py:psycopg2 | src/service/sa_market_news_health.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/smoke/pg_unreachable_e2e.py:psycopg | src/smoke/pg_unreachable_e2e.py | psycopg | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/smoke/pg_unreachable_e2e.py:psycopg2 | src/smoke/pg_unreachable_e2e.py | psycopg2 | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/tools/analysis_tools.py:data_access.DataAccessLayer | src/tools/analysis_tools.py | data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/analysis_tools.py:data_sources.financial_datasets_client.FinancialDatasetsClient | src/tools/analysis_tools.py | data_sources.financial_datasets_client.FinancialDatasetsClient | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/db_backend.py:psycopg | src/tools/backends/db_backend.py | psycopg | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/tools/backends/db_backend.py:psycopg2 | src/tools/backends/db_backend.py | psycopg2 | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/tools/backends/db_backend.py:psycopg2.extras | src/tools/backends/db_backend.py | psycopg2.extras | module_import | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| module_import:src/tools/backends/local_market_backend.py:db_backend.DatabaseBackend | src/tools/backends/local_market_backend.py | db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend.DatabaseBackend | src/tools/backends/sa_capture_backend.py | db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend._plan_comment_duplicate_cleanup | src/tools/backends/sa_capture_backend.py | db_backend._plan_comment_duplicate_cleanup | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend._prepare_comments_for_upsert | src/tools/backends/sa_capture_backend.py | db_backend._prepare_comments_for_upsert | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:local_market_backend.LocalMarketDatabaseBackend | src/tools/backends/sa_capture_backend.py | local_market_backend.LocalMarketDatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:psycopg | src/tools/backends/sa_capture_backend.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/backends/sa_capture_backend.py:psycopg2 | src/tools/backends/sa_capture_backend.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/data_access.py:backends.db_backend.DatabaseBackend | src/tools/data_access.py | backends.db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/data_access.py:src.tools.backends.local_market_backend.LocalMarketDatabaseBackend | src/tools/data_access.py | src.tools.backends.local_market_backend.LocalMarketDatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/data_access.py:src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend | src/tools/data_access.py | src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/freshness.py:psycopg | src/tools/freshness.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/freshness.py:psycopg2 | src/tools/freshness.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/freshness.py:src.tools.backends.db_backend.DatabaseBackend | src/tools/freshness.py | src.tools.backends.db_backend.DatabaseBackend | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/memory_tools.py:data_access.DataAccessLayer | src/tools/memory_tools.py | data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/news_tools.py:data_access.DataAccessLayer | src/tools/news_tools.py | data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/price_tools.py:data_access.DataAccessLayer | src/tools/price_tools.py | data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/report_tools.py:data_access.DataAccessLayer | src/tools/report_tools.py | data_access.DataAccessLayer | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_digest_tools.py:psycopg | src/tools/sa_digest_tools.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_digest_tools.py:psycopg2 | src/tools/sa_digest_tools.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_digest_tools.py:psycopg2.extras | src/tools/sa_digest_tools.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_tools.py:psycopg | src/tools/sa_tools.py | psycopg | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_tools.py:psycopg2 | src/tools/sa_tools.py | psycopg2 | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| module_import:src/tools/sa_tools.py:psycopg2.extras | src/tools/sa_tools.py | psycopg2.extras | module_import | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| route:src/api/routes/app_records.py:migration_apply | src/api/routes/app_records.py | migration_apply | route | api_route | retire_pg_only | pg_no_tail | A reviewed current product consumer requires this PostgreSQL migration endpoint. |
| route:src/api/routes/app_records.py:migration_preview | src/api/routes/app_records.py | migration_preview | route | api_route | retire_pg_only | pg_no_tail | A reviewed current product consumer requires this PostgreSQL migration endpoint. |
| runtime_config:config/.env.template:database_url | config/.env.template | database_url | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:config/.env.template:sslmode | config/.env.template | sslmode | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:data_sources/financial_datasets_client.py:database_url | data_sources/financial_datasets_client.py | database_url | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/agents/anthropic_agent/agent.py:db_dsn | src/agents/anthropic_agent/agent.py | db_dsn | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/agents/cli.py:db_dsn | src/agents/cli.py | db_dsn | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/agents/openai_agent/agent.py:db_dsn | src/agents/openai_agent/agent.py | db_dsn | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/api/dependencies.py:db_dsn | src/api/dependencies.py | db_dsn | runtime_config | startup | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/api/routes/app_records.py:use_local_records | src/api/routes/app_records.py | use_local_records | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/app_records_store.py:use_local_records | src/app_records_store.py | use_local_records | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/audit/sa_article_reconciliation.py:postgresql | src/audit/sa_article_reconciliation.py | postgresql:// | runtime_config | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/audit/universe_retirement.py:db_dsn | src/audit/universe_retirement.py | db_dsn | runtime_config | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/daily_update.py:db_dsn | src/daily_update.py | db_dsn | runtime_config | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/sa_native_host.py:db_dsn | src/sa_native_host.py | db_dsn | runtime_config | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/service/data_scheduler.py:database_url | src/service/data_scheduler.py | database_url | runtime_config | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/smoke/pg_unreachable_e2e.py:db_dsn | src/smoke/pg_unreachable_e2e.py | db_dsn | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/smoke/pg_unreachable_e2e.py:postgresql | src/smoke/pg_unreachable_e2e.py | postgresql:// | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/tools/backends/db_backend.py:postgresql | src/tools/backends/db_backend.py | postgresql:// | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/tools/backends/db_backend.py:sslmode | src/tools/backends/db_backend.py | sslmode | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/tools/backends/local_market_backend.py:sslmode | src/tools/backends/local_market_backend.py | sslmode | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/backends/sa_capture_backend.py:sslmode | src/tools/backends/sa_capture_backend.py | sslmode | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/data_access.py:database_url | src/tools/data_access.py | database_url | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/data_access.py:db_dsn | src/tools/data_access.py | db_dsn | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/data_access.py:postgresql | src/tools/data_access.py | postgresql:// | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/data_access.py:sslmode | src/tools/data_access.py | sslmode | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/data_access.py:use_local_records | src/tools/data_access.py | use_local_records | runtime_config | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| runtime_config:src/tools/db_config.py:database_url | src/tools/db_config.py | database_url | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| runtime_config:src/tools/db_config.py:sslmode | src/tools/db_config.py | sslmode | runtime_config | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| startup_hook:src/api/app.py:app_records_router | src/api/app.py | app_records_router | startup_hook | startup | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/TickerDetail.tsx:pg | apps/arkscope-web/src/TickerDetail.tsx | pg_ | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/api.ts:pg | apps/arkscope-web/src/api.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/i18n/resources/en/explore.ts:pg | apps/arkscope-web/src/i18n/resources/en/explore.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/i18n/resources/en/settings.ts:pg | apps/arkscope-web/src/i18n/resources/en/settings.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts:pg | apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts:pg | apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:apps/arkscope-web/src/marketDataDisplay.ts:pg | apps/arkscope-web/src/marketDataDisplay.ts | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:config/.env.template:postgres | config/.env.template | postgres | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:data_sources/financial_datasets_client.py:FinancialDatasetsClient._db_get | data_sources/financial_datasets_client.py | FinancialDatasetsClient._db_get | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:data_sources/sec_edgar_source.py:pg | data_sources/sec_edgar_source.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/agents/anthropic_agent/agent.py:get_freshness_summary | src/agents/anthropic_agent/agent.py | _get_freshness_summary | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/agents/cli.py:handle_save_command | src/agents/cli.py | handle_save_command | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/agents/openai_agent/agent.py:get_freshness_prompt | src/agents/openai_agent/agent.py | _get_freshness_prompt | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/analyst_consensus.py:pg | src/analyst_consensus.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/app.py:pg | src/api/app.py | pg | store_or_backend | startup | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/dependencies.py:get_dal | src/api/dependencies.py | get_dal | store_or_backend | startup | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/routes/app_records.py:source | src/api/routes/app_records.py | _source | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/api/routes/fundamentals.py:fundamentals | src/api/routes/fundamentals.py | fundamentals | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/routes/macro_calendar.py:pg | src/api/routes/macro_calendar.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/routes/market_data.py:pg | src/api/routes/market_data.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/routes/news.py:news_feed | src/api/routes/news.py | news_feed | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/api/routes/profile.py:ticker_state_payload | src/api/routes/profile.py | _ticker_state_payload | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/app_records_migrate.py:PgAppRecordsSource._rows | src/app_records_migrate.py | PgAppRecordsSource._rows | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/app_records_store.py:pg | src/app_records_store.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/audit/sa_article_reconciliation.py:main | src/audit/sa_article_reconciliation.py | main | store_or_backend | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/audit/universe_retirement.py:load_production_overview_tickers | src/audit/universe_retirement.py | _load_production_overview_tickers | store_or_backend | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/card_runs.py:pg | src/card_runs.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/daily_update.py:RunTelemetry.__init | src/daily_update.py | _RunTelemetry.__init__ | store_or_backend | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/fundamentals/cache.py:db_backend | src/fundamentals/cache.py | db_backend | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/ibkr_gateway_lock.py:pg | src/ibkr_gateway_lock.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/macro_calendar/__init__.py:pg | src/macro_calendar/__init__.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/macro_calendar/fred_ingestion.py:ingest_full_vintages | src/macro_calendar/fred_ingestion.py | _ingest_full_vintages | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/macro_calendar/local_store.py:pg | src/macro_calendar/local_store.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/macro_calendar/store.py:module | src/macro_calendar/store.py | <module> | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/market_data_admin.py:pg | src/market_data_admin.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/market_data_direct.py:pg | src/market_data_direct.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/news_direct.py:pg | src/news_direct.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/news_normalized/routing.py:NEWS_PG_EXIT_COMPLETED_KEY | src/news_normalized/routing.py | NEWS_PG_EXIT_COMPLETED_KEY | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/news_normalized/schema.py:pg | src/news_normalized/schema.py | pg_ | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/news_providers.py:pg | src/news_providers.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/news_sync_status.py:pg | src/news_sync_status.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/portfolio_state.py:pg | src/portfolio_state.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/profile_state.py:postgres | src/profile_state.py | postgres | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/research_threads.py:pg | src/research_threads.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/sa/comment_signal_backfill.py:run_backfill_sqlite | src/sa/comment_signal_backfill.py | _run_backfill_sqlite | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/sa_capture_store.py:pg | src/sa_capture_store.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/sa_native_host.py:handle_message | src/sa_native_host.py | handle_message | store_or_backend | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/scheduler_state.py:pg | src/scheduler_state.py | pg | store_or_backend | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/service/data_scheduler.py:module | src/service/data_scheduler.py | <module> | store_or_backend | scheduler | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/service/job_runs_store.py:module | src/service/job_runs_store.py | <module> | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/service/macro_calendar_health.py:evaluate_job | src/service/macro_calendar_health.py | _evaluate_job | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/service/provider_health.py:databasebackend | src/service/provider_health.py | databasebackend | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/service/sa_market_news_health.py:evaluate_health | src/service/sa_market_news_health.py | evaluate_health | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/smoke/pg_unreachable_e2e.py:module | src/smoke/pg_unreachable_e2e.py | <module> | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/tools/analysis_tools.py:get_fd_cache_days | src/tools/analysis_tools.py | _get_fd_cache_days | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/backends/__init__.py:databasebackend | src/tools/backends/__init__.py | databasebackend | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/backends/db_backend.py:DatabaseBackend.__init | src/tools/backends/db_backend.py | DatabaseBackend.__init__ | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py | LocalMarketDatabaseBackend | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/backends/provenance.py:pg | src/tools/backends/provenance.py | pg_ | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py | SACaptureDatabaseBackend | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/backends/sqlite_backend.py:pg | src/tools/backends/sqlite_backend.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/data_access.py:DataAccessLayer._compute_unresolved_symbols_raw_PG_connection | src/tools/data_access.py | DataAccessLayer._compute_unresolved_symbols raw PG connection | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/data_coverage_tools.py:postgres | src/tools/data_coverage_tools.py | postgres | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/db_config.py:postgres | src/tools/db_config.py | postgres | store_or_backend | product_runtime | retire_pg_only | pg_no_tail | An uncensused runtime caller requires this PostgreSQL-only definition. |
| store_or_backend:src/tools/freshness.py:module | src/tools/freshness.py | <module> | store_or_backend | product_runtime | rewrite_to_local_capability | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/macro_calendar_tools.py:pg | src/tools/macro_calendar_tools.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/memory_tools.py:pg | src/tools/memory_tools.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/news_tools.py:get_news_brief | src/tools/news_tools.py | get_news_brief | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/price_tools.py:get_price_change | src/tools/price_tools.py | get_price_change | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/report_tools.py:pg | src/tools/report_tools.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/sa_digest_tools.py:fetch_dicts | src/tools/sa_digest_tools.py | _fetch_dicts | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:src/tools/sa_tools.py:focus_local | src/tools/sa_tools.py | _focus_local | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:tests/conftest.py:pg | tests/conftest.py | pg | store_or_backend | product_runtime | rewrite_current_authority | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| store_or_backend:tests/live/smoke_fred.py:main | tests/live/smoke_fred.py | main | store_or_backend | product_runtime | retain_operator_remove_pg_branch | pg_no_tail | A retained consumer requires behavior outside the measured local capability or local-only rewrite. |
| test-contract:apps/arkscope-web/src/AICard.test.tsx | apps/arkscope-web/src/AICard.test.tsx | apps/arkscope-web/src/AICard.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/Home.test.tsx | apps/arkscope-web/src/Home.test.tsx | apps/arkscope-web/src/Home.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/News.test.tsx | apps/arkscope-web/src/News.test.tsx | apps/arkscope-web/src/News.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | apps/arkscope-web/src/SettingsNewsStorage.test.ts | apps/arkscope-web/src/SettingsNewsStorage.test.ts | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | apps/arkscope-web/src/SettingsProviderConfig.test.ts | apps/arkscope-web/src/SettingsProviderConfig.test.ts | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/SettingsStabilizationCss.test.ts | apps/arkscope-web/src/SettingsStabilizationCss.test.ts | apps/arkscope-web/src/SettingsStabilizationCss.test.ts | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | apps/arkscope-web/src/TickerDetail.test.tsx | apps/arkscope-web/src/TickerDetail.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/Universe.test.tsx | apps/arkscope-web/src/Universe.test.tsx | apps/arkscope-web/src/Universe.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/Watchlist.test.tsx | apps/arkscope-web/src/Watchlist.test.tsx | apps/arkscope-web/src/Watchlist.test.tsx | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | apps/arkscope-web/src/marketDataDisplay.test.ts | apps/arkscope-web/src/marketDataDisplay.test.ts | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_agents.py | tests/test_agents.py | tests/test_agents.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_analyst_tools.py | tests/test_analyst_tools.py | tests/test_analyst_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_api.py | tests/test_api.py | tests/test_api.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_app_records_migrate.py | tests/test_app_records_migrate.py | tests/test_app_records_migrate.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_app_records_store.py | tests/test_app_records_store.py | tests/test_app_records_store.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_chatgpt_oauth_driver.py | tests/test_chatgpt_oauth_driver.py | tests/test_chatgpt_oauth_driver.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_claude_code_sdk_driver.py | tests/test_claude_code_sdk_driver.py | tests/test_claude_code_sdk_driver.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_compressor_layer5.py | tests/test_compressor_layer5.py | tests/test_compressor_layer5.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_credential_env_routes.py | tests/test_credential_env_routes.py | tests/test_credential_env_routes.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_data_access.py | tests/test_data_access.py | tests/test_data_access.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_data_scheduler.py | tests/test_data_scheduler.py | tests/test_data_scheduler.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_db_backend.py | tests/test_db_backend.py | tests/test_db_backend.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_db_backend_retired_pg_sa.py | tests/test_db_backend_retired_pg_sa.py | tests/test_db_backend_retired_pg_sa.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_db_backend_retired_prices.py | tests/test_db_backend_retired_prices.py | tests/test_db_backend_retired_prices.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_detailed_financials.py | tests/test_detailed_financials.py | tests/test_detailed_financials.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_eir006_retired_data_boundaries.py | tests/test_eir006_retired_data_boundaries.py | tests/test_eir006_retired_data_boundaries.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_financial_datasets.py | tests/test_financial_datasets.py | tests/test_financial_datasets.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_finnhub_ingestion.py | tests/test_finnhub_ingestion.py | tests/test_finnhub_ingestion.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_fred_ingestion.py | tests/test_fred_ingestion.py | tests/test_fred_ingestion.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_freshness.py | tests/test_freshness.py | tests/test_freshness.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_fundamentals_cache.py | tests/test_fundamentals_cache.py | tests/test_fundamentals_cache.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_fundamentals_sec_cache.py | tests/test_fundamentals_sec_cache.py | tests/test_fundamentals_sec_cache.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_ibkr_gateway_lock.py | tests/test_ibkr_gateway_lock.py | tests/test_ibkr_gateway_lock.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_job_runs.py | tests/test_job_runs.py | tests/test_job_runs.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_legacy_iv_retirement_boundaries.py | tests/test_legacy_iv_retirement_boundaries.py | tests/test_legacy_iv_retirement_boundaries.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_legacy_score_retirement.py | tests/test_legacy_score_retirement.py | tests/test_legacy_score_retirement.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_health.py | tests/test_macro_calendar_health.py | tests/test_macro_calendar_health.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_local_store.py | tests/test_macro_calendar_local_store.py | tests/test_macro_calendar_local_store.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_local_wiring.py | tests/test_macro_calendar_local_wiring.py | tests/test_macro_calendar_local_wiring.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_read.py | tests/test_macro_calendar_read.py | tests/test_macro_calendar_read.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_settings_route.py | tests/test_macro_calendar_settings_route.py | tests/test_macro_calendar_settings_route.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_macro_calendar_store.py | tests/test_macro_calendar_store.py | tests/test_macro_calendar_store.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_macro_scheduler_integration.py | tests/test_macro_scheduler_integration.py | tests/test_macro_scheduler_integration.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_market_coverage_boundaries.py | tests/test_market_coverage_boundaries.py | tests/test_market_coverage_boundaries.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_market_data_admin.py | tests/test_market_data_admin.py | tests/test_market_data_admin.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_market_data_direct.py | tests/test_market_data_direct.py | tests/test_market_data_direct.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_memory_tools.py | tests/test_memory_tools.py | tests/test_memory_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_direct.py | tests/test_news_direct.py | tests/test_news_direct.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_feed_content_route.py | tests/test_news_feed_content_route.py | tests/test_news_feed_content_route.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_normalized_routing.py | tests/test_news_normalized_routing.py | tests/test_news_normalized_routing.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_pg_unreachable.py | tests/test_news_pg_unreachable.py | tests/test_news_pg_unreachable.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_providers.py | tests/test_news_providers.py | tests/test_news_providers.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_news_settings_route.py | tests/test_news_settings_route.py | tests/test_news_settings_route.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_peer_comparison.py | tests/test_peer_comparison.py | tests/test_peer_comparison.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_pg_unreachable_e2e.py | tests/test_pg_unreachable_e2e.py | tests/test_pg_unreachable_e2e.py | test_contract | test_only | retire_pg_only | pg_no_tail | A node in this file proves current local behavior that has no replacement owner. |
| test-contract:tests/test_profile_state.py | tests/test_profile_state.py | tests/test_profile_state.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_provider_health.py | tests/test_provider_health.py | tests/test_provider_health.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_research_routes.py | tests/test_research_routes.py | tests/test_research_routes.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_research_threads.py | tests/test_research_threads.py | tests/test_research_threads.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_article_reconciliation_backend.py | tests/test_sa_article_reconciliation_backend.py | tests/test_sa_article_reconciliation_backend.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_capture_backend.py | tests/test_sa_capture_backend.py | tests/test_sa_capture_backend.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_capture_store.py | tests/test_sa_capture_store.py | tests/test_sa_capture_store.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_comment_focus.py | tests/test_sa_comment_focus.py | tests/test_sa_comment_focus.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_comment_signal_port.py | tests/test_sa_comment_signal_port.py | tests/test_sa_comment_signal_port.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_comment_signals.py | tests/test_sa_comment_signals.py | tests/test_sa_comment_signals.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_digest.py | tests/test_sa_digest.py | tests/test_sa_digest.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_extension_diagnostics.py | tests/test_sa_extension_diagnostics.py | tests/test_sa_extension_diagnostics.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_feed.py | tests/test_sa_feed.py | tests/test_sa_feed.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_local_readers.py | tests/test_sa_local_readers.py | tests/test_sa_local_readers.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_market_news_health.py | tests/test_sa_market_news_health.py | tests/test_sa_market_news_health.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_market_news_recovery.py | tests/test_sa_market_news_recovery.py | tests/test_sa_market_news_recovery.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_reconciliation_native_host.py | tests/test_sa_reconciliation_native_host.py | tests/test_sa_reconciliation_native_host.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_routing.py | tests/test_sa_routing.py | tests/test_sa_routing.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sa_tools.py | tests/test_sa_tools.py | tests/test_sa_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_scheduler_state.py | tests/test_scheduler_state.py | tests/test_scheduler_state.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sec_tools.py | tests/test_sec_tools.py | tests/test_sec_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_sqlite_backend.py | tests/test_sqlite_backend.py | tests/test_sqlite_backend.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_stored_sec_projection.py | tests/test_stored_sec_projection.py | tests/test_stored_sec_projection.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_tools.py | tests/test_tools.py | tests/test_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_trading_day_coverage.py | tests/test_trading_day_coverage.py | tests/test_trading_day_coverage.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_universe_summaries_local.py | tests/test_universe_summaries_local.py | tests/test_universe_summaries_local.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| test-contract:tests/test_web_tools.py | tests/test_web_tools.py | tests/test_web_tools.py | test_contract | test_only | rewrite_current_authority | pg_no_tail | Removing PG names, fixtures, or identity gates weakens a current local behavior assertion. |
| type_gate:src/agents/anthropic_agent/agent.py:isinstance | src/agents/anthropic_agent/agent.py | isinstance | type_gate | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:src/agents/cli.py:isinstance | src/agents/cli.py | isinstance | type_gate | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:src/agents/openai_agent/agent.py:isinstance | src/agents/openai_agent/agent.py | isinstance | type_gate | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:src/tools/data_access.py:isinstance | src/tools/data_access.py | isinstance | type_gate | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:src/tools/freshness.py:isinstance | src/tools/freshness.py | isinstance | type_gate | product_runtime | rewrite_to_local_capability | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_db_backend.py:isinstance | tests/test_db_backend.py | isinstance | type_gate | test_only | retire_pg_only | pg_no_tail | A current consumer reaches this PG-only nominal contract outside the classified caller set. |
| type_gate:tests/test_freshness.py:isinstance | tests/test_freshness.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_job_runs.py:isinstance | tests/test_job_runs.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_market_data_admin.py:isinstance | tests/test_market_data_admin.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_news_pg_unreachable.py:isinstance | tests/test_news_pg_unreachable.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_sa_capture_backend.py:isinstance | tests/test_sa_capture_backend.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |
| type_gate:tests/test_sqlite_backend.py:isinstance | tests/test_sqlite_backend.py | isinstance | type_gate | test_only | rewrite_current_authority | pg_no_tail | A current local contract still requires PostgreSQL nominal identity. |

### Surface counts

| Axis | Value | Count |
|---|---|---|
| kind | archive_asset | 16 |
| kind | cli_entrypoint | 10 |
| kind | dependency | 1 |
| kind | documentation_claim | 159 |
| kind | environment_dependency | 2 |
| kind | inheritance | 8 |
| kind | module_import | 82 |
| kind | route | 2 |
| kind | runtime_config | 27 |
| kind | startup_hook | 1 |
| kind | store_or_backend | 75 |
| kind | test_contract | 83 |
| kind | type_gate | 12 |
| reachability | api_route | 2 |
| reachability | archive_only | 18 |
| reachability | documentation_only | 157 |
| reachability | legacy_agent | 2 |
| reachability | operator | 8 |
| reachability | product_runtime | 181 |
| reachability | scheduler | 6 |
| reachability | startup | 8 |
| reachability | test_only | 96 |

## 5. Measured Consumer Methods

| Surface | Path | Symbol | Local owner | Exact call-site methods |
|---|---|---|---|---|
| inheritance:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py | LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | ["get_available_tickers","get_financial_cache","query_fundamentals","query_health_stats","query_news","query_news_feed","query_news_search","query_news_stats","query_prices","set_financial_cache"] |
| inheritance:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py | SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | ["accept_sa_article_link","apply_sa_refresh","audit_unresolved_symbols","get_sa_article_with_comments","get_sa_pick_detail","get_sa_refresh_meta","invalidate_dirty_sa_market_news_detail","preview_sa_legacy_article_links","query_sa_article_review_queue","query_sa_articles","query_sa_market_news","query_sa_market_news_body_presence","query_sa_market_news_missing_detail_interval","query_sa_market_news_need_detail","query_sa_market_news_recent_ids","query_sa_market_news_recovery_rows","query_sa_picks","reconcile_sa_articles","record_sa_refresh_failure","reject_sa_article_candidate","resolve_sa_reconciliation_event","sanitize_corrupted_sa_comments_counts","save_article_with_comments","save_sa_market_news_detail","update_article_comments","update_sa_pick_detail","upsert_sa_articles_meta","upsert_sa_market_news"] |
| local-capability:src/tools/data_access.py:backend-contract | src/tools/data_access.py | DataAccessLayer._backend | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["accept_sa_article_link","apply_sa_refresh","audit_unresolved_symbols","get_available_tickers","get_sa_article_with_comments","get_sa_pick_detail","get_sa_refresh_meta","invalidate_dirty_sa_market_news_detail","query_fundamentals","query_news","query_news_feed","query_news_search","query_news_stats","query_prices","query_sa_article_review_queue","query_sa_articles","query_sa_market_news","query_sa_market_news_body_presence","query_sa_market_news_missing_detail_interval","query_sa_market_news_need_detail","query_sa_market_news_recent_ids","query_sa_market_news_recovery_rows","query_sa_picks","query_sec_filings","reconcile_sa_articles","record_sa_refresh_failure","reject_sa_article_candidate","resolve_sa_reconciliation_event","sanitize_corrupted_sa_comments_counts","save_article_with_comments","save_sa_market_news_detail","update_article_comments","update_sa_pick_detail","upsert_sa_articles_meta","upsert_sa_market_news"] |
| store_or_backend:data_sources/financial_datasets_client.py:FinancialDatasetsClient._db_get | data_sources/financial_datasets_client.py | FinancialDatasetsClient._db_get | src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | ["get_financial_cache","set_financial_cache"] |
| store_or_backend:src/agents/anthropic_agent/agent.py:get_freshness_summary | src/agents/anthropic_agent/agent.py | _get_freshness_summary | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| store_or_backend:src/agents/cli.py:handle_save_command | src/agents/cli.py | handle_save_command | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| store_or_backend:src/agents/openai_agent/agent.py:get_freshness_prompt | src/agents/openai_agent/agent.py | _get_freshness_prompt | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| store_or_backend:src/macro_calendar/fred_ingestion.py:ingest_full_vintages | src/macro_calendar/fred_ingestion.py | _ingest_full_vintages | src/macro_calendar/local_store.py:MacroCalendarLocalStore | ["is_available","upsert_macro_observation","upsert_macro_series","upsert_release_date"] |
| store_or_backend:src/service/job_runs_store.py:module | src/service/job_runs_store.py | <module> | src/service/job_runs_store.py:JobRunsLocalStore | ["checkpoint_market_news_repair","completed_extension_runs_by_name","create_run","finish_market_news_repair","finish_run","get_market_news_repair","get_runs_by_ids","is_available","latest_runs_by_name","list_runs","mark_market_news_repair_interrupted","record_completed_run","record_extension_event_once","run_summary_by_name","start_market_news_repair","structured_extension_summary_by_name"] |
| store_or_backend:src/service/provider_health.py:databasebackend | src/service/provider_health.py | databasebackend | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["get_sa_refresh_meta","query_health_stats"] |
| store_or_backend:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py | LocalMarketDatabaseBackend | src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend | ["get_available_tickers","get_financial_cache","query_fundamentals","query_health_stats","query_news","query_news_feed","query_news_search","query_news_stats","query_prices","set_financial_cache"] |
| store_or_backend:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py | SACaptureDatabaseBackend | src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend | ["accept_sa_article_link","apply_sa_refresh","audit_unresolved_symbols","get_sa_article_with_comments","get_sa_pick_detail","get_sa_refresh_meta","invalidate_dirty_sa_market_news_detail","preview_sa_legacy_article_links","query_sa_article_review_queue","query_sa_articles","query_sa_market_news","query_sa_market_news_body_presence","query_sa_market_news_missing_detail_interval","query_sa_market_news_need_detail","query_sa_market_news_recent_ids","query_sa_market_news_recovery_rows","query_sa_picks","reconcile_sa_articles","record_sa_refresh_failure","reject_sa_article_candidate","resolve_sa_reconciliation_event","sanitize_corrupted_sa_comments_counts","save_article_with_comments","save_sa_market_news_detail","update_article_comments","update_sa_pick_detail","upsert_sa_articles_meta","upsert_sa_market_news"] |
| store_or_backend:src/tools/freshness.py:module | src/tools/freshness.py | <module> | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| type_gate:src/agents/anthropic_agent/agent.py:isinstance | src/agents/anthropic_agent/agent.py | isinstance | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| type_gate:src/agents/cli.py:isinstance | src/agents/cli.py | isinstance | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| type_gate:src/agents/openai_agent/agent.py:isinstance | src/agents/openai_agent/agent.py | isinstance | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |
| type_gate:src/tools/data_access.py:isinstance | src/tools/data_access.py | isinstance | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["accept_sa_article_link","apply_sa_refresh","audit_unresolved_symbols","get_available_tickers","get_sa_article_with_comments","get_sa_pick_detail","get_sa_refresh_meta","invalidate_dirty_sa_market_news_detail","query_fundamentals","query_news","query_news_feed","query_news_search","query_news_stats","query_prices","query_sa_article_review_queue","query_sa_articles","query_sa_market_news","query_sa_market_news_body_presence","query_sa_market_news_missing_detail_interval","query_sa_market_news_need_detail","query_sa_market_news_recent_ids","query_sa_market_news_recovery_rows","query_sa_picks","query_sec_filings","reconcile_sa_articles","record_sa_refresh_failure","reject_sa_article_candidate","resolve_sa_reconciliation_event","sanitize_corrupted_sa_comments_counts","save_article_with_comments","save_sa_market_news_detail","update_article_comments","update_sa_pick_detail","upsert_sa_articles_meta","upsert_sa_market_news"] |
| type_gate:src/tools/freshness.py:isinstance | src/tools/freshness.py | isinstance | src/tools/backends/local_capabilities.py:LocalDataCapabilities | ["query_health_stats"] |

Only these call-site sets may shape the no-tail local capability. The sole absent owner
is `src/tools/backends/local_capabilities.py:LocalDataCapabilities`; its ceiling is the
35 retained direct `DataAccessLayer` methods after raw `_get_conn` removal.

## 6. Test Contracts and Environment Assumptions

| Suite | Node ID | Surface | Outcome | Role | Environment assumptions |
|---|---|---|---|---|---|
| backend | tests/test_agents.py::TestAgentConfig::test_anthropic_effort_default | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAgentConfig::test_anthropic_thinking_default | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAgentConfig::test_context_management_defaults | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAgentConfig::test_default_config | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAgentConfig::test_get_agent_config | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolExecution::test_execute_calculate_greeks | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_price_change | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_sa_digest_dispatch | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolExecution::test_execute_unknown_tool | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestAnthropicToolSchemas::test_tool_schema_structure | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_call_id_mapping | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_no_raw_responses | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_orphan_output_no_calls | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_tickers_from_list_param | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_typed_call_and_output | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_untyped_fallback_with_call_id | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestExtractToolInfo::test_untyped_output_without_call_id | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestOpenAIMaxTokens::test_model_max_output_lookup | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestOpenAIMaxTokens::test_reasoning_effort_uses_model_max | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestOpenAIMaxTokens::test_reasoning_none_uses_config_max | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestOpenAIToolCreation::test_tools_have_names | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestPrompts::test_system_prompt_exists | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestPrompts::test_system_prompt_mentions_tools | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestRegistrySchemaExport::test_to_anthropic_schema | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_agents.py::TestRegistrySchemaExport::test_to_openai_schema | test-contract:tests/test_agents.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestBridgeIntegration::test_analysis_category_count | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestBridgeIntegration::test_anthropic_includes | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestBridgeIntegration::test_openai_includes | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestBridgeIntegration::test_openai_includes | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestBridgeIntegration::test_registry_total_count | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestConsensus::test_full_aggregation | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestConsensus::test_json_serializable | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestConsensus::test_missing_finnhub_returns_provider_config_missing | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestConsensus::test_ticker_uppercase | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestEarningsHistory::test_4_quarters | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestEarningsHistory::test_empty | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestFinnhubGet::test_200_success | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestFinnhubGet::test_403_graceful | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestFinnhubGet::test_no_api_key | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestFinnhubGet::test_request_error | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestPriceTarget::test_available | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestPriceTarget::test_premium_403 | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestRecommendations::test_basic | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestRecommendations::test_empty | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestUpcomingEarnings::test_found | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_analyst_tools.py::TestUpcomingEarnings::test_no_upcoming | test-contract:tests/test_analyst_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestConfigEndpoints::test_morning_brief | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestConfigEndpoints::test_overview | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestConfigEndpoints::test_sectors | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestConfigEndpoints::test_strategy | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestConfigEndpoints::test_watchlist | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestFundamentalsEndpoints::test_sec_filings | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestHealth::test_status | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestNewsEndpoints::test_get_news | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestNewsEndpoints::test_search_news | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestNewsFeed::test_feed_rejects_invalid_content | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestNewsFeed::test_feed_route_not_captured_by_ticker_route | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestNewsFeed::test_feed_search_and_filters | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestOptionsEndpoints::test_greeks | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestPriceEndpoints::test_get_prices | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestPriceEndpoints::test_price_change | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::TestPriceEndpoints::test_sector_performance | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_fundamentals_stored_source_path_mapping | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_retired_market_admin_and_iv_routes_are_absent_while_greeks_remains_reachable | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_api.py::test_retired_sentiment_and_signal_routes_are_absent_while_raw_news_remains_reachable | test-contract:tests/test_api.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_apply_backs_up_before_write | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_apply_preserves_pg_ids | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_apply_raises_on_insert_failure_atomic_rollback | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_apply_uses_single_source_snapshot | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_backup_refuses_to_overwrite | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_backup_taken_before_ddl | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_full_field_difference_is_conflict_not_skip | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_idempotent_rerun_skips_same_content | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_migrator_scope_excludes_signals | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_partial_overlap_inserts_only_new_ids | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_pg_source_maps_tables | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_pg_source_unavailable_without_get_conn | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_preview_is_readonly_and_classifies | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_route_409_without_pg | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_route_pg_error_becomes_409_not_500 | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_route_preview_and_apply | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_migrate.py::test_same_id_different_content_refuses_before_any_write | test-contract:tests/test_app_records_migrate.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_absent_db_query_is_empty_not_crash | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_agent_query_insert | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_create_false_does_not_materialize_db | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_create_store_makes_missing_parent_dirs | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_dal_local_records_default_is_local | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_end_to_end_save_report_routes_local_when_on | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_factory_explicit_false_still_returns_local_store | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_factory_on_returns_local_store | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_factory_toggleless_dal_routes_local | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_gate4_on_empty_local_is_honest_no_crash | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_memory_insert_query_roundtrip | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_memory_meta_excludes_content_and_delete | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_memory_search_category_importance_order | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_memory_ticker_and_tag_overlap_filter | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_no_pg_dependency | test-contract:tests/test_app_records_store.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_report_filters_ticker_type_days_limit | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_report_insert_query_roundtrip | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_report_metadata_full_dict | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_report_query_empty_has_parity_columns | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_app_records_store.py::test_resolver_no_api_import_and_env_precedence | test-contract:tests/test_app_records_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_call_llm_collects_done_text | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_all_ids_garbage_is_error_seed | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_backend_error_falls_back_to_seed_redacted | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_drops_token_or_pii_shaped_ids | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_empty_ids_is_error_with_seed | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_missing_driver_wiring_is_not_reauth | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_missing_token_requires_reauth | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_models_refresh_401_sets_reauth_error_code | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_models_transient_failure_has_no_error_code | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_no_token_is_missing_credential_seed | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_plain_list_succeeds_without_extra_query | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_refresh_failure_returns_relogin_error_redacted | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_returns_live_ids_as_provider_api | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_discover_uses_refreshed_token | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_identity | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_refresh_failure_message_split_by_reauth | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_refresh_if_needed_delegates_to_login | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_backend_error_only_classifies_auth_rejection_as_reauth[401-reauth_required] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_backend_error_only_classifies_auth_rejection_as_reauth[404-None] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_closes_execution_client_when_consumer_stops_early | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_off_allowlist_tool_errors_without_calling_registry | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_overall_timeout_errors | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_preserves_openai_cached_token_usage | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_returns_tool_timeout_to_model_instead_of_terminal_error | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_runs_allowed_tool_and_continues_without_previous_response_id | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_runs_allowed_tool_and_continues_without_previous_response_id | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_full_reduced_tool_result_to_model_not_ui_preview | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_selected_effort_without_silent_coercion[default-None] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_selected_effort_without_silent_coercion[low-expected2] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_selected_effort_without_silent_coercion[max-expected4] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_selected_effort_without_silent_coercion[none-expected1] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_sends_selected_effort_without_silent_coercion[xhigh-expected3] | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_streams_text_done_and_strips_max_output_tokens | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_uses_last_call_id_when_arguments_done_omits_id | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_llm_uses_last_call_id_when_arguments_done_omits_id | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_missing_driver_wiring_yields_non_reauth_event | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_missing_token_yields_reauth_event | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_stream_refresh_401_event_carries_code | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_test_defers_to_probe_when_token_present | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_chatgpt_oauth_driver.py::test_unauthenticated_without_token | test-contract:tests/test_chatgpt_oauth_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_apikeysource_guard_aborts | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_builds_one_tool_per_allowlisted_name | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_fail_fast_on_missing_registry_tool | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_handler_raises_with_token_is_redacted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_happy_invoke_returns_content | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_input_schema_preserves_optional_args | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_off_allowlist_name_vetoed | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_oversized_result_truncated_with_marker | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_per_tool_timeout | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_bridge_sk_ant_secret_in_result_is_redacted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_build_options_omits_default_reasoning_effort | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_build_options_passes_reasoning_effort_to_claude_sdk | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_call_llm_not_implemented | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_compose_input_empty_is_empty_string | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_compose_input_folds_multi_turn_history_and_drops_system | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_compose_input_single_user_returns_bare_content | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_current_quote_is_research_readonly_allowlisted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_discover_models_static_list | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_done_answer_not_overredacted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_driver_default_max_turns_is_not_hidden_eight | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_eof_without_result_synthesizes_error | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_exactly_one_terminal_stops_after_done | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_get_quota_status_unknown | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_happy_path_mapping | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_implements_research_provider_protocol | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_is_error_result_single_error_terminal | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_is_error_true_but_subtype_success_still_error | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_no_rate_limit_event_means_unknown_without_probe | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_no_token_raises | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_options_config_posture | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_overall_timeout | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_rate_limit_event_snapshot_is_credential_bound_and_redacted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_result_model_usage_aggregates_cache_tokens_when_top_level_missing | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_result_usage_preserves_cache_token_counters | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_sdk_exception_while_streaming | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_stream_event_is_ignored_but_rate_limit_event_is_persisted | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_stream_folds_multi_turn_prompt_into_query | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_stream_removes_temp_config_dir | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_test_missing_credential_without_token | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_test_returns_non_ok_without_live_call | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_thinking_block_maps_to_thinking_content | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_token_in_env_not_in_events | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_token_never_read_from_credential_secret | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_tool_end_is_error_flag_is_not_terminal | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_zero_max_turns_omits_sdk_max_turns | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_claude_code_sdk_driver.py::test_zero_timeout_disables_overall_timeout | test-contract:tests/test_claude_code_sdk_driver.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestAnthropicSummaryCaller::test_concatenates_text_blocks | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestAnthropicSummaryCaller::test_empty_response_returns_none | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestAnthropicSummaryCaller::test_failure_returns_none_not_raise | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_caps_tickers_and_record_ids | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_empty_messages_returns_empty_dict | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_extracts_record_ids_from_tool_result_markers | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_extracts_ticker_from_tool_use_blocks | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_extracts_tickers_list_from_tool_use | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestBuildAnchorFromMessages::test_messages_without_tickers_or_records_returns_empty | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCapSummary::test_char_cap_is_hard | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCapSummary::test_no_cap_for_compliant_summary | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCapSummary::test_word_cap_truncates_with_marker | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_armed_when_master_enabled | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_armed_when_master_enabled | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_idempotent_when_already_armed | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_idempotent_when_already_armed | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_rejected_for_openai_provider | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_rejected_for_openai_provider | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_rejected_when_master_disabled | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_compact_rejected_when_master_disabled | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestCompactCommand::test_force_flag_still_builds_summary_caller_when_layer5_disabled | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestDetachHelpers::test_detach_anchor_no_op_when_not_present | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestDetachHelpers::test_detach_anchor_strips_tail | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestDetachHelpers::test_detach_recognises_compaction_summary | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestDetachHelpers::test_detach_recognises_scratchpad_summary | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestForceLayer5Flag::test_force_flag_cleared_when_caller_missing | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestForceLayer5Flag::test_force_flag_cleared_when_circuit_open | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestForceLayer5Flag::test_force_flag_cleared_when_master_disabled | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestForceLayer5Flag::test_force_flag_consumed_on_success | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Firing::test_circuit_breaker_after_3_failures | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Firing::test_circuit_resets_on_success | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Firing::test_layer_5_default_off | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Firing::test_layer_5_fires_when_enabled_and_threshold_exceeded | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Firing::test_noop_does_not_burn_circuit_breaker | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Idempotency::test_prior_summary_passed_to_caller | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Idempotency::test_repeated_compact_does_not_stack_summaries | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Prompt::test_prompt_forbids_reasoning_passthrough | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Prompt::test_prompt_locks_record_id_preservation | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Prompt::test_render_transcript_includes_prior_summary_tag | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer5Prompt::test_seven_sections_present_in_system_prompt | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer6Anchor::test_anchor_appended_with_tickers_and_record_ids | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer6Anchor::test_anchor_block_under_1kb | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer6Anchor::test_anchor_no_op_for_data_without_useful_keys | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer6Anchor::test_anchor_no_op_for_empty_data | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestLayer6Anchor::test_anchor_not_counted_as_user_turn | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestMarkerWrappers::test_wrap_anchor_idempotent | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestMarkerWrappers::test_wrap_compaction_summary_idempotent | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestPrefixReplacementBoundary::test_replace_prefix_to_out_of_range_is_noop | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestPrefixReplacementBoundary::test_replace_prefix_to_zero_is_noop | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestReasoningPassthrough::test_projection_does_not_paraphrase_thinking_as_assistant_text | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestReasoningPassthrough::test_projection_handles_dict_form_thinking | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestReasoningPassthrough::test_projection_renders_redacted_thinking_as_dropped | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestReasoningPassthrough::test_summary_caller_output_attached_as_user_summary_not_reasoning | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestRequestForceLayer5::test_returns_false_when_no_compressor | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestRequestForceLayer5::test_returns_true_and_sets_flag | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestSafeNativeCut::test_back_up_for_tool_result_group | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestSafeNativeCut::test_no_back_up_at_index_zero | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestSafeNativeCut::test_no_back_up_for_attachment_user_msg | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_compressor_layer5.py::TestSafeNativeCut::test_no_back_up_for_plain_user_text | test-contract:tests/test_compressor_layer5.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_refused_when_apply_disabled | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_refuses_symlink_to_arbitrary_file | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_refuses_symlink_to_live_env | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_refuses_to_clobber_live_env | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_rejects_blank_path | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_export_env_route_writes_0600_and_returns_labels | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_import_env_route_dry_run_previews_without_writing | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_import_env_route_real_writes_and_gates | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_import_env_route_refuses_real_write_when_apply_disabled | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_update_route_key_oauth_switch_both_directions | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_update_route_key_to_key_switch_keeps_single_active | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_credential_env_routes.py::test_update_route_oauth_metadata_label_and_expiry | test-contract:tests/test_credential_env_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestBackendProtocol::test_file_backend_is_data_backend | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestCache::test_cache_clear | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestCache::test_cache_miss | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestCache::test_cache_store_and_retrieve | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_all_sectors | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_sector_tickers | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_strategy_weights | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_strategy_weights_default | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_watchlist | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_watchlist_has_details | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestConfigAccess::test_get_watchlist_sectors | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestFundamentals::test_fundamentals_empty_ticker | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestNews::test_get_news_ibkr_source | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestNews::test_get_news_polygon_source | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestNews::test_get_news_ticker | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestNews::test_news_article_schema | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestPrices::test_get_prices_df | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestPrices::test_price_bar_schema | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_access.py::TestSECFilings::test_get_sec_filings_empty | test-contract:tests/test_data_access.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_adapter_gets_universe_tickers_and_progress | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_adapter_universe_unavailable_fails_loud | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_blocked_news_route_fails_despite_stale_normalized_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_default_ibkr_legacy_news_route_does_not_launch_collector | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_default_ibkr_legacy_news_route_fails_before_pg_sync | test-contract:tests/test_data_scheduler.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_defaults_everything_disabled | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_failed_manual_normalized_continuation_preserves_pending | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_get_schedule_snapshot_shape | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_backlog_unavailable_is_partial_without_fake_zero | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_gateway_serializes_across_processes | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_legacy_local_route_is_retired_before_collector_sync_and_mirror | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_lock_skip_does_not_leave_durable_running | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_news_fails_closed_when_pg_exit_audit_cannot_be_read | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_news_worker_lock_busy_payload_is_skip_not_failure | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_news_worker_stdout_parse_preserves_retryable_lock_busy | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_retry_failure_persists_partial_without_manual_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_sources_serialize_behind_gateway_lock | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_ibkr_success_persists_scheduled_backlog_without_partial | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_is_due_matrix | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_last_result_surfaces_skips_in_snapshot | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_legacy_local_news_route_runs_despite_stale_normalized_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_legacy_news_route_local_keeps_direct_writer_without_pg_or_mirror | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_legacy_news_route_pg_fails_before_collector_sync_and_mirror | test-contract:tests/test_data_scheduler.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_manual_normalized_body_continuation_does_not_require_active_scope | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_market_writer_backpressure_is_not_failed | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_news_write_mode_classifier_is_exhaustive_for_current_modes | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_no_active_runtime_source_uses_migrate_to_supabase_sync | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_ibkr_news_route_launches_isolated_worker_without_pg_or_mirror | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_ibkr_worker_failure_hides_raw_child_stderr | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_ibkr_worker_invalid_stdout_is_generic_failure | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_ibkr_worker_partial_stdout_marks_scheduler_partial | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_lock_busy_is_retryable_skip | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_manual_trigger_passes_pending_continuation_and_clears_it | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_partial_without_continuation_stays_partial | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_route_calls_writer_under_market_lock[finnhub_news-finnhub-src.collectors.finnhub_news-FinnhubConfig-FinnhubNewsCollector-FinnhubNormalizedProvider] | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_route_calls_writer_under_market_lock[polygon_news-polygon-src.collectors.polygon_news-CollectionConfig-PolygonNewsCollector-PolygonNormalizedProvider] | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_route_preserves_writer_partial_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_normalized_news_scheduler_skips_pending_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_p0c1_ibkr_prices_runs_prices_worker_subprocess | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync | test-contract:tests/test_data_scheduler.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_pg_reachable_probe_is_bounded | test-contract:tests/test_data_scheduler.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_post_exit_blocked_news_route_fails_closed_and_records_failure | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_when_profile_store_unavailable | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_worker_without_pg_or_mirror | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_price_partial_projection_does_not_change_normalized_news_audit_status | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_price_scope_required | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_failed_payload_persists_failed_without_partial | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_gateway_failure_persists_typed_diagnostic | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_success_clears_prior_partial_and_preserves_audit_history | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_worker_stdout_parse_preserves_retryable_and_counts | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_worker_stdout_parser_preserves_allowlisted_gateway_code | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_prices_worker_stdout_parser_rejects_malformed_partial_payloads | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_put_schedule_validates | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_reconcile_interrupted_runtime_state_marks_local_running_rows | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_now_fires_background_and_skips_running | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_adapter_failure_short_circuits | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_explicit_tickers_reaches_active_adapter_without_mirror_controls | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_failure_persists_error_locally | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_never_raises | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_news_direct_when_use_local_news_on | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_persists_attempt_and_outcome_to_local_state | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_provider_config_missing_returns_not_configured | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_refuses_provider_work_when_provider_config_setup_required | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_releases_file_locks | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_skips_when_already_running | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_run_source_skips_when_running_in_another_process | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_sanitized_ibkr_news_worker_parser_preserves_gateway_unavailable_code | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_sanitized_ibkr_news_worker_timeout_returns_failed_payload | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_schedule_routes_reject_removed_source_ids_before_writes_or_provider_work | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_schedule_status_exposes_post_pg_exit_presentation_metadata | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_scheduler_passes_market_lock_factory_to_normalized_news_writer | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_scheduler_runtime_no_longer_references_migrate_to_supabase_script | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_scheduler_source_defs_have_no_legacy_collector_plumbing | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_seed_last_attempts_from_local_state | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_seed_skipped_fast_when_pg_unreachable | test-contract:tests/test_data_scheduler.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_set_config_roundtrip_and_clamp | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_set_config_unknown_source | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_skip_does_not_overwrite_durable_outcome | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_stale_legacy_pg_news_route_is_retired_before_sync | test-contract:tests/test_data_scheduler.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_startup_burst_defers_all_extra_market_writers | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_status_snapshot_marks_stale_running_durable_state | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_status_snapshot_provider_fetch_tracks_live_fetch_paths | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_tick_fires_only_enabled_and_due | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_tick_once_defers_extra_market_writers | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_unknown_news_write_mode_fails_before_provider_adapter_worker_and_telemetry | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_v14a_status_snapshot_no_create_on_fresh_db | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_worker_stdout_parse_preserves_entitlement_block_count | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_worker_stdout_parse_preserves_retry_legs_and_body_backlog | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_worker_stdout_parser_rejects_malformed_body_backlog_values | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_data_scheduler.py::test_worker_stdout_parser_rejects_malformed_entitlement_block_count | test-contract:tests/test_data_scheduler.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_db_backend.py::TestAvailableTickersDB::test_fundamentals_tickers | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestAvailableTickersDB::test_news_tickers | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestBackendProtocol::test_backend_type | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestBackendProtocol::test_db_backend_is_data_backend | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestDALBackendSwitch::test_both_backends_same_schema | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestDALBackendSwitch::test_dal_auto_mode | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestDALBackendSwitch::test_dal_auto_mode | type_gate:tests/test_db_backend.py:isinstance | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestDALBackendSwitch::test_dal_default_is_file | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestDALBackendSwitch::test_dal_explicit_dsn | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_empty_ticker | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_via_dal | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestFundamentalsDB::test_query_fundamentals | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestNewsDB::test_news_schema_via_dal | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestNewsDB::test_query_news_all | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestNewsDB::test_query_news_source_filter | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestNewsDB::test_query_news_ticker | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestPricesDB::test_available_price_tickers | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::TestPricesDB::test_query_prices | test-contract:tests/test_db_backend.py | skipped | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::test_auto_dal_survives_fresh_checkout_without_base | test-contract:tests/test_db_backend.py | passed | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::test_query_health_stats_is_retired_after_batch3 | test-contract:tests/test_db_backend.py | passed | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::test_query_prices_is_retired_after_batch3 | test-contract:tests/test_db_backend.py | passed | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend.py::test_retired_pg_domain_methods_do_not_query_dropped_tables | test-contract:tests/test_db_backend.py | passed | pg_only | ["requires_database_url","requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_pg_sa.py::test_retired_pg_sa_methods_do_not_connect | test-contract:tests/test_db_backend_retired_pg_sa.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_prices.py::test_app_record_archive_methods_are_not_removed_by_batch3 | test-contract:tests/test_db_backend_retired_prices.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_prices.py::test_file_backend_prices_and_fundamentals_are_empty_without_path_probes | test-contract:tests/test_db_backend_retired_prices.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_prices.py::test_price_ticker_listing_is_retired_stub_after_batch3 | test-contract:tests/test_db_backend_retired_prices.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_prices.py::test_query_health_stats_no_longer_queries_prices_after_batch3 | test-contract:tests/test_db_backend_retired_prices.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_db_backend_retired_prices.py::test_query_prices_is_retired_stub_after_batch3 | test-contract:tests/test_db_backend_retired_prices.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_full_creation | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_minimal_creation | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_model_dump | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestFinancialCache::test_cache_miss_returns_none | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestFinancialCache::test_pg_cache_hit_path_is_retired | test-contract:tests/test_detailed_financials.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_data_source_remains_static_sec_source | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_legacy_ibkr_snapshot_cannot_override_sec_or_price_basis | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_no_qualified_price_preserves_static_and_nulls_dynamic_fields | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_old_metrics_cache_key_is_ignored | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_returns_detailed_financials_type | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_static_cache_hit_recomputes_dynamic_metrics_without_static_refetch | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestGetDetailedFinancials::test_v2_static_cache_excludes_price_and_dynamic_fields | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestLiveTechMetrics::test_nvda_tech_metrics | test-contract:tests/test_detailed_financials.py | skipped | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestTechMetrics::test_empty_statements | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestTechMetrics::test_no_revenue_returns_none | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestTechMetrics::test_rd_to_revenue | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestTechMetrics::test_rule_of_40 | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_detailed_financials.py::TestTechMetrics::test_sbc_to_revenue | test-contract:tests/test_detailed_financials.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_eir006_retired_data_boundaries.py::test_current_docs_training_and_tool_copy_name_only_current_authorities | test-contract:tests/test_eir006_retired_data_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_eir006_retired_data_boundaries.py::test_current_runtime_consumer_census_is_closed_and_exact | test-contract:tests/test_eir006_retired_data_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestBuildResult::test_builds_from_statements | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestBuildResult::test_empty_statements_returns_minimal | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestCacheBackendMode::test_api_result_written_to_backend_only | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestCacheBackendMode::test_backend_hit_skips_api | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestCacheBackendMode::test_backend_without_cache_methods_is_ignored | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestCacheBackendMode::test_backend_write_failure_falls_back_to_file | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestCacheBackendMode::test_file_hit_promoted_to_backend | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFDFallbackConditions::test_fd_disabled_in_config | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFDFallbackConditions::test_fd_disabled_no_api_key | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFDFallbackConditions::test_fd_enabled_with_key_and_config | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_api_call_returns_dataclass | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_api_error_returns_empty | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_balance_sheet_returns_dataclass | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_cache_expired_calls_api | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_cache_hit_skips_api | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_extra_fields_ignored | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_financial_datasets.py::TestFinancialDatasetsClient::test_no_api_key_returns_empty | test-contract:tests/test_financial_datasets.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_401_raises_finnhub_error | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_429_raises_finnhub_error | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_500_raises_finnhub_error | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_earnings_events_no_symbol_omits_param | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_earnings_events_threads_symbol_param | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_economic_events_parses_rows | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_economic_events_skips_bad_rows | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_economic_events_threads_date_range | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_ipo_events_parses_status_and_null_exchange | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestClientHttpShape::test_token_in_every_request | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsDispatcher::test_default_window_today_to_plus30 | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsDispatcher::test_empty_watchlist_falls_back_to_unfiltered | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsDispatcher::test_explicit_symbols_override_watchlist | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsDispatcher::test_uses_watchlist_when_no_symbols_param | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_invalid_quarter_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_missing_date_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_missing_symbol_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_parses_full_row | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_symbol_uppercased | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsFromJson::test_unknown_hour_normalised | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsIngestion::test_deduplicates_same_symbol_year_quarter | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsIngestion::test_maps_camelcase_to_snake_case_in_payload | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsIngestion::test_no_symbols_issues_one_unfiltered_call | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEarningsIngestion::test_per_symbol_issues_one_call_per_symbol | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicBackfillDispatcher::test_default_years_back_is_one | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicBackfillDispatcher::test_explicit_from_date_overrides_years_back | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicBackfillDispatcher::test_years_back_param_widens_window | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicBackfillDispatcher::test_zero_years_back_raises | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_country_uppercased | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_missing_country_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_missing_event_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_missing_time_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_null_actual_becomes_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_parses_full_row | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_unit_empty_string_preserved | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicFromJson::test_unknown_impact_normalised_to_empty | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicIngestion::test_api_error_recorded_in_stats | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicIngestion::test_calls_store_with_correct_payload | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicIngestion::test_counts_inserted_mutated_unchanged | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicIngestion::test_filebackend_uses_local_macro_store_not_unavailable | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicIngestion::test_store_exception_increments_skipped | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicRecentDispatcher::test_default_window_is_minus7_plus14 | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicRecentDispatcher::test_explicit_dates_override_defaults | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicRecentDispatcher::test_invalid_iso_date_raises | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestEconomicRecentDispatcher::test_to_before_from_raises | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubIngestionLocalWrite::test_economic_ingestion_writes_local_macro_calendar_db | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobDefinitions::test_disabled_reports_availability_reason | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobDefinitions::test_jobs_present_when_macro_calendar_enabled | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobSummaries::test_summary_for_backfill_uses_event_keys | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobSummaries::test_summary_for_earnings_with_errors | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobSummaries::test_summary_for_economic_recent | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobSummaries::test_summary_for_ipo_unchanged_only | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestFinnhubJobSummaries::test_unknown_result_shape_falls_back_to_generic | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIPOIngestion::test_api_error_recorded | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIPOIngestion::test_calls_store_with_correct_payload | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIPOIngestion::test_camelcase_fields_mapped_correctly | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIPOIngestion::test_revision_action_counted | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoDispatcher::test_default_window_minus30_plus90 | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoDispatcher::test_explicit_dates_threaded | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_empty_exchange_becomes_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_invalid_status_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_missing_date_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_missing_name_yields_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_null_symbol_becomes_none | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_parses_full_row | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestIpoFromJson::test_status_lowercased | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestNormalizeImpactHour::test_unknown_hour_becomes_empty | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestNormalizeImpactHour::test_unknown_impact_becomes_empty | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestNormalizeImpactHour::test_valid_hour_lowercased | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestNormalizeImpactHour::test_valid_impact_lowercased | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestParseFinnhubTime::test_fomc_19_utc | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestParseFinnhubTime::test_returns_none_for_empty | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_finnhub_ingestion.py::TestParseFinnhubTime::test_returns_none_for_malformed | test-contract:tests/test_finnhub_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestCatalogLoad::test_default_catalog_has_v1_series | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestCatalogLoad::test_full_vintages_strategy_used_for_GDP | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestCatalogLoad::test_latest_only_strategy_used_for_CPIAUCNS | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_429_raises_FREDError | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_dot_in_value_becomes_none | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_get_observations_includes_token_and_file_type | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_get_observations_threads_vintages | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_get_release_dates_parses_rows | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_get_series_metadata_offset_aware | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_no_output_type_omits_param | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_output_type_sent_as_param | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientHttpShape::test_unsupported_output_type_raises_value_error | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientParsers::test_offset_aware_parse_handles_minus_05 | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientParsers::test_offset_aware_parse_promotes_naive_to_utc | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientParsers::test_offset_aware_parse_returns_none_for_empty | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestClientParsers::test_value_dot_becomes_none | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestFredIngestionLocalWrite::test_fred_series_ingestion_writes_local_store | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestFullVintagesIngestion::test_full_vintages_passes_full_alfred_window_to_client | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestFullVintagesIngestion::test_full_vintages_uses_output_type_real_time_period | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestFullVintagesIngestion::test_writes_one_row_per_realtime_window | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDefinitions::test_disabled_reports_availability_reason | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDefinitions::test_jobs_present_when_macro_calendar_enabled | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDispatchers::test_run_fetch_fred_release_dates_calls_ingestion | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDispatchers::test_run_fetch_fred_release_dates_rejects_zero_limit | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDispatchers::test_run_fetch_fred_release_dates_threads_limit | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobDispatchers::test_run_fetch_fred_series_threads_full_refresh | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobSummaries::test_summary_for_release_dates | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestJobSummaries::test_summary_for_series_includes_skipped_obs | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestLatestOnlyIngestion::test_latest_only_passes_each_row_to_store | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestLatestOnlyIngestion::test_latest_only_passes_full_alfred_window_to_client | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestLatestOnlyIngestion::test_latest_only_uses_output_type_initial_release | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestLatestOnlyIngestion::test_uses_FRED_realtime_start_authoritatively | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestRealtimeChunking::test_incremental_latest_only_stays_single_window | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestRealtimeChunking::test_latest_only_full_refresh_bisects_under_vintage_cap | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestRealtimeChunking::test_pre_alfred_window_tolerated_as_empty | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestRealtimeChunking::test_right_spine_keeps_9999_not_local_today | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDateIngestion::test_explicit_limit_overrides_catalog | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDateIngestion::test_fetches_from_catalog_release_ids | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDateIngestion::test_skips_null_release_id | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDateIngestion::test_uses_catalog_lookback_for_page_size | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDatesPageSize::test_caps_at_1000_for_long_lookback | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDatesPageSize::test_default_when_no_catalog | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestReleaseDatesPageSize::test_short_lookback_returns_proportional_size | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fred_ingestion.py::TestUnavailableDal::test_filebackend_uses_local_macro_store_not_unavailable | test-contract:tests/test_fred_ingestion.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestCheckDataFreshness::test_file_backend | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestCheckDataFreshness::test_no_backend_attr | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessFormat::test_format_detailed | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessFormat::test_format_detailed_empty | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessFormat::test_format_summary | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessFormat::test_format_summary_empty | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_cache_hit | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_force_bypass_cache | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_fresh_data | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_no_backend | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_no_data | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_query_error | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_stale_news | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestFreshnessRegistryScan::test_scan_total_failure | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestParseTs::test_datetime_with_tz | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestParseTs::test_datetime_without_tz | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestParseTs::test_none | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestParseTs::test_string_date | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_get_registry_creates | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_get_registry_creates | type_gate:tests/test_freshness.py:isinstance | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_get_registry_none_before_init | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_get_registry_none_returns_current | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_get_registry_reuses | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSingleton::test_reset_for_tests | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_freshness.py::TestSourceHealth::test_defaults | test-contract:tests/test_freshness.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_cache.py::test_fundamentals_analysis_cache_key_is_stable | test-contract:tests/test_fundamentals_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_ignores_incompatible_payload | test-contract:tests/test_fundamentals_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_recognizes_negative_cache | test-contract:tests/test_fundamentals_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_returns_empty_on_miss | test-contract:tests/test_fundamentals_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_cache.py::test_read_cached_sec_fundamentals_uses_local_market_store_without_pg_fallback | test-contract:tests/test_fundamentals_cache.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_annual_analysis_ignores_legacy_snapshot_and_preserves_sec_fd_order | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_sec_cache_hit_with_local_market_backend_does_not_pg_fallback | test-contract:tests/test_fundamentals_sec_cache.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_sec_cache_miss_then_hit_round_trips_result | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_sec_cache_miss_writes_with_shared_cache_key | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_sec_empty_uses_short_negative_cache | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_sec_result_is_cached_then_served_from_cache | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_user_agent_back_compat_legacy_vars | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_fundamentals_sec_cache.py::test_user_agent_prefers_canonical_arkscope_var | test-contract:tests/test_fundamentals_sec_cache.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_context_manager_acquires_and_releases | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_filelock_cross_process_dir_resolution | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_mutual_exclusion_serializes_two_threads | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_scheduler_shares_the_same_objects | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_second_acquire_times_out_while_held | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_ibkr_gateway_lock.py::test_thread_lock_released_even_if_file_lock_times_out | test-contract:tests/test_ibkr_gateway_lock.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_create_run_returns_inserted_id | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_create_run_swallows_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_extension_record_endpoint_derives_complete_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_extension_record_endpoint_maps_degraded_to_failed | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_extension_record_endpoint_maps_skipped_to_typed_succeeded | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_extension_record_endpoint_records_via_store_factory | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_extension_record_endpoint_rejects_invalid_protocol_or_reason | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_finish_run_rejects_running_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_finish_run_rejects_unknown_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_finish_run_returns_false_when_run_id_none | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_finish_run_swallows_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_finish_run_updates_row | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_get_job_runs_store_explicit_false_uses_local_after_n9 | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_get_job_runs_store_explicit_false_uses_local_after_n9 | type_gate:tests/test_job_runs.py:isinstance | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_get_job_runs_store_uses_profile_toggle_for_local | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_get_job_runs_store_uses_profile_toggle_for_local | type_gate:tests/test_job_runs.py:isinstance | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_jobs_history_endpoint_returns_empty_when_unavailable | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_jobs_history_endpoint_returns_rows_from_store | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_jobs_history_endpoint_uses_store_factory | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_latest_runs_by_name_keys_by_job_name | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_latest_runs_by_name_swallows_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_list_jobs_status_falls_back_to_process_local_when_db_empty | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_list_jobs_status_falls_back_when_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_list_jobs_status_uses_db_latest_when_available | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_list_runs_clamps_limit_and_offset | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_list_runs_returns_serialized_rows | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_create_finish_and_latest | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_duplicate_event_returns_existing_run_id | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_finish_run_computes_duration_when_omitted | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_list_runs_filters_by_trigger_source | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_record_completed_preserves_ids_and_payload | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_records_client_event_once_inside_immediate_transaction | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_rejects_event_id_reuse_with_different_hash | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_rolls_back_invalid_event_without_partial_row | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_local_store_run_summary_distinguishes_latest_success_and_latest_any | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_native_host_does_not_construct_job_runs_store_or_profile_writer | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_native_host_record_extension_job_degrades_when_sidecar_unreachable | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_native_host_record_extension_job_posts_to_sidecar | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_read_job_activity_if_exists_distinguishes_relevant_and_unrelated_rows | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_read_job_activity_if_exists_missing_profile_is_none_and_no_create | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_read_job_activity_if_exists_missing_table_is_none_and_no_mutation | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_read_job_activity_if_exists_unreadable_or_malformed_is_unknown | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_inserts_terminal_row | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_omits_finished_at_when_not_provided | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_rejects_running_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_rejects_unknown_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_returns_none_when_unavailable | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_completed_run_swallows_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_extension_job_dispatched_via_handle_message | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_extension_job_rejects_caller_supplied_status | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_extension_job_rejects_missing_job_name | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_record_extension_job_rejects_missing_started_at | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_job_continues_when_create_run_returns_none | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_job_persists_failure | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_job_persists_start_and_finish_on_success | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_summary_by_name_returns_none_on_db_error | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_summary_by_name_uses_single_row_cursor_shape | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_telemetry_disabled_is_inert | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_telemetry_records_terminal_rows | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_run_telemetry_store_failure_never_breaks_the_step | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_sa_store_activity_job_names_cover_all_current_authorities | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_sa_store_history_contract_has_no_pruning_or_time_cutoff | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_serialize_row_converts_datetimes | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_store_available_with_database_backend | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_store_unavailable_with_filebackend | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_store_unavailable_with_no_backend | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_structured_extension_summary_separates_latest_attempt_from_latest_complete | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_summarize_handles_non_dict | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_summarize_monitor_scan_result | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_job_runs.py::test_summarize_unknown_job_falls_back | test-contract:tests/test_job_runs.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_iv_retirement_boundaries.py::test_current_runtime_has_no_legacy_iv_storage_or_api_owner | test-contract:tests/test_legacy_iv_retirement_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_iv_retirement_boundaries.py::test_non_migration_scripts_do_not_read_legacy_iv_store | test-contract:tests/test_legacy_iv_retirement_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_iv_retirement_boundaries.py::test_retained_option_capabilities_do_not_import_legacy_iv_store | test-contract:tests/test_legacy_iv_retirement_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_iv_retirement_boundaries.py::test_sql_init_and_current_backends_have_no_legacy_iv_schema | test-contract:tests/test_legacy_iv_retirement_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_current_authorities_make_no_legacy_capability_claim | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_fresh_schemas_create_no_legacy_score_storage | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_model_visible_contracts_exclude_legacy_score_and_composite_capabilities | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_ordinary_news_contract_has_no_legacy_score_fields | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_provider_native_sentiment_and_investor_risk_contracts_are_preserved | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_raw_news_backend_contract_has_no_score_parameters | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_runtime_legacy_score_consumer_writer_census_is_closed_and_empty | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_legacy_score_retirement.py::test_scoring_scripts_and_root_package_are_absent | test-contract:tests/test_legacy_score_retirement.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestBackfillOneShot::test_old_backfill_clean_history_is_ok | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestBackfillOneShot::test_old_backfill_with_recent_failure_warns | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestDbUnavailable::test_backend_query_failure_degrades_gracefully | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestDbUnavailable::test_job_runs_query_uses_store_factory | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestDbUnavailable::test_no_backend_returns_critical_with_full_shape | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestEvaluateHappyPath::test_all_fresh_returns_ok | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestEvaluateHappyPath::test_evaluated_at_carries_utc | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestEvaluateHappyPath::test_thresholds_visible_in_response | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobNeverRun::test_backfill_never_run_can_be_muted_to_ok | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobNeverRun::test_backfill_never_run_is_warning_not_critical | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobNeverRun::test_failed_but_never_succeeded_is_critical | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobNeverRun::test_periodic_job_never_run_warns | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobStaleness::test_job_stale_critical_threshold | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobStaleness::test_job_stale_warning_offhours | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobStaleness::test_other_jobs_no_market_hours_upgrade | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobStaleness::test_recent_job_market_hours_upgrades_warning_to_critical | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestJobStaleness::test_recent_job_within_cadence_ok | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMacroCalendarHealthRoute::test_default_returns_200_with_payload | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMacroCalendarHealthRoute::test_disabled_macro_calendar_returns_503 | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMacroCalendarHealthRoute::test_strict_with_ok_stays_200 | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMacroCalendarHealthRoute::test_strict_with_warning_returns_503 | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMarketHoursDetection::test_naive_input_treated_as_utc | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMarketHoursDetection::test_saturday_is_false | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMarketHoursDetection::test_weekday_market_hours_is_true | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestMarketHoursDetection::test_weekday_off_hours_is_false | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestPeriodicRecentFailure::test_fresh_success_with_recent_failure_warns | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestPeriodicRecentFailure::test_periodic_success_only_no_failure_is_ok | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestPeriodicRecentFailure::test_stale_critical_with_recent_failure_keeps_critical | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestTableCoverage::test_empty_table_is_warning | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestTableCoverage::test_null_fetched_at_with_rows_is_critical | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_health.py::TestTableCoverage::test_stale_table_warning | test-contract:tests/test_macro_calendar_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_check_constraints_reject_invalid_enums | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_earnings_baseline_mutate | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_economic_baseline_mutate_unchanged | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_economic_default_observed_at_distinct_revisions | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_economic_numeric_coercion_no_false_mutation | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_economic_read_as_of_vintage | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_empty_db_honest_empty | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_fetched_at_present_on_all_health_tables | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_fk_cascade_deletes_revisions | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_get_macro_observations_current_and_as_of | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_health_table_stats_query_shape | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_ipo_baseline_unchanged | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_list_earnings_events | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_list_economic_events_as_of_excludes_unobserved | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_list_economic_events_canonical_and_filters | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_list_ipo_events_as_of_status_filter | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_macro_observation_realtime_start_mandatory | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_macro_observation_requires_parent_series | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_macro_observation_vintage_window | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_macro_observations_has_surrogate_id_and_fk | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_macro_series_roundtrip | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_no_pg_dependency | test-contract:tests/test_macro_calendar_local_store.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_not_null_parity_with_pg | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_release_dates | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_store.py::test_source_payload_json_roundtrip | test-contract:tests/test_macro_calendar_local_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_wiring.py::test_dal_local_macro_toggle_default_off_and_env | test-contract:tests/test_macro_calendar_local_wiring.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_wiring.py::test_factory_returns_local_store_when_toggle_off_after_n9 | test-contract:tests/test_macro_calendar_local_wiring.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_wiring.py::test_factory_returns_local_store_when_toggle_on | test-contract:tests/test_macro_calendar_local_wiring.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_wiring.py::test_health_local_first_without_pg | test-contract:tests/test_macro_calendar_local_wiring.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_local_wiring.py::test_local_store_table_stats | test-contract:tests/test_macro_calendar_local_wiring.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEarningsAndIpoRoutes::test_earnings_threads_symbols_csv | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEarningsAndIpoRoutes::test_ipo_threads_status_csv | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_as_of_date_only_maps_to_eod_utc | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_as_of_threaded_through | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_default_window_reaches_store | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_disabled_returns_503 | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_invalid_iso_date_returns_400 | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_same_day_window_covers_full_day | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestEconomicCalendarRoute::test_to_before_from_returns_400 | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_date_only_as_of_passes_eod_to_store | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_disabled_returns_helpful_string | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_filebackend_dal_returns_local_empty_message | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_formats_event_rows | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_invalid_as_of_returns_error | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetEconomicCalendarTool::test_no_rows_message | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetMacroValueTool::test_found_value_formatted | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetMacroValueTool::test_invalid_observation_date | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetMacroValueTool::test_no_observation_with_as_of_explains_unknown | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetMacroValueTool::test_refresh_disabled_still_reads_local_macro_value | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestGetMacroValueTool::test_unknown_series | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_macro_series_readable_when_refresh_disabled | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_returns_metadata_plus_observations | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_series_id_uppercased | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_snapshot_readable_when_refresh_disabled | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_unknown_series_returns_404 | test-contract:tests/test_macro_calendar_read.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_settings_route.py::test_local_first_active_when_toggle_on_even_if_db_absent | test-contract:tests/test_macro_calendar_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_settings_route.py::test_put_settings_persists_toggle | test-contract:tests/test_macro_calendar_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_settings_route.py::test_status_db_absent_is_honest_and_does_not_create | test-contract:tests/test_macro_calendar_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_settings_route.py::test_status_reflects_setting_and_env_and_coverage | test-contract:tests/test_macro_calendar_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_settings_route.py::test_status_settings_not_gated_by_macro_calendar_enabled | test-contract:tests/test_macro_calendar_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestAvailability::test_unavailable_with_filebackend | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestAvailability::test_unavailable_with_no_backend | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestBaselineOnFirstInsert::test_earnings_first_insert_writes_baseline | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestBaselineOnFirstInsert::test_economic_first_insert_writes_canonical_and_baseline_revision | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestBaselineOnFirstInsert::test_ipo_first_insert_writes_baseline | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_earnings_fingerprint_distinct_per_quarter | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_earnings_fingerprint_normalises_symbol | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_economic_fingerprint_deterministic_and_normalised | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_economic_fingerprint_distinct_per_time | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_economic_fingerprint_rejects_naive_datetime | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_economic_fingerprint_same_instant_different_offsets | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestFingerprints::test_ipo_fingerprint_is_name_plus_date | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestGetMacroObservations::test_as_of_uses_vintage_window_bracket | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestGetMacroObservations::test_current_vintage_uses_realtime_end_sentinel | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestGetMacroObservations::test_unknown_series_returns_none | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEarningsAndIpo::test_earnings_as_of_uses_revisions | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEarningsAndIpo::test_earnings_canonical_filters | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEarningsAndIpo::test_ipo_status_lowercased | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEconomicEvents::test_as_of_uses_lateral_join_to_revisions | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEconomicEvents::test_canonical_filters_threaded_into_sql | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEconomicEvents::test_limit_clamped_to_1000 | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEconomicEvents::test_no_filters_passes_none_for_array_params | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestListEconomicEvents::test_unavailable_dal_returns_empty_list | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMacro::test_macro_value_as_of_filters_vintage_window | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMacro::test_realtime_start_required_no_sentinel | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMacro::test_upsert_macro_observation_passes_realtime_window | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMutationAppendsObservedState::test_canonical_revision_atomicity_rollback_on_revision_failure | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMutationAppendsObservedState::test_subsequent_mutation_appends_revision_with_NEW_state | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestMutationAppendsObservedState::test_unchanged_payload_skips_writes | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_bool_not_normalised_to_decimal | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_decimal_vs_float_equal | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_decimal_vs_int_equal | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_decimal_vs_numeric_string_equal | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_mutation_detection_treats_none_to_value_as_change | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_non_numeric_string_passes_through | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_none_passes_through | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_tracked_payload_differs_decimal_vs_float_no_mutation | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestNumericDiffNormalisation::test_tracked_payload_differs_real_change_still_detected | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestReadAsOf::test_economic_read_as_of_walks_revision_log_backwards | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestReadAsOf::test_read_as_of_returns_none_when_no_revision_predates | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestTrackedFields::test_earnings_tracked_fields_include_hour | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestTrackedFields::test_economic_tracked_fields | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestTrackedFields::test_ipo_tracked_fields_include_status | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_calendar_store.py::TestUpsertEconomicNoOpOnDecimalFloatEqual::test_decimal_existing_vs_float_payload_is_unchanged | test-contract:tests/test_macro_calendar_store.py | passed | pg_only | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_all_six_macro_jobs_share_one_writer_lock | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_backfill_job_is_not_a_recurring_schedule_source | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_direct_job_failure_records_one_failed_canonical_row | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_direct_job_uses_shared_execution_and_records_one_canonical_row | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_fred_series_schedule_is_incremental_and_cannot_request_full_refresh | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_interrupted_macro_state_is_not_reconciled_as_success | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_and_market_writer_groups_may_fire_in_the_same_tick | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_lock_busy_records_one_non_success_row_without_provider_work | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_source_registry_has_exact_ids_jobs_providers_and_defaults | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_sources_default_disabled_while_manual_run_remains_available | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_writer_lock_releases_descriptors_after_success_and_failure | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_macro_writer_lock_serializes_two_real_processes | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_missing_provider_config_fails_before_shared_execution | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_schedule_failure_records_one_failed_canonical_row | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_schedule_reads_do_not_create_macro_calendar_database | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_schedule_uses_shared_execution_and_records_one_canonical_row | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_scheduler_deferral_keeps_other_macro_sources_due_without_success | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_macro_scheduler_integration.py::test_scheduler_fires_at_most_one_due_macro_writer_per_tick | test-contract:tests/test_macro_scheduler_integration.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_coverage_boundaries.py::test_backend_v2_contract_and_source_contain_no_retired_coverage_fields | test-contract:tests/test_market_coverage_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_coverage_boundaries.py::test_coverage_enum_consumers_use_exact_exhaustive_matching | test-contract:tests/test_market_coverage_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_coverage_boundaries.py::test_market_coverage_package_exports_no_write_or_repair_operation | test-contract:tests/test_market_coverage_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_coverage_boundaries.py::test_market_coverage_package_has_no_provider_gateway_or_pg_runtime_dependency | test-contract:tests/test_market_coverage_boundaries.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_market_coverage_boundaries.py::test_scheduler_has_no_planner_missing_feed_or_unknown_exclusion_path | test-contract:tests/test_market_coverage_boundaries.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_news_collision_keeps_fts_in_sync | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_news_collision_merges_and_keeps_canonical_id | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_news_rows_pk_safe_when_both_forms_present | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_news_updates_ticker_and_hash_together | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_prices_pk_safe_on_collision | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_canonicalize_rename_moves_history_when_canonical_absent | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_ensure_news_hash_unique_dedups | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_ensure_ticker_aliases_seeds_brk_idempotent | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_fresh_profile_without_market_db_uses_local_backend_not_pg | test-contract:tests/test_market_data_admin.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_fresh_profile_without_market_db_uses_local_backend_not_pg | type_gate:tests/test_market_data_admin.py:isinstance | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_local_stats_financial_cache_counts | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_local_stats_missing | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_local_ticker_coverage | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_local_ticker_coverage_resolves_aliases | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_news_fts_triggers_keep_index_in_sync | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_p0c_market_status_reports_prices_local_authority | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_seed_includes_lc_to_hapn_rename | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_status_news_sync_follows_active_writer_only | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_status_route_local_only | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_status_route_reports_strict_local_only_when_enabled | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_toggle_invalidates_dal_cache | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_admin.py::test_toggle_persists_and_dal_reads_it | test-contract:tests/test_market_data_admin.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_acquire_gateway_lock_false_skips_when_caller_holds_it | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_acquires_gateway_lock_by_default | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_canonicalizes_ticker_before_insert | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_dedupes_alias_and_canonical_scope | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_default_ibkr_path_builds_polygon_fallback | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_default_ibkr_path_survives_missing_polygon_key | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_empty_scope_fails_loud | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_exception_and_unresolved_tickers_share_one_issue_rollup | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_failed_when_every_ticker_has_issue | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_fatal_path_finish_failure_does_not_mask_original | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_fetches_provider_rows_outside_market_write_lock | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_ibkr_successful_empty_response_falls_to_polygon | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_inserts_canonical_rows_and_is_idempotent | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_meta_write_failure_in_error_path_does_not_abort_batch | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_non_target_rows_do_not_resolve_original_zero_bar_target | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_none_provider_constructs_default | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_one_row_low_volume_day_stays_succeeded | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_per_ticker_exception_isolated | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_polygon_fallback_when_ibkr_empty | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_polygon_path_no_gateway_lock | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_polygon_provider_skips_ibkr_preflight | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_preflight_connect_failure_fails_fast_no_lock_no_run | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_preflight_connect_ok_proceeds | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_preserves_typed_security_definition_issue | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_progress_cb_shape | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_rechecks_original_target_set_only_once | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_resolved_zero_bar_target_stays_succeeded_and_clears_error | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_tops_up_a_partial_day | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_topup_excludes_in_progress_today | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_topup_idempotent_on_complete_day | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backfill_unavailable_scope_raises_before_provider_construction | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backup_is_wal_safe_captures_uncheckpointed_rows | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backup_missing_src_returns_none | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_backup_refuses_to_overwrite_existing_destination | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_default_ibkr_src_uses_prices_domain_client_id | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_after_close_today_is_complete | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_empty_tickers_returns_empty | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_include_incomplete_today_escape_hatch | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_intraday_partial_today_does_not_hide_prior_gap | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_intraday_today_not_flagged | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_missing_midweek_day | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_missing_table_reports_all_trading_days | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_next_day_flags_prior_trading_day | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_now_et_aware_utc_is_converted_to_et | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_one_bar_counts_as_present | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_resolves_alias_ticker | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_gaps_weekend_holiday_still_excluded_with_completeness | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_ibkr_bars_to_rows_canonical_utc_pk | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_ibkr_bars_to_rows_skips_nan_ohlc_coerces_nan_volume | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_market_write_lock_acquires_and_releases | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_market_write_lock_actually_flocks_the_shared_file | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_market_write_lock_shares_scheduler_lock_file_path | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_normalize_utc_already_aware_utc_idempotent | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_normalize_utc_edt_summer | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_normalize_utc_est_winter | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_normalize_utc_format_matches_pg_literal | test-contract:tests/test_market_data_direct.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_normalize_utc_polygon_epoch_matches_ibkr_path | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_polygon_results_use_raw_epoch_not_mutated_datetime | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_preflight_creates_aliases_on_clean_db | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_preflight_folds_pre_canon_news_pk_safe | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_preflight_idempotent_second_run_noop | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_preflight_missing_db_is_noop_success | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_preflight_touches_no_pg | test-contract:tests/test_market_data_direct.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_run_status_constrained_to_valid_set | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_sync_meta_error_preserves_last_success | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_sync_meta_upsert_then_update | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_sync_run_lifecycle | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_sync_runs_status_check_enforced_at_schema | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_provider_sync_tables_idempotent | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_market_data_direct.py::test_reconcile_interrupted_provider_runs_marks_stale_running | test-contract:tests/test_market_data_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestDeleteMemory::test_delete_db_failure | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestDeleteMemory::test_delete_not_found | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestDeleteMemory::test_delete_with_db | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestDeleteMemory::test_delete_with_file_cleanup | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestFilenameGeneration::test_filename_format | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestFilenameGeneration::test_unique_filenames | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestListMemories::test_list_all | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestListMemories::test_list_by_category | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestListMemories::test_list_empty | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestListMemories::test_list_limit | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestListMemories::test_list_with_db | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestMemoryToolRegistry::test_memory_tools_registered | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestMemoryToolRegistry::test_total_tool_count | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_all | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_by_category | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_by_query | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_by_tickers | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_empty | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_limit | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestRecallMemories::test_recall_with_db | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_basic_save | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_directory_auto_created | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_importance_clamped | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_invalid_category_defaults_to_note | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_save_db_failure_graceful | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_save_markdown_structure | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_save_with_db | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestSaveMemory::test_save_with_tickers_and_tags | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_memory_tools.py::TestValidCategories::test_all_categories | test-contract:tests/test_memory_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_dedup_idempotent_on_article_hash | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_direct_dedups_against_mirror_sha_row | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_exact_inclusive_cursor_keeps_same_second_sibling | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_fts_search_finds_written_articles | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_fts_synced_by_trigger_no_double_write | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_incremental_cursor_is_source_scoped | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_no_pg_dependency | test-contract:tests/test_news_direct.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_norm_published_offset_fractional_and_space | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_offset_articles_written_normalized | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_per_ticker_failure_isolated | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_provider_sync_telemetry_news_domain | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_skips_articles_missing_required_fields | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_direct.py::test_writes_articles_to_local_news | test-contract:tests/test_news_direct.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_feed_content_route.py::test_local_backend_propagates_content_without_postgres_fallback | test-contract:tests/test_news_feed_content_route.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_feed_content_route.py::test_news_feed_route_forwards_content_to_dal | test-contract:tests/test_news_feed_content_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_environment_values_override_profile_values | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_explicit_normalized_environment_false_blocks_after_exit | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_local_environment_value_overrides_profile_value | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_malformed_exit_marker_blocks_pure_route | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_malformed_stored_exit_marker | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_when_profile_database_is_corrupt | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_blocks_when_profile_table_is_missing | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_defaults_without_profile_database | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_encodes_sqlite_uri_metacharacters | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_read_news_write_route_uses_profile_and_environment | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_is_immutable | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-False-False-legacy_pg] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-False-None-legacy_local] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-False-True-legacy_local] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-None-False-legacy_pg] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-None-None-legacy_local] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-None-True-legacy_local] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-True-False-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-True-None-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[False-True-True-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-False-False-blocked] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-False-None-blocked] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-False-True-blocked] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-None-False-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-None-None-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-None-True-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-True-False-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-True-None-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_matrix[True-True-True-normalized] | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_normalized_routing.py::test_route_reuses_news_toggle_string_semantics | test-contract:tests/test_news_normalized_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_completed_audit_marker_forces_news_hard_local_without_profile_exit_setting | test-contract:tests/test_news_pg_unreachable.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_completed_audit_marker_forces_news_hard_local_without_profile_exit_setting | type_gate:tests/test_news_pg_unreachable.py:isinstance | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_news_hard_local_no_dsn_never_calls_pg_for_empty_reads | test-contract:tests/test_news_pg_unreachable.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_news_hard_local_no_dsn_never_calls_pg_for_empty_reads | type_gate:tests/test_news_pg_unreachable.py:isinstance | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_no_dsn_completed_news_exit_selects_local_backend_with_market_strict | test-contract:tests/test_news_pg_unreachable.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_no_dsn_completed_news_exit_selects_local_backend_with_market_strict | type_gate:tests/test_news_pg_unreachable.py:isinstance | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_news_pg_unreachable.py::test_no_dsn_get_conn_fails_before_psycopg | test-contract:tests/test_news_pg_unreachable.py | passed | negative_no_pg | ["requires_psycopg2_import","sealed_fixture"] |
| backend | tests/test_news_providers.py::test_article_to_raw_maps_real_collector_dataclass | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_article_to_raw_prefers_description_when_present | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_article_to_raw_uses_canonical_sha256_hash | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_provider_fetch_uses_collector_fetch_parse_no_parquet | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_provider_skips_none_parse_results | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_default_on | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_env_false_overrides_profile_true | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_env_override_on | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_env_true_overrides_profile_false | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_profile_false_is_rollback | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_providers.py::test_use_local_news_profile_setting_on | test-contract:tests/test_news_providers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_post_exit_profile_marker_rejects_pg_selecting_toggles | test-contract:tests/test_news_settings_route.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_put_normalized_writes_persists_with_permission | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_put_settings_persists_explicit_rollback | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_static_status_route_is_declared_before_dynamic_ticker_route | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_status_and_http_409_after_completed_audit_marker | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_status_is_read_only_and_reports_default_direct | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_news_settings_route.py::test_status_reports_explicit_and_env_rollback | test-contract:tests/test_news_settings_route.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestComparisonMatrix::test_handles_none_values | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestComparisonMatrix::test_matrix_contains_metrics | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestComparisonMatrix::test_matrix_has_all_peers | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestComparisonMatrix::test_sector_stats_computed | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestDataQuality::test_data_quality_fields | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestDataQuality::test_unavailable_valuation_prices_are_counted_named_and_excluded | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestErrorHandling::test_all_failures | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestErrorHandling::test_partial_failures | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestExplicitInputs::test_explicit_tickers | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestExplicitInputs::test_sector_only | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestLivePeerComparison::test_nvda_peer_comparison | local-capability:src/tools/data_access.py:backend-contract | skipped | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestLivePeerComparison::test_nvda_peer_comparison | test-contract:tests/test_peer_comparison.py | skipped | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestPercentileRanking::test_no_rankings_without_target | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestPercentileRanking::test_ranking_with_target | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestSectorDetection::test_no_args_returns_error | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestSectorDetection::test_nvda_found_in_ai_chips | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_peer_comparison.py::TestSectorDetection::test_unknown_ticker | test-contract:tests/test_peer_comparison.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_bootstrap_repo_root_inserts_src_import_path | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_handler_direct_client_preserves_http_exception_detail | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_handler_direct_client_runs_healthz_without_testclient | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_macro_disabled_503_is_explicit_config_state_not_pg_failure | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_market_status_assertion_requires_no_pg_fallback | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_pg_poison_records_and_raises | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_pg_poison_redacts_kwarg_credentials | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_provider_config_policy_assertion_is_env_and_invariant_aware | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_report_sanitizes_poison_dsn | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_required_checks_cover_pg_exit_surfaces | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_run_smoke_restores_environment_flags | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_smoke_fails_if_any_pg_attempt_is_recorded | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_pg_unreachable_e2e.py::test_smoke_fails_on_bad_route_status | test-contract:tests/test_pg_unreachable_e2e.py | passed | pg_only | ["requires_psycopg2_import","scheduler_disabled","sealed_fixture"] |
| backend | tests/test_profile_state.py::test_add_member_reactivates_archived | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_add_note_blank_is_422 | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_add_note_rejects_blank | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_add_tag_blank_is_422 | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_add_tag_rejects_blank | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_aggregate_read_model_active_vs_archived_lists | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_all_tickers_distinct_sorted | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_archive_restore_roundtrip | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_archive_unknown_ticker_is_404 | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_cockpit_read_does_not_write | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_cockpit_universe_ticker_state_carry_tags | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_create_list_blank_is_422 | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_default_aggregate_for_unknown_ticker | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_default_watchlist_get_set_stale_and_404 | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_get_tags_empty | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_lists_allows_duplicate_membership | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_universe_creates_no_lists_and_archive_filter | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_universe_deletes_non_custom_lists | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_universe_seeds_theme_tags_and_drops_groups | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_universe_theme_groups_best_effort | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_import_universe_uses_annotations_without_opening_json | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_legacy_overview_enriches_but_never_qualifies_universe | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_list_crud_and_membership | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_list_crud_routes | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_notes_add_list_count_delete | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_notes_endpoints | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_priority_route_overrides_universe_and_ticker_state | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_priority_set_get_clear | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_profile_settings_get_set | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_provenance_system_normalized_to_legacy_editable | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_seed_tags_get_and_facet_grouping | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_seed_tags_is_additive_and_preserves_user | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_set_priority_route_overrides_overview | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_suppression_does_not_clobber_priority | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_sync_universe_creates_lists_and_memberships | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_sync_universe_is_idempotent_and_archive_preserving | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_tag_add_remove_user_default_and_facets | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_tag_catalog_groups_distinct_values_by_facet | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_tags_v1_to_v2_migration | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_batch_summary_fills_universe_only | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_export_route_is_deterministic_read_only_and_omits_settings | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_route_returns_sanitized_503_for_unavailable_source | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_route_uses_snapshot_and_keeps_archived_history_non_active | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_suppression_hides_ticker | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_universe_surfaces_all_imported_with_has_summary | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_user_tag_add_remove_routes | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_profile_state.py::test_user_tag_label_colliding_with_legacy_is_distinct | test-contract:tests/test_profile_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_config_file_key_source_sets_import_suggestion | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_connected_when_local_sqlite_timestamp_uses_compact_utc_offset | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_connected_when_signal_recent | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_direct_news_health_uses_provider_runs_and_current_ticker_errors | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_disabled_outranks_missing_key | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_fd_disabled_is_a_state | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_fred_refresh_off_without_snapshot_is_no_signal | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_fred_snapshot_available_when_refresh_is_off | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_ibkr_weekend_is_maintenance_not_stale | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_key_source_reports_effective_origin | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_no_signal_when_nothing_recorded | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_p0c_provider_health_marks_price_sync_retired | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_provider_health_missing_managed_key_is_not_configured | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_route_returns_aggregation | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_sa_capture_error_and_success_merge | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_sa_provider_ignores_legacy_and_skipped_success_rows | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_sa_provider_uses_derived_complete_success_and_latest_attempt_separately | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_sec_edgar_ttl_governed_never_stale | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_section_failure_degrades_not_raises | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_provider_health.py::test_stale_when_signal_old_on_weekday | test-contract:tests/test_provider_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_accumulate_anthropic_pairs | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_accumulate_duplicate_tool_two_distinct_rows | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_accumulate_openai_name_only_no_tool_start | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_anthropic_run_query_stream_raise_becomes_error_event_and_persists | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_anthropic_subscription_stream_builds_driver_with_registry_dal_and_prompt | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_anthropic_subscription_stream_no_history_uses_bare_prompt | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_api_key_stream_receives_research_max_turns | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_apikey_active_anthropic_still_uses_run_query_stream | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_compose_agent_question_with_ticker | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_compose_agent_question_without_ticker | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_delete_active_thread_returns_409_without_cascade | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_delete_thread_route_422_for_blank_thread_id | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_delete_thread_route_is_idempotent_for_missing | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_delete_thread_route_removes_thread_and_messages | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_exact_thread_route_returns_archived_target_outside_history_page | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_history_route_filters_before_pagination_and_batches_active_runs | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_latest_selection_route_returns_semantic_tuple_without_credentials | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_list_messages_404_for_missing | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_list_messages_422_for_blank_thread_id | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_list_messages_route_roundtrip | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_list_threads_route_orders_desc | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_oauth_active_anthropic_routes_to_subscription_driver | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_oauth_active_driver_raises_persists_error_turn_no_crash | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_oauth_active_openai_routes_to_chatgpt_oauth_driver | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_openai_api_key_active_still_uses_run_query_stream | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_openai_subscription_stream_builds_driver_with_research_runtime | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_patch_archive_active_thread_returns_409_without_mutation | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_patch_archive_and_unarchive_preserve_transcript_and_runs | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_patch_thread_renames_and_rejects_invalid_titles_without_mutation | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_persist_error_turn_marks_is_error_and_preserves_partial_trace | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_persist_is_best_effort_swallows_store_errors | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_persist_user_then_assistant_roundtrip | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_enabled_profile_passes_context_and_persists_trace | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_explicit_model_and_effort_passthrough | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_invalid_assistant_stance_returns_400 | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_no_thread_id_sends_empty_history | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_profile_off_does_not_pass_personalization_kwarg | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_retry_last_failed_excludes_failed_pair_from_history | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_subscription_branches_receive_personalization_context[anthropic-_anthropic_subscription_stream] | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_subscription_branches_receive_personalization_context[openai-_openai_subscription_stream] | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_subscription_profile_off_does_not_pass_personalization_kwarg | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_threads_history_into_provider[anthropic-src.agents.anthropic_agent.agent] | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_query_stream_threads_history_into_provider[openai-src.agents.openai_agent.agent] | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_run_and_message_routes_expose_typed_redacted_failure_details | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_unknown_provider_persists_error_turn_not_a_dangling_user | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_routes.py::test_valid_thread_id | test-contract:tests/test_research_routes.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_append_bumps_thread_updated_at | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_append_message_is_error_roundtrips | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_append_minimal_assistant_tolerates_none_json_fields | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_append_user_then_assistant_roundtrips_and_orders | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_archive_hides_default_list_but_exact_lookup_survives | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_archive_never_deletes_runs_or_messages | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_full_thread_roundtrips_role_content_in_order | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_no_history_policy_and_empty_thread | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_rejects_unimplemented_policy | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_retry_does_not_exclude_successful_tail | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_retry_excludes_last_failed_pair_only | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_retry_excludes_last_max_turns_pair | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_skips_empty_content | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_build_thread_history_skips_error_turns | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_delete_thread_missing_is_false | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_delete_thread_removes_messages_and_history_without_touching_other_threads | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_ensure_thread_is_idempotent_keeps_original | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_ensure_thread_roundtrips_fields | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_get_thread_none_for_missing | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_list_threads_orders_by_updated_at_desc | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_list_threads_respects_limit | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_local_only_no_pg | test-contract:tests/test_research_threads.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_message_personalization_round_trip | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_message_personalization_snapshot_round_trip_and_legacy_null | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_message_run_linkage_is_fresh_and_tolerantly_migrated | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_missing_thread_lifecycle_updates_return_none_and_create_nothing | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_rename_thread_updates_title_and_timestamp_without_changing_transcript | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_research_threads.py::test_unarchive_restores_same_thread_and_transcript | test-contract:tests/test_research_threads.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_article_body_capture_survives_reconciliation_failure_byte_for_byte | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_article_list_and_detail_ticker_observations_persist_independently | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_exact_unique_entry_auto_link_projects_to_every_lineage_row | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_exit_auto_link_uses_closed_date_and_never_overwrites_entry_projection | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_legacy_preview_and_review_queue_are_read_only | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_list_detail_conflict_keeps_both_values_and_legacy_projection_is_not_evidence | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_manual_link_never_populates_provider_ticker_observations | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_matcher_requested_enrichment_is_deduped_and_bounded | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_missing_closed_date_is_unmatchable_and_visible | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_multiple_closed_dates_receive_distinct_exit_links | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_null_observation_does_not_erase_prior_explicit_provider_ticker | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_outside_window_legacy_projection_is_reported_not_grandfathered | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_pick_capture_survives_reconciliation_failure_byte_for_byte | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_reconciliation_rerun_is_idempotent | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_refresh_changed_picked_date_resolves_new_lineage | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_refresh_current_and_closed_rows_resolve_one_lineage | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_rejected_candidate_is_durable_and_not_reproposed | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_repeated_symbol_lineages_reconcile_independently | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_replacement_revokes_old_link_and_requires_expected_link_id | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_article_reconciliation_backend.py::test_same_strength_tie_stays_in_review_queue | test-contract:tests/test_sa_article_reconciliation_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_any_mode_overlap_repairs_pending_recovery | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_apply_sa_refresh_marks_stale_and_updates_meta | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_articles_meta_upsert_and_query | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_audit_unresolved_symbols_exact_and_like_fallback | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_backfill_terminal_requires_five_stable_bottom_rounds | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_body_capture_commits_when_comment_scan_is_unusable | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_cleanup_mixed_null_date_comment_duplicates | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_closed_scope_distinct_events_and_idempotent_upsert | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_comment_dedupe_cascade_leaves_no_orphan_signals | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_comment_scan_checkpoint_advances_only_on_usable_observation | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_failure_rolls_back_and_records_failure_meta | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_first_comment_scan_establishes_baseline_without_pending_recovery | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_get_sa_refresh_meta_returns_text_timestamps | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_invalidate_dirty_market_news_detail | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_isinstance_gate_and_lazy_construction | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_isinstance_gate_and_lazy_construction | type_gate:tests/test_sa_capture_backend.py:isinstance | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_mark_stale_not_triggered_by_equal_snapshot | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_market_news_need_detail_and_recent_ids_roundtrip | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_market_news_query_by_ticker_and_fts_keyword | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_market_news_upsert_conflict_semantics | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_no_pg_fallback_even_on_empty_results | test-contract:tests/test_sa_capture_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_read_shapes_match_pg_key_sets | test-contract:tests/test_sa_capture_backend.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_recovery_watermark_is_pre_upsert_and_new_generation_cannot_self_repair | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_refresh_never_clobbers_detail_report | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_sanitize_corrupted_comments_counts | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_save_article_with_comments_shape_and_pick_sync | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_terminal_reanchors_future_epoch_and_preserves_audit | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_two_usable_full_misses_park_without_terminalizing | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_backend.py::test_unusable_scan_freezes_comment_recovery_state | test-contract:tests/test_sa_capture_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_articles_fts_insert_update | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_canon_date | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_canon_ts_one_format_lexicographic | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_cascade_purges_signals_and_mentions | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_closed_identity_allows_distinct_close_events | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_concurrent_schema_creation_two_processes | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_current_identity_rejects_duplicates | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_dual_membership_current_and_closed | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_fk_enforced_on_unknown_article | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_market_news_fts_and_ticker_junction | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_reopen_fast_path_no_ddl | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_capture_store.py::test_schema_tables_and_version | test-contract:tests/test_sa_capture_store.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_bucket_candidate_tickers_and_broad_count | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_candidate_watch_has_samples | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_clamps_params | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_deterministic_ranking | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_empty_reason_backlog_pending | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_empty_reason_min_score_too_high | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_empty_reason_no_comments_in_window | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_keyword_buckets_aggregated | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_multi_ticker_counted_once_each_and_sample_cap | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_pg_mode_requires_local | test-contract:tests/test_sa_comment_focus.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_comment_focus.py::test_focus_ranks_tickers_with_traceable_samples | test-contract:tests/test_sa_comment_focus.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_empty_text_comment_gets_zero_signal_and_resolves_pending | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_guard_lifted_runs_in_sa_local_mode | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_idempotent_rerun_no_growth | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_max_extracted_caps_run | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_max_extracted_spans_batch_boundary | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_mid_batch_failure_rolls_back_whole_batch | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_reextraction_replaces_mention_set | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_rule_set_version_gates_pending | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signal_port.py::test_writes_signals_and_junctions_to_sqlite | test-contract:tests/test_sa_comment_signal_port.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_alpha_picks_radar_post | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_backfill_max_extracted_caps_inside_batch | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_chatty_filler_post | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_chinese_hedges_still_work | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_chitchat_scores_zero | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_default_rule_set_version_is_current | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dividend_query | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dollar_and_bare_dedupe | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dot_ticker_bare_form | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dot_ticker_dollar_form | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dot_ticker_off_universe_is_candidate | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_dot_ticker_paren_form | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_earnings_bucket_stores_matched_terms | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_eligibility_bucket | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_empty_string_returns_empty_signals | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_external_link_adds_bonus | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_hedge_substring_match_does_not_fire_on_unrelated_word | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_hedge_word_boundary_for_might | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_may_as_modal_verb_is_hedge | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_may_as_month_does_not_trigger_verification | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_may_with_ordinal_date_not_hedge | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_multiple_tickers_and_candidates | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_needs_verification_chinese_hedge | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_needs_verification_requires_hedge_and_claim | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_no_buckets_when_chitchat | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_off_universe_token_goes_to_candidate | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_pronoun_i_never_matches | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_rating_change_bucket | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_rule_set_version_is_threaded_through | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_rule_set_version_is_v12 | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_score_caps_at_ten | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_score_increases_with_ticker_and_bucket | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_single_letter_only_via_dollar_form | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_single_letter_paren_form_off_universe_is_candidate | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_stopword_not_in_universe_is_dropped | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_universe_ticker_extracted_as_mention | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_universe_ticker_overrides_stopword | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_upvotes_have_logarithmic_effect | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_v12_does_not_overblacklist_real_or_ambiguous_tickers | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_v12_stopwords_not_candidates | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_comment_signals.py::test_whitespace_returns_empty_signals | test-contract:tests/test_sa_comment_signals.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestCommentsSplitAndCaps::test_keyword_buckets_shape_preserved | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestCommentsSplitAndCaps::test_needs_verification_passthrough | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestCommentsSplitAndCaps::test_split_ticker_vs_candidate | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestCommentsSqlShape::test_comments_sql_uses_layered_cte_with_per_article_cap | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestDataQualityAndSourceNotes::test_data_quality_rows_always_present | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestDataQualityAndSourceNotes::test_source_notes_disclaimer_and_window | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestDisabledOrUnavailable::test_disabled_returns_helpful_string | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestDisabledOrUnavailable::test_empty_ticker_returns_pack_with_error | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestDisabledOrUnavailable::test_unavailable_dal_returns_pack_with_error | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestExcerpt::test_long_excerpt_marked_truncated | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestExcerpt::test_short_excerpt_no_marker | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestMissingFlags::test_article_url_missing_appended | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestNormalization::test_articles_normalization_and_ordering | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestNormalization::test_news_normalization | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestParamClamping::test_max_clamps | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestParamClamping::test_min_comment_score_clamped | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestParamClamping::test_window_days_clamped | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestPerSourceFailure::test_articles_failure_does_not_blank_other_sources | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestSerialization::test_returns_json_serializable | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_digest.py::TestTickerUppercase::test_lowercase_input_passes_uppercase_to_sql | test-contract:tests/test_sa_digest.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_changed_admitted_diagnostics_for_same_event_conflicts | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_changed_admitted_diagnostics_for_same_event_conflicts | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_completed_extension_reader_excludes_running_repair_and_unknown_jobs | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_completed_extension_reader_excludes_running_repair_and_unknown_jobs | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_completed_extension_reader_returns_latest_twenty_allowlisted_rows | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_completed_extension_reader_returns_latest_twenty_allowlisted_rows | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_diagnostic_validator_rejects_identifiers_sizes_and_secret_sentinels_atomically | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_diagnostic_validator_rejects_unknown_fields_enums_and_time_bounds | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_extension_record_route_passes_only_admitted_or_marker_projection_to_store | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_invalid_diagnostics_persist_terminal_result_with_fixed_rejection_marker | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_legacy_request_preserves_pre_diagnostics_hash_and_deduplicates | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_legacy_request_preserves_pre_diagnostics_hash_and_deduplicates | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_rejected_diagnostics_retry_deduplicates_without_raw_bytes | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_rejected_diagnostics_retry_deduplicates_without_raw_bytes | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_valid_diagnostics_round_trip_into_payload_and_extended_hash | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_extension_diagnostics.py::test_valid_empty_diagnostics_records_explicit_recorded_status | test-contract:tests/test_sa_extension_diagnostics.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_backend_unavailable_precedes_store_and_history_checks | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_broken_symlink_sa_store_is_unreadable | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_directory_sa_store_is_unreadable | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_extra_feed_schema_remains_compatible | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_both_types_newest_first | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_clamps_params | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_days_window_keeps_date_only_article_on_cutoff_day | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_empty_window | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_fts_search | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_item_shape_and_detail_route | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_item_type_filter | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_like_fallback_short_and_symbol | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_pagination_accurate_total | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_pg_mode_requires_local | test-contract:tests/test_sa_feed.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_snippet_is_clean_plain_text | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_feed_ticker_filter_column_and_junction | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_like_escapes_sql_wildcards | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_malformed_sa_store_is_unreadable | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_column_is_schema_incompatible | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_table_is_schema_incompatible[sa_articles] | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_table_is_schema_incompatible[sa_articles_fts] | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_table_is_schema_incompatible[sa_market_news] | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_table_is_schema_incompatible[sa_market_news_fts] | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_required_feed_table_is_schema_incompatible[sa_market_news_tickers] | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_extract_sa_comment_signals_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_alpha_picks_refresh_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_extension_manual_fetch_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_market_news_incident_recovery_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_market_news_refresh_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_market_news_repair_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_history_sa_market_news_retry_recorded_is_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_with_empty_profile_is_not_created_without_mutation | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_with_unreadable_history_fails_closed_as_missing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_missing_store_without_profile_is_not_created_and_creates_nothing | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_post_validation_query_failure_is_typed_sanitized_and_preserves_request | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_route_handler_happy_and_disabled | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_route_returns_typed_200_for_every_unavailable_store_reason | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_sa_store_open_failure_is_unreadable_and_sanitized | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_feed.py::test_unexpected_internal_failure_is_typed_sanitized_and_preserves_request | test-contract:tests/test_sa_feed.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestBackfillRouting::test_pg_mode_proceeds | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestBackfillRouting::test_routes_to_sqlite_not_pg | test-contract:tests/test_sa_local_readers.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestDigestLocal::test_articles_shape_order_and_missing_note | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestDigestLocal::test_comments_kind_split_and_per_article_cap | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestDigestLocal::test_news_junction_tickers_and_gate | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestDigestLocal::test_pack_is_json_serializable | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestDigestLocal::test_pg_dispatch_without_sa_db | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHealthSplit::test_local_capture_metrics_without_extension_run_uses_capture_signal | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHealthSplit::test_local_job_runs_failure_degrades_pipeline_signal | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHealthSplit::test_local_with_pg_up_uses_extension_signal | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHealthSplit::test_non_local_sa_backend_does_not_query_pg | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHighValueCommentsLocal::test_pg_dispatch_without_sa_db | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHighValueCommentsLocal::test_shape_lists_and_ordering | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHighValueCommentsLocal::test_ticker_filter_via_junction | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestHighValueCommentsLocal::test_window_and_rule_version_semantics | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestUnresolvedSymbols::test_local_branch_matches_pg_semantics | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::TestUnresolvedSymbols::test_pg_dispatch_without_sa_db | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::test_absent_sa_db_health_query_degrades_honestly | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::test_absent_sa_db_market_news_query_is_honest_empty | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::test_absent_sa_db_refresh_meta_is_honest_empty | test-contract:tests/test_sa_local_readers.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_local_readers.py::test_provider_health_sa_meta_never_touches_pg_on_fresh_profile | test-contract:tests/test_sa_local_readers.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_completeness_at_warning_boundary_is_ok | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_completeness_critical_band | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_completeness_just_below_warning_threshold_is_warning | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_completeness_warning_band | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_empty_db_returns_critical | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_extension_recent_masks_stale_fetched_at | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_healthy_state_returns_ok | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_no_extension_runs_falls_back_to_last_fetched_at_when_recent | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_no_extension_runs_falls_back_to_last_fetched_at_when_stale | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_overall_severity_is_max_of_layers | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_small_sample_skips_completeness_check | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_stale_extension_triggers_warning | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_zero_published_items_market_hours_is_critical | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestEvaluateHealthSeverity::test_zero_published_items_offhours_is_warning_only | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestHealthRoute::test_route_non_strict_warning_returns_200 | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestHealthRoute::test_route_returns_503_when_sa_disabled | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestHealthRoute::test_route_returns_payload_when_ok | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestHealthRoute::test_route_strict_warning_returns_503 | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_naive_datetime_treated_as_utc | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_saturday_during_normal_session_is_not_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_sunday_during_normal_session_is_not_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_weekday_at_close_boundary_is_not_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_weekday_at_open_boundary_is_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_weekday_during_regular_session_is_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestMarketHours::test_weekday_premarket_is_not_market_hours | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestOrchestrator::test_db_unavailable_returns_critical_report | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestOrchestrator::test_extension_run_uses_job_runs_store_factory | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestOrchestrator::test_orchestrator_passes_now_to_query_and_evaluation | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestResponseShape::test_completeness_pct_is_none_when_items_7d_zero | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestResponseShape::test_freshness_block_carries_all_ages | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestResponseShape::test_reasons_carry_severity_and_code | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestResponseShape::test_thresholds_visible_in_response | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestResponseShape::test_top_level_keys_present | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::TestThresholdOverrides::test_custom_stale_fetch_threshold | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::test_later_degraded_run_updates_attempt_without_advancing_success | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::test_latest_derived_complete_sync_is_the_only_extension_success_anchor | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::test_skipped_and_legacy_succeeded_rows_do_not_advance_success | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_health.py::test_structured_summary_outage_degrades_without_hiding_capture_stats | test-contract:tests/test_sa_market_news_health.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_atomic_start_returns_one_running_run_and_manifest_under_concurrency | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_cancel_and_stale_interruption_preserve_resumable_manifest_truth | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_conflicting_or_incompatible_progress_is_rejected_without_write | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_finalize_marks_missing_or_omitted_targets_failed_retryable | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_finalize_reconciles_already_present_repaired_and_source_unavailable | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_incident_preview_caps_at_168_hours_or_marks_missing_anchor_unverified | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_incident_preview_uses_latest_derived_complete_anchor | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_latest_structured_retryable_ids_can_be_previewed_contextually | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_manifest_accepts_only_canonical_sa_pathnames_without_query_or_fragment | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_manifest_json_and_hash_are_canonical_and_order_independent | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_preview_separates_known_detail_targets_from_unknown_metadata_gap | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_progress_checkpoint_is_idempotent_by_news_id_and_attempt_id | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_recorded_failure_preview_has_no_age_cutoff_and_does_not_classify_legacy_prose | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_resume_preserves_run_id_manifest_hash_and_baseline | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_terminal_status_counts_and_result_hash_are_derived_and_idempotent | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_market_news_recovery.py::test_zero_target_rules_distinguish_no_work_from_real_discovery_scope | test-contract:tests/test_sa_market_news_recovery.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_accept_reconciliation_link_requires_confirmation_for_mismatch_or_replacement | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_compatibility_audit_returns_queue_without_mutation | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_get_reconciliation_queue_action_is_read_only_and_sanitized | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_pick_refresh_and_article_meta_capture_commit_before_separate_reconciliation | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_reject_reconciliation_candidate_is_event_scoped_and_idempotent | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_resolve_and_accept_reconciliation_link_validates_exact_event_and_canonical_url | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_retired_pg_reconciliation_methods_never_connect | test-contract:tests/test_sa_reconciliation_native_host.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_save_article_content_commits_before_reconciliation_failure_and_stays_ok | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_save_article_content_passes_detail_ticker_without_manual_symbol_injection | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_reconciliation_native_host.py::test_save_comments_only_forwards_recovery_scan_evidence | test-contract:tests/test_sa_reconciliation_native_host.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_baseless_dal_gets_no_implicit_local_routing | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_both_on_one_instance_serves_both | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_default_routes_sa_local | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_env_override_flips_without_setting | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_explicit_false_is_provenance_only | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_market_only | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_market_strict_threads_to_selected_backend | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_news_exit_threads_news_strict_to_sa_backend_without_market_strict | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_sa_only_still_threads_local_market | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_sa_plus_market_strict_threads_to_single_backend | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_routing.py::test_sa_routes_local_even_without_existing_db_file | test-contract:tests/test_sa_routing.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestArticleTools::test_get_sa_article_detail_not_found | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestArticleTools::test_get_sa_article_detail_returns_content | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestArticleTools::test_get_sa_articles_disabled | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestArticleTools::test_get_sa_articles_returns_list | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_anthropic_bridge_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_anthropic_schema_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_openai_bridge_includes_sa_market_news | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_openai_schema_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_portfolio_category_7 | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_registry_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestBridgeIntegration::test_sa_tool_names_in_registry | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestClientNoSession::test_client_works_without_session_file | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestClientNoSession::test_no_stale_warning_when_fresh | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestClientNoSession::test_refresh_returns_hint | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestClientNoSession::test_stale_warning_when_cache_old | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentDuplicateCleanupPlan::test_plan_comment_duplicate_cleanup_collapses_same_date_duplicates | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentDuplicateCleanupPlan::test_plan_comment_duplicate_cleanup_collapses_shifted_pairs | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentDuplicateCleanupPlan::test_plan_comment_duplicate_cleanup_prefers_dated_over_null | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentNormalization::test_normalize_comment_ids_merges_naive_and_utc_same_wall_clock | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentNormalization::test_normalize_comment_ids_merges_null_and_dated_duplicate | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentNormalization::test_normalize_comment_ids_preserves_distinct_dated_duplicates | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentNormalization::test_normalize_comment_ids_remaps_parent_after_merge | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentUpsertPrep::test_prepare_comments_for_upsert_keeps_distinct_real_duplicates | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentUpsertPrep::test_prepare_comments_for_upsert_matches_existing_utc_row_with_naive_incoming | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentUpsertPrep::test_prepare_comments_for_upsert_merges_into_existing_dated_comment | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestCommentUpsertPrep::test_prepare_comments_for_upsert_remaps_child_to_existing_parent | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDALDualBackend::test_file_backend_uses_json | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDALDualBackend::test_file_stale_in_same_file | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDALDualBackend::test_is_partial_false_when_both_ok | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDALDualBackend::test_is_partial_true_when_one_fails | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDALDualBackend::test_refresh_meta_records_failure | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_backfill_mode_uses_deeper_backfill_limit | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_backfill_skips_stale_zero_comment_articles | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_full_and_backfill_prioritize_recovery_state_with_park_boundary | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_full_mode_adds_top_gap_backfill_articles | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_full_mode_treats_missing_comments_timestamp_as_stale | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_comment_work_uses_observation_checkpoint_not_inventory_gap | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_mode_ignores_year_prefixed_gap_artifact | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_mode_refreshes_comments_when_remote_count_increases | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_mode_skips_comment_refresh_for_articles_not_in_scan | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_sanitize_sa_comments_count_strips_published_year_prefix | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessArticleMeta::test_save_sa_articles_meta_sanitizes_incoming_comments_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_get_sa_market_news_queries_backend | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_get_sa_market_news_recent_ids_queries_backend | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_market_news_body_presence_readback_is_exact_for_frozen_ids | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_market_news_missing_detail_interval_uses_inclusive_canonical_bounds | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_market_news_recovery_queries_fail_closed_when_local_db_is_unavailable | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_market_news_rows_by_exact_ids_ignore_age_and_return_only_manifest_fields | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_recovery_queries_and_job_history_never_expose_titles_bodies_full_urls_or_target_paths | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_save_sa_market_news_detail_updates_backend | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_save_sa_market_news_includes_backfill_candidates | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_save_sa_market_news_normalizes_items | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDataAccessMarketNews::test_save_sa_market_news_respects_current_limit | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDetailKeyResolution::test_closed_only_returns_hint | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDetailKeyResolution::test_single_pick_returns_detail | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDetailStalePassThrough::test_tool_passes_through_stale_warning | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDetailStaleness::test_fresh_detail_no_warning | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestDetailStaleness::test_stale_detail_has_warning | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestGetDetailFileMerge::test_file_detail_merged_with_portfolio_row | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestGetDetailFileMerge::test_file_detail_only_when_no_portfolio_row | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_batch_ts_z_suffix_parsed | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_closed_refresh_accepts_closed_page_payload | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_closed_refresh_rejects_current_page_payload | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_current_refresh_rejects_closed_page_payload | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_detail_url_in_raw_data_survives_dal | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_handle_failure_records_meta | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_handle_ping | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_handle_refresh_calls_dal | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHost::test_refresh_scope_accepts_live_leading_company_cell_shapes | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_audit_unresolved | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_get_market_news_recent_ids | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_save_article_content | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_save_articles_meta | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_save_market_news | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_save_market_news_detail | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostArticles::test_save_market_news_passes_detail_limits | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostDetailCache::test_expired_detail_needs_refetch | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostDetailCache::test_fresh_detail_skipped | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostDetailCache::test_no_article_for_pick_skipped | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostDetailCache::test_null_detail_needs_fetch | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostSaveDetail::test_save_failure_returns_error | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestNativeHostSaveDetail::test_save_success | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestRegistryV3::test_new_tool_names_in_registry | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestRegistryV3::test_news_category_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestRegistryV3::test_portfolio_category_7 | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestRegistryV3::test_registry_count | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSAAlphaPicksStorageContract::test_sql_schema_preserves_dual_tab_membership_and_closed_date | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSAConfig::test_disabled_returns_message | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSAConfig::test_enabled_with_config | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSaveDetailContract::test_db_exception_returns_false | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSaveDetailContract::test_db_failure_returns_false | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestSaveDetailContract::test_db_success_returns_true | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestStaleReconciliation::test_refresh_marks_missing_as_stale | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestStaleReconciliation::test_stale_restored_on_reappear | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestTickerSync::test_current_refresh_never_calls_or_writes_tickers_core | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestTickerSync::test_refresh_portfolio_signature_has_no_sync_tickers_escape_hatch | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolFunctions::test_filter_by_sector | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolFunctions::test_get_market_news_disabled | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolFunctions::test_get_market_news_enabled | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolFunctions::test_get_picks_disabled | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolFunctions::test_refresh_disabled | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sa_tools.py::TestToolStalePassThrough::test_stale_warning_passed_to_tool_response | test-contract:tests/test_sa_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_all_and_missing | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_attempt_does_not_clobber_prior_outcome_fields | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_last_attempts_for_seeding | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_no_pg_dependency | test-contract:tests/test_scheduler_state.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_outcome_records_and_then_clears_error | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_partial_status_and_continuation_roundtrip | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_reconcile_interrupted_running_marks_terminal | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_scheduler_state.py::test_record_attempt_then_outcome | test-contract:tests/test_scheduler_state.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestBridgeIntegration::test_analysis_category_6 | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestBridgeIntegration::test_anthropic_includes_insider_trades | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestBridgeIntegration::test_openai_includes_insider_trades | local-capability:src/tools/data_access.py:backend-contract | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestBridgeIntegration::test_openai_includes_insider_trades | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestBridgeIntegration::test_registry_23 | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetInsiderTrades::test_basic | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetInsiderTrades::test_empty_trades | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetInsiderTrades::test_error_returns_empty | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetInsiderTrades::test_json_serializable | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetInsiderTrades::test_ticker_uppercased | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetSecFilings::test_basic | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetSecFilings::test_default_limit | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetSecFilings::test_error_returns_empty | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sec_tools.py::TestGetSecFilings::test_returns_list | test-contract:tests/test_sec_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_available_tickers_routing | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_canon_resolver_passthrough_when_no_alias_table | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_empty_and_missing | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_expiry | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_get_local_first | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_miss_is_honest_empty_without_pg | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_missing_table_is_safe | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_roundtrip | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_financial_cache_set_is_local_only | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_fts_search_is_tokenized_and | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_fundamentals_mirror_table_retired_no_pg_fallback | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_get_available_tickers | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_health_stats_local_first | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_inherited_vs_overridden_methods | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_is_databasebackend_subclass | test-contract:tests/test_sqlite_backend.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_is_databasebackend_subclass | type_gate:tests/test_sqlite_backend.py:isinstance | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_native_15min_passthrough | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_browse_and_facets | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_description_html_cleaned | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_filters_and_pagination | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_local_authoritative_vs_pre3b_fallback | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_missing_table_not_available | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_search | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_feed_search_relevance_title_weighted | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_hard_local_does_not_make_market_strict | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_stats_local_empty_does_not_fallback_to_pg | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_stats_local_when_present_does_not_hit_pg | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_strict_available_news_tickers_empty_does_not_hit_pg | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_news_strict_feed_local_exception_does_not_hit_pg | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_p0c_available_price_tickers_empty_is_honest_empty_no_pg | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_p0c_non_strict_prices_still_do_not_fallback_to_pg | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_prices_local_when_present | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_provenance_fundamentals_records_none_after_mirror_retirement | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_fundamentals_latest_snapshot | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_fundamentals_partial_and_empty | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_fundamentals_same_day_tiebreak_by_id | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_health_stats_local_shape | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_news_search_fts5 | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_news_search_like_fallback_short_query | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_news_search_malicious_fts_query_is_safe | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_news_stats_unscored_local_counts | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_news_unscored | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_query_resolves_alias_to_canonical | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_rollup_1d | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_rollup_1h | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_sa_capture_backend_threads_strict | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_set_financial_cache_serialized_by_lock | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_strict_market_local_miss_is_honest_empty_not_pg | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_strict_market_serves_local_without_pg | test-contract:tests/test_sqlite_backend.py | passed | negative_no_pg | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_strict_news_feed_exception_returns_full_shape_not_thin | test-contract:tests/test_sqlite_backend.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_sqlite_backend.py::test_strict_uses_fast_pg_connect_timeout | test-contract:tests/test_sqlite_backend.py | passed | historical_compatibility | ["sealed_fixture"] |
| backend | tests/test_stored_sec_projection.py::test_fundamentals_sync_is_null_while_price_and_news_remain_unchanged | test-contract:tests/test_stored_sec_projection.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_stored_sec_projection.py::test_legacy_fundamentals_row_does_not_project_as_stored | test-contract:tests/test_stored_sec_projection.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_stored_sec_projection.py::test_nonpositive_and_nonannual_cache_rows_do_not_project_as_stored | test-contract:tests/test_stored_sec_projection.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_stored_sec_projection.py::test_positive_annual_sec_cache_is_the_shared_projection_authority | test-contract:tests/test_stored_sec_projection.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestAnalysisTools::test_get_morning_brief | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestAnalysisTools::test_get_morning_brief_orders_raw_news_deterministically | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestAnalysisTools::test_get_sec_filings | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestAnalysisTools::test_get_watchlist_overview | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestNewsTools::test_get_ticker_news | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestNewsTools::test_search_news_by_keyword | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestNewsTools::test_search_news_keyword_case_insensitive | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestOptionsTools::test_calculate_greeks | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestOptionsTools::test_calculate_greeks_put | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestPriceTools::test_get_price_change | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestPriceTools::test_get_sector_performance | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestPriceTools::test_get_sector_performance_unknown | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestPriceTools::test_get_ticker_prices | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_anthropic_schema | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_categories | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_get_tool | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_openai_schema | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_register_all | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_tool_catalog_live_table_matches_registry | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_tool_has_parameters | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_tools.py::TestRegistry::test_tool_names | test-contract:tests/test_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_calendar_unavailable_returns_unknown_days | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_early_close_session_uses_derived_fourteen_slot_grid | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_empty_active_universe_returns_honest_unknown_coverage | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_low_fixture_horizon_degrades_health_without_erasing_reviewed_days | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_missing_market_db_is_unavailable_not_empty | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_provider_errors_remain_separate_diagnostics | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_readable_empty_market_db_is_ok_with_unknown_days | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_regular_session_uses_exact_rth_slots_despite_extended_rows | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_route_coverage_path_is_pure_read_without_provider_scheduler_or_pg | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_route_preserves_sanitized_active_universe_503 | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_route_registered | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_route_rejects_unreviewed_interval_with_typed_422 | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_route_wires_active_universe_and_v2_service | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_service_dedupes_aliases_and_orders_requested_window | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_service_emits_exact_v2_contract_without_retired_fields | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_trading_day_coverage.py::test_unreviewed_date_is_unknown_while_reviewed_dates_classify | test-contract:tests/test_trading_day_coverage.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_universe_summaries_local.py::test_missing_db_returns_empty | test-contract:tests/test_universe_summaries_local.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_universe_summaries_local.py::test_news_failure_keeps_price_summaries | test-contract:tests/test_universe_summaries_local.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_universe_summaries_local.py::test_summaries_read_local_db_never_pg | test-contract:tests/test_universe_summaries_local.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_anthropic_tools_excludes_claude_search | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_anthropic_tools_include_web | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_execute_tool_tavily_search | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_execute_tool_web_browse | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_openai_tools_include_web | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestBridgeIntegration::test_registry_web_tools | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestConfigIntegration::test_config_defaults | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestConfigIntegration::test_config_disabling_tavily | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestDaysToTimeRange::test_day | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestDaysToTimeRange::test_month | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestDaysToTimeRange::test_week | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestDaysToTimeRange::test_year | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilyFetch::test_basic_fetch | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilyFetch::test_failed_results | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilyFetch::test_pagination | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_basic_search | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_content_truncation | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_finance_topic | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_max_results_clamped | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_no_api_key | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_no_time_range_when_zero | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_search_exception | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestTavilySearch::test_time_range | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestWebBrowse::test_basic_browse | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestWebBrowse::test_browse_error | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestWebBrowse::test_extract_links | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| backend | tests/test_web_tools.py::TestWebBrowse::test_pagination | test-contract:tests/test_web_tools.py | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > keeps explicit translation user-triggered with the existing request payload | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > maps explicit translation failure without raw detail | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > maps generation failure without changing question or advanced controls | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > maps open-Card failure and preserves modal focus recovery | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > maps recent Card and Investor Profile load failures separately | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > maps save failure without changing Card identity | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > preserves a translated Card node and sends no second request on locale switch | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > preserves evidence claims rationale and source values byte for byte | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > preserves question advanced controls modal and in-flight work across locale switch | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > reactively localizes shared stance and trace chrome without changing IDs | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > renders English Card chrome without translating generated content | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/AICard.test.tsx::AI Card localization > renders reviewed zh-Hant Card chrome and generated content byte for byte | test-contract:apps/arkscope-web/src/AICard.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > keeps an open Card modal and source Card identity across locale switch | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > preserves loading empty and operation-specific error triggers | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > renders English Home chrome without translating tickers lists or cards | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > renders the reviewed zh-Hant Home chrome and planted source values | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > retries with the existing request shape and no extra request | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > shows only safe Developer diagnostics for a failed workspace load | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Home.test.tsx::Home localization > switches locale without resetting loaded data reading position or focus | test-contract:apps/arkscope-web/src/Home.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > changing the content filter replaces page one and sends the selector | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > load more preserves the selected content filter | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > old-sidecar responses hide the filter and never guess row labels | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > resets a selected unknown filter when another facet has no unknown rows | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > seeking alpha mode has no market content filter or market content labels | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News content availability > shows content facet counts and only honest non-full row labels | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > hides all feed claims and controls for every unavailable SA reason | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > keeps an in-flight page response and renders completion in the active locale | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > offers only the reviewed News and Data Sources recovery targets | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > renders English News chrome while preserving Market source content | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > renders Market and Seeking Alpha load failures without raw detail | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > renders typed SA store availability copy in both locales | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/News.test.tsx::News localization > switches locale without resetting filters pagination items or refetching | test-contract:apps/arkscope-web/src/News.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > hides provider and sync errors outside Developer Mode | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > hides_both_migration_controls_even_for_a_pre_exit_compatibility_response | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > reloads_mounted_news_status_after_a_news_source_is_invalidated | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > renders English news storage copy without changing counts | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > renders_cached_news_status_while_one_stale_refresh_runs | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > renders_empty_and_failed_news_statuses_as_user_outcomes | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsNewsStorage.test.ts::SettingsView news storage copy > renders_normal_news_status_without_migration_narration | test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > does not show the completed App Records migration panel in normal settings navigation | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > ignores retired sync errors and scopes coverage diagnostics to Developer Mode | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > keeps calendar degradation separate from reviewed-day coverage | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > keeps corrected single-locale headings without migration narration | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > keeps unmatched rows and provider issues separate from coverage state | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > keys_trading_day_coverage_by_lookback_and_forces_only_storage_reads | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > lists_the_active_data_group_and_its_stable_subsections | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > offers explicit local confirmation only for listing-status events | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > reloads_mounted_market_and_coverage_status_after_price_invalidation | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > renders English market data and storage outcomes | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > renders_market_empty_and_macro_partial_failures_as_user_outcomes | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > shows SEC lifecycle evidence as review material and reloads it after its source runs | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > shows current market data status without projecting retired sync metadata | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts::post-PG-exit storage panels > shows_macro_data_with_manual_and_scheduled_refresh_boundaries | test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > caches_extension_health_only_after_visible_mount_and_manual_recheck | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > cancels_a_guarded_provider_edit_without_mutation_and_restores_focus | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > coalesces timer and focus reads and preserves prior truth on poll failure | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > confirms guarded IBKR client id edits | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > detects a fast idle-to-idle completion and refreshes related state once | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > does not let an older full refresh replace newer schedule truth | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > does_not_render_backend_storage_route_badges_for_active_schedule_rows | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > does_not_request_or_render_the_detailed_fred_snapshot | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > env-controlled client id never shows a save preview (real env wins precedence) | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > hides planted provider schedule and setup diagnostics in normal mode | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > invalidates_price_news_and_unknown_downstream_keys_after_source_completion | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > keeps long last-run messages out of the schedule row summary | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > keeps structured SA telemetry raw detail out of normal mode | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > keeps_schedule_polling_mounted_only_with_retained_cache_truth | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > labels repair as historical and never as current recovery | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > marks_long_runtime_content_as_wrap_capable | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > polls only schedule after thirty idle seconds without a live region | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > refreshes schedule on focus and full-loads only when lifecycle truth changes | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > removes idle timers and focus listeners and ignores a finishing poll after unmount | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders English data-source health config and schedule tables | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders FRED as configured local snapshot with refresh off | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders IBKR connection settings as one grouped block with derived ids below the client id | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders a localized degraded SA health row in English | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders all three SA chain states with distinct copy and tone | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders config-file provenance with per-field import | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders degraded Alpha Picks history without interrupting a healthy chain | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders durable IBKR partial counts without a manual continuation action | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders entitlement-blocked bodies as retained headlines without a retry action | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders only admitted SA diagnostic fields in Developer Mode | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders partial retry outcome with backlog and no continuation button | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders price partial facts without a Continue control in both locales | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders succeeded IBKR run and scheduled body backlog as separate facts | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders_cached_schedule_health_and_config_before_one_stale_refresh | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders_disabled_providers_as_neutral_and_partitions_every_registered_schedule_row_into_one_controllable_owner | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders_known_schedule_progress_without_covering_the_last_run_cell | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders_persisted_skipped_history_as_neutral_instead_of_never_run | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > reports_mutations_as_navigation_blocking_and_clears_after_completion | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > reports_unsaved_provider_and_schedule_drafts_to_navigation_owner | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > reveals the same planted diagnostics only in Developer Mode | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > settings_data_sources_does_not_own_portfolio_capture_controls | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > shows backend-driven derived IBKR client ids with live draft preview | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > switches locale without resetting drafts polling cadence or progress | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > switches to five second polling while running and back to idle after completion | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > wraps_each_wide_data_source_table_in_an_explicit_scroll_owner | test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsStabilizationCss.test.ts::Settings stabilization CSS contracts > gives_wide_settings_tables_one_horizontal_scroll_owner_and_reviewed_min_widths | test-contract:apps/arkscope-web/src/SettingsStabilizationCss.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/SettingsStabilizationCss.test.ts::Settings stabilization CSS contracts > keeps_detail_cells_wrap_capable_and_normal_sections_free_of_migration_copy | test-contract:apps/arkscope-web/src/SettingsStabilizationCss.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > maps reviewed source-path enums and preserves unknown stable IDs | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > preserves note draft and maps note load add and delete failures separately | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > preserves successful price and fundamentals legs while retiring legacy IV requests | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > preserves tag draft and maps catalog add and remove failures separately | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > renders English ticker chrome without translating financial statement rows | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > renders price failure independently from successful detail state | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > renders reviewed zh-Hant ticker chrome and planted source values | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > renders ticker-state failure by operation without raw detail | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > shows only safe ticker diagnostics in Developer Mode | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > switches locale without resetting the active tab day window data or focus | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/TickerDetail.test.tsx::Ticker Detail localization > updates memoized chrome in place without resetting reading position or refetching | test-contract:apps/arkscope-web/src/TickerDetail.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > preserves hide confirmation and renders hide failure by operation | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > preserves the groups-unavailable import warning without source-tag translation | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > preserves unknown facet IDs and filter results across locale switch | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > renders English Universe chrome while preserving tickers tags and lists | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > renders active-universe failure with the exact Data Sources recovery target | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > renders import failure without raw backend detail in normal mode | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > renders structured import counts in both locales | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > renders the reviewed zh-Hant Universe title and terminology corrections | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Universe.test.tsx::Universe localization > switches locale without clearing query list facets outcome or busy ticker | test-contract:apps/arkscope-web/src/Universe.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > does not replay list membership archive or priority mutations on locale switch | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > keeps optimistic priority work in flight and renders completion in the active locale | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > keeps silent list default and search degradation silent | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > preserves create rename and member-search drafts across locale switch | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > preserves list Universe consensus loading and degraded trigger semantics | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > preserves node identity focus and Explore request counts during locale switch | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > preserves selected list archived filter and sort across locale switch | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > renders English Watchlist chrome without translating custom lists tags or tickers | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > renders consensus chrome locally while preserving Provider payload values | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > renders the reviewed zh-Hant Watchlist corrections and source values | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/Watchlist.test.tsx::Watchlist localization > renders visible Watchlist failures by operation without raw detail | test-contract:apps/arkscope-web/src/Watchlist.test.tsx | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > keeps partial and unknown ticker facts independent | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > maps calendar and observation health without parsing diagnostics | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > maps every Coverage v2 day reason in both locales | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > maps every Coverage v2 day status in both locales and reserves positive tone for complete | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > maps non-trading closure reasons without backend prose | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > renders unmatched RTH rows as a separate data-quality warning | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::coverageStatusLabel > separates security review signals from generic provider issues | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::localized Settings market-data presentations > keeps raw schedule reasons out of semantic status mapping | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::localized Settings market-data presentations > renders Settings market and schedule presentations in both locales | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::macroRoutingLabel > labels local-first active (toggle vs env), DB built | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::macroRoutingLabel > never suggests PG fallback when local macro is inactive | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::macroRoutingLabel > toggle-on but DB not built → local-first, pending ingestion (NOT PG fallback) | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::marketRoutingLabel > keeps pending-db distinct while disabled setting is no longer PG fallback | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::marketRoutingLabel > renders prices as local authority after P0-C | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::news cutover labels > keeps normalized writes visibly pre-exit/test while PG remains available | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::news cutover labels > renders the locked post-exit state | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::newsRoutingLabel > distinguishes default direct routing from explicit rollback | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::newsRoutingLabel > makes env override direction explicit | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::providerHealthStatusLabel > keeps generic disabled providers as disabled | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::providerHealthStatusLabel > labels legacy disabled FRED macro ingestion as generic disabled | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::providerHealthStatusLabel > labels strict missing provider config as not configured | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > describes due and never-attempted bodies without a manual action | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > explains entitlement-blocked bodies without calling them permanently missing | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > fails closed on malformed backlog counts | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > keeps a succeeded run successful when bodies are scheduled later | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > renders backlog-query failure as unavailable rather than zero | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerBodyBacklogPresentation > separates new body backlog from the partial run label | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > distinguishes succeeded / failed / skipped / running / none | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > does not turn invalid observed counts into numeric promises | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > keeps actionable ticker continuation ahead of informational counts | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > labels stale running as an interrupted/stuck state | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > names an IBKR Gateway failure instead of collapsing it into generic failure | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > names an IBKR headline coverage gap instead of showing generic partial | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > partial with deferred → needs manual continue (補抓) | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > partial without actionable or observed continuation is generic | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > renders durable IBKR body counts without promising a manual retry | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > renders price unresolved count and bounded ticker list without continuation | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > renders sanitized count/cursor state {"deferred_ticker_count":0,"deferred_body_count":0,"has_cursor":true} | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > renders sanitized count/cursor state {"deferred_ticker_count":3,"deferred_body_count":0,"has_cursor":false} | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |
| frontend | apps/arkscope-web/src/marketDataDisplay.test.ts::schedulerStateLabel > renders sanitized count/cursor state {"deferred_ticker_count":3,"deferred_body_count":10,"has_cursor":false} | test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts | passed | current_product | ["sealed_fixture"] |

Exact node relationships: `1921`; unique focused nodes: `1897`; outcomes: `{"passed":1878,"skipped":19}`; roles: `{"current_product":1763,"historical_compatibility":23,"negative_no_pg":33,"pg_only":102}`.

## 7. Temporary CLI Handoff

This table carries command identity only. `legacy-agent` is not a retirement ruling; the
post-no-tail CLI census independently rescans master and consumes only a neutral survivor seed.

| Entrypoint ID | Path | Symbol | Class | Surface | Disposition |
|---|---|---|---|---|---|
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:build | apps/arkscope-web/package.json | npm:build | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:check:i18n-literals | apps/arkscope-web/package.json | npm:check:i18n-literals | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:dev | apps/arkscope-web/package.json | npm:dev | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:preview | apps/arkscope-web/package.json | npm:preview | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:test | apps/arkscope-web/package.json | npm:test | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:test:watch | apps/arkscope-web/package.json | npm:test:watch | operator | - | - |
| cli_registry:apps/arkscope-web/package.json:-:-:cli_entrypoint:npm:typecheck | apps/arkscope-web/package.json | npm:typecheck | operator | - | - |
| cli_registry:data_sources/financial_metrics_calculator.py:1253:0:cli_entrypoint:python -m data_sources.financial_metrics_calculator | data_sources/financial_metrics_calculator.py | python -m data_sources.financial_metrics_calculator | operator | - | - |
| cli_registry:data_sources/sec_earnings_releases.py:297:0:cli_entrypoint:python -m data_sources.sec_earnings_releases | data_sources/sec_earnings_releases.py | python -m data_sources.sec_earnings_releases | operator | - | - |
| cli_registry:data_sources/sec_insider_trades.py:372:0:cli_entrypoint:python -m data_sources.sec_insider_trades | data_sources/sec_insider_trades.py | python -m data_sources.sec_insider_trades | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py:181:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.controller_probe | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py | python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.controller_probe | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1089:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.destructive_controller | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py | python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.destructive_controller | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py:1137:0:cli_entrypoint:python docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py | python docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py:183:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_consumer_census | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py | python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_consumer_census | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py:296:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_db_row_manifest | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py | python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_db_row_manifest | operator | - | - |
| cli_registry:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py:661:0:cli_entrypoint:python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_price_manifest | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py | python -m docs.superpowers.evidence.2026-08-04-eir-006-deletion-manifest.task8_price_manifest | operator | - | - |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:618:0:cli_entrypoint:python -m extensions.sa_alpha_picks.build_firefox | extensions/sa_alpha_picks/build_firefox.py | python -m extensions.sa_alpha_picks.build_firefox | operator | - | - |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:651:0:cli_entrypoint:extensions/sa_alpha_picks/build_firefox.py | extensions/sa_alpha_picks/build_firefox.py | extensions/sa_alpha_picks/build_firefox.py | operator | - | - |
| cli_registry:extensions/sa_alpha_picks/build_firefox.py:651:0:cli_entrypoint:python extensions/sa_alpha_picks/build_firefox.py | extensions/sa_alpha_picks/build_firefox.py | python extensions/sa_alpha_picks/build_firefox.py | operator | - | - |
| cli_registry:extensions/sa_alpha_picks/install.sh:-:-:cli_entrypoint:extensions/sa_alpha_picks/install.sh | extensions/sa_alpha_picks/install.sh | extensions/sa_alpha_picks/install.sh | mixed | cli:extensions/sa_alpha_picks/install.sh:extensions_sa_alpha_picks_install.sh | retain_operator_remove_pg_branch |
| cli_registry:extensions/sa_alpha_picks/install_firefox.sh:-:-:cli_entrypoint:extensions/sa_alpha_picks/install_firefox.sh | extensions/sa_alpha_picks/install_firefox.sh | extensions/sa_alpha_picks/install_firefox.sh | mixed | cli:extensions/sa_alpha_picks/install_firefox.sh:extensions_sa_alpha_picks_install_firefox.sh | retain_operator_remove_pg_branch |
| cli_registry:package.json:-:-:cli_entrypoint:npm:build | package.json | npm:build | operator | - | - |
| cli_registry:package.json:-:-:cli_entrypoint:npm:dev:desktop | package.json | npm:dev:desktop | operator | - | - |
| cli_registry:package.json:-:-:cli_entrypoint:npm:dev:web | package.json | npm:dev:web | operator | - | - |
| cli_registry:package.json:-:-:cli_entrypoint:npm:start | package.json | npm:start | operator | - | - |
| cli_registry:src/agents/cli.py:2506:0:cli_entrypoint:python -m src.agents.cli | src/agents/cli.py | python -m src.agents.cli | legacy-agent | cli:src/agents/cli.py:legacy-agent | defer_to_legacy_agent_cli_census |
| cli_registry:src/agents/openai_agent/agent.py:-:-:cli_entrypoint:python -m src.agents.openai_agent.agent | src/agents/openai_agent/agent.py | python -m src.agents.openai_agent.agent | legacy-agent | cli:src/agents/openai_agent/agent.py:legacy-agent | defer_to_legacy_agent_cli_census |
| cli_registry:src/api/__main__.py:15:0:cli_entrypoint:python -m src.api.__main__ | src/api/__main__.py | python -m src.api.__main__ | operator | - | - |
| cli_registry:src/audit/ibkr_news_catchup_audit.py:259:0:cli_entrypoint:python -m src.audit.ibkr_news_catchup_audit | src/audit/ibkr_news_catchup_audit.py | python -m src.audit.ibkr_news_catchup_audit | operator | - | - |
| cli_registry:src/audit/sa_article_reconciliation.py:11:0:cli_entrypoint:python -m src.audit.sa_article_reconciliation | src/audit/sa_article_reconciliation.py | python -m src.audit.sa_article_reconciliation | mixed | cli:src/audit/sa_article_reconciliation.py:argparse.ArgumentParser | retain_operator_remove_pg_branch |
| cli_registry:src/audit/universe_retirement.py:1000:0:cli_entrypoint:python -m src.audit.universe_retirement | src/audit/universe_retirement.py | python -m src.audit.universe_retirement | mixed | cli:src/audit/universe_retirement.py:argparse.ArgumentParser | retain_operator_remove_pg_branch |
| cli_registry:src/collectors/finnhub_news.py:684:0:cli_entrypoint:python -m src.collectors.finnhub_news | src/collectors/finnhub_news.py | python -m src.collectors.finnhub_news | operator | - | - |
| cli_registry:src/collectors/polygon_news.py:1104:0:cli_entrypoint:python -m src.collectors.polygon_news | src/collectors/polygon_news.py | python -m src.collectors.polygon_news | operator | - | - |
| cli_registry:src/daily_update.py:379:0:cli_entrypoint:python -m src.daily_update | src/daily_update.py | python -m src.daily_update | mixed | cli:src/daily_update.py:argparse.ArgumentParser | retain_operator_remove_pg_branch |
| cli_registry:src/news_normalized/ibkr_cli.py:380:0:cli_entrypoint:python -m src.news_normalized.ibkr_cli | src/news_normalized/ibkr_cli.py | python -m src.news_normalized.ibkr_cli | operator | - | - |
| cli_registry:src/options_math/option_pricing.py:1335:0:cli_entrypoint:python -m src.options_math.option_pricing | src/options_math/option_pricing.py | python -m src.options_math.option_pricing | operator | - | - |
| cli_registry:src/prices_runtime.py:153:0:cli_entrypoint:python -m src.prices_runtime | src/prices_runtime.py | python -m src.prices_runtime | operator | - | - |
| cli_registry:src/sa_native_host.py:1290:0:cli_entrypoint:python -m src.sa_native_host | src/sa_native_host.py | python -m src.sa_native_host | mixed | cli:src/sa_native_host.py:main | retain_operator_remove_pg_branch |
| cli_registry:src/sa_native_host.py:1290:0:cli_entrypoint:python src/sa_native_host.py | src/sa_native_host.py | python src/sa_native_host.py | mixed | cli:src/sa_native_host.py:main | retain_operator_remove_pg_branch |
| cli_registry:src/smoke/pg_unreachable_e2e.py:616:0:cli_entrypoint:python -m src.smoke.pg_unreachable_e2e | src/smoke/pg_unreachable_e2e.py | python -m src.smoke.pg_unreachable_e2e | PG-only | cli:src/smoke/pg_unreachable_e2e.py:argparse.ArgumentParser | retire_pg_only |
| cli_registry:src/smoke/pg_unreachable_e2e.py:634:0:cli_entrypoint:python src/smoke/pg_unreachable_e2e.py | src/smoke/pg_unreachable_e2e.py | python src/smoke/pg_unreachable_e2e.py | PG-only | cli:src/smoke/pg_unreachable_e2e.py:argparse.ArgumentParser | retire_pg_only |
| cli_registry:tests/live/sdk_driver_smoke.py:-:-:cli_entrypoint:python tests/live/sdk_driver_smoke.py | tests/live/sdk_driver_smoke.py | python tests/live/sdk_driver_smoke.py | operator | - | - |
| cli_registry:tests/live/sdk_route_smoke.py:-:-:cli_entrypoint:python tests/live/sdk_route_smoke.py | tests/live/sdk_route_smoke.py | python tests/live/sdk_route_smoke.py | operator | - | - |
| cli_registry:tests/live/smoke_fred.py:149:0:cli_entrypoint:python -m tests.live.smoke_fred | tests/live/smoke_fred.py | python -m tests.live.smoke_fred | mixed | cli:tests/live/smoke_fred.py:main | retain_operator_remove_pg_branch |
| cli_registry:tests/live/smoke_fred.py:149:0:cli_entrypoint:python tests/live/smoke_fred.py | tests/live/smoke_fred.py | python tests/live/smoke_fred.py | mixed | cli:tests/live/smoke_fred.py:main | retain_operator_remove_pg_branch |
| cli_registry:tests/test_ibkr_scanner.py:296:0:cli_entrypoint:python -m tests.test_ibkr_scanner | tests/test_ibkr_scanner.py | python -m tests.test_ibkr_scanner | operator | - | - |
| cli_registry:tests/test_option_pricing.py:696:0:cli_entrypoint:python -m tests.test_option_pricing | tests/test_option_pricing.py | python -m tests.test_option_pricing | operator | - | - |

## 8. Documentation Claims

| ID | Path | Line refs | Status | Disposition |
|---|---|---|---|---|
| documentation:README.md | README.md | ["25","26","27","66","67","9"] | current | rewrite_current_authority |
| documentation:data_sources/DATA_SOURCE_QUIRKS.md | data_sources/DATA_SOURCE_QUIRKS.md | ["19"] | current | rewrite_current_authority |
| documentation:docker/README.md | docker/README.md | ["1","15","19","25","26","30","4","40","41","42","45","46","49","50","53","56","58","59","6","68","69","72","79","80"] | archive_instruction | retire_pg_only |
| documentation:docs/PROJECT_HISTORY.md | docs/PROJECT_HISTORY.md | ["74"] | historical | retire_pg_only |
| documentation:docs/PUBLICATION_REVIEW.md | docs/PUBLICATION_REVIEW.md | ["16","18","65","68","70","72"] | current | rewrite_current_authority |
| documentation:docs/data/DATA_INVENTORY.md | docs/data/DATA_INVENTORY.md | ["284"] | historical | retire_pg_only |
| documentation:docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md | docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md | ["21"] | historical | retire_pg_only |
| documentation:docs/data/OPTIONS_PRICING_THEORY.md | docs/data/OPTIONS_PRICING_THEORY.md | ["557"] | current | rewrite_current_authority |
| documentation:docs/design/AGENT_EVOLUTION_TRACKER.md | docs/design/AGENT_EVOLUTION_TRACKER.md | ["1160","1455","1466","1472","1478","277","70","755","769","859","901","925","927","939","944","947","948","950","956","961","964","965","966","971","973","984","988","989","990","991","992","993","994"] | historical | retire_pg_only |
| documentation:docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md | docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md | ["391"] | current | rewrite_current_authority |
| documentation:docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md | docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md | ["134","171"] | current | rewrite_current_authority |
| documentation:docs/design/CONFIG_AUTHORITY_PLAN.md | docs/design/CONFIG_AUTHORITY_PLAN.md | ["191","193","199"] | current | rewrite_current_authority |
| documentation:docs/design/CREDENTIAL_MANAGEMENT_PLAN.md | docs/design/CREDENTIAL_MANAGEMENT_PLAN.md | ["354"] | current | rewrite_current_authority |
| documentation:docs/design/CURRENT_PROJECT_CONTEXT.md | docs/design/CURRENT_PROJECT_CONTEXT.md | ["29","45","52"] | current | rewrite_current_authority |
| documentation:docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md | docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md | ["11","112","113","114","115","117","118","119","120","121","124","126","128","138","139","142","143","147","149","151","155","156","175","179","183","186","187","190","192","194","196","198","200","201","202","205","206","211","212","213","214","215","221","226","227","228","237","243","245","252","270","280","281","282","283","287","288","289","293","294","296","298","30","301","302","304","307","32","321","322","326","329","333","334","337","339","347","348","349","361","366","392","400","411","42","43","432","47","473","485","486","489","491","492","493","494","6","61","69"] | current | rewrite_current_authority |
| documentation:docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md | docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md | ["25"] | current | rewrite_current_authority |
| documentation:docs/design/DESKTOP_APP_VISION_DRAFT.md | docs/design/DESKTOP_APP_VISION_DRAFT.md | ["247","260","261"] | current | rewrite_current_authority |
| documentation:docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md | docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md | ["119","125","46","72","73","74","75","76","77"] | historical | retire_pg_only |
| documentation:docs/design/ENGINEERING_ISSUE_REGISTER.md | docs/design/ENGINEERING_ISSUE_REGISTER.md | ["163","164"] | current | rewrite_current_authority |
| documentation:docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md | docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md | ["598","599"] | current | rewrite_current_authority |
| documentation:docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md | docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md | ["365","40","7"] | current | rewrite_current_authority |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md | docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md | ["101","248","250","253","263","269","273","335","347","385","489","490"] | historical | retire_pg_only |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md | docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md | ["15","17","203","213","217","218","223","248","264","31","358","36","360","362","363","364","366","404","49","51","53","54","55","672","675","766","767","768","786","796","813","846","866"] | current | rewrite_current_authority |
| documentation:docs/design/LOCAL_STORAGE_TOPOLOGY.md | docs/design/LOCAL_STORAGE_TOPOLOGY.md | ["111","145","147","150","154"] | current | rewrite_current_authority |
| documentation:docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md | docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md | ["27","34","46","5","75","84","85"] | current | rewrite_current_authority |
| documentation:docs/design/NEWS_DIRECT_LOCAL_PLAN.md | docs/design/NEWS_DIRECT_LOCAL_PLAN.md | ["1","111","127","128","15","152","16","199","206","22","23","283","284","286","287","288","291","296","34","358","359","361","365","368","369","370","374","375","376","38","383","395","405","43","47","51","75","76","85","91","92","93"] | historical | retire_pg_only |
| documentation:docs/design/P1_2_PROVIDER_DISCOVERY.md | docs/design/P1_2_PROVIDER_DISCOVERY.md | ["301"] | historical | retire_pg_only |
| documentation:docs/design/P1_2_SPEC.md | docs/design/P1_2_SPEC.md | ["235"] | historical | retire_pg_only |
| documentation:docs/design/P1_3_SPEC.md | docs/design/P1_3_SPEC.md | ["304","55"] | historical | retire_pg_only |
| documentation:docs/design/P1_5_S3_OSS_SPIKE_DECISION.md | docs/design/P1_5_S3_OSS_SPIKE_DECISION.md | ["112","35","36","92"] | current | rewrite_current_authority |
| documentation:docs/design/PG_EXIT_COMPLETION_PLAN.md | docs/design/PG_EXIT_COMPLETION_PLAN.md | ["1","10","101","103","104","105","107","109","111","116","117","126","127","128","132","133","134","137","139","142","144","145","146","147","148","149","150","152","170","20","22","26","31","32","33","36","38","40","41","47","48","49","50","54","57","6","62","64","65","66","69","7","70","77","78","8","82","84","86","88","9","94","96","97","98"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md | docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md | ["1","100","101","1010","1018","1019","102","1026","1027","1037","1039","104","1048","1052","106","1086","1099","11","110","1121","1143","1151","1152","1159","1161","1170","1198","1199","1210","1216","1239","1242","1247","1279","1283","1286","1296","1305","1331","1341","1344","1358","1364","1378","1382","1385","1388","1394","1396","1410","1411","1412","1414","1418","1426","1427","1429","1430","1431","1436","1437","1447","167","17","174","186","19","201","213","223","228","235","237","241","245","256","270","277","282","284","288","290","297","309","313","322","328","333","336","338","344","347","352","355","357","363","371","374","388","392","394","402","403","408","409","414","442","449","454","458","461","462","463","467","470","472","473","481","5","514","527","531","546","553","566","57","582","593","601","602","609","610","618","622","625","64","640","664","671","69","699","7","702","709","71","72","723","728","73","736","74","749","754","79","792","80","804","805","809","83","830","834","835","836","837","838","839","847","848","866","874","882","883","89","892","893","895","896","90","902","91","916","923","929","930","932","935","938","945","95","956","96","960","97","98","981","982","983","991"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md | docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md | ["11","114","118","122","132","137","141","142","147","152","156","160","161","163","166","188","19","192","20","21","218","220","23","237","248","255","273","286","287","29","294","30","31","32","323","329","33","331","333","34","343","360","373","38","39","41","448","45","453","456","46","461","463","468","47","472","474","477","48","484","488","491","492","493","496","5","519","520","522","527","56","62","64","65","67","68","7","78","79","80","82","85","88","89","9","92"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md | docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md | ["1","10","106","113","119","120","121","123","128","13","14","146","153","156","16","160","164","165","169","170","176","179","18","181","184","186","187","194","20","207","22","221","238","24","241","245","249","253","257","273","274","282","283","32","322","33","330","34","340","343","346","349","35","361","362","43","44","45","451","452","454","455","456","458","459","462","463","47","48","49","5","511","519","521","522","533","547","548","549","55","554","56","570","574","578","580","581","583","584","591","597","62","621","623","630","641","646","66","662","68","681","69","709","71","729","732","734","735","737","738","745","75","753","760","77","770","771","773","784","786","790","791","792","793","794","798","799","801","807","809","810","9","92","94","95","97"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md | docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md | ["25","331","342","37","437","57","61","793","831","832","897","934","98"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md | docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md | ["100","101","1015","102","1026","1027","103","106","1064","1072","1074","1081","1082","1087","1089","11","110","1102","1105","1109","111","1110","1126","1133","114","1141","1181","1193","1201","1257","126","1288","1297","1298","130","1300","136","1367","1368","1398","140","1403","1404","1406","141","1414","142","1421","1429","1430","1438","144","1441","1442","1443","1448","1455","1457","1458","1460","1469","1477","1480","1486","1489","1491","1507","151","1524","1526","1528","162","164","167","168","182","187","20","206","228","229","236","241","242","244","246","251","252","254","256","26","264","269","277","278","295","30","305","306","356","357","372","377","379","390","404","408","414","418","420","426","427","428","471","480","499","508","509","568","569","571","598","599","65","67","685","687","692","695","696","697","7","70","701","703","704","706","707","708","710","711","715","716","737","744","777","79","80","81","824","829","84","842","844","845","847","852","858","867","884","895","897","9","904","910","918","939","947","958","960","997"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md | docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md | ["1","100","101","11","111","113","114","116","117","125","126","130","131","132","145","149","153","154","158","159","162","163","18","196","200","201","208","211","214","215","217","218","219","22","221","227","234","249","273","280","287","292","299","313","321","409","416","417","419","420","421","422","429","43","430","438","44","45","47","472","473","481","482","491","495","499","5","502","503","508","511","513","529","53","54","546","549","55","550","554","555","56","563","57","571","572","577","588","596","600","601","605","606","616","619","621","629","63","639","64","640","65","653","654","659","660","662","663","664","665","669","674","675","685","686","688","697","699","7","701","706","71","713","714","715","74","82","83","9","96","98"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_REMAINDER_SCOPING.md | docs/design/PG_EXIT_REMAINDER_SCOPING.md | ["1","101","106","119","124","125","147","152","153","155","156","157","162","166","168","172","173","175","176","177","185","19","194","196","221","223","240","257","258","259","26","260","262","263","264","265","269","280","283","420","421","464","48","5","50","52","54","55","56","57","577","58","584","585","587","589","59","592","593","6","60","61","62","63","86"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md | docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md | ["1","105","11","118","119","123","127","129","130","17","183","185","190","199","210","217","219","225","253","259","261","285","288","31","39","41","5","55","57","7","97","99"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md | docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md | ["1","103","106","108","110","112","113","114","116","12","120","130","133","137","140","161","17","171","176","187","188","19","20","214","216","225","226","228","23","234","236","241","248","309","314","32","321","324","327","329","332","338","339","34","345","359","360","361","364","369","37","374","375","383","384","390","412","415","45","46","48","58","59","60","64","75","79","80","83","85","88","9"] | historical | retire_pg_only |
| documentation:docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md | docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md | ["1","10","12","20","21","29","33","34","39","41","42","44","45","46","52","54","55","56","6","65","66","68","69","74","77","8","80","83","88","89","90"] | historical | retire_pg_only |
| documentation:docs/design/README.md | docs/design/README.md | ["51","64"] | current | rewrite_current_authority |
| documentation:docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md | docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md | ["17","62","63"] | current | rewrite_current_authority |
| documentation:docs/design/REPO_HYGIENE_AUDIT_2026_07.md | docs/design/REPO_HYGIENE_AUDIT_2026_07.md | ["125","136","168","26","59","60","61","64","67"] | historical | retire_pg_only |
| documentation:docs/design/RL_COLLAPSE_FINDINGS.md | docs/design/RL_COLLAPSE_FINDINGS.md | ["183"] | historical | retire_pg_only |
| documentation:docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md | docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md | ["22"] | current | rewrite_current_authority |
| documentation:docs/design/SA_CUTOVER_3D_RUNBOOK.md | docs/design/SA_CUTOVER_3D_RUNBOOK.md | ["1","108","113","114","13","136","143","147","15","153","160","162","163","164","166","168","17","175","176","18","19","29","3","30","31","32","35","38","44","45","46","47","48","49","55","56","57","58","59","60","66","69","7","78","79","80","81","82","90"] | historical | retire_pg_only |
| documentation:docs/design/SA_EVIDENCE_FEED_C1_SPEC.md | docs/design/SA_EVIDENCE_FEED_C1_SPEC.md | ["13","59"] | current | rewrite_current_authority |
| documentation:docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md | docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md | ["34"] | current | rewrite_current_authority |
| documentation:docs/design/SCHEDULER_HARDENING_PLAN.md | docs/design/SCHEDULER_HARDENING_PLAN.md | ["107","138","139","159","28","29","30","34","35","37","48","53","56","76","77"] | current | rewrite_current_authority |
| documentation:docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md | docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md | ["220","96","98"] | historical | retire_pg_only |
| documentation:docs/design/archive/README.md | docs/design/archive/README.md | ["19"] | archive_instruction | retire_pg_only |
| documentation:docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md | docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md | ["20","21","22","23","25","26","27"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md | docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md | ["120","146"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md | docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md | ["203","204","281","435","436"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md | docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md | ["148","163","241","242","286","311","312","353","483","534","93"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md | docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md | ["141","215","216","287","301","382","483","520","548","560","565","64","83","9"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md | docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md | ["19","23","280","281","333","362","376","390","44"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md | docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md | ["109","111","118","123","357","554","555"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md | docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md | ["457","463","491","505","53"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md | docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md | ["306","377","381","520"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md | docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md | ["436","447","509","596","809"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv | docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv | ["15","16","17","18","19","67","68","90","91","92","93","94"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | ["195","196","411","435","459","570","84"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md | docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md | ["303","316","339"] | historical | retire_pg_only |
| documentation:docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md | docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md | ["157","262","291","352","381","384"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-06-27-news-direct-cutover.md | docs/superpowers/plans/2026-06-27-news-direct-cutover.md | ["66","68","7","72"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-06-27-news-identity-repair.md | docs/superpowers/plans/2026-06-27-news-identity-repair.md | ["540","575","7"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md | docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md | ["1128","1316","1376","22"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md | docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md | ["1034","1220","25","877","9"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md | docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md | ["1","302","32","37","377","38","40","405","421","43","457","466","471","473","476","478","479","483","489","491","499","502","503","508","511","513","514","535","549","550","551","559","578","59","604","614","629","630","649","658","667","685","689","7","737","739","740","746","751","84","9"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md | docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md | ["19","291","330","437","471","491","495","506","516","537"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md | docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md | ["1045","1050","1071","1073","1074","1076","11","112","131","17","183","209","269","274","292","294","295","30","315","33","380","384","39","41","42","44","456","459","463","467","488","49","51","510","513","521","526","537","57","585","622","636","680","7","707","726","752","773","803","820","832","842","866","873","874","882","893","9","900","931","934","94","940","946","952","97","972","975","98","982","983"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md | docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md | ["110","129","1581","1586","1650","1673","24","38","63","89","9"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md | docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md | ["112","114","116","120","127","132","135","17","18","19","21","228","246","253","260","264","313","35","39","404","41","414","427","43","453","457","460","485","518","524","529","530","531","534","551","556","592","603","604","616","62","625","657","664","79","9","93"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md | docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md | ["1","119","129","134","137","156","165","17","19","22","23","354","38","412","49","5","60","648","65","655","664","665","667","672","674","685","687","695","7","705","709","729","742","743","771","779","780","805","81","810","815","820","828","83","851","91"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-05-macro-snapshot-display.md | docs/superpowers/plans/2026-07-05-macro-snapshot-display.md | ["353","48","531","534","535","568","569","572","7","718","726","732","76","760","761","780","795","805","806","93"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-05-news-burst-hardening.md | docs/superpowers/plans/2026-07-05-news-burst-hardening.md | ["1084","1127","1138","1157","1160","1183","1186","1195","15","16","62"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md | docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md | ["1429","1440","1465","1493","1502","1545","23","38","5"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md | docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md | ["108","109","11","13","141","148","156","164","196","203","204","209","21","210","219","223","227","23","230","237","24","240","252","261","265","269","276","28","312","320","327","328","331","333","334","335","342","35","36","37","39","392","395","40","424","448","45","451","456","459","469","475","482","488","489","490","491","494","501","7","71"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md | docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md | ["100","103","104","11","132","144","147","150","152","16","163","166","170","176","178","179","180","181","186","188","196","20","204","205","226","235","236","245","263","27","28","284","323","332","36","37","38","39","41","486","487","489","500","53","541","62","64","66","67","7","76","80","82","87","9","92","95","99"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md | docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md | ["41","91"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-investor-profile-track-a.md | docs/superpowers/plans/2026-07-06-investor-profile-track-a.md | ["15","16","865","868"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md | docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md | ["11","123","138","33","34","36","44","5","6","65","71","72","74","77","86","88","89","95"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md | docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md | ["10","104","131","270","43"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md | docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md | ["115","119","134","16","168","23","43","60","83","84","86","92","96"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-07-current-quote-tool.md | docs/superpowers/plans/2026-07-07-current-quote-tool.md | ["876","881","884","928"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md | docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md | ["1012","1027","1028","1048","1049","1079","1080","1084","150","151","163","164","51"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md | docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md | ["1523","1528","1531","4"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-10-holdings-row-actions.md | docs/superpowers/plans/2026-07-10-holdings-row-actions.md | ["157","158","483","486","489"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-10-model-capability-catalog.md | docs/superpowers/plans/2026-07-10-model-capability-catalog.md | ["1343","1346","308","38","39"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-11-models-ux-implementation.md | docs/superpowers/plans/2026-07-11-models-ux-implementation.md | ["18","46","464","47","533","534"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md | docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md | ["114","504","508","98"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md | docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md | ["1011","1017","1020","19","20"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md | docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md | ["101","1130","1143","1146","1153","1161","1195","1211","1292","1293","1326","1377","1385","1409","1418","1494","151","1532","1544","1567","1663","1719","1722","1725","1813","221","58"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md | docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md | ["2242","2247","2250","41","42","68"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-12-subscription-card-routing.md | docs/superpowers/plans/2026-07-12-subscription-card-routing.md | ["110","112","91"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md | docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md | ["1602","1623","1631","1635","170","1721","31","32","54","55"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md | docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md | ["150","1951","1965","1973","1976","2097","37","40"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md | docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md | ["1044","136","51","56","913","934","937","98","996"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md | docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md | ["114","131","1509","1522","1531","1534","1537","1540","1677","184","45","50","6"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md | docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md | ["24","34","584","69","7"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md | docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md | ["1061","117","123","177","178","30","891","941","945","949","950","987"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md | docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md | ["1056","178","179","192","344","349","357","359","401","403","43","45","645","648","650","651","660","668","669","670","699","701","709","710","712","713","722","724","855","862","864","866","869"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md | docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md | ["1163","1173","1208","1211","1220","1234","1269","1275","1277","1278","1282","1288","1291","1294","1298","1413","1422","1423","15","166","1912","2419","244","245","2522","2524","2525","264","2960","3121","318","3235","3237","3238","3366","3395","3396","925"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md | docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md | ["1364","1375","1376","228","276","281","282"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md | docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md | ["1202","1331","1335","1338","1339","1524","1535","1539","1783","1784","1841","1842"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md | docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md | ["1027","1038","1066","198","264","298","350","694","775","782","913","924","935","973"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md | docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md | ["192","340","676","775","791"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-20-i18n-0-foundation.md | docs/superpowers/plans/2026-07-20-i18n-0-foundation.md | ["1074","1076","1188","64","67"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md | docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md | ["1390","1393","1399","1415","1489","1500","444"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-20-i18n-2-settings.md | docs/superpowers/plans/2026-07-20-i18n-2-settings.md | ["1000","1329","1443","1446","157","1715","1800","24","2615","2667","2759","2796","3019","3156","3159","3165","3184","3205","3297","3317","867","986","987","993","995","996","997"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md | docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md | ["2199","2201","2202","2294","2347","2453","2476","2507"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-23-i18n-3-explore.md | docs/superpowers/plans/2026-07-23-i18n-3-explore.md | ["1667","1791","396","760","761","765"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md | docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md | ["1376","1544","1548","1549","1644","1711","1712","1790","395"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md | docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md | ["450","464","472","499"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-25-i18n-6-release.md | docs/superpowers/plans/2026-07-25-i18n-6-release.md | ["1060","1065","1069","1070","1079","1421","1525","174","200","202","203","204","275","28","388","397","589","594","607","855","864"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md | docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md | ["1899"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md | docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md | ["1182","1193","1465","1524","1593","1712","1716","1736","1766","1799","1832","1883","1914","239","274","319","370","438","470","575","622"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md | docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md | ["1023","1149","1158","122","1264","1273","1278","1283","1327","1330","1339","1362","1367","1373","1418","1505","1683","1699","1732","1774","1789","217","218","223","226","243","273","316","317","38","423","427","433","49","491","492","494","50","502","503","518","521","522","523","526","644","646","65","668","678","689","705","719","729","787","801","884"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md | docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md | ["109","1135","1140","1142","1149","1152","1174","1199","1242","1265","1306","140","218","324","613","615","667","674","678","695","799","816","846"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md | docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md | ["1282","143","1949","1951","1955","3193","3195","3199","3200","3271"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-29-query-route-harness-termination.md | docs/superpowers/plans/2026-07-29-query-route-harness-termination.md | ["79"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md | docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md | ["1831","1936","1971","1985","2065","384","619"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md | docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md | [] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md | docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md | ["1244","1258","1263","1296","1424","1480","254","273","292","411","449","487","529","705","711","848"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md | docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md | ["1549","1577","1648","1652","1671","1697","1760","1812","1843","2078","2084","2151","236","249","2705","337","355","509","908","909"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md | ["1043","150","214","303","331","339","473","474","489","491","703","784","799","827","936","937"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md | docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md | ["419"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md | docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md | ["388","463","537","618","636","743"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md | docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md | ["1059","1064","1068","114","145","265","29","290","733","745","746","748","749","75","823","930"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md | docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md | ["126","968","969","970"] | historical | retire_pg_only |
| documentation:docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md | docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md | ["123","140","190","207","463","464","611","759","97","98"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md | docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md | ["296"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-06-27-news-identity-repair-design.md | docs/superpowers/specs/2026-06-27-news-identity-repair-design.md | ["102","157","47"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-06-28-news-article-normalization-design.md | docs/superpowers/specs/2026-06-28-news-article-normalization-design.md | ["10","18","409","478","486","487","496","545","547","568","572","59"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md | docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md | ["229","263","265","266","270"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md | docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md | ["1","100","103","118","13","14","15","16","166","168","169","178","19","21","219","220","222","225","23","230","232","233","237","238","240","242","243","244","248","249","297","309","317","319","320","321","322","338","340","341","48","53","54","78","8","80","82"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md | docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md | ["495","516"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md | docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md | ["38"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md | docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md | ["221"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md | docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md | ["138","158","171","201","351","352","58"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md | docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md | ["6","991"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md | docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md | ["238","29","319","6"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md | docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md | ["15","211"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-17-news-content-availability-design.md | docs/superpowers/specs/2026-07-17-news-content-availability-design.md | ["221"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md | docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md | ["696"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md | docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md | ["809"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-25-i18n-6-release-design.md | docs/superpowers/specs/2026-07-25-i18n-6-release-design.md | ["17","19","483","659","801"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md | docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md | ["692","769","841","853","934"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md | docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md | ["144","167","172","228","267","291","30","31","381","396","402","406","488","512","519","522","53","543","721","740","85","879","895","945","960","961","97","973"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md | docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md | ["382","429","86"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md | docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md | ["624"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md | docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md | ["180"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md | docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md | ["101","109","255","261","285"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md | docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md | [] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md | docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md | ["211","442","631","649","651","89"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md | docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md | ["240","364"] | historical | retire_pg_only |
| documentation:docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md | docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md | ["239","240"] | historical | retire_pg_only |

## 9. Five-Way Disposition Algebra

| Disposition | Count | Surface IDs SHA-256 |
|---|---|---|
| defer_to_legacy_agent_cli_census | 2 | 1967f9a0a098b5192a908d1d7ef8b31f2e1d9b0068e750b33de734437fbd4a63 |
| retain_operator_remove_pg_branch | 24 | 90756c34a05428291989aff49c532a0e63954333a5a500c02eddecf6231bcfcf |
| retire_pg_only | 192 | 4009da3a7075eaa9fa674f2a260cff20fda4eb965284871e164127b26779950e |
| rewrite_current_authority | 242 | 19f71c076f0396646dfb60f83fca9e060a69404885570329bc4ecb894ed73a94 |
| rewrite_to_local_capability | 18 | 82bfab5653df1612d8937866c8e016d8b38ef8793613240816c8b66d216a8c2a |

All five sets are non-empty, pairwise disjoint, and their union is all 478 surfaces.

### `defer_to_legacy_agent_cli_census`

| Surface ID |
|---|
| cli:src/agents/cli.py:legacy-agent |
| cli:src/agents/openai_agent/agent.py:legacy-agent |

### `retain_operator_remove_pg_branch`

| Surface ID |
|---|
| cli:extensions/sa_alpha_picks/install.sh:extensions_sa_alpha_picks_install.sh |
| cli:extensions/sa_alpha_picks/install_firefox.sh:extensions_sa_alpha_picks_install_firefox.sh |
| cli:src/audit/sa_article_reconciliation.py:argparse.ArgumentParser |
| cli:src/audit/universe_retirement.py:argparse.ArgumentParser |
| cli:src/daily_update.py:argparse.ArgumentParser |
| cli:src/sa_native_host.py:main |
| cli:tests/live/smoke_fred.py:main |
| module_import:extensions/sa_alpha_picks/install.sh:psycopg |
| module_import:extensions/sa_alpha_picks/install.sh:psycopg2 |
| module_import:extensions/sa_alpha_picks/install_firefox.sh:psycopg |
| module_import:extensions/sa_alpha_picks/install_firefox.sh:psycopg2 |
| module_import:src/audit/sa_article_reconciliation.py:src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend |
| module_import:src/audit/universe_retirement.py:src.tools.data_access.DataAccessLayer |
| module_import:src/daily_update.py:src.tools.data_access.DataAccessLayer |
| module_import:src/sa_native_host.py:src.tools.data_access.DataAccessLayer |
| runtime_config:src/audit/sa_article_reconciliation.py:postgresql |
| runtime_config:src/audit/universe_retirement.py:db_dsn |
| runtime_config:src/daily_update.py:db_dsn |
| runtime_config:src/sa_native_host.py:db_dsn |
| store_or_backend:src/audit/sa_article_reconciliation.py:main |
| store_or_backend:src/audit/universe_retirement.py:load_production_overview_tickers |
| store_or_backend:src/daily_update.py:RunTelemetry.__init |
| store_or_backend:src/sa_native_host.py:handle_message |
| store_or_backend:tests/live/smoke_fred.py:main |

### `retire_pg_only`

| Surface ID |
|---|
| archive:docker/README.md |
| archive:docker/docker-compose.yml |
| archive:sql/001_init_schema.sql |
| archive:sql/003_add_reports.sql |
| archive:sql/004_add_memories.sql |
| archive:sql/005_add_financial_cache.sql |
| archive:sql/006_add_news_search.sql |
| archive:sql/007_add_sa_alpha_picks.sql |
| archive:sql/008_add_sa_articles.sql |
| archive:sql/009_add_sa_market_news.sql |
| archive:sql/010_add_sa_market_news_detail.sql |
| archive:sql/011_add_job_runs.sql |
| archive:sql/012_add_sa_comment_signals.sql |
| archive:sql/013_add_p1_2_macro_calendar.sql |
| archive:sql/014_sa_alpha_picks_closed_date_and_dual_membership.sql |
| archive:sql/015_sa_alpha_picks_closed_event_identity.sql |
| cli:src/smoke/pg_unreachable_e2e.py:argparse.ArgumentParser |
| documentation:docker/README.md |
| documentation:docs/PROJECT_HISTORY.md |
| documentation:docs/data/DATA_INVENTORY.md |
| documentation:docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md |
| documentation:docs/design/AGENT_EVOLUTION_TRACKER.md |
| documentation:docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md |
| documentation:docs/design/NEWS_DIRECT_LOCAL_PLAN.md |
| documentation:docs/design/P1_2_PROVIDER_DISCOVERY.md |
| documentation:docs/design/P1_2_SPEC.md |
| documentation:docs/design/P1_3_SPEC.md |
| documentation:docs/design/PG_EXIT_COMPLETION_PLAN.md |
| documentation:docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md |
| documentation:docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md |
| documentation:docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md |
| documentation:docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md |
| documentation:docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md |
| documentation:docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md |
| documentation:docs/design/PG_EXIT_REMAINDER_SCOPING.md |
| documentation:docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md |
| documentation:docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md |
| documentation:docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md |
| documentation:docs/design/REPO_HYGIENE_AUDIT_2026_07.md |
| documentation:docs/design/RL_COLLAPSE_FINDINGS.md |
| documentation:docs/design/SA_CUTOVER_3D_RUNBOOK.md |
| documentation:docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md |
| documentation:docs/design/archive/README.md |
| documentation:docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md |
| documentation:docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md |
| documentation:docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md |
| documentation:docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md |
| documentation:docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md |
| documentation:docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md |
| documentation:docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md |
| documentation:docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md |
| documentation:docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md |
| documentation:docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md |
| documentation:docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv |
| documentation:docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md |
| documentation:docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md |
| documentation:docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md |
| documentation:docs/superpowers/plans/2026-06-27-news-direct-cutover.md |
| documentation:docs/superpowers/plans/2026-06-27-news-identity-repair.md |
| documentation:docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md |
| documentation:docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md |
| documentation:docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md |
| documentation:docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md |
| documentation:docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md |
| documentation:docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md |
| documentation:docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md |
| documentation:docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md |
| documentation:docs/superpowers/plans/2026-07-05-macro-snapshot-display.md |
| documentation:docs/superpowers/plans/2026-07-05-news-burst-hardening.md |
| documentation:docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md |
| documentation:docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md |
| documentation:docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md |
| documentation:docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md |
| documentation:docs/superpowers/plans/2026-07-06-investor-profile-track-a.md |
| documentation:docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md |
| documentation:docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md |
| documentation:docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md |
| documentation:docs/superpowers/plans/2026-07-07-current-quote-tool.md |
| documentation:docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md |
| documentation:docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md |
| documentation:docs/superpowers/plans/2026-07-10-holdings-row-actions.md |
| documentation:docs/superpowers/plans/2026-07-10-model-capability-catalog.md |
| documentation:docs/superpowers/plans/2026-07-11-models-ux-implementation.md |
| documentation:docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md |
| documentation:docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md |
| documentation:docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md |
| documentation:docs/superpowers/plans/2026-07-12-subscription-card-routing.md |
| documentation:docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md |
| documentation:docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md |
| documentation:docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md |
| documentation:docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md |
| documentation:docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md |
| documentation:docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md |
| documentation:docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md |
| documentation:docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md |
| documentation:docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md |
| documentation:docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md |
| documentation:docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md |
| documentation:docs/superpowers/plans/2026-07-20-i18n-0-foundation.md |
| documentation:docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md |
| documentation:docs/superpowers/plans/2026-07-20-i18n-2-settings.md |
| documentation:docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md |
| documentation:docs/superpowers/plans/2026-07-23-i18n-3-explore.md |
| documentation:docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md |
| documentation:docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md |
| documentation:docs/superpowers/plans/2026-07-25-i18n-6-release.md |
| documentation:docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md |
| documentation:docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md |
| documentation:docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md |
| documentation:docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md |
| documentation:docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md |
| documentation:docs/superpowers/plans/2026-07-29-query-route-harness-termination.md |
| documentation:docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md |
| documentation:docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md |
| documentation:docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md |
| documentation:docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md |
| documentation:docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md |
| documentation:docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md |
| documentation:docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md |
| documentation:docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md |
| documentation:docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md |
| documentation:docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md |
| documentation:docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md |
| documentation:docs/superpowers/specs/2026-06-27-news-identity-repair-design.md |
| documentation:docs/superpowers/specs/2026-06-28-news-article-normalization-design.md |
| documentation:docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md |
| documentation:docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md |
| documentation:docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md |
| documentation:docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md |
| documentation:docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md |
| documentation:docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md |
| documentation:docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md |
| documentation:docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md |
| documentation:docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md |
| documentation:docs/superpowers/specs/2026-07-17-news-content-availability-design.md |
| documentation:docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md |
| documentation:docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md |
| documentation:docs/superpowers/specs/2026-07-25-i18n-6-release-design.md |
| documentation:docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md |
| documentation:docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md |
| documentation:docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md |
| documentation:docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md |
| documentation:docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md |
| documentation:docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md |
| documentation:docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md |
| documentation:docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md |
| documentation:docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md |
| documentation:docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md |
| environment-dependency:news-please |
| environment-dependency:psycopg2 |
| inheritance:tests/test_db_backend_retired_pg_sa.py:NoPGSA |
| inheritance:tests/test_db_backend_retired_prices.py:NoPgDatabaseBackend |
| inheritance:tests/test_pg_unreachable_e2e.py:FakePoison |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.PgAppRecordsSource |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.apply_migration |
| module_import:src/api/routes/app_records.py:src.app_records_migrate.preview_migration |
| module_import:src/app_records_migrate.py:psycopg |
| module_import:src/app_records_migrate.py:psycopg2 |
| module_import:src/app_records_migrate.py:psycopg2.extras.RealDictCursor |
| module_import:src/macro_calendar/store.py:psycopg |
| module_import:src/macro_calendar/store.py:psycopg2 |
| module_import:src/macro_calendar/store.py:psycopg2.extras |
| module_import:src/smoke/pg_unreachable_e2e.py:psycopg |
| module_import:src/smoke/pg_unreachable_e2e.py:psycopg2 |
| module_import:src/tools/backends/db_backend.py:psycopg |
| module_import:src/tools/backends/db_backend.py:psycopg2 |
| module_import:src/tools/backends/db_backend.py:psycopg2.extras |
| route:src/api/routes/app_records.py:migration_apply |
| route:src/api/routes/app_records.py:migration_preview |
| runtime_config:src/api/routes/app_records.py:use_local_records |
| runtime_config:src/smoke/pg_unreachable_e2e.py:db_dsn |
| runtime_config:src/smoke/pg_unreachable_e2e.py:postgresql |
| runtime_config:src/tools/backends/db_backend.py:postgresql |
| runtime_config:src/tools/backends/db_backend.py:sslmode |
| runtime_config:src/tools/db_config.py:database_url |
| runtime_config:src/tools/db_config.py:sslmode |
| store_or_backend:src/api/routes/app_records.py:source |
| store_or_backend:src/app_records_migrate.py:PgAppRecordsSource._rows |
| store_or_backend:src/macro_calendar/store.py:module |
| store_or_backend:src/smoke/pg_unreachable_e2e.py:module |
| store_or_backend:src/tools/backends/db_backend.py:DatabaseBackend.__init |
| store_or_backend:src/tools/db_config.py:postgres |
| test-contract:tests/test_app_records_migrate.py |
| test-contract:tests/test_db_backend.py |
| test-contract:tests/test_db_backend_retired_pg_sa.py |
| test-contract:tests/test_db_backend_retired_prices.py |
| test-contract:tests/test_macro_calendar_store.py |
| test-contract:tests/test_pg_unreachable_e2e.py |
| type_gate:tests/test_db_backend.py:isinstance |

### `rewrite_current_authority`

| Surface ID |
|---|
| dependency:requirements.txt:postgres-drivers |
| documentation:README.md |
| documentation:data_sources/DATA_SOURCE_QUIRKS.md |
| documentation:docs/PUBLICATION_REVIEW.md |
| documentation:docs/data/OPTIONS_PRICING_THEORY.md |
| documentation:docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md |
| documentation:docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md |
| documentation:docs/design/CONFIG_AUTHORITY_PLAN.md |
| documentation:docs/design/CREDENTIAL_MANAGEMENT_PLAN.md |
| documentation:docs/design/CURRENT_PROJECT_CONTEXT.md |
| documentation:docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md |
| documentation:docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md |
| documentation:docs/design/DESKTOP_APP_VISION_DRAFT.md |
| documentation:docs/design/ENGINEERING_ISSUE_REGISTER.md |
| documentation:docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md |
| documentation:docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md |
| documentation:docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md |
| documentation:docs/design/LOCAL_STORAGE_TOPOLOGY.md |
| documentation:docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md |
| documentation:docs/design/P1_5_S3_OSS_SPIKE_DECISION.md |
| documentation:docs/design/README.md |
| documentation:docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md |
| documentation:docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md |
| documentation:docs/design/SA_EVIDENCE_FEED_C1_SPEC.md |
| documentation:docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md |
| documentation:docs/design/SCHEDULER_HARDENING_PLAN.md |
| inheritance:tests/test_sa_reconciliation_native_host.py:Backend |
| inheritance:tests/test_sa_reconciliation_native_host.py:MetaBackend |
| inheritance:tests/test_sa_reconciliation_native_host.py:NoPG |
| module_import:data_sources/financial_datasets_client.py:psycopg |
| module_import:data_sources/financial_datasets_client.py:psycopg2 |
| module_import:data_sources/financial_datasets_client.py:psycopg2.extras |
| module_import:src/agents/anthropic_agent/agent.py:src.tools.backends.db_backend.DatabaseBackend |
| module_import:src/agents/anthropic_agent/agent.py:src.tools.data_access.DataAccessLayer |
| module_import:src/agents/cli.py:src.tools.backends.db_backend.DatabaseBackend |
| module_import:src/agents/cli.py:src.tools.data_access.DataAccessLayer |
| module_import:src/agents/openai_agent/agent.py:src.tools.backends.db_backend.DatabaseBackend |
| module_import:src/agents/openai_agent/agent.py:src.tools.data_access.DataAccessLayer |
| module_import:src/api/dependencies.py:src.tools.data_access.DataAccessLayer |
| module_import:src/api/routes/fundamentals.py:src.tools.data_access.DataAccessLayer |
| module_import:src/api/routes/news.py:src.tools.data_access.DataAccessLayer |
| module_import:src/api/routes/profile.py:src.tools.data_access.DataAccessLayer |
| module_import:src/app_records_store.py:psycopg |
| module_import:src/app_records_store.py:psycopg2 |
| module_import:src/monitor/scheduler.py:psycopg |
| module_import:src/monitor/scheduler.py:psycopg2 |
| module_import:src/sa/comment_signal_backfill.py:psycopg |
| module_import:src/sa/comment_signal_backfill.py:psycopg2 |
| module_import:src/sa/comment_signal_backfill.py:psycopg2.extras |
| module_import:src/sa_capture_store.py:psycopg |
| module_import:src/sa_capture_store.py:psycopg2 |
| module_import:src/service/data_scheduler.py:psycopg |
| module_import:src/service/data_scheduler.py:psycopg2 |
| module_import:src/service/data_scheduler.py:psycopg2.extensions.parse_dsn |
| module_import:src/service/job_runs_store.py:psycopg |
| module_import:src/service/job_runs_store.py:psycopg2 |
| module_import:src/service/job_runs_store.py:psycopg2.extras |
| module_import:src/service/macro_calendar_health.py:psycopg |
| module_import:src/service/macro_calendar_health.py:psycopg2 |
| module_import:src/service/macro_calendar_health.py:psycopg2.extras |
| module_import:src/service/provider_health.py:psycopg |
| module_import:src/service/provider_health.py:psycopg2 |
| module_import:src/service/sa_market_news_health.py:psycopg |
| module_import:src/service/sa_market_news_health.py:psycopg2 |
| module_import:src/tools/analysis_tools.py:data_access.DataAccessLayer |
| module_import:src/tools/analysis_tools.py:data_sources.financial_datasets_client.FinancialDatasetsClient |
| module_import:src/tools/backends/local_market_backend.py:db_backend.DatabaseBackend |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend.DatabaseBackend |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend._plan_comment_duplicate_cleanup |
| module_import:src/tools/backends/sa_capture_backend.py:db_backend._prepare_comments_for_upsert |
| module_import:src/tools/backends/sa_capture_backend.py:local_market_backend.LocalMarketDatabaseBackend |
| module_import:src/tools/backends/sa_capture_backend.py:psycopg |
| module_import:src/tools/backends/sa_capture_backend.py:psycopg2 |
| module_import:src/tools/data_access.py:backends.db_backend.DatabaseBackend |
| module_import:src/tools/data_access.py:src.tools.backends.local_market_backend.LocalMarketDatabaseBackend |
| module_import:src/tools/data_access.py:src.tools.backends.sa_capture_backend.SACaptureDatabaseBackend |
| module_import:src/tools/freshness.py:psycopg |
| module_import:src/tools/freshness.py:psycopg2 |
| module_import:src/tools/freshness.py:src.tools.backends.db_backend.DatabaseBackend |
| module_import:src/tools/memory_tools.py:data_access.DataAccessLayer |
| module_import:src/tools/news_tools.py:data_access.DataAccessLayer |
| module_import:src/tools/price_tools.py:data_access.DataAccessLayer |
| module_import:src/tools/report_tools.py:data_access.DataAccessLayer |
| module_import:src/tools/sa_digest_tools.py:psycopg |
| module_import:src/tools/sa_digest_tools.py:psycopg2 |
| module_import:src/tools/sa_digest_tools.py:psycopg2.extras |
| module_import:src/tools/sa_tools.py:psycopg |
| module_import:src/tools/sa_tools.py:psycopg2 |
| module_import:src/tools/sa_tools.py:psycopg2.extras |
| runtime_config:config/.env.template:database_url |
| runtime_config:config/.env.template:sslmode |
| runtime_config:data_sources/financial_datasets_client.py:database_url |
| runtime_config:src/agents/anthropic_agent/agent.py:db_dsn |
| runtime_config:src/agents/cli.py:db_dsn |
| runtime_config:src/agents/openai_agent/agent.py:db_dsn |
| runtime_config:src/api/dependencies.py:db_dsn |
| runtime_config:src/app_records_store.py:use_local_records |
| runtime_config:src/service/data_scheduler.py:database_url |
| runtime_config:src/tools/backends/local_market_backend.py:sslmode |
| runtime_config:src/tools/backends/sa_capture_backend.py:sslmode |
| runtime_config:src/tools/data_access.py:database_url |
| runtime_config:src/tools/data_access.py:db_dsn |
| runtime_config:src/tools/data_access.py:postgresql |
| runtime_config:src/tools/data_access.py:sslmode |
| runtime_config:src/tools/data_access.py:use_local_records |
| startup_hook:src/api/app.py:app_records_router |
| store_or_backend:apps/arkscope-web/src/TickerDetail.tsx:pg |
| store_or_backend:apps/arkscope-web/src/api.ts:pg |
| store_or_backend:apps/arkscope-web/src/i18n/resources/en/explore.ts:pg |
| store_or_backend:apps/arkscope-web/src/i18n/resources/en/settings.ts:pg |
| store_or_backend:apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts:pg |
| store_or_backend:apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts:pg |
| store_or_backend:apps/arkscope-web/src/marketDataDisplay.ts:pg |
| store_or_backend:config/.env.template:postgres |
| store_or_backend:data_sources/sec_edgar_source.py:pg |
| store_or_backend:src/analyst_consensus.py:pg |
| store_or_backend:src/api/app.py:pg |
| store_or_backend:src/api/dependencies.py:get_dal |
| store_or_backend:src/api/routes/fundamentals.py:fundamentals |
| store_or_backend:src/api/routes/macro_calendar.py:pg |
| store_or_backend:src/api/routes/market_data.py:pg |
| store_or_backend:src/api/routes/news.py:news_feed |
| store_or_backend:src/api/routes/profile.py:ticker_state_payload |
| store_or_backend:src/app_records_store.py:pg |
| store_or_backend:src/card_runs.py:pg |
| store_or_backend:src/fundamentals/cache.py:db_backend |
| store_or_backend:src/ibkr_gateway_lock.py:pg |
| store_or_backend:src/macro_calendar/__init__.py:pg |
| store_or_backend:src/macro_calendar/local_store.py:pg |
| store_or_backend:src/market_data_admin.py:pg |
| store_or_backend:src/market_data_direct.py:pg |
| store_or_backend:src/news_direct.py:pg |
| store_or_backend:src/news_normalized/routing.py:NEWS_PG_EXIT_COMPLETED_KEY |
| store_or_backend:src/news_normalized/schema.py:pg |
| store_or_backend:src/news_providers.py:pg |
| store_or_backend:src/news_sync_status.py:pg |
| store_or_backend:src/portfolio_state.py:pg |
| store_or_backend:src/profile_state.py:postgres |
| store_or_backend:src/research_threads.py:pg |
| store_or_backend:src/sa/comment_signal_backfill.py:run_backfill_sqlite |
| store_or_backend:src/sa_capture_store.py:pg |
| store_or_backend:src/scheduler_state.py:pg |
| store_or_backend:src/service/data_scheduler.py:module |
| store_or_backend:src/service/macro_calendar_health.py:evaluate_job |
| store_or_backend:src/service/sa_market_news_health.py:evaluate_health |
| store_or_backend:src/tools/analysis_tools.py:get_fd_cache_days |
| store_or_backend:src/tools/backends/__init__.py:databasebackend |
| store_or_backend:src/tools/backends/provenance.py:pg |
| store_or_backend:src/tools/backends/sqlite_backend.py:pg |
| store_or_backend:src/tools/data_access.py:DataAccessLayer._compute_unresolved_symbols_raw_PG_connection |
| store_or_backend:src/tools/data_coverage_tools.py:postgres |
| store_or_backend:src/tools/macro_calendar_tools.py:pg |
| store_or_backend:src/tools/memory_tools.py:pg |
| store_or_backend:src/tools/news_tools.py:get_news_brief |
| store_or_backend:src/tools/price_tools.py:get_price_change |
| store_or_backend:src/tools/report_tools.py:pg |
| store_or_backend:src/tools/sa_digest_tools.py:fetch_dicts |
| store_or_backend:src/tools/sa_tools.py:focus_local |
| store_or_backend:tests/conftest.py:pg |
| test-contract:apps/arkscope-web/src/AICard.test.tsx |
| test-contract:apps/arkscope-web/src/Home.test.tsx |
| test-contract:apps/arkscope-web/src/News.test.tsx |
| test-contract:apps/arkscope-web/src/SettingsNewsStorage.test.ts |
| test-contract:apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts |
| test-contract:apps/arkscope-web/src/SettingsProviderConfig.test.ts |
| test-contract:apps/arkscope-web/src/SettingsStabilizationCss.test.ts |
| test-contract:apps/arkscope-web/src/TickerDetail.test.tsx |
| test-contract:apps/arkscope-web/src/Universe.test.tsx |
| test-contract:apps/arkscope-web/src/Watchlist.test.tsx |
| test-contract:apps/arkscope-web/src/marketDataDisplay.test.ts |
| test-contract:tests/test_agents.py |
| test-contract:tests/test_analyst_tools.py |
| test-contract:tests/test_api.py |
| test-contract:tests/test_app_records_store.py |
| test-contract:tests/test_chatgpt_oauth_driver.py |
| test-contract:tests/test_claude_code_sdk_driver.py |
| test-contract:tests/test_compressor_layer5.py |
| test-contract:tests/test_credential_env_routes.py |
| test-contract:tests/test_data_access.py |
| test-contract:tests/test_data_scheduler.py |
| test-contract:tests/test_detailed_financials.py |
| test-contract:tests/test_eir006_retired_data_boundaries.py |
| test-contract:tests/test_financial_datasets.py |
| test-contract:tests/test_finnhub_ingestion.py |
| test-contract:tests/test_fred_ingestion.py |
| test-contract:tests/test_freshness.py |
| test-contract:tests/test_fundamentals_cache.py |
| test-contract:tests/test_fundamentals_sec_cache.py |
| test-contract:tests/test_ibkr_gateway_lock.py |
| test-contract:tests/test_job_runs.py |
| test-contract:tests/test_legacy_iv_retirement_boundaries.py |
| test-contract:tests/test_legacy_score_retirement.py |
| test-contract:tests/test_macro_calendar_health.py |
| test-contract:tests/test_macro_calendar_local_store.py |
| test-contract:tests/test_macro_calendar_local_wiring.py |
| test-contract:tests/test_macro_calendar_read.py |
| test-contract:tests/test_macro_calendar_settings_route.py |
| test-contract:tests/test_macro_scheduler_integration.py |
| test-contract:tests/test_market_coverage_boundaries.py |
| test-contract:tests/test_market_data_admin.py |
| test-contract:tests/test_market_data_direct.py |
| test-contract:tests/test_memory_tools.py |
| test-contract:tests/test_news_direct.py |
| test-contract:tests/test_news_feed_content_route.py |
| test-contract:tests/test_news_normalized_routing.py |
| test-contract:tests/test_news_pg_unreachable.py |
| test-contract:tests/test_news_providers.py |
| test-contract:tests/test_news_settings_route.py |
| test-contract:tests/test_peer_comparison.py |
| test-contract:tests/test_profile_state.py |
| test-contract:tests/test_provider_health.py |
| test-contract:tests/test_research_routes.py |
| test-contract:tests/test_research_threads.py |
| test-contract:tests/test_sa_article_reconciliation_backend.py |
| test-contract:tests/test_sa_capture_backend.py |
| test-contract:tests/test_sa_capture_store.py |
| test-contract:tests/test_sa_comment_focus.py |
| test-contract:tests/test_sa_comment_signal_port.py |
| test-contract:tests/test_sa_comment_signals.py |
| test-contract:tests/test_sa_digest.py |
| test-contract:tests/test_sa_extension_diagnostics.py |
| test-contract:tests/test_sa_feed.py |
| test-contract:tests/test_sa_local_readers.py |
| test-contract:tests/test_sa_market_news_health.py |
| test-contract:tests/test_sa_market_news_recovery.py |
| test-contract:tests/test_sa_reconciliation_native_host.py |
| test-contract:tests/test_sa_routing.py |
| test-contract:tests/test_sa_tools.py |
| test-contract:tests/test_scheduler_state.py |
| test-contract:tests/test_sec_tools.py |
| test-contract:tests/test_sqlite_backend.py |
| test-contract:tests/test_stored_sec_projection.py |
| test-contract:tests/test_tools.py |
| test-contract:tests/test_trading_day_coverage.py |
| test-contract:tests/test_universe_summaries_local.py |
| test-contract:tests/test_web_tools.py |
| type_gate:tests/test_freshness.py:isinstance |
| type_gate:tests/test_job_runs.py:isinstance |
| type_gate:tests/test_market_data_admin.py:isinstance |
| type_gate:tests/test_news_pg_unreachable.py:isinstance |
| type_gate:tests/test_sa_capture_backend.py:isinstance |
| type_gate:tests/test_sqlite_backend.py:isinstance |

### `rewrite_to_local_capability`

| Surface ID |
|---|
| inheritance:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend |
| inheritance:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend |
| local-capability:src/tools/data_access.py:backend-contract |
| store_or_backend:data_sources/financial_datasets_client.py:FinancialDatasetsClient._db_get |
| store_or_backend:src/agents/anthropic_agent/agent.py:get_freshness_summary |
| store_or_backend:src/agents/cli.py:handle_save_command |
| store_or_backend:src/agents/openai_agent/agent.py:get_freshness_prompt |
| store_or_backend:src/macro_calendar/fred_ingestion.py:ingest_full_vintages |
| store_or_backend:src/service/job_runs_store.py:module |
| store_or_backend:src/service/provider_health.py:databasebackend |
| store_or_backend:src/tools/backends/local_market_backend.py:LocalMarketDatabaseBackend |
| store_or_backend:src/tools/backends/sa_capture_backend.py:SACaptureDatabaseBackend |
| store_or_backend:src/tools/freshness.py:module |
| type_gate:src/agents/anthropic_agent/agent.py:isinstance |
| type_gate:src/agents/cli.py:isinstance |
| type_gate:src/agents/openai_agent/agent.py:isinstance |
| type_gate:src/tools/data_access.py:isinstance |
| type_gate:src/tools/freshness.py:isinstance |

## 10. Predicted No-Tail Path Sets

| Set | Count | SHA-256 |
|---|---|---|
| Delete | 161 | 8f343f354e61d34f4b0fd27b04ff0ff2a849c7fc05de422035d3b2feaf067916 |
| Modify | 174 | cf53aee5a8e93617b8253cfe8b9b8685e61fbc8eaeb2cb607cc8e51954f7317e |
| Add | 1 | 7a7752d11fc47ec553e85e85099e24582e0ccbc610758b2381b4ca3a3b0b1e48 |
| Protected | 22 | debc51e928c3606b49e7306eac1dd5ecb8ec668039bcc2ab0a7c61f81da35d5e |

Delete/modify/protected partition all `357` tracked surface and no-PG CLI paths; add is disjoint and absent. Frontend PG DTO/name/copy consumers are non-zero, so the bounded frontend modify set is exactly `18` paths rather than a whole-frontend protection claim.

### Delete

| Path |
|---|
| docker/README.md |
| docker/docker-compose.yml |
| docs/PROJECT_HISTORY.md |
| docs/data/DATA_INVENTORY.md |
| docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md |
| docs/design/AGENT_EVOLUTION_TRACKER.md |
| docs/design/DOCS_SWEEP_DISPOSITION_2026_07.md |
| docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md |
| docs/design/NEWS_DIRECT_LOCAL_PLAN.md |
| docs/design/P1_2_PROVIDER_DISCOVERY.md |
| docs/design/P1_2_SPEC.md |
| docs/design/P1_3_SPEC.md |
| docs/design/PG_EXIT_COMPLETION_PLAN.md |
| docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md |
| docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md |
| docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md |
| docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md |
| docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md |
| docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md |
| docs/design/PG_EXIT_REMAINDER_SCOPING.md |
| docs/design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md |
| docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md |
| docs/design/PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md |
| docs/design/REPO_HYGIENE_AUDIT_2026_07.md |
| docs/design/RL_COLLAPSE_FINDINGS.md |
| docs/design/SA_CUTOVER_3D_RUNBOOK.md |
| docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md |
| docs/design/archive/README.md |
| docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md |
| docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md |
| docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md |
| docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md |
| docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md |
| docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md |
| docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md |
| docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md |
| docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md |
| docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv |
| docs/superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md |
| docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md |
| docs/superpowers/evidence/2026-08-13-macro-refresh-scheduler.md |
| docs/superpowers/plans/2026-06-27-news-direct-cutover.md |
| docs/superpowers/plans/2026-06-27-news-identity-repair.md |
| docs/superpowers/plans/2026-06-28-news-normalization-offline-foundation.md |
| docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md |
| docs/superpowers/plans/2026-06-30-news-n8a-pg-exit.md |
| docs/superpowers/plans/2026-07-01-s-a1-ibkr-worker-module.md |
| docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md |
| docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md |
| docs/superpowers/plans/2026-07-03-s-g-scorer-cutover.md |
| docs/superpowers/plans/2026-07-04-data-sources-post-pg-exit-ui-cleanup.md |
| docs/superpowers/plans/2026-07-05-macro-snapshot-display.md |
| docs/superpowers/plans/2026-07-05-news-burst-hardening.md |
| docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md |
| docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md |
| docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md |
| docs/superpowers/plans/2026-07-06-ibkr-news-long-catchup-audit.md |
| docs/superpowers/plans/2026-07-06-investor-profile-track-a.md |
| docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md |
| docs/superpowers/plans/2026-07-06-sa-extension-telemetry-health.md |
| docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md |
| docs/superpowers/plans/2026-07-07-current-quote-tool.md |
| docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md |
| docs/superpowers/plans/2026-07-08-investor-profile-calibration-chat.md |
| docs/superpowers/plans/2026-07-10-holdings-row-actions.md |
| docs/superpowers/plans/2026-07-10-model-capability-catalog.md |
| docs/superpowers/plans/2026-07-11-models-ux-implementation.md |
| docs/superpowers/plans/2026-07-11-s3-credential-lifecycle-hotfix.md |
| docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md |
| docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md |
| docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md |
| docs/superpowers/plans/2026-07-12-subscription-card-routing.md |
| docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md |
| docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md |
| docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md |
| docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md |
| docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md |
| docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md |
| docs/superpowers/plans/2026-07-17-news-content-availability-implementation.md |
| docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md |
| docs/superpowers/plans/2026-07-18-p2-8-slice-3-research-workspace.md |
| docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md |
| docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md |
| docs/superpowers/plans/2026-07-19-p2-8-slice-4-settings-workspace.md |
| docs/superpowers/plans/2026-07-20-i18n-0-foundation.md |
| docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md |
| docs/superpowers/plans/2026-07-20-i18n-2-settings.md |
| docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md |
| docs/superpowers/plans/2026-07-23-i18n-3-explore.md |
| docs/superpowers/plans/2026-07-24-i18n-4-5-remaining-surfaces.md |
| docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md |
| docs/superpowers/plans/2026-07-25-i18n-6-release.md |
| docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md |
| docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md |
| docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md |
| docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md |
| docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md |
| docs/superpowers/plans/2026-07-29-query-route-harness-termination.md |
| docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md |
| docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md |
| docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md |
| docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md |
| docs/superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md |
| docs/superpowers/plans/2026-08-09-provider-smoke-candidate-truth.md |
| docs/superpowers/plans/2026-08-09-settings-navigation-warm-cache.md |
| docs/superpowers/plans/2026-08-13-macro-refresh-scheduler.md |
| docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md |
| docs/superpowers/plans/2026-08-14-settings-schedule-surface-ownership.md |
| docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md |
| docs/superpowers/specs/2026-06-27-news-identity-repair-design.md |
| docs/superpowers/specs/2026-06-28-news-article-normalization-design.md |
| docs/superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md |
| docs/superpowers/specs/2026-06-30-news-n8-pg-exit-design.md |
| docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md |
| docs/superpowers/specs/2026-07-12-ai-execution-usage-observability-design.md |
| docs/superpowers/specs/2026-07-12-fixed-ai-task-runtime-limits-design.md |
| docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md |
| docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md |
| docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md |
| docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md |
| docs/superpowers/specs/2026-07-17-news-content-availability-design.md |
| docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md |
| docs/superpowers/specs/2026-07-23-i18n-3-explore-design.md |
| docs/superpowers/specs/2026-07-25-i18n-6-release-design.md |
| docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md |
| docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md |
| docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md |
| docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md |
| docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md |
| docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md |
| docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md |
| docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md |
| docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md |
| docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md |
| sql/001_init_schema.sql |
| sql/003_add_reports.sql |
| sql/004_add_memories.sql |
| sql/005_add_financial_cache.sql |
| sql/006_add_news_search.sql |
| sql/007_add_sa_alpha_picks.sql |
| sql/008_add_sa_articles.sql |
| sql/009_add_sa_market_news.sql |
| sql/010_add_sa_market_news_detail.sql |
| sql/011_add_job_runs.sql |
| sql/012_add_sa_comment_signals.sql |
| sql/013_add_p1_2_macro_calendar.sql |
| sql/014_sa_alpha_picks_closed_date_and_dual_membership.sql |
| sql/015_sa_alpha_picks_closed_event_identity.sql |
| src/api/routes/app_records.py |
| src/app_records_migrate.py |
| src/macro_calendar/store.py |
| src/smoke/pg_unreachable_e2e.py |
| src/tools/backends/db_backend.py |
| src/tools/db_config.py |
| tests/test_app_records_migrate.py |
| tests/test_db_backend.py |
| tests/test_db_backend_retired_pg_sa.py |
| tests/test_db_backend_retired_prices.py |
| tests/test_macro_calendar_store.py |
| tests/test_pg_unreachable_e2e.py |

### Modify

| Path |
|---|
| README.md |
| apps/arkscope-web/src/AICard.test.tsx |
| apps/arkscope-web/src/Home.test.tsx |
| apps/arkscope-web/src/News.test.tsx |
| apps/arkscope-web/src/SettingsNewsStorage.test.ts |
| apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts |
| apps/arkscope-web/src/SettingsProviderConfig.test.ts |
| apps/arkscope-web/src/SettingsStabilizationCss.test.ts |
| apps/arkscope-web/src/TickerDetail.test.tsx |
| apps/arkscope-web/src/TickerDetail.tsx |
| apps/arkscope-web/src/Universe.test.tsx |
| apps/arkscope-web/src/Watchlist.test.tsx |
| apps/arkscope-web/src/api.ts |
| apps/arkscope-web/src/i18n/resources/en/explore.ts |
| apps/arkscope-web/src/i18n/resources/en/settings.ts |
| apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts |
| apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts |
| apps/arkscope-web/src/marketDataDisplay.test.ts |
| apps/arkscope-web/src/marketDataDisplay.ts |
| config/.env.template |
| data_sources/DATA_SOURCE_QUIRKS.md |
| data_sources/financial_datasets_client.py |
| data_sources/sec_edgar_source.py |
| docs/PUBLICATION_REVIEW.md |
| docs/data/OPTIONS_PRICING_THEORY.md |
| docs/design/AI_RESEARCH_RUN_LIFECYCLE_PLAN.md |
| docs/design/AI_RESEARCH_SURFACE_C2_SPEC.md |
| docs/design/CONFIG_AUTHORITY_PLAN.md |
| docs/design/CREDENTIAL_MANAGEMENT_PLAN.md |
| docs/design/CURRENT_PROJECT_CONTEXT.md |
| docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md |
| docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md |
| docs/design/DESKTOP_APP_VISION_DRAFT.md |
| docs/design/ENGINEERING_ISSUE_REGISTER.md |
| docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md |
| docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md |
| docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md |
| docs/design/LOCAL_STORAGE_TOPOLOGY.md |
| docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md |
| docs/design/P1_5_S3_OSS_SPIKE_DECISION.md |
| docs/design/README.md |
| docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md |
| docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md |
| docs/design/SA_EVIDENCE_FEED_C1_SPEC.md |
| docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md |
| docs/design/SCHEDULER_HARDENING_PLAN.md |
| extensions/sa_alpha_picks/install.sh |
| extensions/sa_alpha_picks/install_firefox.sh |
| requirements.txt |
| src/agents/anthropic_agent/agent.py |
| src/agents/cli.py |
| src/agents/openai_agent/agent.py |
| src/analyst_consensus.py |
| src/api/app.py |
| src/api/dependencies.py |
| src/api/routes/fundamentals.py |
| src/api/routes/macro_calendar.py |
| src/api/routes/market_data.py |
| src/api/routes/news.py |
| src/api/routes/profile.py |
| src/app_records_store.py |
| src/audit/sa_article_reconciliation.py |
| src/audit/universe_retirement.py |
| src/card_runs.py |
| src/daily_update.py |
| src/fundamentals/cache.py |
| src/ibkr_gateway_lock.py |
| src/macro_calendar/__init__.py |
| src/macro_calendar/fred_ingestion.py |
| src/macro_calendar/local_store.py |
| src/market_data_admin.py |
| src/market_data_direct.py |
| src/monitor/scheduler.py |
| src/news_direct.py |
| src/news_normalized/routing.py |
| src/news_normalized/schema.py |
| src/news_providers.py |
| src/news_sync_status.py |
| src/portfolio_state.py |
| src/profile_state.py |
| src/research_threads.py |
| src/sa/comment_signal_backfill.py |
| src/sa_capture_store.py |
| src/sa_native_host.py |
| src/scheduler_state.py |
| src/service/data_scheduler.py |
| src/service/job_runs_store.py |
| src/service/macro_calendar_health.py |
| src/service/provider_health.py |
| src/service/sa_market_news_health.py |
| src/tools/analysis_tools.py |
| src/tools/backends/__init__.py |
| src/tools/backends/local_market_backend.py |
| src/tools/backends/provenance.py |
| src/tools/backends/sa_capture_backend.py |
| src/tools/backends/sqlite_backend.py |
| src/tools/data_access.py |
| src/tools/data_coverage_tools.py |
| src/tools/freshness.py |
| src/tools/macro_calendar_tools.py |
| src/tools/memory_tools.py |
| src/tools/news_tools.py |
| src/tools/price_tools.py |
| src/tools/report_tools.py |
| src/tools/sa_digest_tools.py |
| src/tools/sa_tools.py |
| tests/conftest.py |
| tests/live/smoke_fred.py |
| tests/test_agents.py |
| tests/test_analyst_tools.py |
| tests/test_api.py |
| tests/test_app_records_store.py |
| tests/test_chatgpt_oauth_driver.py |
| tests/test_claude_code_sdk_driver.py |
| tests/test_compressor_layer5.py |
| tests/test_credential_env_routes.py |
| tests/test_data_access.py |
| tests/test_data_scheduler.py |
| tests/test_detailed_financials.py |
| tests/test_eir006_retired_data_boundaries.py |
| tests/test_financial_datasets.py |
| tests/test_finnhub_ingestion.py |
| tests/test_fred_ingestion.py |
| tests/test_freshness.py |
| tests/test_fundamentals_cache.py |
| tests/test_fundamentals_sec_cache.py |
| tests/test_ibkr_gateway_lock.py |
| tests/test_job_runs.py |
| tests/test_legacy_iv_retirement_boundaries.py |
| tests/test_legacy_score_retirement.py |
| tests/test_macro_calendar_health.py |
| tests/test_macro_calendar_local_store.py |
| tests/test_macro_calendar_local_wiring.py |
| tests/test_macro_calendar_read.py |
| tests/test_macro_calendar_settings_route.py |
| tests/test_macro_scheduler_integration.py |
| tests/test_market_coverage_boundaries.py |
| tests/test_market_data_admin.py |
| tests/test_market_data_direct.py |
| tests/test_memory_tools.py |
| tests/test_news_direct.py |
| tests/test_news_feed_content_route.py |
| tests/test_news_normalized_routing.py |
| tests/test_news_pg_unreachable.py |
| tests/test_news_providers.py |
| tests/test_news_settings_route.py |
| tests/test_peer_comparison.py |
| tests/test_profile_state.py |
| tests/test_provider_health.py |
| tests/test_research_routes.py |
| tests/test_research_threads.py |
| tests/test_sa_article_reconciliation_backend.py |
| tests/test_sa_capture_backend.py |
| tests/test_sa_capture_store.py |
| tests/test_sa_comment_focus.py |
| tests/test_sa_comment_signal_port.py |
| tests/test_sa_comment_signals.py |
| tests/test_sa_digest.py |
| tests/test_sa_extension_diagnostics.py |
| tests/test_sa_feed.py |
| tests/test_sa_local_readers.py |
| tests/test_sa_market_news_health.py |
| tests/test_sa_market_news_recovery.py |
| tests/test_sa_reconciliation_native_host.py |
| tests/test_sa_routing.py |
| tests/test_sa_tools.py |
| tests/test_scheduler_state.py |
| tests/test_sec_tools.py |
| tests/test_sqlite_backend.py |
| tests/test_stored_sec_projection.py |
| tests/test_tools.py |
| tests/test_trading_day_coverage.py |
| tests/test_universe_summaries_local.py |
| tests/test_web_tools.py |

### Add

| Path |
|---|
| src/tools/backends/local_capabilities.py |

### Protected

| Path |
|---|
| apps/arkscope-web/package.json |
| data_sources/financial_metrics_calculator.py |
| data_sources/sec_earnings_releases.py |
| data_sources/sec_insider_trades.py |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_consumer_census.py |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py |
| docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py |
| extensions/sa_alpha_picks/build_firefox.py |
| package.json |
| src/api/__main__.py |
| src/audit/ibkr_news_catchup_audit.py |
| src/collectors/finnhub_news.py |
| src/collectors/polygon_news.py |
| src/news_normalized/ibkr_cli.py |
| src/options_math/option_pricing.py |
| src/prices_runtime.py |
| tests/live/sdk_driver_smoke.py |
| tests/live/sdk_route_smoke.py |
| tests/test_ibkr_scanner.py |
| tests/test_option_pricing.py |

## 11. Grounding Identities

| Stream | Rows | SHA-256 |
|---|---|---|
| Backend base | 4394 | b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb |
| Frontend base | 1177 | 90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b |
| PG focused base | 1897 | 57c1b5145529ae0b36f4068406c67d40a7610f5cd0b3472ec0bd9e88dfeefbf9 |
| Dynamic routes | 175 | 488231c63e8c9bb0a28a6baf5e972c959c7eeddf9cc5fa10cdffc3330bc95aea |

Recipes are fixed in the reviewed implementation plan: globally UTF-8 byte-sorted exact
rows with one trailing newline. Backend/frontend/routes are independent grounding streams;
the focused stream is the exact union of canonical test objects joined to those bases.

## 12. Admission Stops and Unresolved Facts

Unresolved inventory facts: **none**.

Any uncensused consumer, missing candidate adjudication, unmeasured method, overlapping
disposition/path partition, unowned CLI/test/documentation surface, or archive preservation
claim is a stop-and-amend event. The active design, plan, evidence, generated inventory
authority, and PostgreSQL priority-map entries are temporary instructions outside the frozen
candidate surface universe; the no-tail plan must add their then-current exact paths to its
closeout ledger before product execution.

## 13. Inventory-Stage Exclusions

This inventory did not read or mutate secret values, remote tables, private untracked dumps,
product databases, tracked archive assets, product code, tests, dependencies, or runtime
configuration. These are execution boundaries, not preservation decisions. Remote table
deletion and private-file handling remain separately authorized work.
