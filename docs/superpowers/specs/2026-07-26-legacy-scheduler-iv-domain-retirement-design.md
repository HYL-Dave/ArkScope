# Legacy Scheduler Sources and IV Domain Retirement Design

> **Status: LIVE COMPLETE - PRODUCTION RETIREMENT APPLIED 2026-07-27**
>
> Written against clean `master` tip `16d77bae` on 2026-07-26. This document
> authorizes no product edit, migration, provider call, or production write.
> Independent full-document review returned GREEN after the accounting and
> ownership amendments through `7bb7cc29`. The RED-first implementation plan
> is `docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md`;
> independent plan review is GREEN after two docs-only corrections. The
> implementation review returned GREEN with no product findings after the two
> evidence-index corrections in `28b136d1`. `master` fast-forwarded to that
> exact reviewed tip on 2026-07-27. Plan clearance is
> `5f528475420c8de407125bceb32d94050cfa8e14`. With ArkScope and all writers
> stopped, merged code produced reviewed preview
> `0ed0916d2cd165574e7ddbce1dbefe755526ced0aa105e82db34d452814aca0b`;
> the user then explicitly approved that exact manifest. Archive/apply,
> idempotent second apply, database health/digest checks, retained-option gates,
> restart, and UI smoke all completed. The rollback archive is
> `data/backups/legacy_scheduler_iv_retirement_20260727T123347933126Z/`
> (manifest SHA-256
> `30c01ea8fd009a3d47c5ac96ffd4dd9b0282a1adef03faafb91c3dd50dd92fad`).

## 1. Purpose And Authority

ArkScope currently exposes three scheduler identities that no longer perform a
real operation:

- `price_backfill` is a Coverage-v2 read-only tombstone;
- `local_incremental` is the retired PostgreSQL-to-local mirror identity; and
- `iv_history` is the retired ATM-IV PostgreSQL-mirror collector.

Keeping these identities in the schedule catalog makes the catalog claim that
ArkScope owns capabilities it does not provide. Hiding or disabling their
controls is not sufficient. The identities, dead execution paths, and dead UI
copy must leave the active product catalog.

The old `iv_history` name also identifies a broader legacy data domain that is
still read by Ticker Detail, APIs, provider health, evidence packets, and agent
tools. Its current data is a stale and incomplete 24-row snapshot duplicated in
SQLite and Parquet. Removing only the scheduler row or only the 24 SQLite rows
would leave an empty or misleading product surface. This design therefore
retires the complete old IV domain while preserving independent option math and
live option-chain capabilities.

Authority order is:

1. this document owns retirement scope, two-tranche attribution, production
   archive/cutover semantics, and the permanent retirement of the three source
   IDs;
2. `IV_PROVIDER_PROOF_PACKET_PLAN.md` owns the future provider-neutral IV proof
   packet and schema hypothesis;
3. `PG_EXIT_REMAINDER_SCOPING.md` owns the historical PG-exit record;
4. `job_runs` remains the historical execution authority; and
5. a future IV slice must choose new semantic IDs and a new schema through its
   own reviewed design. It may not revive this legacy contract by name.

### 1.1 Corrections to prior reasoning

Two prior arguments are explicitly retired:

1. Current `_SOURCE_PROVIDER_CONFIG` does **not** map `price_backfill` to IBKR.
   The identity was historically IBKR-bound, but merged Coverage v2 already
   severed that mapping. Current facts must not be inferred from a pre-merge
   commit.
2. A dead source ID does not need to be freed for reuse. Reusing it would mix a
   new meaning with old telemetry. The ID must instead remain permanently
   retired. The sufficient reason to remove it from `SOURCES` is that the
   active catalog must not advertise an unavailable capability.

### 1.2 Current scheduler ground truth

At the design base, `SOURCES` contains seven entries. Four are active direct
collection identities:

- `polygon_news`;
- `finnhub_news`;
- `ibkr_news`; and
- `ibkr_prices`.

Three are retirement artifacts:

- `iv_history` carries dead `sync_flag="--iv"` configuration and is rejected
  through `_N9_RETIRED_SOURCES`;
- `local_incremental` carries `source_mode="retired_pg_mirror"` and has no
  executor; and
- `price_backfill` carries `coverage_repair_disabled=True`, reports
  `write_target="none"`, and executes only a deliberate no-op/legacy rejection
  state machine.

The remaining active source set has no need for a three-value
`scheduled/read_only/retired` control mode. Every shipped row is schedulable;
unknown or permanently retired IDs must be rejected as unknown rather than
rendered as product rows.

`src.daily_update` still exposes `--iv-history` and `--sync-db`, even though the
IV source and all PG mirror writes are retired. `src.prices_runtime` still
accepts a `--source` selector whose choices include `price_backfill`, although
the worker has one real caller identity and does not use the argument to choose
behavior.

### 1.3 Dated production observations

A read-only inspection at `2026-07-26T21:25:40+08:00` found:

- `job_runs` has no foreign keys and stores `job_name` as plain text;
- `collect.local_incremental` has 1,350 `succeeded` rows;
- `collect.price_backfill` has 2 `failed` rows;
- `collect.iv_history` has 0 rows;
- `scheduler_state` has one historical `local_incremental` row and one blank
  `price_backfill` row;
