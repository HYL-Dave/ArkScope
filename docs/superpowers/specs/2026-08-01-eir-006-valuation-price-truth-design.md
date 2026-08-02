# ArkScope EIR-006 Valuation Price Truth Design

> **Status: APPROVED - IMPLEMENTATION PLAN REVIEW NEXT**
>
> **Date:** 2026-08-01
> **Grounding commit:** `fd6d1b86383df2a98f97b235d9796d4bcaaa7a58`
> **Reviewed design commit:** `124622bc`
> **Scope:** detailed-financials valuation price authority, static financial
> cache semantics, legacy fundamentals bypass, repository CSV price readers,
> and the separately approved final deletion of retired price/fundamentals data

## 1. Purpose

The registered `get_detailed_financials` tool can currently read the last close
from an old repository CSV, call that value current, derive market cap and
eight related valuation fields, and cache the result for 90 days. The observed
CSV frontier was 2026-07-02 while the current SQLite price authority extended
through 2026-07-30.

This is not merely stale storage. It is a live product-truth defect:

```text
registered get_detailed_financials tool
  -> FinancialMetricsCalculator.get_metrics_dict()
  -> get_valuation_metrics()
  -> _get_current_price_ibkr()
  -> final close in data/prices/{15min,hourly} CSV
  -> price-derived values cached for 90 days
```

The target state is a hard authority cutover:

- detailed-financials static facts come from SEC EDGAR; the separate
  fundamentals-analysis tool retains its existing SEC-first, already-gated
  Financial Datasets fallback;
- valuation price comes only from a qualified local `market_data.db` 15-minute
  bar and always carries market date, timestamp, interval, and provenance;
- when that price cannot be qualified, all price-derived valuation fields are
  omitted with a stable typed reason;
- old valuation cache semantics are never read or migrated;
- runtime code no longer reads repository price CSVs or the retired IBKR
  fundamentals mirror; and
- after those product changes are merged and a fresh consumer census is clean,
  the old price artifacts and old DB rows are physically deleted under a
  separate explicit execution approval.

The user has explicitly chosen to discard the 75 unique 2023 hourly CSVs
rather than migrate them. Their uniqueness is known and accepted. Development
must not preserve an obsolete storage decision merely because the data once
existed.

## 2. Grounded Current State

### 2.1 Live detailed-financials chain

At the grounding commit:

1. `src.tools.analysis_tools.get_detailed_financials()` uses cache key
   `metrics_{ticker}_annual_y2`.
2. A cache miss calls
   `FinancialMetricsCalculator.get_metrics_dict()`, which includes valuation
   metrics.
3. The complete `standard` result is cached for 90 days, so price-derived
   values and their static inputs are not separated.
4. `FinancialMetricsCalculator._get_current_price_ibkr()` scans
   `data/prices/15min` and `data/prices/hourly`, reads the last CSV row, and
   returns its close without testing its date against a market calendar.
5. `get_valuation_metrics()` calls that function when the old IBKR
   fundamentals JSON does not supply market cap.
6. `get_detailed_financials()` then calls `dal.get_fundamentals()` again and
   may override SEC values from a legacy snapshot.
7. `get_peer_comparison()` calls `get_detailed_financials()` once per peer, so
   the same stale value can enter comparison matrices, ranks, and sector
   statistics.
8. The tool is registered and reachable through agent and analysis surfaces.
   This is not dead test code.

The current docstrings call the CSV value "current" and the legacy enrichment
"IBKR real-time". Neither claim is supported by the code path.

### 2.2 A second old-fundamentals short circuit remains reachable

`get_fundamentals_analysis(period="annual")` first calls
`dal.get_fundamentals()`. If that result has a snapshot date, it returns the
old snapshot as `data_source="ibkr"` before the SEC EDGAR or gated Financial
Datasets paths run.

The normal desktop/API local backend already rejects this authority:
`LocalMarketDatabaseBackend.query_fundamentals()` returns an honest empty
result and documents the old snapshot table as retired. The stale path remains
reachable through explicit low-level `SqliteBackend` or `FileBackend` shapes.
The product tools must stop asking those backends for a retired authority;
physical row deletion alone is not a semantic fix.

### 2.3 Current local authorities

The product already has the needed current storage:

| Domain | Current authority | Read contract |
|---|---|---|
| 15-minute prices | `market_data.db.prices` | SQLite, local, read-only |
| SEC annual/quarterly facts | `financial_cache` entries owned by the SEC analysis contract | local-primary cache |
| Optional paid fundamentals | Financial Datasets client behind the existing enablement gate | cache-first, provider call only when already permitted |
| Legacy IBKR fundamentals | retired | not a current product authority |

`market_data.db` already contains prices. A new price-only database is not
required to establish truthful valuation semantics.

### 2.4 Existing completed-session authority

`src.market_data_direct` already owns the US trading-day definition:

- clocks are normalized to `America/New_York`;
- weekends and exchange holidays are excluded by `_market_day_status`;
- an earlier ET date is complete; and
- the current ET date becomes complete only at or after 16:30 ET.

This is the same completed-day authority used by gap detection and top-up.
EIR-006 must reuse it. A second valuation-specific calendar or a raw UTC-date
comparison would create conflicting answers.

### 2.5 Dated production observations

The following values were read on 2026-08-01 using SQLite `mode=ro` and
`PRAGMA query_only=ON`. They establish scope; they are not acceptance
constants:

