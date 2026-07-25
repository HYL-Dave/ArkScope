# ArkScope Coverage v2 Session-Truth Design

> **Status: WRITTEN - INDEPENDENT REVIEW PENDING**
>
> Written against clean design branch tip `7a8548fa` on 2026-07-26. This
> document converts the reviewed evidence in
> [`COVERAGE_V2_GROUND_TRUTH_INVENTORY.md`](../../design/COVERAGE_V2_GROUND_TRUTH_INVENTORY.md)
> into the product and engineering authority for Coverage v2. It authorizes
> neither implementation nor dependency changes until a separate RED-first
> implementation plan receives independent GREEN.

## 1. Purpose And Authority

The current trading-day diagnostic compares each ticker's stored row count
with that day's largest observed row count. That maximum is not a market
session authority. One extended-hours ticker can make ordinary RTH-shaped
tickers look partial, while a uniformly truncated day can make every ticker
look consistent with an incomplete maximum. A fixed `<20` threshold partially
limits the damage but also marks legitimate early-close sessions as thin.

Coverage v2 replaces that circular comparison with three explicit facts:

1. an offline calendar resolves whether a US-equity proxy session exists and
   supplies its open and close instants;
2. ArkScope defines RTH as the canonical coverage session; and
3. a pure classifier compares stored observations with the expected RTH slot
   starts without claiming that every absent aggregate is a provider failure.

Authority order is:

1. this document owns the Coverage v2 runtime calendar, RTH policy, state
   model, API replacement, frontend presentation boundary, and planner
   quarantine;
2. the reviewed ground-truth inventory owns dated baseline evidence and
   authority-candidate comparisons;
3. official NYSE calendars and notices own the reviewed fixture facts;
4. the pinned `exchange_calendars` XNYS adapter implements runtime schedule
   lookup but does not outrank official fixtures;
5. active-universe ownership remains with `src.active_universe`; and
6. a later, separately reviewed repair unit must establish evidence for any
   actionable price gap before a planner may consume one.

### 1.1 Grounded baseline

At `7a8548fa`:

- `summarize_trading_day_coverage()` opens `market_data.db` with SQLite URI
  `mode=ro`, performs no provider or Gateway call, and accepts an injectable
  `now_et` clock;
- `_is_session_complete()` treats normal-day `16:30 ET` as complete, which is
  regular close plus a 30-minute settle buffer, but it applies the same fixed
  wall-clock threshold to early-close sessions;
- the route resolves today's active universe and has no historical universe
  membership, listing-date, halt, exchange, or country authority;
- the current API emits maximum-relative `full`, `partial`, `missing`,
  `well_covered`, and `missing_tickers` facts;
- `plan_price_backfill()` directly converts every `missing_tickers` member on
  a completed trading day into scheduled work;
- `exclude_tickers` means a gap is believed to exist but is intentionally not
  attempted; it is not an appropriate home for an unclassifiable ticker;
- the frontend renders backend `coverage_status` rather than rederiving it;
  and
- the focused pre-spec coverage baseline is `82/82` tests.

Read-only production observations on 2026-07-25 and 2026-07-26 found:

- 2,386,679 stored `15min` rows and a 150-symbol current active universe;
- normal RTH-shaped sessions with 26 starts and known early-close sessions
  with 14 starts, both derived from session instants rather than accepted as
  independent constants;
- 2026-07-24 becomes `150 x 26` after read-time RTH projection, while the old
  maximum-relative method reports 149 partial tickers because LCID and QBTS
  contain extended-hours rows;
- seven RTH-window rows ending in `15:59:59+0000` do not match a 15-minute
  slot start, while duplicate physical `(ticker, datetime, interval)` keys are
  zero; all seven affected ticker-days also contain the exact neighboring
  slot rows, so these observations are extra unmatched rows, not evidence that
  an expected slot was replaced; and
- BTSG and ICHR have no stored rows before 2026-07-14 and then each have 234
  rows through 2026-07-24. This cannot prove that either ticker was absent
  from the historical universe or that historical provider data was
  impossible. It proves only that the current authorities cannot distinguish
  historical scope, listing, halt, no-trade, and collection-failure causes.

Every production statement above is dated evidence, not an acceptance
constant. Implementation must rederive it before product edits, and permanent
tests must use controlled fixtures.

## 2. Scope

### 2.1 In scope

- one pinned offline XNYS runtime adapter;
- an official-source fixture manifest with reviewed-range and forward-horizon
  metadata;
- a single owner that composes adapter availability and fixture authority into
  `calendar_health`;
- a read-only RTH observation reader;
- a pure slot-grid classifier;
- explicit market-scope and coverage-session enums;
- the ordered day-state model and separate unmatched-row signal;
- one atomic backend DTO and frontend presentation replacement;
- retirement of the legacy `missing_tickers` planner feed;
- typed calendar, storage, and active-universe failure presentation;
- dual-locale Settings copy and responsive visual verification; and
- dependency, pure-read, no-provider, and no-schema gates.

