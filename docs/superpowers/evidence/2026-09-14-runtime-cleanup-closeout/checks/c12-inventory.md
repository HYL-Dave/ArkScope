# C12 Collector Convergence Inventory

Date: 2026-09-14. Worktree: `/tmp/arkscope-research-output-boundary`.
Inspected HEAD: `a065a0c30a4f75995215cabc0e39dd2579c17c3d`.
Status: read-only source inventory and proposed boundary, not an implemented or
verified cleanup. The worktree was clean at entry and immediately before this
report was written. All source line numbers below refer to that HEAD.

Only this report is authorized for writing. No product/test edits, pytest,
collector execution (including help/status/dry-run), application imports,
network/provider access, production-data inspection, configuration/credential
inspection, or agents were used. Paths to stored artifacts below are derived
from source, not observations of their existence or contents. SQLite engine
admission and CENSUS-SQL are explicitly outside this inventory.

## Conclusion

C12 remains real and open. Its audit row explicitly distinguishes reachable
module CLIs from the app's normalized/direct-local writers and prohibits deleting
already-collected files: [audit C12][audit-c12]. The surrounding retention and
positive-control requirements remain applicable: [audit closeout][audit-close].

The safe boundary is **old collector orchestration/storage/CLI removal, not news
provider removal**. Both modules contain fetch/parse code used by two current
branches. The scheduler still records two old `run_incremental` string targets,
but its current route classification and dispatch bypass both targets. The
standalone module `main()` functions still call them and still write Parquet.

For an unambiguous retirement with no compatibility shell, the recommended
eventual change is to move the live transport/parser implementation into two
non-CLI modules, repoint both live factories and their tests, remove the old
writer code and module files, and remove only the two obsolete scheduler adapter
tuples. **Do not begin the CLI deletion until the product decision below is
resolved.** Routine collection has a current replacement; historical acquisition
and raw-file reporting do not have full feature parity.

## Reachability Evidence

| Entry or consumer | Evidence | Classification |
| --- | --- | --- |
| Massive module CLI | [P main][p-main], [P incremental call][p-cli-inc], [P ordinary collection call][p-cli-collect], [P module guard][p-guard] | Reachable: incremental calls `run_incremental`; ordinary/date/history/resume collection calls `collect_news`; both reach old storage and stats writers. |
| Finnhub module CLI | [F main][f-main], [F incremental call][f-cli-inc], [F ordinary collection call][f-cli-collect], [F module guard][f-guard] | Reachable: both incremental and ordinary collection reach old storage and stats writers. |
| Scheduler string registration | [scheduler sources][sched-sources] | `polygon_news` and `finnhub_news` each have both an old `adapter=(module, "run_incremental")` and a live `news_direct_source`. This is a dynamic reference, not an ordinary import. |
| Scheduler mode admission | [classifier][sched-classify], [route resolution][sched-route], [blocked branch][sched-block] | NORMALIZED/LEGACY_LOCAL are exhaustive admitted local modes; BLOCKED raises before collection; unknown modes return failure before provider/lock/telemetry work. |
| Scheduler dispatch precedence | [normalized branch][sched-normalized], [direct-local branch][sched-direct], [generic adapter][sched-adapter] | Both admitted news branches precede the dynamic `importlib.import_module` plus `getattr` fallback. The two old tuples are redundant for current news execution, not proof that the module CLIs are dead. |
| Live normalized construction | [normalized factory][sched-factory] | Lazily imports each collector's config, class and `load_env`; validates the key and wraps the collector in the normalized adapter. |
| Live direct-local construction | [direct provider factory][provider-factory] | Lazily imports the same config, class and `load_env`. `_CollectorNewsProvider.fetch_news` calls only fetch/parse. |
| Settings Run Now and recurring schedules | [schedule API][schedule-api], [scheduler tick][sched-tick] | Both dispatch `run_source`; keep permission/config gates, source IDs, scheduling and locking. |
| Current operator CLI | [daily CLI execution][daily-exec] | `src.daily_update` calls `run_source(source, trigger_source="cli", tickers=tickers)`, not either collector CLI. |
| Generic adapter's surviving owner | [SEC source registration][sched-sec], [SEC runtime test][test-sec] | `src.sec_research.scheduled.run_incremental` is live. Do not delete `SourceDef.adapter`, the generic dispatch branch, or every symbol named `run_incremental`. |
| Status metadata | [provider_fetch expression][sched-status] | Removing only the two news adapter tuples preserves `provider_fetch=True` because `news_direct_source` remains set. |

### Reference Search Coverage

Read-only `rg`, `rg --files`, line-numbered source reads, and Git metadata checks
were used. Searches covered `src`, `tests`, `apps`, `extensions`, `data_sources`,
`resources`, root README/structure/package metadata, and Markdown documentation
including hidden `.superpowers` notes. Live code searches included Python,
JS/TS/TSX, Rust, shell, JSON, TOML, YAML, INI/CFG, service and timer files. They
excluded dependency trees/lockfile noise; generated audit XML/log/JSON captures
were not used as current caller authority. Documentation snapshots were treated
as historical evidence, not executable consumers.