| Data | Observation |
|---|---|
| `prices`, interval `15min` | 2,402,420 rows, 151 tickers, through `2026-07-30T23:45` |
| legacy `fundamentals` | 130 rows for 130 tickers; all snapshot dates `2025-12-25` |
| legacy fundamentals sync telemetry | one `market_sync_meta` row with last success `2026-06-27T03:33:19+00:00` |
| old detailed-financials cache keys | 19 rows matching `metrics_*_annual_y2` |
| 15-minute CSVs | 225 files, 2,547,747 rows, about 160 MB with hourly files |
| hourly CSVs | 75 files, 129,575 rows, 2023-01-03 through 2023-12-29 |
| legacy collection summary | one 2,656-byte `data/prices/collection_summary.json`, generated 2026-07-03 and reporting zero collected bars |

The 19 observed old cache tickers were:

```text
AMD ARM ASML AVGO COIN DELL GOOGL INTC MRVL MU MXL NVDA PLTR QCOM
RKLB SMCI SNDK STRL TSM
```

Those names and counts may change before execution. The deletion gate must
rederive an exact manifest rather than hard-code this observation.

### 2.6 CSV-to-SQLite comparison

The 225 15-minute CSV files contain 2,547,747 physical rows. Two views must be
kept distinct:

| View | Unique keys | Duplicate rows | Conflicting duplicate keys | Keys differing from SQLite |
|---|---:|---:|---:|---:|
| raw-ticker diagnostic | 2,314,293 | 233,454 | 58 | 161 |
| canonical deletion authority | 2,298,763 | 248,984 | 176 | 43 |

The raw view keys rows by the ticker stored in the CSV plus normalized absolute
timestamp; it resolves that ticker only for the SQLite lookup, so alias-
equivalent raw keys remain separate. The canonical view first applies the
current ticker-alias table, then groups every CSV value variant by
`(canonical_ticker, absolute_datetime)`. A canonical key differs from SQLite
only when none of its CSV value variants exactly matches the current SQLite
row.

Only `LC -> HAPN` changes this corpus. All 15,530 `LC` keys overlap a `HAPN`
key after canonicalization, and 118 of those alias-pair keys carry conflicting
values. That explains both the raw-to-canonical key reduction and why the raw
comparison reports 161 differences while the canonical comparison reports 43.
Of the 43 canonical differences, 23 are volume-only and 20 include OHLC.

Every one of the 2,298,763 canonical 15-minute CSV keys exists in
`market_data.db`. The evidence does not establish whether the CSV or SQLite
value is more accurate for the 43 canonical differences. The product ruling
is to keep the current SQLite authority and discard the historical CSV
alternatives rather than preserve two competing truths. The final deletion
manifest must recompute both views, but only the canonical method is an
admission authority; the raw view is diagnostic.

The 75 hourly CSVs are different: their 2023 rows have no complete current
local duplicate. Training does not read them, and current documentation frames
intraday training as future work. The user has knowingly chosen deletion
without migration. No implementation may silently import these rows into
SQLite, an archive, a training fixture, or a replacement database.

### 2.7 Other current consumers of the old paths

Seven additional surfaces must move before deletion:

1. `src.daily_update.get_ibkr_prices_status()` scans
   `data/prices/{hourly,15min}` and would falsely report no price data after
   deletion even while SQLite is healthy.
2. `FileBackend.query_prices()` still implements CSV/Parquet price reads, and
   `FileBackend.get_available_tickers("prices")` still globs the same retired
   directories. Explicit no-DSN callers can therefore reactivate or advertise
   the retired files. Its `get_available_tickers("fundamentals")` branch also
   scans the already-absent `data_lake/raw/ibkr_fundamentals` path and must not
   survive as a false file-backed capability.
3. `local_market_stats()` and `local_ticker_coverage()` still derive their
   `fundamentals` facts from the retired table.
4. The registered `get_ticker_data_coverage` tool independently summarizes the
   same retired table.
5. Settings and Ticker Detail render those projections. Ticker Detail can
   therefore show "fundamentals local coverage: yes" from a legacy row while
   its stored-only fundamentals request correctly returns no positive SEC cache
   result.
6. `read_sync_meta()` and the registered coverage tool still expose the
   retired fundamentals sync row, so Settings can describe a 2026-06-27
   snapshot refresh as a current successful update.
7. `GET /status` counts
   `LocalMarketDatabaseBackend.get_available_tickers("fundamentals")`, whose
   current implementation still reads the retired table. The system status can
   therefore advertise legacy ticker coverage independently of the stored-only
   SEC contract, and Dashboard renders that count directly.

Two indirect callers are behavior-propagation consumers rather than an eighth
legacy-data authority: the `/fundamentals` route and the evidence packet's
institutional-evidence builder both call `get_fundamentals_analysis()`. The
implementation plan must place their existing test nodes in the affected-node
ledger so LD 12 cannot change beneath them without review.

Current training collection uses yfinance or direct IBKR daily bars, not these
300 CSVs. Its help text incorrectly says the IBKR option reads a retired daily
directory through an already-removed collector; the implementation actually
fetches daily bars directly from Gateway. The help and README must be corrected
so documentation does not recreate a consumer. The README is also the sole
current reference to the stale zero-row
`data/prices/collection_summary.json`.

Other keep-current documents still presenting the retired paths as current
include `docs/analysis/FINANCIAL_METRICS_FORMULAS.md`,
`docs/data/DATA_INVENTORY.md`, and
`docs/data/DATA_SUBSCRIPTION_GUIDE.md`. The canonical
`docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` still names
`data/prices/{15min,hourly}` parquet as a price query authority even though the
implemented authority is now `market_data.db`. These current owners must be
updated. Explicitly dated audit/evidence documents may preserve their
historical facts when their non-current status is unambiguous.

