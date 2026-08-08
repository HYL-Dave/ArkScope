# Scripts Tranche B Legacy Score Retirement Implementation Plan

> **Status:** DRAFT FOR INDEPENDENT PLAN REVIEW; IMPLEMENTATION NOT AUTHORIZED
> **Date:** 2026-08-08
> **Branch base:** `04dd9a67d75042aa078bedde1e6dbc2a68e7736a`
> **Reviewed inventory:** `098dff564faea1fc2617e198414ccde6067f23f8`
> **Product authority:**
> `docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md`
> at reviewed commit `04dd9a67`, plus the post-approval no-tail ruling recorded
> in this plan-gate amendment
> **User ruling:** PD 1 through PD 8 approved as the section 8 bundle on
> 2026-08-08. Physical score-row deletion and `config/scoring_keys.txt`
> disposition remain separately blocked.

## 0. Execution contract

### 0.1 Purpose

This plan removes the frozen ArkScope-generated 1-5 news score semantic and the
unvalidated composite signal built on it. It preserves raw news, raw news
counts, morning brief, watchlist/profile behavior, score-free news-volume
detection, and event sequences under the product decisions in the authority.

This is one atomic product cutover. The storage projection, readers, writers,
DTOs, tools, routes, monitor names, model-visible descriptions, frontend types,
tests, and current authorities must leave together. A temporary compatibility
endpoint, permanent zero response, neutral `3.0`, hidden score field, or dead
advertised tool is not an allowed intermediate product.

### 0.2 Explicit non-authorizations

This plan does not authorize any of the following:

- deleting, updating, copying, vacuuming, migrating, or otherwise mutating the
  491,808 production `news_article_scores` rows;
- reading, hashing, printing, copying, rotating, deleting, or migrating the
  contents of `config/scoring_keys.txt`;
- adding a scorer, scheduler, provider request, model request, paid request, or
  replacement sentiment semantic;
- reusing the retired table, field names, 1-5 scale, cache identity, or tool
  names for provider-native or future on-demand sentiment;
- implementing the future Signals product, a recommendation, or a rank;
- changing `training/` research lineage, provider-native sentiment collection,
  investor-profile risk semantics, normalized raw news, or Seeking Alpha;
- pushing a branch; or
- starting product edits before independent review clears this plan and the
  current OAuth implementation gate has an explicit handoff.

The later disposition packet for score rows and the later exact-path decision
for `config/scoring_keys.txt` are separate work. Neither may be prepared as a
side effect of this product implementation. The row packet must choose exact
deletion by default unless it proves a concrete research use worth discussing;
any approved research retention moves outside the runtime DB under a named,
historical owner. Runtime reconnection is not an outcome.

### 0.3 Atomicity and projected stages

Sections 2.5 and 5 describe five **collection-ledger projections**. They are
precomputed accounting witnesses only. They are not shippable releases, full
suite baselines, or permission to retain a half-removed compatibility surface.

RED tests are written first. The implementation then completes all five
product phases in one unmerged worktree before canonical admission. Only the
final `4461/c7cb78b2...` backend and `1078/de1e0c3f...` frontend identities may
be called GREEN. If a module dependency makes an intermediate projection
uncollectable, stop and finish the owning atomic phase; do not add a shim merely
to make the intermediate tree look green.

### 0.4 Canonical execution boundary

Backend collection and compatible focused tests may run in the managed
environment. Canonical full-suite admission must run in a fresh exact-tip
native worktree with no `config/.env`, an existing empty `data/`, absent
`src/data`, and the pinned `node_modules` toolchain. The wakeup probe must pass
in the same execution context immediately before the suite.

Pinned assets:

| Asset | Required identity |
|---|---|
| `/tmp/arkscope_asyncio_wakeup_probe.py` | `10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e` |
| `/tmp/eir002-green-baseline/arkscope_eir002_reporter.py` | `09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928` |
| `/tmp/eir002-green-baseline/run_native.sh` | `e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f` |
| repository `package-lock.json` | `5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c` |
| pinned `node_modules/.package-lock.json` | `4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff` |
| EIR-006 Vitest normalizer | `62 lines / 2,233 bytes / 955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac` |

Toolchain: Node `v22.14.0`, jsdom `29.1.1`. The required wakeup result is:

```json
{"callback_fired": true, "ready_count": 0, "wake_bytes": 0}
```

Every native stage name is single use. Inventory ordinary and ignored status,
`data/`, `src/data`, symlinks, and toolchain identities before and after. New
test artifacts are recorded by exact relative path and quarantined; any
modified pre-existing file is a stop condition.

## 1. Owned and protected paths

### 1.1 Product owners

The implementation may edit or delete only grounded members of these owner
groups. The Task 0 consumer census must turn this grouped map into an exact
path manifest before product edits.