### 2.2 Out of scope

- writes or migrations to `market_data.db` or profile databases;
- storing provider, session, or row provenance;
- bounding future provider requests to RTH;
- a materialized coverage table or cached second truth owner;
- live IBKR `SCHEDULE`, Gateway, Massive, or other network calls;
- per-listing exchange precision or a claim that every current symbol is
  XNYS-listed;
- listing-date, halt, no-trade, entitlement, or provider-history authority;
- partial-session or zero-observation repair;
- resuming legacy unversioned gap continuations;
- changing raw price/date/number formatters;
- changing normal ingestion, backfill-executor mechanics, or provider retry
  policy; and
- treating production ticker names, dates, or counts as test fixtures.

## 3. Locked Decisions

1. **Runtime schedule:** use a pinned `exchange_calendars` XNYS adapter.
2. **Test authority:** official NYSE-derived fixtures control reviewed facts;
   the package is an implementation, not the authority.
3. **Provider independence:** runtime coverage remains available without a
   live Gateway or provider account.
4. **Market scope:** V1 is explicitly `us_listed_equity_proxy`; it does not
   imply per-ticker exchange identity.
5. **Coverage session:** V1 is RTH, represented by the closed enum value
   `rth`.
6. **Historical handling:** existing rows are projected through session
   windows at read time; no provenance migration is added.
7. **Expected slots:** derive half-open `[open, close)` slot starts from
   session instants and interval length. `26`, `14`, and `20` are not calendar
   constants.
8. **Clock:** preserve injectable time. Product logic must not read the clock
   inside the classifier.
9. **Completion:** preserve the existing 30-minute settle duration, but anchor
   it to each session's actual close. A 13:00 ET early close becomes complete
   at 13:30 ET rather than 16:30 ET.
10. **Absent slot semantics:** without independent evidence, an expected slot
    with no exact stored observation is `unknown`, never `missing` with an
    unknown reason.
11. **Unknown planner boundary:** unknown slots and tickers never enter planner
    candidates or `exclude_tickers`.
12. **Unmatched rows:** an in-window row that does not equal an expected slot
    start increments `unmatched_rth_row_count`; it fills no slot and creates no
    repair work.
13. **Day state:** use the ordered six-state model in Section 7. Do not parse or
    group enum values by prefix or substring.
14. **Atomic replacement:** retire maximum-relative fields, old status values,
    and the `missing_tickers` planner feed in one release. No compatibility
    period carries two meanings of complete or gap.
15. **Calendar maintenance:** a release must ship at least 12 months of
    officially reviewed forward coverage; a running build below six months is
    degraded.
16. **Repair order:** truth model first. Any repair planner follows in a
    separate design after an authority can prove actionable gaps.
17. **Frontend ownership:** the backend owns classification; the frontend
    maps closed semantic IDs to localized copy and never infers completeness
    from counts or prose.
18. **Schema:** no new table, column, marker, or database migration.

## 4. Architecture And Ownership

### 4.1 Components

| Component | Sole responsibility | Inputs | Forbidden behavior |
| --- | --- | --- | --- |
| `MarketSessionCalendar` | Resolve one date to no session or exact UTC open/close instants using pinned XNYS. | Market date. | DB access, provider calls, fixture-horizon policy, coverage classification. |
| `OfficialSessionFixtures` | Answer whether a date is inside the officially reviewed range and how much reviewed forward horizon remains. | Market date and injected `as_of` date. | Runtime schedule generation, DB access, provider calls, day-state classification. |
| `CoverageCalendarHealthEvaluator` | Compose adapter availability, per-date review coverage, and forward horizon into the one canonical `calendar_health`. | Adapter result, fixture authority, injected clock. | Resolving sessions itself or duplicating health logic in either dependency. |
| `RthObservationReader` | Read candidate rows for the active universe and retain every row inside each half-open session window. | Read-only DB path, canonical ticker/alias set, reviewed session windows, interval. | Slot alignment, state classification, dropping off-grid rows, writes, provider calls. |
| `SlotCoverageClassifier` | Build expected grids, match exact observations, count unmatched rows, and derive ticker/day states. | Sessions, reader rows, universe, interval, injected time. | DB/calendar/provider access, internal clock reads, repair decisions. |
| `TradingDayCoverageService` | Orchestrate owners, preserve typed failures, and project the atomic route DTO. | Active-universe snapshot, owners above, lookback, interval, injected clock. | Reimplementing schedule, fixture, reader, or classifier rules. |
| Settings coverage presenter | Render backend enums, counts, and diagnostics in both locales. | Coverage v2 DTO and current `developerMode`. | Recomputing coverage, parsing backend prose, exposing raw diagnostics in normal mode, starting repair. |

