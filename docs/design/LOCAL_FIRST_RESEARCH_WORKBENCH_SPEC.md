# Local-First Financial Research Workbench

> **Status:** Active architecture authority
> **Updated:** 2026-08-16
> **Scope:** Product layers, local profile, storage ownership, portability, UI,
> scheduler, external ingestion, and deferred architecture work.

## 0. Locked boundary

ArkScope is a single-user financial research workbench. The app, agent, data
services, and any desktop wrapper operate on one local profile and its domain stores.
No UI or agent path invents a second persistence authority.

This specification locks eleven areas: product layers, deployment invariant,
profile contract, storage ownership, portability, page structure, scheduler
contract, data-capability boundaries, external ingestion, security, and deferred
work.

## 1. Product architecture

The product has five layers:

1. **Workbench UI** presents research, evidence, settings, and operations.
2. **Agent layer** owns reasoning, tool dispatch, memory use, and research runs.
3. **Data layer** owns provider adapters, normalized reads, local search, and joins.
4. **Profile layer** owns user state and domain databases.
5. **Portability layer** owns export, import, manifests, and profile locks.

Dependencies point downward. Data modules do not call agent or UI code, and external
ingestion clients do not write user-state tables.

## 2. Deployment invariant

The local web app and any desktop wrapper read the same profile directory. A wrapper
may manage process lifecycle and native integration, but it does not introduce a new
configuration or storage layer.

All paths come from explicit resolvers. Tests and temporary worktrees redirect those
resolvers to scratch locations so developer data is never an implicit fixture.

## 3. Profile contract

The profile contains precious user state, research records, local settings, model
credentials, schedules, and export metadata. The profile location is resolved once
and passed to owners; leaf modules do not infer it from the current working directory.

Credentials remain in the ignored local profile database. Exports are sanitized,
manifested, versioned, and written under a single-writer lock. Provider caches and
regenerable market observations are excluded from a profile export unless the export
contract names them explicitly.

## 4. Storage ownership

Current storage is split by durability and writer shape:

| Store | Ownership |
|---|---|
| `profile_state.db` | User state, credentials, routes, research runs, schedules, job history |
| `market_data.db` | Prices, news, fundamentals cache, company events, market metadata |
| `macro_calendar.db` | Economic series, observations, releases, and calendar events |
| `sa_capture.db` | Seeking Alpha captures, comments, signals, and repair state |

SQLite WAL mode and bounded busy timeouts support concurrent local readers. Each
domain has one canonical writer and a fail-closed cross-process lock where separate
processes can write. Read paths return honest empty or typed unavailable outcomes;
they do not consult another store.

Analytic read models may be materialized from these stores in a future slice, but
they remain derived and cannot become an unreviewed write authority.

## 5. Portability

Portability is explicit export and import, not hidden synchronization. An export:

- takes the profile lock;
- produces sanitized database copies;
- includes a versioned manifest and checksums;
- excludes secrets and machine-local runtime files; and
- is verified by importing into a fresh profile.

Conflict resolution for future selective synchronization is deferred. Current import
is an attended operation with preview, validation, and a rollback boundary.

## 6. Workbench information architecture

Primary surfaces are research, evidence, portfolios, market data, models, and
Settings. Settings groups related sections, mounts only the active group, and uses a
single controller for shared polling or cached reads.

Every read surface has a typed loading, available, empty, partial, and unavailable
contract as appropriate. Every write action identifies its owner, permission gate,
busy behavior, and invalidated read keys. Copy describes user-visible facts rather
than storage implementation history.

## 7. Scheduler contract

The app scheduler owns automatic work. Sources are registered with stable IDs,
explicit enabled settings, cadence, writer target, and canonical job names. Default
off means no provider request until enabled or manually run.

Scheduled work may defer before recording an attempt when its writer is occupied.
Attended work receives a visible busy outcome. Restart continuity is rebuilt from
local scheduler state and local job history. Scheduler startup is part of the real
application lifespan and must be covered by hermetic tests.

## 8. Capability boundaries

Callers depend on the smallest domain capability they use. Structural injection is
allowed for tests and specialized owners; configuration-selected implementation
routing is not. Capability protocols are measured from real call sites and may not
grow speculatively.

Errors stay in their domain vocabulary. Missing local state, provider failure,
credential failure, and transport failure are distinct and must not collapse into a
generic fallback result.

## 9. External ingestion

The Seeking Alpha extension writes only through its native-host capture contract.
Other browser or provider clients submit normalized bounded envelopes to their
domain writer. Diagnostics are typed, size-limited, secret-screened, and retained
only where they help explain a durable outcome.

External clients never write `profile_state.db` directly and never receive raw
credential material from status APIs.

## 10. Security and integrity

The application uses explicit permission gates for sensitive writes, bounded payloads,
closed error vocabularies, path and symlink validation, and deterministic event
identities. Tests that claim hermetic behavior run with socket guards and scratch
stores. Production-asset equality claims require pre/post manifests after writers are
quiescent.

## 11. Deferred architecture work

The following require separate reviewed designs:

- selective cross-machine synchronization;
- continuous quote streaming and broader calendar-aware orchestration;
- vector search and large analytic read models;
- packaging choices beyond the shared-profile invariant;
- legacy-agent command-line product disposition; and
- broader runtime ownership and CSS boundary consolidation.

Deferred work must preserve the local ownership, fail-closed locking, typed state,
and explicit-trigger contracts in this specification.
