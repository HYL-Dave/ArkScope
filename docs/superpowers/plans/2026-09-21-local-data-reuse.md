# Local Data Reuse

Durable cross-source policy:
[Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md).
This plan records the completed reuse correction; later trigger/freshness
changes must also update the root-level policy.

## Decision

The September 21 user clarification supersedes the FD refresh-by-default policy.
Controllable reuse is the normal path, not opt-in. This workbench retains both
local research and future live-market assistance; neither implies retiring the
other. Subscription upgrades can add coverage and throughput, but a single live
quote does not establish all account entitlements or trading readiness.

## This Slice

- [x] RED-first defaults, repeat requests, stored-only side effects and concurrency.
- [x] One acquisition-age policy for FD and the two legacy SEC financial tools.
- [x] Four-channel fundamental-analysis `freshness=auto|stored|refresh`, optional strict integer age.
- [x] Detailed-financials Finnhub supplements use a separate short reuse window.
- [x] Related regression and frozen-revision complete backend/frontend acceptance.
- [x] Local merge, main-tree recheck and cleanup of this slice's branch/worktrees.

Acceptance: frozen `a400a52b` passes 11,843 backend tests with the same 12 live
skips, 1,867 frontend tests, build/typecheck, i18n and eight desktop tests. The
main-tree `5089ccec` recheck passes 867 tests with two existing live skips. This
slice's branch and two test worktrees are removed; no push or production change
was made. Evidence: `docs/superpowers/evidence/2026-09-21-local-data-reuse/README.md`.

`auto` first reuses a valid local observation. The existing
`data_preferences.fundamentals_sources.refresh_days` is the default authority
(seven days when unset), independent of storage TTL. Earnings history/calendar
default to one hour, configurable separately. Explicit `max_age_seconds` overrides
these defaults. `stored` performs no acquisition or cache write; without an age it
can reopen an old observation. `refresh` bypasses old observations, but may share
the successful result of an identical refresh already in flight. It does not
authorize paid requests: FD admission still requires an enabled, bounded policy.

Scope includes provider, dataset, ticker, period, request limit and storage owner.
Concurrent acquisitions use a bounded, fail-closed process lock, then recheck
the saved result. Waiting on a failed acquisition is not permission to repeat it.
No SQLite write transaction spans external I/O. Cache failures must not be labeled
successful persistence. Distinct scopes cannot satisfy each other.

Results expose provider, acquisition time, age, reuse policy and retrieval mode.
The constant `latest_period_verified=false` is removed: no latest-period probe
has been implemented. A reuse interval is not a promise of unchanged filings.
Period-bound answers are only immutable when their source version is pinned;
this legacy response cache is not a versioned financial archive.

An unsuccessful or ambiguous SEC/Finnhub fetch is not a fresh empty dataset.
No automatic stale fallback after an explicit refresh failure. Qualified local
valuation prices are recomputed on each detailed-financials read, never stored
inside a reusable static financial payload. Live quote/portfolio requirements
are not weakened by this policy.

## Boundaries

This is not a generic scheduler or a new provider subscription. SA reverse
triggering, scope-aware scheduler job joining, broker portfolio refresh,
persistent streaming and unattended-service lifecycle remain separate slices.
Legacy financial formula and earnings-event alignment defects remain open.
External MCP still needs independent authorization; an internal `auto` default
does not confer permission to spend externally.

Tests use isolated databases and fake transports. No production data changes,
provider HTTP, Gateway calls, purchases, App restart or push are authorized here.

The existing OAuth allowlists exclude `get_detailed_financials`; this slice does
not expand authorization. Its registry and two API-key adapters expose the same
controls, and the two OAuth refusals remain pinned. Obsolete FD-only arguments
are rejected rather than silently ignored by native adapters (which would turn
an old stored-only call into automatic acquisition).