Search families included:

```text
polygon_news | finnhub_news | news_providers
PolygonNewsCollector | FinnhubNewsCollector | CollectionConfig | FinnhubConfig
run_incremental | collect_news | fetch_news_month | generate_months | CheckpointManager
collectors[./] | from src.collectors import
collect_polygon_news | collect_finnhub_news
importlib.import_module | __import__ | spec_from_file_location
runpy | run_module | run_path | entry_points | console_scripts
data/news/raw | polygon_collection_checkpoint | finnhub_collection_stats | collection_stats.json
```

The live-code results identify the two factories, scheduler tuples/dispatcher,
module CLI guards, and test consumers listed here. `src/collectors/__init__.py`
contains only a package docstring; `rg --files src/collectors` lists exactly that
file plus the two target modules. No additional live launcher for the old news
CLIs was found in the searched source/packaging roots. This is **not** a claim
that external shell commands, installed launchers, user scripts, or production
configuration do not invoke them: those were neither inspected nor executed.
No import-count or zero-hit result is used as the retirement authorization.

## Shared Implementation That Must Survive

The two adapters intentionally consume different representations. Preserve their
separate mapping and cursor behavior; do not combine them while deleting writers.

### Massive Transport and Parser

| Symbol or behavior | Exact source | Retention reason |
| --- | --- | --- |
| `CollectionConfig` transport settings | [P config][p-config], lines 83-102 | Preserve request delay, requests-per-minute, page size, retry count/delay used by the transport. `data_dir`, `checkpoint_dir`, `default_start` belong to the old orchestration and need not enter a transport-only owner. |
| `NewsArticle` | [P model][p-model], lines 109-134 | Keep the parsed data contract: ID, ticker, title/time, source, description/content, URL/publisher/author, relations/tags/category, native sentiment, collection time/length/hash. Current adapters consume a subset, but native sentiment is separately protected by [score-retirement owner][test-native-sentiment]. |
| `RateLimiter` | [P limiter][p-limiter], lines 141-175 | Used by constructor/fetch; retain minimum spacing and rolling request-count behavior. |
| `PolygonNewsCollector.__init__`, `BASE_URL`, stats | [P client][p-client], lines 215-232 | Live constructor/session/limiter and counters. Keep the current `https://api.massive.com` host and durable `polygon` source identity. A retained real class is not a compatibility forwarding shell. |
| `fetch_news_range(ticker, start_date, end_date, start_timestamp=None)` | [P range fetch][p-fetch], lines 254-342 | Preserve inclusive `published_utc.gte`, end-of-day upper bound, ascending order/page size, `next_url` pagination, API-key handling, timeout, rate-limit handling and current retry/error accounting. **`start_timestamp` is used by the normalized adapter**, not just the retired incremental writer. |
| `parse_article(raw, collected_at)` | [P parser][p-parse], lines 344-398 | Preserves first returned ticker/UNKNOWN fallback, provider ID or MD5 fallback, time string, description/content, relations/keywords, publisher/author and sentiment. Do not silently change multi-ticker selection or identity during extraction. |
| `load_env()` | [P key resolver][p-env], lines 662-670 | Live factory dependency. Reads only the canonical `MASSIVE_API_KEY` process bridge and rejects empty/placeholder values. Does not revive `POLYGON_API_KEY` or dotenv authority. |

`fetch_news_month` ([P month wrapper][p-month], lines 234-252) is **not** in the
live shared set: its sole found call is the old full-history loop at
[P month orchestration][p-month-call]. `generate_months` is similarly old
orchestration/estimate support. Retaining `fetch_news_range` preserves the
underlying ability to request historical ranges if an approved current CLI later
exposes it.

### Finnhub Transport and Parser

| Symbol or behavior | Exact source | Retention reason |
| --- | --- | --- |
| `FinnhubConfig` | [F config][f-config], lines 79-91 | Keep the transport config and limiter settings; `data_dir` is storage-only. `max_retries`/`retry_delay` are declared but the current fetch method does not consult them; do not invent new retry behavior during extraction. |
| `NewsArticle` | [F model][f-model], lines 98-123 | Keep parsed shape and provider ID/MD5 fallback so both mappings retain their inputs. |
| `FinnhubRateLimiter` | [F limiter][f-limiter], lines 130-163 | Used by live constructor/fetch. |
| `FinnhubNewsCollector.__init__`, `BASE_URL`, stats | [F client][f-client], lines 170-187 | Session, limiter and counters survive; `stats['by_source']` is required by the parser, and `skipped_truncated` is updated there. |
| `fetch_news(ticker, start_date, end_date)` | [F fetch][f-fetch], lines 189-228 | Keep company-news endpoint, symbol/from/to/token parameters, timeout, current 429 handling and other error behavior. |
| `parse_article(raw, ticker, collected_at)` | [F parser][f-parse], lines 230-292 | Unix timestamp to actual UTC `Z`; requested ticker; headline/summary/URL/source/relations/category; `None` for Yahoo summaries of exactly 100 or 500 characters; source/skipped counters. These are live parser semantics, not retired writer policy. |
| `load_env()` | [F key resolver][f-env], lines 486-518 | Still called by both factories. Unlike Massive it retains environment-first resolution and fallback file parsing. C12 does not authorize changing that credential policy or reading those files. Preserve behavior and [its exact tests][test-env]. |