The names above define ownership, not mandatory file names. The implementation
plan may choose code locations that match existing repository conventions, but
it must preserve these dependency directions and one owner per rule.

### 4.2 Load-bearing boundary contracts

1. **Window before alignment.** `RthObservationReader` filters only by
   `[session_open, session_close)`. It must return in-window off-grid rows to
   `SlotCoverageClassifier`; otherwise `unmatched_rth_row_count` would be
   silently forced to zero at the boundary.
2. **One health composer.** Neither `MarketSessionCalendar` nor
   `OfficialSessionFixtures` emits `calendar_health`. Only
   `CoverageCalendarHealthEvaluator` combines their facts.
3. **Injected time throughout.** `TradingDayCoverageService` resolves or
   accepts `now_et` once and passes it down. Tests can therefore prove early-
   close completion without patching global time.
4. **Two fixture questions.** `OfficialSessionFixtures.is_reviewed(date)` and
   `forward_horizon_months(as_of)` remain separate. A historical date may be
   reviewed and computable while the forward horizon is degraded.
5. **Pure classifier.** Golden calendar and observation fixtures can exercise
   the entire state model without SQLite, the calendar package, a provider, or
   the current wall clock.

## 5. Calendar Authority And Dependency Policy

### 5.1 Runtime adapter

V1 uses `exchange_calendars==4.13.2` and its XNYS calendar. The adapter returns
a typed result:

```text
session(date) ->
  closed
  | open { market_date, open_at_utc, close_at_utc, session_kind }
  | unavailable { reason_code }
```

`session_kind` is `regular` or `early_close`. The adapter normalizes all
instants to timezone-aware UTC values. It does not expose pandas objects or
package-specific types beyond its boundary.

XNYS is a schedule proxy for the current ticker-only US-equity universe. It is
not a claim that every symbol is NYSE-listed. The DTO states that limitation
through `market_scope` rather than leaving it implicit.

### 5.2 Official fixture authority

The repository ships a reviewed manifest containing:

- `reviewed_from` and `reviewed_through` dates;
- direct official NYSE source references used for that review;
- at least one ordinary full session;
- every known early-close date in the reviewed support interval; and
- extraordinary closures required by the evidence set, including
  2025-01-09.

Package output must match these facts in tests. A mismatch is a release
failure, not a runtime preference between two competing schedule owners.
Fixtures do not become a second session generator.

The fixture API answers two independent questions:

```text
is_reviewed(date) -> bool
forward_horizon_months(as_of) -> non-negative number
```

The first controls whether a requested date may be classified. The second
controls maintenance health. Conflating them would make it impossible to show
a reviewed historical day while warning that future fixture review is aging.

### 5.3 Forward horizon

- Every new release must have `reviewed_through` at least 12 calendar months
  beyond the release evidence date.
- `reviewed_from` must cover every date reachable through the route's maximum
  reviewed lookback at release.
- A running build with less than six months remaining reports
  `calendar_health.status = degraded` and reason
  `fixture_horizon_low` on the same Settings coverage surface.
- A running build with at least six but less than 12 months remaining stays
  runtime-`ok`; its returned horizon makes maintenance visible, while the
  12-month rule prevents a new release from shipping in that state.
- A date outside the reviewed interval is `unknown`, even if the package can
  mechanically generate a schedule for it.
- Dates inside the reviewed interval remain classifiable when the global
  horizon is degraded.

The horizon detects neglected maintenance. It cannot predict a suddenly
announced closure such as 2025-01-09. That risk is controlled only by timely
official review and a new release; the UI must not imply otherwise.

The 12- and six-month thresholds use calendar-date arithmetic, not a fixed
30-day month approximation. A numeric `forward_horizon_months` is presentation
evidence; threshold decisions compare exact dates.

The pinned package's default calendar bounds are based on its construction
date and explicit requests can generate far-future sessions. Therefore the
horizon measures the reviewed fixture manifest, never the package's ability
to generate dates.

### 5.4 Dependency solution

The direct requirement is pinned to `exchange_calendars==4.13.2`. Before
product edits, the implementation plan must resolve and record the complete
Python 3.10 dependency solution against the repository environment, including
NumPy `1.26.4` and pandas `2.3.1`. A mechanical test must verify:

- the installed direct version;
- the reviewed resolved dependency constraints;
- importability under the supported Python runtime; and
- one normal, one early-close, and one extraordinary-closure schedule probe.

A bare unconstrained requirement is forbidden. The current Python and NumPy
versions are a baseline, not permanent architecture; however, if this bounded
unit requires an unrelated Python or NumPy major upgrade, implementation must
stop for a separate dependency-modernization decision.