The registered and Anthropic detailed-financials tool descriptions, Python
docstring, and response-schema comments also claim "IBKR real-time". These are
model-visible or maintainer-visible contract text and must describe qualified
local SQLite price provenance plus typed unavailability instead.

### 2.8 Unit inconsistency is live

The calculator's old JSON branch correctly treats IBKR `MKTCAP` and `EV` as
millions and multiplies by `1e6`. A separate enrichment in
`get_detailed_financials()` reads `snapshot.market_cap` and assigns it directly
to the response without that conversion.

For example, the observed AMD legacy row stores market cap `349866.1` in the
old unit convention. Returning that raw value beside SEC values expressed in
base currency units is inconsistent. The hard cutover removes this override;
it must not add a heuristic such as "multiply values below a threshold".

### 2.9 Current green baseline

The merged canonical backend collection at the grounding commit is:

```text
4553 collected
collection SHA-256:
69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca

4481 passed
72 skipped
0 failed
```

The implementation plan must rederive this baseline and pin the exact target
collection before product edits. No design count in this document authorizes
an unreviewed node delta.

## 3. Product Ruling

### 3.1 Selected approach: hard local authority cutover

The selected design is:

1. calculate and cache static financial facts independently of market price;
2. select a qualified local SQLite price for the latest completed US trading
   day;
3. derive all price-dependent valuation fields on every request;
4. expose the exact price basis or a stable unavailable reason;
5. never read old CSVs, old detailed-financials cache keys, or old IBKR
   fundamentals in product paths; and
6. delete the retired data after the merged product has proven it has no
   consumers.

This preserves useful current capability without preserving obsolete storage.

### 3.2 Rejected: live IBKR quote fan-out

`get_peer_comparison()` evaluates multiple tickers. Fetching a live quote for
each peer would add Gateway availability, entitlement, request pacing, and
N-provider-call behavior to a currently local analysis tool. It would also make
the result nondeterministic and unavailable when the desktop Gateway is down.

The existing current-quote tool remains available for explicit quote requests.
It is not the valuation authority selected here.

### 3.3 Rejected: retain stale values with warnings

A warning does not make a stale market cap safe. Agents can quote the number,
peer ranks can include it, and a 90-day cache can outlive the warning's
salience. When freshness is not proven, omission plus a typed reason is the
truthful result.

### 3.4 Rejected: migrate the 2023 hourly CSVs

The hourly files have unique historical rows, but no current runtime or
training consumer. Migrating them would create and maintain semantics for an
obsolete source solely because it exists. The user explicitly selected
discard, so migration is forbidden.

### 3.5 Rejected: create a price-only database

Prices are already a first-class table in `market_data.db`, with current
writers, aliases, read-only access, and coverage contracts. Splitting the same
rows into a new database would not solve freshness or provenance; it would add
another topology, synchronization boundary, backup surface, and query path.

This design does not prohibit a future database-topology decision supported by
new evidence. It does not use EIR-006 to create one.

## 4. Scope

### 4.1 In scope

- a read-only qualified valuation-price selector over
  `market_data.db.prices`;
- reuse of the existing completed-session calendar contract;
- explicit valuation price basis and typed unavailability in
  `DetailedFinancials`;
- separation of static financial cache data from request-time valuation;
- a new semantic cache key that cannot read old `metrics_*_annual_y2` rows;
- removal of legacy IBKR snapshot overrides and annual-analysis short circuit;
- truthful propagation through peer comparisons;
- rewire of `daily_update` price status to the SQLite authority;
- retirement of FileBackend CSV price reads and dead price/fundamentals file
  discovery;
- replacement of legacy-table fundamentals status/coverage with the exact
  positive stored-SEC cache contract already used by `stored=true`;
- truthful existing Settings, Ticker Detail, Dashboard, market-data API,
  system-status API, and registered coverage-tool projections without adding a
  new screen;
- correction of stale training/help references;
- a static runtime-consumer census for the old data paths;
- RED-first product and regression tests;
- a post-merge read-only production observation; and
- a final, separately approved physical deletion task for the retired price
  artifacts and DB rows.

### 4.2 Out of scope

- live IBKR quote calls or any provider request added to valuation;
- changes to the Financial Datasets metered-spend policy or enablement switch;
- automatic use of a paid endpoint;
- a new price database, DB split, load balancer, or row-provenance migration;
- changing price collection cadence, fallback, retry, or partial-truth logic;
- changing Coverage v2 slot classification or claiming complete coverage from
  the valuation selector;
- backfilling, repairing, or choosing among the 43 canonical CSV/SQLite
  differences or 176 conflicting canonical duplicate keys;
- migrating the 75 hourly CSVs;
- preserving a durable archive of the deleted data;
- secure-erasure or DB-file compaction solely to reclaim pages from these rows;
- dropping the `fundamentals` table or changing `market_data.db` schema solely
  to remove empty legacy rows;
- redesigning the generic current-quote tool;
- adding a new detailed-financials frontend screen;
- Tranche B score retirement, EIR-001, EIR-003, or Financial Datasets policy
  implementation; and
- provider, Gateway, SEC, Financial Datasets, Finnhub, or other network calls
  during tests or review.

## 5. Terms

### 5.1 Latest completed market date

The latest date for which the existing
`src.market_data_direct._complete_trading_days()` contract says the US session
is complete at the supplied ET clock.

Before 16:30 ET on a trading day, the date is the previous completed trading
day. At or after 16:30 ET, the date is today. Weekends and exchange holidays
resolve to the preceding completed trading day.

### 5.2 Qualified valuation price

The latest finite, positive `close` among stored `15min` rows whose timestamp,
converted to `America/New_York`, belongs to the latest completed market date.