The old Finnhub seven-day clamp is in `collect_news` and `run_incremental`, not
in shared `fetch_news`: [F old clamp][f-collect], [F incremental window][f-inc].
Both current adapters default a missing cursor to seven days, but a supplied
older cursor is not capped there. Do not transfer the old clamp into shared fetch
under the assumption that it already governs current collection. The provider's
history-limit descriptions are source claims, not live-provider verification.

### Preserve Both Current Branches

| Branch | Contract and retention boundary |
| --- | --- |
| Direct-local | [provider mapping/fetch][provider-map]: description takes precedence over content; shared SHA-256 identity replaces collector MD5 as local row hash; skip `None`. `_since_to_start` uses the cursor's date inclusively, or seven-day bootstrap. [direct writer][direct-writer] obtains each source+ticker's newest local time, writes `news`, maintains FTS through existing triggers, records provider telemetry and isolates per-ticker failures. No Parquet cursor/writer. |
| Normalized | [candidate mapper][normalized-map]: keep provider ID, primary/related tickers, observed time and raw summary/body provenance. Here nonblank content takes precedence over description; summaries stay summaries, not full text. [normalized fetch][normalized-fetch] passes Massive's exact inclusive timestamp and Finnhub's date cursor, skips `None`, and defaults missing cursors to seven days. |
| Normalized progress/frontier | [writer cursor][normalized-cursor] first uses the completely covered source+ticker telemetry frontier; [store fallback][normalized-store-cursor] bootstraps from normalized rows only when appropriate. Preserve budget/partial/manual-continuation behavior and market lock factory at [writer assembly][sched-writer]. Never replace this with global Parquet latest+1s. |
| Current projection/readers | Scheduler deliberately passes `project_legacy=True` at [writer assembly][sched-writer]. [projection][projection] maintains per-ticker `news` rows and existing FTS triggers. [local backend][local-backend] delegates current news reads to [news queries/FTS][news-queries]. The word `legacy` in this live projection or `LEGACY_LOCAL` route does not make it removable compatibility code. |
| Routing and settings | [routing policy][routing-policy]: for these REST sources, true normalized setting selects normalized; unset/false selects direct-local; malformed state blocks. Preserve `parse_news_toggle`, current settings/status and C11's already-retired-switch behavior. Do not force normalized-only or change stored settings to simplify C12. |

Keep existing transport/error behavior during relocation. This inventory does not
claim that every provider HTTP failure currently raises: both clients also use
error counters/empty results. Fixing that separately would require its own
behavioral scope and tests, not an incidental rewrite while retiring storage.

## Current CLI Authority and Product Decision

[README operator authority][readme-operator] and [protected runtime guardrail][smoke]
identify `src.daily_update` plus Settings as current owners. Its source selector
and parser are at [daily flags][daily-flags]; ticker resolution, dry-run boundary,
environment setup and scheduler call are at [daily scope/execution][daily-scope].

Routine replacements, shown as documentation only and **not executed**:

```bash
python -m src.daily_update --massive --scope active-universe
python -m src.daily_update --finnhub --scope active-universe
python -m src.daily_update --massive --tickers AAPL,MSFT
```

The current public Massive selector is `--massive`; `--polygon` already exists
as a hidden selector for the same live source. C12 needs no new alias or wrapper.
Keep durable `polygon`, `polygon_news`, `finnhub_news`, `collect.<source>` and
existing stored source identities. `--news` also includes IBKR news; `--all` adds
IBKR prices. Do not replace a provider-specific manual task with `--all`.

| Old functionality | Current replacement parity | Decision before deletion |
| --- | --- | --- |
| Routine incremental collection and explicit ticker/universe selection | Available through `daily_update`/`run_source`, using current local per-ticker cursors, locks and telemetry. | Reroute operator documentation; do not preserve global Parquet latest+1s or full-history-on-empty semantics. |
| Massive `--start`, `--end`, `--days`, `--full-history`; default recent/month collection | **Not exposed by current CLI or `run_source` news arguments.** First-run local adapters use seven days, not the old 2022 full fallback. | Owner must explicitly retire manual historical/custom-window acquisition or require it in the current CLI before deleting its sole found executable owner. |
| Massive `--resume` checkpoint and `--estimate` | No equivalent CLI controls. Normalized writer continuation is a different runtime contract, not a month-checkpoint replacement. | Explicitly retire these operator capabilities or specify a current-owner replacement. Do not preserve old checkpoint-writing code just to keep the flags accepted. |
| Finnhub explicit start/end/days override | Not exposed by `daily_update`; current cursor-driven recent collection remains. | Explicitly retire arbitrary overrides or add approved current-owner support. Do not presume a historical-fetch guarantee from the old source prose. |
| Collector `--status` raw-file count, date range, ticker/year breakdown | `daily_update --status` has an independent partial Parquet summary, not the same detail and not current local news-ingest truth. | Decide whether an explicit archive report remains a supported capability. It must not be confused with current ingest status or justify retaining a storage writer. |