- `profile_settings` has one dead
  `schedule.local_incremental.enabled=false` preference;
- `market_sync_meta` has one `domain='iv'` row with last success
  `2026-07-03T00:14:04+00:00` and `rows_added=0`;
- `market_data.db.iv_history` has 24 rows, 4 tickers, minimum ID 1, maximum ID
  248, non-contiguous IDs
  `1-11,27,32,36,70,76,81,190,197,203,211,233,241,248`, and dates
  `2026-01-30..2026-03-06`;
- ticker counts are AMD 9, NVDA 8, PLTR 1, and PYPL 6; and
- four files under `data/options/iv_history/` contain 9/8/1/6 rows and are
  value-for-value identical to the 24 SQLite rows.

These are dated observations, not acceptance constants. Preview must rederive
all counts, rows, paths, and hashes immediately before any cutover. A changed
shape is a stop condition, not permission to broaden a delete query.

The historical `job_runs` rows are not dead runtime state. They truthfully
record prior operations and remain untouched. `scheduler_state`, dead schedule
preferences, the IV sync cursor, and duplicated IV snapshots are current-state
artifacts and may be archived then removed.

### 1.4 The legacy IV domain is still active at read time

The old 24-row shape is not isolated to one table. Current production code
still exposes it through:

- `GET /options/{ticker}` and `GET /options/{ticker}/history`;
- `GET /scan/mispricing`;
- Ticker Detail's IV summary, source, local-coverage row, and history table;
- `MarketDataStatus.iv`, `MarketDataStatus.sync.iv`, and ticker coverage `iv`;
- `/health.data_sources.iv_tickers`;
- the IBKR provider-health `iv_latest` signal;
- `DataAccessLayer.get_iv_history()` and all file/local/SQLite/PG backend
  protocol implementations;
- `get_iv_analysis`, `get_iv_history_data`, and the DAL-backed
  `scan_mispricing` tool;
- OpenAI and Anthropic hand-written tool bridges plus the central registry;
- the dedicated IV-history compressor reducer;
- the `iv_environment` evidence-packet section used by AI Card;
- `analysis_tools`' opt-in `latest_iv/latest_vrp` path;
- `scripts/analysis/compare_bs_vs_american.py`, which calls
  `DataAccessLayer.get_iv_history()`, plus
  `scripts/analysis/scan_option_mispricing.py`, which bypasses the DAL and
  reads `data/options/iv_history/{ticker}.parquet` directly; and
- legacy local-market bootstrap, validation, checksum, and incremental mirror
  machinery.

Deleting only the rows would make these surfaces return honest-empty data but
would still claim that the capability exists. This design removes the contract,
not merely its current observations.

### 1.5 Future IV work is already recorded

The future direction is not lost by retirement:

- `IV_PROVIDER_PROOF_PACKET_PLAN.md` explicitly says the old 24-row PG
  `iv_history` remains a drop candidate;
- its schema hypothesis is a provider-neutral raw snapshot with explicit
  provider, endpoint, snapshot time, granularity, timestamp semantics, raw
  payload reference, confidence, and status fields;
- `PG_EXIT_REMAINDER_SCOPING.md` keeps S-D provider-neutral schema design and
  S-E small-scope IBKR computed-IV prototyping separate; and
- the priority map keeps paid/provider IV work gated by a written hypothesis,
  out-of-sample plan, kill criteria, and cost-versus-value evidence.

This retirement does not select a future provider, metric definition,
granularity, scheduler identity, storage schema, or UI.

## 2. Locked Decisions

1. **Full retirement, not concealment.** Remove all three identities from the
   active schedule catalog and remove the complete legacy IV read domain.
2. **Two independently reviewed tranches.** Tranche 1 owns scheduler identity
   retirement. Tranche 2 owns the old IV domain and production data cutover.
3. **Named checkpoint.** Tranche 1 ends at a full 40-character commit recorded
   as `TRANCHE_1_TIP`. Final review compares base to `TRANCHE_1_TIP`, then
   `TRANCHE_1_TIP` to final.
4. **Historical telemetry stays.** All `job_runs` rows remain byte-for-byte
   unchanged. No Settings archive row is added; `/jobs` remains the history
   access path.
5. **Operational tombstones leave current state.** Dead `scheduler_state`,
   schedule preference, and `market_sync_meta.domain='iv'` rows are archived
   and removed during final cutover.
6. **Permanent source-ID retirement.** `price_backfill`,
   `local_incremental`, and scheduler ID `iv_history` may not re-enter
   `SOURCES`, schedule routes, or future collector definitions.
7. **Future IV receives new identities.** A future schema/tool/source name is
   chosen only after its semantics are locked. Generic mathematical parameter
   names such as `iv_history` are not prohibited; reusing the retired runtime
   source/tool/table contract is prohibited.
8. **No compatibility rows.** `/schedule` returns only the four active
   sources. Old IDs receive the ordinary unknown-source response; they do not
   receive a special retired placeholder.
