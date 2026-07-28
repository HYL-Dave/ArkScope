# ArkScope Price Collection Partial-Truth Design

> **Status: DRAFT - FINAL INDEPENDENT RE-REVIEW REQUIRED**
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

- canonical backend A/B collection and node-ID comparison;
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

## 11. Sequencing

This contract violation is inserted before maintenance work:

1. price collection partial truth;
2. EIR-002 environment-dependent backend baseline;
3. root `scripts/` retirement decision, plan, and tranches.

The untracked `docs/design/SCRIPTS_RETIREMENT_DECISION.md` remains user-owned in
the main worktree and is not copied into or modified by this isolated slice.

Independent full-document review is the only next gate. Product edits,
implementation planning, provider calls, production writes, merge, and push
remain unauthorized.