The actual product question is therefore: **may the dedicated historical/range,
resume/estimate and detailed archive-status capabilities be retired, or must any
be rehomed before the old executable modules disappear?** This report does not
answer that for the owner. If required, expose them at the current CLI/service
boundary with both local writer routes, explicit scope, current locks/telemetry,
and separately reviewed cursor/budget semantics. Do not make the old CLI forward
to the new one or accept flags that are ignored.

Two important limits on any parity claim:

- Old Massive date collection expands the requested dates into whole months
  ([month generation][p-months], [month fetch call][p-month-call]); a replacement
  promising exact date bounds is an explicit behavior decision. The existence
  of checkpoint/resume code is not evidence of reliable resume under every
  interruption: [old collection completion][p-checkpoint-clear] clears the
  checkpoint after the catch block as well. Do not copy bugs as requirements.
- `daily_update` still has false old-writer guidance at [historical help text][daily-stale],
  claiming global incremental cursor semantics and recommending the retiring
  module. Its [Massive/Finnhub status functions][daily-status] independently scan
  raw Parquet; [show_status][daily-show-status] reports freshness from those files,
  and [end of run][daily-finish] calls it after local writes. Fix or explicitly
  scope this reporting before claiming the replacement reports current local
  news freshness. Current status/telemetry owners are preferable; raw archive
  inspection, if retained by decision, must be labeled separately. Do not drop
  existing files to make the reported sources converge.

## Proposed Physical Boundary

This is a recommendation for later approved implementation, not permission to
edit product code in this task. Suggested new ownership paths, not existing
files: `src/news_clients/polygon.py` and `src/news_clients/finnhub.py`, with a
side-effect-free package initializer. Keep the two concrete transport/parser
implementations separate; no new generic provider framework is needed.

1. Resolve the CLI capability decision above. Until then do not describe C12 as
   closed. Removing the two redundant scheduler tuples is independently bounded,
   but it alone does not retire the reachable CLI writers.
2. Move only the shared config/model/limiter/client/key-resolver code listed
   above. Repoint `src/news_providers.py:86` and
   `src/service/data_scheduler.py:438`/`:452`, plus exact tests below, in the same
   change. Preserve lazy construction and parser contracts; do not rename
   durable source/class identities merely for branding.
3. Physically remove these old symbols, their CLI examples and storage-only
   imports/config fields together:

| Module | Exact removable surface once CLI disposition is approved |
| --- | --- |
| `polygon_news.py` | `_setup_cli_logging` 68-76; `CheckpointManager` 182-208; `fetch_news_month` 234-252; entire `StorageManager` 405-628 (including status/cursor/cache helpers); `_scope_error`/`load_tickers` 635-659; `generate_months` 673-688; `collect_news` 691-815; `estimate_time` 818-829; `_save_collection_stats` 836-849; `run_incremental` 852-941; `main` and module guard 944-1085. Source anchors are linked above. |
| `finnhub_news.py` | `_setup_cli_logging` 64-72; entire `StorageManager` 299-452; `_scope_error`/`load_tickers` 459-483; `collect_news` 521-606; `_save_collection_stats` 613-626; `run_incremental` 629-680; `main` and module guard 683-787. Preserve `load_env` between these blocks. |

4. Remove the original two module files after repointing all current consumers.
   Remove the now-empty `src/collectors/__init__.py` only if it still has no other
   live members at edit time. No re-exports, deprecated forwarding functions,
   inert `main`, `sys.modules` aliases, or compatibility CLI shells. Keeping
   only fetch/parse in the old files is a smaller alternative, but bare
   `python -m old.module ...` would then be capable of silently exiting without
   collecting; full relocation/deletion makes executable retirement unambiguous.
5. Remove only the two `SourceDef.adapter` tuples at scheduler lines 141/149;
   update stale comments at lines 10-12, 103-107 and 991. Keep source entries,
   route validation, both branch bodies, factories, generic SEC adapter and
   status metadata. No scheduler state/key migration, source-ID renaming,
   schedule enablement, service restart or in-flight-run manipulation.
6. Repair current CLI docs/status as explicitly scoped above. If capability
   rehoming is required, it precedes old CLI deletion and gets current-owner
   tests. Do not retain retired writer code as temporary compatibility.

`pandas`/`asdict` storage usage disappears from the extracted clients, but this
does not authorize removing repository dependencies: current status/readers and
other paths still use them. `hashlib` is not automatically storage-only: both
parsers use MD5 as an article-ID fallback when a provider ID is absent.

## Exact Test Collateral

Nothing in this section was run. It identifies edits and future isolated
verification owners, not passing tests or an expected test-count reduction.

