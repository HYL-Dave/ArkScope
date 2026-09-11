# Pre-Release Abandoned-Surface Audit

Observed: 2026-09-10. Source tree: `fef26dcf` on
`codex/listing-sec-macro-convergence`; main worktree remains separate.
Status updated September 11: **first leaf batch, bounded SEC intake/execution/UI,
neutral journal codec, five further unused HTTP entries, obsolete fixed
orchestrator, test-only wrappers and spent operators/scheduler cleaned up;
current journal/review extraction and SEC configuration/path foundation are
implemented and verified. The C08 and pure SEC source-parser batch has
passed independent review and fresh full verification (8,292P / 12 unchanged S).
Wider cleanup and actual data disposition stay open**.
The original findings below are a dated source inventory, not all-complete
status. Implementation and verification details: [leaf-cleanup.md](leaf-cleanup.md)
and [SEC entrypoint cleanup](sec-entrypoint-cleanup/README.md). The preceding
[helper cleanup checkpoint](sec-retention-helper-cleanup/README.md) records
7,971 passed/12 skipped at `0c5896a5`, separate follow-up verification, the first
unavailable read and the subsequently authorized WAL/SHM-assisted inventory.
The [actual retention manifest](sec-retention-helper-cleanup/retention-manifest.md)
records seven absent old-web tables but populated shared cases/history. Do not
treat the failed first read or an absent old journal as empty shared data.
The latest [obsolete execution cleanup](obsolete-execution-cleanup/README.md)
records the source-only continuation through `38319f16`: fresh full backend
7,966P/12S, exact7,978-node accounting, no new census candidates and explained
remaining review-required deltas. It performs no renewed production inventory.
The next [current journal cleanup](current-journal-cleanup/README.md) removes the
old journal/schema/migration and directly owns retained current review/history.
Its strict readback transfer also required producer interruption fixes and
case-correct external-FK retention. The new SEC capacity/path modules are only
a foundation, not a working catalog/facts/document service. See that batch for
its own frozen review and verification; do not reuse the preceding test counts.
That batch's fresh complete backend is **8,116 passed / 12 unchanged skips**,
with 8,128 exact collected/executed nodes and 191 removed / 341 added IDs.

The current [structured-source core and C08 follow-up](../2026-09-11-sec-structured-source-core/README.md)
adds exact raw JSON/catalog/fact parsing without registering unfinished tools.
It also archives an executable form of the exact SQLite UPSERT reproducer and
confirms that main's tracked audit files are not disposable bytecode. Its own
complete run has 8,304 exact collected/executed nodes, 5 removed / 181 added,
and unchanged source/test bytes; prior counts above are historical evidence.

| Candidate | Current disposition | Commit |
| --- | --- | --- |
| C01 | Company-event collector, scheduler registration and Settings source removed; current admission is unconditional; actual stored settings/schema disposition remains open | `06511f44` |
| C02 | Dormant edgartools module physically deleted; active SEC clients retained | `300b7400` |
| C04 | Current execution owner and neutral codec extracted; old case-web execution/UI and five individually reviewed HTTP entries removed. Current shared history/confirmation readers and schema disposition remain | `83eeb5ef`, `302106d2`, `5d41f570`, `0c5896a5` |
| C04 follow-up | Fixed two-call orchestrator physically deleted; current agent owns cancellable source reads and retains four-channel behavior. Shared journal readers/writers and disposition remain separate | `38319f16` |
| C04 current journal | Old store/review/projection/schema/migration and orphan two-phase usage helpers removed; current review/history/source/usage owners transferred and verified. No actual-store disposal | `e2f77cb7`; [evidence](current-journal-cleanup/README.md) |
| C05/C06 | Six test-only macro delegates and two unused subprocess wrappers removed; current macro execution, sanitized workers and daily CLI retained | `36dac28d` |
| C14/C16 | Three spent audit CLIs, empty audit package and independent monitor scheduler removed; live SA reconciliation and monitor engine/job/tools retained | `2f80f452` |
| C07 | Unreachable auth factory placeholder/export removed; six real modes retained | `263c21a5` |
| C08 | Unused OpenAI synchronous entrypoint/export and five sync-only test nodes removed; current async/stream and Anthropic synchronous Research retained, 16 retained ASTs identical | `41ab878e`; [evidence](../2026-09-11-sec-structured-source-core/README.md) |
| C17 | Old publisher-acquisition adapter deleted; current investigation news retained | `300b7400` |
| C18 | Disconnected SEC earnings parser/CLI and catalog claim removed | `300b7400` |
| C19 | Unused repair facade deleted; current identity planner/admin retained | `300b7400` |

