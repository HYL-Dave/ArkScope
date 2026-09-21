# Data Acquisition And Updates

Maintained policy and implementation map. Last reconciled with source: 2026-09-21.

This document owns the cross-source acquisition, update-trigger and freshness
contract. It distinguishes current behavior from approved follow-up work; dated
plans and test receipts are evidence, not the only place to discover the policy.
The [priority map](docs/design/PROJECT_PRIORITY_MAP.md) owns work sequencing;
source-specific specifications still own their detailed protocols.

## Core Rules

- Reuse suitable local observations for efficiency, not just to avoid charges.
  Local-first does not mean that every dataset can tolerate the same age.
- Keep provider, dataset, requested scope and observation time visible. A local
  copy from one provider is not proof that another provider has equivalent data.
- A successful request, a recent download and a new financial period are three
  different facts. None alone proves that all requested data is current.
- Users must be able to choose local-only reads, automatic acquisition when
  needed, or an explicit update where the source supports it. A browser capture
  cannot promise the latency or availability of a quote API.
- Refresh permission, paid admission and request limits remain independent.
  A freshness override does not authorize spending or bypass provider limits.
- An acquisition failure must not become a fresh empty result. Partial coverage
  must not be presented as complete. Reuse eligibility is not a deletion policy.

## Which Clock Means What?

| Concept | Meaning | Does not establish |
| --- | --- | --- |
| Period / observation date | What fiscal period, trading instant or event the value describes | When we retrieved it, or whether a later version exists |
| Source version | Provider identity plus filing/revision/snapshot identity where available | Immutability merely because `period_end` is unchanged |
| Publication / event date | When a release is expected or observed | When each provider finishes processing each statement |
| `fetched_at` | When the retained response was acquired | The newest available financial period or a quote's trade time |
| `checked_at` / last check | When a request checked a stated scope, even if nothing changed | New content, successful persistence or complete provider coverage |
| `evaluated_at` | When the consumer judged the observation | A new acquisition |
| Reuse window | Accepted acquisition age for a particular read | A quarterly publication schedule or a retention period |
| Schedule interval | When another collection attempt becomes due | Fresh data or successful previous collection |
| `next_check_at` | Intended absolute next availability-check time in the event-aware design | An implemented field shared by all current sources |

These are semantic distinctions, not a claim that every current response exposes
all these fields. Calendar receipts currently use `checked_at`; financial reuse
currently exposes `fetched_at` and `evaluated_at`. The event-aware decision record
is still follow-up work.

## Current Acquisition Behavior

| Data / entrypoint | Trigger and reuse today | Important limit |
| --- | --- | --- |
| Legacy financial analysis and detailed financials | On-demand `auto` reuses eligible local observations; otherwise acquire within source permissions. Financial Datasets is a separately governed fallback in fundamental analysis. | Age-based reuse, not a latest-period check. No explicit fiscal-period/version selector on these tools. |
| Earnings supplements in detailed financials | Separate shorter reuse window for Finnhub history/upcoming responses | Not the earnings-calendar scheduler interval, and not an earnings-reaction monitor |
| SEC research: `list_sec_filings`, `get_sec_financial_facts`, `read_sec_filing` | Default `stored`; explicit `auto` / `refresh` can download and persist with acquisition permission | Separate from the legacy SEC financial-analysis path above |
| General news | Opt-in source schedules, Run now, or the scoped `daily_update` wrapper; source-specific incremental collection | No universal query-triggered catch-up or interval-completeness guarantee |
| SA articles / comments | Signed-in browser extension captures into local storage; research reads retained captures | Body and comment outcomes are separate. A successful body does not prove comments loaded. |
| FRED and Finnhub calendars | Local reads plus explicit jobs or opt-in source schedules | A release calendar is not evidence that a financial provider has processed the release. |
| `get_current_quote` | `source=auto` tries an IBKR snapshot; `ibkr` requires that path; `local` reads stored bars | Snapshot, not streaming. Auto's local fallback is labeled historical, not live. |
| `get_portfolio_holdings` | Reads the local profile snapshot only | Does not sync IBKR or establish current account value |

