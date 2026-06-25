# P1.2 Spec — Free Calendar / Macro (FRED + Finnhub)

> **Status**: design doc, no code yet. Written 2026-04-26.
> **Predecessor**: `P1_2_PROVIDER_DISCOVERY.md` — read first; it lists the smoke-tested provider behaviour this spec assumes.
> **Goal**: ship a calendar + macro data layer that's honest about lookahead bias and adds zero false neutrals to downstream analysis.
> **Non-goal**: backtest infrastructure, signal validation, macro feature engineering (e.g. CPI YoY), SA comment integration, real-time / WebSocket, LLM scoring.

---

## 1. What this is and isn't

**Is**:

- A read-only data layer covering economic events (FOMC, CPI prints, etc.), earnings + IPO calendars, and macro time-series values (CPI, FFR, GDP, unemployment).
- An ingestion pipeline that captures **mutating rows** (e.g. `actual` flipping null → value at release, IPO `status` changing) as an append-only revision log so backtests can replay any decision date without lookahead bias.
- A small set of API endpoints and agent tools that surface this data with explicit `as_of` semantics (ISO 8601 date or timestamp; see §6).

**Isn't**:

- A unified "calendar" model that hides Finnhub vs FRED. The two cover different shapes — events vs values — and the spec keeps them separate.
- A signal-validation layer. P1.2 produces inputs; downstream factor-rank / decile-analysis sits on top of P1.2 and is not in scope here.
- A macro feature library. We store raw FRED observations; YoY changes / z-scores / regime detectors are derivative work for a later cycle.

---

## 2. Sources of truth (settled by smoke)

| Concern | Source | Why |
|---|---|---|
| Economic event calendar (FOMC, CPI release, NFP, etc.) | **Finnhub `/calendar/economic`** | Free-tier covers upcoming + historical with `actual`/`estimate`/`prev`, UTC-stamped |
| Earnings calendar | **Finnhub `/calendar/earnings`** | Estimates + `hour` (BMO/AMC/dmh) on free tier; actuals never observed populated, captured via re-poll |
| IPO calendar | **Finnhub `/calendar/ipo`** | Full 4-state status enum (priced/filed/expected/withdrawn) |
| Macro time-series values | **FRED `/series/observations`** | Vintages via `realtime_start/end` + `vintage_dates` (ALFRED) |
| Macro release schedule | **FRED `/release/dates`** | Day-level scheduled release dates per release group |

---

## 3. Data model

### 3.1 Naming + namespace

All P1.2 tables live under the `macro_*` and `cal_*` prefixes to keep them out of the way of existing news / SA / scoring tables. Migration file `sql/013_add_p1_2_macro_calendar.sql`.

### 3.2 Tables

#### `cal_economic_events` (Finnhub economic calendar)

```
event_id           bigserial primary key
country            char(2) not null               -- ISO-2 (US, CN, ...)
event_name         text not null                  -- e.g. "Fed Interest Rate Decision"
event_time         timestamptz not null           -- UTC, from Finnhub `time`
impact             varchar(8) check (impact in ('low','medium','high','')) not null default ''
unit               text                            -- '%' / '$' / '' / etc.
actual             numeric                         -- null until released
estimate           numeric                         -- consensus
prev               numeric                         -- prior period
fingerprint        text not null                   -- sha256(country|event_name|event_time)
fetched_at         timestamptz not null default now()
updated_at         timestamptz not null default now()
unique (fingerprint)
```

Index: `(event_time desc)`, `(country, event_time desc)`, `(impact, event_time desc) where impact = 'high'`.

`fingerprint` is a stable identity so re-fetching the same event upserts the same row instead of duplicating it. Mutations to `actual`/`estimate`/`prev` go to `cal_economic_event_revisions`.

#### `cal_economic_event_revisions` (append-only)