The first five leaf dispositions passed the scoped RED/green/mutation checks, full
backend selection with documented harness-correction follow-up, and independent
review. Other candidates keep their existing retention/extraction/data-disposal
boundaries. No production data, schema, provider call, merge or push was involved.
The C01 checkpoint has its own scoped regression and independent review, recorded
in the entrypoint cleanup evidence. `0ee801cd` also removes the current API
specification's abandoned edgartools recommendation; the old inventory below is
preserved as evidence of the original finding, not current guidance.

Follow-up: the mechanical census below extends the original C01-C13 audit at
`8ebdb8ba`. Its scanner is maintenance/test tooling, not product execution.
Do not read the original dated test results as verification of later cleanup.

## User Decision

ArkScope has no released compatibility population to support. Permanently
abandoned functionality should be deleted from runtime code, tools, routes,
schedules, Settings and current schema, not retained as a disabled/retired shell.
Old SEC company-event intake is abandoned. SEC financial research is a new
feature, not its renamed successor and not another lifecycle authority.

This decision does not authorize wiping existing prices, news, SA captures,
credentials, routes, research conversations or membership removals. Nor does
it make domain states such as retired models or Former-pick tombstones obsolete
code. Current consumers and retained-data dependencies decide the removal order.

## Method And Limits

Repository-wide name/import/call-site searches covered application Python,
`data_sources/`, frontend code, current skills, tests, dependencies and relevant
design/entrypoint documentation, with a residual-name sweep of extension and
desktop sources and the remaining tracked code roots. An independent backend audit cross-checked
non-SEC candidates. Findings below distinguish a leaf with no current caller
found from a coordinated retirement and a still-required component. Static
search is not proof against every possible dynamic/plugin import; each removal
must verify its actual current entrypoints and regression owners first.

No production database, private `.env`, token store or provider was read. No
App was started/restarted and no collector/schedule was executed. The historical
36-case count is not a fresh production measurement. This is not a full security
audit or a claim that every unreachable symbol in the repository has been found.

## Review Corrections

- The three category assertions really exist: `test_sec_tools.py:156`,
  `test_tools.py:227`, `test_analyst_tools.py:293`, all `analysis == 15`.
  The three new tools belong to `analysis`, giving 15 -> 17. Together with
  17 total-count assertions there are 20 sites across eight files.
- `ProfileStateStore.get_setting/set_setting` use string key/value storage.
  `PortfolioObservationStore.set_settings` does **not** wrap that storage: it
  writes the dedicated `portfolio_capture_settings` table. The new SEC config
  module will own a typed accessor over `profile_settings`; no generic typed
  configuration framework currently exists.
- `CREATE TABLE IF NOT EXISTS` leaves an incompatible existing definition alone.
  An in-memory SQLite probe created `(id, value)`, then executed a definition
  containing `new_field`; `PRAGMA table_info` still returned only `id, value`
  and the existing row remained. Canonical schema creation is not schema repair.
- An installation-table name alone does not prove valid lifecycle installation;
  `cutover_active` verifies the schema/journal. This audit did not inspect the
  user's installed state.
- `compose_security_lifecycle` adds provider-check observations independently of
  that flag. The flag still affects SEC filtering and the automation filter.
  Therefore "no cutover means no listing-authority path at all" is too broad.
  No old-SEC compatibility fallback is required by the user's current decision.

## SEC And Lifecycle Removal Boundary

### C01: Old Company-Event Intake Is Still Product-Exposed

Evidence: `src/collectors/sec_corporate_actions.py:274` remains callable;
`src/service/data_scheduler.py:169` still registers its SourceDef, adapter and
universe scope. The collector returns retired only after the lifecycle gate.
The source also remains in `settingsBackendCopy.ts`, `settingsReadCache.ts` and
the English/Traditional Chinese Settings dictionaries.

Remove the collector, SourceDef/provider mapping, old source settings, direct
dispatch and UI descriptions. No permanent retired/no-op wrapper or copied
schedule-enabled flag. Current listing-authority checks and financial consumers
must continue unchanged. Existing owners to replace or preserve include
`test_sec_corporate_actions.py`, `test_data_scheduler.py`,
`test_lifecycle_investigation_retirement.py`, `SettingsProviderConfig.test.ts`
and `settingsBackendCopy.test.ts`. Journal-absent fixtures must prove the old
feature cannot return, not exercise an unreleased compatibility edition.

