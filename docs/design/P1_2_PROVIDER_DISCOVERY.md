# P1.2 Provider Discovery — FRED + Finnhub

> **Status: HISTORICAL RECORD** — provider smoke evidence behind P1.2 (shipped 2026-04-27).

> **Purpose**: Lock in what FRED and Finnhub actually provide on the free tier *before* writing the P1.2 spec. Schema, ingestion jobs, freshness telemetry, API/tool surfaces all depend on these constraints.
>
> **Scope**: pure research from official docs. **No spec, no code, no schema decisions yet** — only facts, gaps, and risks the next doc has to resolve.
>
> **Date**: 2026-04-26.
>
> **Status**: doc-only discovery; an API-key smoke test is still pending for two unknowns flagged below.

---

## 1. FRED (Federal Reserve Economic Data)

### 1.1 Auth + rate limit

- Free, requires API key registration.
- **Rate limit: 2 requests/second** before HTTP 429. No documented monthly cap. Persistent throttling violations can trigger temporary blocks.
- API root: `https://api.stlouisfed.org/fred/`. Responses default XML; `&file_type=json` for JSON.

### 1.2 Endpoints we care about for P1.2

| Endpoint | What it returns |
|---|---|
| `/fred/series/observations` | Time series values for one series ID (e.g. CPIAUCNS, GDP, FEDFUNDS). |
| `/fred/series` | Series metadata (frequency, units, last update). |
| `/fred/series/updates` | Series whose data changed in a window — useful for incremental sync. |
| `/fred/releases` + `/fred/release/dates` | Release metadata + scheduled release calendar (e.g. when next CPI prints). |
| `/fred/categories`, `/fred/category/series` | Browse series by category. Useful one-time for series picks; not a live ingestion endpoint. |

### 1.3 Data semantics

- **Frequency**: `d` daily, `w` weekly, `bw` biweekly, `m` monthly, `q` quarterly, `sa` semiannual, `a` annual. Caller can request aggregation to a *lower* frequency than native; cannot upsample.
- **Units**: per-series (Index 1982=100, Billions of Dollars, %, etc.). Stored on series metadata, not on each observation. Must be persisted alongside values.
- **Observation date**: the date the value *refers to* (e.g. `2026-03-01` for March 2026 CPI). **Not** the release date — for that you need releases endpoints (or ALFRED, below).

### 1.4 ALFRED — point-in-time / vintages

This is the part that closes the lookahead-bias hole. ALFRED is a *separate frontend* but the **same `/fred/series/observations` endpoint** exposes vintages via two parameters:

- `realtime_start` / `realtime_end` (YYYY-MM-DD): "what was the value on this date?" Defaults to *today* — i.e. the latest revision. To replay history without lookahead bias, set both to the historical decision date.
- `vintage_dates`: comma-separated list of explicit vintage dates to retrieve.

For each observation row the response carries `realtime_start` and `realtime_end` so callers can see the exact window over which that value was the published version.

**Implication for our store**: a FRED row needs `series_id`, `observation_date`, `value`, `realtime_start`, `realtime_end`. Storing only `(date, value)` and inferring "this was the value at decision time" silently introduces revision bleed.

### 1.5 Lookahead risks specific to FRED

- **Initial release vs revisions**: macro series get revised. CPI for March prints on ~April 10, then revised again later. Storing only the latest value means a backtest "knows" April-revised CPI in March.
- **Observation date is not release date**: a March CPI observation has `observation_date=2026-03-01` but doesn't print until ~April 10. Naïve "get values where date ≤ today" exposes future data. Mitigations:
  - prefer `realtime_*` parameters, or
  - join to a release schedule from `/fred/release/dates` to compute the earliest-known date, or
  - apply a series-specific publication lag (more brittle).
- **Release date is not the same as FRED/ALFRED availability**: the FRED docs are explicit that release dates are "scheduled or actual dates when data is released by the *source*"; FRED/ALFRED ingestion can lag the source release by an unspecified interval. So `release_date` is an **upper bound** on lookahead safety (data is *not* knowable before that), not a lower bound on knowability. A lookahead-safe query must use `realtime_start ≥ release_date` (or `realtime_*` directly), not `decision_date ≥ release_date`. This nuance has to flow into whatever store strategy §4.2 picks.

