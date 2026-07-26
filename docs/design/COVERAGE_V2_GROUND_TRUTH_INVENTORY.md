# Coverage v2 Ground-Truth Inventory

> **Status:** ADOPTED AND LIVE - 2026-07-26
> **Observed:** 2026-07-25
> **Code base:** `f019f9faf31c25ff8d71f29d97fe5945bf992d94`
> **Purpose:** Evidence-only pre-spec inventory. This document does not select a
> runtime calendar, authorize product changes, or turn observed bar counts into
> acceptance constants.
> **Successor:** The reviewed decisions are written at
> [`2026-07-26-coverage-v2-session-truth-design.md`](../superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md),
> now LIVE through merged product tip `3f0fb18f`.

## 1. Executive Finding

Coverage v2 is not primarily a choice between a hard-coded `26` and `14` bars.
The current system combines three different questions that require separate
owners:

1. **Session schedule:** was the US equity market open, and what were that
   session's open and close instants?
2. **Coverage session:** does ArkScope judge regular trading hours (RTH), all
   available hours, or a provider-specific interval?
3. **Per-symbol observations:** which expected time slots actually produced a
   stored aggregate for a ticker?

The production `prices` table contains both RTH-shaped rows and
extended-hours-shaped rows that the current IBKR and Massive paths can produce,
while the table stores no provider or session provenance. Exact row origin is
therefore unobservable. On 2026-07-24, for example, 148 stored tickers had 26
rows, while two had 58 and 63 rows spanning 08:00-23:45 UTC. The current per-day
maximum therefore classified 149 tickers as `partial_tickers` even though the
day-level status remained `complete_like`.

Replacing the holiday helper without first fixing that session mismatch would
leave the central false comparison intact.

The evidence supports one **working recommendation for review**, not a locked
decision:

- use one offline, pinned US-equity session-calendar owner for runtime schedule
  facts;
- validate that owner against official NYSE dates as golden fixtures;
- treat IBKR's per-contract historical schedule as optional corroboration, not
  a runtime dependency for a read-only health surface;
- define coverage against RTH and filter stored timestamps through the selected
  session before counting; and
- derive expected slots from `[session_open, session_close)` divided by the
  requested interval instead of storing `26` or `14` as calendar constants.

`exchange_calendars`/XNYS is the strongest currently grounded offline candidate.
It is not an exchange authority, so package pinning, official-date fixtures,
and an update policy remain required decisions. No candidate is adopted by
this inventory.

## 2. Scope And Method

### 2.1 In scope

- current calendar, completeness, planner, API, and UI ownership;
- the actual semantics of IBKR and Massive intraday retrieval;
- production `market_data.db` schema and dated read-only distributions;
- runtime calendar candidates and their authority/failure properties;
- decisions that must be made before a Coverage v2 design can be written; and
- reproducible evidence for independent review.

### 2.2 Out of scope

- implementation, dependency changes, schema changes, or migrations;
- a new coverage state machine or UI copy;
- provider calls against the live IBKR Gateway or Massive account;
- changing scheduler/backfill behavior;
- declaring every absent aggregate a provider failure; and
- treating any production count, ticker, or date distribution as a permanent
  acceptance constant.

### 2.3 Evidence discipline

- All production SQLite inspection used URI `mode=ro`.
- The `market_data.db` size and nanosecond mtime were identical before and
  after the full integrity/schema/distribution probe:
  `(3293126656, 1784993444752306713)`.
- That tuple is the probe's dated before/after witness, not a permanent file
  fingerprint; later application activity may legitimately advance it.
- `PRAGMA integrity_check` returned `ok`.
- The active universe was resolved through the production profile and SA
  databases in read-only mode and contained 150 symbols at observation time.
- `exchange_calendars==4.13.2` was installed only in a temporary directory for
  the candidate probe; the temporary directory was removed automatically.
- No product file, dependency file, production database, provider setting, or
  scheduler state was changed.

## 3. Current Ownership And Semantics

### 3.1 Code owners

