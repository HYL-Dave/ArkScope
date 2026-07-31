# ArkScope Price Collection Partial-Truth Design

> **Status: LIVE COMPLETE - MERGED AND NATURAL-CYCLE VERIFIED**
>
> **Date:** 2026-07-28
> **Grounding commit:** `542776c2e00ae1737d5b424a3b8858b079a63e38`
> **Scope:** direct-local 15-minute price top-up, its per-ticker telemetry,
> sanitized worker contract, scheduler outcome, and existing Settings status
> presentation

## 1. Purpose

Coverage v2 correctly reported `indeterminate_tickers` for 2026-07-27: 149
current-universe tickers had all 26 RTH slots, while LCID had no stored bars for
the day. The collection path nevertheless persisted a successful run and a
successful LCID provider frontier after fetching no LCID rows.

This is not a Coverage v2 classifier defect. It is a collection-truth defect:
one batch can write thousands of valid rows while silently failing to resolve a
target for one ticker. The batch is partially successful, not wholly failed and
not wholly succeeded.

This slice makes that partial truth structural. A ticker whose pre-fetch
zero-bar target remains zero-bar after the write receives a stable unresolved
reason. The direct collector, worker, scheduler state, provider telemetry, and
Settings presentation derive their outcomes from those per-ticker facts.

The design does not guess whether the upstream cause was IBKR pacing, timeout,
error 162, a genuinely empty IBKR response, unavailable Polygon fallback, a
halt, no trades, or another condition. Those causes require a later structured
provider-outcome protocol.

## 2. Grounded Current State

### 2.1 Code facts at the grounding commit

1. `src.market_data_direct.detect_price_gaps()` defines a target day as a
   completed US trading day with zero stored rows for the ticker and interval.
   It is a day-presence check, not a Coverage v2 slot-grid check.
2. `_run_backfill_body()` records that pre-fetch zero-bar set in `gaps`, fetches
   the entire completed-day window, writes returned rows, and never checks
   whether any original zero-bar target remains empty.
3. `IBKRDataSource.fetch_historical_intraday()` catches request/chunk exceptions,
   logs them, and continues with an empty list. The caller cannot distinguish
   that shape from a genuine empty response.
4. `_fetch_rows_for_gaps()` invokes Polygon when the IBKR result is empty.
   `PolygonDataSource.fetch_intraday_prices()` also returns an empty list for a
   non-OK response.
5. An empty final row list is therefore treated as a successful per-ticker
   fetch. `_upsert_provider_meta(..., error=None)` advances `last_success`,
   clears `last_error`, and keeps the previous `last_bar_datetime` when the new
   value is `None`.
6. `provider_sync_runs` is always finalized as `succeeded` after the per-ticker
   loop unless a non-per-ticker exception escapes. Existing per-ticker errors
   are isolated but do not affect the run status.
7. `src.prices_runtime.sanitize_result()` hard-codes `status="succeeded"`, even
   when its input contains per-ticker errors.
8. The scheduler treats prices-worker exit code zero as success and does not
   inspect a structured partial outcome. Its durable state supports `partial`,
   but that path currently belongs only to normalized news writers.
9. `job_runs` and `provider_sync_runs` accept only `running`, `succeeded`, and
   `failed`. Neither table can persist `partial` as a status without a schema
   migration.
10. The frontend already supports a durable scheduler `partial` state and does
    not show a Continue action when no continuation exists. It has no price
    unresolved-count contract today.
11. `prices` contains no row-level provider/provenance column. The
    `provider_sync_meta.provider` value records the configured primary path for
    the run; it does not prove whether an individual stored row came from IBKR
    or Polygon fallback.
12. Three-value `job_runs.status` projection is not consistent across existing
    degraded work. In `src.service.data_scheduler.run_source()`, normalized-news
    writers set scheduler durable status to `partial` while `ok` remains true,
    so `store.finish_run()` persists their `job_runs` row as `succeeded`.
    `src.sa.extension_run_protocol` instead maps semantic `degraded` to
    `job_runs.status='failed'`. Normalized-news `partial` is not uniformly
    resumable: current covered shapes include both a real continuation and
    `continuation=null`.
13. `DataSourcesSection.jobOutcome()` renders the latest `job_runs` status as a
    generic check/cross glyph, while `renderLastRun()` also renders the
    scheduler durable-state badge. Consequently, existing normalized-news
    partial work can appear as check-plus-partial, while the price projection
    in LD 10 will appear as cross-plus-partial. This is a
    projection/presentation inconsistency, not evidence that either audit
    glyph is the semantic partial-state owner.

### 2.2 Dated production observations

All observations in this subsection were read with SQLite `mode=ro` on
2026-07-28. They are evidence for the defect shape, not test fixtures or
acceptance constants.

- The active universe contained 150 tickers.
- Coverage v2 reported 2026-07-27 as a normal 26-slot session with 149 complete
  tickers, zero partial tickers, and one indeterminate ticker: LCID.
- LCID's latest stored 15-minute row was
  `2026-07-24T23:45:00+0000`; it had no 2026-07-27 row.
- Seven `collect.ibkr_prices` runs from `01:32Z` through `12:18Z` failed loudly
  because the child produced no parsable output. This design does not rewrite
  that already-honest failure class.
- The `22:19Z` run scanned all 150 tickers, reported 150 zero-bar targets,
  inserted 3,874 rows, and persisted `succeeded` with zero errors.
- A later `00:19Z` run scanned all 150 tickers, reported one remaining gap,
  inserted zero rows, and again persisted `succeeded` with zero errors.
- The current LCID `provider_sync_meta` row was the only 15-minute row with a
  recent success frontier and a data frontier older than 2026-07-25:

  ```text
  provider          ibkr
  ticker            LCID
  interval          15min
  last_success      2026-07-28T00:22:54+00:00
  last_bar_datetime 2026-07-24T23:45:00+0000
  last_error        NULL
  rows_added        0
  ```

- Two independent public market-data pages showed LCID trades on 2026-07-27,
  including non-null open/high/low values and intraday volume. Their intraday
  volume values differed, so neither exact value is treated as an authority or
  pinned in tests. Both values were nonzero. The runtime reason in this design
  does not depend on proving that LCID traded.
- LCID stored 58-64 rows per day from 2026-07-13 through 2026-07-24, spanning
  approximately `08:00Z` through `23:45Z`. That shape is consistent with an
  extended-hours Polygon response, but the schema has no provenance with which
  to prove it. It does not support the claim that Polygon fallback has either
  always failed or definitely succeeded.