9. **No compatibility API shell for IV.** The old analysis/history/mispricing
   routes are removed rather than returning an empty success payload.
10. **Keep independent options capability.** Preserve `calculate_greeks`,
    `get_option_chain`, `get_iv_skew_analysis`, `src.options_math`, and the
    standalone live/pure option-analysis scripts that do not read the legacy
    IV store.
11. **Remove three DAL-backed agent tools.** Retire `get_iv_analysis`,
    `get_iv_history_data`, and the legacy DAL-backed `scan_mispricing` from the
    registry and both provider bridges.
12. **Remove stale AI evidence.** AI Card evidence no longer emits or reports
    a missing `iv_environment` leg. A capability that has been retired is not
    a failed evidence source.
13. **No active duplicate store.** Both the SQLite table and the four active
    Parquet files leave runtime paths after a restore-ready archive is made.
14. **No full market DB copy required.** The target table is archived as a
    restore-ready mini SQLite database plus exact Parquet copies. Transactional
    DDL and non-target logical digests protect the 3.3 GB market database.
15. **Fresh installations do not recreate the legacy domain.** Remove legacy
    DDL and bootstrap/incremental code from current schemas and runtime admin
    paths.
16. **Historical migration artifacts remain historical.** N9 drop scripts,
    evidence, and dated decision-log entries are not rewritten merely to reach
    a repository-wide zero-string count.
17. **No provider or PG action.** Implementation and cutover are local code,
    local SQLite, and local file operations only.
18. **No future-IV placeholder.** Do not replace the old panel with "coming
    soon", a disabled source, or speculative provider controls.
19. **Historical market payload stays.** Do not delete prices, news,
    fundamentals, or other current local-authority rows merely because
    `local_incremental` may once have written them. Those rows are not a
    separable dead domain and remain product data.
20. **Retire the price-backfill identity, not the shared price primitive.**
    Remove the redundant `prices_runtime --source` selector and scheduler
    tombstone, but retain `backfill_prices_direct()` and active price-writer
    behavior used by `ibkr_prices`.
21. **Surviving diagnostics shed only the old IV dimension.**
    `check_data_freshness` and `get_ticker_data_coverage` remain registered
    tools. Their old `iv_history`/`iv` facts, prose, thresholds, and backend
    queries leave with the legacy store; their live price/news/fundamentals
    behavior remains.
22. **Retire the two old-store analysis scripts.** Remove
    `compare_bs_vs_american.py` and `scan_option_mispricing.py` rather than
    adapting an about-to-retire scripts surface to a new IV input. The reusable
    option math and its tests remain in `src/options_math`; no replacement CLI
    is created. This specifically supersedes the B6 survivor-table ruling for
    these two files only. `scan_unusual_activity.py` and every other entry in
    the scripts disposition remain unchanged; broader scripts retirement is a
    separate bounded line.

## 3. Scope

### 3.1 Tranche 1: scheduler identities

In scope:

- remove the three `SourceDef` entries and all catalog metadata unique to
  them;
- reduce the shipped schedule catalog from seven IDs to exactly four;
- remove read-only/retired schedule control modes and always-false DTO fields;
- remove price-backfill no-op and legacy-unproven-gap scheduler branches;
- remove retired-source execution guards whose only consumers were these
  rows;
- remove dead PG-mirror refresh/sync wiring from the scheduler;
- remove `--iv-history` and `--sync-db` from `daily_update`;
- remove the redundant `prices_runtime --source` selector rather than leaving
  a one-choice argument;
- remove the three frontend schedule mappings, read-only/retired rendering,
  and their resource leaves; and
- add permanent absence gates for the three source IDs.

Out of scope for Tranche 1:

- production writes or deletion of state rows;
- deletion or rewriting of any market payload historically produced by
  `local_incremental`;
- any legacy IV API, table, Parquet, tool, or Ticker Detail change;
- any tool-count change; and
- any future IV design.

### 3.2 Tranche 2: legacy IV domain and cutover

In scope:

- remove the old IV table/files, schema, DAL/backend protocol, API, UI,
  health/status, evidence, and agent-tool surfaces;
- remove the two analysis scripts that consume the old DAL/Parquet store;
- remove obsolete all-domain PG mirror bootstrap/validate/incremental code and
  public retired endpoints that no current caller uses;
- remove the old IV sync-meta shape from current status DTOs;
- preserve and explicitly test independent option math/live-chain/skew
  capabilities;
- add an audited preview/archive/apply/restore migration tool;
- archive then remove dead profile/market operational state; and
- update current design docs without rewriting historical records.

Out of scope for Tranche 2:

- changing `job_runs` rows or retention;
- changing prices, news, fundamentals, financial cache, option-chain, Greeks,
  or skew data;
- deleting historical market rows based on which retired scheduler identity
  may once have written them;
- implementing a replacement IV schema/provider/collector;
- migrating old values into a future schema;
- treating old ATM IV, HV30, VRP, rank, or percentile values as seed data;
- changing Coverage v2's read-only session-truth model; and
- removing generic pure-math functions merely because a parameter is named
  `iv_history`.

