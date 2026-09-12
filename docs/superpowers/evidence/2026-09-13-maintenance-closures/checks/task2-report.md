# Task 2: C11 Handoff

## Status

Bounded backend/frontend/collateral implementation complete. Final restored owned
backend/API checks: **329 passed, 0 skipped**. Adjacent controls: **303 passed,
0 skipped**. Focused frontend/i18n: **75 passed**, typecheck and i18n literal scan
passed. Both independent inverses failed their named owners and were restored to
the exact reviewed bytes. No unresolved product blocker found in this scope.

Workspace: `/tmp/arkscope-research-output-boundary`; branch
`codex/sec-research-integration`; base and unchanged HEAD:
`eec66b9e129eb3383c1c6b136f6d10953a3568f8`.

No agents, stage/commit, merge/push, dependency changes, provider requests, real
DB/config/key access, external CLI sessions, App/server startup, schema changes,
or stored-key disposal. All owned subprocesses have exited. Controller retains
independent review, final frozen full backend/frontend/build, census and Git.

## Implemented Files

- `src/news_providers.py`: physically removed both old constants, resolver,
  enabled helper and its profile helper; retained parser and real adapters.
- `src/news_normalized/routing.py`: removed obsolete parameters, validation and
  reads. Only the current normalized key is queried. Current-setting/requirement
  blockers, missing-profile noncreation, corruption handling and live
  `legacy_local` enum remain.
- `src/api/routes/news.py`: removed `LocalNewsToggle`, setter and the five old
  status fields. GET status, normalized setter and all news read routes remain.
- `src/news_sync_status.py`: unconditional news-only overlay, including `None`;
  encoded read-only URI fix described below. Telemetry aggregation unchanged.
- `src/service/provider_health.py`: Massive/Finnhub ingest success comes only
  from provider-sync observations, never publication time. Article signals remain
  visible. IBKR combined price/news logic and status semantics are unchanged.
- `src/news_direct.py`: stale scheduler prose only; writer code unchanged.
- Frontend `src/api.ts`, `src/marketDataDisplay.ts`: removed unused setter/label
  and exactly the five obsolete `NewsStatus` fields.
- Frontend `src/i18n/resources/{en,zh-Hant}/settings.ts`: removed only
  `newsStorage.routing.{directEnvOn,directEnvOff,localCompatibility,directExplicit,directDefault}`.
  `write`, `read`, `authority` and all macro fields remain.

Tests changed: `test_news_settings_route.py`, `test_news_providers.py`,
`test_news_normalized_routing.py`, `test_news_sync_status.py`,
`test_provider_health.py`, `test_data_coverage_tools.py`,
`test_stored_sec_projection.py`, `test_market_data_admin.py`,
`test_data_scheduler.py`, `test_security_lifecycle_routes.py`, `test_api.py`;
new `test_news_routing_cleanup.py`. Frontend tests:
`SettingsNewsStorage.test.ts`, `SettingsLocalStorage.test.ts`,
`marketDataDisplay.test.ts`, `i18n/resources.test.ts`.

All 26 product/test paths and SHA-256s are in [final source](task2-final-source.json).
Controller-owned dirty docs/evidence were neither edited nor reverted. Current
docs/catalog scans found no switch advertisement requiring a documentation edit;
dated evidence remains historical.

## Narrow Rulings

1. `/news/status` already read real telemetry before this patch. Its defects were
   stale fields and old-setting validation, not suppression of sync reads.
2. Removing PUT `/news/settings` yields **405**, because GET `/news/{ticker}`
   still matches that literal path. No stub or ticker-route deletion was added.
   Both actual route-count owners now assert **223 -> 222**, explicit old-PUT
   absence and the exact five surviving news routes. AST comparison reports
   exactly one removed route and no additions.
3. `test_api.py` was required additional collateral: its hermetic lifespan test
   also counted 223 routes. Only that count and retained-news-route assertions
   changed; scheduler/lifespan/provider-isolation controls remain.
4. `i18n/resources.test.ts` was required additional collateral: current Settings
   count **1019 -> 1014**, total **2962 -> 2957**. Five explicit retired paths
   were added to its existing accounting; historical counts/subtrees and useful
   locale assertions were preserved, not replaced by looser bounds.