The evaluated fallback A-prime is a bounded, generated session table checked
into the repository, with `exchange_calendars` used only by a maintenance
script. It avoids runtime dependency risk but creates a new generation and
review ceremony with no repository precedent. It is not selected. It may be
reopened only if the reviewed dependency solve is not clean.

## 6. Session And Observation Model

### 6.1 Coverage scope

The DTO carries two orthogonal closed enums:

```text
market_scope = us_listed_equity_proxy
coverage_session = rth
```

`market_scope` answers which universe policy is being judged.
`coverage_session` answers which daily time window is being judged. Combining
them into one value would couple future changes that are logically separate.

There is no ticker-pattern scope detector in V1. `ticker_meta` does not carry
exchange or country, and inferring listing identity from a symbol would create
false confidence. A scope-violation detector may enter the engineering issue
register only after concrete non-US evidence or an exchange-identity owner
exists.

### 6.2 Expected grid

For a trading session and a supported interval:

```text
expected_slot_starts = [open, open + interval, ..., value < close]
```

The grid is half-open. A 09:30-16:00 ET regular session yields 26 15-minute
starts; a 09:30-13:00 ET early close yields 14. Tests assert the instants and
derivation rather than a free-standing `26` or `14` constant.

Coverage v2 supports `15min` only. Other interval values receive a typed 422
instead of silently applying unreviewed grid semantics.

### 6.3 Observation reader

The reader:

1. opens the resolved market database with SQLite URI `mode=ro` and
   `PRAGMA query_only=ON`;
2. validates that the `prices` table and required columns exist;
3. bounds reads by canonical universe/aliases, `interval='15min'`, and the UTC
   span containing the requested session windows;
4. maps stored aliases to canonical tickers;
5. retains a row only when its timestamp lies inside that date's exact
   `[open_at_utc, close_at_utc)` window; and
6. returns every retained timestamp to the classifier, whether aligned or not.

The reader must not use `substr(datetime, 1, 10)` as session identity. Extended
hours can cross UTC-date boundaries during Eastern Standard Time; schedule
instants, not a UTC prefix, assign rows to a market date.

Physical duplicates cannot increase slot coverage. The existing primary key
prevents identical raw keys, and any alias-canonicalized collision is reduced
to one observed slot by the classifier.

### 6.4 Slot matching and unmatched rows

For each canonical ticker:

- an expected slot is `observed` only if at least one normalized stored
  timestamp equals that slot start exactly;
- otherwise it is `unknown`;
- an in-window timestamp that equals no slot start increments the day's
  `unmatched_rth_row_count`;
- an unmatched row does not fill the nearest slot;
- a row outside RTH is excluded by policy and does not count as unmatched; and
- neither unknown slots nor unmatched rows create planner work.

`unmatched_rth_row_count` is a data-quality signal. It is displayed on the
same coverage surface but does not alter slot, ticker, or day coverage state.
A day can therefore be coverage-complete and separately carry an unmatched-
row warning without contradiction.

### 6.5 Ticker state

For a completed reviewed session:

| State | Derivation |
| --- | --- |
| `complete` | Every expected slot is observed. |
| `partial` | At least one expected slot is observed and at least one is unknown. |
| `unknown` | No expected slot is observed. |

`unknown` does not assert that data is unavailable at the provider, that the
ticker was listed, that it traded, that it was in the historical universe, or
that a repair is possible.

## 7. Health And Day-State Model

### 7.1 Calendar health

`CoverageCalendarHealthEvaluator` is the only owner of:

```text
calendar_health.status = ok | degraded | unavailable
```

Closed reason codes include:

- `fixture_horizon_low`;
- `date_unreviewed`; and
- `calendar_unavailable`.

More than one reason may be present across a lookback. `degraded` due only to
future horizon does not erase valid classifications for reviewed dates.
Adapter failure is `unavailable`, and affected dates are `unknown`, never
`non_trading` or complete-like.

### 7.2 Observation health

Storage availability is a separate fact:

```text
observation_health.status = ok | unavailable
```

Closed unavailability reasons are `market_db_missing`,
`market_db_unreadable`, and `prices_schema_missing`. A readable empty prices
table is `ok` with zero observations; a missing or unreadable store is not
misrepresented as an empty dataset. Affected trading dates are `unknown`.

### 7.3 Ordered day-state precedence

The backend applies this ordered table exactly once per date:

| Order | Condition | `coverage_status` |
| --- | --- | --- |
| 1 | Calendar cannot resolve a reviewed session decision for the date, or observations are unavailable for a trading date. | `unknown` |
| 2 | Reviewed calendar says there is no session. | `non_trading` |
| 3 | Injected time is before `session_close + 30 minutes`. | `in_progress` |
| 4 | Session is complete and every universe ticker has zero observed slots. | `unknown` |
| 5 | At least one observed ticker is `partial`. | `partial` |
| 6 | Every observed ticker is complete and at least one ticker is `unknown`. | `indeterminate_tickers` |
| 7 | Every universe ticker is complete. | `complete` |

