# Data Collection and Local Storage Plan

> **Status:** Active current-state authority
> **Updated:** 2026-08-16
> **Scope:** Collection modes, local persistence, writer ownership, scheduling,
> completeness, and operator controls. Provider-specific limits remain owned by
> `ARKSCOPE_PROVIDER_CATALOG.md`.

## 0. Decisions

ArkScope uses local domain stores. Each store has one explicit writer boundary,
typed read outcomes, and a visible freshness surface. Collection is divided into
manual backfill, scheduled incremental work, and ephemeral display reads.

The current files are:

- `profile_state.db`: user state, credentials, routes, schedules, and job history.
- `market_data.db`: prices, news, fundamentals cache, and market metadata.
- `macro_calendar.db`: economic series, observations, releases, and calendars.
- `sa_capture.db`: Seeking Alpha captures, comments, signals, and repair state.

No store silently substitutes another authority. A missing or incompatible local
store produces an honest empty or typed unavailable result according to its domain
contract.

## 1. Collection modes

| Mode | Purpose | Trigger | Persistence |
|---|---|---|---|
| Manual backfill | Seed or repair bounded history | Explicit operator or app action | Domain store |
| Scheduled incremental | Keep admitted sources current | App scheduler, per source | Domain store plus job history |
| Ephemeral display | Read a current quote or forming state | Visible user workflow | Memory unless a reviewed writer exists |

Manual and scheduled work share the same domain writer and lock. A manual request
must receive a typed busy or failure outcome; a scheduled request may defer before
recording an attempt when the writer is already occupied.

## 2. Sources and cadence

| Source | Default mode | Cadence / control | Target |
|---|---|---|---|
| Polygon news | Scheduled, manual available | Per-source setting | `market_data.db` |
| Finnhub news | Scheduled, manual available | Per-source setting and rate limits | `market_data.db` |
| IBKR news | Scheduled, manual available | Gateway-gated | `market_data.db` |
| IBKR prices | Scheduled delta, manual backfill | Gateway-gated | `market_data.db` |
| SEC company events | Default off, manual available | Daily candidate | `market_data.db` |
| FRED series and releases | Default off, manual available | Weekly candidate | `macro_calendar.db` |
| Finnhub calendars | Default off, manual available | Daily candidate | `macro_calendar.db` |
| Seeking Alpha extension | Event-driven | Explicit browser activity | `sa_capture.db` |

Source definitions, costs, authentication, and provider limitations are catalog
facts. This plan owns only trigger and persistence semantics.

## 3. Storage topology

### 3.1 `profile_state.db`

This is precious user state. It contains lists, notes, settings, credentials,
model routing, research runs, schedules, and local job telemetry. Backup and export
workflows must treat it as the primary user-owned asset.

### 3.2 `market_data.db`

This is the canonical local market store. SQLite WAL mode and bounded busy timeouts
support concurrent readers and controlled writers. Provider data may be regenerated,
but observations, coverage state, and collection outcomes must remain internally
consistent.

### 3.3 `macro_calendar.db`

This store owns economic events, earnings, IPO events, series metadata,
observations, release dates, and their revision history. FRED and Finnhub writers
share one fail-closed writer lease.

### 3.4 `sa_capture.db`

The browser extension and native host write this isolated capture store. Reads are
read-only where possible. Missing or malformed capture state is surfaced with typed
outcomes and never causes another store to be consulted.

## 4. Writer ownership

Each domain has one canonical writer implementation. Process-local locks coordinate
threads; file locks coordinate separate processes. Lock acquisition failure is never
treated as permission to continue unlocked.

Provider adapters normalize payloads before the writer boundary. UI components,
read tools, and health projections do not write provider rows. A new source with a
bursty or independent process shape must receive an inbox or isolated source store
unless the canonical writer can prove safe serialization.

## 5. Scheduler and telemetry

The app scheduler owns automatic collection. Every source has an explicit enabled
setting, interval, running state, last terminal outcome, and next eligibility.
Default-off sources remain off until the user enables them.

Canonical job names use `collect.*` or `fetch_*` identities defined by the owning
domain. A completed run invalidates the matching Settings read keys. Scheduled busy
deferral does not consume the interval; attended busy requests remain visible.

## 6. Completeness and integrity

Collectors must distinguish complete, partial, skipped, and failed outcomes. Partial
work records its continuation or missing scope. Pagination and bounded provider
windows continue until the requested interval is covered or the provider returns a
typed terminal condition.

Deduplication is an integrity aid, not a substitute for window coverage. A collector
may stop early only when its persisted frontier and the provider ordering prove the
remaining page is already covered.

## 7. Operator controls

Settings exposes per-source schedule controls, an explicit run action, recent
outcomes, and typed errors. Local status reloads are GET-only. Provider work starts
only from an explicit run action or an enabled scheduler source.

Heavy repair and backfill operations remain attended. They report scope, progress,
partial completion, and retry boundaries rather than hiding work behind a generic
success message.

## 8. Read surfaces

Read APIs and tools consume domain capabilities rather than storage implementation
details. They return typed unavailable results when required local state is absent.
Current quote and other ephemeral reads do not imply persistence.

## 9. Verification

Changes to collection or storage require:

1. hermetic unit and integration coverage over scratch stores;
2. socket guards for tests that claim local-only execution;
3. writer-lock contention coverage across threads and processes;
4. byte or row-projection checks for production assets when a run claims no mutation;
5. browser verification for Settings controls and truthful status copy; and
6. mutation coverage for fail-open, hidden provider work, and stale-state regressions.

## 10. Deferred product decisions

Continuous streaming quotes, calendar-aware orchestration beyond per-source cadence,
new paid-provider ingestion, and broader storage-owner consolidation require separate
reviewed designs. They must reuse the ownership and honesty contracts above rather
than adding implicit fallback paths.