5. Health fixtures now insert real disposable `provider_sync_runs/meta` rows.
   The old mocked partial DTO claimed success at10 and a later attempt at11,
   a combination that cannot represent a latest durable partial run: the schema
   allows only running/succeeded/failed, and partial is derived from ticker
   errors. The replacement has two explicit cases: succeeded-at10 + ticker error
   yields partial; an additional failed-at11 run retains success-at10 and the
   distinct attempt-at11. Both retain connected provider health and the error.
   Stale/key-precedence/IBKR expectations are retained. Missing-telemetry controls
   retain nonempty article signals and require no_signal, not publication fallback.

## Concrete URI Defect

Actual disposable populated databases named `market?data.db` and `market#data.db`
were misread by raw `file:{path}?mode=ro`. Both calls returned `None` and created
an unintended zero-byte sibling named `market`; the intended DBs were 20,480 bytes.
Those RED fixture directories are preserved under `task2-regression-red/pytest/`.

`test_sync_reader_encodes_sqlite_uri_metacharacters[...]` failed for both names.
The fix is only `read_news_sync_status` using
`f"{path.resolve().as_uri()}?mode=ro"`, retaining `uri=True`, the exists guard,
typed SQLite errors and connection cleanup. GREEN verifies actual timestamps,
counters, unchanged DB bytes and no sibling artifacts. Named missing-path cases
also verify noncreation. No unrelated SQLite helper was changed.

## Commands and Receipts

Every test command used this workspace's unchanged copied runner:

```sh
PY=/home/hyl/.virtualenvs/llm_app/bin/python
WORK=.superpowers/sdd/2026-09-13-maintenance-closures
$PY -B "$WORK/run_checks.py" RUN backend -q TEST_PATHS
$PY -B "$WORK/run_checks.py" RUN collect TEST_PATHS
$PY -B "$WORK/run_checks.py" RUN frontend test -- FRONTEND_PATHS
$PY -B "$WORK/run_checks.py" RUN frontend run typecheck
$PY -B "$WORK/run_checks.py" RUN frontend run check:i18n-literals
```

`RUN` receipts are create-only; the exact expanded commands, cwd, environment,
exit codes, timings and log paths for all **21 runs** are in
[run accounting](task2-run-accounting.json) and each `RUN/command.json`.
These are audit-hook guards, not a claimed OS sandbox. Guards were not modified.

| Run | Outcome |
| --- | --- |
| task2-collect-before | 275 collected, before any test/product edits |
| task2-baseline-backend | 275 passed |
| task2-collect-api-before / task2-baseline-api | 25 collected / 25 passed |
| task2-baseline-frontend | 75 passed |
| task2-regression-red | 19 failed / 28 passed: 17 assertion failures + 2 missing-field KeyErrors; not a pure19-assertion RED |
| task2-regression-assertion-red | 19 assertion failures / 30 passed; missing-field assertion clarified, current malformed controls added; still before product edits |
| task2-frontend-red | 2 failed / 41 passed; old exports and locale leaves |
| task2-first-green | 2 fixture CHECK failures / 326 passed; invalid persisted partial status, corrected with real run/meta cases |
| task2-frontend-green | 3 failed / 72 passed; leftover localized alias and exact locale inventories |
| task2-typecheck | Exit2; same leftover alias and removed DTO fields |
| task2-owned-green | 329 passed |
| task2-frontend-green-2 | 75 passed across the four scoped files |
| task2-typecheck-2 | Exit0 |
| task2-i18n-literals | Exit0; 37 candidates, 20 signatures, 0 debt signatures |
| task2-controls-green | 303 passed across 23 adjacent files |
| task2-collect-after | 329 collected |
| task2-inverse-validation | 4 failed / 8 passed |
| task2-restored-validation | 12 passed |
| task2-inverse-telemetry | 6 failed / 14 passed |
| task2-final-restored | 329 passed, 0 skipped |

Nonzero receipts were preserved, not overwritten or disguised as expected passes.
Between the two regression RED runs, `_assert_telemetry` changed its initial
dictionary indexing to an explicit non-None check and `sync.get("status")`
assertion. The two old-overlay payloads then failed assertions instead of raising
KeyError. No profile or telemetry fixture rows changed between those RED runs;
two malformed-current-setting positive controls were also added, explaining
28 -> 30 passes. Both runs preceded every product edit. The invalid persisted
partial-run fixtures occurred later in `task2-first-green`, not in either RED run.
Repeated checks are not an additive total. No full backend or full frontend suite
was run. Final focused backend command covered the 12 backend files listed above.
Adjacent command covered direct/news-normalized schema, store, identity, tickers,
body policy, projection, adapters, IBKR adapter, writer/locking/retry queue,
collector adapters/load-env, news event/feed/local-authority/content/identity,
current investigation-news, lifecycle news evidence/ownership and current tools.