One valid row is sufficient. This is a day-presence qualification, not a
26-slot coverage claim. The selected row may be an extended-hours row; the
response exposes its exact timestamp and does not call it an official exchange
close.

### 5.3 No qualified price

The target completed market date has no valid qualifying row, or the local
store cannot be read safely. The stable external reason is:

```text
no_qualified_price
```

This reason states only that the local proof required by this contract is
absent. It does not claim provider failure, no trading, missing entitlement,
store corruption, or a complete-day coverage gap.

### 5.4 Static financial facts

Financial statement values and ratios that do not depend on the selected
market price, including report date, revenue, income, equity, debt, cash,
shares, margins, growth, and per-share statement values.

### 5.5 Dynamic valuation fields

The following nine response fields depend on the qualified price and must be
recomputed per request:

```text
market_cap
enterprise_value
pe_ratio
pb_ratio
ps_ratio
ev_to_ebitda
ev_to_revenue
fcf_yield
peg_ratio
```

## 6. Locked Decisions

### LD 1 - `market_data.db` is the sole valuation price authority

The selector reads only the current local SQLite price table through a
no-create, read-only connection. It may honor `ARKSCOPE_MARKET_DB` through
`resolve_market_db_path()`. It must not fall back to FileBackend, PG, CSV,
provider APIs, or the generic current-quote routing chain.

### LD 2 - Store access fails closed without creating or leaking

Missing, unreadable, schema-incompatible, and query-failed stores all produce
`available=false` and `empty_reason="no_qualified_price"`.

The implementation may log a bounded internal diagnostic. Response fields may
not contain exception text, absolute paths, SQL, or environment values. A read
must not create a directory, database file, schema, WAL, or journal.

### LD 3 - ET market-date identity owns selection

Stored timestamps are converted from their actual offset/UTC form into
`America/New_York` before comparison with the target market date. Raw
`substr(datetime, 1, 10)` is insufficient because an extended-hours ET row can
cross a UTC date boundary.

Ticker canonicalization must reuse the existing alias table behavior.

### LD 4 - Presence is not completeness

One valid row on the required completed market date qualifies. The selector
must not require 26 RTH slots, a minimum volume, a particular provider, or a
specific time of day.

Coverage v2 remains the read-side authority for full slot coverage. A
qualified valuation price and partial Coverage result may coexist because they
answer different questions.

### LD 5 - No older-day fallback

If an older bar exists but the required completed market date has none, the
selector returns `no_qualified_price`. It may not silently step backward until
it finds a number.

This rule is the actual stale-price correction.

### LD 6 - The price basis is part of the product response

`DetailedFinancials` gains a nested `valuation_price_basis` object:

```text
available: bool
source: "local_market_db" | null
interval: "15min" | null
required_market_date: YYYY-MM-DD | null
market_date: YYYY-MM-DD | null
timestamp: ISO-8601 | null
price: float | null
empty_reason: null | "no_qualified_price"
```

When available, all provenance fields are populated and `empty_reason` is
null. When unavailable, `price`, `market_date`, `timestamp`, `source`, and
`interval` are null; `required_market_date` remains populated whenever the
calendar could derive it.

No top-level error string is added.

### LD 7 - Price-dependent output is all-or-none by price basis

When the basis is unavailable, all nine fields in Section 5.5 are null.
Static facts remain available.

When the basis is available, each field is calculated only when its required
static inputs are present. Missing static inputs may leave individual fields
null without changing the price-basis reason. EIR-006 does not invent a second
missing-fundamentals reason taxonomy.

### LD 8 - Units are explicit, never heuristic

Market cap is:

```text
qualified USD/share price * SEC/FD outstanding shares
```

Enterprise value and ratios then use static inputs expressed in their source
contract's base units. The old IBKR raw snapshot override leaves the path.

No magnitude threshold may guess whether a value is in dollars, thousands, or
millions. If a source needs conversion, that conversion belongs at the source
boundary and must have a direct test.

`FinancialMetricsCalculator` becomes storage-agnostic for valuation. Its
valuation API accepts an explicit optional price from the caller; it does not
open a market DB, scan a CSV, load the retired IBKR fundamentals mirror, or
call a provider. `_get_current_price_ibkr()`, `_load_ibkr_data()`, and their
constructor/file-path state leave the module when the consumer census proves
they have no non-retired use.

Convenience functions and the module CLI that do not receive an explicit
qualified price return static metrics with dynamic valuation fields null. They
may not recover the old behavior through an implicit fallback.

### LD 9 - Cache static facts, never a 90-day market price

The new semantic key is:

```text
detailed_financials:v2:sec_edgar:{TICKER}:annual:y2
```

The cached payload may contain:

- report date and static standard/tech metrics;
- the exact statement inputs required to recompute the nine dynamic fields;
- source identity and semantic version; and
- no market price, price timestamp, price market date, or dynamic valuation
  result.

Every request resolves the current qualified price basis and recomputes
dynamic fields, including on a static-cache hit.

Existing earnings-surprise and upcoming-earnings fields remain outside this
static cache. EIR-006 neither retires them nor changes their runtime provider
semantics; tests use doubles and make no live request.

If a future Financial Datasets implementation supplies the same static shape,
it must use a distinct source-bearing semantic key. It may not overwrite a SEC
key or bypass the existing metered-spend gate.

### LD 10 - Old cache semantics are abandoned, not migrated

`metrics_{TICKER}_annual_y2` is never read by the new code. Existing rows do not
receive a conversion or compatibility fallback.

This is semantic invalidation. Physical deletion of matching rows occurs only
at the final data gate.

### LD 11 - Static-source identity stays static