### 1.6 Open questions

1. Do we need vintage replay on day 1, or is "today's revision + a release-lag column" enough for the first cut? Vintages roughly 10× the storage cost.
2. Do we want an offline series catalog (curated list of FRED series IDs we care about — CPI, FFR, unemployment, GDP, ISM, etc.) or a runtime-discoverable one via `/fred/categories`?

---

## 2. Finnhub

### 2.1 Auth + rate limit

- Free tier. Requires API key.
- **Rate limit: 60 calls/minute, internal cap 30 calls/second** across all endpoints on the free plan.
- Responses are JSON.

### 2.2 Endpoints we care about for P1.2

| Endpoint | Free tier? | Notes |
|---|---|---|
| `/calendar/earnings?from=&to=&symbol=` | ⚠️ **upcoming-only on free tier** | Free-tier returns recent/upcoming with `epsEstimate` + `revenueEstimate` + `hour`; `epsActual`/`revenueActual` never observed populated on free tier; historical date windows return 0 rows. The "lookback to 2003" public claim does **not** apply on free tier. See §5.1 for smoke evidence. |
| `/calendar/economic?from=&to=` | ✅ **free tier** | Smoke-confirmed: free tier returns BOTH upcoming AND historical economic events with `actual` / `estimate` / `prev` populated. Earlier "Enterprise gating" claim from public sources is wrong — see §5.2. |
| `/calendar/ipo?from=&to=` | ✅ | Full 4-state `status` enum (priced/filed/expected/withdrawn) confirmed via smoke. ~56% of rows have null `exchange` (mostly pre-priced). |
| `/fda-advisory-committee-calendar` (no params) | ✅ | Smoke-confirmed live path. `/calendar/fda` returns empty `{}` and is dead. |

### 2.3 Earnings calendar — schema

Confirmed fields per row:

- `symbol`, `date`, `year`, `quarter`
- `epsActual`, `epsEstimate`
- `revenueActual`, `revenueEstimate`
- `hour` ∈ `{bmo, amc, dmh}` — before market open / after market close / during market hours

**Lookahead-bias notes**:

- `epsActual` / `revenueActual` are populated *after* the earnings release. If we sync the day-of, the row may flip from `null` actual → real actual mid-day. Need an ingestion model that captures both states and is honest about which row is "before close" vs "after close".
- `hour` is the right precision for intraday gating; we don't get a real release timestamp.
- No estimate-revision history. We see the consensus snapshot at fetch time only.

**Range limits**: caller must pass `from` and `to`. Largest single-call window is undocumented in search results — to be confirmed via smoke call.

### 2.4 Economic calendar — schema (smoke-confirmed)

> The original draft of this section parroted the public claim that historical events + surprises are gated to Enterprise. **Smoke testing in §5.2 disproved that** — the free tier returns historical and upcoming, with `actual` / `estimate` / `prev` populated. The block below describes the actual surface.

Free-tier returns:

- **upcoming** events (`actual = null`)
- **historical** events with `actual` populated (verified back to at least 2024-01-01; further floor not probed)
- mutating row: `actual` flips null → value at release, so snapshot semantics still matter

Fields commonly listed: event name, country, time, impact, unit, currency, plus `actual`, `estimate`, `previous`. **Whether `actual` is present on free tier — and whether the timestamp is intraday or day-only — is the most important thing to confirm with a smoke call.** If `actual` is gated, our economic-calendar ingestion is an "upcoming events only" surface, and historical macro lookups have to fall back to FRED.

### 2.5 IPO calendar — schema

Confirmed fields:

- `date`, `exchange`, `name`, `symbol`
- `numberOfShares`, `price` (range or projected), `totalSharesValue`
- `status` ∈ `{expected, priced, withdrawn, filed}`

Status enum is critical for backtesting: a row that was `expected` on day T and later flipped to `withdrawn` looked like a real upcoming IPO at the time. We need to capture **status as observed, with the observation timestamp**, not the latest status.

### 2.6 Timezone semantics — UNKNOWN

None of the search results state what timezone Finnhub uses for the `time` field on economic-calendar rows or for `date` on earnings rows. UTC and US/Eastern are both plausible. **This is the second blocker for the spec** — must be confirmed with a smoke call against a known event (e.g. FOMC announcement at 14:00 ET) before we lock the schema.