### Tests That Must Change With Removal or Relocation

| File and exact test/site | Required treatment |
| --- | --- |
| [test_collector_adapters.py][test-collectors]: `test_collectors_expose_contract_from_src_package` (22), `test_import_is_side_effect_free` (40) | Rehome positive assertions to real client modules; retain no logging/filesystem/provider work at import. Replace required `run_incremental`/CLI-logging presence with physical absence of old symbols/files/entrypoints. |
| Same file: `test_paths_are_repo_anchored` (60), `test_polygon_up_to_date_short_circuit` (69), `test_finnhub_up_to_date_short_circuit` (125), `test_finnhub_incremental_window_capped_at_7_days` (143) | Remove old storage/config/global-cursor contracts. Test current bootstrap/inclusive cursors at live providers; do not relocate the obsolete global seven-day cap assertion onto shared fetch. |
| Same file: `test_polygon_missing_key_raises` (81), `test_finnhub_missing_key_raises` (135) | Move failure coverage to current provider preflight/factory/CLI boundaries, not a re-created incremental writer. |
| Same file: `test_massive_news_transport_builds_requests_on_the_current_api_host` (89) | Keep, repoint to extracted real client, preserve its fake-session/no-network control. Add focused pagination/timestamp/parser controls where currently absent. |
| Same file: `test_load_tickers_requires_explicit_scope` (161), `test_load_tickers_active_universe` (170), helper at 197 and unavailable-scope tests at 238/246 | Transfer scope/error assertions to `daily_update` and real `run_source` consumers. Do not retain test-only `load_tickers` copies. Preserve no provider construction on unavailable/empty scope. |
| [test_collector_load_env.py][test-env]: dynamic module paths at 26, 35, 44, 52, 62, 70, 78 | Repoint all seven tests. Preserve Massive process-only and Finnhub env-first/file-fallback behavior; test-owned temporary files only. Correct stale module-wide prose that incorrectly groups their policies. |
| [test_news_providers.py][test-providers]: import at 10, all mapping/fetch tests | Repoint the concrete `NewsArticle`; preserve SHA-256, description precedence, same-date input, no-Parquet and `None` filtering. |
| [test_news_normalized_provider_adapters.py][test-normalized-providers]: imports 3/7, mapping tests 50/64/76/84, cursor tests 93/124, real Finnhub UTC parser test 156 | Repoint real types and keep every behavioral control, including raw summary text and exact timestamp support. |
| [test_news_direct.py:73][test-direct-parity], concrete import at 82 | Repoint the dataclass in `test_direct_dedups_against_mirror_sha_row`; retain compatibility with already-existing local rows rather than deleting that parity assertion. |
| [test_active_universe.py:455][test-active-universe] and `:500` | `test_former_alpha_pick_crosses_real_news_and_price_scope_consumers` and `test_provider_marked_former_pick_merges_with_manual_identity_for_consumers` currently call removed `load_tickers` (474/475/537). Send the real resolved scope through current news consumers; retain former-pick normalization, price-scope and SA behavior. |
| [test_security_lifecycle_terminal_workflow.py:83][test-terminal] | `test_reviewed_legacy_delisting_stops_shared_scope_and_sa_sync_cannot_resurrect` imports collectors at 84 and calls `load_tickers` at 138/139. Replace only those consumer assertions with current news dispatch. Keep delisted exclusion, SA history and exact pre-existing price/news-row retention at 131/143/144. |
| [test_legacy_score_retirement.py:124][test-native-sentiment] and [path allowlist at 210][test-score-path] | Repoint provider-native-sentiment dataclass import; move the narrowly scoped `score_api` path allowance only if its actual matching source still moves with the client. Do not restore retired scores or broaden scanner exemptions. |
| [test_trading_day_coverage.py:685][test-no-provider-import] | Its no-provider-import guard contains `src.collectors` at 700. Include the new live-client prefix so relocation does not silently weaken this unrelated pure-read guarantee. No coverage/SQL redesign. |
| [test_daily_update_wrapper.py][test-daily] | Preserve help/source set (62), Massive selector (80), four-source dry-run (90), direct-local plan (111), no-scope (121), unavailable-scope-before-environment/provider (127), and price-only status protection (178). Add current-owner CLI dispatch/exit and news-status truth coverage; add date/resume controls only if approved. |
| [test_massive_brand_surface.py:44][test-brand] | If status wording changes, its exact lowercase-copy allowlist for `src/daily_update.py` must match the retained wording, not become a stale exemption. Preserve public Massive label/durable source distinction. |

### Scheduler Test Patch Sites

All references below are in [tests/test_data_scheduler.py][test-scheduler].
Remove old-target monkeypatches, not the behavioral tests they surround. Do not
use `raising=False` to recreate deleted writer symbols just for tests.