```
revision_id        bigserial primary key
event_id           bigint not null references cal_economic_events(event_id) on delete cascade
observed_at        timestamptz not null default now()
actual             numeric                         -- value of the field as observed at observed_at
estimate           numeric                         -- "
prev               numeric                         -- "
source_payload     jsonb not null                  -- raw provider row at this observation
unique (event_id, observed_at)
```

**Semantics**: each row stores **the state observed at `observed_at`**, not the prior state. So if at t0 we ingest the event with `actual = null` and at t1 (after release) we re-ingest and now see `actual = 4.5`, the table holds:

| observed_at | actual | estimate | prev |
|---|---:|---:|---:|
| t0 (initial baseline)   | null | 4.5 | 4.75 |
| t1 (post-release re-poll) | 4.5  | 4.5 | 4.75 |

The canonical `cal_economic_events` row carries the **latest** observed state (t1's). The revision log is the audit trail of what the canonical row used to be.

Two rules around insertion ensure the log is queryable from the first observation:

1. **First insert** of a new event also appends a baseline revision row with the current observed state — otherwise an as-of query before any mutation has no row to find.
2. **Subsequent ingestions** append a revision row only when at least one tracked field differs from the canonical row.

For lookahead-safe queries by `as_of` (timestamp; see §6), the read tool computes:

```sql
-- The state of an event as we knew it at as_of:
SELECT actual, estimate, prev
FROM cal_economic_event_revisions
WHERE event_id = $1 AND observed_at <= $2
ORDER BY observed_at DESC
LIMIT 1
```

`as_of = t0 + 30s` → returns the t0 row (null actual). `as_of = t1 + 1s` → returns the t1 row (actual=4.5). `as_of = t1 − 1s` → returns the t0 row even though the world has the actual at that wall-clock — because at t1 − 1s **we** had not yet observed it. That's the correct lookahead-safety semantic: backtests reason about what our system had access to, not what was true in the world.

`source_payload` is the raw provider row (Finnhub returns rows with empty strings, missing keys, occasional schema drift); preserving it lets us re-derive any tracked field if extraction logic changes without re-fetching.

The same revision pattern is reused for earnings + IPO below.

#### `cal_earnings_events` + `cal_earnings_event_revisions`

```
earnings_id        bigserial primary key
symbol             text not null
report_date        date not null                  -- Finnhub `date`
year               int not null
quarter            int not null check (quarter between 1 and 4)
hour               varchar(4) not null default '' -- 'bmo'|'amc'|'dmh'|''
eps_estimate       numeric
eps_actual         numeric                         -- never seen on free tier; reserved for paid upgrade
revenue_estimate   numeric
revenue_actual     numeric
fingerprint        text not null                   -- sha256(symbol|year|quarter)
fetched_at         timestamptz not null default now()
updated_at         timestamptz not null default now()
unique (fingerprint)
```

Index: `(symbol, report_date desc)`, `(report_date desc)`.

Revisions table mirrors `cal_economic_event_revisions` shape — same first-insert-baseline + observed-state semantics, plus `source_payload jsonb`. Tracked fields: `eps_estimate`, `eps_actual`, `revenue_estimate`, `revenue_actual`, `hour`. `hour` revisions matter — Finnhub flips `''` → `bmo`/`amc` as the report date approaches.

**Per-symbol ingestion is required** — the unfiltered date-range query under-samples (smoke §5.1). Watchlist coverage = 50 tickers × 1 query per ingestion run × per-day frequency = 50/min, well inside the 60/min free tier rate limit.

#### `cal_ipo_events` + `cal_ipo_event_revisions`

```
ipo_id             bigserial primary key
symbol             text                            -- can be null pre-listing
name               text not null
ipo_date           date not null
exchange           text                            -- ~56% null pre-priced
status             varchar(12) not null check (status in ('priced','filed','expected','withdrawn'))
number_of_shares   bigint
price              numeric                         -- can be range; we store midpoint or null
total_shares_value numeric
fingerprint        text not null                   -- sha256(name|ipo_date) since symbol can be null
fetched_at         timestamptz not null default now()
updated_at         timestamptz not null default now()
unique (fingerprint)
```

Revisions table mirrors the same shape (first-insert-baseline + observed-state semantics + `source_payload jsonb`). Tracked fields: `status`, `price`, `exchange`, `number_of_shares`, `total_shares_value`. `status` flipping (`expected`→`priced`/`withdrawn`) is the most common revision; `price` finalising and `exchange` populating come second.

#### `macro_series` (FRED metadata catalog)

```
series_id          text primary key                -- e.g. 'CPIAUCNS'
title              text not null
frequency          varchar(8) not null             -- 'd'/'w'/'bw'/'m'/'q'/'sa'/'a'
units              text not null                   -- 'Index 1982-1984=100' / 'Percent' / etc.
seasonal_adjustment text
last_updated       timestamptz                     -- offset-aware parse from FRED's '-05' format
revision_strategy  varchar(16) not null default 'latest_only'
                                                    -- 'latest_only' or 'full_vintages'
fetched_at         timestamptz not null default now()
updated_at         timestamptz not null default now()
```

`revision_strategy` is the per-series knob:

- `latest_only` (default): store only the current-vintage values + `first_release_date`; suitable for non-revising monthly series like CPIAUCNS, FEDFUNDS, UNRATE.
- `full_vintages`: store the full revision log via `vintage_dates`; required for GDP, BEA NIPA, payrolls — anything BLS/BEA actively revises.

Curated initial set in `config/macro_calendar_series.yaml` (file, not table — easier to review in PRs). _Note: file was renamed from `config/p1_2_macro_series.yaml` post-commit-3; runtime module lives in `src/macro_calendar/` rather than `src/p1_2/`._

#### `macro_observations` (FRED time series)

```
observation_id     bigserial primary key
series_id          text not null references macro_series(series_id) on delete cascade
observation_date   date not null                   -- 'date' field from FRED
value              numeric                         -- nullable (FRED returns '.' for missing)
realtime_start     date not null                   -- no default; ingestion error if unknown
realtime_end       date not null default '9999-12-31'
fetched_at         timestamptz not null default now()
unique (series_id, observation_date, realtime_start)
```

Index: `(series_id, observation_date desc)`, `(series_id, realtime_start desc)`.

`realtime_start` is **NOT NULL with no fallback sentinel**. Lookahead-safety is the core contract of P1.2; an unknown `realtime_start` would mean we don't know when this value was knowable — that's not a writable observation. For `latest_only` series, `realtime_start` is FRED's authoritative **first-publication date**, obtained by requesting `output_type=4` (Initial Release Only) over the full ALFRED real-time window — **not** derived from a `macro_release_dates` join. _(Corrected 2026-06-25: the original release-date-join design leaked values early — a within-month release of a different period pre-dated the new observation; see `_ingest_latest_only`'s docstring. The implementation switched to FRED `output_type=4`.)_ If FRED returns no real-time row, ingestion skips it rather than writing `'1970-01-01'` and pretending it's queryable.