### C02: Dormant Edgartools File Has Only A Test Import

`data_sources/sec_filings.py:34` imports `edgar` and defines the unused
`SECFilingsClient`. `tests/test_sec_user_agent.py:44` still imports the file
solely to test its identity helper. Current `src/` consumers are forbidden by
`test_sec_transport.py`'s existing guard; edgartools is not in requirements.

Delete the module and the obsolete test-only dependency. Preserve active contact
identity/HTTP-governor tests and add an absence/import guard rather than keeping
dead code for a test. Do not uninstall development-environment packages as a side
effect of source cleanup.

### C03: Two Catalog Paths Have Different Behavior

`src/tools/sec_tools.py::get_sec_filings` is a functioning registered direct
EDGAR tool. In contrast, `src/api/routes/fundamentals.py:55` ->
`analysis_tools.get_sec_filings` -> DAL -> LocalMarketBackend ->
`FileBackend.query_sec_filings` ends in an empty DataFrame. No current frontend
caller of that old HTTP metadata route was found.

The new three-tool integration removes the empty route/DAL forwarding chain
and replaces the functioning catalog tool atomically. Seven current skills
still mention `get_sec_filings`: dcf-model, competitive-analysis, comps-analysis,
earnings-analysis, catalyst-calendar, full-analysis and earnings-prep. Their
metadata and prose, both API bridges, both OAuth allowlists, deep_researcher,
tool catalog and all 20 count assertions belong to that same change.

### C04: Old Web Investigation Cannot Be Deleted By Filename

The old router remains included by `src/api/app.py` and its launch route uses a
cutover-dependent 410 response. The new implementation still depends on it:

| Current consumer | Still imports/uses |
|---|---|
| `src/lifecycle_investigation/controller.py:47` | Inherits `LifecycleWebController` |
| `src/api/routes/lifecycle_investigation.py:11` | Old router's `ConfirmWebRequest` |
| Investigation agent/store/findings | Web dispatch/model/usage, digest helpers, finding schema and guarded source reads |
| Investigation adoption and current transition/review | `lifecycle_web_review` acceptance/freshness/provenance helpers |
| `src/ticker_identity_history.py` | Old web journal/page/run data for historical provenance |
| Investigation acceptances schema | FK to `security_lifecycle_assessments` |

Extract the current primitives into their real owners first, then remove the old
router/App hooks/launch implementation. `CurrentLifecycleView.tsx` has no current
non-test importer found; it alone mounts `LifecycleWebPanel.tsx` and
`CurrentLifecycleAudit.tsx`. All three are removal candidates. The barrel re-export
of `translationFailurePresentation` only serves tests outside the old UI; that
does not establish live audit rendering. Preserve `InvestigationView`'s actual
`TrackingHistory`/decision view, confirmation, cancellation, adoption and reversal
flows with behavior tests after extraction.

`src/lifecycle_investigation/disposal.py` already supplies FK-aware disposition,
immutable digest-bound receipts, WAL backups and resumable profile/market stages.
It can discard unneeded intake rows while retaining human acceptance/dependencies;
it does not remove all old table definitions. Reuse its useful operator primitives
for the actual-store cleanup, then remove spent conversion entrypoints after
verified rollout. Do not add a second generic migration framework or drop every
`security_lifecycle_*` table: listing assessments and current investigation use
that shared schema today. Move required historical references before deleting
obsolete tables; do not preserve an executable old feature to keep history readable.

## Non-SEC Candidates

These are scoped follow-ups, not part of SEC research acquisition. No runtime
code in this table was changed by this audit.

