# SQLite Admission Preflight

2026-09-13; `/tmp/arkscope-research-output-boundary`;
source base `5526bc40dc8d62efa6dd819cf1ffc99d8acff7ce`.

## Recommendation

**Prepare a managed SQLite-only upgrade; do not activate the scratch artifact.**
Keep Python 3.10.12 and `numpy==1.26.4` unchanged. The minimum path is a durable,
versioned app-private SQLite library and one installation-owned executable
wrapper selected independently by Electron and SA. Existing executable selectors
support this shape; no whole-project launcher refactor or store rewrite is needed.
That support is not evidence of actual local activation.

**It is not yet only backup + integrity + launch wiring:** production compile
options, packaging/relocation, loader impact and the sanitized analysis-child
exception still need decisions and acceptance. Afterwards, the operational window
can be quiesce/back up/check/switch/verify/resume.

Only this report was written, via `apply_patch`. No actual DB, private selector,
configuration/`.env`, credential material or previous `.superpowers` workspace
was read. No network/provider call, runtime inspection, application launch,
build/install/test, agent or commit occurred. CSS/C11 remain controller-owned.
The current plan's global rules are headed `Constraints` at
`docs/superpowers/plans/2026-09-13-maintenance-closures.md:14`.

## Evidence

`docs/superpowers/evidence/2026-09-12-sec-integration/sqlite-candidate.md:69`
records unchanged `/home/hyl/.virtualenvs/llm_app/bin/python` and unchanged system
`_sqlite3.cpython-310-x86_64-linux-gnu.so` loading 3.53.4 in isolated probes.
The subsequent baseline still loaded 3.37.2. This supports the mechanism on that
Linux install, not either application's actual interpreter selection today.

Historical evidence: five candidate UPSERT cases, eight synthetic cases and
330 disposable application-store tests passed. Not established: all child
engines, full-suite coverage, installed launchers, existing-data health or
deployment. I read tracked identity/linkage/ELF/configure-help receipts under
`docs/superpowers/evidence/2026-09-12-sec-integration/checks/sqlite-candidate/logs/`
and the adjacent `sqlite-application-stores/command.json`/`output.log.gz`;
no historical scratch path was followed.

Target source ID:
`2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc`.
A production build needs its own manifest/hash and fresh acceptance, not just
the scratch binary's old test receipts.

## Exact Entrypoints

Paths/lines below identify source contracts, not inspected private values.

| Entry | Source behavior and minimum admission requirement |
| --- | --- |
| Electron: `apps/arkscope-desktop/main.js:25`, `startSidecar():104` | Selects `ARKSCOPE_PYTHON` or PATH `python`; spawns `-m src.api` with inherited env, repo cwd and reload off. Select the wrapper in the actual desktop launch environment. Do not globally set the loader path on Electron/npm/Chromium. |
| Standalone API: `src/api/__main__.py:15`; uvicorn factory at `src/api/app.py:5` | Independent launch can bypass Electron selection; reload defaults on. Include supported standalone invocations through the wrapper, with production reload off. |
| SA: `extensions/sa_alpha_picks/native_host_launcher.sh:22`, `:37`, `:56`; `src/sa_native_host.py:82`, `:1270` | PATH python3 only parses JSON; persisted `python_path` executes `host_script`. Independently select the wrapper there. Fresh host processes write refresh/failure, details, articles/comments, market news and reconciliation through DAL. API shutdown does not stop them. Direct script/shebang use (`:1`) is another bypass to inventory later. |
| Daily CLI: `src/daily_update.py:327`, `:452` | Calls scheduler `run_source(..., trigger_source="cli")` and writes telemetry; optional threads. Manual/cron/service invocations need the same runtime contract. |
| Prices: `src/service/data_scheduler.py:1348`; `src/prices_runtime.py:161`, `:195` | Child/standalone `sys.executable -m src.prices_runtime` writes prices and repair state. Spawn helper at scheduler `:930` inherits env. The wrapper itself is bypassed, but its loader env propagates; verify the child later, without assuming dispatch must be refactored. |
| Normalized IBKR news: scheduler `:1291`; `src/news_normalized/ibkr_cli.py:235`, `:279`, `:359` | `sys.executable -m src.news_normalized.ibkr_cli`; helper at scheduler `:761` inherits env. Same child-identity requirement; preserve gateway locks and sanitized JSON stdout. |
| Analysis child: `src/tools/code_executor.py:57`, `:85`, `:197` | Closed environment drops `LD_LIBRARY_PATH`; permitted imports include `sqlite3` (`:29`). This is not an OS sandbox. Parent activation does not cover it. Full Python-engine coverage needs a narrowly reviewed trusted-runtime injection/launcher change at this call site, preserving the closed environment. Otherwise explicitly restrict/exclude this path; do not claim every potential writer upgraded. |
| Operator CLI: `src/lifecycle_investigation/__main__.py:12` | `install`/`disposal-stage` write; previews are distinct. Keep maintenance writers stopped; later authorized operations use the admitted interpreter. None is needed for an SQLite engine upgrade. |