For `latest_only` series, one row exists per `(series_id, observation_date)` with `realtime_start` = FRED's first-publication date (output_type=4) and `realtime_end = '9999-12-31'`.

For `full_vintages` series, multiple rows can exist per `(series_id, observation_date)` covering each revision; lookahead-safe query is:

```sql
SELECT value FROM macro_observations
WHERE series_id = $1 AND observation_date = $2
  AND realtime_start <= $3 AND realtime_end > $3
LIMIT 1
```

`$3` is the caller's `as_of` cast to `date` (FRED's vintage axis is day-precision).

#### `macro_release_dates` (FRED release schedule)

```
release_id         int not null
release_name       text not null
release_date       date not null
fetched_at         timestamptz not null default now()
primary key (release_id, release_date)
```

Populates the release-schedule surface (the calendar of scheduled / actual source releases). **NOTE (2026-06-25):** observation `realtime_start` is **not** derived from this table — it comes from FRED `output_type=4` (first publication). The release schedule is informational; it is no longer joined to date observations.

### 3.3 Snapshot semantics — single rule

For every mutating row (`cal_*_events.actual` etc.), each ingestion run does:

1. **First time we see a fingerprint**: insert canonical row + append one initial-baseline revision row carrying the same observed state. Without this baseline, an as-of query targeted before any later mutation has no row to find.
2. **Subsequent observation**: if any tracked field differs from the canonical row, append one revision row carrying the **current observed state** (not the previous state) at `observed_at = now()`, and overwrite the canonical row with the new state.
3. **Read** with `as_of` returns the most recent revision row whose `observed_at <= as_of`. Reads without `as_of` return the canonical row directly.