The enum deliberately uses `indeterminate_tickers`, not a value beginning
with `complete`. It avoids inviting prefix-based consumers to treat an
unresolved universe as fully complete. Every backend and frontend consumer
must still use an exhaustive exact-match switch; substring, prefix, and prose
parsing are forbidden.

If partial and unknown tickers coexist, the day is `partial` and
`unknown_ticker_count`/`unknown_tickers` preserve the independent unknown
fact. No `partial_with_unknown_tickers` state is added.

### 7.4 State invariants

For every completed trading day:

```text
complete_ticker_count
  + partial_ticker_count
  + unknown_ticker_count
  == universe_count

observed_ticker_count
  == complete_ticker_count + partial_ticker_count
```

Additional invariants:

- `complete` requires `complete_ticker_count == universe_count`;
- `indeterminate_tickers` requires `complete_ticker_count > 0`,
  `partial_ticker_count == 0`, and `unknown_ticker_count > 0`;
- `partial` requires `partial_ticker_count > 0`;
- post-session `unknown` requires `observed_ticker_count == 0` unless a typed
  calendar/storage failure already selected it;
- `unmatched_rth_row_count >= 0` and never changes these equations; and
- no state is stored independently from the facts that derive it.

## 8. Atomic API Contract

### 8.1 Top-level shape

The route remains `GET /market-data/trading-days` and pure read. Its V2
contract is conceptually:

```ts
type MarketScope = "us_listed_equity_proxy";
type CoverageSession = "rth";
type CalendarHealth = "ok" | "degraded" | "unavailable";
type ObservationHealth = "ok" | "unavailable";
type CalendarHealthReason =
  | "fixture_horizon_low"
  | "date_unreviewed"
  | "calendar_unavailable";
type ObservationHealthReason =
  | "market_db_missing"
  | "market_db_unreadable"
  | "prices_schema_missing";

interface TradingDayCoverageV2 {
  version: 2;
  market_scope: MarketScope;
  coverage_session: CoverageSession;
  interval: "15min";
  lookback_days: number;
  universe_count: number;
  generated_at_et: string;
  calendar_health: {
    status: CalendarHealth;
    reason_codes: CalendarHealthReason[];
    reviewed_through: string;
    forward_horizon_months: number;
  };
  observation_health: {
    status: ObservationHealth;
    reason_code: ObservationHealthReason | null;
  };
  days: TradingDayCoverageRowV2[];
  provider_errors: ProviderSyncIssue[];
}
```

`market_scope`, `coverage_session`, health statuses, reason codes, and day
statuses are closed backend and frontend enums. The implementation must not
weaken them to arbitrary strings.

### 8.2 Day shape

```ts
type CoverageDayStatus =
  | "non_trading"
  | "in_progress"
  | "complete"
  | "partial"
  | "indeterminate_tickers"
  | "unknown";

type CoverageDayReason =
  | "calendar_unavailable"
  | "date_unreviewed"
  | "observation_unavailable"
  | "no_observations";

interface TradingDayCoverageRowV2 {
  date: string;
  coverage_status: CoverageDayStatus;
  status_reason_code: CoverageDayReason | null;
  closure_reason_code: "weekend" | "market_closed" | null;
  session_kind: "regular" | "early_close" | null;
  session_open_at_utc: string | null;
  session_close_at_utc: string | null;
  expected_slot_count: number | null;
  observed_ticker_count: number | null;
  complete_ticker_count: number | null;
  partial_ticker_count: number | null;
  unknown_ticker_count: number | null;
  partial_tickers: Array<{
    ticker: string;
    observed_slot_count: number;
    expected_slot_count: number;
  }>;
  unknown_tickers: string[];
  unmatched_rth_row_count: number | null;
}
```

Counts and ticker classifications are null for `non_trading` and calendar or
storage failure. `in_progress` may expose session instants and expected slot
count, but it does not publish completed-session ticker classifications. The
UI must not display unfinished slots as gaps.

`closure_reason_code` intentionally makes no unsupported claim about a named
holiday. Weekend versus market-closed is sufficient localized chrome for V1;
official source references remain in the fixture authority and developer
evidence.

### 8.3 Retired contract

The following V1 semantics are removed in the same backend/frontend change:

- `max_observed_bar_count`;
- `full`;
- `well_covered`;
- maximum-relative `partial` and `partial_tickers[].bars`;
- `missing` and `missing_tickers`;
- `covered`;
- fixed-wall-clock `session_complete`;
- status values `missing`, `thin`, and `complete_like`; and
- frontend copy that describes maximum-relative completeness.

