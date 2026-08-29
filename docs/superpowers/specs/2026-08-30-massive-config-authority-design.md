# Massive Configuration Authority Design

Date: 2026-08-30
Status: offline implementation complete; production operations and merge gated

## Decision

`massive.api_key` is the only current profile-database authority for the
Massive reference, news, and market-data credential. `MASSIVE_API_KEY` remains
the process bridge used by existing clients. `POLYGON_API_KEY` is retired.

The rename applies only to configuration and provider-health identities.
Historical source IDs such as `polygon`, `polygon_news`, stored news rows, and
evidence provenance remain unchanged because they identify the source lineage
that produced existing data.

## Environment Boundary

Neither `MASSIVE_API_KEY` nor `POLYGON_API_KEY` may be loaded from, imported
from, or restored from `config/.env`. The generic environment loader must also
exclude both names, including cleanup of values it loaded before this rule was
installed. Its raw parser may retain them solely as inert input for a future
explicit migration. A real operator process environment may still override the
profile value. A future user-selected settings import/export artifact is a
separate feature and must not be implemented as an implicit `.env` fallback.

## Compatibility Migration

The legacy profile row is `polygon.api_key`; the current row is
`massive.api_key`. Migration is an explicit, network-free profile operation,
not startup DDL or an automatic startup write.

- Legacy only: move the row to `massive.api_key`, preserving the exact value
  and `updated_at`.
- Current only or neither: no-op.
- Both with equal values: keep the current row and remove the legacy row.
- Both with different values: fail closed and leave both rows unchanged.

Preflight returns only state and hashes, never the credential. Apply must bind
to that preflight state and re-check it under one write lock.

## Runtime Projection

Settings, provider health, connection tests, scheduler configuration checks,
and lifecycle listing acquisition use the current `massive` configuration ID.
Code that reads or stores market/news provenance may continue to use
`polygon` identifiers.

## Authority Stops

Offline code and scratch-database tests are authorized. Reading or writing the
production profile database, calling a provider, starting the App, merging,
and pushing remain separate decisions.