### Financial Read Controls

`get_fundamentals_analysis` and `get_detailed_financials` accept `freshness` and
optional `max_age_seconds`:

| Mode | Behavior |
| --- | --- |
| `auto` (default) | Reuse a valid matching observation inside the selected window. Acquire only when needed and permitted. |
| `stored` | No provider acquisition or cache write. With no age bound, an older valid observation may be returned; a missing eligible observation is reported as a gap. |
| `refresh` | Bypass observations predating this request. An identical successful acquisition already in flight may satisfy it. Failure is not silently replaced by an older success. |

`max_age_seconds` must be a nonnegative integer, not a boolean or string. It
overrides the automatic defaults and can constrain `stored`; combining it with
`refresh` is rejected rather than silently ignored. These are tool controls,
not a claim that every Settings screen exposes them.

Current default authority is
[`config/user_profile.yaml`](config/user_profile.yaml), under
`data_preferences.fundamentals_sources`:

- `refresh_days`: **7 days** for financial observations.
- `earnings_refresh_seconds`: **3600 seconds** for detailed-financials earnings
  history/upcoming observations, unless an explicit age overrides it.

These are configurable fallbacks, not the final event-aware policy. A local read
does not restart the acquisition-age clock; a fresh provider response currently
does. Legacy `ttl_days` / `cache_days_*` storage metadata does not decide read
eligibility in this path. Merely choosing annual or quarterly data does not make
the response permanently valid: restatements and provider corrections can change
a period. Reopening an exact retained version and asking for the latest version
are different requests.

Results describe source observations with provider/dataset, retrieval mode,
`freshness_mode`, `fetched_at`, `evaluated_at`, age, selected maximum and persistence
outcome. The constant `latest_period_verified=false` field has been removed;
there is no implemented latest-period verifier behind these tools. Acquisition
reuse also does not certify the legacy financial formulas or period alignment.

Owners: [reuse policy](src/fundamentals/reuse.py),
[financial tools](src/tools/analysis_tools.py),
[FD client](data_sources/financial_datasets_client.py).

### SEC Research, Quotes And Browser Captures

SEC research's explicit `auto` mode uses a **24-hour** recency check for issuer
mapping and full refresh receipts, and retries pending receipt coverage. This is
an application policy, not an SEC publication guarantee. Already captured filing
documents may be reused without this age test. Pinned captures/fact selections
and continuation cursors remain local; `refresh` is invalid for those pinned
reads. See the [tool service](src/sec_research/tool_service.py) and
[SEC operations](docs/design/SEC_RESEARCH_OPERATIONS.md).

Quotes default to a **60-second** requested age tolerance. `market_data_type`,
`price_basis`, provider trade time and local receipt time remain separate.
Previous close and stored bars are historical; delayed/frozen feeds are not live.
When freshness cannot be established, `stale` is null, not false. Even a newly
received bid/ask midpoint does not prove a known price timestamp. These rules
do not admit a low-latency trading service. Owners:
[quote tool](src/tools/current_quote.py),
[local holdings tool](src/tools/portfolio_holdings_tools.py).