**Installed SA:** `extensions/sa_alpha_picks/install.sh:43`/`:61`/`:64`
and `install_firefox.sh:41`/`:59`/`:62` choose Python, copy the launcher
outside the repo and rewrite host JSON. Re-running them can reset the wrapper
selection; Firefox also builds the extension. Do not rerun installers merely
to switch SQLite. Later update only approved selector fields, preserve other
values and document reinstall behavior. `apps/arkscope-desktop/sidecarConfig.js:31`
updates API address/token, not Python; shutdown at `:46` is not an all-writer drain.

**Health false assurance:** `src/service/sa_extension_health.py:532` runs
`[sys.executable, host_script]`, bypassing the installed launcher/selected Python.
SA ping and `/healthz` do not report or enforce SQLite identity.

### Remaining Writer Boundary

API startup performs migration/reconciliation at `src/api/app.py:67`, before
or independently of scheduler disabling at `:131`. Request/background writers
include routes `schedule.py:59`, `jobs.py:202`/`:255`, `research.py:351`,
`portfolio_capture.py:65`, `lifecycle_investigation.py:200`/`:231`,
`sec_research.py:184`/`:286` under `src/api/routes/`.
Scheduler `src/service/data_scheduler.py:1680` also performs SA tracking,
lifecycle and identity work before dispatching writer threads at `:1769`.

Include every existing applicable store in the recovery set; these are defaults,
not actual selected paths:

- `data/market_data.db`: direct prices/news, normalized news, financial cache
  (`src/tools/backends/sqlite_backend.py:546`), SEC install/capture/document
  writes (`src/sec_research/store.py:147`/`:154`) and repair/lifecycle work.
- `data/sa_capture.db`: native DAL, reconciliation, comment backfill,
  recovery/diagnostics; writable connection/schema owner
  `src/sa_capture_store.py:582`.
- `data/profile_state.db`: profile/cards, calibration, portfolio, Research,
  credential/provider/model settings and observations, app records, job/scheduler
  state, tracking/lifecycle/identity. Factories/resolver:
  `src/api/dependencies.py:99` through `:526`.
- `data/macro_calendar.db`: `src/macro_calendar/local_store.py:295` and ingestion;
  `data/cache/analyst_consensus.db`: `src/analyst_consensus.py:147`;
  `<market-parent>/price_repairs/<id>/requests.sqlite3`:
  `src/price_repair_execution.py:145`/`:215`.

Callable lifecycle/identity/Massive migration and restore modules are additional
operator writers, not upgrade prerequisites. Domain flocks and the in-process
financial-cache lock are not a global maintenance barrier. Standalone
`src/collectors/polygon_news.py:944` and `finnhub_news.py:683` write
Parquet/checkpoint/statistics files, not directly SQLite in those modules.
Tracked source cannot enumerate private schedules, ad hoc scripts or external
SQL tools.

## Minimum Engineering Work

1. **Package, not scratch activation.** Stage one immutable versioned library
   outside `/tmp`/`.superpowers`, with manifest, hashes, ownership and relative
   `libsqlite3.so.0` symlink. Candidate SONAME is suitable; RUNPATH is an absolute
   scratch prefix. Tracked configure help supports `--disable-rpath`; rebuild
   accordingly, or separately re-admit an ELF rewrite. Verify another prefix,
   changed cwd and executable/symlink paths. No Electron distribution project or
   relocation of Python is required for this single-install scope.