| ID | Evidence and current status | Removal boundary and regression owner |
|---|---|---|
| C05 | Six `_run_fetch_*` delegates in `src/service/jobs.py:515` onward are used by tests; product job dispatch and recurring macro sources call `execute_macro_job` directly. These wrappers were retained in the current convergence branch, not just old debt. | Remove delegates and move existing ingestion/argument tests to the current job entrypoint. Keep all six named jobs and truthful partial/failed behavior. Owners: `test_fred_ingestion.py`, `test_finnhub_ingestion.py`, `test_macro_scheduler_integration.py`. |
| C06 | `data_scheduler._run_subprocess` and `daily_update.run_command` have no current production call sites found. Scheduler tests still monkeypatch the former. | Remove unused generic subprocess helpers and obsolete patch sites. Preserve current sanitized workers and test their actual dispatch, timeout and environment boundary. Owners: `test_data_scheduler.py`, `test_daily_update_wrapper.py`. |
| C07 | `auth_drivers.factory.NotImplementedDriver`, `_MODE_SLICE` prose and the return annotation still describe an inert skeleton. Every allowed provider/auth pair now returns a real driver; invalid pairs reject. | Delete the placeholder/export/unreachable fallback and stale prose, use the current driver protocol, preserve exact provider/auth validation. Owners: `test_auth_factory.py`, `test_api_key_drivers.py`; don't remove OAuth or API-key paths. |
| C08 | OpenAI `run_query_sync` is exported but only used by tests in the scanned repo; current API uses async/streaming paths. | Candidate for removal with exports and synchronous-only test branches. Preserve runtime model/auth binding tests on actual routes. Anthropic's synchronous `run_query` has real callers and is not the same candidate. Owners: `test_task_runtime_binding.py`, `test_legacy_agent_surface_retirement.py`. |
| C09 | Old `EODHDDataSource`, `AlphaVantageDataSource`, `FinnhubDataSource` and factory/package exports form a mostly disconnected cluster; the factory's found test consumer builds Polygon. | Remove only obsolete classes/factory paths after validating imports and intended module CLI entrypoints. Preserve `PolygonDataSource`, current EDGAR classes and the current EODHD lifecycle transport in `data_sources/lifecycle_provider_census_transport.py`. This does not remove EODHD Settings/key support. Owners: `test_data_provider_config.py`, `test_ibkr_source_import_safety.py`, `test_lifecycle_provider_census_transport.py`. |
| C10 | `FileBackend` retains empty price/fundamentals methods. LocalMarketBackend has live SQLite prices and financial-cache access, but its `query_fundamentals` also returns `{}` unconditionally; useful financial analysis is the separate SEC/cache path in `analysis_tools`. The old SEC catalog chain still delegates to FileBackend. | Coordinate empty-method/protocol/backend deletion with C03; preserve the actual price DAL and independent financial analysis/cache. `test_eir006_retired_data_boundaries.py` currently protects compatibility wording, so change that obsolete contract explicitly while preserving truthful real reads. Owner also `test_data_access.py`. |
| C11 | `news_providers.use_local_news_enabled` promises `false` restores collector storage. `resolve_news_write_route` validates the flag but falls through to direct-local even when it is false; status consumers still use the separate boolean. | A real routing/diagnostic contract mismatch, not just an unused symbol. Converge current writer selection and status/Settings, then delete rollback semantics. Do not disable news or remove currently required normalized-to-news projection. Owners: `test_news_settings_route.py`, `test_news_providers.py`, `test_provider_health.py`, `test_news_sync_status.py`. No live UI claim from this static finding. |
| C12 | Polygon/Finnhub `run_incremental` still have module CLI consumers writing the old collector storage; the App uses normalized/direct-local branches. | They are not unreachable leaves. Remove or reroute old collector CLI/writer paths together, preserving provider fetch/parse reused by `src/news_providers.py`. Never delete already-collected files as a consequence of code deletion. Owners: `test_collector_adapters.py`, `test_data_scheduler.py`, `test_news_normalized_provider_adapters.py`. |
| C13 | `.page-head` rules in `styles.css:950` and responsive rules have no matching current TSX consumer found; current `.ui-page-header` and `.detailpage-head` are different live selectors. | Already owned by `ENGINEERING_ISSUE_REGISTER.md` EIR-001. Revalidate and remove in that maintenance batch with layout checks, not another duplicate issue. |

The current priority-map premises also retained an August 17 queued-model
description saying Opus 5 was absent and Spark was only a candidate. That text
no longer describes the current registry/workstream; replace it with current
authority pointers rather than maintaining a second stale model roster.

## Required Retention Is Not Abandoned Compatibility

- `news_normalized/legacy_projection.py` still feeds `news`/`news_fts`, which
  `SQLiteBackend.query_news/search_news` currently reads. Deleting it alone
  would hide new news from current consumers. Finish the reader transition and
  preserve IDs/links before removing that projection.
- `security_lifecycle_*` assessments, applied transitions, reversal receipts and
  Former membership tombstones have current consumers. They are not disposable
  because their name contains an old subsystem prefix.