`DetailedFinancials.data_source` describes the source of static financial
facts, such as `sec_edgar` or `financial_datasets`. It must not become
`ibkr+sec_edgar` merely because a local market price was used.

Price provenance belongs only to `valuation_price_basis`.

### LD 12 - The retired fundamentals snapshot cannot short-circuit tools

`get_detailed_financials()` no longer calls `dal.get_fundamentals()` for an
IBKR override.

`get_fundamentals_analysis(period="annual")` no longer returns a legacy
snapshot before SEC/FD evaluation. Existing SEC cache behavior and the
Financial Datasets enablement gate remain unchanged.

The `/fundamentals` route and evidence-packet institutional-evidence path
inherit this behavior through `get_fundamentals_analysis()`. Their existing
tests must be named in the implementation node ledger even though those
callers do not reference the retired table or cache key directly.

The low-level table may remain inspectable until its rows are deleted, but it
is not a product authority.

### LD 13 - Peer comparison reports valuation absence

Peer comparison continues to include peers whose static financials succeeded.
Null dynamic fields are excluded from metric statistics and rankings as they
are today.

Its `data_quality` adds:

```text
valuation_price_unavailable_count
valuation_price_unavailable_tickers
valuation_price_empty_reason_counts
```

The only current external reason is `no_qualified_price`. This prevents a peer
matrix with silent null valuation fields from appearing complete.

### LD 14 - `daily_update` reports the current store

`get_ibkr_prices_status()` projects the existing read-only
`local_market_stats()` price facts. It no longer walks repository price files.

The command may retain its user-facing label for compatibility, but its
docstring/output must say that prices are served from local
`market_data.db`, not from a CSV directory or necessarily from a live Gateway.

### LD 15 - Fundamentals coverage follows the stored product contract

The existing `fundamentals` member in:

- `local_market_stats()`;
- `local_ticker_coverage()`;
- `LocalMarketDatabaseBackend.get_available_tickers("fundamentals")`;
- `get_ticker_data_coverage`;
- `/status`;
- `/market-data/status`; and
- `/market-data/coverage/{ticker}`

must stop reading the legacy `fundamentals` table.

It instead reports positive, unexpired annual SEC cache entries using the exact
semantic key family already owned by the stored-only route:

```text
fundamentals_analysis:sec_edgar:{TICKER}:annual:v1
```

A negative cache payload, expired row, malformed payload, old
`metrics_*_annual_y2` row, detailed-financials v2 cache row, or Financial
Datasets endpoint cache does not establish this stored-only SEC coverage.
`LocalMarketDatabaseBackend.get_available_tickers("fundamentals")` must return
that projection directly and must not fall back to the legacy SQLite table or
PG when the positive cache set is empty.

`financial_cache` status remains the all-cache operational count. The
`fundamentals` status becomes the user-facing positive stored-SEC projection:
positive row count, distinct ticker count, and latest validated report/snapshot
date. Cache-fetch time remains owned by
`financial_cache.latest_fetched_at`; `fundamentals.latest_date` must not
silently change into an operational fetch timestamp.

This preserves the existing API field shapes while making Ticker Detail's
coverage boolean agree with `GET /fundamentals/{ticker}?stored=true`. Existing
Settings, Ticker Detail, and Dashboard copy must identify the value as stored
SEC fundamentals rather than an unspecified legacy local snapshot or raw
`fundamentals_tickers` identifier, in both locales.

The backend already returns stable `source_path="local_cache"` for a positive
stored-only hit. The frontend `SourcePath` union and reviewed presentation
must include that value and render localized copy; it may not expose the raw
identifier to the user.

The retired `market_sync_meta.domain='fundamentals'` row is not a current
refresh authority. `read_sync_meta()` and `get_ticker_data_coverage` must
project `sync.fundamentals=null` even before physical deletion. Current price
and news telemetry remain unchanged.

### LD 16 - FileBackend cannot resurrect retired file authorities

`FileBackend.query_prices()` returns the standard empty price frame and does
not inspect `data/prices`. `FileBackend.get_available_tickers("prices")` and
`FileBackend.get_available_tickers("fundamentals")` return an exact empty list
without testing, globbing, or opening the retired `data/prices` or already-
absent `data_lake/raw/ibkr_fundamentals` paths. Its price-file loaders are
removed if no remaining non-test consumer exists.

This is a deliberate capability retirement for the no-DSN file backend.
SQLite-backed DAL shapes retain price capability.

### LD 17 - Documentation cannot remain a consumer

Training help and current documentation must stop instructing users to place
or read price data under `data/prices`. Historical design/evidence documents
may retain dated paths when explicitly labeled as history.

At minimum:

- `prepare_training_data.py --help` describes its IBKR option as a direct
  Gateway daily fetch and does not name the removed collector;
- the training README removes the retired CSV inventory and stale collection
  summary;
- the current formulas, data inventory, and subscription guide describe the
  qualified SQLite authority where they discuss ArkScope valuation or stored
  prices; and
- the canonical workbench spec supersedes its parquet-price authority with the
  implemented `market_data.db` authority. Any future DuckDB/parquet price
  design requires a new reviewed data path rather than reusing deleted files.

The registered/Anthropic tool descriptions, detailed-financials docstring, and
schema comments must stop calling the retired path "IBKR real-time". OpenAI and
Anthropic wrappers continue to expose the same tool and response shape.

### LD 18 - The 300 price CSVs are discarded

The final deletion set includes:

- 225 `data/prices/15min/*.csv` files;
- 75 `data/prices/hourly/*.csv` files;
- `data/prices/collection_summary.json`; and
- the resulting empty `15min`, `hourly`, and `data/prices` directories.