| Site or test | Exact patch line(s) | Replacement/control to retain |
| --- | --- | --- |
| Autouse hermetic fixture | 115-120 (patches 117/119) | Remove collector imports and old stubs; keep temp profile/market/lock paths and current provider/direct-writer stubs at 121-131. |
| `test_run_source_news_direct_when_normalized_writes_unset` (1136) | 1140 | Assert current provider and direct writer called once, no worker/normalized writer; separately assert old module/registration absent. |
| `test_unknown_news_write_mode_fails_before_provider_adapter_worker_and_telemetry` (1190) | 1260 | Keep early rejection and zero current factory/writer/worker/telemetry/lock calls; no obsolete adapter probe. |
| `test_normalized_news_route_calls_writer_under_market_lock` (1305) | 1324; dynamic module strings 1299/1301 | Repoint factory module strings and config/class patches (1385-1387); retain real normalized assembly, write-lock factory, `project_legacy=True`, result and progress checks. |
| `test_blocked_news_route_fails_despite_stale_normalized_continuation` (1590) | 1614 | Keep blocked outcome/no normalized or direct work and stale-continuation handling. |
| `test_local_news_route_keeps_single_direct_writer` (1846) | 1853 | Preserve one direct writer, selected provider, no worker/refresh. |
| `test_post_exit_blocked_news_route_fails_closed_and_records_failure` (2182) | 2190 | Keep failure telemetry and zero current-provider/writer work. |
| `test_adapter_universe_unavailable_fails_loud` (2529) | 2562 | Keep typed/sanitized scope failure and zero current provider/writer/worker calls, plus durable failure. |
| `test_run_source_persists_attempt_and_outcome_to_local_state` (2945) | 2948 | Keep durable state test using current direct-writer stub; remove ineffective old-adapter stub. |

Also repoint the live `load_env` patch at 1126 in
`test_normalized_massive_provider_missing_key_names_only_canonical_bridge`.
Keep `test_polygon_news_keeps_its_source_id_but_uses_massive_config_authority`
(1117), exact current route classifier (1177), universe/progress (2505), explicit
CLI tickers (2596), provider setup gates (1098/3268), status metadata (249/2449),
cross-process locks (2351/2376), and real failure persistence (2958/2968).

Normalized continuation tests at 1436, 1515, 1548, 1631, 1685, 1739 and 1781,
and writer lock tests at 3361/3391, must survive unchanged in meaning. Retain
[SEC scheduler runtime tests][test-sec] as positive controls on the generic
adapter that C12 must not remove. IBKR news/prices dispatch and lock tests are
regression controls, not opportunities to change those writers.

### Adjacent Verification Owners and Gaps

- `tests/test_news_normalized_projection.py`: existing-row adoption/FTS (296),
  cross-source dedup (345), Massive/Finnhub direct-row parity (656), and
  provider-date identity across UTC boundaries (677). Keep the actual projection.
- `tests/test_news_direct.py`: idempotence (61), FTS (110/128), telemetry (147),
  isolated ticker failures (164), source cursor (181), and same-second siblings
  (238). Expand to explicit per-ticker cursor independence if needed.
- `tests/test_news_normalized_writer.py`,
  `tests/test_news_normalized_writer_locking.py`,
  `tests/test_news_normalized_routing.py`, `tests/test_news_routing_cleanup.py`,
  `tests/test_news_local_authority.py`, `tests/test_news_settings_route.py`,
  `tests/test_news_sync_status.py`, `tests/test_provider_health.py`: retain live
  routing, frontier/partial results, lock ownership, reads, current telemetry
  and C11's absence contracts. These are focused news regression owners, not a
  duplicate SQL/schema audit.
- `tests/test_job_runs.py:1303`, `:1316`, `:1344` cover daily telemetry behavior;
  do not restore obsolete writer return shapes to satisfy old step vocabulary.
- New absence controls should inspect old paths/symbols and scheduler tuples,
  while positive tests build both real factories with fake transports and
  exercise both routes. Static absence alone cannot prove collection survived.
- In a later authorized test run, create only temporary sentinel raw Parquet,
  checkpoint and stats artifacts, and pre-existing local news/FTS rows. Execute
  current branches against isolated test stores/fake transports; prove sentinel
  bytes unchanged, existing row identities/search retained, new rows admitted
  idempotently, and no old storage/checkpoint/stat writer reached. Guard all
  production paths and provider/network work. No such execution occurred here.

## Documentation Collateral

