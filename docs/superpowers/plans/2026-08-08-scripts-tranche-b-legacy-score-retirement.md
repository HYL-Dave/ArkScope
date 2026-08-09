# Scripts Tranche B Legacy Score Retirement Implementation Plan

> **Status:** TASK 0 MANIFEST PACKET COMPLETE; INDEPENDENT REVIEW PENDING;
> USER-AUTHORIZED BATCH CONTINUATION TO TASK 1; CUTOVER NOT YET COMMITTED
> **Date:** 2026-08-08
> **Current branch base:** `814ef2edd1b6aa66499145e1a9109d05f5fb0d89`
> **Reviewed inventory:** `098dff564faea1fc2617e198414ccde6067f23f8`
> (rebased byte-equivalent commit `8c952773`)
> **Product authority:**
> `docs/superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md`
> at reviewed commit `04dd9a67` (rebased byte-equivalent commit `f34463df`),
> plus the post-approval no-tail, training-retirement, and Phase D owner-closure rulings recorded in
> this plan-gate amendment
> **User ruling:** PD 1 through PD 8 approved as the section 8 bundle on
> 2026-08-08. On 2026-08-09 the user also superseded `training/`'s
> paused-preserve status and approved direct Git retirement with no archive or
> preservation branch. Physical score-row deletion and
> `config/scoring_keys.txt` disposition remain separately blocked.

## 0. Execution contract

### 0.1 Purpose

This plan removes the frozen ArkScope-generated 1-5 news score semantic and the
unvalidated composite signal built on it. It preserves raw news, raw news
counts, morning brief, watchlist/profile behavior, score-free news-volume
detection, and event sequences under the product decisions in the authority.
It also removes the disconnected offline RL/training implementation, its
implementation-only tests, manual yfinance smoke, unowned dependency surface,
and current instructions. Future RL/Signals research remains a new product
line, not a reason to retain this scaffold.

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
- changing provider-native sentiment collection, investor-profile risk
  semantics, normalized raw news, or Seeking Alpha;
- pushing a branch; or
- starting product edits before independent review clears this one-time
  absolute-identity amendment. OAuth, provider hygiene, and Settings navigation
  have already completed their reviewed handoffs on merged `master`.

The later disposition packet for score rows and the later exact-path decision
for `config/scoring_keys.txt` are separate work. Neither may be prepared as a
side effect of this product implementation. The row packet must choose exact
deletion by default unless it proves a concrete research use worth discussing;
any approved research retention moves outside the runtime DB under a named,
historical owner. Runtime reconnection is not an outcome.

### 0.3 Atomicity and projected stages

Sections 2.5 and 5 describe six **collection-ledger projections**. They are
precomputed accounting witnesses only. They are not shippable releases, full
suite baselines, or permission to retain a half-removed compatibility surface.

RED tests are written first. The implementation then completes all six
product phases in one unmerged worktree before canonical admission. Only the
final `4282/281cad97...` backend and `1124/da69a294...` frontend identities may
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

### 0.5 One-time post-handoff identity rebase

The full plan received independent GREEN review at pre-handoff tip `52354806`.
After OAuth, provider hygiene, and Settings navigation merged, the four
docs-only authority commits were rebased exactly once onto `814ef2ed`:

```text
098dff56 -> 8c952773  inventory
04dd9a67 -> f34463df  product decision
d1c5b5a5 -> bda76296  exact implementation plan
52354806 -> f9958efb  no-tail amendment
```

Before this amendment, the inventory, decision, plan, and evidence files were
byte-identical to their reviewed pre-rebase versions. Priority-map differences
are only the expected intervening merged history plus the same Tranche B
decision entry in newest-first order. The merged product base is exact backend
`4527/4eeb1178...` and frontend `98 files / 1123/9262d7b1...`.

The intervening reviewed lines changed backend collection by `-81/+27` and
frontend collection by `-1/+47`. Those delta streams have zero intersection
with the frozen Tranche B retirement and addition streams. All 138 retired IDs
still occur exactly once; all 18 backend additions and the one frontend
addition remain absent. Therefore only absolute full/projection identities and
native arithmetic were re-derived. At that review point, relative `+18/-138`,
frontend `+1/-0`, all node names, focused identities, phase partitions, product
decisions, protected boundaries, mutations, and destructive non-authorizations
were frozen. The later explicit user ruling in section 0.7 supersedes only the
training protected boundary and expands retirement to `+18/-247`; the Task 0
owner closure in section 0.8 expands it again to `+18/-263`; all older
relative and final identities remain dated evidence, not current admission.

At the one-time identity rebase, the product-decision document changed only its
status and completed-handoff sequence; its dated identity was `411 lines /
19,689 bytes / 0b5512e65abc851d5244c1065e2b8b82e3cf92be690b19032a39125670a61cfe`
(Git blob `51acdf559dcbb44ae01a52c14d583d826fbd0c97`). The later user training
ruling and this Phase D/PostgreSQL owner closure amend scope while leaving PD
1-PD 8 intact. The current decision identity is `457 lines / 22,825 bytes /
b490d46b250757c674af89f4f04d8e1030e35de1b442ec4847ee6f89a9b16e01`
(Git blob `7f01edc5cffb06aa4e5b796150fa080c9495c1f3`).