## 4. Tranche And Review Mechanics

### 4.1 `TRANCHE_1_TIP`

Tranche 1 must finish in its own named commit. Evidence records:

- the 40-character commit hash as `TRANCHE_1_TIP`;
- backend and frontend node lists/counts/hashes for the tranche-owned suites;
- exact source-catalog response containing only four IDs;
- Settings and total resource counts;
- unchanged central/bridge tool counts;
- scanner counts and manifest hashes;
- static absence of the three IDs from active schedule/CLI/UI owners; and
- production DB/file size, mtime, and relevant row counts proving no data
  write occurred.

Tranche 2 may not rewrite Tranche-1-owned product files except through a
reviewed deviation that explains why the IV-domain retirement requires it.
Final review must run Tranche 1's focused suite again at final tip.

### 4.2 Canonical comparisons

Independent implementation review performs two comparisons:

1. design base `16d77bae` to `TRANCHE_1_TIP`; and
2. `TRANCHE_1_TIP` to final product/evidence tip.

One base-to-final total is supplementary. It cannot replace the two canonical
comparisons because a Tranche 2 deletion must not hide a Tranche 1 regression.

## 5. Tranche 1 Contract

### 5.1 Active source catalog

After Tranche 1, the source catalog is exactly:

```text
polygon_news
finnhub_news
ibkr_news
ibkr_prices
```

All four rows are normal scheduled sources. The schedule DTO no longer emits:

- `retired`;
- `retired_reason`; or
- `control_mode`.

`source_mode`, `write_target`, provider-fetch facts, badges, progress, durable
state, interval, and job name remain where they still distinguish active
sources.

PUT/run routes first validate exact catalog membership. Each retired ID returns
the existing unknown-source `404` path before profile writes, provider config,
Gateway locks, worker launch, or telemetry creation.

### 5.2 Scheduler simplification

Remove these obsolete concepts rather than preserving wrappers:

- `_N9_RETIRED_SOURCES` as an active routing owner;
- `ScheduleControlMode` and `source_control_mode()`;
- `SourceDef.coverage_repair_disabled`;
- legacy price-backfill result normalization and blank/legacy-state projection;
- the coverage-read-only execution branch;
- `_local_refresh()` and its scheduler-owned locks;
- `SourceDef.sync_flag` and the retired PG-sync rejection branch, but only
  after replacing their conditional fail-closed role with the exhaustive
  pre-provider boundary below;
- `run_source(..., skip_sync=...)`; and
- scheduled/manual branches whose only purpose was to distinguish no-op,
  retired, or mirror sources.

The active direct writers retain their existing lock, provider, continuation,
retry, telemetry, and local-write behavior. Removing the scheduler's obsolete
`local_refresh` owner must not remove or rename active market-write locks used
by direct collectors. Removing `price_backfill` also must not remove or alter
the provider-neutral `backfill_prices_direct()` primitive used by the active
`ibkr_prices` worker.

The `sync_flag` guard is unreachable for the current four `NewsWriteMode`
members, but it is not intrinsically dead: `BLOCKED` and `LEGACY_PG` fail
before collection, unsupported IBKR `LEGACY_LOCAL` fails before collection,
and the two permitted direct-local paths set `local_news_writer=true`. A future
unhandled mode could currently fall through to collection and be caught only
by the post-collect `sync_flag` guard. Therefore Tranche 1 must replace that
accidental protection with an explicit exhaustive mode classifier before any
provider call. `NORMALIZED`, `LEGACY_LOCAL`, `LEGACY_PG`, and `BLOCKED` each
have one named path; any unrecognized/future mode fails before provider,
worker, write, or telemetry work. A mutation test must prove that adding or
injecting a fifth mode cannot fall through to an adapter. Only then may the
stale `sync_flag` field and post-collect PG guard leave.

### 5.3 CLI and route contract

- `daily_update --all` continues to mean active news plus active prices.
- `--iv-history` is rejected by argparse because the option no longer exists.
- `--sync-db` is removed; direct-local writers already own persistence.
- `prices_runtime` accepts ticker/provider/lock inputs but no source selector.
- retired mirror bootstrap/update/validate endpoints are removed with the
  shared mirror implementation in Tranche 2, not replaced with a second UI.

### 5.4 Settings behavior

The schedule table renders four rows with ordinary enable, interval, and run
controls. It has no read-only or retired chips and no row for any retired ID.
Historical `job_runs` do not appear through a synthetic schedule row.

Unknown future source IDs continue through the existing generic display
fallback only if a newer backend returns one; that fallback is not used to
resurrect the three permanent retired IDs.

### 5.5 Tranche 1 resource delta

Contrary to the initial "zero resource effect" assumption, eight Settings
leaves per locale become dead and must be removed in Tranche 1:

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

With the current dated baseline, expected per-locale counts are:

| Point | Settings | Explore | Total |
|---|---:|---:|---:|
| Base | 714 | 401 | 1814 |
| `TRANCHE_1_TIP` | 706 | 401 | 1806 |

The implementation plan must rederive the base before edits and evolve the
existing resource-count node in place. Any extra leaf deletion is a stop and
amend condition.