| Current source/document | Exact evidence | Treatment in an eventual C12 change |
| --- | --- | --- |
| Both collector module docs/CLI epilogs | [P header/main][p-header], [F header/main][f-header] and main links above | Remove with retired CLI; put only approved current commands in current operator documentation. |
| `src/news_providers.py` | [module/factory prose][provider-map], factory line 83 | Repoint shared-code descriptions; stop implying both providers resolve `config/.env` identically. |
| `src/service/data_scheduler.py` | lines 10-12, 103-107, 991, 1432 | Stop describing current news as old `run_incremental` execution. Keep truthful generic-adapter description for SEC. |
| `src/daily_update.py` | [lines 33-37][daily-stale], [status functions][daily-status], [show_status recommendations][daily-show-status] | Remove global-cursor/historical-collector advice; document approved history availability and truthful local-versus-archive status. Current recommended commands must include explicit scope. |
| `README.md` | [58-71][readme-operator] | Preserve current CLI/Settings authority; amend status/historical caveat if needed, not a new standalone collector runbook. |
| `PROJECT_STRUCTURE.md` | [18][structure] | Repoint protected ingestion module location if `src/collectors` is removed; keep protected current CLI. |
| `docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md` | [13-30][smoke] | Keep four-source CLI, explicit scope, exit, lock, telemetry and SA preservation gates; distinguish current local writer routes from retired file writers. No live gate executed for this report. |
| `docs/design/ARKSCOPE_PROVIDER_CATALOG.md` | [158][catalog] | Update Finnhub fetch/parse location; retain Finnhub news/calendar as current capabilities. |
| `docs/design/DESKTOP_APP_VISION_DRAFT.md` | [228][vision] | Update both provider paths and C12 disposition only after implementation; retain current calendar ownership. |
| `docs/data/IBKR_NEWS_API_LIMITATIONS.md` | [454][ibkr-doc] | Repoint the current Finnhub fetch/parse note; leave unrelated IBKR capabilities alone. |
| `docs/design/PROJECT_PRIORITY_MAP.md` | [26][priority], C12-open mentions at 672/728 | Record the actual decision and implementation evidence when completed; do not mark C12 closed from this inventory. |
| `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md` | [C12 row 247][audit-c12] | Preserve the original finding; add/link dated disposition and evidence after approved cleanup, not rewrite history as if it had always been dead. |

Historical listing-authority plans/specs, universe-retirement CLI references
(`docs/superpowers/specs/2026-07-17-db-derived-universe-tickers-core-retirement-design.md:281`),
past C09/C11 reports and evidence snapshots are provenance. Do not mass-rewrite
them merely to get zero matches; update current authorities and add a dated
superseding pointer when needed. This report leaves all of them untouched.

## Retained Data and Operational Boundary

The old code owns these path patterns:

| Artifact | Source evidence | Required disposition |
| --- | --- | --- |
| `data/news/raw/polygon/YYYY/YYYY-MM.parquet` | [P config][p-config], [P storage][p-storage] | Leave all existing files in place, with no rewrite, renaming to Massive, compaction, purge or implicit import. |
| `data/news/raw/finnhub/YYYY/YYYY-MM.parquet` | [F config][f-config], [F storage][f-storage] | Same. Old Finnhub collection writes the end-date month bucket ([F collection][f-collect]); do not repartition old files during code removal. |
| `data/news/metadata/polygon_collection_checkpoint.json` | [checkpoint][p-checkpoint] | Retain bytes; deleting code must not call `CheckpointManager.clear()` or unlink it. Do not interpret it as normalized continuation automatically. |
| `data/news/metadata/collection_stats.json` | [P stats][p-stats] | Retain; remove only future old-writer execution. |
| `data/news/metadata/finnhub_collection_stats.json` | [F stats][f-stats] | Retain; no reset or migration by C12. |
| Existing local/normalized news, relations/bodies/maps, FTS, sync/job/scheduler state | [current writers][sched-writer], [direct writer][direct-writer], [projection][projection] | Keep current writes and reads, identities, cursors, historical telemetry and data. No schema/data disposal, source-key migration or route-setting edits. |

Code deletion is not data retirement. Do not infer that all old Parquet articles
are already in the local store, or that retained files are automatically visible
in the current app. That completeness question would require separately
authorized data inspection; it is not answered here.

Do not disable, restart or run ongoing SA/news/prices collection; change active
scope/permissions; touch production configuration/environment/credentials; or
remove SA sources because old collector scope helpers disappear. The scheduler
and `daily_update` already own shared active-universe resolution. Preserve
provider-specific dispatch and existing rows while changing code ownership.

Closeout requires a recorded CLI capability decision, physical old executable
and writer removal with both live factories rehomed, truthful operator docs and
status, updated collateral tests, positive current-route controls and
temporary-fixture retained-data checks. This inventory supplies source evidence;
it supplies no test-pass, live-provider, stored-data-completeness or C12-closure
claim.

## Source Links