| Concern | Current owner | Current contract |
| --- | --- | --- |
| Trading day | `src/tools/data_coverage_tools.py:27-87` | Hand-built weekend plus ten recurring US holiday rules. No early closes or extraordinary closures. |
| Session completion | `src/market_data_direct.py:67-73`, `:226-232` | Any earlier date is complete; current date becomes complete only after fixed 16:30 ET. |
| Zero-day gaps | `src/market_data_direct.py:260-309` | One stored row marks a completed trading day present. |
| Daily diagnostic | `src/market_data_direct.py:319-457` | Counts all stored rows by UTC date; compares each ticker with the day's maximum; uses a fixed `<20` thin threshold and two `0.9` ratios. |
| Scheduler plan | `src/scheduler_planner.py:1-84` | Schedules zero-bar complete-day gaps only. Partial/thin days are explicitly excluded. |
| API | `src/api/routes/market_data.py:154-177` | Pure-read `/market-data/trading-days`; resolves active universe and local market DB. |
| Frontend presenter | `apps/arkscope-web/src/marketDataDisplay.ts:85-125` | Renders backend `coverage_status`; does not rederive completeness. |
| Settings surface | `apps/arkscope-web/src/settings/DataStorageSection.tsx:155-343` | Shows daily counts, missing/partial tickers, and provider errors. |

The current focused baseline is green:

```text
pytest -q tests/test_trading_day_coverage.py tests/test_market_data_direct.py
82 passed in 1.88s
```

These tests correctly pin the existing contract. They are not evidence that
the contract can identify exchange-specific session length.

### 3.2 Hand-built calendar limits reproduced locally

The current helper returns `regular_trading_day` for all of these dates:

| Date | Ground truth | Current result |
| --- | --- | --- |
| 2025-01-09 | NYSE closed for the National Day of Mourning for President Jimmy Carter | trading day |
| 2025-07-03 | 13:00 ET early close | regular trading day |
| 2025-11-28 | 13:00 ET early close | regular trading day |
| 2025-12-24 | 13:00 ET early close | regular trading day |
| 2026-11-27 | 13:00 ET early close | regular trading day |
| 2026-12-24 | 13:00 ET early close | regular trading day |

At 13:31 ET on the tested early-close dates, `_is_session_complete` still
returned `False`; it waits for the fixed 16:30 ET threshold. The source comment
acknowledges this as conservative behavior, but Coverage v2 needs the actual
session close to judge an expected interval grid.

Primary references:

- [NYSE holiday and trading-hours calendar](https://www.nyse.com/markets/hours-calendars)
- [NYSE 2025 yearly trading calendar](https://www.nyse.com/publicdocs/ICE_NYSE_2025_Yearly_Trading_Calendar.pdf)
- [NYSE regulatory memo for the 2025-01-09 closure](https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf)

### 3.3 Provider and storage semantics

#### IBKR primary path

`IBKRDataSource.fetch_intraday_prices` and `fetch_historical_intraday` default
`include_extended=False` and call `reqHistoricalData(... useRTH=True)`
(`data_sources/ibkr_source.py:804-880`, `:917-950`). This is an RTH retrieval
contract.

The same adapter can read `timeZoneId`, `tradingHours`, and `liquidHours` from
contract details (`data_sources/ibkr_source.py:982-1007`), but Coverage does
not consume them. The installed `ib_insync 0.9.86` also exposes
`reqHistoricalSchedule`; ArkScope does not call it.

IBKR's current TWS API documentation states that `useRTH` selects regular-only
versus all available hours, and that `whatToShow="SCHEDULE"` returns session
start, end, timezone, and reference date through `historicalSchedule`.
It also requires connectivity to TWS or IB Gateway. See the
[IBKR TWS API historical-data documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/).

#### Massive fallback path

When an IBKR request returns no rows, `_fetch_rows_for_gaps` calls Massive once
per day (`src/market_data_direct.py:634-662`). The Massive adapter passes a
date-only `/v2/aggs/.../{date}/{date}` range and no intraday time bounds
(`data_sources/polygon_source.py:390-431`).

Massive documents that stock aggregates cover pre-market, regular, and
after-hours sessions. Its aggregate endpoint has no RTH-only switch; callers
must supply timestamps to restrict the result to 09:30-16:00 ET. It also states
that an interval with no eligible trades produces no bar:

- [Massive extended-hours behavior](https://massive.com/knowledge-base/article/does-massive-offer-pre-market-and-after-hours-data)
- [Massive stock custom bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars)

Massive's holiday endpoint reports upcoming holidays; its own documentation
says historical holiday support is planned rather than available. It cannot
own historical runtime schedule truth:
[Massive market holiday/status scope](https://massive.com/knowledge-base/article/does-massive-have-a-market-holiday-or-status-page).

#### Local schema

The production `prices` primary key and value columns are:

```text
(ticker, datetime, interval, open, high, low, close, volume)
```

There is no `provider`, `exchange`, `session`, or retrieval-run column.
`provider_sync_runs` and `provider_sync_meta` identify run/frontier providers,
but cannot attribute an individual historical `prices` row. The active-universe
boundary is likewise `list[str]` (`src/universe_scope.py:4-5`); it deliberately
does not return exchange identity.

Therefore neither storage nor the active-universe contract currently supports
per-row or per-symbol exchange-session reconstruction. The diagnostic's
`substr(datetime, 1, 10)` grouping adds a second ambiguity: during Eastern
Standard Time, extended-hours bars from 19:00-20:00 ET fall on the next UTC
date. A UTC-day bucket can therefore contain bars from two different exchange
session dates. A future session owner must assign rows by schedule instants,
not by a UTC date prefix.

## 4. Dated Production Observations

### 4.1 Database snapshot

Observed read-only on 2026-07-25:

| Fact | Observation |
| --- | --- |
| `prices` rows | 2,386,679 |
| Stored symbols | 151 |
| Active-universe symbols | 150 |
| Intervals | `15min` only |
| Earliest timestamp | `2024-01-02T14:30:00+0000` |
| Latest timestamp | `2026-07-24T23:45:00+0000` |
| Current provider errors | 0 |

These are observations, not gates.

### 4.2 Session-length witnesses

The modal row count on known early-close days is consistently 14:

| Date | Stored distribution |
| --- | --- |
| 2024-07-03 | 144 tickers x 14 bars |
| 2024-11-29 | 145 x 14; one x 5 |
| 2024-12-24 | 145 x 14; one x 18 |
| 2025-07-03 | 148 x 14; one x 12 |
| 2025-11-28 | 149 x 14 |
| 2025-12-24 | 149 x 14 |

A 09:30-13:00 ET half-open 15-minute grid contains 14 slots. A
09:30-16:00 ET grid contains 26. Those values are consequences of session
instants and interval size; they must not become independent calendar facts.

### 4.3 Mixed-session witnesses

| Date | Stored distribution | Current diagnostic consequence |
| --- | --- | --- |
| 2026-07-02 | 147 x 26; GOOG x 64 | day max 64; 147 RTH-shaped tickers reported partial |
| 2026-07-10 | 148 x 26 | day max 26; no partial ticker among stored symbols |
| 2026-07-14 | 149 x 26; LCID x 58 | day max 58; 149 tickers reported partial |
| 2026-07-24 | 148 x 26; LCID x 58; QBTS x 63 | day max 63; 149 tickers reported partial |

On 2026-07-24, AAPL and GOOG span 13:30-19:45 UTC (26 starts), while LCID and
QBTS span 08:00-23:45 UTC. QBTS stores 63 rows across that 64-slot span, so even
the ticker setting that day's maximum is missing one interval relative to its
own observed time range. The separate 2026-07-02 GOOG witness stores all 64
rows from 08:00 through 23:45 UTC. Both shapes are consistent with Massive's
documented 04:00-20:00 ET coverage and its rule that an interval with no
eligible trade produces no aggregate.

The current status output illustrates the contradiction:

```text
2026-07-24 complete_like max=63 full=1 well_covered=150 partial=149 missing=0
2026-07-14 complete_like max=58 full=1 well_covered=150 partial=149 missing=0
2026-07-10 complete_like max=26 full=148 well_covered=148 partial=0 missing=2
2026-07-02 complete_like max=64 full=1 well_covered=148 partial=147 missing=2
```

For these recent outlier witnesses, `coverage_status` happens to remain
`complete_like`, but the displayed `full`/`partial` facts no longer mean one
coherent thing. Known early-close sessions remain false-`thin` under the same
current logic.

### 4.4 Known truncation witnesses

The existing fixed threshold does catch two important failure shapes:

```text
2026-06-26: 147 tickers x 3 bars; one x 19 -> thin
2026-06-25: 147 tickers x 5 bars; one x 26 -> partial
```

This is valuable behavior and must not be lost. It does not make `20` an
exchange-derived expected count. The source itself calls the threshold a blunt
rule and notes its early-close false positive (`src/market_data_direct.py:319-324`).

## 5. The Required Three-Layer Model

### 5.1 Layer A: session schedule

Required facts for each market date:

- trading session or closed;
- session open and close instants with timezone;
- regular versus special/early close; and
- enough history to cover the local database and planned lookback.

This layer can derive expected interval slots. For a no-break half-open
session:

```text
expected_slots = (session_close - session_open) / interval
```

It does not say that every ticker must emit every slot.

### 5.2 Layer B: ArkScope coverage-session policy

ArkScope must choose what `15min coverage` means. The current primary path is
RTH, while the fallback is all-session. A day cannot be compared until the
policy is explicit and both stored timestamps and new provider results are
projected into it.

The least disruptive shape is an RTH coverage policy with read-time filtering
through `[open, close)`. It can judge existing mixed history without a schema
migration. Whether future Massive retrieval should also be time-bounded is a
separate but closely coupled implementation decision.

### 5.3 Layer C: per-symbol observations

An expected slot without a stored bar can mean multiple things:

- local ingestion missed a provider-available bar;
- no eligible trade produced an aggregate;
- the symbol was not yet listed or was halted;
- the provider lacked entitlement/history; or
- the symbol/session mapping was wrong.

Calendar truth can prove the slot existed. It cannot by itself prove that a
bar should exist for every symbol. Coverage v2 must not relabel all missing
slots as provider failures without an additional evidence source.

## 6. Authority Candidate Evaluation

### 6.1 Candidate table

| Candidate | Strengths | Limits | Inventory disposition |
| --- | --- | --- | --- |
| Pinned `exchange_calendars` XNYS | Offline and deterministic; exposes sessions/open/close/minutes; supports early closes and special closures; Python `>=3.10`; direct XNYS calendar. | User-maintained, not NYSE authority; package updates are required for corrections; XNYS is a US-equity proxy because ArkScope lacks exchange metadata. | Strongest runtime candidate; requires official golden fixtures and an update policy. Not yet selected. |
| Pinned `pandas_market_calendars` NYSE | Offline; explicitly supports holiday, late-open, and early-close schedules; Python `>=3.9`; already speaks pandas. | Mirrors `exchange_calendars` calendars in part, adding another abstraction; also package-maintained rather than live exchange truth. | Viable alternative, but no current ArkScope need justifies the extra wrapper. Not selected. |
| IBKR `SCHEDULE` / contract `LiquidHours` | Per-contract schedule from the primary market-data provider; captures contract timezone and session. | Requires TWS/Gateway, contract qualification, provider availability, and likely caching; cannot be the only dependency for a pure-read health endpoint. | Useful corroboration/live canary or a more complex cached-authority option. Not recommended as sole V1 authority. |
| Official NYSE calendars/memos | Primary human authority for core hours, holidays, early closes, and exceptional closures. | No reviewed historical machine API in the current system; scraping a web/PDF surface would add a brittle runtime dependency. | Golden-fixture and review authority, not runtime API. |
| Massive market-status/holiday endpoints | Provider-aligned current/upcoming state. | Historical holidays are not currently available; raw aggregates include extended sessions and missing no-trade bars. | Reject as sole historical authority. Retain as data-provider documentation/corroboration. |
| Per-day observed maximum or modal count | No new dependency; reflects actual stored data. | Circular; one extended-hours outlier changes the maximum, while uniform truncation can change the mode. Cannot know holidays or early closes independently. | Reject as authority. Retain only as anomaly evidence. |
| Current `_us_market_holidays` rules | Local, small, deterministic. | Misses early closes and extraordinary closures; fixed session completion; requires ArkScope to maintain exchange policy manually. | Retire as Coverage v2 authority if a calendar owner is adopted. |

References:

- [`exchange_calendars` project and XNYS API](https://github.com/gerrymanoim/exchange_calendars)
- [`exchange_calendars` 4.13.2 metadata](https://pypi.org/project/exchange-calendars/)
- [`pandas_market_calendars` schedule and update model](https://github.com/rsheftel/pandas_market_calendars)

Both open-source projects explicitly describe package-shipped, contributor-
maintained calendars. That is operationally useful but weaker than an official
exchange feed; the distinction must stay visible in the eventual design.

### 6.2 Isolated candidate probe

The temporary `exchange_calendars==4.13.2` XNYS probe returned:

| Date | Session | Open UTC | Close UTC | Derived 15-minute slots |
| --- | --- | --- | --- | --- |
| 2025-01-09 | no | - | - | - |
| 2025-07-03 | yes | 13:30 | 17:00 | 14 |
| 2025-11-28 | yes | 14:30 | 18:00 | 14 |
| 2025-12-24 | yes | 14:30 | 18:00 | 14 |
| 2026-07-03 | no | - | - | - |
| 2026-11-27 | yes | 14:30 | 18:00 | 14 |
| 2026-12-24 | yes | 14:30 | 18:00 | 14 |

This proves capability and matches the cited NYSE dates. It does not elevate
the package to official authority or prove all historical dates correct.

The current environment is Python `3.10.12` with NumPy `1.26.4`, satisfying
the candidate's published minimums. An unconstrained isolated resolver probe,
however, selected NumPy `2.2.6`, while the current Python 3.10 environment also
contains `newspaper4k` with a NumPy `<2` requirement. This does not disqualify
the candidate, but an implementation plan must pin and validate the dependency
solution instead of adding a bare unconstrained requirement.

## 7. Working Recommendation For Review

### Option A - Offline schedule owner plus official golden fixtures

**Recommended for the eventual spec, but not adopted here.**

Shape:

1. Add one backend `MarketSessionCalendar`-style owner backed by a pinned
   `exchange_calendars` XNYS version.
2. Define the current ArkScope universe as a reviewed US-equity-session proxy;
   do not imply per-listing exchange precision that the ticker-only universe
   cannot support.
3. Pin official NYSE full-day, early-close, holiday, and extraordinary-closure
   examples in tests.
4. Derive interval slots and current-day completion from returned session
   instants.
5. Judge coverage on timestamps inside the selected RTH session, not all rows
   on the UTC date.
6. Keep observed distributions as diagnostics, never as schedule authority.
7. Optionally compare a small IBKR `SCHEDULE` canary in an operational smoke;
   a provider outage must not remove the local health surface's calendar.

Why it currently leads:

- no provider or network request on every read;
- deterministic tests and historical replay;
- handles early and exceptional closes;
- preserves the pure-read route; and
- can normalize the existing mixed table without an immediate migration.

### Option B - Cached IBKR per-contract schedule authority

This is more contract-specific but introduces a provider-backed cache,
refresh/failure semantics, likely schema ownership, and an answer for what the
health endpoint does before Gateway startup. It is justified only if review
rejects a US-equity proxy and requires per-symbol exchange precision.

### Option C - Extend the hand-built holiday helper

Rejected as the default direction. Adding early-close tables and exceptional
closures manually would make ArkScope the calendar maintainer while still
leaving provider-session mixing unresolved.

## 8. Decisions Required Before Opening The Spec

Independent review should either answer or explicitly carry these questions:

1. **Runtime authority:** adopt the pinned offline calendar shape, require
   cached IBKR schedules, or request another candidate.
2. **Exchange scope:** is XNYS an explicit US-equity-session proxy for the
   current ticker-only universe, or must the universe gain exchange identity?
3. **Coverage session:** confirm RTH as the canonical diagnostic interval, or
   define another session policy.
4. **Historical normalization:** read-time RTH filtering only, future
   provider request bounding, row provenance, or some reviewed combination.
5. **No-trade slots:** decide whether they are `missing coverage`, `unknown`,
   or require provider corroboration before classification.
6. **Current-day completion:** derive from session close plus what reviewed
   settlement buffer, rather than fixed 16:30 ET?
7. **Listing/halts:** keep them as explicit limitations in V2 or add an
   authority that can prevent impossible repairs.
8. **Package maintenance:** pin/version/update cadence and official fixture
   review for exceptional closures.
9. **API/UI evolution:** retain existing fields during transition or replace
   maximum-relative `full`/`partial` semantics in one bounded contract change.
10. **Planner ownership:** whether partial-session repair enters the same slice
    as diagnostic truth or follows after the truth model is live.

## 9. Evidence-Derived Constraints For A Future Spec

These are not a final test ledger, but a design that contradicts them needs an
explicit reviewed reason:

1. Expected 15-minute counts are derived from session instants; neither `26`,
   `14`, nor `20` is an independent calendar constant.
2. 2025-01-09 is non-trading; the known 2025/2026 early-close dates carry their
   real close instants.
3. Neither the 64-row GOOG witness on 2026-07-02 nor the 63-row QBTS maximum on
   2026-07-24 can redefine the expected RTH count for the rest of the universe;
   the latter is itself one row short of its 64-slot observed span.
4. A uniformly truncated day and the one-full-outlier truncation shape remain
   visibly incomplete.
5. Massive fallback rows are either bounded to or filtered through the
   canonical coverage session.
6. Session assignment uses schedule instants rather than a UTC date prefix;
   during Eastern Standard Time, the final extended-hours bars cross into the
   next UTC date.
7. Calendar unavailability cannot silently produce `complete_like`; the
   eventual state/failure behavior must be explicit.
8. The pure-read diagnostics route does not require a live Gateway.
9. Frontend copy continues to render backend semantic IDs and does not infer
   coverage from English prose or raw counts.
10. Existing zero-day planner behavior changes only if the reviewed spec names
   partial repair as owned scope.
11. Production observations are rederived before implementation and never
    asserted as fixed ticker/count fixtures.

## 10. Reproduction Notes

### 10.1 Current calendar counterexamples

```bash
python - <<'PY'
from datetime import date, datetime
from zoneinfo import ZoneInfo
from src.tools.data_coverage_tools import _market_day_status
from src.market_data_direct import _is_session_complete

for day in (
    date(2025, 1, 9),
    date(2025, 7, 3),
    date(2025, 11, 28),
    date(2025, 12, 24),
    date(2026, 11, 27),
    date(2026, 12, 24),
):
    print(day, _market_day_status(day))

day = date(2025, 11, 28)
now = datetime(2025, 11, 28, 13, 31,
               tzinfo=ZoneInfo("America/New_York"))
print("early-close complete at 13:31 ET", _is_session_complete(day, now))
PY
```

### 10.2 Read-only row-distribution shape

```bash
python - <<'PY'
from collections import Counter
from pathlib import Path
import sqlite3

path = Path("data/market_data.db").resolve()
before = (path.stat().st_size, path.stat().st_mtime_ns)
with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
    for day in ("2025-11-28", "2026-06-25", "2026-07-10", "2026-07-24"):
        rows = conn.execute(
            "SELECT ticker, COUNT(*) FROM prices "
            "WHERE interval='15min' AND substr(datetime,1,10)=? "
            "GROUP BY ticker ORDER BY ticker",
            (day,),
        ).fetchall()
        print(day, Counter(int(n) for _, n in rows))
after = (path.stat().st_size, path.stat().st_mtime_ns)
assert before == after
PY
```

Run it only against the intended local DB. Counts will evolve and must be
dated; the distribution shapes are the evidence of interest.

### 10.3 Candidate package probe

The reviewed probe must use a temporary environment and print the installed
version, session open/close, and the derived half-open interval count. It must
not add a project dependency before the spec selects an authority.

## 11. Independent Review Resolution

Independent written review returned GREEN with zero substantive findings. Its
one precision question was the apparent `63`/`64` mismatch. A read-only replay
confirmed that the numbers belong to different dated witnesses:

- 2026-07-02 GOOG: 64 stored rows, 08:00-23:45 UTC;
- 2026-07-24 QBTS: 63 stored rows over the same endpoint span.

Sections 4.3 and 9 now name both witnesses explicitly. This resolves the
document ambiguity without changing either production observation.

The review covered:

- whether the three-layer problem statement matches the code and data;
- whether any viable runtime authority candidate is missing;
- whether XNYS can be an explicit US-equity proxy for the ticker-only universe;
- whether RTH read-time filtering is a valid migration-free baseline;
- whether provider/no-trade semantics require another authority before design;
  and
- whether the inventory is sufficient to open a separately reviewed Coverage
  v2 design spec.

The inventory is now cleared as the evidence basis for a separately reviewed
Coverage v2 design spec. It still does not adopt a runtime authority, RTH
policy, dependency, schema change, provider behavior, or repair scope by
itself. Product code and implementation planning remain unauthorized until the
design decisions in section 8 are resolved and that spec receives review.