### 5.6 Tranche 1 node accounting

The implementation plan must provide exact `+N/-M` arithmetic and list every
node ID. At minimum it must classify these existing contracts:

Evolve in place:

- `test_no_active_runtime_source_uses_migrate_to_supabase_sync` into an exact
  no-mirror-field/no-mirror-call boundary;
- `test_scheduler_source_defs_have_no_legacy_collector_plumbing` into the
  four-source catalog contract;
- `test_status_snapshot_provider_fetch_tracks_live_fetch_paths` for the four
  active rows;
- `test_run_now_choke_point_guards_scheduled_and_rejects_retired_sources` into
  exact unknown-ID rejection before writes/provider work;
- `maps all seven schedule source ids without backend labels` into an exact
  four-ID mapping node; and
- mounted Settings schedule tests into exactly four controlled rows.

Retire with the removed behavior:

- `test_run_source_iv_history_retired_before_provider_work`;
- `test_local_incremental_has_no_subprocess`;
- `test_price_backfill_source_registered`;
- `test_coverage_derived_price_backfill_is_deliberate_noop`;
- `test_blank_price_backfill_history_is_neutral_and_first_run_succeeds`;
- `test_status_or_continuation_only_price_backfill_state_fails_closed`;
- `test_error_or_result_only_price_backfill_state_fails_closed`;
- `test_local_incremental_retired_after_p0c`;
- `test_local_incremental_retirement_does_not_call_local_refresh`;
- `test_price_backfill_ignores_gateway_lock_but_keeps_source_lock`;
- `test_price_backfill_does_not_resolve_scope_for_deliberate_noop`; and
- `test_iv_history_opt_in_only`.

The plan must also census legacy `skip_sync`, local-refresh, and PG-mirror
nodes. It may evolve a node only if the surviving assertion still tests a live
property; deleting implementation while keeping a test name that claims the
old behavior is forbidden.

New durable boundaries must prove:

- exact four-source catalog membership;
- permanent IDs absent from schedule, CLI, and Settings owners;
- old IDs produce `404` with zero provider/write/worker calls;
- the four current `NewsWriteMode` values are exhaustive and an unknown mode
  fails before provider/adapter work; and
- all four remaining rows still execute through their existing paths.

Tranche 1 changes no registry or bridge tool count: central registry remains
56 and each provider bridge remains 57 at this checkpoint.

## 6. Tranche 2 Contract

### 6.1 Remove the old IV storage contract

Remove current runtime ownership of:

- SQLite table/index `iv_history` / `idx_iv_ticker_date`;
- `_IV_SCHEMA`, old PG selects/inserts/checksums, incremental domain `iv`, and
  local bootstrap/validation branches;
- `data/options/iv_history/*.parquet` as active files;
- SQLite/File/Local/DB backend `query_iv_history` implementations and protocol
  methods;
- `DataAccessLayer.get_iv_history()` and `get_iv_history_df()`;
- old available-ticker type `iv_history`; and
- current SQL initialization of the legacy PG table.

Current N9 migration scripts and their tests remain because they document and
verify a historical PG drop. They are not runtime or fresh-schema owners.

### 6.2 Remove old API and DTO contracts

Remove:

- `GET /options/{ticker}`;
- `GET /options/{ticker}/history`;
- `GET /scan/mispricing`;
- `IVAnalysisResult`, `IVHistoryPoint`, and the DAL-backed
  `MispricingResult` if no surviving consumer remains;
- frontend `IVAnalysis`, `IVHistoryPoint`, `IVHistoryResult`, and request
  helpers;
- `MarketDataStatus.iv` and `MarketDataStatus.sync.iv`;
- ticker `MarketDataCoverage.iv`; and
- `/health.data_sources.iv_tickers`.

Also remove the unreachable in-process market-data job poller as one closed
subsystem: `GET /market-data/jobs/{job_id}`, `_JOBS`, `_JOBS_LOCK`,
`start_bootstrap_job`, `start_update_job`, `get_job`, and frontend
`MarketDataJob` / `getMarketDataJob()`. The only routes that formerly created
these jobs are permanent 409 PG-mirror tombstones. This removal does not touch
the separate durable `/jobs` API or any `job_runs` row.

`GET /options/greeks/calculate` remains. If route reordering or module
extraction is needed to preserve it after dynamic routes disappear, that is a
mechanical change within this tranche, not permission to alter calculations.

### 6.3 Ticker Detail and Settings

Ticker Detail's Data tab stops issuing the two old IV requests. It keeps:

- local market status;
- price/news/fundamentals coverage facts that still exist;
- fundamentals source and local-coverage rows;
- fundamentals details/statements; and
- independent error handling for surviving legs.

It removes the IV source row, local-coverage row, summary, signal, rank,
percentile, VRP, history table, and old IV error operations. The remaining
layout must reflow without an empty column, placeholder, or horizontal
overflow.

Settings Data Storage removes the legacy IV row and removes IV from incremental
status prose. The section description/search aliases may be rewritten but do
not change leaf counts. Provider client-domain key `iv` remains because live
IBKR option/IV calls still use an IV-specific client domain; it is not the old
history store.

