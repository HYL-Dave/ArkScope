# N9 Batch-2 Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** DRAFT for review. No live PG action is authorized by this document until the plan is reviewed, implemented, and the live evidence packet is explicitly approved.

**Goal:** Finish the second N9 cleanup batch after S-H1/P0-C by dropping the frozen PG `job_runs` archive, removing dead PG-domain code paths, collapsing transitional local-toggle defaults so fresh profiles do not construct dead PG routes, and proving normal runtime remains local-only.

**Architecture:** Batch-2 is a small cleanup batch, not a data migration. Runtime authority already lives in local stores (`market_data.db`, `macro_calendar.db`, `profile_state.db`, `sa_capture.db`). The implementation has four rails: (1) collapse post-PG-exit routing defaults to local, (2) remove or stub PG backend methods for tables already dropped in batch-1, (3) retire legacy PG import code from `migrate_to_supabase.py`, and (4) run an N9-style dump/restore/drop gate for PG `job_runs` plus the orphan `news_search_vector_update()` function.

**Tech Stack:** Python, FastAPI route handlers, SQLite local stores, PostgreSQL archive/drop tooling (`pg_dump`, `pg_restore`, `psql`), pytest. No frontend UI work except removing unreachable client exports if found by grep.

---

## Map Check

Active map authority:

- `docs/design/PROJECT_PRIORITY_MAP.md` P0-B: batch-2 = PG `job_runs`, orphan `news_search_vector_update()`, dead `DatabaseBackend` methods, retired `migrate_to_supabase` code.
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` §8: batch-1 live drop is complete; remaining PG objects are `prices`, frozen `job_runs`, and app-record archive tables.
- `docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md`: destructive PG drops require preview, fingerprint, targeted dump, restore proof, explicit approval, no `CASCADE`, and postcheck.

Recent UI cleanup added one more batch-2 requirement: because the Settings UI no longer exposes the old local/PG toggles, `use_local_market`, `use_local_macro`, and `use_local_job_runs` must stop using unset or explicit false as a live route back to PG. The rollback target is gone or archive-only; recovery now means restoring an archive.

## Scope

In scope:

- Collapse post-PG-exit defaults for market, macro, and job-runs routing.
- Remove/stub PG `DatabaseBackend` paths that reference tables already dropped in batch-1.
- Physically retire `migrate_to_supabase.py` code for dropped domains and make any remaining PG price import archive-explicit.
- Add a batch-2 PG evidence/drop CLI or a batch-2 mode in the existing N9 CLI.
- Drop PG `job_runs` and `news_search_vector_update()` only after restore proof and explicit user approval.
- Update docs and run PG-unreachable runtime smoke.

Non-goals:

- Do not drop PG `prices`; that is batch-3 after a fresh prices archive packet.
- Do not drop PG app-record tables (`agent_queries`, `research_reports`, `agent_memories`) in this batch unless a separate reviewed decision amends this plan. They are archive-only, but not part of the current batch-2 destructive scope.
- Do not redesign IV, macro ingestion, model lists, token monitoring, or Data Sources UI layout.
- Do not reintroduce UI toggles for retired PG fallback paths.

## Decisions Locked By This Plan

1. **Post-drop rollback semantics:** `use_local_market=false`, `use_local_macro=false`, and `use_local_job_runs=false` no longer select PG for normal runtime after batch-2. If a user needs old PG data, restore the relevant archive first.
2. **Fresh profile semantics:** unset local flags resolve to local for market, macro, and job-runs. A reset profile must not create a dead plain-PG store for dropped domains.
3. **Archive policy:** targeted `pg_dump` plus restore proof is the rollback basis for PG `job_runs`.
4. **Soak policy:** the original 2026-07-10 calendar soak is acceptable, but not the only gate. Early live drop is allowed only if the evidence gate proves local `job_runs` has been operating normally, PG `job_runs` is frozen, and a PG-poison/unavailable smoke proves normal pages do not fall back to PG. If that evidence is not clean, wait until the calendar gate.

---

## Task 1 - Collapse Local Defaults

### Intent

Make post-PG-exit local authority the default path for market, macro, and job-runs. This closes the stranding window where UI controls are hidden but a fresh/reset profile still routes to PG.

### Red Tests

- [ ] In `tests/test_market_data_admin.py`, update/add a test showing `/market-data/status` with no `use_local_market` profile value reports:
  - `prices_authority == "local"`
  - `pg_fallback_active is False`
  - `routing_enabled` reflects local authority even when `market_data.db` does not yet exist.
- [ ] Flip the old `test_status_route_local_only` expectation so unset no longer means "PG/off".
- [ ] Add a test for a fresh profile with no `market_data.db`: constructing `DataAccessLayer(db_dsn="auto")` with a poisoned PG DSN must select a local market backend and return honest-empty local reads rather than constructing plain `DatabaseBackend`.
- [ ] In `tests/test_macro_calendar_settings_route.py`, update/add a test showing unset `use_local_macro` reports `local_first_active is True`.
- [ ] In `tests/test_macro_calendar_local_wiring.py`, flip `test_factory_returns_pg_store_when_toggle_off_default`: default/unset must return `MacroCalendarLocalStore`, not `MacroCalendarStore`.
- [ ] In `tests/test_job_runs.py`, flip `test_get_job_runs_store_explicit_false_keeps_pg_store`: explicit false must now return `JobRunsLocalStore` or an equivalent local-only store.
- [ ] Add one regression test for explicit false as an invalidated rollback lever:
  - market and macro status may still expose the persisted value for provenance;
  - runtime routing remains local.

### Implementation

- [ ] Modify `src/tools/data_access.py`:
  - Keep `_profile_setting_truthy()` unchanged for toggles that still need true opt-in semantics.
  - Make `_local_market_enabled()` return `True` after N9 local-default collapse.
  - Remove the `market_db_exists` requirement from actual local-market backend selection. If a local market DB path is resolvable, select `LocalMarketDatabaseBackend` even when the file is absent; the local SQLite layer should return honest empty rows until ingestion creates the DB.
  - Apply the same fresh-profile logic to completed-news hard-local routing: a missing `market_data.db` must not force plain PG when profile markers say PG-exit is complete.
  - Plain `DatabaseBackend` should remain only for pathological/test cases where no local path is resolvable and the caller explicitly asks for PG.
  - Make `_local_macro_enabled()` return `True` after N9 local-default collapse.
  - Update docstrings that still say local market or macro defaults to PG/off.
- [ ] Modify `src/macro_calendar/__init__.py`:
  - `get_macro_calendar_store(dal)` should route to `MacroCalendarLocalStore` by default.
  - The PG `MacroCalendarStore` fallback becomes a test/legacy object only, not normal runtime routing.
- [ ] Modify `src/api/routes/macro_calendar.py`:
  - `macro_status()` should report `local_first_active=True` by default.
  - Preserve `use_local_macro_setting` as "persisted legacy setting" if useful, but do not use it to imply PG routing.
  - Update `set_local_macro()` docstring: the endpoint is legacy/provenance only, not a runtime PG fallback lever.
- [ ] Modify `src/api/routes/market_data.py`:
  - `market_data_status()` should report local authority independent of the old setting.
  - Keep `pg_fallback_active=False`.
  - Update route docstrings to say retired mirror/fallback controls no longer change authority.
- [ ] Modify `src/service/job_runs_store.py`:
  - `get_job_runs_store(dal)` must return `JobRunsLocalStore` by default and when the legacy setting is explicit false.
  - Update docstring: explicit false was the rollback lever until N9; after batch-2 it is invalidated.

### Green Gate

```bash
pytest \
  tests/test_market_data_admin.py \
  tests/test_macro_calendar_settings_route.py \
  tests/test_macro_calendar_local_wiring.py \
  tests/test_job_runs.py \
  tests/test_provider_health.py \
  tests/test_macro_calendar_health.py \
  tests/test_sa_local_readers.py \
  -q