The old `4581 -> 4461` backend and `1077 -> 1078` frontend identities are dated
pre-handoff evidence only and are forbidden for admission after this amendment.

### 0.6 Task 0 no-tail owner amendment

Task 0 at reviewed rebase tip `5be77be2` reproduced every base and projected
identity plus native base admission before the exact owner census found one
omitted source path: `src/news_normalized/score_migration.py`. Its only tracked
importer is `tests/test_news_score_migration.py`, whose five nodes are already in
the frozen 138-node retirement ledger, and the module itself imports
`src.news_normalized.scores`, which this cutover deletes. Leaving it would create
an unowned, non-importable legacy-score migration tail.

This bounded amendment adds that source module to the phase-1 deletion set. It
does not change any backend or frontend node ID, collection count, projection,
native arithmetic, product decision, data/secret boundary, or approved surviving
capability. Focused review cleared this amendment at `a6e99c02` and allowed
Task 0 to resume at owned/protected-manifest construction without repeating the
unchanged native base gate.

### 0.7 User ruling: direct retirement of the training lineage

Manifest construction exposed that section 1.4 still protected a 53-path
offline training tree under the old `paused-preserve` ruling. The user has now
explicitly superseded that ruling. Grounding establishes:

- all 53 tracked `training/` paths form one disconnected RL research lineage;
  their current sorted `path<TAB>Git blob SHA-1` stream is
  `782dd7e42eabaacc814cde180b04f473d6e2433c6dd5e3cc907fa00f96211351`;
- no `src/`, app, scheduler, service, or current runtime imports `training`;
- exactly eight external test files import it, contributing 109 canonical
  nodes (`101 passed / 8 skipped` in the current environment);
- `tests/live/smoke_yfinance.py` exists only for this lineage and contributes no
  canonical node;
- `gymnasium`, `torch`, `datasets`, `mpi4py`, `spinup`, `matplotlib`,
  `stable-baselines3`, and `yfinance` have no remaining Python owner after this
  family leaves; these are eight package names but nine exact requirement lines
  because `torch` is duplicated; `scipy` remains owned by current option
  pricing; and
- current instructions/config still name the retired tree, yfinance smoke,
  `trained_models`, or the old paused status and must change in the same cutover.

The exact direct-deletion path stream contains 62 paths (53 training, eight
test files, and the manual smoke) and has SHA-256
`7c552b4940deeb666cd865656e980f9bba392507e6ed3f9b11b1672269b61c7d`.
The 109-node retirement stream is
`db3cad74da2ec956e252096948d80631297e9d4e8c731fb6706da7b2976941b2`.
Combined with the reviewed score/signal ledger, retirement is exact 247 nodes
with stream SHA
`149962668e116460f4b88402b1fabb8bb24f0a3409e33d8cade5924dd34ca671`.

Git history is the archive. Do not create a branch, tag, copied directory,
tarball, compatibility import, or disabled package for this deletion. The
future research intent is recorded in current product authorities, while any
future implementation starts from a new design. This ruling changes scope and
therefore invalidates the prior `-138/+18` implementation authorization; Task 0
stops for independent review of the expanded exact plan before any RED or
product byte changes.

### 0.8 Task 0 Phase D and PostgreSQL owner-closure amendment

The resumed exact owner census found that the first plan's partial Phase D
deletion was internally impossible. `src/analysis/pipeline.py` is imported by
the surviving factory, scheduler hooks, and service; those surfaces are in turn
mounted through an enabled `/analysis/run` route, `analysis_watchlist_batch`,
and `/analyze` CLI commands. The package's default chain consumes the retired
sentiment field and emits a weighted `buy`/`hold`/`sell` recommendation. It is
therefore the current unvalidated recommendation surface governed by PD 7, not
a neutral orchestration utility.

The exact disposition is complete retirement, not an in-place redesign:

- delete all 18 tracked `src/analysis/` paths, `src/api/routes/analysis.py`, and
  `tests/test_analysis_pipeline.py`;
- remove the route registration, scheduled job, CLI commands/status copy,
  feature flag/config, and current authority claims;
- preserve generic job-run persistence and report-history behavior by evolving
  their fixtures to current non-Phase-D jobs; do not delete those shared owners;
- delete executable legacy migration `sql/002_add_news_scores.sql`; and
- evolve `sql/001_init_schema.sql` to remove only score columns, the `signals`
  table/index/RLS example, and the sentiment-summary helper while preserving its
  unrelated raw-news, price, fundamentals, query-log, and helper definitions.

The sorted path-only 21-path Phase D/SQL deletion stream is
`635d5091410cbb953cadb768aa190b23690e035877188b0b58ccf9e160fcdba9`.
It contributes 16 additional passing-node retirements: all 12 nodes in
`tests/test_analysis_pipeline.py`, two analysis endpoint nodes, one analysis
batch node, and one analysis-only summary node. Combined retirement is exact
263 nodes with stream SHA
`93459510fc09e961b0d726527d953ed6fdfd07c584d598ee1de9a60851ca3eda`.
The 18 additions and frontend ledger are unchanged. This amendment implements
the approved no-tail/PD 7 result; it does not create the future Signals or
on-demand analysis design prohibited by compatibility rule 4.