### 2.3 Reproduced baseline

The following focused baseline is green at the grounding commit:

```text
pytest tests/test_market_data_direct.py \
       tests/test_prices_runtime.py \
       tests/test_data_scheduler.py -q
151 passed
```

The merged repository baseline remains backend `4722` collected and frontend
`96 files / 1074 nodes` from the SA feed closeout. The implementation plan must
rederive canonical counts and hashes before product edits; this paragraph is
not a substitute for Task 0.

## 3. Scope

### 3.1 In scope

- recheck each pre-fetch zero-bar target after returned rows are committed;
- classify unresolved target days per ticker without guessing an upstream
  cause;
- derive direct-collector `succeeded`, `partial`, or `failed` from per-ticker
  terminal facts;
- prevent unresolved tickers from advancing provider success or clearing their
  current error;
- derive `provider_sync_runs`, sanitized worker, scheduler durable state, and
  `job_runs` projections from the same facts;
- carry bounded unresolved counts and ticker IDs through the sanitized worker
  boundary;
- render a localized price-partial explanation in the existing Data Sources
  schedule row without adding a manual recovery control;
- prove that idempotent zero-row runs and low-volume partial days are not
  reclassified merely because `rows_added == 0`; and
- add RED-first backend, frontend, and telemetry regression coverage.

### 3.2 Out of scope

- changing Coverage v2 enums, slot-grid classification, calendar authority,
  API DTO, or the `indeterminate_tickers` presentation;
- deciding whether an absent 15-minute slot is a no-trade interval, halt,
  entitlement issue, provider omission, or repairable gap;
- changing the legacy top-up target calendar or replacing its fixed close
  buffer with the Coverage v2 calendar in this slice;
- normalizing `job_runs` partial projections across normalized news, prices,
  and the SA extension, changing non-price persistence, or redesigning the
  Data Sources audit-glyph/durable-state presentation;
- changing provider-health aggregation or presentation;
- requiring every RTH slot to be present after collection;
- changing IBKR or Polygon adapter return types, retry policy, request count,
  fallback order, or error handling;
- claiming that Polygon fallback is healthy or unhealthy without provenance;
- adding row provenance, a second price table, or any DB schema migration;
- adding automated repair, continuation, retry, backfill controls, or a new
  scheduler source;
- provider/Gateway calls during implementation review;
- automatically repairing LCID or any production ticker;
- changing formatter behavior, price values, or existing OHLCV rows; and
- EIR-002 or root `scripts/` retirement work.

## 4. Terms

### 4.1 Zero-bar target

A `(ticker, interval, market_date)` returned by the existing pre-fetch
`detect_price_gaps()` call. The target is based on the writer's present
day-presence contract: no stored row exists for that date. This slice does not
reinterpret it through the Coverage v2 RTH slot grid.

### 4.2 Resolved target

After the fetched rows have been inserted, at least one stored row exists for
that exact ticker, interval, and target date.

### 4.3 Unresolved after fetch

After insertion, a pre-fetch zero-bar target still has no stored row. The stable
machine reason is:

```text
price_day_unresolved_after_fetch
```

This reason states only a local before/after fact. It does not mean
`provider_failed`, `ticker_did_not_trade`, `not_entitled`, or
`unavailable_at_source`.

### 4.4 Per-ticker issue

Either an existing per-ticker exception or at least one unresolved target day.
Unresolved target days are a typed subset of per-ticker issues.

## 5. Locked Decisions

### LD 1 - Coverage v2 remains the read-side truth owner

The 2026-07-27 `indeterminate_tickers` result is correct for the stored evidence
and must not be renamed, suppressed, or special-cased for LCID. Collection
telemetry learns from that defect; Coverage does not bend around it.

### LD 2 - External trading evidence is corroboration, not runtime authority

The fix does not need a live quote, daily bar, halt feed, or second provider to
classify `price_day_unresolved_after_fetch`. Even if a future zero-bar target
turns out to be a legitimate full-day no-trade or halt case, the honest local
statement remains that collection did not resolve the target.

### LD 3 - Low volume is not inferred as failure

`rows_added == 0` is not an error. A pre-populated idempotent day may add zero
rows and remain successful. A low-volume day with one or more stored rows is
not a zero-bar target and is not classified by this V1 rule, even if Coverage
v2 later reports missing slots. Slot-level truth and no-trade authority remain
separate work.

Collection outcome and Coverage status answer different questions. Collection
`succeeded` means that this bounded operation left no original zero-bar target
unresolved; it does not mean that every expected RTH slot is present. The same
ticker-day may therefore be collection `succeeded` and Coverage v2 `partial`
after one row resolves the day-presence target but fewer than all expected RTH
slots are observed. This is an intentional dual state, not a contradiction. The
collector and Settings source row must not translate operation success into a
claim that price coverage is complete; Coverage remains the read-side owner of
that claim.

Removing this dual state is separate work. It requires per-slot collection
facts plus sufficient authority to distinguish provider omission from no-trade
intervals, halts, listing boundaries, and entitlement failures. This slice
must not infer any of those causes from low volume or an incomplete slot grid.

### LD 4 - Reconciliation uses the original target identity

Only the pre-fetch zero-bar target dates are rechecked. The writer must not
rederive a different target set after the provider call. This makes the
before/after claim falsifiable and prevents a changing clock or calendar read
from moving the acceptance set mid-run.

### LD 5 - Reconciliation happens after insertion under the write boundary

The collector inserts returned rows and then queries the same market database
for the original target identities while it still owns the write phase. The
check uses parameterized SQL and canonical ticker/interval values. Provider
fetch remains outside `market_write_lock`; this slice must not extend the lock
across network work.

### LD 6 - Batch status is derived, never independently assigned

Let `N` be `tickers_scanned` and `I` be the number of distinct tickers with a
per-ticker issue:

| Condition | Direct collector / worker status |
|---|---|
| `I == 0` | `succeeded` |
| `0 < I < N` | `partial` |
| `N > 0` and `I == N` | `failed` |
| a fatal batch exception escapes | existing exception failure boundary |

The 149-success/1-unresolved production shape is therefore `partial`. The
3,874 inserted rows remain reported; they are not discarded or mislabeled as
an all-or-nothing failure.

### LD 7 - Existing per-ticker exceptions join the same truth model

