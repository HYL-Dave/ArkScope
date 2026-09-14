# C12 News Client And CLI Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans with TDD; use scoped read-only review before final acceptance. Tasks 1 and 2 share caller contracts and are executed sequentially.

**Goal:** Physically remove obsolete news CLI/storage owners while preserving current incremental ingestion and making the current CLI's news status truthful.

**Architecture:** Move the two live transport/parser implementations to non-CLI `src/news_clients` modules. Both existing factories keep their contracts and source IDs. The current `daily_update` CLI delegates collection as before, but reads durable SQLite news telemetry instead of Parquet archives.

**Tech Stack:** Python, requests, dataclasses, SQLite read-only status, pytest.

**Spec:** `docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md`; detailed source inventory in `docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/checks/c12-inventory.md`. The user approved retiring old custom-date/full-history/checkpoint/archive CLI capabilities and retaining collected data. Shared fourteen-day bootstrap is already complete at `8b468771`.

## Constraints

- No compatibility forwarding modules, retired stubs, old entrypoints or storage configuration in the new clients.
- Preserve current parser values, source identities, date/timestamp behavior, rate limiting and credential authority. No new entitlement assumption, retry redesign or source renaming.
- Preserve active-universe exclusions, source/market/Gateway locks, job telemetry, current writer routing and SEC's generic scheduled adapter.
- Retain collected files/databases. No production access, live provider calls, runtime installation, schema mutation, merge or push.
- Use the existing isolated worktree `codex/sec-research-integration`, base `8c64f884`. No dependency install or engine upgrade in this change.
- Execute full backend only after all changes/reviews, with no concurrent pytest, scanner or agent sessions.

## Task 1: Move Live Clients And Delete Old Owners

Files: create `src/news_clients/{__init__,polygon,finnhub}.py`; delete `src/collectors/{__init__,polygon_news,finnhub_news}.py`; update `src/news_providers.py`, `src/service/data_scheduler.py` and exact imports/patches in the tests listed by the C12 inventory.

Interfaces retained: `CollectionConfig`, `FinnhubConfig`, `NewsArticle`, rate limiters, `PolygonNewsCollector.fetch_news_range/parse_article`, `FinnhubNewsCollector.fetch_news/parse_article`, each `load_env`. New clients have no `main`, `collect_news`, `run_incremental`, storage/checkpoint/month orchestration or global file cursor. Factories import `src.news_clients.polygon` / `.finnhub` lazily.

- [x] RED: `tests/test_news_client_cleanup.py` asserts the three old module files are absent, two news `SourceDef.adapter` values are `None`, SEC's adapter is intact, and the current CLI no longer advertises retired paths. Expected failures are physical absence and stale tuples/text, not import errors. Capture before implementation.
- [x] Move only listed live definitions, remove storage-only config fields and unused imports, then delete original files. Keep method bodies unchanged except stale prose. A structural AST comparison against the base proves parser, fetch, limiter, initializer and credential methods did not acquire behavior changes.
- [x] Repoint both factories and test callers. Remove obsolete self-tests for deleted CLI/storage/global-cursor behavior; replace import safety with a real fresh import under logging/filesystem guards. Preserve missing-key, active-universe and exclusion contracts at current scheduler/CLI consumers; add nonempty fake-page timestamp/pagination/parser controls in `tests/test_news_clients.py`.
- [x] GREEN: run cleanup, client, credential, writer, scheduler, active-universe, lifecycle-terminal, score-retirement and coverage tests offline. Test imports must all resolve; no broad skips or `raising=False` disguises for deleted symbols.

## Task 2: Current CLI Status

Files: `src/daily_update.py`, `tests/test_daily_update_wrapper.py`; add focused status tests there. No new public HTTP or storage API.

Use `read_news_sync_status(resolve_market_db_path())` as the current news telemetry reader. Present per-provider recorded run status, last attempt/success and rows added by that run. `None` means no recorded telemetry, not zero articles. Reader failure means status unavailable, not empty or succeeded. Keep price status and actual collection dispatch/exit behavior intact.

- [x] RED: create disposable direct/normalized writer telemetry and stale archive traps; assert `--status` reads current state, preserves partial/failed, reports missing/corrupt telemetry honestly and does not scan Parquet. Assert recent published data or a succeeded run never prints a news-completeness guarantee. Expected old implementation failures: Parquet trap / stale status / false completion wording.
- [x] Delete `get_polygon_status`, `get_finnhub_status`, `get_ibkr_news_status` and archive scans. Replace their display with one read of current news telemetry. Remove unverified history-limit claims and invalid no-scope recommendations. Update the CLI docstring to per-source/ticker cursors and the shared initial target, not a second hardcoded default.
- [x] Preserve real `main()` tests for all source flags, explicit and unavailable scopes, dry run, dispatch, skipped/partial/failure exit codes and summary telemetry. Keep `get_ibkr_prices_status`'s existing SQLite contract.
- [x] GREEN: run CLI/status plus news sync status and scheduler controls, using only disposable data and no provider calls.

Integration additions: apply the existing diagnostic redactor only to displayed
provider errors (synthetic credential echo RED), and report meta-only failures
without inventing an aggregate run. Remove the CLI's unused `timed()` wrapper,
imports/config constant; rehome three `test_job_runs.py` cases to `record()`.
The first combined run found an invalid test fixture (`headline`); it now uses
the actual schema's `headline_only`. No validation or expected statuses relaxed.
Final focused acceptance: 427 passed, including the additional absence owner.

## Task 3: Current Documentation And Acceptance

- [x] Repoint current provider/catalog/vision/data documents and remove current advertisements for retired commands. Keep historical specs/evidence archival; record source-anchor distinctions. Do not rewrite historical reports as if new paths existed then.
- [x] Scope review: base-to-tip diff, deleted-test ownership mapping, AST preservation, unbounded source/reference search. Resolve actionable findings before full acceptance.
- [x] Commit product source; freeze source/runtime/runners. Collect and execute the full backend, reconcile every node and unchanged skip identity. First full: 11,167P/1F/12S; fix the stale exact brand-copy allowance at `c30c5bb8`, then repeat the entire suite: 11,168P/12 unchangedS, 11,180 exact nodes, no source/runtime/runner drift. Same-scanner comparison has zero new candidates; all 17 new uncertainty IDs and four intentional deleted-file reductions are attributed.
- [x] Publish selected RED/GREEN/full results and update priority/current policy. C12 code/entrypoint cleanup is CLOSED; provider-limit reporting, initial-window persistence, C15/C20, SQLite activation and SA targeting remain separate. Evidence: `docs/superpowers/evidence/2026-09-14-news-client-cleanup/README.md`.

## Preflight

Task 1 -> Task 2 share the public CLI contract only: Task 1's absence test checks the docstring, completed by Task 2; no Task 1 completion claim before that guard passes. The existing writer/bootstrap tests remain positive controls, not deleted-CLI owners. Task 3 does not alter product source after full-run freeze. No task assumes a new schema, runtime or entitlement API exists.