SA capture requires a usable signed-in browser and the relevant access. Article
body success with comment failure remains incomplete for a comments request.
There is no universal synchronous "refresh SA now" contract on research reads.
Larger scrolling budgets do not prove date coverage or list exhaustion. See the
[recent collection and Alpha Picks policy](docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md#alpha-picks-open-positions-first)
for the Open-position-first direction and its remaining implementation limits.

## Scheduled And Manual Collection

[`SOURCES`](src/service/data_scheduler.py) is the executable interval authority.
All ten data-source schedules default to **disabled**. Settings may override
`schedule.<source>.enabled` and `schedule.<source>.interval_minutes` independently;
manual execution does not require enabling the recurring schedule.

| Source ID | Default interval (minutes) |
| --- | --- |
| `sec_research_filings` | 1440 |
| `polygon_news` (Massive) | 60 |
| `finnhub_news` | 60 |
| `ibkr_news` | 120 |
| `ibkr_prices` | 60 |
| `fred_series` | 1440 |
| `fred_release_dates` | 10080 |
| `finnhub_economic_calendar` | 60 |
| `finnhub_earnings_calendar` | 240 |
| `finnhub_ipo_calendar` | 1440 |

The scheduler checks due work every 30 seconds. Due-ness uses the last attempt,
including failed terminal outcomes, so the interval also acts as retry backoff;
it is not a successful-data clock. Settings currently bounds intervals to 5
through 10080 minutes. Source locks, writer contention and Gateway availability
can defer or skip execution; the configured interval is not a completion SLA.
The source scheduler runs in the API sidecar. Independent unattended lifetime
after Desktop shutdown is not delivered by these scheduling controls.

Same-source overlap is skipped, not queued or returned as a shared task.
Financial acquisition has separate same-query coordination and rereads the saved
result after waiting. That does not implement scope-aware joining for all jobs.
Equivalent future catch-up requests must match provider, dataset, storage owner,
symbols, period/date range and completeness requirements; "the source ran" is
not enough. A failed or unsaved acquisition is not permission for every waiting
caller to retry automatically.

The shared first-news-fetch target is **14 calendar days per source/ticker**,
including newly added tickers. Existing cursors govern subsequent collection.
This target does not prove entitlement, returned coverage or completion: source
limits, pagination and interrupted work still matter. Do not invent a seven-day
free-tier ceiling from an empty result. See the
[news policy](docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md#news-a-recent-target-subject-to-real-access)
and [shared target](src/news_collection_policy.py) for implemented paths and gaps.

### Calendar Outcomes And Coverage

The default earnings-calendar request covers **today through 30 days ahead**,
using explicit symbols, otherwise the watchlist, otherwise an unfiltered request.
It cannot establish a date 70 or 90 days away. Economic recent collection uses
7 days back through 14 ahead; IPO uses 30 back through 90 ahead. These request
horizons are independent of both schedule cadence and financial reuse age.

Finnhub calendar jobs now preserve sanitized request receipts: dataset, symbol,
date range, `checked_at`, accepted/rejected row counts, response state and typed
failure. Response states distinguish `empty`, `data`, `partial`, `rejected` and
`failed`. Inserted, changed, unchanged and skipped counts describe storage work,
not the entire provider universe. Rows returned unchanged can be successful;
a valid empty window can also be successful. Malformed/error envelopes cannot
masquerade as empty data. Runs with completed storage work and errors are partial;
errors without completed storage work fail.

Corrected earnings dates are recorded as revisions. Historical reads use the date
from the selected revision, not today's canonical date. Missing historical date
evidence is unavailable, not fabricated. These repairs do not establish live
Finnhub coverage or provider statement readiness.

The old September 18 zero-row job lacks request/response evidence and was
API-triggered; its status alone cannot identify why the table remained empty.
Do not retroactively label it a failed schedule or rewrite its history. See the
[calendar repair receipt](docs/superpowers/evidence/2026-09-21-calendar-refresh-evidence/README.md).
Owners: [calendar client](data_sources/finnhub_calendar_client.py),
[job execution](src/macro_calendar/execution.py),
[revision store](src/macro_calendar/local_store.py).

## Event-Anchored Financial Updates: Approved Direction, Not Implemented

The next integration must replace the uniform-window decision where sufficient
evidence exists, without claiming that a calendar date alone proves freshness.
These are design requirements, not currently selectable states or configuration:

1. Identify the requested provider, statement set, financial periods and observed
   versions. Establish that the latest relevant released period is actually
   covered before treating a later event as a quiet-period boundary.
   Do not equate a calendar year/quarter with the company's fiscal period without
   matching evidence.
2. Keep the next expected publication/check as an **absolute time** with its
   evidence. Re-reading or fetching the same financial version updates check
   evidence, not the publication anchor. Calendar corrections can change it.
3. At an applicable release, or while a released statement is missing, check
   provider availability at bounded, authorized intervals. Income, balance and
   cash-flow statements may become available separately. An earnings calendar
   is only a hint; provider-specific readiness or actual new data is stronger
   evidence. No maximum processing delay is assumed.
4. Reuse the newly observed version when it satisfies the scope. Missing or
   ambiguous anchors use an explicit configurable fallback, currently the
   acquisition-age window. Keep unknown/pending coverage visible, respect paid
   refusal/backoff, and retain the user's ability to request a refresh.

For example, if a justified next check is at day 90, checking again on day 20
leaves **70 days**, not a new 90-day timer. A forced request returning the same
version must not move that anchor to day 110. But if the cache is already missing
the latest released quarter, a future day-90 event cannot justify waiting.
Likewise, a calendar with only 30 days of coverage cannot invent that anchor.

The future decision should record last check, data period/version, next check,
reason and evidence scope separately. Quiet-period financial reuse can avoid
repeated statement requests, but calendar/availability checks may still cost time
or money. Do not advertise 3-5 polls per event, 16-20 yearly requests or a savings
guarantee without measured usage, coverage and billing evidence.

Implementation boundary and acceptance owner:
[calendar and event-aware refresh plan](docs/superpowers/plans/2026-09-21-calendar-refresh-evidence.md).
The existing seven-day local-reuse behavior remains active until this separate
integration is implemented and verified. There is no automatic provider webhook
subscription or live latest-period probe in this policy.

## Cost, Access And Retention

Financial Datasets HTTP requires an enabled policy with positive
`daily_request_limit` and `requests_per_minute`, under
`data_preferences.paid_sources.financial_datasets`. Missing limits refuse new
requests; they do not prevent eligible local reads. The installation/key-scoped
[governor](data_sources/financial_datasets_governance.py) reserves attempts before
dispatch and does not refund failed/uncertain attempts. It enforces request counts,
not a verified dollar cap or the account's remaining credit balance. The legacy
`daily_budget_usd` preference is not an enforced spending limit. Separate machines
are not coordinated by this local ledger.

SEC research acquisition requires the configured identity, additive-write
permission and the shared [transport governor](data_sources/sec_transport.py). This protection
must not be attributed to every other provider: for example, Finnhub calendar
client spacing is per client, not a shared cross-process request governor.
Future external tools need independent operation/cost authorization; internal
`auto` or detailed audit logs do not grant it. No subscription upgrade, credential
switch or repeated billable probe is implicit in a refresh request.

Acquisition lookback, read reuse and retention are separate policies. The
14-day news bootstrap and seven-day financial reuse window authorize no deletion.
The user's approximately 90-day general-news retention preference still requires
inventory, protected-reference handling and a delete/export decision; there is
no general periodic purge implemented here. SA analysis/comments do not inherit
a general-news cutoff. Existing captures, citations and operational recovery
procedures retain their own protection requirements.

## Maintenance And Verification

Changes to triggers, defaults, scope matching, reuse eligibility, retry rules or
reported coverage must update this document in the same change. Keep current
behavior and planned behavior visibly separate, and link source/test owners
instead of treating an old implementation diary as current policy.

Current regression owners include
[local reuse](tests/test_financial_local_reuse.py),
[same-query concurrency](tests/test_financial_reuse_concurrency.py),
[paid admission](tests/test_financial_datasets_governance.py),
[calendar evidence](tests/test_calendar_refresh_evidence.py),
[macro outcomes](tests/test_macro_scheduler_outcomes.py),
[scheduler behavior](tests/test_data_scheduler.py),
[news initialization](tests/test_news_bootstrap_policy.py) and
[quote freshness](tests/test_quote_freshness.py).
These offline tests do not certify live account entitlements or source coverage.
Event-aware integration additionally needs tests for missed periods, changed
event dates, staggered statement availability and the day-20/day-90 example above.
