# IBKR 15-Minute Historical Prices: Pacing And Error Semantics

> **Status:** REVIEW DRAFT - RESEARCH REFERENCE, NOT A DESIGN AUTHORITY
> **Rewritten:** 2026-07-31
> **Primary scope:** ArkScope's scheduled US-equity
> `reqHistoricalData(..., barSizeSetting="15 mins")` price path.
> **Secondary scope:** Other IBKR request families appear only in the boundary
> table in section 7.
> **Supersedes:** The uncommitted 2026-07-28 broad pacing draft. That draft
> incorrectly treated the small-bar 60-requests-per-10-minutes rules as the
> central constraint for ArkScope's 15-minute collector.

## 0. Reading Rules

This file separates four evidence classes:

| Label | Meaning |
|---|---|
| **DOCUMENTED** | Stated by current IBKR documentation or, when explicitly marked, its deprecated TWS API documentation. |
| **OBSERVED-IN-REPO** | Directly established by current ArkScope source or tests. |
| **OBSERVED-LOCAL-LIBRARY** | Directly established from the installed `ib_insync` 0.9.86 source. |
| **UNKNOWN** | The reviewed evidence does not establish the claim. |

Do not upgrade a label when citing this file. In particular, a deprecated-only
statement is not current authority, and an in-repo safeguard is not evidence
that IBKR imposes the same rule.

## 1. Executive Answer

1. **DOCUMENTED:** IBKR's current documentation places the familiar
   identical-request, six-request, and 60-request rules under
   **"Pacing Violations for Small Bars (30 secs or less)"**. ArkScope requests
   15-minute bars. The published scope therefore does not support applying
   those small-bar rules to this collector.
2. **DOCUMENTED, deprecated-only:** The deprecated historical-limitations page
   states that historical-data limits for bar sizes of one minute and greater
   were lifted. The same note warns that large or frequent requests can still
   be slowed, throttled, or disconnected. The current page preserves the
   small-bar heading but omits the lifted-limit sentence.
3. **DOCUMENTED:** General TWS API message-rate pacing still exists. Current
   documentation describes it per client connection and derives the
   requests-per-second value from the user's market-data lines. TWS/Gateway may
   either reject excess messages or pace them internally, depending on its
   setting.
4. **OBSERVED-IN-REPO:** ArkScope also imposes its own conservative
   half-second request delay and a shared cross-process IBKR operation lock.
   Those are repository policies, not proof that 15-minute requests consume a
   60-per-10-minute bucket.
5. **OBSERVED-LOCAL-LIBRARY:** The installed `ib_insync` defaults
   `RaiseRequestErrors=False`. A request error such as code 162 can therefore
   complete the synchronous request with an empty result instead of raising.
6. **OBSERVED-IN-REPO:** ArkScope's price adapter catches per-chunk exceptions,
   logs them, and continues. Its caller cannot distinguish a request failure
   from a genuine empty result and may then try Polygon.
7. **OBSERVED-IN-REPO:** The shipped price-truth reconciliation prevents that
   ambiguity from becoming a false success. It reports the local fact
   `price_day_unresolved_after_fetch` when a zero-bar target remains empty.
   It still cannot identify the upstream cause.

The product problem established by this evidence is **loss of error
semantics**, not a proven breach of the small-bar 60/10 rule.

## 2. Correction Of The 2026-07-28 Draft

The previous draft extracted the three small-bar rules but failed to bind them
to their containing section. That changed a scoped rule into an apparently
general rule.

### 2.1 What the official pages actually establish

The current IBKR page is titled
[Pacing Violations for Small Bars (30 secs or less)](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/pacing-violations-for-small-bars-30-secs-or-less).
Within that scope it lists:

- no identical historical request within 15 seconds;
- fewer than six requests for the same contract, exchange, and tick type in
  two seconds; and
- no more than 60 requests in ten minutes.