The 15-minute differences are not reconciled. The unique hourly history is not
migrated. Git history, a durable archive, a new DB, and a training fixture are
not substitutes for carrying these files forward.

### LD 19 - Old DB rows leave with the same closeout

The final deletion set also includes:

- every exact manifested `financial_cache` key with prefix `metrics_` and
  suffix `_annual_y2`; and
- every row in the retired legacy `fundamentals` table; and
- the exact `market_sync_meta` row whose domain is `fundamentals`.

Other SEC, Financial Datasets, provider, and application cache rows are not
part of this deletion. The table schemas remain unless a later schema decision
explicitly retires them.

The deletion implementation must enumerate exact cache keys first and delete
by exact equality. SQL `LIKE 'metrics_%_annual_y2'` is not an execution
authority because `_` is a wildcard and could silently widen the set.

For SQLite, "deleted" means the reviewed rows no longer exist transactionally.
This is not a forensic secure-erasure claim, and EIR-006 does not run
`VACUUM` merely to shrink or overwrite a multi-gigabyte live database. DB file
size may remain unchanged.

### LD 20 - Physical deletion is a separate execution approval

Approval of this design, implementation plan, or product merge does not
authorize data destruction.

After the product cutover is merged:

1. run a fresh consumer census;
2. build an exact file-and-row manifest;
3. present coverage/difference facts and the exact destructive action;
4. obtain explicit user approval for that manifest;
5. create only a temporary rollback quarantine/snapshot;
6. delete exact paths and rows;
7. run post-delete product and canonical verification; and
8. remove the temporary rollback copy so no durable archive remains.

If the manifest finds a current consumer, an unexpected file family, a writer
repopulating old rows, or a scope beyond this design, deletion stops.

### LD 21 - No provider spend is needed

All implementation and review tests use fixture databases and provider
doubles. No IBKR, SEC, Financial Datasets, Finnhub, Polygon, or other provider
request is authorized.

The separate Financial Datasets metered-policy slice remains the owner of
spend controls and UI.

## 7. Contract Tables

### 7.1 Price selector

| Local fact | Result |
|---|---|
| valid row on required completed market date | available; latest row selected |
| only older rows exist | `no_qualified_price` |
| target day has one low-volume row | available |
| current day is before 16:30 ET | prior completed date is required |
| current day is at/after 16:30 ET | current date is required |
| weekend or exchange holiday | preceding completed date is required |
| missing/unreadable DB | `no_qualified_price`; no create |
| missing required table/columns | `no_qualified_price` |
| query error | `no_qualified_price`; no exception text |
| close is null, non-finite, or non-positive | row does not qualify |

### 7.2 Detailed financials

| Static facts | Price basis | Product result |
|---|---|---|
| available | available | static and computable dynamic fields |
| available | unavailable | static fields; all nine dynamic fields null; typed basis |
| partial | available | computable fields only; missing-input fields null |
| unavailable | available | response remains structurally valid; no fabricated ratios |
| cache hit | changed price | dynamic values change; static provider call remains avoided |

### 7.3 Authority after cutover

| Concern | Authority |
|---|---|
| price row | `market_data.db.prices`, `interval='15min'` |
| completed market date | existing market-data calendar contract |
| detailed-financials static annual facts | SEC EDGAR cache |
| fundamentals-analysis static annual facts | SEC cache, then already-enabled FD fallback |
| stored-fundamentals coverage | positive unexpired SEC annual v1 cache |
| price provenance | `valuation_price_basis` |
| full session coverage | Coverage v2, unchanged |
| old CSV values | none |
| old IBKR fundamentals rows | none |

## 8. RED-First Test Contract

The implementation plan must name exact existing and new node IDs, pin the
pre/post collection hashes, and budget every node before edits. At minimum,
independent nodes must prove the following.

### 8.1 Qualified price

1. Before 16:30 ET, today's rows do not displace the preceding completed
   market date.
2. At or after 16:30 ET, a valid row from today qualifies.
3. Weekend and exchange-holiday clocks select the preceding completed date.
4. One valid row qualifies without a 26-slot requirement.
5. Older bars do not substitute for a missing required market date.
6. Missing DB returns typed unavailable and does not create a path.
7. Unreadable DB, missing table/columns, and query failure return typed
   unavailable without leaking exception text.
8. A timestamp whose UTC date differs from its ET market date is classified by
   ET date.
9. Null, non-finite, zero, and negative closes do not qualify.
10. A known alias reaches the canonical ticker rows.

The low-volume one-row test must turn RED if the implementation is mutated to
require 26 slots. The older-bar test must turn RED if fallback to the most
recent available day is introduced.

### 8.2 Static cache and valuation

11. A populated old `metrics_*_annual_y2` row is ignored.
12. The v2 cache payload contains no price, price timestamp, price market date,
    or any of the nine dynamic valuation fields.
13. A static-cache hit with a changed qualified price changes market cap and
    the dependent ratios without a static-fundamentals provider call; the
    existing earnings-provider path remains separately doubled.
14. No qualified price preserves static fields, nulls all nine dynamic fields,
    and returns exactly `no_qualified_price`.
15. An old IBKR snapshot with million-unit market cap cannot override the SEC
    inputs or output.
16. `price * outstanding_shares` uses exact base units; adding or removing an
    erroneous `1e6` factor turns the owning node RED.
17. Static missing inputs leave only their dependent fields null.
18. `data_source` remains the static source and never reports
    `ibkr+sec_edgar`.
19. Calculator convenience and CLI paths with no explicit price never open a
    CSV/legacy fundamentals file and leave all dynamic valuation fields null.

### 8.3 Other live surfaces