### 6.4 Health and provenance

IBKR health is derived from current price and news facts only. Remove stale
`iv_latest` from success selection, detail prose, and signals. Do not replace
it with a fabricated no-data warning.

Remove old per-call IV provenance and local coverage facts. Fundamentals and
other domain provenance remain unchanged.

The registered `check_data_freshness` tool remains, but its source set,
fallback-error projection, thresholds, summary/detail formatting, and provider
tool descriptions no longer mention `iv_history`. The registered
`get_ticker_data_coverage` tool remains, but its result no longer emits an
`iv` member or queries `iv_history`. Neither surviving tool treats retirement
as missing, stale, or failed data.

### 6.5 Agent, evidence, and analysis surfaces

Remove these tools from the central registry, OpenAI bridge, Anthropic schema,
Anthropic dispatch, prompts, and count assertions:

```text
get_iv_analysis
get_iv_history_data
scan_mispricing
```

Remove the dedicated `get_iv_history_data` compressor reducer and its routing
entry. Do not remove option-chain reduction.

Remove `iv_environment` from `evidence_packet`. Coverage metadata must no
longer list `iv` as missing or errored merely because the capability is gone.
Remove `ARKSCOPE_OVERVIEW_INCLUDE_IV` and `latest_iv/latest_vrp` from
`analysis_tools`.

Retain:

```text
calculate_greeks
get_option_chain
get_iv_skew_analysis
```

Retain pure option-pricing, IV-rank, volatility, and mispricing mathematics and
surviving product code that computes from explicit/live inputs rather than the
old store. Remove `scripts/analysis/compare_bs_vs_american.py` and
`scripts/analysis/scan_option_mispricing.py` in full. The former's math-only
mode does not justify preserving or splitting a CLI that is already scheduled
for scripts retirement; equivalent reusable math remains library-owned and
tested. The retirement boundary is storage-backed product capability, not the
mathematical concept of IV.

### 6.6 Tranche 2 resource delta

Remove two Settings leaves per locale:

```text
dataStorage.labels.iv
dataStorage.summary.iv
```

Rewrite, without changing leaf count:

```text
registry.sections.dataStorage.description
registry.sections.dataStorage.searchAliases
dataStorage.update.succeeded
```

Remove these 22 Explore leaves per locale:

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

Expected dated counts are:

| Point | Settings | Explore | Total |
|---|---:|---:|---:|
| `TRANCHE_1_TIP` | 706 | 401 | 1806 |
| Final | 704 | 379 | 1782 |

Key parity, non-empty leaves, scanner `36/20/0/20`, and global `src/**`
coverage remain mandatory. The plan must stop if any listed leaf has a
surviving non-legacy consumer.

### 6.7 Tool-count delta

The current central registry contains 56 tools; each provider bridge contains
those 56 plus `delegate_to_subagent`, for 57.

| Point | Central registry | OpenAI bridge | Anthropic bridge |
|---|---:|---:|---:|
| Base / `TRANCHE_1_TIP` | 56 | 57 | 57 |
| Final | 53 | 54 | 54 |

The three removals above are the only tool-count changes. Count nodes evolve in
place, and name-set tests must prove the three retired names are absent while
the three retained option tools remain present.

### 6.8 Tranche 2 node accounting

The implementation plan must provide a complete named node ledger. It must at
least classify all old IV nodes in:

- `test_api.py` analysis/history/mispricing routes and source-path mapping;
- `test_data_access.py` IV-history classes;
- `test_sqlite_backend.py` IV local/read/provenance/health tests;
- `test_market_data_admin.py` IV bootstrap/checksum/incremental/status tests;
- `test_provider_health.py` IBKR IV detail expectations;
- `test_freshness.py` old IV source/threshold/summary expectations;
- `test_data_coverage_tools.py` old ticker-level IV member expectations;
- `test_tools.py` three old tools and tool catalog;
- `test_agents.py` name sets and four count nodes;
- `test_evidence_packet.py` IV evidence/missing-source behavior;
- `test_compressor_reducers.py` IV history reducer behavior;
- Ticker Detail, Explore operation, Settings Data Storage, API DTO, and
  resource inventory tests; and
- any freshness/data-coverage tests that still enumerate the old domain.

New or evolved named contracts must prove:

- old routes are absent while Greeks remains reachable;
- no current runtime backend/schema/status owner references the old store;
- retained option tools have no dependency on the old DAL/table/files;
- Ticker Detail makes no old IV request and renders no empty IV shell;
- evidence packets neither emit nor report missing legacy IV;
- provider health no longer derives success from stale IV dates;
- resource and tool-count deltas are exact;
- the no-PG smoke removes exactly
  `CheckSpec("iv_history", "GET", "/options/AMD/history", ...)` and its direct
  `options.iv_history(...)` dispatch, changing the fixed check inventory from
  24 to 23 with every other check unchanged;
- no non-migration script reads the retired DAL/table/Parquet path; and
- the production migration preview/archive/apply/replay/restore contracts in
  Section 7 are mutation-sensitive.

## 7. Production Archive And Cutover