No alias, hidden field, compatibility DTO, or transition period preserves
these meanings. A mixed old-backend/new-frontend or new-backend/old-frontend
deployment is unsupported; ArkScope ships both in one local application
release.

### 8.4 Provider diagnostics

`provider_sync_meta.last_error` remains a separate current diagnostic and is
cleared by an eventual successful provider sync under existing behavior. It
does not prove that a particular expected slot should exist, does not affect
coverage state, and never enters planner candidates or exclusions.

The Settings surface renders a generic localized provider-issue summary in
normal mode. Existing raw diagnostic detail remains Developer-only under the
current Settings diagnostic boundary; sanitizer alignment remains separately
owned work and is not silently absorbed here. Provider issues are no longer
shown only beneath a `missing_tickers` day, because that field no longer
exists.

## 9. Planner Boundary

### 9.1 Three epistemic classes

Planner inputs have three conceptually different classes:

| Class | Meaning | Planner destination |
| --- | --- | --- |
| Proven actionable gap | Independent authority proves a slot should exist and repair can address it. | Candidate input. |
| Proven gap, intentionally skipped | A gap is proven, but policy or known provider limitation forbids the attempt. | `excluded`. |
| No proven gap | The expected session slot has no observation, but listing, trade, historical scope, halt, provider, and collection causes are unresolved. | Neither candidate nor `excluded`; planner never sees it. |

Coverage v2 supplies only observations and unknowns. It introduces no
independent bar-availability authority, so it produces no proven actionable
gap.

### 9.2 Legacy feed retirement

The old path

```text
completed day -> missing_tickers -> plan_price_backfill() -> scheduled work
```

is retired atomically with the V2 DTO. `unknown_tickers` must never be renamed,
adapted, copied, or defaulted into `missing_tickers`, and must not be placed in
`exclude_tickers`.

Coverage-derived automatic price-gap planning therefore becomes a deliberate
no-op until a later repair design supplies proof. The generic backfill executor
and explicit ticker/window operations remain unchanged; only the unproven
coverage-derived candidate source is removed.

Any saved continuation produced by the legacy gap semantics is unversioned and
cannot be trusted under V2. It must not resume. The implementation plan must
choose a fail-closed, no-schema mechanism that rejects it with a stable
`legacy_unproven_gap` reason while preserving historical audit rows. It must
not infer V2 proof from old ticker/date lists.

## 10. Failure Semantics

| Failure | API behavior | Day behavior | UI behavior |
| --- | --- | --- | --- |
| Active universe unavailable | Preserve existing typed 503 and recovery route. | No denominator, so no fabricated day rows. | Localized error and existing Settings recovery navigation. |
| Calendar adapter unavailable | Return V2 DTO with `calendar_health=unavailable`. | Affected dates `unknown`. | Explicit calendar-unavailable state; never market-closed or complete. |
| Date outside reviewed fixture interval | Return `calendar_health=degraded` with `date_unreviewed`. | That date `unknown`. | Explain reviewed range without implying the market was closed. |
| Forward fixture horizon below six months | Return `calendar_health=degraded` with `fixture_horizon_low`. | Reviewed dates still classify normally. | One maintenance warning on the coverage surface. |
| Market DB missing/unreadable/schema-invalid | Return V2 DTO with typed `observation_health=unavailable`. | Trading dates `unknown`. | Distinguish unavailable storage from a readable empty dataset. |
| Readable DB with zero rows | `observation_health=ok`. | Completed trading dates `unknown`. | Show zero observed tickers, not a storage failure and not complete. |
| Unsupported interval | Typed HTTP 422. | No classification. | Existing localized request failure presentation. |
| Off-grid RTH rows | Successful DTO with positive `unmatched_rth_row_count`. | Coverage state unchanged. | Data-quality warning; no repair action. |

All failures use structured reason codes. The frontend must not parse exception
text to choose copy. The coverage read path remains free of writes, provider
requests, PG attempts, and automatic repair.

## 11. Settings Presentation

The existing Settings -> Data Storage coverage panel remains the sole user-
facing owner. It stays explicitly read-only.

### 11.1 Normal mode

- Render one localized status for each closed `coverage_status` value.
- Reserve the positive tone for `complete` only.
- Render `indeterminate_tickers` as a neutral attention state: "Observed
  tickers complete; N tickers cannot be assessed," not as a missing-data or
  repair claim.
- Render `partial` with observed/expected slot counts for affected tickers and
  separately report any unknown ticker count.
- Render `unknown` with its stable reason rather than a zero count.
- Show `unmatched_rth_row_count > 0` as a separate data-quality warning.
- Show market scope, RTH session policy, expected session slots, and the
  reviewed-through date without presenting XNYS as every ticker's listing
  exchange.