The [deprecated historical-limitations page](https://interactivebrokers.github.io/tws-api/historical_limitations.html)
contains the same heading and rules, then explicitly says that limits for bar
sizes of one minute and greater had been lifted. It also retains a soft-load
warning for large or frequent requests.

### 2.2 Claims retired by this rewrite

| Prior claim or framing | Disposition |
|---|---|
| The 60/10 rule is the core pacing question for ArkScope prices. | **RETRACTED.** The collector uses 15-minute bars. |
| Determining whether 60/10 is per account, session, or `clientId` is necessary before changing this collector. | **RETRACTED AS A PRODUCT DEPENDENCY.** That scope question may matter to small-bar consumers, but it does not control this path. |
| Market-data-line sharing proves how historical 60/10 is scoped. | **RETRACTED.** It is an analogy across different limits. |
| Multiple `clientId` values provably increase or cannot increase 15-minute historical throughput. | **UNKNOWN.** No reviewed measurement establishes either direction. |
| A second Gateway gives exactly twice the throughput. | **REJECTED.** No primary evidence or controlled measurement supports it. |
| News, historical ticks, fundamentals, and prices can be assigned to documented shared or separate pacing buckets. | **UNKNOWN except where section 7 states an explicit limit.** |

### 2.3 Facts preserved

The rewrite preserves facts that remain relevant after correcting the scope:

- the general API message-rate limit;
- the 32-client connection ceiling documented by current and deprecated IBKR
  pages;
- the distinction between `clientId` isolation and throughput;
- historical-data availability and entitlement constraints;
- the generic nature of official error code 162;
- `ib_insync`'s empty-result behavior;
- the current ArkScope news/price error-handling asymmetry; and
- the requirement to report an unknown cause rather than infer one.

## 3. The Actual ArkScope Price Request

### 3.1 Request shape

**OBSERVED-IN-REPO**, current source:

- `src/market_data_direct.py::_fetch_rows_for_gaps` calls
  `IBKRDataSource.fetch_historical_intraday` with `interval="15 mins"`.
- `data_sources/ibkr_source.py::fetch_historical_intraday` passes that value as
  `barSizeSetting`, requests `TRADES`, and defaults to
  `include_extended=False`, which becomes `useRTH=True`.
- The adapter uses a local interval-to-chunk table and advances date ranges
  sequentially. Those chunk values are repository choices, not asserted IBKR
  hard limits.
- The top-up path fetches the full completed-day window for every ticker, not
  only the dates currently known to have zero bars. Existing rows are deduped
  during insertion.
- Provider fetch occurs outside `market_write_lock`; writes are batched under
  that lock.

### 3.2 Local pacing and serialization

**OBSERVED-IN-REPO:**

- `IBKRDataSource.REQUEST_DELAY` is 0.5 seconds.
- `_rate_limit_wait` enforces that delay between source-level operations.
- `src/ibkr_gateway_lock.py` serializes ArkScope IBKR operations across threads
  and processes.
- `data_sources/ibkr_client_id.py` assigns domain-specific IDs and explicitly
  says this is isolation hardening, not a throughput lever.

These safeguards are conservative. This reference does not claim each one is
required by an IBKR 15-minute-bar rule, and it does not authorize removing
them. Any relaxation requires measured latency, lock wait/hold time, provider
outcomes, and a separately reviewed design.

### 3.3 What cadence can and cannot be justified by pacing

The small-bar 60/10 rules do **not** justify ArkScope's saved 600-minute price
cadence. Cadence should instead be evaluated against:

- the collector's completed-trading-day contract;
- exchange-calendar timing and close buffers;
- the value of a pre-open reconciliation;
- observed provider latency and failure outcomes; and
- user-visible data freshness.

This file does not set that cadence. It only removes an invalid pacing premise
from the decision.

## 4. Limits That Still Apply

Excluding the small-bar rule does not mean 15-minute requests are unlimited.

### 4.1 General API request rate

**DOCUMENTED:** Current IBKR
[Pacing Limitations](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction)
describes a per-client-connection request rate equal to maximum market-data
lines divided by two per second. The associated
[Pacing Behavior](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/pacing-behavior)
allows TWS/Gateway either to reject excess messages or to delay them
internally.

Consequences:

- absence of an error does not prove absence of pacing;
- a response delay may be local queueing, Gateway pacing, HMDS latency, or
  another cause;
- different `clientId` values do not remove server, entitlement, availability,
  or shared-resource constraints; and
- this general message-rate rule must not be renamed "historical 60/10".

### 4.2 Request size and server load

**DOCUMENTED:** IBKR publishes allowed bar sizes, duration/bar-size step
relationships, and maximum duration tables for historical requests. The
deprecated page additionally warns of soft slowing, throttling, and eventual
disconnect for excessive large requests.

**UNKNOWN:** The reviewed current documentation does not give ArkScope a
numeric sustainable-throughput guarantee for 15-minute bars. Treating either
the local 0.5-second delay or `ib_insync`'s generic message throttle as that
guarantee would be unsupported.

### 4.3 Data can genuinely be unavailable

**DOCUMENTED:** IBKR's
[Unavailable Historical Data](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/unavailable-historical-data)
lists classes that are not retrievable, including delisted securities, certain
expired instruments, native combo history, and history before some exchange
moves. Separately, IBKR's
[third-party FAQ](https://www.interactivebrokers.com/docs/third-party-integrations/general-third-party-frequently-asked-questions)
states that receiving historical bars through the API requires the applicable
streaming Level 1 market-data subscription.

Therefore an empty result can be genuine. The defect is not that empty results
exist; it is that the current adapter cannot tell which empties are genuine.

## 5. Historical Error Semantics

### 5.1 Official codes do not provide a complete classifier

The current [IBKR error table](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes)
documents:

| Code | Published meaning relevant here |
|---|---|
| `162` | Generic historical market-data service error; the note is empty. |
| `165` | Historical service query message; its note mentions no data in the database. |
| `166` | Historical data unavailable for an expired contract. |
| `366` | Historical query was cancelled or not found for the ticker ID. |
| `2105` | Historical data farm disconnected. |
| `2106` | Historical data farm connected. |
| `2107` | Historical data farm inactive while unused; it should reconnect on demand. |
| `10089` | The user's market-data subscription does not include API use. |

Code 162 alone does not state whether a request was rate-limited, denied,
cancelled, unavailable, or failed for another reason. A future structured
outcome must correlate `reqId`, code, and message text, and it must retain an
unknown category. Message-text matching may improve diagnosis but must not be
treated as a stable provider protocol without tests and a fallback.

### 5.2 Installed `ib_insync` collapses request failure into empty

**OBSERVED-LOCAL-LIBRARY**, version 0.9.86:

- `ib_insync/ib.py` sets `RaiseRequestErrors = False`.
- Its own documentation defines `False` as silently returning an empty result
  and `True` as raising `RequestError`.
- `ib_insync/wrapper.py::error` treats code 162 as a non-warning error.
- For an active request with `RaiseRequestErrors=False`, it calls `_endReq`
  without an error object.
- It emits `errorEvent(reqId, errorCode, errorString, contract)` after handling
  the request.
- `ib_insync/client.py` separately throttles each `Client` instance at 45
  messages per second. That generic client throttle is not the historical
  small-bar 60/10 rule.

Thus the library receives error text, but the synchronous historical request
can still return an empty collection.

### 5.3 ArkScope's current price path loses the distinction

**OBSERVED-IN-REPO:**

1. `IBKRDataSource.fetch_historical_intraday` calls `reqHistoricalData`.
2. A per-chunk exception is caught, logged, and not returned to the caller.
3. The method returns a ticker key whose bar list may be empty.
4. `_fetch_rows_for_gaps` sees no IBKR rows and may invoke Polygon fallback.
5. If the final local target date is still empty, post-write reconciliation
   reports `price_day_unresolved_after_fetch`.

The reconciliation proves a local before/after fact. It does not prove any of:

- IBKR had no trade;
- IBKR returned no data;
- IBKR rejected or paced the request;
- the account lacked entitlement;
- Polygon was unavailable; or
- either provider supplied a stored row.

### 5.4 Existing strict-news precedent

**OBSERVED-IN-REPO:**
`IBKRDataSource.fetch_news_article_body_strict` temporarily sets
`RaiseRequestErrors=True`, restores it in `finally`, and maps news error 10172
to a typed exception. Its docstring explicitly preserves the distinction
between empty and failed.

This proves the installed library can expose request failure. It does **not**
pre-approve copying that implementation into prices: historical bars have
different codes, retries, partial results, and multi-ticker effects. It is a
candidate seam for a future reviewed structured-outcome slice.

## 6. Current User-Visible Truth Boundary

The price-truth rollout completed on 2026-07-31 establishes:

- `succeeded` only when every scanned ticker has no issue;
- `partial` when some, but not all, tickers remain unresolved or fail;
- `failed` when all scanned tickers have issues;
- a zero-bar target still empty after insertion receives
  `price_day_unresolved_after_fetch`;
- unresolved tickers do not advance per-ticker `last_success`;
- Settings receives bounded unresolved counts and ticker IDs; and
- the local Coverage surface remains the read-side authority for completeness.

This is the correct user contract even before upstream causes are classified:
the application says what it can prove and does not blame a provider without
evidence.

Production rollout has so far proved the resolved path: a previously empty LCID
target was naturally filled and the run correctly remained `succeeded`.
The first natural unresolved/partial production case has not yet occurred.

## 7. Other IBKR Request Families: Boundary Only

| Request family | What this reference can say | What it cannot say |
|---|---|---|
| `reqHistoricalData`, 15-minute bars | Current small-bar heading does not cover it; general API rate, availability, entitlement, and soft-load behavior remain relevant. | No numeric sustainable throughput or 60/10 bucket scope is established. |
| Historical bars, 30 seconds or less | The three small-bar pacing rules apply as published. | This file does not decide their scope across multiple connections. |
| `reqRealTimeBars`, 5-second bars | Current docs explicitly combine market-data-line limits with small-bar historical pacing. | It is not a substitute for ArkScope's completed 15-minute history. |
| Streaming `reqMktData` | General request-rate and market-data-line limits apply. | A streaming quote does not fill the historical 15-minute table. |
| `reqHistoricalTicks` | Current docs publish per-request and availability constraints. | No reviewed source establishes a shared or separate 60/10 bucket. |
| Historical news / news article bodies | Entitlement and result-shape rules exist; ArkScope has separate news handling. | No reviewed source establishes its relationship to price pacing. |
| Market scanner | Current docs publish scanner-specific result and active-scan limits; ArkScope exposes scanner methods in `data_sources/ibkr_source.py`. | No `src/` consumer was found. This reference does not decide whether to retain the capability or how scanner limits relate to price pacing. |
| Fundamentals / WSH | Outside this document. | No pacing-bucket claim is supported here. |

This table prevents a price-path conclusion from being silently promoted into
a universal IBKR rule.

## 8. Client IDs, Connections, And The Shared Lock

**DOCUMENTED, current and deprecated:** Current
[architecture documentation](https://www.interactivebrokers.com/docs/tws-api/doc/architecture/introduction)
allows up to 32 API clients on one TWS or IB Gateway instance. The deprecated
[connectivity documentation](https://interactivebrokers.github.io/tws-api/connection.html)
states the same ceiling and says that `clientId` distinguishes the clients.

**OBSERVED-IN-REPO:** ArkScope derives separate IDs for prices, news, options,
quotes, holdings, and other domains. This avoids client-ID collision and
improves diagnostics.

Neither fact establishes a throughput multiplier. The shared
`ibkr_gateway_lock` is an ArkScope coordination policy that serializes IBKR
operations to avoid concurrent request storms across threads and processes.
Its existence must not be cited as proof that Gateway accepts only one API
connection; it does not.

Before changing that policy, measure:

- lock wait and hold time;
- request duration and timeout distribution;
- error code plus sanitized message class;
- per-domain overlap;
- Gateway disconnects; and
- user-visible freshness.

Multiple databases, a load balancer, or more writer threads do not solve an
upstream request that returned no rows. Those architecture changes need their
own demonstrated bottleneck.

## 9. Design Consequences And Non-Decisions

### 9.1 Supported consequences

- Do not use the small-bar 60/10 rules to justify the 15-minute collector's
  cadence, lock, retry policy, or client-ID topology.
- Keep local post-fetch reconciliation as the truth authority even after
  provider errors become structured.
- A future provider outcome should distinguish at least:
  `returned_rows`, `empty_response`, `request_failed`, and
  `cause_unknown`; exact names require a separate spec.
- Correlate provider diagnostics to the request/ticker. A global log line is
  insufficient for per-ticker state.
- Preserve unknown when IBKR's code/message combination is not safely
  classified.
- Calendar-aware scheduling and pre-open reconciliation are product/efficiency
  decisions, not consequences of a 60/10 rule.

### 9.2 Not decided here

This reference does not authorize:

- changing the saved 600-minute cadence;
- removing or narrowing `ibkr_gateway_lock`;
- running IBKR price and news requests concurrently;
- enabling `RaiseRequestErrors=True` on the price source;
- parsing specific provider message strings into a final taxonomy;
- adding retries or dynamic rate adaptation;
- changing the completed-day or Coverage contracts;
- adding extended-hours storage/session semantics; or
- introducing more databases, a load balancer, or writer concurrency.

Each would change product or operational behavior and requires its own evidence
and reviewed design.

## 10. Unknowns Worth Measuring

Only measure these when they serve a product decision:

1. Which code/message classes occur on ArkScope's 15-minute requests in
   production?
2. For each class, does IBKR return no rows, partial rows, or raise?
3. How often does Polygon fallback run, and which stored rows came from it?
4. What are the observed lock wait/hold distributions by IBKR domain?
5. Does a calendar-aware cadence reduce requests without delaying completed-day
   availability?
6. If concurrent IBKR domains are proposed, what changes in request latency,
   disconnects, and user-visible freshness under a controlled trial?

The per-connection scope of the small-bar 60/10 counter is not a blocking
unknown for the current 15-minute collector.

## 11. Sources And Reproduction Boundary

### 11.1 Primary IBKR sources

- [Current small-bar pacing page](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/pacing-violations-for-small-bars-30-secs-or-less)
- [Deprecated historical limitations, including the one-minute-and-greater
  note](https://interactivebrokers.github.io/tws-api/historical_limitations.html)
- [Current general pacing introduction](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction)
- [Current pacing behavior](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/pacing-behavior)
- [Current historical-bar request documentation](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-bars/requesting-historical-bars)
- [Current historical bar sizes and durations](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-bars/historical-bar-sizes)
- [Current historical step sizes](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-bars/step-sizes)
- [Current maximum duration per bar size](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-bars/max-duration-per-bar-size)
- [Current unavailable historical data](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/unavailable-historical-data)
- [Current third-party FAQ, including API historical-bar subscription
  requirements](https://www.interactivebrokers.com/docs/third-party-integrations/general-third-party-frequently-asked-questions)
- [Current error codes](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes)
- [Current TWS API architecture introduction](https://www.interactivebrokers.com/docs/tws-api/doc/architecture/introduction)
- [Deprecated connectivity documentation](https://interactivebrokers.github.io/tws-api/connection.html)
- [Current market-scanner introduction](https://www.interactivebrokers.com/docs/tws-api/doc/market-scanner/introduction)

### 11.2 Local evidence inspected

- `data_sources/ibkr_source.py`
- `data_sources/ibkr_client_id.py`
- `src/market_data_direct.py`
- `src/prices_runtime.py`
- `src/ibkr_gateway_lock.py`
- installed `ib_insync` 0.9.86:
  `ib.py`, `wrapper.py`, and `client.py`
- `docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md`

This rewrite deliberately excludes practitioner throughput claims. The prior
draft's secondary-source survey did not establish a controlled
multi-`clientId` measurement, and that question is not load-bearing for the
15-minute collector.