### 2.7 Lookahead risks specific to Finnhub

- `epsActual` / `revenueActual` mutate from null → value as a release happens. Snapshot semantics matter.
- IPO `status` mutates over the company's pre-listing lifecycle.
- Economic calendar `actual` likely populated post-release; if we ingest a row before and after release we should preserve both versions.
- No vintage / point-in-time mechanism. We must do our own append-only history.

---

## 3. Cross-cutting findings

### 3.1 Timestamp precision

| Source | Field | Precision | Lookahead-safe? |
|---|---|---|---|
| FRED observations | `date` | day | No — release lags exist; combine with releases endpoint or vintages. |
| FRED releases | `date` | day | Day-level; no time-of-day. |
| Finnhub earnings | `date` + `hour` | day + BMO/AMC/dmh enum | Conservative day-level + intraday gating via `hour`. |
| Finnhub economic | `time` | unknown — possibly minute, possibly day | TBD via smoke call. |
| Finnhub IPO | `date` | day | Day-level. |

### 3.2 actual/estimate/previous

| Source | actual | estimate | previous |
|---|---|---|---|
| FRED | n/a (revisions instead) | n/a | n/a — concept doesn't apply |
| Finnhub earnings | ✅ post-release | ✅ snapshot | n/a (consensus only) |
| Finnhub economic | ⚠️ likely free, gating to confirm | ⚠️ likely free | ⚠️ likely free |

### 3.3 Point-in-time fidelity

- **FRED**: yes, via ALFRED `realtime_*` / `vintage_dates`. Native, well-documented.
- **Finnhub**: no native vintages. Must roll our own append-only log if backtesting requires it.

### 3.4 Free-tier viability summary

- **FRED**: viable for macro **time-series values** + vintage replay (ALFRED). 2 req/s is plenty for batched ingestion. Use for the actual numbers (CPI value, GDP, FFR) and revision-aware backtest features — **not** as an economic-event calendar.
- **Finnhub economic calendar**: viable as the unified event-calendar source on free tier — both upcoming and historical, with `actual` / `estimate` / `prev` populated. UTC-stamped.
- **Finnhub earnings**: free-tier covers upcoming with estimates + `hour`; `epsActual` is never observed populated on free tier and historical date windows return empty. To capture surprises P1.2 must snapshot rows around release time, not query past dates.
- **Finnhub IPO**: viable for the full P1.2 IPO calendar surface.

The right division is **Finnhub for events, FRED for values** — not Finnhub for future / FRED for past. They cover different shapes.

---

## 4. Risks the P1.2 spec has to resolve

### 4.1 Sources for events vs values (settled by smoke)

The original draft considered a Finnhub-future / FRED-historical split because we believed Finnhub free-tier had no historical events. Smoke proved otherwise. The shape of the split is now:

- **Finnhub `/calendar/economic`** → unified economic-event store (both upcoming and historical, UTC-stamped, `actual`/`estimate`/`prev` populated). One ingestion job, one table, snapshot-aware so the row's `actual` flipping null → value at release is captured.
- **FRED `/series/observations`** → macro **time-series values** (CPI numbers, GDP, FFR, unemployment) + revision history via ALFRED. NOT an event-calendar replacement.

For backtests that need to reason about an event AND the macro number that printed, the read tool joins the two on `(country, event_name, date)` where applicable; FRED is the source of truth for the value, Finnhub for the event metadata.

### 4.2 Vintage / point-in-time strategy

Three options, increasing fidelity:

- **A. Latest-only + release_lag column** (cheapest). Each row stores latest value + a series-level lag. Backtest queries filter by `decision_date ≥ observation_date + release_lag`.
- **B. ALFRED-anchored vintages for FRED, append-only log for Finnhub** (medium). Faithful to FRED's model; costs ~10× storage on the FRED side but matches the source-of-truth.
- **C. Full append-only log for both** (highest fidelity, highest cost).

Pick this *before* the schema, not after.

### 4.3 Snapshot semantics for mutating rows

`epsActual` flipping null → value, IPO `status` flipping `expected` → `priced`/`withdrawn`, economic `actual` arriving post-release — all need a clear answer:

- Do we overwrite (latest-state only)?
- Do we append a new row each time we observe a change (full history)?
- Do we keep a hybrid (latest in canonical row + revision log)?

This is a one-decision-many-tables choice; the spec needs it locked.

### 4.4 Timezone

Until the smoke call confirms Finnhub's `time` field timezone, do not write the SQL `TIMESTAMPTZ` columns. Worst case is silently storing local Europe/Lisbon time as UTC.

---

## 5. Smoke-call results — Finnhub (run 2026-04-26)

Three rounds against the free-tier key already in `config/.env`. Token redacted from all logs. Probes targeted gaps from §4.4 and the open questions above.

### 5.1 Earnings calendar

| Window | Rows | with epsEstimate | with hour | with epsActual |
|---|---:|---:|---:|---:|
| 2026-04-19 (1d, week-old) | 1 | 0 | 0 | 0 |
| 2026-04-25 (yesterday) | 0 | — | — | — |
| 2026-04-26 (today) | 1 | 1 | 1 | 0 |
| 2026-04-27 to 04-30 (next 4d) | 932 | 760 | 654 | 0 |
| 2026-05-01 to 05-10 (next 10d) | 1,500 | 1,266 | 404 | 0 |
| 2026-02-22 to 02-28 (NVDA Q4 release) | 0 | — | — | — |
| 2015 / 2020 / 2003 lookbacks | 0 | — | — | — |
| `symbol=AAPL`, 2026-04-19 to 05-10 | 1 (AAPL @ 2026-04-30, hour=amc, epsEstimate=1.9801) | 1 | 1 | 0 |

**Confirmed**:

- Schema: `date`, `symbol`, `year`, `quarter`, `epsEstimate`, `epsActual`, `revenueEstimate`, `revenueActual`, `hour`.
- `hour` values seen: `bmo`, `amc`, empty string. `dmh` documented but not observed in this sample.
- Symbol filter works exactly. Critical surprise: **unfiltered query is capped/sampled and may NOT include a symbol whose row the symbol-filtered query returns** — AAPL appeared with `symbol=AAPL` but was absent from the unfiltered query over the same date range. For watchlist coverage we must per-symbol query.
- Free tier returns **upcoming** earnings with estimates + hour populated.

**Confirmed gated / missing**:

- `epsActual` / `revenueActual` were `null` on every row, including yesterday and last week. We never saw a populated actual on free tier in this run.
- All historical windows returned 0 rows: 2015, 2020, 2003-2024-02. The "lookback to 2003" claim from public sources does **not** apply on free tier.
- Implication: cannot retrieve historical earnings surprises via this endpoint on free tier. To track surprises P1.2 must snapshot rows around release time (before-release with estimate + after-release re-poll), since past rows aren't replayable.

### 5.2 Economic calendar

| Window | Rows | actual populated | timezone evidence |
|---|---:|:---|---|
| 2026-04-20 to 04-26 (recent week) | 404 | yes (e.g. CN Loan Prime Rate 1Y, actual=3) | row time `01:15:00` for CN morning event |
| 2024-01-01 to 01-08 (historical) | 642 | yes (KR Balance of Trade actual=4.48, prev=3.78) | — |
| 2024-12-17 to 12-19 (Dec 2024 FOMC) | (US subset 77) | yes | **Fed Interest Rate Decision @ `2024-12-18 19:00:00`** = 14:00 ET → confirms **UTC** |

**Confirmed**:

- Schema: `actual`, `country`, `estimate`, `event`, `impact`, `prev`, `time`, `unit`. `time` format `"YYYY-MM-DD HH:MM:SS"` no tz suffix.
- **Timezone = UTC** (FOMC at 19:00 = 14:00 ET; Philadelphia Fed Manufacturing also at 13:30 UTC = 8:30 ET on the same release day cross-checks).
- Historical actuals + estimates + prev **are** available on free tier. A single Finnhub-backed economic-calendar ingestion covers both upcoming and historical events; no Finnhub-future / FRED-historical split is required.
- `actual` is `null` for upcoming events and populated for completed ones; the row mutates from null → value at release. Snapshot strategy from §4.3 still required.

**Other**:

- `country` codes are 2-letter ISO (e.g. `US`, `CN`, `KR`, `MD`, `BY`).
- `impact` ∈ low/medium/high.
- `unit` can be empty string (holidays / observances) or e.g. `%`, `$`.

### 5.3 IPO calendar

Range 2026-01-01 to 2026-04-26: 200 rows.

- Status histogram: **priced 84, filed 94, expected 4, withdrawn 18** — full 4-state enum confirmed.
- Exchange histogram: NASDAQ Global 42, NYSE 20, NASDAQ Global Select 12, NASDAQ Capital 11, NYSE MKT 3, **null 112**. About 56% of rows (mostly pre-priced) have `exchange = null`.
- 200-row count for ~4 months is suspect — possibly capped — but small for our use case so unlikely to bite.

### 5.4 FDA endpoint

- `/calendar/fda?from=&to=` returns HTTP 200 with empty `{}` payload — **endpoint dead or wrong path**.
- `/fda-advisory-committee-calendar` (no params) returns a list of 582 events with `fromDate`, `toDate`, `eventDescription`, `url`. **This is the live path** and confirms the finnhub-python 2.4.24 client mapping.
- Not on the P1.2 critical path; recorded so a future spec can reference the right URL.

### 5.5 Updated risk picture for the spec

- **Economic-calendar source (§4.1)**: a single Finnhub-backed ingestion serves both upcoming and historical events. FRED is the source of truth for macro **values** (CPI numbers, GDP) + revisions / point-in-time, not for the event calendar itself.
- **§4.3 Snapshot semantics**: confirmed mandatory for both economic (`actual` flips null → value at release) and earnings (`epsActual` flips at release; though on free tier we never observed a populated actual, so for earnings on this tier the value is "estimate now, never see actual unless we re-poll within the recent window before the row vanishes").
- **§4.4 Timezone**: economic-calendar `time` is **UTC**. Earnings `date` is day-only (no time field; intraday gating uses `hour` enum). IPO `date` is day-only.
- New finding: **earnings unfiltered query under-samples the universe**. P1.2 ingestion can't rely on a single date-range pull to cover a watchlist; per-symbol queries are required for completeness. Rate budget = 60/min, so a 50-symbol watchlist in one pass is fine.

## 6. Smoke-call results — FRED (run 2026-04-26)

API key registered at <https://fred.stlouisfed.org/docs/api/api_key.html> and added to `config/.env`. Token redacted from all logs.

### 6.1 Endpoint behaviour

| Probe | Result |
|---|---|
| `/series/observations?series_id=CPIAUCNS&limit=3&sort_order=desc` | HTTP 200. count=1359. Latest obs `2026-03-01 = 330.213` with `realtime_start=realtime_end=2026-04-26`. Default vintage = today. |
| `/series?series_id=CPIAUCNS` | freq=Monthly, units="Index 1982-1984=100", last_updated="2026-04-10 08:08:04-05" (carries CST/EST offset — parsing must respect it). |
| `/series/observations?series_id=CPIAUCNS&realtime_start=2025-01-15&realtime_end=2025-01-15` | HTTP 200. Latest obs as-of 2025-01-15 = `2024-12-01 = 315.605`. **Vintage replay works** — January-15-2025 only knew through December 2024 CPI. |
| `/series/observations?series_id=CPIAUCNS&observation_start=2024-03-01&observation_end=2024-03-01&vintage_dates=2024-04-10,2024-05-15,2026-04-26` | One row: `value=312.332, realtime_start=2024-04-10, realtime_end=2026-04-26`. Older CPI months are not revised after first release; the row's realtime window collapses to one tuple. |
| `/release/dates?release_id=10&limit=5&sort_order=desc` | HTTP 200. CPI publish dates: 2026-04-10, 2026-03-11, 2026-02-13, 2026-01-13, 2025-12-18. Day-level only (no hour). |
| `/releases?order_by=popularity` | HTTP 400 — `popularity` not a valid order_by here. Not blocking; we'll hardcode the small set of releases we actually care about. |
| Rate-limit poke (5 fast calls) | All HTTP 200. 2 req/s budget is comfortable for the macro series we'd ingest. |

### 6.2 Confirmed for the spec