- Show provider issues in a separate diagnostic summary rather than attaching
  them to an unknown ticker or day.
- Do not add a repair, retry, or backfill control.

### 11.2 Developer mode

Developer mode may show exact unknown ticker IDs, partial slot counts, session
instants, unmatched-row counts, fixture reason codes, and existing provider
diagnostics. It still may not infer a missing bar or planner action from an
unknown slot.

### 11.3 Localization and responsive behavior

All new chrome uses the existing Settings namespace and is born in zh-Hant and
English with strict key parity and non-empty values. Tickers, timestamps, and
backend diagnostic source content retain their original values. Formatter
behavior remains frozen under the app-wide i18n decision.

The panel must remain usable at 390, 760, 960, and 1440 CSS pixels in both
locales, including the worst credible composition:

- long English health and indeterminate text;
- horizon degradation;
- partial and unknown ticker lists together;
- provider issue summary; and
- a positive unmatched-row warning.

No page-level horizontal overflow, clipped status text, overlapping controls,
or locale-keyed remount is allowed. CSS changes require measured evidence and
the implementation plan's reviewed-deviation procedure.

## 12. Test And Evidence Contract

### 12.1 Calendar and dependency

RED-first tests must prove:

- exact installed direct and resolved dependency versions;
- no unrelated Python or NumPy major change;
- normal full-day open/close instants;
- every reviewed early-close fixture;
- 2025-01-09 as non-trading;
- package/official-fixture disagreement fails the release gate;
- `is_reviewed(date)` is independent from
  `forward_horizon_months(as_of)`;
- release horizon below 12 months fails the release fixture gate;
- runtime horizon below six months yields degraded health;
- a reviewed historical date still classifies under global horizon
  degradation; and
- adapter failure cannot become `non_trading` or complete.

### 12.2 Reader/classifier boundary

Independent tests must prove:

- the reader opens SQLite read-only and leaves size/mtime unchanged;
- no PG, Gateway, provider, scheduler, or write path is invoked;
- rows are assigned by UTC session instants rather than date prefix;
- extended-hours rows are excluded without becoming unmatched;
- an in-window `15:59:59` row reaches the classifier and increments
  `unmatched_rth_row_count`;
- that unmatched row does not fill `15:45` or any nearest slot;
- alias-canonicalized duplicate observations fill one slot only;
- a normal RTH fixture yields all exact expected slots despite extended-hours
  outliers; and
- uniform truncation and one-complete-outlier truncation both remain partial.

### 12.3 State model

Use one named test for each ordered precedence path:

1. calendar unavailable -> `unknown`;
2. non-trading -> `non_trading`;
3. pre-close-buffer -> `in_progress`;
4. completed session with all tickers zero-observation -> `unknown`;
5. at least one observed partial ticker -> `partial`;
6. observed cohort complete plus unknown ticker ->
   `indeterminate_tickers`; and
7. all tickers complete -> `complete`.

Additional nodes must prove:

- early-close 13:29 ET is in progress and 13:30 ET is complete under the
  reviewed 30-minute buffer;
- partial plus unknown remains `partial` while preserving the unknown count
  and list;
- all count equations in Section 7.4;
- unmatched rows never affect state;
- frontend and backend switches are exhaustive exact matches; and
- no code uses `startswith`, substring inclusion, or prose parsing for
  coverage enum classification.

### 12.4 Planner isolation

Mutation-style tests must prove that:

- passing unknown tickers cannot create planner candidates;
- passing unknown tickers through `exclude_tickers` is rejected or impossible
  by construction;
- provider errors cannot create candidates or exclusions;
- the V2 DTO contains no `missing_tickers` compatibility field;
- legacy unversioned continuations do not execute; and
- removing the planner boundary makes a focused test RED.

### 12.5 API, UI, and runtime

- Backend route fixtures cover every health/day enum and typed failure.
- TypeScript contract tests reject unknown enum values and retired fields.
- Presenter tests cover both locales and every state, including
  `indeterminate_tickers`, partial-plus-unknown, horizon degradation, and
  unmatched-row warning.
- Normal mode contains no raw provider diagnostic; Developer mode retains its
  reviewed owner.
- Locale switching preserves expansion, lookback selection, focus, and node
  identity without a data refetch beyond the locale PUT.
- Real-browser matrices cover both locales and the four widths in Section
  11.3.
- A read-only production replay records current distributions as dated
  evidence, verifies integrity/FK where applicable, and proves DB size/mtime
  unchanged. Production values are never copied into permanent assertions.

### 12.6 Structural gates

The implementation plan must provide byte or semantic gates proving:

- no market/profile DB schema or migration changed;
- no provider retrieval, write, formatter, prompt, extension, Electron, or
  unrelated Settings behavior changed;