- Model lifecycle rows marked retired preserve provenance and reject obsolete
  routes. This is a domain policy, not an unused collector left callable.
- Explicitly deferred capabilities such as sandboxed Python re-admission are
  not permanently abandoned simply because they are unavailable to agents today.
- `env_keys.py` still has live consumers. Its removal requires the separately
  owned profile-credential-authority transition, not a blind deletion or reading
  private `.env` contents during this audit.
- Current provider SDKs and Native Messaging host/addon identifiers remain real
  integration contracts. No package or external identifier is removed based on
  a legacy-name search alone. `compat_firefox.js` is loaded by the current Firefox
  manifest/build, and `attachExtensionRunProtocol` still wraps live extension runs;
  their compatibility/legacy names do not establish abandonment.
  Archived documentation/evidence is provenance,
  while current entrypoints/specs must stop advertising abandoned functionality.

## Implementation Order And Completion Gate

1. Delete verified leaf residue in a bounded maintenance batch (C02, C05-C08,
   and C13 under its existing EIR owner); retain behavioral tests at live owners.
   C09 needs its import/CLI boundary checked before joining that batch.
2. Remove the old company-event source/settings/UI and disentangle old web
   investigation from current execution/history (C01/C04). Inventory current
   schema and authorize a digest-bound actual-store disposition, then remove
   old structures. No new research feature is needed to justify the old intake.
3. Build the new SEC research service with the C03/C10 catalog replacement;
   all three tools, seven skills, four transports and data/citation owners must
   land together. The revised SEC spec owns that implementation plan.
4. Converge remaining news rollback/CLI/reader boundaries (C11/C12 and the live
   projection), independently of SEC. Do not make this a prerequisite to all
   other work or delete current news reads to obtain a clean grep.

The priority map owns these workstreams; this audit is their dated evidence,
not a second backlog. For every removal, report deleted runtime surfaces and
test-count changes with their source. Require positive controls for the live
replacement, absence owners for removed entrypoints and retained-data checks.
"No provider calls" or passing old tests is not evidence that cleanup happened.

## Mechanical Census Follow-Up

The review correctly identified a coverage gap in the original manual inventory.
It did not establish that every additional candidate is abandoned. In particular,
`korean-lunar-calendar==0.4.0` is **required indirectly**, not unused:
installed `exchange-calendars 4.13.2` declares
`korean_lunar_calendar>=0.3.1`. The live calendar imports exchange_calendars,
and `tests/test_market_coverage_dependencies.py` owns that reviewed dependency
set. Modern wheels can omit `top_level.txt`; the scanner also examines installed
wheel RECORD metadata rather than incorrectly treating those packages as unused.
No installed package code is imported for dependency discovery.

### Reproducible Method

- `tests/repository_inventory.py` enumerates **tracked working-tree files** with
  `git ls-files -z`, records inclusion/exclusion/read status and SHA-256 per read
  file, and parses Python using `ast`. It records relative imports, re-exports,
  literal dynamic imports, unresolved loaders, test-only references and possible
  CLI/module-launch witnesses. An import edge is not whole-program reachability.
- `tests/repository_sql_inventory.py` creates only disposable `:memory:` SQLite
  schemas, prepares literal queries with `EXPLAIN`, and records SQLite-authorizer
  reads/writes, triggers and foreign keys. It never opens product databases.
  SQLite-managed FTS shadow tables are not unused-table candidates. Dynamic SQL,
  unpreparable queries and unresolved database ownership remain explicit gaps.
- `apps/arkscope-web/scripts/maintenance/frontend-inventory.mjs` uses the existing
  TypeScript parser on supplied source strings, not application execution. It
  inventories all three package manifests (including the root workspace), script
  and config references, both locales' leaf keys, translation references, HTTP
  clients and CSS selectors. It does not resolve cross-file translator dataflow,
  evaluate arbitrary shell scripts or fully implement CSS selector semantics.
- Python settings accessors and FastAPI decorators are enumerated. Dynamic keys
  remain unknown; raw SQL is covered separately. HTTP matching is method-aware
  but router-local and syntactic: no frontend caller is **not** evidence that
  Native Messaging, a job, an external client or a dynamic wrapper cannot use it.
