# News Direct-Local Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Complete S3.1-S3.3 so Polygon/Finnhub news ingest defaults to direct SQLite writes with honest local telemetry and an explicit Settings rollback.

**Architecture:** Add one read-only telemetry adapter over `provider_sync_runs` and `provider_sync_meta`, then overlay only the news status while direct routing is active. Resolve routing with explicit precedence `env > profile > default ON`, expose it through `/news/status` and `/news/settings`, and render a focused Settings panel. Keep `ibkr_news`, IV, fundamentals, the PG mirror implementation, and all existing market fallback controls unchanged.

**Tech Stack:** Python 3, SQLite, FastAPI/Pydantic, React/TypeScript, pytest, Vitest/Vite.

---

### Task 1: S3.1 Direct-News Telemetry

**Files:**
- Create: `src/news_sync_status.py`
- Create: `tests/test_news_sync_status.py`
- Modify: `src/api/routes/market_data.py`
- Modify: `src/tools/data_coverage_tools.py`
- Modify: `src/service/provider_health.py`
- Modify: `tests/test_market_data_admin.py`
- Modify: `tests/test_data_coverage_tools.py`
- Modify: `tests/test_provider_health.py`

- [x] Add failing tests for absent telemetry, latest run per provider, successful aggregate runs with current per-ticker errors, and provider isolation.
- [x] Run the focused tests and verify they fail because `read_news_sync_status` is missing.
- [x] Implement a read-only SQLite adapter returning the existing sync-summary fields plus provider-level run/error detail.
- [x] Add failing OFF/ON overlay tests at all three readers: OFF preserves `market_sync_meta`; ON replaces only `sync.news` and leaves prices/IV/fundamentals untouched.
- [x] Wire the gated overlays and verify focused plus existing market/news/provider-health tests pass.
- [x] Commit S3.1 independently.

### Task 2: S3.2 Default-On Routing and Backend Settings

**Files:**
- Modify: `src/news_providers.py`
- Modify: `src/api/routes/news.py`
- Modify: `tests/test_news_providers.py`
- Create: `tests/test_news_settings_route.py`

- [x] Add failing tests for unset default ON, profile false rollback, env false overriding profile true, env true overriding profile false, and default direct scheduler routing.
- [x] Implement explicit boolean parsing and routing precedence without caching.
- [x] Add failing route tests for pure-read status and permission-gated persistence.
- [x] Declare `/news/status` and `/news/settings` before dynamic `/{ticker}` routes; return local DB coverage, routing origin, and direct telemetry.
- [x] Verify route, scheduler, provider, and news tests pass.
- [x] Commit backend S3.2 independently.

### Task 3: S3.2 Settings UI

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts`

- [x] Add failing display-helper tests for direct active, explicit rollback, and env override states.
- [x] Add typed `getNewsStatus` / `setUseLocalNews` API functions.
- [x] Add a compact News Ingestion Settings section showing local row coverage, telemetry, active routing, and the rollback toggle.
- [x] Run Vitest, TypeScript/Vite build, and fix only regressions caused by this slice.
- [x] Commit frontend S3.2 independently.

### Task 4: S3.3 Cutover Gate and Live Smoke

**Files:**
- Modify: `tests/test_data_scheduler.py`
- Modify: `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`

- [x] Pin G1: unset defaults Polygon/Finnhub direct; explicit OFF restores collector -> PG sync -> mirror.
- [x] Pin G2: `ibkr_news` still executes collector + `--news` sync, and mirror code still retains news/IV/fundamentals.
- [x] Pin G3-G5: direct telemetry, idempotency, FTS parity, and existing news identity invariants.
- [x] Run full relevant backend and frontend suites plus compile/build checks.
- [x] Run a gated live one-ticker provider smoke using the real profile and market DB: verify DB-sourced key, no PG sync/mirror, first-run continuity, FTS parity, and second-run idempotency.
- [x] Verify normal local news reads, update the design status honestly, retain the S3.0a backup until this gate passes, and record whether both eligible backups are deletable.
- [x] Commit verification documentation; do not remove the mirror, `ibkr_news`, IV/fundamentals paths, or backups as part of this slice.