2. **Local wrapper only.** Select it through existing Electron/SA selectors and
   supported manual commands. Set exactly the trusted SQLite-only lib directory
   before exec of unchanged Python; preserve argv/cwd/signals/stdout and reject
   missing/wrong artifacts before application writes. Keep its version immutable
   for the entire running process generation. The library's own RUNPATH does
   not redirect Python's `_sqlite3`; a venv alone does not privatize that library.
3. **Loader scope.** The override affects every dynamic consumer in that Python
   process and inheriting descendants, not only DB-API. Final acceptance must
   cover normal native imports and optional SQLite symbols, plus the analysis
   exception above. Do not widen isolated provider environments
   (`src/auth_drivers/codex_app_server_runtime.py:189`,
   `src/auth_drivers/claude_agent_sdk_runtime.py:117`).
   The archived CLI embeds a separate engine: CLI replacement alone does nothing
   for Python; supplying a production CLI is optional.
4. **Compile profile, then final-artifact checks.** The candidate is a feature
   floor, not distro parity. Preserve `MAX_VARIABLE_NUMBER=250000` unless bounded
   callers are proved: candidate is 32766, and dynamic binds at
   `src/sa_article_reconciliation_store.py:44`/`:162` and
   `src/tools/backends/sa_capture_backend.py:855` are not capped by result LIMIT.
   Preserve baseline `SECURE_DELETE` and LIKE behavior unless explicitly changed.
   Review URI/read-only behavior and optional FTS3/4, RTREE, column metadata,
   session/preupdate, dbstat/statement, unlock-notify, UPDATE/DELETE LIMIT and
   soundex differences against needed schemas/native consumers. Those consumers
   were not inspected locally. Missing JSON/load-extension option text alone
   does not prove missing functionality. Record remaining page/function-limit,
   lookaside, overflow-read and percentile differences from the two tracked
   identity receipts. Retain FTS5/tokenization, JSON, threading, FK, transaction,
   WAL/backup and exact decimal-TEXT contracts. Changed build/ELF bytes require
   fresh disposable acceptance; the historical 330 tests are not that admission.

## User Decisions And Cutover

- **Scope/ownership:** approve a durable package/wrapper location and maintainer,
  compile-profile departures, and the analysis-child policy. Keep Python/numpy
  unchanged. Actual selectors may not match the receipted interpreter; verify
  only in a separately authorized window.
- **Authorization:** specify installed-selector/schedule/store-path inspection,
  shutdown/relaunch control, backup destination/capacity/privacy/retention and
  integrity-check window. Stop API, browser message sources, detached workers,
  standalone jobs and maintenance writers. Scheduler-off/UI-close is insufficient.
- **Recovery set:** WAL-consistent backups of all applicable stores, with writers
  stopped for cross-store consistency; preserve objects at `<market-db>.sec-research`
  (`src/sec_research/paths.py:26`). `src/sqlite_backup.py:9` is a private exclusive
  backup primitive, not shutdown/integrity/restore orchestration.
  `src/market_data_direct.py:149` defaults to overwrite: explicitly forbid
  clobbering admission backups.
- **Acceptance:** full `integrity_check`, `foreign_key_check`, external-content
  FTS checks on disposable verification copies, restore/backward-read rehearsal,
  and final-package launch/child identity checks. The baseline UPSERT receipt
  proves `quick_check=ok` can miss corruption. Upgrade does not repair damage.
  Switch both selectors while stopped; verify actual mapped engines before
  resuming writes and account for startup migrations/reconciliation.
- **Failure/rollback:** decide whether to remain stopped, authorize separate repair,
  or restore. Retain old package/selector bindings. Before writes, reverting
  bindings may suffice; after writes, prove old-engine compatibility or restore
  the coherent pre-window set with compatible source/schema/referenced files.
  Never pair restored main files with stale WAL/SHM. Restoring loses post-backup
  changes and requires acceptance. Returning to 3.37.2 reintroduces documented
  defects; no automatic fallback/resumption.

No REINDEX, VACUUM, FTS rebuild, schema disposal, route change or SEC cleanup/reset
is part of this upgrade. SEC reference-root/lease prerequisites remain separate.
**Result: conditional minimum path identified; no local activation, production
health, package admission or successful rollback claimed.**