- **Vintage replay is real and free.** The `realtime_start/end` parameters do exactly what ALFRED documents. `vintage_dates` collapses output to those specific snapshots. Either form is enough for lookahead-safe joins.
- **Older CPI observations are not revised.** This means the simplest schema (latest value + first-release date) is faithful for monthly macro series like CPI. For revision-heavy series (GDP, BEA NIPA tables) full vintages still matter — pick the strategy in §4.2 per series, not globally.
- **Release schedule is day-level.** Not enough for intraday gating; combine with Finnhub's UTC-stamped event row (which has the actual release time) when we want the full picture for the day of release.
- **`last_updated` carries a timezone offset** (`-05`), so SQL `TIMESTAMPTZ` ingestion needs `python-dateutil`-style parsing or psycopg2 native handling, not naive `datetime.fromisoformat`.

### 6.3 output_type behaviour (run 2026-04-27)

Spike against `GDP` for observation_date 2024-01-01 with full ALFRED window (`realtime_start=1776-07-04, realtime_end=9999-12-31`):

| `output_type` | rows returned | row shape | what it means |
|---|---:|---|---|
| 1 (default) | 5 | `{realtime_start, realtime_end, date, value}` per vintage | **By Real-Time Period** — one row per [start, end) window. The natural full-revision history. |
| 2           | 1 | wide: `{date, GDP_YYYYMMDD: value, ...}` for **every** publish snapshot (incl. unchanged) | **By Vintage Date — All**. Different shape; our parser doesn't handle it. |
| 3           | 1 | wide: `{date, GDP_YYYYMMDD: value, ...}` for **changed** values only | **New and Revised Only**. Same wide shape as 2; not what our parser expects. |
| 4           | 1 | `{realtime_start, realtime_end, date, value}` matching first publication | **Initial Release Only**. Exactly the latest_only semantic. |

Cross-check against `CPIAUCNS` 2024-03-01 with `output_type=4`: returns one row, `realtime_start=2024-04-10, value=312.332` — matches the expected first publication.

Ingestion implications now baked in:

- `latest_only` paths pass `output_type=4` so the response IS the first-publication row. No deduping logic required.
- `full_vintages` paths pass `output_type=1` (explicit, even though it's the default) so a future FRED change of default doesn't silently collapse our revision history. Each row is one [realtime_start, realtime_end) window — exactly the shape `macro_observations` expects.

Both shapes reuse the existing `_observation_from_json` parser; `output_type=2` / `=3` would require a separate wide-format parser and are intentionally NOT used.

### 6.4 Open / minor

- `/releases` `order_by` valid values to confirm if we ever need to walk the release catalog dynamically. Not on the P1.2 critical path; we'll seed a small curated `release_id` set.
- We didn't probe near a release boundary (e.g. CPI as-of `2026-04-09` vs `2026-04-10`) — would confirm that requesting before the publish date returns empty for that observation. Worth doing once during ingestion-job tests, not now.

## 7. Open action items before writing the P1.2 spec

1. ✅ ~~Reconcile priority map FRED-anonymous-quota wording.~~ Done in this same docs cleanup pass.
2. **Write P1.2 spec doc** answering §4.1-§4.4 with the smoke results in §5-§6, then break implementation into the order already approved: schema + store → ingestion jobs → freshness/health → API/tool read-only exposure.

---

## 8. Sources

### FRED

- API root + endpoint index: <https://fred.stlouisfed.org/docs/api/fred/>
- Series observations: <https://fred.stlouisfed.org/docs/api/fred/series_observations.html>
- Real-time periods (vintages): <https://fred.stlouisfed.org/docs/api/fred/realtime_period.html>
- ALFRED archive: <https://alfred.stlouisfed.org/> + <https://fred.stlouisfed.org/docs/api/fred/alfred.html>
- Errors / rate limit: <https://fred.stlouisfed.org/docs/api/fred/v2/errors.html>
- Series updates (for incremental sync): <https://fred.stlouisfed.org/docs/api/fred/series_updates.html>

### Finnhub

- Earnings calendar: <https://finnhub.io/docs/api/earnings-calendar>
- Economic calendar: <https://finnhub.io/docs/api/economic-calendar>
- IPO calendar: <https://finnhub.io/docs/api/ipo-calendar>
- Rate-limit page: <https://finnhub.io/docs/api/rate-limit>
- Pricing: <https://finnhub.io/pricing>