Product bytes remain unchanged. Task 0 stops again before RED or implementation
until independent review clears this corrected owner map and exact ledger.

### 0.9 Task 3 stale shared registry-count owner amendment

The broad protected-suite gate after the cutover exposed an omitted shared-test
owner class. The approved registry change removes four legacy score/composite
tools, adds two honest news-event tools, and moves both surviving event tools to
the `news` category. The reviewed product truth is therefore registry `50`,
Anthropic/OpenAI bridge `51` including `delegate_to_subagent`, and news category
`11`. Ten existing assertions in five files still pinned the pre-cutover values
`53`, `54`, and `10`:

```text
tests/test_sa_tools.py::TestBridgeIntegration::test_registry_count
tests/test_sa_tools.py::TestBridgeIntegration::test_openai_schema_count
tests/test_sa_tools.py::TestBridgeIntegration::test_anthropic_schema_count
tests/test_sa_tools.py::TestBridgeIntegration::test_anthropic_bridge_count
tests/test_sa_tools.py::TestRegistryV3::test_registry_count
tests/test_sa_tools.py::TestRegistryV3::test_news_category_count
tests/test_analyst_tools.py::TestBridgeIntegration::test_registry_total_count
tests/test_memory_tools.py::TestMemoryToolRegistry::test_total_tool_count
tests/test_sec_tools.py::TestBridgeIntegration::test_registry_23
tests/test_portfolio_tools.py::TestPortfolioToolRegistration::test_tool_registered
```

All ten fail on the intended current value; no SA, analyst, memory, SEC, or
portfolio capability assertion fails. Their sorted node stream has SHA-256
`3c7e2870264e5959a6418701553af6a8870f2adde30b18b9c35e326056b4c305`.
Together with section 2.8's original 33 retained/evolved nodes, the exact
43-node stream has SHA-256
`7e4f4d2b5290f47c368227223a558043a040304eb6a042af5519e0207a91ed54`.

This amendment authorizes only the ten numeric assertion updates above. It
does not authorize node renames, collection changes, product changes, or other
test edits. `tests/test_sa_tools.py` is removed from the byte-identical path
manifest solely for this bounded delta; the re-pinned remaining 122-row
`path<TAB>Git blob` stream has SHA-256
`c174c7d7b7e9731d4cb04bf00a7b40af1fcaacee5c09f6c77c3f2c585d6f9ca2`.
Every non-authorized assertion in that file remains behavior protected. The
backend/frontend identities, `+18/-263` ledger, projection streams, and native
target remain unchanged.

## 1. Owned and protected paths

### 1.1 Product owners

The implementation may edit or delete only grounded members of these owner
groups. The Task 0 consumer census must turn this grouped map into an exact
path manifest before product edits.

| Group | Owners |
|---|---|
| score storage/writer | `src/news_normalized/schema.py`, `scores.py`, `score_import.py`, `score_migration.py`, `src/market_data_admin.py`, `src/news_identity.py`, `src/daily_update.py`, all nine tracked `scripts/` paths, delete `sql/002_add_news_scores.sql`, and evolve `sql/001_init_schema.sql` only as section 0.8 permits |
| raw news protocol | `src/tools/schemas.py`, `data_access.py`, `news_tools.py`, `analysis_tools.py`, `src/tools/backends/{__init__,db_backend,file_backend,local_market_backend,sqlite_backend}.py` |
| event/signal implementation | delete `src/signals/README.md`, `src/signals/{__init__,anomaly_detector,event_chain,event_tagger,sector_aggregator,synthesizer}.py`, `src/tools/signal_tools.py`, the complete 18-path `src/analysis/` scaffold, and `src/api/routes/analysis.py`; add `src/news_analytics.py` and `src/tools/news_event_tools.py` |
| HTTP/profile/jobs/CLI | `src/api/app.py`, `src/api/routes/{news,profile,signals,jobs}.py`, `src/service/jobs.py`, `src/agents/{config,cli}.py`, `config/user_profile.yaml` |
| monitoring | `src/monitor/{__init__,engine,watchers,discord_bot}.py`, `src/tools/monitor_tools.py` |
| model-visible contract | `src/tools/registry.py`, `src/agents/shared/{prompts,subagent}.py`, `src/agents/{anthropic_agent,openai_agent}/tools.py`, `src/evidence_packet.py` retirement copy only, and exact tool-count/allowlist owners found by Task 0 |
| frontend DTO fixtures | `apps/arkscope-web/src/api.ts`, `Home.test.tsx`, `Watchlist.test.tsx`, `Universe.test.tsx`, new `legacyScoreRetirement.test.ts` |
| current authorities | the exact current/historical disposition in section 1.3 below plus this plan/evidence/spec and `PROJECT_PRIORITY_MAP.md` |
| retired training lineage | delete all 53 tracked `training/` paths, the eight exact test owners in section 2.2, and `tests/live/smoke_yfinance.py`; remove only dependencies/config/ignore/current-copy entries proven ownerless by their exit |
| retirement boundary owners | evolve `tests/test_eir006_retired_data_boundaries.py`, generic service/job tests that used Phase D only as a fixture, and current Phase D/SQL authority copy; delete only the exact 16 nodes in section 2.3 |

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
tests/test_analysis_pipeline.py (retired whole-file owner)
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

