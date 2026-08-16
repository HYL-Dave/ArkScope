# Macro and FRED Product Semantics

- **Status:** current product authority
- **Updated:** 2026-08-16

## Product Model

Macro data has three independent states:

1. provider credentials and availability;
2. durable local coverage and freshness;
3. scheduled refresh enablement.

The UI must not collapse these states into one label. A configured provider can
have useful local data while automatic refresh is off, and a refresh failure does
not erase previously admitted observations.

## Storage And Reads

`data/macro_calendar.db` is the sole macro store. Read routes and agent tools use
the local snapshot and report observation dates and fetch receipt times. Missing
or stale data is visible as such; it is not converted into a provider failure.

The primary FRED snapshot covers the curated series used by the research surface.
Release dates and Finnhub calendar tables remain separate domains because their
coverage and freshness differ.

## Refresh Ownership

The scheduler registry owns five macro sources:

- `fred_series`;
- `fred_release_dates`;
- `finnhub_economic_calendar`;
- `finnhub_earnings_calendar`;
- `finnhub_ipo_calendar`.

Each source has an independent interval and defaults to disabled. Settings exposes
both the toggle and an explicit run command. Mount, focus, visibility, idle warmup,
and local status reloads must never start a provider request.

All five sources write through the single fail-closed macro writer lease. Only one
macro writer may run at a time. A scheduler collision is deferred without consuming
the source interval; an attended collision returns a visible typed result. A source
that remains due may run on a later tick.

## Settings Contract

The Macro section owns the five macro schedule rows. The general Data Sources
section owns non-macro schedules. Both surfaces share one group-scoped schedule
controller, so one polling cycle means one status request regardless of how many
visible consumers render it.

Provider health, local table coverage, and schedule status remain distinct facts:

- provider health answers whether credentials and the provider path are usable;
- coverage answers what is stored and when it was last received;
- schedule status answers whether automatic refresh is enabled and what the last
  run did.

Unknown schedule targets stay visible in the general table rather than disappearing.
Descriptions may wrap; source names and controls must not overlap at supported
desktop or mobile widths.

## Failure And Freshness Rules

- A failed refresh preserves the last admitted local snapshot.
- Job telemetry uses canonical `fetch_*` identities and stable typed errors.
- Snapshot reads do not create files or schemas.
- Manual runs and scheduled runs use the same execution functions.
- No source may claim automatic freshness unless its schedule is enabled and a
  successful run has been recorded.

## Deferred Work

New macro providers, expanded historical-vintage consumers, and automatic defaults
require separate product decisions. They must not be inferred from the existence of
the current local tables or provider credentials.
