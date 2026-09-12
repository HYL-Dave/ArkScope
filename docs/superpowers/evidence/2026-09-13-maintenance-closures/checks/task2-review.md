# Task 2 C11 Spec And Quality Review

Reviewed base `eec66b9e129eb3383c1c6b136f6d10953a3568f8` through
`a4bf0a739fabba418138829f3ce501edc6dab5f8` in `/tmp/arkscope-research-output-boundary`.
HEAD matches the diff package; read-only comparison confirms its 26 changed
product/test files match that commit.

## Findings

### R1 - P2: Health retains legacy news telemetry when the current read fails

Location: [src/service/provider_health.py:241](/tmp/arkscope-research-output-boundary/src/service/provider_health.py:241).

`sync` already contains `read_sync_meta()`'s legacy news row at line 239.
If `read_news_sync_status()` raises, replacement at line 243 never happens;
the handler only appends a note, and line 526 returns that legacy row as
`local_market.sync.news`. For example, a readable `market_sync_meta` news row
alongside a malformed `provider_sync_runs` table reaches this path: the current
reader's query at `src/news_sync_status.py:42` raises a SQLite error. Massive and
Finnhub then have no ingest success, but the same response still exposes the old
news success/counters as current sync telemetry.

This is an existing exceptional-path pattern left unresolved by the closure,
not a newly introduced publication-time fallback. The error note makes the
failure visible, but does not make the retained legacy news authoritative.
Clear only the provisional legacy news slice before acquisition, or on this
failure path, while preserving the existing note and all non-news sync entries.

Controller-owned focused test recommendation, not executed: add
`test_health_clears_legacy_news_when_current_telemetry_read_fails` in
`tests/test_provider_health.py`. Use a disposable valid legacy sync row plus a
malformed current telemetry table, allowing the real legacy reader instead of
the autouse fixture's `{}` stub. Assert the degradation note, no legacy news
success/counters in `local_market.sync.news`, no provider publication fallback,
and unchanged price authority/non-news telemetry. The new corruption regression
tests the standalone overlay, not this health exception boundary.

No other reportable findings in the bounded review.

## Spec Verdict

**Needs changes for R1 before unconditional telemetry-authority closure.**
The remaining requested contracts are satisfied by static inspection:

- Obsolete constants/helpers/profile reader, resolver arguments, PUT setter/model,
  five news-only status fields, frontend setter/label, and five paired locale
  leaves are physically removed. Focused symbol/call-site checks found no retained
  product callers, forwarding aliases, or ignored legacy kwargs.
- Current normalized setting/env validation, malformed requirement rejection,
  source-required blocking, direct/default selection, and `legacy_local` remain.
  The profile query reads only the current key, preserves typed configuration
  failures and missing-store noncreation; scheduler calls remain compatible.
- GET news status still reads actual telemetry, as it did before. The normalized
  setter still checks permission before writing only its own key. Removed PUT
  naturally returns 405 through the retained ticker route; all five current news
  routes survive. No auth or permission boundary is removed elsewhere.
- The standalone overlay replaces only news, including `None`, without mutating
  its input; SQLite errors propagate. Coverage/status callers retain their price,
  SA/cache and stored-SEC controls. Massive/Finnhub ingest success no longer uses
  article publication time; article signals remain visible. IBKR's combined
  price/news health calculation and its assertions are unchanged.
- The URI fix is confined to `read_news_sync_status` using resolved `as_uri()`
  with `mode=ro`, its existence guard and connection cleanup. Named `?`/`#`
  populated/missing-store tests check telemetry, unchanged bytes and no siblings.
  Locale `write`/`read`/`authority` and similarly named macro fields remain.

## Quality Verdict And Limitations

**Needs changes for R1; otherwise the patch is narrow and maintainable.**
Real disposable run/meta fixtures replace obsolete flag-selected mocks without
weakening healthy/stale/key-precedence assertions. Distinct ingest/publication
timestamps, persisted old-value invariance, required/current-malformed blockers,
permission ordering and physical-absence owners cover the intended change.
The node ledger explains 34 removals and 63 additions, including the redundant
18-to-6 route matrix and the accurately renamed test that never asserted 409.

Additional collateral is justified: `tests/test_api.py:169` updates its existing
lifespan route census from 223 to 222 and asserts the exact surviving news routes,
without weakening lifespan/scheduler isolation. `apps/arkscope-web/src/i18n/resources.test.ts`
changes Settings 1019 to 1014 and total 2962 to 2957 for precisely five retired
leaves per locale, adding their explicit absence to existing inventory checks.

Existing receipts inspected: final scoped 329 passed, adjacent 303 passed,
frontend 75 passed, controller scoped 329 passed; typecheck/i18n commands exited 0.
These are separate historical runs, not an additive count or fresh verification.
Independent inverse/restoration evidence was reviewed from the report and source
audit, not rerun. Full frozen suites/build/census and broad final review remain
controller-owned; this is task review, not integration acceptance.

Read the brief/report and binding current-checkout plan, then the supplied diff
as the changed-file view. The first tool output was truncated mid-function; only
the omitted span and its boundary context were recovered. Follow-up reads were
limited to concrete contracts/call sites and current maintenance scratch.
No agents, tests, imports of product code, network/private-data access, mutations,
or Git writes were performed, except creating this requested review via apply_patch.