The five shared registry-owner files in section 0.9 are outside the focused
family. Only their ten named assertions may evolve; every node ID remains.

### 1.3 Current versus historical documents

The cutover must reconcile current instructions in at least:

```text
docs/design/ARKSCOPE_TOOL_CATALOG.md
docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md
docs/design/AGENT_EVOLUTION_TRACKER.md
docs/design/README.md
docs/design/RL_COLLAPSE_FINDINGS.md
docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md
docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md
docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md
docs/design/PHASE_D_ANALYSIS_PIPELINE_SKETCH.md
docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md
docs/design/REPO_HYGIENE_AUDIT_2026_07.md
docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
docs/design/PROJECT_PRIORITY_MAP.md
README.md
PROJECT_STRUCTURE.md
scripts/scoring/README.md
tests/live/README.md
data_sources/API_SPECIFICATIONS.md
```

Historical plans, evidence, and migration records keep dated facts. They may
receive a short historical/superseded marker only when a current instruction
would otherwise remain runnable. Do not rewrite historical evidence to hide the
old implementation.

### 1.4 Protected boundaries

Task 0 pins an exact blob/path manifest for these boundaries and Task 6 proves
byte identity except for the explicitly bounded EvidencePacket copy delta:

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

The original Task 0 byte-protected manifest remains dated evidence. Section
0.9 is its sole exception: `tests/test_sa_tools.py` receives only the six named
numeric assertion changes, while the other 122 paths remain byte-identical.

Provider-native `source_sentiment` and investor `risk_score` are not the retired
ArkScope 1-5 score. The new boundary test must prove they remain available and
must not erase them through a broad text replacement.

## 2. Exact node ledger

### 2.1 Backend base, RED, and final identities

All streams are UTF-8 node IDs, unique, sorted by byte order, with one trailing
newline. They are derived from the deterministic reporter, never terminal prose.

| State | Nodes | SHA-256 |
|---|---:|---|
| rebased reviewed base | 4,527 | `4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d` |
| RED tests added, old nodes retained | 4,545 | `e1fa3f7d54d671c984e9800e38850ccb802f06f83d78aa2114b749bb7414f9da` |
| final target | 4,282 | `281cad976a2df29224f41d7442f39ee6deb5b78165fb9efe3945bee6d520abe3` |

Arithmetic: `4527 + 18 - 263 = 4282`. The 263-node retired stream is
`93459510fc09e961b0d726527d953ed6fdfd07c584d598ee1de9a60851ca3eda`.
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
| `tests/test_backtest_enhanced.py` | 18 |
| `tests/test_env_extra_features.py` | 16 |
| `tests/test_feature_engineering.py` | 36 |
| `tests/test_inference_offline.py` | 4 |
| `tests/test_integration_pipeline.py` | 4 |
| `tests/test_live_features.py` | 8 |
| `tests/test_state_parity.py` | 4 |
| `tests/test_train_utils.py` | 19 |
| `tests/test_analysis_pipeline.py` | 12 |
| **Total** | **223** |

### 2.3 Mixed-file retired nodes

The remaining 40 IDs leave without deleting their containing files:

```text
tests/test_api.py::TestNewsEndpoints::test_get_news_sentiment
tests/test_api.py::TestAnalysisEndpoint::test_analysis_run_disabled_by_default
tests/test_api.py::TestAnalysisEndpoint::test_analysis_run_enabled
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
tests/test_service_api_slice.py::TestServiceJobs::test_run_analysis_watchlist_batch
tests/test_job_runs.py::test_summarize_analysis_pipeline_result
tests/test_tools.py::TestNewsTools::test_get_news_sentiment_summary
tests/test_tools.py::TestSignalTools::test_detect_anomalies
tests/test_tools.py::TestSignalTools::test_detect_event_chains
tests/test_tools.py::TestSignalTools::test_synthesize_signal
```

The original score/signal ledger has two canonical skips in the blank
environment:

- `TestNewsDB::test_query_news_scored_only` is skipped by the existing
  `requires_db` marker;
- `test_contributions_sum_to_composite_score` in the retired factor file skips
  when the empty fixture emits no factors.

The training-only files were separately executed as `101 passed / 8 skipped`.
All 16 additional Phase D retirements are passing base nodes. Therefore the
combined final native target is `4253 passed / 29 skipped / 0 failed`, not an
inferred pass total.

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
| training lineage retirement | 4,418 | `284db7fe2fac55bb84ea2bfed4b68a9a566b303b132dda0aaabcfd440978cd56` | `+0/-109` |
| storage/writer/root | 4,374 | `fcd8775f6255b780c68cb0a943031d49b8f357dd2dcd6da1c8def2af268c19bf` | `+2/-46` |
| raw DTO/backend | 4,335 | `c6a074a3649b515216402b1b868eb588f57f873474f8b5a15934fcaea48c0d95` | `+4/-43` |
| raw user behavior | 4,335 | `d17b58f518fb48be84087c6c9169a7738baa478be3d55fac6156449fdc366835` | `+1/-1` |
| volume/event/composite/Phase D | 4,279 | `7ed812b25be6c29d74d9d3b311d105c218d5eca19b386efa936ae612f291352d` | `+5/-61` |
| model/API/authority/census final | 4,282 | `281cad976a2df29224f41d7442f39ee6deb5b78165fb9efe3945bee6d520abe3` | `+6/-3` |