```

---

## Task 2 - Remove Dead PG Backend Paths

### Intent

Prevent accidental plain `DatabaseBackend` calls from producing `relation does not exist` after batch-1 and batch-2. These methods are not runtime authority anymore, but they should fail honestly or return local-equivalent empty structures rather than attempting SQL against dropped tables.

### Red Tests

- [ ] In `tests/test_db_backend.py`, add tests that monkeypatch `DatabaseBackend._query_df` / `_get_conn` to raise if called, then assert these methods do not touch PG:
  - `query_news(...)`
  - `query_news_feed(...)`
  - `query_news_search(...)`
  - `query_news_stats(...)`
  - `query_news_scores(...)`
  - `query_iv_history(...)`
  - `query_fundamentals(...)`
  - `get_financial_cache(...)`
  - relevant non-price sections of `query_health_stats()`.
- [ ] Preserve `query_prices(...)` SQL in `DatabaseBackend` until batch-3. Add a test that Task 2 does not remove the PG prices method.
- [ ] Add a test that `query_health_stats()` no longer reports errors for dropped batch-1 domains when only prices remains.

### Implementation

- [ ] Modify `src/tools/backends/db_backend.py`:
  - Convert batch-1 dropped-domain methods to retired stubs that return the same empty shapes their local counterparts use.
  - Remove `query_news_scores()` as a live SQL method or make it a retired stub if callers still expect the attribute.
  - Stop `query_health_stats()` from querying dropped tables (`news`, `iv_history`, `financial_data_cache`). Keep prices until batch-3.
  - Do not remove app-record methods in this task; app-record PG archive tables are out of batch-2 destructive scope.
- [ ] Update comments/docstrings that still describe PG `news`, `iv_history`, `fundamentals`, `financial_data_cache`, or `news_scores` as available runtime tables.

### Green Gate

```bash
pytest tests/test_db_backend.py tests/test_news_pg_unreachable.py tests/test_provider_health.py -q
```

---

## Task 3 - Retire `migrate_to_supabase.py` PG Import Code

### Intent

Stop the old import script from looking like a supported runtime path. After P0-C, even prices ingestion is direct-local; PG prices is archive/rollback only until batch-3.

### Red Tests

- [ ] Add/update tests in `tests/test_pg_drop_domain_retirement.py` or create `tests/test_migrate_to_supabase_retirement.py`:
  - no flags -> refuses with "PG imports retired" message;
  - `--news`, `--iv`, `--fundamentals`, `--scores`, `--archive-scores` all refuse after batch-1;
  - `--prices` refuses too. Do not add `--archive-prices`: after P0-C, writing PG prices only creates stale archive drift. Batch-3's restore basis is the batch-3 dump, not continued sync.
- [ ] Update old tests that import `article_hash` or score helpers from `scripts.migrate_to_supabase`:
  - `article_hash` callers should import from `src.news_identity.canonical_article_hash`;
  - score import tests should use `scripts/scoring/import_news_scores_local.py` or a small local parsing helper, not the PG importer.
- [ ] Add a regression test that no scheduler or daily update runtime path invokes `migrate_to_supabase.py`.

### Implementation

- [ ] Modify `scripts/migrate_to_supabase.py`:
  - Delete or quarantine retired import functions for news, scores, IV, and fundamentals.
  - Make default execution fail closed instead of importing prices.
  - Reject `--prices` too; do not preserve an archive-price writer.
  - Ensure no DSN or secret is printed.
- [ ] Update `scripts/collection/daily_update.py` if it still advertises or shells out to retired `migrate_to_supabase` paths. Prefer honest CLI errors over silent no-ops.
- [ ] Update README/help text under `scripts/collection/README.md` if tests or grep show stale usage examples.

### Green Gate

```bash
pytest \
  tests/test_daily_update_wrapper.py \
  tests/test_data_scheduler.py \
  tests/test_news_scores.py \
  tests/test_news_identity.py \
  tests/test_news_direct.py \
  tests/test_pg_drop_domain_retirement.py \
  -q