- no live Gateway, Massive, PG, or repair call occurs in coverage tests;
- the old maximum-relative constants and frontend status copy are gone from
  the coverage path; and
- only the reviewed dependency solution entered requirements/constraints.

## 13. Rollout And Operational Proof

1. Land dependency and calendar contract RED tests before runtime wiring.
2. Build the pure calendar-health and classifier owners against fixtures.
3. Build the read-only reader and boundary tests.
4. Replace backend DTO, planner feed, TypeScript contract, and frontend
   presentation as one non-shippable-until-green tranche.
5. Run focused, full, typecheck/build, no-PG, schema, and byte gates.
6. Run isolated API/browser matrices with an isolated copied or synthetic
   market database.
7. On the reviewed tip, perform production read-only replay only. Do not run a
   backfill, scheduler source, provider request, or database migration as a
   smoke test.

Rollback is code-only because the unit changes no database format or stored
data. The newly pinned dependency must remain in sync with the code rollback;
partial rollback of only the API or frontend is unsupported.

## 14. Alternatives Rejected

### 14.1 Cached IBKR schedule authority

Rejected for V1. It would make a currently pure-read diagnostic depend on the
Gateway precisely when provider failure makes diagnostics most valuable. It
also requires cache, refresh, failure, and historical-retention policy.
Optional corroboration may be designed later but cannot control runtime state.

### 14.2 Hand-maintained holiday and early-close rules

Rejected. ArkScope would become the calendar maintainer while still lacking
exceptional closures and provider-session normalization.

### 14.3 Count-only completeness

Rejected. Existing off-grid rows prove that raw row count and expected slot
identity are different facts. Count-only logic can be satisfied by the wrong
timestamps and cannot produce repairable slot identities later.

### 14.4 Materialized coverage table

Rejected. It conflicts with the locked read-time normalization and no-schema
decisions, introduces refresh semantics, and creates a second state owner that
can lag `prices`.

### 14.5 Treat every zero-observation ticker as partial or excluded

Rejected. Applying today's universe to historical dates without membership,
listing, halt, or provider evidence creates persistent false alarms. Putting
unknowns in `exclude_tickers` is also false: exclusion asserts a proven gap
that policy chose not to repair.

### 14.6 Generated checked-in session table

Not selected for V1. It is the explicit A-prime escape hatch if the dependency
solution fails review. Adopting it requires a new generation, review, horizon,
and update ceremony in a separate amendment.

## 15. Acceptance Criteria

Coverage v2 is complete only when all of the following are true:

1. A pinned, mechanically verified offline XNYS adapter supplies runtime
   session instants without provider access.
2. Official fixtures cover the reviewed range, early closes, and exceptional
   closures with at least 12 months forward at release.
3. Calendar health has one owner and distinguishes unavailable, unreviewed,
   and low-horizon states.
4. RTH observations are read from SQLite in pure-read mode and off-grid rows
   survive the reader/classifier boundary.
5. Expected slots derive from session instants and interval size.
6. Slot, ticker, and day states obey the ordered model and invariants.
7. `indeterminate_tickers`, unknown counts, and unmatched rows remain distinct
   facts.
8. The old maximum-relative DTO and status values are absent.
9. Unknowns and provider diagnostics have no path into planner candidates or
   exclusions, and legacy unversioned continuations cannot run.
10. Settings renders the new contract in both locales without recomputation,
    overflow, clipping, raw normal-mode diagnostics, or repair controls.
11. Production verification is read-only and leaves databases unchanged.
12. A separate independent implementation review returns GREEN before merge.

## 16. Implementation-Plan Requirements And Stop Conditions

The RED-first implementation plan must include:

- a grounded file map and exact dependency solution;
- baseline and target backend/frontend node ledgers;
- named tests for all seven precedence paths and all planner boundaries;
- package/fixture, horizon, reader/classifier, API/UI, visual, no-PG,
  no-provider, no-write, schema, and byte gates;
- the precise atomic tranche that changes backend, frontend, and planner
  consumers together;
- isolated runtime and production read-only procedures; and
- independent review focus on every load-bearing boundary in Section 4.2.

Implementation must stop for reviewed amendment if:

1. the clean dependency solve requires an unrelated Python or NumPy major
   upgrade;
2. pinned package output disagrees with an official reviewed fixture;
3. historical timestamps cannot be normalized without a schema change;
4. active-universe scope requires exchange/listing inference to classify a
   day;
5. any design attempts to classify unknown as missing or feed it to planner;
6. an existing saved continuation cannot be prevented from running without a
   migration or destructive state rewrite;
7. the API cannot replace old semantics atomically across backend, frontend,
   and planner consumers;
8. a provider or Gateway call becomes necessary for the read path;
9. production verification would write, repair, or schedule work; or
10. responsive correction requires CSS outside a separately recorded bounded
    deviation.