This applies uniformly across economic events, earnings, IPO. FRED has its own native vintage mechanism — no separate revision log needed.

### 3.4 Timezone discipline

- Every timestamp column is `TIMESTAMPTZ`. Every input parsed with explicit timezone.
- Finnhub `time` strings (`"YYYY-MM-DD HH:MM:SS"` no tz) are parsed as UTC (smoke §5.2).
- FRED `last_updated` strings (`"2026-04-10 08:08:04-05"`) are parsed offset-aware via `dateutil.parser.parse` or psycopg2 native; never `datetime.fromisoformat`.
- Date-only fields (FRED `observation_date`, FRED `release_date`, Finnhub `date` for earnings/IPO) stay `DATE`.

---

## 4. Ingestion jobs

All jobs go through the existing P0.2 `JobRunsStore`. Each job records start, finish, status, message, payload, result via `record_completed_run` or `create_run`/`finish_run` so /jobs/status and /jobs/history surface them uniformly.

| Job name | Source | Cadence | Default window | Override params |
|---|---|---|---|---|
| `fetch_economic_calendar_recent` | Finnhub | hourly | today − 7d → today + 14d | `from_date`, `to_date` |
| `fetch_economic_calendar_backfill` | Finnhub | one-shot per range | today − 1y → today | `from_date`, `to_date`, `years_back` |
| `fetch_earnings_calendar` | Finnhub | every 4h | today → today + 30d | `from_date`, `to_date`, `symbols` |
| `fetch_ipo_calendar` | Finnhub | daily | today − 30d → today + 90d | `from_date`, `to_date` |
| `fetch_fred_series` | FRED | daily | (catalog-defined per series) | `series_ids`, `full_refresh` |
| `fetch_fred_release_dates` | FRED | weekly | (catalog-defined per release_id) | `release_ids`, `limit` |

**Implementation notes (2026-04-27)**:

- `fetch_earnings_calendar` was originally specced as
  `fetch_earnings_calendar_watchlist`; the suffix was dropped because the
  watchlist is now the *default* selection but `symbols` is a documented
  override. The job is still per-symbol — unfiltered queries under-sample
  the universe (smoke §5.5). When the watchlist is empty and no `symbols`
  param is given, the job falls back to a single unfiltered call.
- The earnings default window is forward-only (today → today+30d) because
  Finnhub's free tier never populates `epsActual`/`revenueActual` (smoke
  §5.1); a backward window for "actual flip" capture would be wasted on
  this tier. Re-evaluate if/when we move to a paid tier.
- `fetch_economic_calendar_recent` uses today − 7d (not today − 1d as the
  earlier draft proposed) because Finnhub's economic `actual` does flip
  null → value post-release and we want to catch it even if the cron
  misses a few hours. 14d forward keeps the upcoming-event window.
- `fetch_ipo_calendar` extends to +90d (vs the earlier +60d draft) for
  more upcoming-pipeline visibility; status revisions are captured in
  the same revision-log shape.