### 7.1 Safety boundary

No production write occurs during implementation or implementation review.
After merge, the user must stop ArkScope, the sidecar, scheduler, desktop, and
any CLI writer before cutover. The cutover runs merged code only and requires a
separate explicit approval.

The migration tool must support `preview`, `apply`, and `restore`. Preview is
the only mode allowed before approval and must open both databases read-only.
No mode may contact PG, Gateway, or a provider.

### 7.2 Preview classification

Preview must report, without accepting remembered counts:

- exact SQLite schema/index and every dependent view/trigger/reference;
- IV row count, ticker/date/id bounds, and row digest;
- every Parquet path, schema, row count, and digest;
- whether SQLite and Parquet value multisets match exactly;
- target `scheduler_state` rows;
- target `profile_settings schedule.<id>.*` rows;
- `market_sync_meta.domain='iv'` rows;
- target `job_runs` counts/statuses/digest; and
- non-target table inventory/digest inputs.

Apply stops if:

- the IV table schema differs;
- an unknown dependent view/trigger exists;
- SQLite and active Parquet rows differ;
- an unexpected active collector/source is found;
- any target is changing while preview runs; or
- the databases fail integrity/FK checks.

### 7.3 Restore-ready archive

Before deletion, create a mode-0700 directory under:

```text
data/backups/legacy_scheduler_iv_retirement_<UTC timestamp>/
```

All artifacts are mode 0600. The archive contains:

- a mini SQLite database with the exact `iv_history` table, index, and rows;
- exact copies of all active IV Parquet files;
- JSON exports of removed `scheduler_state`, schedule preference, and
  `market_sync_meta` rows;
- a manifest with source DB paths, sizes, mtimes, schema SQL, row counts,
  ticker/date/id bounds, per-artifact SHA-256, and non-target digest inputs;
- the target `job_runs` digest marked **preserve, do not restore/delete**; and
- exact restore instructions tied to the pre-retirement code commit.

The mini database is sufficient rollback material for the tiny target table;
duplicating the full 3.3 GB market DB is not required. The migration's
transaction and pre/post non-target logical digests must prove that no other
market table changed.

### 7.4 Apply sequence

After archive verification:

1. delete `profile_settings` keys matching only
   `schedule.{price_backfill,local_incremental,iv_history}.%`;
2. delete `scheduler_state` rows for exactly those three IDs;
3. delete `market_sync_meta` rows for exactly `domain='iv'`;
4. drop `iv_history` transactionally (its index drops with it);
5. remove the active four-file IV directory only after its archived copies
   verify; and
6. write final manifest state and post-apply digests.

No prices, news, fundamentals, financial-cache, option-chain, or other market
payload row is selected for deletion. In particular, the cutover does not try
to infer or erase rows historically written by `local_incremental`.

Profile and market databases are separate transaction owners. The tool must be
idempotent and resumable from its verified archive if interrupted between
owners. A partially applied state without the matching archive manifest is a
hard failure.

`job_runs` receives no DELETE, UPDATE, or INSERT. Its target-name row multiset
digest must match before and after apply.

### 7.5 Post-apply proof

Required proof:

- second apply reports `already_applied=true` and changes no byte/row;
- `PRAGMA integrity_check` is `ok` and FK violations are zero in both DBs;
- every non-target table logical digest is unchanged;
- target `job_runs` digest is unchanged;
- old table/index, sync row, operational state, preferences, and active
  Parquet paths are absent;
- old API paths are unavailable;
- `/schedule` has exactly four active sources;
- Ticker Detail and Settings render no old IV/source row in both locales; and
- retained Greeks/option-chain/skew gates still pass.

### 7.6 Rollback semantics

Data restoration alone does not restore product behavior because merged code
no longer owns the old contract. Rollback requires:

1. stop all processes;
2. check out the exact pre-retirement product commit named in the manifest;
3. run the reviewed restore command against the archive;
4. verify restored table/files/state and integrity; and
5. restart the old code.

Restore refuses to overwrite any non-empty or differently shaped target. A
future IV implementation never imports this archive automatically.

## 8. File Ownership Map

### 8.1 Tranche 1 principal owners

- `src/service/data_scheduler.py`
- `src/api/routes/schedule.py`
- `src/daily_update.py`
- `src/prices_runtime.py`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- `apps/arkscope-web/src/settings/settingsBackendCopy.ts`
- Settings resource files and their focused tests
- scheduler, schedule-route, daily-update, and prices-worker tests

### 8.2 Tranche 2 principal owners

- `src/market_data_admin.py`
- `src/market_data_direct.py` (protected shared price primitive; IV-domain
  enumerations only)