Per-ticker exception isolation remains. A bad ticker must not abort successful
siblings, but its existence must prevent `succeeded`. Existing tests that pin
batch continuation evolve to require `partial` or `failed` according to LD 6;
they are not deleted as obsolete.

### LD 8 - Unresolved meta never advances success

For an unresolved ticker, `provider_sync_meta` is updated through the error
path with `last_error="price_day_unresolved_after_fetch"`. The prior
`last_success` is preserved rather than advanced, and the current error is not
cleared. `rows_added` retains the actual number inserted for that ticker. If
the run proves a newer persisted bar frontier even while another target date
remains unresolved, `last_bar_datetime` may advance to that factual frontier;
otherwise the prior frontier is preserved.

A later run that resolves every current target may advance `last_success`, set
the actual fetched frontier, and clear the current error. Historical run rows
remain immutable.

### LD 9 - There is no global timestamp-only invariant

`last_success > last_bar_datetime` is not by itself contradictory. A weekend,
pre-session run, idempotent top-up, or already-current store can legitimately
have an operation timestamp later than its latest market bar. The protected
invariant is target-relative:

> If this run began with a zero-bar completed-day target and that target is
> still zero-bar after insertion, this run may not record ticker success.

Tests must encode that invariant directly. A broad date-comparison alert is not
part of this slice.

### LD 10 - Three-value run tables use a documented projection

No schema migration is justified for this bounded fix:

| Semantic outcome | `provider_sync_runs.status` | scheduler durable status | `job_runs.status` |
|---|---|---|---|
| `succeeded` | `succeeded` | `succeeded` | `succeeded` |
| `partial` | `failed` | `partial` | `failed` |
| `failed` | `failed` | `failed` | `failed` |

The structured result retains status, counts, and bounded ticker IDs, so the
`failed` audit projection does not erase the successful per-ticker facts. The
prices path deliberately chooses the fail-closed side of the existing
three-value split: degraded work is not stored as audit success. This is a
local decision, not a claim that the repository already has one universal
projection rule.

Normalized news currently makes the opposite audit projection, and generic
Data Sources rendering can therefore show check-plus-partial for news and
cross-plus-partial for prices. This slice records that inconsistency but does
not change normalized news, SA, provider health, global job history, or the
generic glyph. A separate bounded follow-up must first inventory history,
health, failure counters, backoff, status APIs, and UI consumers; distinguish
the existing partial/degraded shapes without assuming continuation is always
present; and only then decide whether the durable enum, audit projection,
schema, or presentation should converge.

### LD 11 - Partial is a completed process result

The prices child exits zero for `succeeded` and `partial`: it completed its
bounded work and emitted valid structured JSON. It exits nonzero for `failed`
or an exception. The scheduler must inspect the closed payload status rather
than using return code alone as semantic truth.

### LD 12 - Price partial has no continuation

This slice does not invent a manual repair or continuation. Scheduler durable
state is `partial` with `continuation=null`; Settings must not show Continue.
The next ordinary scheduled run can re-evaluate the same current window.

### LD 13 - The actual row provider remains unknown

No acceptance statement may infer Polygon success or failure from
`provider_sync_meta.provider='ibkr'`. The configured primary provider and the
row producer are different concepts in the current implementation. Full
structured adapter outcomes and row provenance remain a separately reviewed
follow-up.

### LD 14 - Existing false success is not rewritten in place

Implementation and merge perform no production data repair. On the first
post-release run, an unresolved current target writes a current error while
preserving the previous success timestamp under the existing meta history
rule. A healthy later run supersedes current health naturally. No migration
nulls or edits historical `last_success` or `job_runs` rows.

## 6. Direct Collector Contract

### 6.1 Buffered per-ticker facts

Before provider work, each ticker buffer owns its exact `zero_bar_targets`.
After fetch, the buffer owns returned rows or an exception. It does not decide
success before the write phase.

After insertion, the write phase computes:

```text
unresolved_targets = zero_bar_targets - dates_now_present_in_prices
```

The presence query uses the canonical ticker, normalized DB interval, and only
the original dates. It does not count rows, require 26 slots, inspect volume,
or call Coverage v2.

### 6.2 Result envelope

`backfill_prices_direct()` retains the existing fields and adds one semantic
status plus bounded facts:

```json
{
  "status": "partial",
  "provider": "ibkr",
  "tickers_scanned": 150,
  "succeeded_ticker_count": 149,
  "gaps_found": 150,
  "rows_added": 3874,
  "errors": {
    "LCID": "price_day_unresolved_after_fetch"
  },
  "unresolved_after_fetch_count": 1,
  "unresolved_after_fetch_tickers": ["LCID"]
}
```

The internal `errors` map remains available to existing Python callers.
Unresolved ticker IDs are sorted and deduplicated. The sanitized child boundary
exposes no more than the existing 25-ticker cap; its count remains the full
count.

### 6.3 Issue precedence

An exception for a ticker remains its per-ticker issue. Reconciliation is not
attempted for that ticker because no successful insert phase exists to verify.
An unresolved reason is assigned only to a ticker whose provider call and
insert path did not raise. One ticker therefore has one terminal issue entry,
not competing exception and unresolved labels.

### 6.4 Provider telemetry

`provider_sync_meta` is finalized once per ticker after reconciliation.
`provider_sync_runs` is finalized once after all ticker outcomes are known.
The partial summary error is a stable bounded code, not a concatenation of raw
provider diagnostics:

```text
price_collection_partial
price_collection_failed
```

Existing per-ticker diagnostic logging remains available. This slice does not
broaden raw error exposure through worker stdout or frontend copy.

## 7. Worker And Scheduler Contract

### 7.1 Sanitized worker payload

`sanitize_result()` validates and preserves the direct collector's closed
status. It includes:

- `status`;
- `provider`;
- `tickers_scanned`;
- `succeeded_ticker_count`;
- `gaps_found`;
- `rows_added`;
- `error_count` and bounded `error_tickers`;
- `unresolved_after_fetch_count`; and
- bounded `unresolved_after_fetch_tickers`.

Raw provider exception text and target dates do not enter stdout. Invalid
status or malformed negative/non-integer counts fail closed rather than being
coerced into success.

### 7.2 Scheduler projection

The scheduler's prices parser allowlists the new fields and rejects malformed
ticker arrays/counts. For a valid `partial` payload it:

1. preserves the payload under `result.collect`;
2. sets top-level and durable status to `partial`;
3. leaves continuation absent;
4. persists the job-run projection as `failed` with the stable partial code;
5. retains `rows_added`, successful count, error count, unresolved count, and
   bounded ticker IDs in the structured result; and
6. does not throw away the 149 successful ticker outcomes.

A valid `failed` payload or nonzero worker exit follows the existing failed
path. Lock-busy remains a retryable `skipped` result and does not become
partial.

### 7.3 Settings presentation

The existing Data Sources schedule row renders scheduler durable state. When a
price partial result has a positive `unresolved_after_fetch_count`, its badge
uses dedicated bilingual copy rather than the generic partial label. It shows
the full count and the bounded ticker list. It does not claim that the ticker
failed to trade, that IBKR failed, or that recovery is guaranteed.

The copy is conceptually:

```text
zh-Hant: 部分完成（抓取後仍有 1 個標的無法確認：LCID）
en: Partially completed (1 ticker remains unresolved after collection: LCID)
```

The implementation uses normal i18next plural leaves. The implementation plan
must state the exact per-locale resource delta and evolve the existing resource
inventory node in place.

## 8. Component Boundaries

### 8.1 Owners expected to change

- `src/market_data_direct.py`
- `src/prices_runtime.py`
- `src/service/data_scheduler.py`
- `tests/test_market_data_direct.py`
- `tests/test_prices_runtime.py`
- `tests/test_data_scheduler.py`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/marketDataDisplay.ts`
- focused frontend tests owning scheduler status presentation
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- resource inventory tests
- this spec, implementation plan, evidence packet, and priority map

### 8.2 Protected boundaries expected to remain unchanged

- `data_sources/ibkr_source.py`
- `data_sources/polygon_source.py`
- `src/market_coverage/**`
- Coverage v2 API route and frontend DTO/presentation
- `src/service/provider_health.py` and provider-health presentation
- SQLite schemas and migration files
- provider configuration authority
- scheduler source catalog and intervals
- IBKR Gateway locking
- Polygon fallback order and request volume
- price/calendar formatters
- root `scripts/` and its untracked retirement decision
- production databases during implementation and review

If implementation requires changing an adapter return type, Coverage v2,
schema, provider retry/fallback policy, or a production row before post-merge
approval, stop and revise this design.

## 9. Required RED-First Evidence

The implementation plan must create exact node accounting and make at least the
following behaviors mutation-sensitive.

### 9.1 Direct collector

1. One healthy ticker plus one zero-bar target that remains empty derives
   `partial`, keeps healthy rows, and lists only the unresolved ticker.
2. All scanned tickers unresolved derives `failed` without discarding their
   per-ticker facts.
3. A pre-populated/idempotent day with zero inserted rows remains `succeeded`.
4. A low-volume fixture with one stored row, no new rows, and no other issue is
   not classified as unresolved and derives `succeeded` under this V1
   day-presence rule. Its collection result makes no Coverage-completeness
   claim and may coexist with a Coverage v2 `partial` result for the same
   ticker-day.
5. A provider result that returns older-window rows but leaves the target date
   empty is unresolved; non-empty fetch output alone is not success proof.
6. A run whose only pre-fetch zero-bar target gains at least one stored row and
   has no other issue derives `succeeded`, advances meta success, and clears
   its current error.
7. An unresolved target preserves prior `last_success`, writes the stable
   reason, retains factual rows-added/frontier progress, and cannot clear the
   current error.
8. Existing per-ticker exception isolation now derives `partial` when siblings
   succeed and `failed` when every ticker has an issue.
9. `provider_sync_runs` maps semantic partial/failed to persisted failed and
   never stores partial as succeeded.
10. Provider fetch remains outside `market_write_lock`; reconciliation and
    telemetry remain inside the write phase.

Items 3, 4, and 6 are three separately named anti-false-partial nodes. They
must not be collapsed into one parametrized assertion or inferred only from a
positive unresolved case.

### 9.2 Worker and scheduler

11. Worker `succeeded`, `partial`, and `failed` payloads have the specified exit
    and sanitized field contract.
12. Malformed status/count/ticker values cannot become success.
13. Scheduler parsing preserves full counts and bounded sorted ticker IDs.
14. Price partial becomes durable `partial`, no continuation, and failed
    job-run projection with structured successful/unresolved counts.
15. A later successful price result clears current durable partial state while
    the prior failed audit row remains queryable.
16. Existing invalid-stdout, process failure, lock-busy skip, and full-success
    paths retain their current classifications.

### 9.3 Frontend

17. Both locales render the price-specific unresolved count/list instead of a
    generic success or generic retry invitation.
18. The same fixture renders no Continue control.
19. A generic non-price partial result retains existing presentation.
20. Resource parity, empty-leaf, count, scanner, typecheck, build, and mounted
    Settings tests remain green.

### 9.4 Required mutation probes

At minimum, independently prove RED for:

- deleting the post-write target query;
- treating `rows_added == 0` as unconditional success;
- replacing the day-presence recheck with an all-slots rule such as
  `stored_row_count == 26`; the one-row low-volume node must turn RED;
- advancing meta success for an unresolved ticker;
- hard-coding worker status back to `succeeded`;
- making the scheduler rely on return code while ignoring payload `partial`;
- mapping a price partial job run to persisted `succeeded`; and
- removing the frontend unresolved-count branch.

## 10. Verification And Release

### 10.1 Pre-merge

- complete tiered backend A/B collection and node-ID comparison;
- focused direct/worker/scheduler suites;
- canonical frontend A/B collection and focused scheduler-presentation tests;
- resource delta/parity and scanner twice;
- typecheck and production build;
- no-PG smoke and central/bridge tool-count gates;
- protected-boundary byte checks from section 8.2;
- SQLite fixture integrity; and
- no provider, Gateway, browser, scheduler, or production write.

The known environment-dependent backend non-green baseline remains EIR-002.
The branch must prove no new non-passing node IDs rather than adopting a dated
absolute failure count as an allowlist.

### 10.2 Post-merge production observation

No manual provider run or repair is implicit in merge. After the merged desktop
is restarted, use either the next ordinary enabled `ibkr_prices` cycle or a
separately approved manual run.

Before that run, capture read-only facts for:

- latest `collect.ibkr_prices` job;
- LCID `provider_sync_meta`;
- LCID latest stored bar;
- current 2026-07-27 Coverage v2 row; and
- database size, mtime, integrity, and FK state.

Then accept exactly one of these truthful outcomes:

1. **Resolved:** one or more valid 2026-07-27 LCID rows are written; current
   provider error clears; collector/scheduler succeeds; Coverage no longer has
   LCID as all-unknown for that day. Coverage may still report `partial` when
   fewer than all expected RTH slots are observed; that does not invalidate the
   bounded collection outcome.
2. **Still unresolved:** no LCID row is written; current provider meta receives
   `price_day_unresolved_after_fetch` without advancing success; direct worker
   and scheduler report partial with count one; audit-layer runs are failed;
   Coverage remains indeterminate and now reports a provider issue.

The observation must not assert which upstream provider caused the outcome.
Any live manual trigger, provider probe, or data repair requires explicit user
approval immediately before execution.

### 10.3 Observed release closeout

Reviewed tip `66ef3bbc` fast-forwarded to `master` on 2026-07-31. Merged
verification reproduced backend focused `168`, canonical backend collection
`4739/a72bbd36...`, frontend `96/1076`, canonical frontend collection
`de48671a...`, typecheck/build, and both scanner passes.

The merged desktop first loaded with its scheduler disabled solely to capture
read-only pre-run facts, then restarted with the unchanged saved cadence.
`collect.ibkr_prices` job `18329` started naturally at
`2026-07-31T10:21:39+00:00`; no Run control, provider probe, cadence change,
retry experiment, or repair was used. It found one target, inserted 62 LCID
rows, rechecked the original target as resolved, and finished with
`status=succeeded`, `succeeded_ticker_count=150`, and
`unresolved_after_fetch_count=0`.

LCID advanced from a latest stored bar of `2026-07-29T23:45:00+0000` to
`2026-07-30T23:45:00+0000`. Coverage v2 changed 2026-07-30 from
`149 complete / 1 unknown (LCID)` to `150 complete / 0 unknown`; 2026-07-27
remained complete. Both production SQLite databases returned
`PRAGMA integrity_check=ok` and zero foreign-key violations before and after
the natural cycle. This is the bounded local before/after fact required by
this design; it does not identify which upstream path supplied the rows or why
they were previously unavailable.

## 11. Sequencing

This contract violation is inserted before maintenance work:

1. price collection partial truth;
2. EIR-002 environment-dependent backend baseline;
3. root `scripts/` retirement decision, plan, and tranches.

The untracked `docs/design/SCRIPTS_RETIREMENT_DECISION.md` remains user-owned in
the main worktree and is not copied into or modified by this isolated slice.

Independent full-document re-review returned GREEN with zero findings at
`1a695141`; independent plan review then cleared reviewed plan tip `9d1e648a`.
Task 0 reproduced every collection and focused gate but stopped under Stop
Condition 11 when the required full-suite baseline hung reproducibly at
`tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint`. The
reviewed harness slice merged at `2edf12e1`. A later causal diagnosis merged
at `e6d4b7fa` after independently reviewed evidence selected
`V6 ambient_or_machine_state_dominates`: the tested SEC collection, route-mount
predecessor, and direct `edgar` import factors were not necessary for the
stall, while its mechanism remained unknown. The condition also changed in
both directions without a reboot. No product, dependency, SEC, import, or
additional TestClient seam was selected.

This branch is rebased onto `e6d4b7fa` with all reviewed decision-log history
preserved. Focused review cleared the tiered verification contract at
`3863b3be`, but its first runtime execution was invalidated by manual
termination delay and an added process-identity race. Section 13 replaces
manual supervision with a deterministic runner. Product edits remain
unauthorized until that runner amendment receives focused review and Task 0
produces a complete tiered baseline. Provider calls, production writes, merge,
and push remain separately unauthorized.

## 12. Tiered Verification Amendment

### 12.1 Purpose and boundary

The historical monolithic backend command remains useful diagnostic evidence,
but its intermittent portal stall is not the sole admission mechanism for this
product fix. The replacement admission protocol partitions the complete
backend collection into deterministic fresh-process tiers. This changes
execution mechanics, not test ownership or expected behavior:

- no node is excluded, renamed, marked, or converted;
- every real lifespan node remains in exactly one tier;
- partial output from a stalled process is never a pass;
- a failed assertion in a naturally completed tier remains a non-passing node;
  and
- the unresolved stall remains owned by `EIR-005`, not by a speculative
  product or test seam in this slice.

### 12.2 One immutable coverage map

The base side first produces the canonical sorted, unique backend collection.
The reviewed scratch builder counts nodes per test file and assigns whole
files to eight tiers using deterministic longest-processing-time ordering:

1. sort files by descending base node count, then ascending path;
2. assign each file to the currently lightest tier, breaking load ties by
   ascending tier number; and
3. serialize each tier's paths in ascending order.

The resulting map is immutable for the base/tip comparison. Tip-side nodes
added to an already mapped file inherit that file's tier. A new or missing
test file, duplicate node, unmapped node, changed builder hash, or changed map
hash is a stop condition requiring review.

Before any runtime result is admitted, collection-only runs for all eight
tiers must prove:

```text
sorted union(tier node IDs) == canonical node IDs
sum(tier node counts) == canonical node count
sum(tier node counts) == count(unique tier node IDs)
```

This proof is performed independently on base and tip. It is the mechanical
answer to whether tiering silently dropped or duplicated coverage.

### 12.3 Runtime outcomes and banking

Each tier runs sequentially in its own fresh Python process from the same
isolated worktree protocol. Each attempt starts from empty ignored worktree
data and unique temporary dependency paths; generated data is archived before
the next attempt. The subprocess environment is rebuilt from an explicit
allowlist: runtime paths, locale/timezone, scheduler disablement, isolated
ArkScope stores/locks, and the SHA-pinned reporter interface. Ambient provider
credentials, database overrides, Python paths, and user configuration are not
inherited. No tiers run concurrently. Within a tier, sorted file paths preserve
their relative order. A SHA-pinned scratch pytest reporter captures exact
`report.nodeid` values; transcript token parsing is not an authority because
valid node IDs contain spaces. The reporter must add no collected node, and
its collected and seen sets must both equal the tier's collection manifest. A
tier has one of four closed outcomes:

| Outcome | Meaning | Admission |
|---|---|---|
| `complete_pass` | pytest exits naturally with code 0, a terminal summary, and zero reporter non-passing nodes | complete |
| `complete_nonpassing` | pytest exits naturally with code 1, a terminal summary, and at least one reporter non-passing node, including test setup/teardown errors | complete; every failed/error node enters the baseline |
| `unresolved_stall` | the current node makes no progress through the reviewed dump/termination bound | incomplete; no partial result is admitted |
| `invalid` | collection/runner/command/isolation failure, pytest exit outside 0/1, missing terminal summary, or exit/non-passing inconsistency | incomplete and stop |

All eight initial attempts run even if one tier stalls. An unresolved tier
receives exactly one deferred retry after the remaining initial attempts.
Completed tier artifacts may be banked across that retry window only while the
side, Git identity, canonical collection hash, builder/map hashes, interpreter
and dependency fingerprint, command, and isolation boundary remain unchanged.
Any change invalidates the bank.

The base baseline is complete only when all eight tiers have a complete
outcome. If any tier remains unresolved or invalid, Stop Condition 11 applies
at that tier boundary: Task 0 remains incomplete and product RED remains
unauthorized, while already completed tiers do not need to be rerun under an
unchanged identity.

### 12.4 Base/tip comparability

Base and tip must use the same protocol version, immutable file map, tier
commands, outcome classifier, isolation rules, retry limit, and normalization
recipe. The final A/B compares the union of normalized non-passing node IDs
from eight complete base tiers with the corresponding union from eight
complete tip tiers.

Tiered output may be compared only with tiered output. Historical monolithic
failure totals or partial transcripts cannot serve as either side. A bounded,
instrumented monolithic attempt may still be retained as diagnostic evidence,
but it cannot replace, override, or invalidate a complete tiered result.

### 12.5 Honest limitation

Fresh-process tiers reset process-global, module, fixture, and teardown state
between groups of files. A historical monolithic run does not. The two
execution contexts can expose different failures and are not directly
comparable.

The protocol therefore proves the complete test collection under the reviewed
tiered context; it does not claim to reproduce every order-dependent property
of a single 4,722-node process. Real lifespan tests remain present, and the
separate `EIR-005` observer owns the unresolved monolithic machine-state
behavior. This limitation must appear in every base/tip evidence summary.

## 13. Deterministic Tier Runner Amendment

### 13.1 Reason and scope

The tier contract is sound, but its first execution did not follow its own
control protocol:

- T0 and T1 emitted their 120-second faulthandler dumps, but manual
  orchestration did not enforce the 150-second no-progress boundary;
- an operator-added immediate PID/PGID/SID assertion sampled T2 before
  `setsid` completed; and
- all three attempts were therefore `invalid`, with no admitted runtime node.

This amendment changes only how the reviewed tier protocol is executed. It
does not change the eight-tier map, collection identity, final reporter,
environment allowlist, outcome table, banking tuple, retry count, node
accounting, product code, test code, providers, Gateway, or production data.
The invalid `/tmp/price-truth-tier-v1` and
`/tmp/price-truth-tier-v2` roots remain frozen evidence and must not be
reused. The next protocol identity is `price-truth-tier-v3`, and its
implementation must use a fresh `/tmp/price-truth-tier-v3` root.

The replacement is one standard-library, SHA-pinned Python module. The same
file has two roles:

1. the parent-side controller owns launch, progress deadlines, signal
   delivery, artifact persistence, classification, banking, and side-level
   sequencing; and
2. when loaded by pytest as a plugin, it emits structured test start/finish
   events over one inherited pipe.

No operator may add a wrapper assertion, signal, timeout, retry, or alternate
classification around this runner. An operator may start the reviewed command
and observe it; all control decisions remain inside the pinned process.

Two smaller-looking alternatives are rejected. A fixed whole-tier timeout
either guesses too low and kills a healthy slow tier or guesses too high and
wastes an unbounded operational window. Parsing verbose transcript lines
would reintroduce the exact ambiguity removed by the final reporter; the
canonical collection already contains 11 node IDs with spaces.

The T0/T1 dumps add two non-lifespan event-loop-stall shapes to `EIR-005`.
They remain referenced through evidence Section 8.4. This price branch does
not edit the EIR register; the later observer spec owns that transfer.

Focused review later cleared the exact deterministic-v2 runner at
`00d35376`. Its Task 0 run bounded three stalls correctly, then stopped at T3:
all 590 expected nodes produced 1,180 balanced progress events, the reporter
recorded exact collected/seen sets with zero non-passing nodes and exit status
0, and the terminal summary was complete. The progress pipe nevertheless
reached EOF while `Popen.poll()` still returned `None`; the reviewed v2 rule
therefore injected `SIGINT`, after which the leader returned 0 and the group
disappeared about 10 milliseconds later. That signal makes T3 permanently
invalid and does not permit retroactive admission. It does establish that an
immediate EOF/poll comparison conflates a complete final-exit handoff with
malformed early EOF. Evidence Section 8.7 pins the complete blocker packet;
the v3 transport handshake below resolves only that classification boundary.

### 13.2 Pinned-copy preflight

The implementation plan must provide the runner as exact appendix source,
copy it into a fresh artifact root, and record its SHA-256 in immutable
`preflight.json`. Before any subprocess launch, the runner must:

- prove `Path(__file__).resolve()` is the copied path recorded by preflight;
- hash itself, the unchanged final reporter, builder, tier map, canonical
  manifests, interpreter/dependency fingerprint, and any reviewed probe
  fixture;
- compare every value with `preflight.json`; and
- refuse to run if a file is missing, changed, relocated, or inconsistent.

This follows the diagnosis-controller pattern. It protects against accidental
source drift; it is not presented as an adversarial code-signing boundary.
An incomplete attempt directory or non-atomic prior record is also `invalid`
and prevents further launch.

### 13.3 Stable process-group ownership

The controller launches pytest directly with:

```text
subprocess.Popen(..., start_new_session=True, pass_fds=(progress_write_fd,))
```

`Popen` returns only after child setup has passed the fork/exec error channel,
so the controller receives the real child PID after `setsid`. It then records
PID, PGID, and SID and requires:

```text
PID == PGID == SID
```

before admitting the attempt. This check exists only inside the runner. A
mismatch is `invalid`; it must never cause the controller to guess or signal
an unverified process group. The controller terminates only the directly owned
child in that exceptional cleanup path, records whether cleanup completed,
and refuses every later tier.

The controller and child remain in the same PID namespace. Operator-side PID
translation, process-name selection, and external `kill` commands are
forbidden.

### 13.4 Structured progress channel

The controller adds one runner-internal
`PRICE_TRUTH_PROGRESS_FD=<write-fd>` variable after constructing the unchanged
application environment allowlist, and passes only that descriptor through
`pass_fds`. It is never inherited from the operator's ambient environment and
is not an application configuration seam. When pytest loads the runner file
as a plugin:

- a missing, non-integer, closed, or non-writable
  `PRICE_TRUTH_PROGRESS_FD` raises immediately;
- the descriptor is marked non-inheritable before tests can spawn children;
- `pytest_runtest_logstart(nodeid, location)` and
  `pytest_runtest_logfinish(nodeid, location)` each emit exactly one JSON
  object per line;
- every event contains schema version, sequence number, event name, exact
  `nodeid`, and child `time.monotonic_ns()`; and
- each newline-terminated JSON event is encoded and sent in one `os.write`
  no larger than the descriptor's `PIPE_BUF`.

There is no buffered text wrapper and no delayed flush. A malformed,
oversized, duplicate-sequence, out-of-order, or unexpected event makes the
attempt `invalid`.

The controller drains the pipe continuously. For each valid event it appends
one canonical line to `progress.jsonl`, adding runner receive
`time.monotonic_ns()` and receive wall time. The write is flushed before the
deadline state changes. Child monotonic time is audit evidence; the runner
receive timestamp owns the deadline so control does not depend on comparing
two process-local observations.

The progress stream is control-plane evidence only. It must never contribute
to collection totals, seen-node totals, non-passing sets, or A/B comparison.
The unchanged final reporter remains the sole node-admission authority, and
its collected/seen sets must still compare byte-for-byte with the tier
manifest.

### 13.5 Three no-progress phases

Runtime bounds remain fixed at:

```text
faulthandler per-item dump: 120 seconds
no-progress deadline:       150 seconds
SIGINT grace:                10 seconds
```

Transport shutdown adds two separately named bounds:

```text
EOF_LEADER_HANDSHAKE_SECONDS = 1
PROCESS_GROUP_DRAIN_SECONDS  = 1
```

Both constants are exactly one second in runtime and probe mode. They are
independent budgets: time consumed waiting for the pytest leader does not
reduce the complete process-group drain budget. Runtime and probe mode accept
no command-line override for any of these values.

The controller uses `time.monotonic_ns()` and has three explicit phases:

1. **Pre-first-node.** The 150-second deadline starts immediately before
   `Popen`. Collection normally consumes about 20-30 seconds, but it does not
   borrow time from the first test: receipt of the first log-start event
   resets the full 150-second window.
2. **Active node.** Every valid log-start event resets the full 150-second
   deadline. The matching log-finish event proves that item setup/call/teardown
   completed and resets the deadline once more. Arbitrary transcript output,
   logs, faulthandler text, and file mtime changes do not reset it.
3. **Post-last-progress.** After a log-finish event, the runner is in this
   phase until the next log-start event or process exit. For the final item,
   that full 150-second window covers session finish and final process
   shutdown. There is no separate unbounded teardown grace.

Pytest's configured faulthandler timer is per item. A collection or final
session-finish hang may therefore cross the 150-second boundary without a
120-second dump. This is expected input to the closed classification below,
not permission to wait longer.

The no-progress machine ends when the runner first observes a transport
terminal fact: clean pipe EOF or natural leader exit. From that observation
onward, the 150-second deadline is cancelled and cannot compete with or
override the two transport-handshake bounds. The runner receive-side
monotonic timestamp of each stage transition owns its corresponding deadline.

EOF is eligible for the handshake only when the pipe buffer is empty, no node
is active, and the valid progress count is exactly twice the expected node
count. Partial buffered data, unbalanced progress, incomplete progress, or a
later event after EOF is immediately `invalid`; no transport grace may turn
any of those shapes into a natural result.

### 13.6 Deadline, dump, and signal classification

At a no-progress deadline breach, the runner records the exact phase, last
valid progress sequence/node, monotonic timestamps, transcript size/hash
snapshot, and whether the exact faulthandler dump marker is present. Reading
that marker is permitted only to distinguish dump presence. Transcript text
never supplies node IDs or pass/fail accounting.

Dump presence is scoped to the current progress window. At launch and on every
valid start/finish event, the controller records the current transcript byte
offset. At breach it searches only bytes written after that offset for the
exact `Timeout (0:02:00)!` marker. A dump from an earlier item cannot classify
a later collection, item, session-finish, or shutdown breach.

The controller then:

1. revalidates that the live PID owns an equal PGID and SID;
2. sends `SIGINT` to that exact process group;
3. waits exactly 10 monotonic seconds;
4. sends `SIGKILL` to the same group only if it remains alive; and
5. waits for and records final process termination.

The result is closed:

| Breach evidence | Outcome |
|---|---|
| 150-second breach and transcript contains the 120-second per-item dump | `unresolved_stall` |
| 150-second breach without that dump, including collection or final-teardown hang | `invalid` |
| malformed/missing progress channel, identity failure, controller error, unsafe cleanup, or artifact boundary failure | `invalid` |

Whether `SIGINT` alone terminates pytest or `SIGKILL` is required does not
change `unresolved_stall`; it is retained as signal-path evidence. No forced
termination can become `complete_pass` or `complete_nonpassing`.

Natural transport shutdown is a symmetric two-stage handshake:

1. **EOF/leader convergence.** The first observed side starts
   `EOF_LEADER_HANDSHAKE_SECONDS`.
   - If clean, fully complete EOF arrives first, the runner waits up to the
     complete one-second bound for `Popen.poll()` to observe leader exit.
   - If leader exit arrives first, the runner waits up to the same complete
     one-second bound for clean EOF.
   - Success records `leader_exit_after_eof` or
     `pipe_eof_after_leader_exit`, including the bound and elapsed monotonic
     time. Timeout remains `invalid` as
     `pipe_eof_while_child_running` or
     `child_exit_without_timely_pipe_eof`.
2. **Process-group drain.** After both EOF and leader exit are observed, the
   runner records `process_group_drain_started` and waits a separate complete
   `PROCESS_GROUP_DRAIN_SECONDS` for the originally verified PGID to
   disappear. This stage is mandatory in both observation orders. Natural
   disappearance records `group_drained`; a still-live group after the
   complete bound remains `invalid` as
   `pipe_eof_with_live_process_group`.

The phrase "child/group is still running" in this contract means that the
corresponding complete handshake bound expired while the verified process or
process group remained observable. A single immediate `poll()` or
`killpg(..., 0)` observation is not sufficient.

Successful transport convergence injects no signal. Only after both stages
succeed may the runner call the unchanged natural-result validator. Exit 0/1
is admitted only after the unchanged terminal summary, final reporter,
collected/seen/non-passing manifest comparisons, progress-count check, data
boundary, and Section 12.3 outcome checks all pass. The handshake resolves
only transport ordering; it cannot make incomplete or malformed test evidence
admissible.

### 13.7 Attempt and side records

Every attempt has a unique directory and an atomically replaced
`record.json`. At minimum it records:

- protocol version, side, tier, attempt, Git and all preflight identities;
- exact command and allowlisted environment names;
- PID/PGID/SID and wall/monotonic launch/end values;
- fixed dump/deadline/signal bounds and both named transport bounds;
- `progress.jsonl` path, SHA-256, event count, and last valid event;
- transcript, reporter, terminal-summary, and data-boundary validation;
- deadline phase and dump-marker result;
- ordered EOF/leader/group-drain and signal events with receive-side
  monotonic timestamps, wall time, elapsed time, bound, and process state;
- natural or forced return status; and
- one closed Section 12.3 outcome with its mechanical reasons.

The attempt directory is created before launch and is never reused. Runner
interruption, missing final record, leftover temporary record, or an artifact
that cannot be reconstructed is `invalid` on the next invocation.

The side-level controller, not the operator, runs tiers in order. An
`unresolved_stall` permits the remaining initial tiers and exactly one
deferred retry under the unchanged Section 12.3 rule. The first `invalid`
atomically closes the side as incomplete and the runner refuses to launch
every subsequent initial tier, retry, or diagnostic monolithic run.

Completed-tier banking retains the exact existing identity tuple. Protocol
identity becomes `price-truth-tier-v3`; the pinned runner and progress
protocol remain represented by the already-required command and protocol
identity. No v2 record may be imported, selected, or treated as a v3 banked
result. This amendment does not weaken or replace any banking field.

### 13.8 Mandatory pre-runtime probes

The implementation plan must pin scratch fixtures and execute five probes
before Task 0 runtime:

1. **Fast natural pass:** one test emits a progress event, exits 0, closes the
   pipe, and satisfies final-reporter admission without any signal.
2. **EOF/leader/group handshake:** one passing scratch test is accompanied by
   a `pytest_sessionfinish` hook that starts a short-lived same-PGID
   descendant without inheriting the progress descriptor, closes the progress
   descriptor, and then sleeps for 0.5 seconds. The descendant must outlive
   the pytest leader but disappear within the separate group-drain bound. The
   result must be `complete_pass`, inject no signal, and record
   `leader_exit_after_eof`, `process_group_drain_started`, and
   `group_drained` in order. Final reporter and manifest admission must also
   pass.
3. **SIGINT termination:** one sleeping test crosses a short probe deadline,
   emits the probe faulthandler dump, receives process-group `SIGINT`, and
   exits within the probe grace without `SIGKILL`.
4. **SIGKILL fallback:** one sleeping test deliberately ignores `SIGINT`,
   crosses the same probe deadline, and requires process-group `SIGKILL`
   after the complete grace.
5. **Collection identity:** collect-only execution with and without the
   progress plugin yields the same exact one-node collection and SHA-256.

Probe mode uses separately pinned short constants so review does not spend
160 seconds per kill-path fixture; the two transport constants remain exactly
one second in both modes. Runtime mode cannot select probe dump/deadline/signal
constants, and every record states its mode and effective bounds. Probe
source, runner, reporter, commands, raw artifacts, records, and manifests all
receive SHA-256 entries in evidence.

The exact-source plan must replace the v2 appendix with the complete v3
runner, pin every new fixture SHA-256, update the runner/preflight identity
tables, add an `eof_exit_handshake` check to the closed probe-summary object,
and predict the new deterministic probe-summary SHA-256. Those values belong
to the plan after extraction and execution; this design does not invent them.

Each mutation must be mechanically visible:

- remove or delay a progress event and the corresponding deadline probe
  changes outcome;
- omit the dump marker and the hang class becomes `invalid`;
- make the child ignore `SIGINT` and the fallback record must show
  `SIGKILL`;
- alter the runner after preflight and no child may launch;
- omit/garble the progress descriptor and plugin startup must fail closed;
  and
- let an `invalid` record exist and a later-tier launch must be refused;
- **M7a:** set only `EOF_LEADER_HANDSHAKE_SECONDS` to zero; the handshake
  probe must become `invalid` in stage one and must not reach
  `group_drained`; and
- **M7b:** set only `PROCESS_GROUP_DRAIN_SECONDS` to zero; the same probe must
  complete stage one, enter `process_group_drain_started`, and become
  `invalid` in stage two.

M7a and M7b use separate fresh roots and exact diffs. A mutation that zeros
both constants is insufficient because a stage-one failure cannot prove that
stage two independently fails closed.

### 13.9 Protected invariants and stop conditions

This amendment is invalid if implementation or its plan:

- parses transcript node IDs or derives any node accounting from progress;
- changes the final reporter or its collected/seen/non-passing authority;
- changes tier membership, count, ordering, retries, banking semantics,
  outcome names, environment allowlist, or base/tip comparison;
- adds a repository test node merely to test scratch control code;
- permits runtime deadline overrides or operator-added wrappers;
- launches a later tier after `invalid`;
- treats a no-dump breach as `unresolved_stall`;
- shares one elapsed budget between the two transport stages;
- admits an EOF handshake with partial, active, or incomplete progress;
- skips process-group drain after either EOF/leader observation order;
- reuses `/tmp/price-truth-tier-v1`,
  `/tmp/price-truth-tier-v2`, or any prior attempt directory;
- touches product/test/provider/Gateway/production-data paths; or
- starts Task 0 or product RED before separate plan review clears the exact
  runner source, probes, hashes, and commands.

Focused review cleared this amendment at `6c89d4a1` with zero findings. The
exact-source implementation plan is now the next independent gate. It must use
protocol `price-truth-tier-v3`, include the exact runner source and
reproducible probe/mutation recipes, and update every identity and predicted
hash named above. This design alone authorizes no runtime attempt.
