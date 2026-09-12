# Current News Routing Cleanup

> Use superpowers:executing-plans or superpowers:subagent-driven-development, RED-first. This plan is source-verified preparation, not implemented behavior.

**Goal:** Finish C11's obsolete local-news switch removal without changing the
actual normalized/direct writers, news contents, provider credentials or cursors.
**Source anchor:** `ae2055e3`; user authorized continued cleanup. Do not modify
product/test files while the current integration full-backend run is frozen.

## Verified Contract

- `resolve_news_write_route` never uses the old local toggle to choose between
  direct-local and normalized. It does still reject malformed old values. The
  earlier statement that the switch has only display effects was incomplete.
- `/news/status`, `overlay_news_sync_status` and provider health still use that
  independent switch, so false can hide actual provider_sync observations.
- `PUT /news/settings` only persists the abandoned switch. The frontend setter
  has no product caller; `newsRoutingLabel` is also unused outside its own tests.
- Normalized settings, source-required normalized writes and their malformed
  configuration blockers are live. So are `parse_news_toggle`, real news fetch/
  parse, financial_cache and current normalized-to-news projection.
- C12 collector CLIs still have real main entrypoints. They are not authorized
  leaf deletions in this patch. No stored file/key/table is deleted here.

## Exact Change

Remove USE_LOCAL_NEWS_KEY, ENV_USE_LOCAL_NEWS, resolve_use_local_news,
use_local_news_enabled and that read-only profile helper from news_providers;
keep the shared boolean parser and real provider adapters. Remove obsolete
local_value/local_env parameters and reads from normalized routing. Old keys
that remain in stored data no longer affect the route, including malformed
values; this does not weaken validation of current normalized settings or
source requirements. Do not rename the live legacy_local writer enum.

Delete PUT /news/settings and LocalNewsToggle. Remove the five status fields
use_local_news_setting, setting_explicit, env_override, env_value, direct_active.
Keep GET /news/status, PUT /news/settings/normalized-writes and the current
write_route/reason, normalized settings, local stats and sync observations.
Do not remove similarly named fields from macro or other APIs.

Always obtain current news telemetry through read_news_sync_status. No fallback
from a publication timestamp to last_success when telemetry is absent. Preserve
all non-news sync entries and existing typed missing/error behavior. Missing DBs
must remain uncreated. Actual old persisted-key disposal is a separate bounded
inventory/backup operation, not automatic startup cleanup.

## Owned Files

- Product: `src/news_providers.py`, `src/news_normalized/routing.py`,
  `src/api/routes/news.py`, `src/news_sync_status.py`,
  `src/service/provider_health.py`; `src/news_direct.py` stale prose only.
- Frontend: `apps/arkscope-web/src/api.ts`, `marketDataDisplay.ts`; delete only
  the unused setter/helper and corresponding NewsStatus fields.
- Paired locale files: `src/i18n/resources/{en,zh-Hant}/settings.ts` under the
  frontend root. Remove only newsStorage.routing directEnvOn/directEnvOff/
  localCompatibility/directExplicit/directDefault after rechecking consumers.
  Keep routing.write, routing.read and routing.authority subtrees.
- Primary tests: `test_news_settings_route.py`, `test_news_providers.py`,
  `test_news_normalized_routing.py`, `test_news_sync_status.py`,
  `test_provider_health.py`; add `test_news_routing_cleanup.py` if a separate
  cross-entrypoint owner reduces fixture coupling.
- Constructor/monkeypatch collateral: `test_data_coverage_tools.py`,
  `test_stored_sec_projection.py`, `test_market_data_admin.py`,
  `test_data_scheduler.py`. Remove obsolete helper patches only after moving
  useful assertions to current behavior; retain their actual data/price owners.
- Route-count collateral: `test_security_lifecycle_routes.py`, count223->222
  for the one deleted PUT route, with explicit absence and exact retained sets.
- Frontend tests: `SettingsNewsStorage.test.ts`, `SettingsLocalStorage.test.ts`,
  `marketDataDisplay.test.ts`; remove old mock/fields and obsolete display-only
  cases while keeping real normalized-write and authority controls.
- Current docs and provider/tool catalogs only where they advertise this switch;
  dated evidence remains historical. No unrelated CSS/locale bulk deletion.

## RED-First Acceptance

- [ ] Baseline these scoped tests using the current plan's disposable offline
  runner. No provider, real DB/config, external CLI session, schema disposal or
  App restart. Record exact collected/pass/skip counts rather than predicting.
- [ ] Add named current-writer/status owners before product edits. With an
  actual disposable profile holding old false or malformed values, require
  current normalized/direct route selection and real provider_sync timestamps,
  errors and counters to remain visible through status, overlay and health.
  Expected RED: stale fields, suppressed telemetry or an old-value BLOCKED route.
- [ ] Add physical API/helper absence owners and require the old PUT setter to
  be unmounted. The surviving GET `/news/{ticker}` also matches the literal
  path `/news/settings`, so Starlette returns405 for PUT, not404; do not add a
  compatibility stub or remove the useful ticker route to force404. The
  current normalized setter retains permission checks and writes only its key.
  Expected RED: old PUT still mounted or obsolete helper still importable.
- [ ] Preserve nonempty current-news/price/SA/cache controls, normalized-required
  rejection, malformed-current-setting rejection, corrupted DB failure and
  missing-store noncreation. Do not substitute empty fixtures for real reads.
- [ ] Implement the bounded changes. Transfer old rollback-only tests to the
  current contract, enumerate every removed/added node and re-scan call sites.
- [ ] GREEN all owned backend tests plus direct/normalized news, collector adapter,
  current investigation-news, API and SEC projection controls. Run frontend
  tests/typecheck/i18n and ensure the five locale leaves have no retained caller.
- [ ] Inverse-check telemetry suppression and old-value validation independently:
  each must fail its named owner. Restore and rerun the unmutated controls.
- [ ] Independent review, frozen full backend and mechanical census before
  acceptance. No master merge/push, no installation or stored-data cleanup
  implied by source acceptance. C12 and SEC citation/export/recovery remain open.

## Execution Clarifications

September13 source preflight distinguishes two health signals. C11 removes the
obsolete switch and the Massive/Finnhub fallback from publication time to ingest
success. The IBKR market-health combination of prices/news is unchanged by this
switch and is not redesigned here. Retain its current tests. Health fixtures
that intentionally selected old rollback must instead supply actual disposable
provider_sync run telemetry; preserve their stale/error/key-precedence checks,
and add a missing-telemetry control rather than merely weakening expectations.