- All four Finnhub jobs and the two FRED jobs are gated on
  `macro_calendar.enabled` in `config/user_profile.yaml`. When disabled,
  they remain visible in `/jobs/status` with `enabled=false` and an
  `availability_reason` ("Enable macro_calendar.enabled to expose this
  job.") — the UI can render the disabled tile and explain how to turn
  it on, instead of having jobs silently disappear from the catalog.
  `/jobs/run/{name}` returns 503 with the same reason while the flag is off.

### 4.1 Mutating-row contract

Every ingestion job that touches `cal_*` tables follows the same loop:

```python
for row in fetched_rows:
    fingerprint = sha256_of(row)
    existing = dal.get_event_by_fingerprint(fingerprint)
    if existing is None:
        new = dal.insert_event(row)
        # Initial baseline: as-of queries before any mutation must find a row.
        dal.append_revision(new.id, observed_state=row, source_payload=row.raw)
    elif row_differs_from(existing, row, tracked_fields):
        dal.update_event(existing.id, new_state=row)
        dal.append_revision(existing.id, observed_state=row, source_payload=row.raw)
```

`tracked_fields` is per-table (economic events track `actual`/`estimate`/`prev`; earnings track `eps_estimate`/`eps_actual`/`revenue_estimate`/`revenue_actual`/`hour`; IPO track `status`/`price`/`exchange`/`number_of_shares`/`total_shares_value`).

Note: `observed_state=row` (NOT `prior_state=existing`). The revision row records what we observed AT `observed_at`, which is exactly what the as-of query in §3.2 expects. Storing prior state would invert the time semantic.

### 4.2 Rate-limit budgets

- Finnhub: 60 calls/min. Watchlist earnings ingestion = 50 calls per run; one run every 4h is fine.
- FRED: 2 req/s. Backfill of 10 series × 5 years monthly = 50 series-fetches; comfortable in batches.

### 4.3 Failure handling

Each job is best-effort and idempotent (fingerprint upsert). DB outage / API outage logs `failed` to `job_runs` and exits non-zero. Rate-limit (HTTP 429) triggers exponential backoff up to 3 attempts then fail.

---

## 5. Freshness / health telemetry

Mirrors P0.4's `/sa/market-news/health` shape. New module `src/service/macro_calendar_health.py`, new endpoint `GET /macro/health`.

Layers (per source):

- **freshness**: `last_successful_run_at` per ingestion job, age in seconds. Severity: warning > 6h, critical > 24h on any job.
- **coverage**: rows in last 24h / 7d per table. Zero for 24h is warning; zero for 7d is critical.
- **revisions**: revisions appended in last 24h. Zero for an active calendar window is warning (suggests `actual` flips aren't being captured).
- **fred_lag**: max(`now() - last_updated`) across `latest_only` series. Severity per-series via `macro_series.frequency` (daily series stale > 2 days = warning; monthly stale > 45 days = warning).

`?strict=true` returns 503 if severity != ok, same convention as P0.4.

---

## 6. Read-only API + agent tools

### 6.1 API endpoints

All under existing FastAPI router pattern. Spec uses `/macro` (new prefix) since `/calendar` is too generic and might collide with future ad-hoc routes.

```
GET  /macro/economic-calendar?from=&to=&country=&impact=&as_of=
GET  /macro/economic-calendar/{event_id}/revisions
GET  /macro/earnings-calendar?from=&to=&ticker=&as_of=
GET  /macro/earnings-calendar/{symbol}/{year}/{quarter}/revisions
GET  /macro/ipo-calendar?from=&to=&status=&exchange=&as_of=
GET  /macro/series/{series_id}?start=&end=&as_of=
GET  /macro/series/{series_id}/metadata
GET  /macro/release-dates/{release_id}
GET  /macro/health
```

`as_of` is the lookahead-safe replay knob on every endpoint that touches mutating data.

- **Type**: ISO 8601 string. Accepts either a date (`YYYY-MM-DD`) or a full timestamp (`YYYY-MM-DDTHH:MM:SSZ` / `YYYY-MM-DDTHH:MM:SS+00:00`).
- **Date inputs** are interpreted as **end-of-day UTC** (`date + 23:59:59.999Z`) so a calling convention of "as-of business close on day D" works naturally without forcing every caller to pick a time.
- **Timestamp inputs** are honoured at second precision, which is what the §8 acceptance test for "1 minute before `event_time`" needs.
- **Default**: `now()` (latest known state — same as querying the canonical row).
- **422** on unparseable values; never silently coerce.

The 422 contract matters because intraday tests will pass `event_time − 1m` strings; if we silently truncated to date the test would pass for the wrong reason.

### 6.2 Agent tools

```
get_economic_calendar(start, end, country=None, impact=None, as_of=None)
get_earnings_for_ticker(ticker, start=None, end=None, as_of=None)
get_ipo_calendar(start, end, status=None, as_of=None)
get_macro_value(series_id, as_of=None, start=None, end=None)
```

Tools accept the same ISO 8601 (date or timestamp) form as the API endpoints; tool docstrings explicitly list both forms so agents can pick whichever fits the question.

Same shape as P1.1 — each tool returns a `data_quality` block (rows, errors, missing fields) so agents never confuse "no data" with "neutral".

---

## 7. Lookahead-bias safety contract

Three rules, all enforced by the read layer. No backtest code in P1.2 — but the read layer is the foundation any future backtest will use, so getting these right matters.

1. **Mutating-row reads** (`cal_*_events`): when `as_of` is supplied, the read joins to `cal_*_event_revisions` and returns the state observed at the most recent `observed_at <= as_of`. When no `as_of`, returns the canonical (latest) row.
2. **FRED observation reads**: `as_of` filters `realtime_start <= as_of::date < realtime_end`. For `latest_only` series this collapses to `first_publication_date <= as_of::date`. For `full_vintages` series this picks the right vintage. (FRED's vintage axis is day-precision; timestamp inputs are cast to date for this filter.)
3. **Release schedule**: a release_date is a **scheduled or actual source release**, not FRED/ALFRED ingestion availability (smoke §1.5). Lookahead-safe queries that need "data was knowable at decision time" use `realtime_start`, not a derived `decision_date >= release_date`.

---

## 8. Acceptance criteria for v1

Listed by area; each is a thing a reviewer can check.

**Schema + store**

- Migration `sql/013_add_p1_2_macro_calendar.sql` applies cleanly. Down-migration drops all P1.2 tables in reverse order.
- DAL helpers exist for canonical upsert + revision append on each `cal_*` table.
- Snapshot test: a mutating-row update creates exactly one revision row.

**Ingestion**

- Watchlist earnings ingestion completes for 50 tickers in < 60 seconds (per-symbol queries).
- Economic-calendar ingestion captures `actual` flipping null → value when re-run after a release; revision log shows the transition.
- FRED `latest_only` series stores `realtime_start` = FRED's first-publication date (output_type=4).
- FRED `full_vintages` series for GDP returns multiple rows per `observation_date` after backfill.

**Health**

- `/macro/health` returns `severity = ok` when all jobs ran in the last 6h and coverage is non-zero.
- Killing one ingestion job for 7h moves that job's `freshness` to `warning`.
- `?strict=true` returns 503 in that warning state.

**Read API + tools**

- `/macro/economic-calendar?from=2024-01-01&to=2024-01-31&country=US&impact=high&as_of=2024-01-15` returns rows with state as observed by end-of-day UTC 2024-01-15 (no `actual` for events after that date).
- `/macro/series/CPIAUCNS?as_of=2025-01-15` returns observations through 2024-12-01 (smoke-confirmed vintage replay).
- `get_economic_calendar` / `get_macro_value` tools registered in registry + Anthropic + OpenAI bridges with bumped count assertions.

**Lookahead safety**

- Test: query an event 1 minute before its `event_time` with `as_of = event_time − 1m` (timestamp input) returns `actual = null`.
- Test: query the same event after its release with the same `as_of` still returns `actual = null` (revision log respected — what the system knew at as_of, not what the world had).
- Test: `as_of = "2024-01-15"` (date input) is interpreted as end-of-day UTC; an event with `observed_at = 2024-01-15 23:59:00Z` is included, an event with `observed_at = 2024-01-16 00:00:01Z` is not.

---

## 9. Implementation order

Six commits. Each commit is reviewable independently; later commits depend only on earlier ones landing.

1. **Schema + DAL** (no ingestion, no API). Migration `sql/013_add_p1_2_macro_calendar.sql` + DAL helpers in `src/macro_calendar/store.py` + snapshot-revision unit tests. Smallest commit; gates everything else. _(landed `e8fc1db`, `926a81c`)_
2. **FRED ingestion** + curated series catalog YAML (`config/macro_calendar_series.yaml`) + `fetch_fred_series` job + `fetch_fred_release_dates` job + tests against captured fixtures. _(landed `f03cf86`, `6536652`, `959c589`)_
3. **Finnhub calendar ingestion** — all three callable functions (`fetch_finnhub_economic_events` / `_earnings_events` / `_ipo_events`) + client + parser unit tests. No job wiring yet. _(landed `d3ec85a`)_
4. **Finnhub job wiring** — four `JobDefinition` entries (`fetch_economic_calendar_recent`, `_backfill`, `fetch_earnings_calendar`, `fetch_ipo_calendar`) + dispatcher arms + summary heuristics + feature-flag tests. Earnings dispatcher selects watchlist by default. _(landed `2edea5e`)_
5. **Health module + endpoint** mirroring P0.4 layout. _(pending)_
6. **Read API endpoints + agent tools** + bridge wiring + count-assertion bumps + integration tests using the fixtures from earlier commits. _(pending)_

> **Decomposition note**: the earlier draft of this section bundled commit-3 ingestion with the economic-calendar jobs and split the Finnhub work into "economic" (commit 3) and "earnings + IPO" (commit 4). Implementation rebalanced this so commit 3 ships pure ingestion logic and commit 4 ships pure job wiring — keeping each commit ≤ ~1.4 kloc with one clear concern.

Estimated total: ~5-7 days incremental, but each commit ships value (e.g. after commit 2 we have FRED CPI in our DB even if no API surfaces it yet).

---

## 10. Open questions / explicit deferrals

- **Curated FRED series list (v1)**: CPIAUCNS, CPILFESL (latest_only); FEDFUNDS, UNRATE (latest_only); GDP, GDPC1, PAYEMS (full_vintages — actively revised); DGS10, DGS2, T10Y2Y (latest_only); VIXCLS (latest_only). M2SL deferred until a concrete liquidity / money-supply hypothesis uses it. Catalog lives in `config/macro_calendar_series.yaml`; review before commit 2.
- **Watchlist source for earnings ingestion**: reuse `dal.get_watchlist().tickers` (same source as P1.1 factor-rank). No alpha_picks earnings ingestion in v1 — duplicate symbols + paid Alpha Picks can happen later.
- **Macro feature library** (CPI YoY, real FFR, regime detection): out of scope. P1.2 stores raw observations; derivative features are a later cycle.
- **Backtest integration**: out of scope. The lookahead-safe read layer is the contract; an actual backtest harness consumes it later.
- **Reddit / social**: explicitly excluded (per priority map P3.3).
- **Eq option calendar** (option expiries): not in P1.2; can extend the same model later.
- **Country whitelisting**: economic-calendar ingestion currently keeps all countries Finnhub returns (~140). Filtering at read time is fine; if storage cost matters, a country whitelist can be added later without a schema change.