[audit-c12]: /tmp/arkscope-research-output-boundary/docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md:247
[audit-close]: /tmp/arkscope-research-output-boundary/docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md:291
[p-header]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:1
[p-config]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:83
[p-model]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:109
[p-limiter]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:141
[p-checkpoint]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:182
[p-client]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:215
[p-month]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:234
[p-fetch]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:254
[p-parse]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:344
[p-storage]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:405
[p-env]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:662
[p-months]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:673
[p-month-call]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:775
[p-checkpoint-clear]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:793
[p-stats]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:836
[p-main]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:944
[p-cli-inc]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:1025
[p-cli-collect]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:1073
[p-guard]: /tmp/arkscope-research-output-boundary/src/collectors/polygon_news.py:1084
[f-header]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:1
[f-config]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:79
[f-model]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:98
[f-limiter]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:130
[f-client]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:170
[f-fetch]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:189
[f-parse]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:230
[f-storage]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:299
[f-env]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:486
[f-collect]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:521
[f-stats]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:613
[f-inc]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:629
[f-main]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:683
[f-cli-inc]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:750
[f-cli-collect]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:775
[f-guard]: /tmp/arkscope-research-output-boundary/src/collectors/finnhub_news.py:786
[provider-map]: /tmp/arkscope-research-output-boundary/src/news_providers.py:36
[provider-factory]: /tmp/arkscope-research-output-boundary/src/news_providers.py:81
[normalized-map]: /tmp/arkscope-research-output-boundary/src/news_normalized/provider_adapters.py:38
[normalized-fetch]: /tmp/arkscope-research-output-boundary/src/news_normalized/provider_adapters.py:118
[normalized-cursor]: /tmp/arkscope-research-output-boundary/src/news_normalized/writer.py:94
[normalized-store-cursor]: /tmp/arkscope-research-output-boundary/src/news_normalized/store.py:207
[direct-writer]: /tmp/arkscope-research-output-boundary/src/news_direct.py:100
[projection]: /tmp/arkscope-research-output-boundary/src/news_normalized/legacy_projection.py:33
[local-backend]: /tmp/arkscope-research-output-boundary/src/tools/backends/local_market_backend.py:38
[news-queries]: /tmp/arkscope-research-output-boundary/src/tools/backends/sqlite_backend.py:159
[routing-policy]: /tmp/arkscope-research-output-boundary/src/news_normalized/routing.py:46
[sched-sec]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:132
[sched-sources]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:139
[sched-factory]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:435
[sched-writer]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:466
[sched-classify]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1015
[sched-route]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1053
[sched-block]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1234
[sched-normalized]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1275
[sched-direct]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1332
[sched-adapter]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1431
[sched-tick]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1792
[sched-status]: /tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:1855
[schedule-api]: /tmp/arkscope-research-output-boundary/src/api/routes/schedule.py:58
[daily-stale]: /tmp/arkscope-research-output-boundary/src/daily_update.py:33
[daily-status]: /tmp/arkscope-research-output-boundary/src/daily_update.py:123
[daily-show-status]: /tmp/arkscope-research-output-boundary/src/daily_update.py:250
[daily-flags]: /tmp/arkscope-research-output-boundary/src/daily_update.py:358
[daily-scope]: /tmp/arkscope-research-output-boundary/src/daily_update.py:414
[daily-exec]: /tmp/arkscope-research-output-boundary/src/daily_update.py:453
[daily-finish]: /tmp/arkscope-research-output-boundary/src/daily_update.py:501
[test-collectors]: /tmp/arkscope-research-output-boundary/tests/test_collector_adapters.py:22
[test-env]: /tmp/arkscope-research-output-boundary/tests/test_collector_load_env.py:25
[test-providers]: /tmp/arkscope-research-output-boundary/tests/test_news_providers.py:10
[test-normalized-providers]: /tmp/arkscope-research-output-boundary/tests/test_news_normalized_provider_adapters.py:3
[test-direct-parity]: /tmp/arkscope-research-output-boundary/tests/test_news_direct.py:73
[test-active-universe]: /tmp/arkscope-research-output-boundary/tests/test_active_universe.py:455
[test-terminal]: /tmp/arkscope-research-output-boundary/tests/test_security_lifecycle_terminal_workflow.py:83
[test-native-sentiment]: /tmp/arkscope-research-output-boundary/tests/test_legacy_score_retirement.py:124
[test-score-path]: /tmp/arkscope-research-output-boundary/tests/test_legacy_score_retirement.py:210
[test-no-provider-import]: /tmp/arkscope-research-output-boundary/tests/test_trading_day_coverage.py:685
[test-daily]: /tmp/arkscope-research-output-boundary/tests/test_daily_update_wrapper.py:62
[test-brand]: /tmp/arkscope-research-output-boundary/tests/test_massive_brand_surface.py:44
[test-scheduler]: /tmp/arkscope-research-output-boundary/tests/test_data_scheduler.py:115
[test-sec]: /tmp/arkscope-research-output-boundary/tests/test_sec_research_schedule_runtime.py:101
[readme-operator]: /tmp/arkscope-research-output-boundary/README.md:58
[structure]: /tmp/arkscope-research-output-boundary/PROJECT_STRUCTURE.md:18
[smoke]: /tmp/arkscope-research-output-boundary/docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md:13
[catalog]: /tmp/arkscope-research-output-boundary/docs/design/ARKSCOPE_PROVIDER_CATALOG.md:158
[vision]: /tmp/arkscope-research-output-boundary/docs/design/DESKTOP_APP_VISION_DRAFT.md:228
[ibkr-doc]: /tmp/arkscope-research-output-boundary/docs/data/IBKR_NEWS_API_LIMITATIONS.md:454
[priority]: /tmp/arkscope-research-output-boundary/docs/design/PROJECT_PRIORITY_MAP.md:26