- `scripts/analysis/compare_bs_vs_american.py` (remove)
- `scripts/analysis/scan_option_mispricing.py` (remove)
- `src/api/routes/options.py`
- `src/api/routes/scan.py`
- `src/api/routes/market_data.py`
- `src/api/routes/health.py`
- `src/service/provider_health.py`
- `src/tools/backends/*`
- `src/tools/data_access.py`
- `src/tools/data_coverage_tools.py`
- `src/tools/freshness.py`
- `src/tools/options_tools.py`
- `src/tools/schemas.py`
- `src/tools/registry.py`
- `src/tools/analysis_tools.py`
- `src/evidence_packet.py`
- OpenAI/Anthropic bridge and shared prompt/reducer owners
- shared subagent tool-name owners and PG-unreachable smoke fixtures
- `apps/arkscope-web/src/TickerDetail.tsx`
- frontend API, Explore presenter, Data Storage, resources, and focused tests
- `sql/001_init_schema.sql`
- a new audited retirement migration and its isolated tests

Historical N9 scripts/evidence and pure/live option math are protected unless a
specific current-runtime dependency is demonstrated in the implementation
plan.

## 9. Test And Acceptance Matrix

### 9.1 Baselines

Current merged evidence reports backend collection `4749`, frontend
`96/1072`, scanner `36/20/0/20`, resources `714/1814`, central tools `56`, and
provider bridge tools `57`. The no-PG smoke currently contains 24 checks and
must finish with exactly 23 after its one named IV-history check/dispatch is
retired. A design-time focused backend census across 15 principal files
collected 461 nodes; an eight-file frontend census collected 129 nodes.

All are dated observations. Task 0 of the implementation plan must reproduce
normalized node lists and hashes before locking exact tranche arithmetic.

### 9.2 Required layers

- pure source-catalog and API route tests;
- scheduler/CLI static absence and mutation tests;
- mounted dual-locale Settings schedule tests;
- backend protocol/schema/API retirement tests;
- retained option-capability tests;
- evidence/agent/compressor name-set tests;
- mounted dual-locale Ticker Detail and Data Storage tests;
- resource parity/count/scanner/typecheck/build gates;
- migration preview/archive/apply/idempotence/restore tests on copied synthetic
  DBs and copied production-shaped data; and
- post-merge production read/write proof under the approval sequence in
  Section 7.

### 9.3 Visual gate

At minimum, verify Settings Data Sources, Settings Data Storage, and Ticker
Detail Data tab in `zh-Hant` and `en` at 1440, 960, and 390 px. Use
production-shaped long schedule/history/fundamentals content. Required:

- exactly four schedule rows;
- no empty IV column or stale heading;
- no old IV data-source row;
- surviving tables fit without horizontal page overflow;
- locale switch preserves active tab, focus, drafts, and reading position; and
- no new CSS by default. Any CSS change follows the reviewed visual-deviation
  protocol with a named test.

## 10. Stop Conditions

Stop and amend the design if implementation finds:

- a current non-test caller of any retired scheduler identity;
- IV data not equal to the reviewed SQLite/Parquet duplicate set;
- a current consumer requiring the old table/API for a capability that the
  user still relies on;
- a retained live/pure option tool importing the old DAL/table;
- a foreign key, trigger, view, or unknown schema dependency on `iv_history`;
- a need to mutate or delete `job_runs`;
- a need to delete or rewrite non-IV market payload, including rows once
  written by `local_incremental`;
- a need for a provider/Gateway/PG call;
- a new future-IV schema/provider decision;
- a resource deletion outside the exact reviewed key ledgers;
- a tool-count change other than the three named removals;
- an unreviewed change to prices/news/fundamentals data or Coverage v2; or
- production drift after preview.

## 11. Documentation And Closeout

Implementation closeout updates:

- this document and its implementation plan/evidence to `LIVE COMPLETE` only
  after production cutover and smoke;
- `PROJECT_PRIORITY_MAP.md` with both tranche tips, archive path/digests,
  migration result, and the unchanged future-IV gate;
- `PG_EXIT_REMAINDER_SCOPING.md` current-state rows to say the local legacy IV
  surface is retired, while preserving dated PG-drop history;
- `IV_PROVIDER_PROOF_PACKET_PLAN.md` with a short note that the old source/data
  contract is gone and no old row is a future seed;
- `REPO_HYGIENE_B6_MODULE_DISPOSITION.md` to supersede its survivor ruling for
  exactly the two removed analysis scripts and to retain the separate broader
  scripts-retirement direction;
- current option-theory documentation so it no longer advertises either
  removed script as an executable workflow while preserving historical
  methodology findings; and
- current CLI/API documentation that still advertises the removed paths.

No closeout may claim that IV as a product/research domain is abandoned. Only
the old PG-mirror ATM-IV snapshot contract is retired.

## 12. Implementation Sequence

1. Reproduce all baselines and lock exact node/resource/tool ledgers.
2. Implement Tranche 1 RED-first.
3. Record `TRANCHE_1_TIP` and its full evidence snapshot.
4. Independently re-run Tranche 1 gates before opening Tranche 2.
5. Implement Tranche 2 code and migration tool RED-first without production
   writes.
6. Run copied-production preview/apply/idempotence/restore proof.
7. Stop at review-ready for independent implementation review.
8. After GREEN and explicit approval, fast-forward merge.
9. Stop all ArkScope writers and run merged-code production preview.
10. Obtain explicit approval for the exact fresh manifest.
11. Archive, apply, verify, restart, and run bilingual smoke.
12. Mark docs live and leave future IV at its existing evidence gate.