- Private config/data and dependency/build directories are excluded explicitly.
  Historical evidence and design Markdown are not scanned as executable import
  consumers. Otherwise, thousands of archived source-manifest strings would make
  deleted/dead modules appear used. Current runbooks and documented deferred
  capabilities are checked manually during candidate disposition.
- Main-worktree untracked files are enumerated by **name only**, not read or
  deleted. The observation contains 15 files, not two: directory-level
  `git status` entries are not a file count. Ignored private files are not
  enumerated. This does not authorize deleting the user's private work.

### Rerun And Review

Use the existing project Python environment (including `packaging`) and Node
with the web workspace's existing `typescript` installed. No application server
or provider credentials are required. Stage newly created scanner/source files
before running: untracked contents are intentionally outside the census.

```bash
python -B -m tests.repository_inventory --root . --output /tmp/arkscope-inventory.json.gz
python -B -m tests.repository_inventory --root . --output /tmp/arkscope-inventory-next.json.gz --compare /tmp/arkscope-inventory.json.gz
python -B -m pytest -q tests/test_repository_inventory.py
node --test apps/arkscope-web/scripts/maintenance/frontend-inventory.test.mjs
```

Reports are create-only. `--compare` exits 2 for new candidates, new uncertainty,
narrowed source coverage, new untracked names or changed dependency metadata;
it does not silently update a baseline. Exit 0
means the observation/comparison completed, **not that the repository contains
no dead code**. The checked-in census is an observation baseline, not an allowlist
of approved deletion or a waiver for unresolved references. `--skip-frontend`
records an explicit incomplete scan. Input/parse failures cannot become clean
coverage. Changes in scanner scope or installed dependency metadata must be
reviewed alongside candidate deltas.

The full source manifest, evidence locations and unresolved sites are retained
in `mechanical-census.json.gz`. `mechanical-summary.json` contains the compact
counts and validation results. Counts describe **source observations**, not the
shape or contents of the user's live databases.

### Observed Coverage And Verification

| Axis | Observed coverage | Interpretation |
|---|---|---|
| Python | 720/720 files parsed | Includes tests and operator/build entrypoints; not a call-graph proof. |
| Frontend | 321 files: 293 source, 16 locale resources, 6 CSS, 3 manifests, 3 configs; zero parse errors | All supplied files and unsupported kinds are recorded. |
| Dependencies | 25 Python declarations, 15 npm declarations | Import, transitive, tooling and unknown evidence stay distinct. |
| i18n / CSS | 5,968 locale leaf keys, 1,260 selectors | Dynamic/reference gaps remain; these counts are not unused-code counts. |
| Settings | 3 resolved literal accessor keys, 16 dynamic accessor sites | Does not claim that the application has only three settings. Raw SQL/generic access remains separately unresolved. |
| SQL | 2,820 sites; 1,434/1,901 literal queries preparable against 140 unscoped table shapes | Not a live DB inventory; includes engine-managed and temporary schemas. |
| HTTP | 224 decorators, 158 syntactic frontend matches | Remaining 66 need review, not deletion; mounted/dynamic/external consumers are not fully resolved. |
| Untracked | 15 main-worktree file names | Contents untouched; two porcelain entries included a directory. |

There are 4,350 candidate-or-unresolved rows (4,324 distinct IDs) and 3,471
uncertainty sites, **not thousands of proven abandoned objects**. The 1,124 read
files have content hashes. Three historical Markdown files outside `docs/`
could not be decoded as UTF-8; those are retained explicit coverage gaps.

Verification: **35 Python tests + 24 Node tests passed**. The fresh Python run
uses `--noconftest`, no pytest plugin autoload and a socket-connect/name-resolution
audit guard; it needs no product imports or database fixture. Node tests run the
parser/CLI on synthetic supplied strings. The full census repeats identically
apart from its additional comparison envelope; unchanged comparison exits 0.
Comparing against the earlier deliberately incomplete Python-only observation
exits 2 (4,103 new candidates and 2,203 new uncertainty sites). The CLI exit-code
owner also fails under a reverse mutation that silently returns 0 for new
candidates, then passes after restoration.

An independent scanner review found nine issues involving private filename
variants, metadata loss, Python constant/import scope, translator escapes/scopes,
workspace ownership and SQLite trigger/statement-cache witnesses. Each original
repro now has regression coverage; bounded independent recheck found no remaining
required fix among those nine. This is not a new whole-product/security review.

### Additional Candidate Disposition