20. Annual fundamentals analysis does not short-circuit on a legacy snapshot
    and still respects the existing SEC cache and FD enablement gate; existing
    `/fundamentals` route and evidence-packet tests remain in the affected-node
    ledger and pass against that result shape.
21. Peer comparison counts and names peers whose valuation price is
    unavailable while excluding null values from rankings/statistics.
22. `daily_update` price status reads fixture SQLite stats and never scans a
    price directory.
23. FileBackend returns the exact empty price-frame shape and exact empty
    price/fundamentals ticker lists without testing, globbing, or opening a
    retired directory.
24. A legacy `fundamentals` row alone cannot make market-data status, system
    status, ticker coverage, or the registered coverage tool claim stored
    fundamentals.
25. A positive unexpired SEC annual v1 cache row makes every named projection
    available, agrees with `stored=true`, and projects the payload snapshot date
    rather than cache fetch time.
26. Negative, expired, malformed, old detailed-financials, v2
    detailed-financials, and FD endpoint cache rows do not make the
    stored-SEC projection available.
27. Existing Settings, Ticker Detail, and Dashboard labels describe stored SEC
    fundamentals in both locales.
28. Ticker Detail recognizes `source_path="local_cache"` as an exact typed
    value and renders localized copy rather than the raw stable ID.
29. Retired fundamentals sync telemetry is absent from API, Settings, and the
    registered coverage tool while current price/news telemetry is unchanged.
30. Current training help, current data/formula guides, the canonical workbench
    spec, and model-visible tool descriptions no longer name the retired price
    directory, its collection summary, or "IBKR real-time" as the valuation
    input or price authority.
31. A static consumer-census test fails on any new current runtime reference to
    the retired CSV directories, old detailed-financials cache key, or legacy
    fundamentals product call.

Historical documents and the EIR-006 design/evidence files must be explicitly
excluded from the static census; current source, tests, user instructions, and
runtime configuration may not be excluded.

### 8.4 Mutation evidence

The evidence packet must preserve exact diffs and owning-node results for at
least:

- target-day fallback changed to latest available day;
- one-row presence changed to 26-slot completeness;
- ET-date comparison changed to raw UTC date;
- old cache key re-enabled;
- dynamic valuation inserted into the static cache payload;
- valuation calculation multiplied or divided by `1e6`;
- old IBKR snapshot override restored;
- FileBackend CSV read restored;
- `daily_update` changed back to directory scanning; and
- fundamentals coverage changed back to the legacy table.

Each mutation runs its owning node or smallest owning set. Restoring the
pre-mutation product SHA is mandatory before the next mutation.

## 9. Consumer-Census Contract

Before product edits and again before physical deletion, the plan must search
at least:

```text
data/prices
prices/15min
prices/hourly
collection_summary.json
_get_current_price_ibkr
metrics_.*_annual_y
dal.get_fundamentals
query_fundamentals
ibkr_fundamentals
FROM fundamentals
local_ticker_coverage
local_market_stats
get_available_tickers
get_ticker_data_coverage
market_sync_meta
```

Every current hit receives one closed verdict:

```text
rewired_current_consumer
retired_current_consumer
low_level_empty_compatibility
historical_reference
test_fixture_reference
unrelated_lexical_hit
```

Unknown is not a verdict. Any unclassified hit stops the slice.

This old-data census is not the complete affected-node ledger. Before test
counts are locked, the implementation plan must separately enumerate current
product callers of `get_fundamentals_analysis()` and identify their existing
owning tests. At minimum, the `/fundamentals` route and evidence-packet
institutional-evidence path must receive explicit ledger dispositions. This
behavior-propagation inventory does not create an eighth old-data authority or
expand the final deletion census.

The final deletion census must show:

- zero `rewired_current_consumer` entries still targeting old data;
- zero current writer capable of repopulating the retired cache/fundamentals
  families;
- no training input owner for the CSVs;
- no keep-current documentation authority or user instruction presenting the
  retired artifacts as available inputs;
- exact ownership for any remaining low-level empty compatibility method;
- no status, API, registered tool, or frontend projection using legacy
  fundamentals rows;
- system-status fundamentals ticker count agreeing with the positive SEC cache
  reader;
- stored-fundamentals coverage agreeing with the positive SEC cache reader;
  and
- no current surface projecting retired fundamentals sync telemetry.

## 10. Data-Deletion Gate

### 10.1 Manifest inputs

The final manifest records, without reading secrets:

- every exact CSV relative path, size, mtime, inode, and SHA-256;
- the exact collection-summary identity and contents classification;
- per-family file and row counts and min/max timestamps;
- the current SQLite comparison summary;
- the exact ticker-alias rows and deterministic comparison implementation
  identity used to derive the raw and canonical views;
- exact old cache keys and row metadata;
- exact legacy fundamentals ticker/snapshot metadata;
- exact retired fundamentals sync-row metadata;
- database path/inode/size/mtime/SHA before deletion;
- saved scheduler enablement/cadence and the active market-writer process census;
- current consumer-census SHA; and
- the reviewed product and test commit identities.

The manifest must repeat the known decision-relevant facts:

- the raw-ticker diagnostic view contained 2,314,293 unique keys and reported
  161 SQLite differences;
- after current aliases, the canonical deletion-authority view contained
  2,298,763 unique keys, all represented in SQLite, with 176 conflicting
  duplicate keys and 43 SQLite differences left unreconciled: 23 volume-only
  and 20 including OHLC;
- the hourly 2023 rows were unique locally; and
- the user chose discard without migration.

The final manifest must rederive both views from normalized absolute
timestamps. Only the canonical view decides deletion admission. A raw-view
match cannot substitute for it, and any change to the alias input or comparison
method between review and execution stops for re-review.