## Independent Inverses

Validation mutation changed **only** `src/news_normalized/routing.py`: it queried
the old stored key and reintroduced its malformed-value BLOCKED decision.
`test_current_writer_ignores_obsolete_profile_and_environment` failed all four
`stored-malformed`/`env-malformed` normalized/direct cases. Six false/true controls
and two malformed-current-setting blockers remained passing. After restoration,
all12 passed.

Telemetry mutation changed **only** `src/news_sync_status.py` and
`src/service/provider_health.py`: a temporary read-only helper resolved the
actual old profile/env flag, restoring overlay suppression and health's old
publication-time fallback. The following owners each failed for `stored-false`
and `env-false`:

- `test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings`
- `test_overlay_clears_stale_news_when_current_store_is_absent`
- `test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings`

The five `/news/status` actual-telemetry controls remained green, accurately
distinguishing its unchanged acquisition behavior. Tests, runners and the other
product files were untouched during each inverse. Both mutations were manual
`apply_patch` edits, followed by exact-byte restoration and ordinary backend runs;
no expected-failure flags or runner changes.

Product collection SHA-256s:

```text
reviewed / both restorations / final:
864f232ce0fee471e31c8d206ef3fa9ff34d3e4062e84497b75c06ad097031f4
validation inverse:
7d387cdd151c9170a37703545ab802147ac19a98d67389927b060f8ad092bbcd
telemetry inverse:
e61c73822043c9668839643ff144eb01ed572d136c7300c2359a01a874f27846
```

Each phase has `task2-*-source.json` hashes and matching `.diff` artifacts.
`task2-reviewed-before-inverse.json` equals both restored manifests and
`task2-final-source.json` byte-for-byte (`cmp`, exit0), including all16 test and
all3 runner hashes. [Source audit](task2-source-audit.json) independently checks
the changed mutation-file sets, current hashes, no staged files and clean diff.

## Exact Node Ledger

[Machine ledger](task2-node-ledger.json) contains every pre/post node;
[readable ledger](task2-node-ledger.md) enumerates all **34 removed** and **63 added**
nodes and the current replacement owners for each removal. Counts: **300 before
(275 primary/collateral + 25 API), 329 after, 266 unchanged**.

The 18-case route matrix becomes six current-required/current-normalized cases;
separate real persisted-profile/environment owners cover inert old values. Old
rollback-only tests transfer to helper/API absence and actual state owners. The
misnamed completed-audit-marker/409 test transfers to accurately named direct
selection when normalized writes are disabled; no409 assertion was discarded.

Frontend node transfer (75 before and75 after, including i18n):

- Removed `newsRoutingLabel > distinguishes default direct routing from explicit rollback`
  and `newsRoutingLabel > makes env override direction explicit`.
- Added `current news contract > does not export the obsolete news setter or routing label`
  and `current news contract > keeps current routing locale subtrees without obsolete switch copy`.
- Renamed `SettingsView news storage copy > hides_both_migration_controls_even_for_a_pre_exit_compatibility_response`
  to `SettingsView news storage copy > keeps_news_storage_read_only_for_the_current_direct_writer`;
  retained no-checkbox/no-write assertions for the current normalized setter.
- Current normalized-write/read/authority, macro, locale and other display tests
  remain. The surviving mixed-locale test loses only its obsolete-label assertion.

## Controls and Final Boundary

Source audit has **zero product matches** for the obsolete symbols/parameters,
five locale leaves or retired frontend exports; remaining test matches are
explicit absence and persisted-old-value owners. No ignored kwargs/forwarders.
Only PUT `/news/settings` was removed; all five retained news routes are exact.

Positive controls include actual nonempty news/price rows, distinct ingest and
publication timestamps, run/meta errors and counters, normalized/current setting
validation, required-source blocking, missing/corrupt profile and market behavior,
non-news overlay preservation, current permission ordering, real adapters and
writers, SA investigation reads, financial_cache and stored SEC projection.
Fixtures assert old stored keys remain present and unchanged.

`task2_evidence.py {snapshot,ledger,receipts,audit}` generated create-only source,
node and receipt artifacts without product imports or DB access. Final audit
found **no remaining worktree Python/Node/npm/pytest/Vitest test/server processes**;
all command sessions returned completion. No service was left running.

Remaining acceptance work belongs to controller: independent review, frozen full
backend/frontend/build and mechanical census. C12 collector CLI retirement,
stored-key disposal and SEC citation/export/recovery are not closed by C11.