| ID | Mechanical evidence and source recheck | Disposition and regression boundary |
|---|---|---|
| C14 | Three `src/audit/` operator modules: article reconciliation has no inbound module reference; universe retirement and IBKR news catch-up are test-only. All three have real CLI main guards, so zero imports alone was insufficient. The priority map calls the historical IBKR catch-up audit closed/runbook-only. | Remove spent entrypoints and their obsolete CLI tests in the cleanup batch, retaining dated receipts. Keep the **different, live** `src/sa_article_reconciliation.py` and current SA backend reconciliation operations. No operator command is executed just to decide whether its source can be deleted. Owner: new `test_abandoned_surface_cleanup.py`, existing `test_universe_retirement_audit.py` and `test_ibkr_news_catchup_audit.py`. |
| C15 | `massive_config_migration.py`, `security_lifecycle_migration.py`, `security_lifecycle_automation_migration.py`, `security_lifecycle_provider_migration.py`, `ticker_identity_migration.py`, `security_lifecycle_retirement.py` and the old `security_lifecycle_provider_census.py` are test-only at this module boundary. They are separate from the current listing-authority census/transport. | Remove obsolete version-conversion and old canary entrypoints after moving any still-needed canonical-schema, backup or retained-data regression owners. Do not delete current schema/transition modules, `lifecycle_provider_census_transport.py`, current lifecycle installation/disposal tooling needed for this rollout, or receipts. Each removal must identify which old-schema tests disappear and which current-schema tests remain. |
| C16 | `src/monitor/scheduler.py::MonitorScheduler` has only test importers. Product monitoring calls `MonitorEngine` through `src/service/jobs.py` and `src/tools/monitor_tools.py`; the independent scheduler is not their owner. | Delete the unused scheduler and its scheduler-only tests, preserving monitor jobs, watchers, notifications and tool behavior. Owners: `test_monitor.py`, `test_legacy_agent_surface_retirement.py::test_monitor_engine_and_scheduler_remain_available` and new `test_abandoned_surface_cleanup.py`. The old preservation test must deliberately move to the live job/engine owner, not just disappear. |
| C17 | `src/security_lifecycle_news_evidence.py` explicitly describes a retired publisher-acquisition adapter retained for history tests; only its own tests import it. | Physical removal is consistent with the user's decision. Replace its test-only retirement-status contract with absence of the old execution path. Preserve current investigation local-news search and captured finding/history readers, which do not need this acquisition adapter. Owner: `test_security_lifecycle_news_evidence.py` and current investigation-agent tests. |
| C18 | `data_sources/sec_earnings_releases.py` has a module CLI and test-only references; the provider catalog still advertises it with dormant edgartools. No current tool/route imports its press-release function. | Coordinate removal of the obsolete parser/CLI/catalog claim with SEC cleanup. Preserve the active EDGAR source, financials and insider-trades consumers. The new SEC research service must not silently call this old parser as a fallback. Owner: `test_sec_transport.py`, `test_sec_user_agent.py`, new SEC service tests. |
| C19 | `src/news_identity_repair.py` is test-only; actual market-data administration calls `src/news_identity.py` directly. | Remove the unused standalone repair facade while retaining the active identity planner/application logic and its data-preservation tests. Owners: `test_news_identity_repair.py`, `test_news_identity.py`, market-data administration tests. No historical news row is changed by deleting the facade. |
| C20 | `AppRecordsLocalStore` still declares `agent_queries` and provides insert/count/migration helpers; found direct callers are tests. Literal SQL scan shows no reader, but generic `count/raw_rows` can read it dynamically. | Candidate schema/API cleanup, **not an approved DROP**. Inventory actual retained rows before disposition; keep `research_reports`, `agent_memories`, current Research conversation records, citations and usage. This is a concrete example where static no-reader does not prove no stored-data dependency. Owner: `test_app_records_store.py` and current query/history tests. |
| C21 | `src/service/sa_market_news_density.py` is test-only, but `SA_EXTENSION_ROADMAP.md` explicitly retains it for future auto-sync tuning. | Deferred capability, not proven abandonment. Keep under that existing owner until the scope is deliberately cancelled or a real consumer replaces it. Do not silently broaden the user's abandoned-code decision into removal of every deferred capability. |

### CENSUS-SQL-001: SQL Scanner Union-Schema Completeness

Status: **Queued maintenance, not implemented or a passing-test claim.**
Owners: `tests/repository_inventory.py` and `tests/test_repository_inventory.py`.