| Group | Owners |
|---|---|
| score storage/writer | `src/news_normalized/schema.py`, `scores.py`, `score_import.py`, `src/market_data_admin.py`, `src/news_identity.py`, `src/daily_update.py`, all nine tracked `scripts/` paths |
| raw news protocol | `src/tools/schemas.py`, `data_access.py`, `news_tools.py`, `analysis_tools.py`, `src/analysis/context_builder.py`, `src/tools/backends/{__init__,db_backend,file_backend,local_market_backend,sqlite_backend}.py` |
| event/signal implementation | delete `src/signals/README.md`, `src/signals/{__init__,anomaly_detector,event_chain,event_tagger,sector_aggregator,synthesizer}.py`, and `src/tools/signal_tools.py`; add `src/news_analytics.py` and `src/tools/news_event_tools.py`; retire `src/analysis/pipeline.py` and `src/analysis/strategies/{__init__,decision,sentiment}.py` |
| HTTP/profile | `src/api/app.py`, `src/api/routes/{news,profile,signals}.py` |
| monitoring | `src/monitor/{__init__,engine,watchers}.py`, `src/tools/monitor_tools.py`, `config/user_profile.yaml` |
| model-visible contract | `src/tools/registry.py`, `src/agents/shared/{prompts,subagent}.py`, `src/agents/{anthropic_agent,openai_agent}/tools.py`, `src/evidence_packet.py` retirement copy only, and exact tool-count/allowlist owners found by Task 0 |
| frontend DTO fixtures | `apps/arkscope-web/src/api.ts`, `Home.test.tsx`, `Watchlist.test.tsx`, `Universe.test.tsx`, new `legacyScoreRetirement.test.ts` |
| current authorities | the exact current/historical disposition in section 1.3 below plus this plan/evidence/spec and `PROJECT_PRIORITY_MAP.md` |

The surviving PD 5-PD 6 capabilities move to honest news/event owners. Delete
the complete `src/signals/` package and `src/tools/signal_tools.py`; add no
compatibility import, re-export, alias module, or old `TestSignalTools`
namespace. `src/news_analytics.py` owns only deterministic raw news-volume,
title-event tagging, and event-sequence logic. `src/tools/news_event_tools.py`
owns the two surviving agent wrappers. The public `/signals` router and every
model-visible composite Signals capability leave.

### 1.2 Test owners

Existing tests may evolve or leave only through the exact ledger in section 2.
The focused family is:

```text
tests/test_agents.py
tests/test_analysis_pipeline.py
tests/test_api.py
tests/test_daily_update_wrapper.py
tests/test_db_backend.py
tests/test_evidence_packet.py
tests/test_market_data_admin.py
tests/test_monitor.py
tests/test_news_identity.py
tests/test_news_event_tools.py (new)
tests/test_news_normalized_schema.py
tests/test_news_normalized_scores.py
tests/test_news_pg_unreachable.py
tests/test_news_score_import.py
tests/test_news_score_migration.py
tests/test_news_score_tool_parity.py
tests/test_news_scores.py
tests/test_profile_state.py
tests/test_score_ibkr_keys.py
tests/test_scoring_api_routing.py
tests/test_scoring_continue_from.py
tests/test_signal_factors_p1.py
tests/test_sqlite_backend.py
tests/test_subagent.py
tests/test_tools.py
tests/test_legacy_score_retirement.py (new)
```

Frontend focused files are `Home.test.tsx`, `Watchlist.test.tsx`,
`Universe.test.tsx`, and new `legacyScoreRetirement.test.ts`.

### 1.3 Current versus historical documents

The cutover must reconcile current instructions in at least:

```text
docs/design/ARKSCOPE_TOOL_CATALOG.md
docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md
docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md
docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md
docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md
docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Historical plans, evidence, and migration records keep dated facts. They may
receive a short historical/superseded marker only when a current instruction
would otherwise remain runnable. Do not rewrite historical evidence to hide the
old implementation.

### 1.4 Protected boundaries

Task 0 pins an exact blob/path manifest for these boundaries and Task 6 proves
byte identity except for the explicitly bounded EvidencePacket copy delta:

- all tracked `training/` files (current 53-path blob-stream SHA
  `2284c8989f6104979a11a5111de987f5d6f2974e3d2f74f0cf47ed5b4854e14a`);
- `data_sources/alpha_vantage_source.py`, `data_sources/polygon_source.py`,
  `src/collectors/finnhub_news.py`, and `src/collectors/polygon_news.py`;
- investor-profile risk owners and tests;
- EvidencePacket output shape, news whitelist, score/composite exclusion, and
  tests. `src/evidence_packet.py` may change only the docstring/current
  `_EXCLUSION_NOTE` wording that names the retired `signal_tools` module; it is
  excluded from the byte-identical path manifest, receives a pre/post blob
  review, and may not change projection or gather logic;
- normalized raw-news and Seeking Alpha ingestion/feed owners;
- OAuth lifecycle worktree/branch and its evidence;
- production DB bytes except read-only witnesses; and
- `config/scoring_keys.txt` contents and bytes.

Provider-native `source_sentiment` and investor `risk_score` are not the retired
ArkScope 1-5 score. The new boundary test must prove they remain available and
must not erase them through a broad text replacement.

## 2. Exact node ledger

### 2.1 Backend base, RED, and final identities

All streams are UTF-8 node IDs, unique, sorted by byte order, with one trailing
newline. They are derived from the deterministic reporter, never terminal prose.

| State | Nodes | SHA-256 |
|---|---:|---|
| reviewed base | 4,581 | `6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f` |
| RED tests added, old nodes retained | 4,599 | `ae382261eddb2b9bbe02e8c15ca2acc48a23a99745d910a28aba8f4ac7e3059b` |
| final target | 4,461 | `c7cb78b222952e9c1b5b3e18abcf413a14875a84ef7bc01d55ef500d939a74f9` |

Arithmetic: `4581 + 18 - 138 = 4461`. The 138-node retired stream is
`b48b161d573afb37496763c0afe388c2421f06e35eb5cd7de959ba5778c05254`.
The 18-node addition stream is
`88ac9e5652c9df79eb42284d6a9c42a2f0f4a60b967badae37524fa127499520`.
Their intersection with the base/non-base sets must be exact: all retired IDs
exist once in base; all additions are absent from base.

### 2.2 Whole retired test files

| File | Nodes |
|---|---:|
| `tests/test_news_scores.py` | 19 |
| `tests/test_news_score_import.py` | 7 |
| `tests/test_news_score_tool_parity.py` | 4 |
| `tests/test_news_normalized_scores.py` | 5 |
| `tests/test_news_score_migration.py` | 5 |
| `tests/test_signal_factors_p1.py` | 33 |
| `tests/test_score_ibkr_keys.py` | 11 |
| `tests/test_scoring_continue_from.py` | 17 |
| `tests/test_scoring_api_routing.py` | 1 |
| **Total** | **102** |

### 2.3 Mixed-file retired nodes

The remaining 36 IDs leave without deleting their containing files:

```text
tests/test_api.py::TestNewsEndpoints::test_get_news_sentiment
tests/test_api.py::TestSignalEndpoints::test_anomalies
tests/test_api.py::TestSignalEndpoints::test_event_chains
tests/test_api.py::TestSignalEndpoints::test_synthesize_signal
tests/test_daily_update_wrapper.py::test_scores_flag_is_retired_and_does_not_shell_to_pg_importer
tests/test_db_backend.py::TestNewsDB::test_query_news_scored_only
tests/test_market_data_admin.py::test_ensure_news_sentiment_columns_migrates_pre_existing_in_place
tests/test_market_data_admin.py::test_ensure_news_sentiment_columns_no_news_table_is_safe
tests/test_market_data_admin.py::test_local_news_sentiment_score_is_check_constrained_to_1_5
tests/test_monitor.py::TestSentimentWatcher::test_no_alert_when_disabled
tests/test_monitor.py::TestSentimentWatcher::test_sentiment_shift_alert
tests/test_monitor.py::TestSignalWatcher::test_high_risk_alert
tests/test_monitor.py::TestSignalWatcher::test_hold_no_alert
tests/test_monitor.py::TestSignalWatcher::test_reuses_preloaded_news_context_across_tickers
tests/test_monitor.py::TestSignalWatcher::test_strong_buy_alert
tests/test_news_identity.py::test_apply_merges_missing_sentiment_fields
tests/test_news_normalized_schema.py::test_article_scores_schema_constraints_and_indexes
tests/test_sqlite_backend.py::test_news_local_unscored_scored_falls_back
tests/test_sqlite_backend.py::test_query_news_model_filter_uses_normalized_model_name
tests/test_sqlite_backend.py::test_query_news_normalized_scores_joins_maps_after_news_filter
tests/test_sqlite_backend.py::test_query_news_scored_no_pg_fallback
tests/test_sqlite_backend.py::test_query_news_scored_returns_empty
tests/test_sqlite_backend.py::test_query_news_search_scored_no_pg_fallback
tests/test_sqlite_backend.py::test_query_news_search_surfaces_local_sentiment
tests/test_sqlite_backend.py::test_query_news_search_surfaces_normalized_scores
tests/test_sqlite_backend.py::test_query_news_stats_aggregates_local_sentiment
tests/test_sqlite_backend.py::test_query_news_stats_aggregates_normalized_scores
tests/test_sqlite_backend.py::test_query_news_surfaces_local_sentiment_when_present
tests/test_sqlite_backend.py::test_query_news_surfaces_normalized_scores_from_both_legacy_maps
tests/test_sqlite_backend.py::test_query_news_unscored_mode_keeps_unscored_rows_with_score_columns
tests/test_subagent.py::TestAnthropicBridgeIntegration::test_anthropic_tools_count_31
tests/test_subagent.py::TestOpenAiBridgeIntegration::test_openai_tools_count_31
tests/test_tools.py::TestNewsTools::test_get_news_sentiment_summary
tests/test_tools.py::TestSignalTools::test_detect_anomalies
tests/test_tools.py::TestSignalTools::test_detect_event_chains
tests/test_tools.py::TestSignalTools::test_synthesize_signal
```

Two retired nodes are canonical skips in the blank environment:

- `TestNewsDB::test_query_news_scored_only` is skipped by the existing
  `requires_db` marker;
- `test_contributions_sum_to_composite_score` in the retired factor file skips
  when the empty fixture emits no factors.

This was directly reproduced as `2 skipped`; therefore the final native target
is `4391 passed / 70 skipped / 0 failed`, not an inferred pass total.

### 2.4 New backend nodes

The 18 additions are independent named contracts:

```text
tests/test_api.py::test_retired_sentiment_and_signal_routes_are_absent_while_raw_news_remains_reachable
tests/test_legacy_score_retirement.py::test_current_authorities_make_no_legacy_capability_claim
tests/test_legacy_score_retirement.py::test_fresh_schemas_create_no_legacy_score_storage
tests/test_legacy_score_retirement.py::test_model_visible_contracts_exclude_legacy_score_and_composite_capabilities
tests/test_legacy_score_retirement.py::test_ordinary_news_contract_has_no_legacy_score_fields
tests/test_legacy_score_retirement.py::test_provider_native_sentiment_and_investor_risk_contracts_are_preserved
tests/test_legacy_score_retirement.py::test_raw_news_backend_contract_has_no_score_parameters
tests/test_legacy_score_retirement.py::test_runtime_legacy_score_consumer_writer_census_is_closed_and_empty
tests/test_legacy_score_retirement.py::test_scoring_scripts_and_root_package_are_absent
tests/test_monitor.py::TestNewsVolumeWatcher::test_news_volume_spike_alert
tests/test_monitor.py::TestNewsVolumeWatcher::test_no_alert_under_volume_threshold
tests/test_monitor.py::TestNewsVolumeWatcher::test_no_alert_when_disabled
tests/test_news_event_tools.py::test_detect_event_chains_returns_typed_unavailable_impact
tests/test_news_event_tools.py::test_detect_news_volume_anomaly
tests/test_news_identity.py::test_apply_collision_does_not_project_retired_sentiment_fields
tests/test_subagent.py::TestAnthropicBridgeIntegration::test_anthropic_tools_match_registry
tests/test_subagent.py::TestOpenAiBridgeIntegration::test_openai_tools_match_registry
tests/test_tools.py::TestAnalysisTools::test_get_morning_brief_orders_raw_news_deterministically
```

Do not parametrize these into fewer IDs or create helper names beginning with
`test_`. Every node owns a distinct regression shape.

The two bridge count IDs are explicit renames, not accidental churn. Retaining
`tools_count_31` while changing its assertion would leave a false test name;
the replacement IDs instead assert exact equality with the current registry.
The raw-backend node must exercise query, ticker, source, date, and pagination
behavior in addition to proving that old score parameters are absent.

### 2.5 Audit projections

These projections are constructed from the exact removal/addition streams and
must be independently reproducible. They do not authorize intermediate merge.

| Projection | Nodes | SHA-256 | Delta from prior |
|---|---:|---|---|
| storage/writer/root | 4,537 | `e2a744b8fdcb9cadcaa1a9e68f050805faf36b5e7beae1d033d889a71e2f44af` | `+2/-46` |
| raw DTO/backend | 4,498 | `55b26b2ea092a378f04eb8f64de248e7c74364544ec1ab00eee2c29fb157324c` | `+4/-43` |
| raw user behavior | 4,498 | `d6a0793368c7cc68b81bb96863028b46db4cbd3dc6200977b7ec8621d5fda2ba` | `+1/-1` |
| volume/event/composite | 4,458 | `3896c617ca5594b30a644bd8cf61f96eea39ba753cf1858049121c626dfc469b` | `+5/-45` |
| model/API/authority/census final | 4,461 | `c7cb78b222952e9c1b5b3e18abcf413a14875a84ef7bc01d55ef500d939a74f9` | `+6/-3` |

### 2.6 Backend focused identities

| State | Nodes | SHA-256 |
|---|---:|---|
| base | 555 | `ea5d897ca3597ef4edca7583db0b363360ceba9e362e516422f901ff8af004dd` |
| RED additions present | 573 | `5e0a5538c4106ca9b9cf0d701ab719d62c3a4056d1e101864ddb09b6beb9fb75` |
| final | 435 | `2e5fcb6c22d6a1657e609542138830f2d5fd367a0e353ab30efdfbb8851a7c6a` |

### 2.7 Frontend identities

Use only the pinned JSON-decoding normalizer from section 0.4. Raw JSON text,
terminal output, `jq @tsv`, or prose parsing is not an identity authority.

| State | Files / nodes | SHA-256 |
|---|---:|---|
| full base | `97 / 1077` | `3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb` |
| full target | `98 / 1078` | `de1e0c3fccb1fad3574a5089f76164791895e7c5a70bb4a2ce578b38b30d4192` |
| focused base | `3 / 27` | `c77d25d5bf7c868899d555f099fc245b13d35d4052a6a8242ac3f5c1300fb584` |
| focused target | `4 / 28` | `b11cc27b90c570b20aeb728c48d39497e7eff555976f0c00a42d6129b26cf1cd` |

The sole addition is:

```text
src/legacyScoreRetirement.test.ts<TAB>legacy score retirement boundary > removes score fields from current frontend DTOs and fixtures
```

Its one-row stream SHA is
`6ee13afa0a184c2de613001edd698a99f3fa24516e69fa8600625c3860088e62`.

### 2.8 Retained IDs whose assertions evolve

These 25 base IDs remain present exactly once. Their assertions evolve with the
approved behavior rather than disappearing under the net node count:

```text
tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news
tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count
tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names
tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count
tests/test_analysis_pipeline.py::test_build_dal_context_builder_uses_existing_data_access_contracts
tests/test_analysis_pipeline.py::test_default_strategy_chain_degrades_when_nontechnical_context_is_missing
tests/test_analysis_pipeline.py::test_default_strategy_chain_runs_end_to_end_with_mixed_context
tests/test_api.py::TestConfigEndpoints::test_morning_brief
tests/test_api.py::TestConfigEndpoints::test_overview
tests/test_api.py::TestConfigEndpoints::test_watchlist
tests/test_api.py::TestNewsEndpoints::test_search_news
tests/test_evidence_packet.py::test_news_rows_are_whitelisted_fields_only
tests/test_evidence_packet.py::test_no_llm_scores_anywhere_in_packet
tests/test_monitor.py::TestMonitorEngine::test_scan_once_records_watcher_metrics
tests/test_monitor.py::TestMonitorEngine::test_scan_once_returns_alerts
tests/test_monitor.py::TestMonitorToolRegistration::test_scan_alerts_registered
tests/test_profile_state.py::test_legacy_overview_enriches_but_never_qualifies_universe
tests/test_subagent.py::TestSubagentRegistry::test_code_analyst_has_enhanced_tools
tests/test_tools.py::TestAnalysisTools::test_get_morning_brief
tests/test_tools.py::TestAnalysisTools::test_get_watchlist_overview
tests/test_tools.py::TestNewsTools::test_get_ticker_news
tests/test_tools.py::TestNewsTools::test_search_news_by_keyword
tests/test_tools.py::TestNewsTools::test_search_news_keyword_case_insensitive
tests/test_tools.py::TestRegistry::test_tool_catalog_live_table_matches_registry
tests/test_tools.py::TestRegistry::test_tool_names
```

Their sorted stream SHA is
`2f0e0dd31390f975eb2b4f20244525a0bf09b0bc112f39f0f4cebfe2db76aa08`.
Task 0 and final review require identity preservation and inspect assertion
changes against PD 2-8. The two count-bearing bridge IDs are deliberately not
in this retained set; section 2.4 records their truthful renames.

## 3. Locked behavior after cutover

### 3.1 Raw news and DTOs

- `NewsArticle` and `NewsBrief` have no ArkScope legacy score/risk/model fields.
- DAL/backend raw news methods have no `scored_only`, `model`,
  `min_sentiment`, or `max_risk` parameters.
- Ticker/query/source/date/pagination, article count, earliest/latest date,
  source breakdown, title, timestamp, URL, and excerpt remain.
- Raw file fallback may read raw news only; it may not detect old score columns.
- Fresh schemas do not create `news_article_scores`; existing production table
  bytes remain untouched.

### 3.2 Morning brief, profile, and frontend

- Morning brief performs one raw one-day batch query for the tracked/watchlist
  universe, excludes zero-count tickers, sorts by count descending, latest date
  descending, ticker ascending, and returns at most five exact
  `{ticker,count,latest_date}` rows.
- Watchlist/profile/universe keep price and raw news count and remove
  `sentiment_mean`/`bullish_ratio` from Python and TypeScript DTOs.
- No visible frontend feature is replaced; fixtures stop teaching hidden fields.

### 3.3 Volume, events, and Signals

- `NewsVolumeWatcher` and `detect_news_volume_anomaly` use raw count windows and
  use no score preload or sentiment threshold.
- `src/news_analytics.py` is the sole pure owner for raw volume anomaly,
  deterministic title-event tagging, and event sequence detection;
  `src/tools/news_event_tools.py` is the sole tool wrapper owner.
- Event chains retain sequence fields and return exactly
  `impact={status:"unavailable",reason:"legacy_score_retired"}`. They contain no
  numeric impact and no per-event sentiment impact.
- `src/signals/`, `src/tools/signal_tools.py`, scorer-oriented tagging prompts,
  sentiment anomaly/sector aggregation, and all compatibility exports are
  absent.
- `synthesize_signal`, `get_signal_factors`, `SignalWatcher`, current rank and
  recommendation types, and the public `/signals` router are absent.
- Future Signals remains a product goal, not a compatibility alias.
  `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` and the Priority Map retain that roadmap;
  this cutover clears the invalid semantic so the later research can start on
  explicit hypotheses, OOS validation, and kill criteria.

### 3.4 Model-visible and authority contract

- Registry, Anthropic/OpenAI bridges, prompts, subagent allowlists, monitor copy,
  examples, and current docs advertise only surviving raw capabilities.
- `get_news_sentiment_summary`, old score filters, `detect_anomalies`, and
  `synthesize_signal` are absent rather than returning typed zeroes.
- EvidencePacket's existing exclusion remains behavior protected; only the
  reviewed retirement wording changes, with output shape and whitelist intact.
- Historical docs remain historical; current authorities contain no runnable
  scorer or current composite claim.

## 4. RED and mutation discipline

### 4.1 RED-first rules

Create all 18 backend nodes and the one frontend node before product edits.
Imports of future symbols must occur inside test bodies or use explicit
`getattr`/route/schema assertions so collection remains clean. Every node must
fail for its intended missing/legacy contract. SQLite setup errors, missing
empty `data/`, fixture import errors, or unavailable test tooling are wrong RED.

The RED collection identities are `4599/ae382261...`,
`573/5e0a5538...`, and frontend `1078/de1e0c3f...`. Runtime RED evidence names
each node and expected assertion. A broad static grep alone is not sufficient
for behavior contracts.

### 4.2 Required mutation cycles

After GREEN, apply each mutation only to its owning node, save the exact diff,
prove RED for the intended reason, restore the pre-mutation blob, and prove the
restored SHA before the next cycle.

| ID | Mutation | Owning witness |
|---|---|---|
| M1 | re-add fresh `news_article_scores` DDL | fresh-schema boundary |
| M2 | re-add `scored_only` or a legacy field to the raw backend/DTO contract | raw backend + ordinary DTO nodes |
| M3 | make morning brief depend on scored rows or reverse its deterministic tie order | two morning-brief behavior nodes (existing positive plus new tie node) |
| M4 | restore `sentiment_mean`/`bullish_ratio` to profile or frontend DTOs | backend ordinary contract + frontend boundary |
| M5 | restore the old watcher/tool namespace, compatibility export, or sentiment branch | NewsVolumeWatcher/news-event tool nodes |
| M6 | restore `fillna(3.0)`, numeric `impact_score`, event sentiment impact, or scorer-oriented tag prompt | news-analytics event-chain exact-payload owner |
| M7 | restore a `/signals` route, composite tool, bridge schema, or prompt claim | API absence + model-visible census |
| M8 | restore a score writer/import executable | runtime writer census + scripts absence |
| M9 | restore legacy sentiment fields to `MERGE_FIELDS` | collision projection node |
| M10 | restore a current-authority claim that scoring/composite is available | current-authority node |

M2, M7, and M8 must mutate the real shared owner, not add a dead condition after
an empty target set. Mutation diffs are review artifacts; running the full suite
for each mutation is forbidden because it adds cost without discrimination.

## 5. Tasks

### Task 0 - Re-ground identities and protected state

1. Verify branch ancestry from `72576991` through `04dd9a67`; verify this plan,
   authority, evidence, and priority entry are the only plan-gate changes.
2. Verify all pinned assets in section 0.4 by full SHA, not prefix matching.
3. Collect backend full/focused base streams and frontend full/focused base
   streams. Require exact section 2 identities.
4. Reconstruct retired/addition/projection streams independently from the named
   IDs. Require all counts and SHA values in section 2.
5. Run the backend focused base suite and the current frontend focused suite.
   Any non-passing node stops the line.
6. Run native canonical base admission under section 0.4 and require
   `4581 seen / 4509 passed / 72 skipped / 0 failed`.
7. In read-only SQLite URI mode plus `PRAGMA query_only=ON`, record table
   existence, exact current score-row count, min/max article date and scored-at,
   and DB identity. The reviewed 491,808 count is a dated expectation, not a
   value to force.
8. For `config/scoring_keys.txt`, record only path existence, mode, inode, and
   mtime. Do not read, hash, print, copy, or record content/size.
9. Build the exact owned-path and protected-path blob manifests. Require the
   53-path `training/` stream SHA in section 1.4.
10. Record Task 0 evidence, commit docs only, and stop for independent review.

No RED test or product byte may be changed in Task 0.

### Task 1 - Establish RED across every approved surface

1. Add `tests/test_legacy_score_retirement.py` with the eight exact IDs in
   section 2.4.
2. Add the API absence/raw-news node, three NewsVolumeWatcher nodes, one
   morning-brief tie node, two score-free news-event tool nodes in the new
   `test_news_event_tools.py` owner, the collision projection node, and the two
   truthful bridge-registry IDs under their existing describe/class owners.
3. Add `legacyScoreRetirement.test.ts` with the exact frontend ID.
4. Collect and require the RED identities in sections 2.1, 2.6, and 2.7.
5. Run each owning node separately and record the intended RED reason. Existing
   raw-news/provider-native/EvidencePacket owners must remain GREEN.
6. Do not commit a knowingly RED product branch. Preserve the RED artifacts and
   proceed directly to the atomic cutover only after independent Task 0 review.

### Task 2 - Execute the atomic product cutover

Complete all five phases before any claim of GREEN:

1. **Storage/writer/root:** delete all nine `scripts/` paths, the score importer
   and writer-only key/API helpers, remove the daily-update tombstone, stop fresh
   score-table/column creation, and remove the corresponding 46 test IDs while
   adding the two storage/root boundaries.
2. **Raw DTO/backend:** remove score fields/parameters/projection/aggregation
   across schemas, DAL, all backends, identity merge, and analysis context;
   remove 43 old IDs and add four raw/provenance boundaries.
3. **Raw user behavior:** remove the sentiment summary contract, rebuild morning
   brief from one raw batch, remove hidden profile/frontend sentiment fields,
   remove one old node, and add the deterministic tie node.
4. **Volume/event/composite:** move approved raw-volume/title-event/sequence
   behavior into `src/news_analytics.py` plus
   `src/tools/news_event_tools.py`; delete the complete `src/signals/` and
   `src/tools/signal_tools.py` namespaces without re-export; evolve event chains
   to exact typed unavailable impact; remove composite/rank/router/strategy/
   watcher owners and 45 old nodes; and add five news-volume/event owners.
5. **Model/API/authority/census:** remove the final sentiment route and all dead
   model-visible claims, update only the bounded EvidencePacket retirement copy,
   reconcile current authorities, add fail-closed runtime census/API/model/
   current-doc nodes, replace the two stale bridge count IDs, and remove the
   final old route node (`+6/-3`).

During these phases, reconstruct each projected node stream in section 2.5 from
the ledger. Do not treat an intermediate projection as a test baseline. At the
end require exact backend `4461/c7cb78b2...`, focused `435/2e5fcb6c...`,
frontend `98/1078/de1e0c3f...`, and focused frontend `4/28/b11cc27b...`.

The runtime census must be structured and fail closed. Every discovered
consumer/writer/current-authority path receives exactly one disposition:
`retired`, `raw_preserved`, `provider_native_protected`,
`historical_only`, or `current_authority_rewritten`. Unknown, duplicate, or
unclassified paths fail. Run it in an unlocked tree or explicitly enumerate
git-crypt files as unsearchable-by-content and classify by path.

Commit the complete product/test/current-authority cutover as one atomic commit.
No production data or secret byte belongs in the commit.

### Task 3 - Prove focused GREEN and mutation sensitivity

1. Run the 435-node backend focused suite. Existing allowed skips must be named;
   all other nodes pass.
2. Run frontend focused `28/28`, full Vitest `1078/1078`, typecheck, build, and
   the current i18n scanner.
3. Run existing raw-news, normalized-news, Seeking Alpha, provider-native
   sentiment, investor-risk, EvidencePacket, profile, and monitor protection
   suites.
4. Execute M1-M10 exactly as section 4.2. Record diff SHA, owning-node RED,
   pre/post blob SHA, and restored GREEN for every cycle.
5. Re-run the structured runtime census and require zero retired consumer or
   writer and zero unknown classifications.
6. Recheck production score rows read-only and secret metadata-only. Require no
   product-cutover mutation.

### Task 4 - Canonical native admission

1. Create a fresh exact-tip detached worktree with the section 0.4 boundary.
2. Run the wakeup probe in that same native context.
3. Collect exact backend target `4461/c7cb78b2...` and frontend target
   `1078/de1e0c3f...` before runtime.
4. Run the native suite through the pinned wrapper/reporter. Require all 4,461
   collected nodes seen, empty non-passing stream, exit zero, and
   `4391 passed / 70 skipped / 0 failed`.
5. Record every generated path, quarantine exact paths, and restore pre-run
   ordinary/ignored/data/src-data/symlink/toolchain boundaries byte-for-byte.
6. Prove protected-path manifests and production read-only witnesses unchanged.
7. Complete implementation evidence and stop before merge for independent
   implementation review.

### Task 5 - Independent review and fast-forward merge

The reviewer reconstructs, rather than trusts prose:

- all backend/frontend base, RED, projected, focused, and final streams;
- exact `+18/-138` and frontend `+1/-0` node identities;
- the 102 whole-file and 36 mixed-file retirements;
- all 18 backend additions and the frontend addition;
- M1-M10 diffs, RED reasons, and restored blob SHAs;
- structured consumer/writer/current-authority census;
- native report, empty non-passing set, and artifact transaction;
- protected provider-native/training bytes plus the exact EvidencePacket copy
  delta and unchanged negative-contract behavior; and
- read-only score-row and metadata-only secret boundaries.

After GREEN, prove linear ancestry and use `git merge --ff-only`. Do not push.

### Task 6 - Merged verification and closeout

1. In a fresh exact-master native worktree, repeat final collection, frontend,
   focused/protected, and canonical native admission with new single-use stage
   names.
2. Perform read-only rollout checks: raw news remains available, morning brief
   uses raw activity, old sentiment and `/signals` routes/tools are absent,
   volume/event contracts match PD 5-6, and score rows remain untouched.
3. Record `SCRIPTS_TRANCHE_B_PRODUCT_CUTOVER_TIP` and update authority/evidence/
   priority status in a docs-only closeout commit after focused review.
4. Only after merged rollout may a new read-only task classify concrete
   research utility, build an exact score-row disposition manifest, and inspect
   scoring-secret **consumer metadata**. It must present detailed provenance,
   limitations, owner/hypothesis, and non-reproducible value before proposing an
   external historical research artifact; absent that evidence, exact deletion
   is the default. Keeping rows in the runtime DB is forbidden. Physical row
   deletion, any external research retention, and exact-path secret disposition
   each require independent review and a later explicit user approval. They are
   not Task 6 mutations.

## 6. Stop conditions

Stop immediately and amend/review before continuing if any of these occurs:

1. any base, RED, projection, focused, or final collection identity differs;
2. a retired ID is missing from base, an addition already exists, or an
   unplanned node is added/removed/renamed/parametrized;
3. RED occurs through collection/import/fixture/tooling failure rather than the
   intended product assertion;
4. an intermediate projection is described as shippable or full GREEN;
5. a compatibility shim, permanent zero endpoint, neutral `3.0`, dead tool
   advertisement, legacy `src/signals/` or `src/tools/signal_tools.py` survivor,
   compatibility re-export, or old `TestSignalTools` namespace is proposed;
6. raw news, morning brief, profile counts, volume detection, or event sequence
   is removed rather than evolved as approved;
7. provider-native sentiment or investor risk is mistaken for the retired
   ArkScope score and removed;
8. the current composite/rank/recommendation survives under another name;
9. a future Signals semantic is implemented without its separate evidence gate;
10. any scorer/model/provider/scheduler/network request is added or triggered by
    this implementation;
11. production `news_article_scores` is written, deleted, migrated, vacuumed, or
    used as a new acceptance fixture;
12. `config/scoring_keys.txt` contents, bytes, digest, size, or secret values are
    read or recorded;
13. a deletion manifest is built before product merge and read-only rollout;
14. `training/`, normalized raw news, Seeking Alpha, OAuth, or a protected
    collector changes outside reviewed scope, or EvidencePacket changes beyond
    the exact retirement-copy delta while its projection/gather logic is not
    byte-identical;
15. the runtime census has an unknown, duplicate, or unclassified path;
16. the census relies only on locked git-crypt ciphertext without explicit path
    classification;
17. a mutation changes a dead branch or fails to turn its owning node RED;
18. a mutation restore does not reproduce the exact pre-mutation blob;
19. frontend identity is parsed from escaped JSON text or terminal prose;
20. native wakeup preflight fails or full admission runs in the managed sandbox;
21. full admission does not see every collected node or has any non-passing ID;
22. a test run modifies a pre-existing repository-relative file;
23. an artifact cannot be restored by exact path without touching production;
24. merge is non-fast-forward, contains an unexpected commit, or would push; or
25. OAuth and Tranche B edit the same owner without an explicit reviewed handoff.

## 7. Completion criteria

The product cutover is complete only when:

- PD 1-8 behavior is live from merged master;
- backend is exactly `4461/c7cb78b2...`, frontend exactly
  `1078/de1e0c3f...`, and native admission is `4391/70/0`;
- no runtime reader/writer/model-visible/current-authority path exposes the old
  score or composite semantic;
- `src/signals/` and `src/tools/signal_tools.py` are physically absent, their
  approved surviving behavior is owned only by the new news analytics/tool
  modules, and no compatibility import or re-export remains;
- raw news, morning brief, profile counts, volume, and event sequence contracts
  remain green;
- protected provider-native/training boundaries are unchanged and EvidencePacket
  differs only by the reviewed retirement copy while preserving its negative
  contract;
- production score rows and scoring secret are still physically untouched; and
- later data/secret disposition remains explicitly blocked behind its own exact
  reviewed authority and user approval.