### 10.2 Execution shape

After explicit approval:

1. preserve the saved scheduler state, stop the sidecar/scheduler and other
   market-data writers, and prove no process holds a writable DB connection;
2. stop if the production databases or retired price-artifact set changed from
   the approved manifest;
3. move exact CSV and collection-summary paths to a temporary same-filesystem
   quarantine and create a verified temporary full-row snapshot of only the DB
   rows approved for deletion while writers remain stopped;
4. delete matching cache rows, all legacy fundamentals rows, and the exact
   retired fundamentals sync row in one explicit SQLite transaction;
5. verify no product path reads the quarantine;
6. run focused, canonical, and provider-free read-only production checks with
   scheduler/writers still disabled;
7. verify old rows are absent and no current cache family changed;
8. on any failure, restore and verify the exact file quarantine and target-row
   snapshot in one explicit transaction before any writer restarts;
9. on success, permanently remove the exact quarantine and row snapshot;
10. restart the application with the exact saved scheduler
    enablement/cadence; and
11. record the deletion evidence without retaining data contents.

No glob may be used for destructive execution after manifest approval. The
approved manifest is the exact path/row authority.

### 10.3 Stop conditions

Deletion stops if:

- any file or DB identity differs from the approved manifest;
- any old-data consumer remains;
- any old-data writer remains;
- the transaction would affect a non-retired cache key;
- a CSV outside the two approved families appears;
- production activity makes a safe transaction or verification ambiguous;
- a market-data writer cannot be quiesced or the saved scheduler state cannot
  be restored exactly;
- the temporary rollback copy cannot be verified;
- focused or canonical verification is non-green; or
- the user has not separately approved the exact destructive manifest.

## 11. Verification and Rollout

### 11.1 Development boundary

- fixture DBs only;
- no provider credentials;
- no provider calls;
- no production DB writes;
- RED before product GREEN;
- exact collection identity before and after;
- focused tests in the managed sandbox where compatible; and
- canonical admission under the established native wakeup-probe boundary.

### 11.2 Product merge

Before merge:

- every Section 8 contract is green;
- the consumer census is closed;
- current price collection, Coverage, current quote, SEC cache, FD gate, and
  unrelated financial-cache tests remain green;
- existing detailed-financials earnings-surprise and upcoming-earnings
  contracts remain green under provider doubles;
- existing Settings and Ticker Detail contracts remain green in both locales;
- product and test node deltas match the predeclared ledger; and
- no data file or production row changed.

After merge:

- rerun exact collection and canonical admission;
- perform a direct read-only production selector observation for a ticker with
  a qualified price; do not invoke the full detailed-financials tool;
- perform a fixture-only unavailable request;
- rerun the fixture/provider-double contract proving old cache keys are not read
  even while still present;
- confirm `daily_update` reports SQLite price facts; and
- leave all physical old data untouched until the deletion gate.

### 11.3 Physical closeout

EIR-006 closes only when:

1. the product cutover is merged and verified;
2. the fresh deletion census is clean;
3. the user approves the exact destructive manifest;
4. 225 15-minute CSVs, 75 hourly CSVs, the stale collection summary, and the
   empty retired directories are absent;
5. retired old detailed-financials cache rows are absent;
6. legacy fundamentals rows are absent;
7. retired fundamentals sync telemetry is absent;
8. no durable data archive was created;
9. canonical admission is green; and
10. read-only production behavior remains truthful.

If the product cutover is complete but deletion is deferred, EIR-006 remains
open with a named deletion owner and revalidation trigger. It may not silently
become an ownerless cleanup note.

## 12. Protected Boundaries

The implementation may not:

- change price collector scheduling, provider fallback, or partial outcomes;
- change Financial Datasets spend policy or enablement semantics;
- issue a provider request during tests;
- change the generic quote tool;
- change detailed-financials earnings-surprise or upcoming-earnings semantics;
- introduce a second market calendar;
- treat a valuation price as proof of full session coverage;
- let a legacy fundamentals row establish stored-product coverage;
- read old cache keys for compatibility;
- migrate the hourly CSVs;
- retain a durable archive after deletion;
- drop a DB schema without a separate decision;
- edit Tranche B scoring behavior;
- delete production data before the explicit manifest approval; or
- weaken the canonical green baseline to accommodate the change.

## 13. Stop Conditions for Planning and Implementation

Stop and amend this design or its implementation plan if:

1. a current runtime consumer of the hourly CSVs is found;
2. training is proven to consume one of the 300 CSVs;
3. the existing completed-session calendar cannot be reused without changing
   its product semantics;
4. qualified price selection would require a provider call;
5. old cache data is required to preserve a current non-price capability;
6. removing the annual snapshot short circuit changes FD spend behavior;
7. the response cannot carry typed price provenance through the registered
   tool surface;
8. a frontend owner beyond the named Settings, Ticker Detail, and Dashboard
   projections is found;
9. product code would need to guess units;
10. test node identity or collection changes outside the reviewed ledger;
11. a provider request occurs;
12. production data changes during product implementation;
13. the consumer census has an unknown verdict;
14. the deletion manifest, canonicalization input, or comparison method differs
    between review and execution;
15. any destructive step lacks explicit user approval; or
16. the managed sandbox is used as canonical admission despite a failing
    wakeup probe.

## 14. Next Gate

Independent full-document review returned GREEN with zero findings at
`124622bc`.

Independent review of
`docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md` is next.
No product edit, cache-row deletion, CSV movement, or provider request is
authorized before that plan review clears its own next gate. Physical deletion
still requires the later exact manifest and separate explicit user approval.