```

If `tests/test_pg_drop_domain_retirement.py` does not exist, replace it with the new retirement test file name.

---

## Task 4 - Build Batch-2 Evidence/Drop CLI

### Intent

Reuse the N9 batch-1 destructive-drop discipline for a narrower target set: `job_runs` and `news_search_vector_update()`.

### Target Objects

- Tables to drop: `job_runs`
- Functions to drop: `news_search_vector_update()`
- Excluded/protected tables: `prices`, `agent_queries`, `research_reports`, `agent_memories`

### Red Tests

- [ ] Create `tests/test_n9_batch2_cleanup.py`.
- [ ] Test deterministic evidence fingerprint:
  - object order changes must not change the fingerprint.
- [ ] Test object classification:
  - `job_runs` present -> target present;
  - `news_search_vector_update()` present -> target function present;
  - `prices` and app-record tables present -> excluded/protected.
- [ ] Test grep classifier:
  - runtime PG `FROM job_runs` is a blocker unless it is inside the batch-2 CLI, tests, docs, or local SQLite `JobRunsLocalStore`.
  - `src/service/job_runs_store.py` local SQLite SQL is allowed.
  - `src/tools/backends/db_backend.py` dropped-domain stubs are allowed only if they no longer issue SQL against dropped tables.
- [ ] Test dump command:
  - targets only `public.job_runs`;
  - does not include DSN in argv;
  - writes manifest and evidence.
- [ ] Test restore proof compares row counts and row fingerprints.
- [ ] Test drop validation refuses without:
  - reviewed fingerprint;
  - restore proof;
  - archive manifest;
  - scheduler/native-host pause confirmations;
  - destructive-drop confirmation.
- [ ] Test generated drop SQL contains no `CASCADE`.
- [ ] Test postcheck reports target absent and excluded present.

### Implementation

- [ ] Create `scripts/migration/n9_batch2_cleanup.py`, or refactor common helpers out of `scripts/migration/n9_batch1_pg_drop.py` and add a batch-2 mode.
- [ ] Implement commands:
  - `preview --database-url --repo-root --output`
  - `dump --database-url --expected-report --archive-dir`
  - `verify-dump --database-url --archive-dir --restore-db --confirm-create-drop-restore-db`
  - `drop --database-url --archive-dir --reviewed-fingerprint --repo-root --confirm-scheduler-paused --confirm-native-host-paused --confirm-destructive-drop`
  - `postcheck --database-url --archive-dir`
- [ ] Evidence report must include:
  - server version;
  - `job_runs` count and row fingerprint;
  - `news_search_vector_update()` presence;
  - dependency scan including `pg_depend` and rowtype edges;
  - excluded table presence;
  - repo grep blockers and allowed hits;
  - local-default collapse proof fields if available from tests or static grep.
- [ ] Dump archive should be under:

```text
data/pg_archive/n9_batch2_<UTC>/
```

- [ ] Restore proof must use a disposable DB and verify row count + row fingerprint, not just file existence.

### Green Gate

```bash
pytest tests/test_n9_batch2_cleanup.py -q
python -m compileall scripts/migration/n9_batch2_cleanup.py
```

---

## Task 5 - Offline Integration Gate

### Intent

Prove code changes do not regress local runtime before any live PG action.

### Commands

```bash
pytest \
  tests/test_market_data_admin.py \
  tests/test_macro_calendar_settings_route.py \
  tests/test_macro_calendar_local_wiring.py \
  tests/test_job_runs.py \
  tests/test_provider_health.py \
  tests/test_macro_calendar_health.py \
  tests/test_sa_local_readers.py \
  tests/test_db_backend.py \
  tests/test_news_pg_unreachable.py \
  tests/test_daily_update_wrapper.py \
  tests/test_data_scheduler.py \
  tests/test_n9_batch2_cleanup.py \
  -q
```

Then run the standard A/B suite from a clean worktree. If the full suite has known live-data failures, record the failure-set diff exactly as in prior A/B reviews; any new deterministic failure blocks live PG action.

### Required Grep Gates

```bash
rg -n "FROM job_runs|INSERT INTO job_runs|UPDATE job_runs|news_search_vector_update|query_news_scores|news_scores|news_latest_scores|financial_data_cache|iv_history|fundamentals" src scripts tests docs/design
rg -n "migrate_to_supabase.py|--news|--iv|--fundamentals|--scores|--prices" src scripts tests docs/design
rg -n "use_local_market|use_local_macro|use_local_job_runs|ARKSCOPE_USE_LOCAL_MARKET|ARKSCOPE_USE_LOCAL_MACRO|ARKSCOPE_USE_LOCAL_JOB_RUNS" src tests apps/arkscope-web
```

All hits must be classified in the implementation review:

- runtime blocker,
- local SQLite authority,
- retired/legacy script,
- tests/docs,
- protected batch-3 prices path,
- app-record archive path.

---

## Task 6 - Live Evidence Packet

### Preconditions

- Scheduler quiet or paused.
- Firefox/SA native host quiet or paused.
- Sidecar is not using old code.
- No new commits between preview and destructive drop unless the preview is regenerated.
- PG client tools installed and not older than the server major version.

### Early-Execution Evidence Gate

The original calendar soak date is 2026-07-10. Live drop may happen earlier only if the preview evidence proves:

- PG `job_runs` row count is frozen since S-H1 or any delta is fully explained and local `profile_state.db` contains the corresponding rows.
- Provider health, SA health, and macro health read local job history successfully.
- No runtime code path writes PG `job_runs`.
- `get_job_runs_store()` selects local even with unset or explicit false legacy setting.
- A PG-poison or PG-unavailable smoke proves Data Sources, Jobs, Provider Health, SA Health, Macro Health, prices, and news do not fall back to PG.
- Repo grep blockers are zero.

If any item is inconclusive, wait for the calendar soak date and re-run this evidence gate.

### Commands

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
SCRIPT=scripts/migration/n9_batch2_cleanup.py
DB_URL="$DATABASE_URL"

"$PY" "$SCRIPT" preview \
  --database-url "$DB_URL" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --output /tmp/n9-batch2-preview-1.json

"$PY" "$SCRIPT" preview \
  --database-url "$DB_URL" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --output /tmp/n9-batch2-preview-2.json

cmp /tmp/n9-batch2-preview-1.json /tmp/n9-batch2-preview-2.json
```

Reviewer independently checks:

- PG `job_runs` count/status distribution;
- `news_search_vector_update()` exists before drop;
- `prices` and app-record tables are present and protected;
- local `profile_state.db` job_runs count/health;
- grep blockers are zero.

---

## Task 7 - Dump And Restore Proof

### Commands

```bash
ARCHIVE=data/pg_archive/n9_batch2_$(date -u +%Y%m%dT%H%M%SZ)

"$PY" "$SCRIPT" dump \
  --database-url "$DB_URL" \
  --expected-report /tmp/n9-batch2-preview-1.json \
  --archive-dir "$ARCHIVE"

"$PY" "$SCRIPT" verify-dump \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE" \
  --restore-db arkscope_n9_batch2_restore_$(date -u +%Y%m%dT%H%M%S) \
  --confirm-create-drop-restore-db
```

Gate:

- `restore_proof.json` has `ok: true`.
- manifest sha256 matches the dump file.
- restored row fingerprint equals evidence row fingerprint.
- function DDL is recoverable if needed.

No live drop may happen before the user explicitly approves the fingerprint and archive path.

---

## Task 8 - Live Drop

### Approval Phrase

Before running this task, the operator must explicitly approve:

- reviewed fingerprint,
- archive directory,
- dump sha256,
- restore proof status.

### Command

```bash
"$PY" "$SCRIPT" drop \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE" \
  --reviewed-fingerprint "<APPROVED_FINGERPRINT>" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --confirm-scheduler-paused \
  --confirm-native-host-paused \
  --confirm-destructive-drop
```

Drop rules:

- Single transaction.
- No `CASCADE`.
- `lock_timeout` and `statement_timeout` set.
- Transaction verifies:
  - `job_runs` absent;
  - `news_search_vector_update()` absent;
  - `prices`, `agent_queries`, `research_reports`, and `agent_memories` still present.
- Rollback on any error.

Postcheck:

```bash
"$PY" "$SCRIPT" postcheck \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE"
```

---

## Task 9 - Runtime Smoke

Run after live drop:

```bash
pytest tests/test_news_pg_unreachable.py tests/test_provider_health.py tests/test_macro_calendar_health.py tests/test_sa_local_readers.py -q
```

Manual/app smoke:

- Data Sources page loads without PG table errors.
- Provider health shows job history from local `profile_state.db`.
- SA health distinguishes local capture health and extension run signal.
- Macro health does not query PG `job_runs`.
- `/jobs/status` and `/jobs/history` return local rows.
- Price chart / ticker feed still works from local prices.
- News scored read still returns S-G baseline-equivalent local rows for a long window.

Post-drop PG-unreachable smoke:

- Repeat the PG-poison or PG-unavailable smoke after live drop and record it in Task 10 docs. This is mandatory if the live drop was executed before the 2026-07-10 calendar soak.

---

## Task 10 - Docs And Cleanup

- [ ] Update `docs/design/PG_EXIT_REMAINDER_SCOPING.md`:
  - batch-2 live record;
  - archive path;
  - fingerprint;
  - remaining PG objects.
- [ ] Update `docs/design/PROJECT_PRIORITY_MAP.md` §10:
  - batch-2 completion entry;
  - next active PG-exit item = batch-3 prices drop or PG-unreachable E2E, depending on reviewer decision.
- [ ] Update `docs/design/PG_EXIT_COMPLETION_PLAN.md`:
  - job_runs no longer PG archive;
  - dead paths removed;
  - local-default collapse done.
- [ ] Update `docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md` or this file if a runbook lesson from batch-2 should be banked for batch-3.
- [ ] Record invalidated levers:
  - `use_local_market=false`,
  - `use_local_macro=false`,
  - `use_local_job_runs=false`,
  - any old `.env` equivalents.
- [ ] Remove or note cleanup of unreachable frontend exports:
  - `bootstrap/update/validate/setUseLocalMarket/setUseLocalMacro` if grep confirms no UI consumer remains.
  - generic provider-config `hintRows` / client-id sub-row paths left unreachable by the grouped IBKR renderer.

---

## Final Review Gate

Batch-2 is complete only when all are true:

- Offline focused tests pass.
- Full A/B has no new deterministic failures.
- Preview evidence is byte-identical across two runs.
- Restore proof succeeds.
- User explicitly approves the reviewed fingerprint and archive path.
- Drop postcheck succeeds.
- Runtime smoke succeeds with PG dropped tables absent.
- Docs record the live facts and the remaining PG scope.

Expected remaining PG after batch-2:

- `prices` until batch-3.
- app-record archive tables unless separately approved for drop.

At that point, normal runtime should be PG-free in practice. Batch-3 is the physical `prices` archive/drop, not a runtime cutover.