### 2.6 Backend focused identities

| State | Nodes | SHA-256 |
|---|---:|---|
| base | 555 | `ea5d897ca3597ef4edca7583db0b363360ceba9e362e516422f901ff8af004dd` |
| RED additions present | 573 | `5e0a5538c4106ca9b9cf0d701ab719d62c3a4056d1e101864ddb09b6beb9fb75` |
| final | 421 | `385d0ac7a142ba1cb488a1dccd3d1a7ae8e2065585b59130f4b3bf75120a2739` |

### 2.7 Frontend identities

Use only the pinned JSON-decoding normalizer from section 0.4. Raw JSON text,
terminal output, `jq @tsv`, or prose parsing is not an identity authority.

| State | Files / nodes | SHA-256 |
|---|---:|---|
| full base | `98 / 1123` | `9262d7b15a926d7eeb60952e4c351c6c9b944772904fdb82438c62a2a51f6c1c` |
| full target | `99 / 1124` | `da69a2942c03e4794e3384e6125936f9f25c1fafbad7d006b67025f8fd97bc39` |
| focused base | `3 / 27` | `c77d25d5bf7c868899d555f099fc245b13d35d4052a6a8242ac3f5c1300fb584` |
| focused target | `4 / 28` | `b11cc27b90c570b20aeb728c48d39497e7eff555976f0c00a42d6129b26cf1cd` |

The sole addition is:

```text
src/legacyScoreRetirement.test.ts<TAB>legacy score retirement boundary > removes score fields from current frontend DTOs and fixtures
```

Its one-row stream SHA is
`6ee13afa0a184c2de613001edd698a99f3fa24516e69fa8600625c3860088e62`.

### 2.8 Retained IDs whose assertions evolve

These original 33 base IDs remain present exactly once. Their assertions evolve with the
approved behavior rather than disappearing under the net node count:

```text
tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news
tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count
tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names
tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count
tests/test_api.py::TestConfigEndpoints::test_morning_brief
tests/test_api.py::TestConfigEndpoints::test_overview
tests/test_api.py::TestConfigEndpoints::test_watchlist
tests/test_api.py::TestNewsEndpoints::test_search_news
tests/test_eir006_retired_data_boundaries.py::test_current_docs_training_and_tool_copy_name_only_current_authorities
tests/test_eir006_retired_data_boundaries.py::test_current_runtime_consumer_census_is_closed_and_exact
tests/test_evidence_packet.py::test_news_rows_are_whitelisted_fields_only
tests/test_evidence_packet.py::test_no_llm_scores_anywhere_in_packet
tests/test_job_runs.py::test_list_jobs_status_falls_back_when_db_error
tests/test_job_runs.py::test_list_jobs_status_uses_db_latest_when_available
tests/test_job_runs.py::test_local_store_create_finish_and_latest
tests/test_job_runs.py::test_run_job_continues_when_create_run_returns_none
tests/test_job_runs.py::test_run_job_persists_failure
tests/test_job_runs.py::test_run_job_persists_start_and_finish_on_success
tests/test_job_runs.py::test_summarize_handles_non_dict
tests/test_monitor.py::TestMonitorEngine::test_scan_once_records_watcher_metrics
tests/test_monitor.py::TestMonitorEngine::test_scan_once_returns_alerts
tests/test_monitor.py::TestMonitorToolRegistration::test_scan_alerts_registered
tests/test_profile_state.py::test_legacy_overview_enriches_but_never_qualifies_universe
tests/test_service_api_slice.py::TestJobsRoutes::test_jobs_status_route_returns_count
tests/test_service_api_slice.py::TestServiceJobs::test_list_jobs_status_includes_external_and_flagged_jobs
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
`d9cf7a2826d24f72aeb7db840d19bdb979d077e64b23fdf23ccaa79e2e16f67b`.
Section 0.9 adds ten shared registry-count owners without changing collection
identity. The complete 43-node retained/evolved stream is
`7e4f4d2b5290f47c368227223a558043a040304eb6a042af5519e0207a91ed54`.
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

### 3.5 Phase D and PostgreSQL source boundaries

- The full recommendation-shaped `src/analysis/` scaffold, `/analysis/run`,
  `analysis_watchlist_batch`, `/analyze`, `/analyze-save`, and
  `analysis_pipeline.enabled` configuration leave together.
- Generic report history and job-run persistence remain; tests that used the
  retired job only as sample data move to a current job fixture without losing
  their existing node identities.
- No compatibility module, disabled feature flag, permanent unavailable route,
  or half-package remains for future analysis.
- `sql/002_add_news_scores.sql` is absent. `sql/001_init_schema.sql` retains
  unrelated raw-news/price/fundamentals/query-log definitions but creates no
  score columns, `signals` table/index, or sentiment-summary helper.
- Future on-demand analysis and Signals restart under new reviewed semantics;
  this cutover does not implement either replacement.

## 4. RED and mutation discipline

### 4.1 RED-first rules

Create all 18 backend nodes and the one frontend node before product edits.
Imports of future symbols must occur inside test bodies or use explicit
`getattr`/route/schema assertions so collection remains clean. Every node must
fail for its intended missing/legacy contract. SQLite setup errors, missing
empty `data/`, fixture import errors, or unavailable test tooling are wrong RED.

The RED collection identities are `4545/e1fa3f7d...`,
`573/5e0a5538...`, and frontend `1124/da69a294...`. Runtime RED evidence names
each node and expected assertion. A broad static grep alone is not sufficient
for behavior contracts.

### 4.2 Required mutation cycles

After GREEN, apply each mutation only to its owning node, save the exact diff,
prove RED for the intended reason, restore the pre-mutation blob, and prove the
restored SHA before the next cycle.

| ID | Mutation | Owning witness |
|---|---|---|
| M1 | re-add fresh score storage/columns, `signals` DDL, or sentiment helper to either current schema owner | fresh-schema boundary |
| M2 | re-add `scored_only` or a legacy field to the raw backend/DTO contract | raw backend + ordinary DTO nodes |
| M3 | make morning brief depend on scored rows or reverse its deterministic tie order | two morning-brief behavior nodes (existing positive plus new tie node) |
| M4 | restore `sentiment_mean`/`bullish_ratio` to profile or frontend DTOs | backend ordinary contract + frontend boundary |
| M5 | restore the old watcher/tool namespace, compatibility export, or sentiment branch | NewsVolumeWatcher/news-event tool nodes |
| M6 | restore `fillna(3.0)`, numeric `impact_score`, event sentiment impact, or scorer-oriented tag prompt | news-analytics event-chain exact-payload owner |
| M7 | restore a `/signals` or `/analysis/run` route, the retired Phase D job/CLI/config/package, composite tool, bridge schema, or prompt claim | API absence + model-visible/current-owner census |
| M8 | restore a score writer/import executable | runtime writer census + scripts absence |
| M9 | restore legacy sentiment fields to `MERGE_FIELDS` | collision projection node |
| M10 | restore a current-authority claim that scoring/composite is available | current-authority node |
| M11 | restore exact base bytes for `training/__init__.py` or the yfinance requirement/smoke | training-retirement structural census + current-authority boundary |

M2, M7, M8, and M11 must mutate the real shared owner, not add a dead condition
after an empty target set. M11 must restore an exact base artifact, not merely
insert the word `training` in unrelated prose. Mutation diffs are review
artifacts; running the full suite for each mutation is forbidden because it
adds cost without discrimination.

## 5. Tasks

### Task 0 - Re-ground identities and protected state

1. Verify branch ancestry from current base `814ef2ed` through rebased authority
   tip `f9958efb`; verify the one-time mapping in section 0.5 and require that
   this plan, evidence, and priority entry are the only amendment changes.
2. Verify all pinned assets in section 0.4 by full SHA, not prefix matching.
3. Collect backend full/focused base streams and frontend full/focused base
   streams. Require exact section 2 identities.
4. Reconstruct retired/addition/projection streams independently from the named
   IDs. Require all counts and SHA values in section 2.
5. Run the backend focused base suite and the current frontend focused suite.
   Any non-passing node stops the line.
6. Run native canonical base admission under section 0.4 and require
   `4527 seen / 4488 passed / 39 skipped / 0 failed`.
7. In read-only SQLite URI mode plus `PRAGMA query_only=ON`, record table
   existence, exact current score-row count, min/max article date and scored-at,
   and DB identity. The reviewed 491,808 count is a dated expectation, not a
   value to force.
8. For `config/scoring_keys.txt`, record only path existence, mode, inode, and
   mtime. Do not read, hash, print, copy, or record content/size.
9. Build the exact owned-path and protected-path blob manifests. Require the
   62-path training deletion stream and 109-node training-family stream in
   section 0.7, plus the 21-path Phase D/PostgreSQL direct-deletion stream and
   16-node retirement stream in section 0.8. Prove the eight named
   training-only package families (nine requirement lines because `torch` is
   duplicated), including yfinance, have no surviving Python owner, while
   `scipy` retains its option-pricing owner. Prove every `src/analysis/`, route,
   job, CLI, config, current-copy, SQL, and shared test owner has exactly the
   disposition in sections 0.8 and 3.5.
10. Record Task 0 evidence, commit docs only, and stop for independent review.

No RED test or product byte may be changed in Task 0.

### Task 1 - Establish RED across every approved surface

1. Add `tests/test_legacy_score_retirement.py` with the eight exact IDs in
   section 2.4. The existing fresh-schema and API/model/current-authority
   boundary IDs also own the PostgreSQL and complete Phase D absence contracts;
   do not create unaccounted extra node names.
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

Complete all six phases before any claim of GREEN:

0. **Training lineage:** delete the exact 62-path stream: all 53 tracked
   `training/` files, eight implementation-only test files, and the manual
   yfinance smoke. Remove the smoke README entry, `trained_models/` ignore and
   unread config hint, and only the ownerless requirement entries named in
   section 0.7. Rewrite current authorities to state that the implementation is
   retired and recoverable from Git history; do not create an archive copy,
   branch, tag, placeholder, or replacement scaffold.
1. **Storage/writer/root:** delete all nine `scripts/` paths, the score importer,
   the now-consumerless `src/news_normalized/score_migration.py` planner,
   executable `sql/002_add_news_scores.sql`, and writer-only key/API helpers;
   remove the daily-update tombstone; evolve `sql/001_init_schema.sql` so fresh
   PostgreSQL setup creates no old score columns, `signals` table/index, or
   sentiment-summary helper; stop fresh SQLite score-table creation; and remove
   the corresponding 46 test IDs while adding the two storage/root boundaries.
2. **Raw DTO/backend:** remove score fields/parameters/projection/aggregation
   across schemas, DAL, all backends, and identity merge;
   remove 43 old IDs and add four raw/provenance boundaries.
3. **Raw user behavior:** remove the sentiment summary contract, rebuild morning
   brief from one raw batch, remove hidden profile/frontend sentiment fields,
   remove one old node, and add the deterministic tie node.
4. **Volume/event/composite/Phase D:** move approved raw-volume/title-event/sequence
   behavior into `src/news_analytics.py` plus
   `src/tools/news_event_tools.py`; delete the complete `src/signals/` and
   `src/tools/signal_tools.py` namespaces without re-export; delete all 18
   `src/analysis/` paths and its API route; remove the Phase D route registration,
   scheduled job, CLI/config/current-copy owners; evolve event chains to exact
   typed unavailable impact; remove composite/rank/router/strategy/watcher/Phase
   D owners and 61 old nodes; preserve generic job/report infrastructure with
   current fixtures; and add five news-volume/event owners.
5. **Model/API/authority/census:** remove the final sentiment route and all dead
   model-visible claims, update only the bounded EvidencePacket retirement copy,
   reconcile current authorities, add fail-closed runtime census/API/model/
   current-doc nodes, replace the two stale bridge count IDs, and remove the
   final old route node (`+6/-3`).

After all six phases, evolve only the ten stale shared registry-count
assertions in section 0.9 to registry `50`, bridge `51`, and news category `11`.
This is part of the same atomic commit and changes no node identity.

During these phases, reconstruct each projected node stream in section 2.5 from
the ledger. Do not treat an intermediate projection as a test baseline. At the
end require exact backend `4282/281cad97...`, focused `421/385d0ac7...`,
frontend `99/1124/da69a294...`, and focused frontend `4/28/b11cc27b...`.

The runtime census must be structured and fail closed. Every discovered
consumer/writer/current-authority path receives exactly one disposition:
`retired`, `raw_preserved`, `provider_native_protected`,
`historical_only`, or `current_authority_rewritten`. Unknown, duplicate, or
unclassified paths fail. Run it in an unlocked tree or explicitly enumerate
git-crypt files as unsearchable-by-content and classify by path.

Commit the complete product/test/current-authority cutover as one atomic commit.
No production data or secret byte belongs in the commit. The exact subject is:

```text
refactor: retire legacy scoring and training lineage
```

The body must state all of the following facts; a generic `cleanup`, `old code`,
or path-only message is a stop condition:

- the disconnected offline RL implementation, its eight dedicated test owners,
  and manual yfinance smoke leave as the exact 62-path training family;
- total backend retirement is exact 263 nodes, comprising 109 training-only,
  138 legacy score/signal, and 16 recommendation-shaped Phase D nodes, with 18
  replacement contract nodes;
- raw news, news volume/event sequences, provider-native sentiment, investor
  risk, and current caller-supplied options pricing remain;
- future RL, Signals, or provider-backed options estimation starts from a new
  reviewed design and current data/provider contracts, not restored compatibility
  code; and
- production `news_article_scores` remained read-only and unchanged, while
  `config/scoring_keys.txt` contents were not read, copied, changed, or deleted
  by this commit.

### Task 3 - Prove focused GREEN and mutation sensitivity

1. Run the 421-node backend focused suite. Existing allowed skips must be named;
   all other nodes pass.
2. Run frontend focused `28/28`, full Vitest `1124/1124`, typecheck, build, and
   the current i18n scanner.
3. Run existing raw-news, normalized-news, Seeking Alpha, provider-native
   sentiment, investor-risk, EvidencePacket, profile, and monitor protection
   suites. Require all ten section 0.9 shared registry owners GREEN and verify
   that the other assertions in those files remain unchanged.
4. Execute M1-M11 exactly as section 4.2. Record diff SHA, owning-node RED,
   pre/post blob SHA, and restored GREEN for every cycle.
5. Re-run the structured runtime census and require zero retired consumer or
   writer and zero unknown classifications.
6. Recheck production score rows read-only and secret metadata-only. Require no
   product-cutover mutation.

### Task 4 - Canonical native admission

1. Create a fresh exact-tip detached worktree with the section 0.4 boundary.
2. Run the wakeup probe in that same native context.
3. Collect exact backend target `4282/281cad97...` and frontend target
   `1124/da69a294...` before runtime.
4. Run the native suite through the pinned wrapper/reporter. Require all 4,282
   collected nodes seen, empty non-passing stream, exit zero, and
   `4253 passed / 29 skipped / 0 failed`.
5. Record every generated path, quarantine exact paths, and restore pre-run
   ordinary/ignored/data/src-data/symlink/toolchain boundaries byte-for-byte.
6. Prove protected-path manifests and production read-only witnesses unchanged.
7. Complete implementation evidence and stop before merge for independent
   implementation review.

### Task 5 - Independent review and fast-forward merge

The reviewer reconstructs, rather than trusts prose:

- all backend/frontend base, RED, projected, focused, and final streams;
- exact `+18/-263` and frontend `+1/-0` node identities;
- the 223 whole-file and 40 mixed-file retirements;
- all 18 backend additions and the frontend addition;
- M1-M11 diffs, RED reasons, and restored blob SHAs;
- structured consumer/writer/current-authority census;
- native report, empty non-passing set, and artifact transaction;
- exact absence of the 62-path training family, its ownerless dependency/config
  tail, and any archive/compatibility copy; exact absence of the 21-path Phase
  D/PostgreSQL direct-deletion family plus every route/job/CLI/config/current-copy
  tail; exact PostgreSQL survivor projection; protected provider-native bytes
  plus the exact EvidencePacket copy delta and unchanged negative-contract
  behavior; and
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
   advertisement, legacy `src/signals/`, `src/tools/signal_tools.py`, or
   `src/news_normalized/score_migration.py` survivor, any `src/analysis/` path,
   `/analysis/run`, Phase D job/CLI/config/current-copy survivor, compatibility
   re-export, or old `TestSignalTools` namespace is proposed;
6. raw news, morning brief, profile counts, volume detection, or event sequence
   is removed rather than evolved as approved;
7. provider-native sentiment or investor risk is mistaken for the retired
   ArkScope score and removed;
8. the current composite/rank/recommendation or Phase D recommendation scaffold
   survives under another name;
9. a future Signals semantic is implemented without its separate evidence gate;
10. any scorer/model/provider/scheduler/network request is added or triggered by
    this implementation;
11. production `news_article_scores` is written, deleted, migrated, vacuumed, or
    used as a new acceptance fixture;
12. `config/scoring_keys.txt` contents, bytes, digest, size, or secret values are
    read or recorded;
13. a deletion manifest is built before product merge and read-only rollout;
14. a `training/` path, training-only test, yfinance smoke, ownerless training
    dependency/config hint, archive copy, preservation branch instruction, or
    compatibility import survives; normalized raw news, Seeking Alpha, OAuth,
    or a protected collector changes outside reviewed scope; or EvidencePacket
    changes beyond the exact retirement-copy delta while its projection/gather
    logic is not byte-identical;
15. the runtime census has an unknown, duplicate, or unclassified path;
16. the census relies only on locked git-crypt ciphertext without explicit path
    classification;
17. a mutation changes a dead branch or fails to turn its owning node RED;
18. a mutation restore does not reproduce the exact pre-mutation blob;
19. frontend identity is parsed from escaped JSON text or terminal prose;
20. native wakeup preflight fails or full admission runs in the managed sandbox;
21. full admission does not see every collected node or has any non-passing ID;
22. the atomic deletion commit lacks the exact subject or any required body fact
    in Task 2, or describes the change only as generic cleanup;
23. a test run modifies a pre-existing repository-relative file;
24. an artifact cannot be restored by exact path without touching production;
25. merge is non-fast-forward, contains an unexpected commit, or would push; or
26. OAuth and Tranche B edit the same owner without an explicit reviewed handoff.

The cutover also stops if `sql/002_add_news_scores.sql` survives, or if
`sql/001_init_schema.sql` still creates a news score column/storage owner,
`signals` table/index, or sentiment-summary helper, or loses an unrelated
raw-news, price, fundamentals, query-log, or retained helper definition.

## 7. Completion criteria

The product cutover is complete only when:

- PD 1-8 behavior is live from merged master;
- backend is exactly `4282/281cad97...`, frontend exactly
  `1124/da69a294...`, and native admission is `4253/29/0`;
- no runtime reader/writer/model-visible/current-authority path exposes the old
  score or composite semantic;
- `src/signals/` and `src/tools/signal_tools.py` are physically absent, their
  approved surviving behavior is owned only by the new news analytics/tool
  modules, and no compatibility import or re-export remains;
- the complete recommendation-shaped Phase D package, route, scheduled job,
  CLI/config/current-copy surface, and executable score migration are absent;
  the retained PostgreSQL schema creates none of their legacy storage or helper
  contracts while preserving unrelated schema owners;
- raw news, morning brief, profile counts, volume, and event sequence contracts
  remain green;
- the 62-path training family and its ownerless dependency/config/current-copy
  tail are absent with no archive/compatibility copy; protected provider-native
  boundaries are unchanged and EvidencePacket differs only by the reviewed
  retirement copy while preserving its negative contract;
- production score rows and scoring secret are still physically untouched; and
- later data/secret disposition remains explicitly blocked behind its own exact
  reviewed authority and user approval.