Complete the scanner's union schema before preparing SQL JOIN read observations.
Acceptance: a dynamically declared joined table must not silently erase an
actual translation-reader observation. If preparation cannot be established,
retain an explicit uncertainty; missing preparation never authorizes deletion.

This item corrects the scanner follow-up's mistaken C21 label. C21 remains the
deferred SA news-density capability above; C01-C21 and all other candidate
dispositions remain unchanged. Existing census measurements and raw
uncertainties are preserved.

### Protected Controls And Remaining Review Queues

- Retain `src/api/__main__.py`, `src/api/app.py`, `src/sa_native_host.py`,
  `extensions/sa_alpha_picks/build_firefox.py`, `src/daily_update.py` and the
  active normalized IBKR worker. CLI/Native Messaging/build entrypoints need
  not have a Python importer. `openai-codex` is the reviewed bundled executable
  dependency; no Python-import match does not authorize its removal.
- All declared npm dependencies have a current use after manual config/type
  review. The scanner leaves `@types/react`, `@types/react-dom` and `jsdom`
  unresolved rather than pretending ordinary imports cover implicit TypeScript
  resolution and Vitest's jsdom environment. No npm removal is proposed.
- i18n keys and CSS selectors without an observed reference remain unresolved
  when translators/classes are dynamic. Scope these to removed UI components
  and their current consumers during cleanup. Do not bulk-delete locale keys
  from this scan or equate syntactic references in tests with runtime use.
- Some current HTTP calls pass a local `path` variable; their concrete route
  cannot be resolved by this scanner. For example, card-generation routes are
  live despite appearing in the no-frontend-match queue. C03's empty `/sec`
  route has an independent DAL/source proof; the scan alone is insufficient.
- Generic database readers, schema markers, staging tables and immutable
  receipts are not abandoned tables. In particular, membership tombstones and
  `sa_tracking_events` are retained intent/provenance, while `*_new` and
  `ticker_tags__v2` can be temporary conversion names. No production table or
  column may be dropped based on this source-only table union.

This completes the repeatable **enumeration phase**, not whole-program
reachability proof or runtime cleanup. C01-C21 are reviewed groups; the detailed
report also keeps unclassified mechanical candidates and uncertainty. The next
bounded implementation is leaf cleanup, then coordinated SEC intake/web
removal and canonical-schema/data disposition, then the new SEC research
service. Unrelated news/provider convergence remains independently owned.

The first bounded RED-first plan is
`docs/superpowers/plans/2026-09-10-abandoned-leaf-cleanup.md`: four disconnected
leaves (C02/C17-C19), then the inert auth factory placeholder (C07). It includes
named absence owners, positive controls and reverse mutations. Other groups
retain their separate disposition/rollout dependencies; no schema or product
code was deleted in this census change.

## Offline Verification Performed

Executed on isolated temporary DB/HOME/lock paths with `.env` loading disabled,
pytest plugin autoload disabled and a Python socket audit hook rejecting network
connect/name-resolution attempts. No provider/production credentials were injected.

```text
tests/test_lifecycle_investigation_retirement.py                          7 passed
tests/test_lifecycle_investigation_cli.py                                 2 passed
tests/test_subagent.py::TestSubagentRegistry::
  test_code_analyst_uses_existing_data_tools_without_python_execution     1 passed
```

Result: **10 passed**, exit 0. The initial run emitted eight unknown-`anyio`-mark
warnings because plugin autoload was disabled. A fresh repeat explicitly loaded
only the AnyIO pytest plugin, used the same temporary-path/no-network boundary
plus a private-file/production-path audit guard, and returned **10 passed in 1.99s**
without warnings. Runner flags: `-q -p no:cacheprovider -p anyio.pytest_plugin
--tb=short`; test selectors are listed above. A source-AST recheck also counted
exactly 17 total plus three analysis assertions and found the seven skill files.
These tests establish the current
disposal/data-preservation and subagent-membership baseline only. They do not
validate future schema dropping, new tools, whole-project cleanup or production
data disposition. No full-suite result is newly claimed for this documentation
revision; the earlier branch verification remains separately dated evidence.

An independent documentation/source review found two scope-description errors:
the old audit component was test/old-view-only, and `query_fundamentals` was still
an empty stub rather than the actual financial-cache path. Both were rechecked
against imports/callers and corrected above and in the spec. No additional
architectural blocker was reported; this is not runtime cleanup acceptance.
