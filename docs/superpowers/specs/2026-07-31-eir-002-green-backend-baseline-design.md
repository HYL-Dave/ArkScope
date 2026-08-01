# ArkScope EIR-002 Green Backend Baseline Design

> **Status: TASK 7 BOUNDED AMENDMENT - INDEPENDENT REVIEW NEXT**
>
> **Date:** 2026-07-31
> **Grounding commit:** `3092fb4128dad9a2579f267e915519fa9cdf648c`
> **Reviewed design commit:** `20d4e7e2`
> **Scope:** the exact 27-node native backend non-passing set owned by
> `EIR-002`, its obsolete ambient-data assumptions, and the test seams needed
> to establish a green backend baseline

## 1. Purpose

The backend suite has carried a known non-green baseline through multiple
product slices. The current native census is stable and exact:

```text
4739 collected
27 failed
4640 passed
72 skipped
non-passing node-set SHA-256:
7aafce5d2cba923480cc1fb6221bce4f5a33e0bf61c06cf94227cafefe227f15
```

Twenty-six failures were introduced together on 2026-02-05 as "real data"
tests. They assume that historical files under the repository remain populated
forever. One later failure is a test clock that crossed its 30-day window.
None of the 27 failures proves that a current collector stopped writing new
data.

The goal is not to preserve those historical files as a permanent test
fixture. The goal is to make current product contracts deterministic:

- remove nine tests whose positive ambient-data premise has retired;
- retain and hermetically rewire seventeen API, tool, and agent contracts;
- repair one fixed-date round-trip contract;
- preserve every current production authority and every unrelated passing
  node; and
- end with a native full backend suite that has zero non-passing nodes.

This is a test-authority repair. It does not rewrite product behavior to satisfy
old tests.

## 2. Grounded Current State

### 2.1 Failure age and shape

The exact 27-node set has two origins:

| Origin | Date | Nodes | Current diagnosis |
|---|---:|---:|---|
| `74433f84` | 2026-02-05 | 26 | ambient positive-data assumptions copied through DAL, API, tools, and agents |
| `e6d99342` | 2026-06-26 | 1 | a fixed `2026-06-20` record queried through a moving default 30-day window |

The 26 old failures divide by data domain, not by 26 independent bad records:

| Domain | DAL | API | Tools | Agents | Total |
|---|---:|---:|---:|---:|---:|
| Prices | 4 | 4, including `/status` | 3 | 1 | 12 |
| News | 2 | 3 | 3 | 1 | 9 |
| Fundamentals | 3 | 1 | 1 | 0 | 5 |
| **Total** | **9** | **8** | **7** | **2** | **26** |

The tests read data. They do not invoke the price, news, or fundamentals
collectors and do not prove that a particular historical crawl was malformed.

### 2.2 Historical inputs are not current authorities

The following observations were taken on 2026-07-31. They are lineage evidence,
not acceptance constants:

- `data/news/ibkr_scored_final.parquet` contains 52,755 rows and stops at
  2025-12-24.
- `data/news/polygon_scored_final.csv` contains 107,640 rows and stops at
  2026-01-03.
- `data/prices/15min/` contains 225 CSV files for 150 tickers, and its global
  latest timestamp is 2026-07-02.
- `data/prices/hourly/` contains 2023-era snapshots for 75 tickers.
- `data_lake/raw/ibkr_fundamentals/`, historically described as containing 131
  JSON snapshots, no longer exists.

The current local authority is different:

| Store | Dated read-only observation |
|---|---|
| `market_data.db.prices` | 2,402,420 rows, 151 tickers, through 2026-07-30 |
| `market_data.db.news` | 436,459 rows, three sources, through 2026-07-31 |
| `market_data.db.financial_cache` | 44 rows for 24 tickers, fetched through 2026-07-29 |

Current collectors write SQLite and normalized news paths. `data/news/raw/`
remains a current output and is protected. The scored-final files and old price
CSVs are historical inputs, not current collection-health witnesses.

### 2.3 Current runtime and old tests choose different backends

The old tests instantiate `DataAccessLayer()` or
`DataAccessLayer(base_path=project_root)`, which selects `FileBackend`. Their
module docstrings explicitly say they run against real repository data.

The current app and API construct `DataAccessLayer(db_dsn="auto")`, whose local
composite backend reads current SQLite authorities. Current backend contracts
already have hermetic coverage in:

- `tests/test_sqlite_backend.py`;
- `tests/test_fundamentals_sec_cache.py`;
- the stored-fundamentals contracts in `tests/test_api.py`;
- `tests/test_news_scores.py` while the score contract remains live; and
- `tests/test_db_backend.py` for backend selection and empty-schema behavior.

Creating a new checked-in `data_lake/` or copying old CSV/parquet snapshots into
fixtures would therefore test a retired storage premise and make it look
current again.

### 2.4 Canonical admission boundary

The managed sandbox is not a valid full-suite boundary for cross-thread asyncio
wakeups. `EIR-005` closed that issue with a pinned wakeup probe. At the
grounding commit:

```text
canonical collection: 4739
collection SHA-256:
a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd

focused five-file collection: 132
focused SHA-256:
76f8f087a24f2ff2934274cbbd1711d203c9dbe7056ba4bf5d6022b2d1a03f9c
```

Canonical and API admission must run natively after the pinned wakeup probe.
Focused non-ASGI test development may run in the managed sandbox.

### 2.5 A separate live product defect was exposed

The investigation found a live chain that is not one of the 27 test failures:

```text
registered get_detailed_financials agent tool
  -> FinancialMetricsCalculator.get_metrics_dict()
  -> get_valuation_metrics()
  -> _get_current_price_ibkr()
  -> latest close in data/prices/{15min,hourly} CSV
```

`_get_current_price_ibkr()` calls that close "current". On the observed tree,
the newest old CSV timestamp is 2026-07-02. If the SEC metrics cache misses and
IBKR fundamentals do not provide market cap, that old close can calculate
market cap and related valuation ratios, which may then be cached for 90 days.

This is a product-truth defect: the code knows only that it found the last row
in a historical file, not that the price is current. It is promoted separately
as `EIR-006`. This design neither fixes it nor permits physical deletion of the
price CSVs before it is resolved.

## 3. Decisions

### LD 1 - Retire obsolete data premises, not product capabilities

The nine failing `tests/test_data_access.py` positive-data nodes are removed.
They are not skipped, archived as executable tests, or made green by restoring
historical data.

Git history preserves their implementation. The decision table in Section 4.1
preserves what each node used to claim and identifies the current owner of any
behavior that remains relevant.

### LD 2 - Preserve all seventeen live-surface node identities

The eight API, seven tool, and two agent nodes in Section 4.2 remain collected
under their exact current node IDs. Their assertions are reviewed against the
current user-visible behavior and run through deterministic data injected at
the same seam used by production:

- tools and agents receive an explicit `DataAccessLayer`;
- API routes receive an `app.dependency_overrides[get_dal]` value; and
- route registration, HTTP status, JSON serialization, tool dispatch, and
  result-schema behavior remain real.

No test may patch the function it is supposed to prove.

### LD 3 - Hermetic data must express current shapes

Test data is small and deterministic. It may seed temporary SQLite or use a
minimal backend double, but it must return the same `DataFrame`, schema model,
or dictionary shape as the current backend boundary.

Each mocked seam is anchored by at least one existing current-backend test.
The implementation plan must name those anchors. A double may not invent a
second product contract.

No provider key, network request, production database, repository CSV,
repository parquet, or `data_lake/` directory is required.

### LD 4 - Do not change product code in EIR-002

Owned implementation files are limited to:

- `tests/test_data_access.py`;
- `tests/test_api.py`;
- `tests/test_tools.py`;
- `tests/test_agents.py`;
- `tests/test_app_records_store.py`; and
- EIR-002 authority, plan, and evidence documents.

If a retained node cannot be made truthful through an existing injection seam,
stop and amend the design. Do not add a product seam merely to make this batch
convenient.

### LD 5 - Fix the date contract with an explicit clock

`test_report_insert_query_roundtrip` keeps its node ID and all round-trip
assertions. It passes `today="2026-06-21"` to `query_reports()` so the inserted
2026-06-20 record remains inside a deterministic 30-day window.

The test must not widen `days`, move the fixture date relative to wall clock,
or remove the query-window behavior.

### LD 6 - Keep the score contract coherent until its atomic retirement

The current sentiment API/tool nodes remain green under a deterministic scored
article while the score reader and routes still exist. This does not reaffirm
per-article scoring as a future product direction.

The reviewed scripts-retirement decision owns the later atomic score-line
retirement. When that tranche removes the score readers and routes, their tests
leave in the same reviewed change. EIR-002 does not partially retire that
contract early.

### LD 7 - Physical data deletion is a later, separately approved action

This slice does not delete, move, archive, or rewrite:

- old price CSVs;
- scored-final news files;
- `data/news/raw/`;
- `market_data.db`; or
- any production or user data.

Before old price CSV deletion, `EIR-006` must close and a read-consumer census
must prove no live path still depends on them. Any physical deletion requires a
fresh manifest, the established backup/archive decision, and explicit user
approval. The absent `data_lake/` directory is not recreated.

### LD 8 - Blank environment is the test contract

The final suite must pass without provider credentials and without copied
repository data. Adding a key, mount, or historical file to make a node pass
changes the question and is not an EIR-002 repair.

### LD 9 - Keep canonical admission blank and repair the exposed protected node

Task 7 proved that the merged main worktree is not the blank environment
defined by LD 8. Its ignored `config/.env` is read directly at import time by
`tests/test_db_backend.py`, enabling nineteen PostgreSQL integration nodes that
remain skipped in the reviewed branch worktree. The production scheduler also
writes ignored databases in the main worktree while a long suite is running.
Neither state is an admissible canonical input.

The data-bearing run exposed one independently reproducible stale assertion:
`tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_via_dal`
expects `FundamentalsResult.found`, but that field has never existed in the
schema. The current typed absence fact is `data_source == "none"`. This node
must keep its exact identity and change only that assertion. No product code,
skip rule, fixture, provider behavior, or other integration node may change.

Canonical merged admission must run from a fresh worktree at the exact merged
master commit with:

- no `config/.env`;
- an existing but empty repository `data/` directory;
- no copied production or historical data; and
- one explicit `node_modules` symlink to the reviewed main-worktree install,
  pinned by target path, tracked and installed lockfile SHAs, Node version,
  and required `jsdom` version; and
- the same pinned native wrapper, reporter, Node.js, and wakeup probe.

The `node_modules` link is a test-toolchain dependency, not an admission data
input. No other symlink into the production root is allowed.

The canonical ledger remains `4730 collected / 4658 passed / 72 skipped`.
The main worktree's data-bearing owning node is a supplemental proof that the
stale assertion is repaired; its different pass/skip projection is not a
substitute for canonical admission. This amendment additionally owns only
`tests/test_db_backend.py` and the EIR-002 authority documents.

## 4. Exact Node Disposition

### 4.1 Nine nodes removed with explicit successor ownership

| Removed node | Retired premise | Current behavior owner |
|---|---|---|
| `tests/test_data_access.py::TestNews::test_get_news_all` | scored-final repository files must contain positive rows forever | `tests/test_sqlite_backend.py::test_query_news_unscored` owns current local-news reads; retained API/tool news nodes own DAL conversion and user-facing shape |
| `tests/test_data_access.py::TestNews::test_get_news_source_breakdown` | ambient old files must produce a non-empty source map | retained `tests/test_tools.py::TestNewsTools::test_get_ticker_news` must assert the seeded `source_breakdown`; current SQLite news tests own source-filtered reads |
| `tests/test_data_access.py::TestPrices::test_get_prices_15min` | old NVDA CSVs must exist | `tests/test_sqlite_backend.py::test_native_15min_passthrough` plus retained API/tool 15-minute nodes |
| `tests/test_data_access.py::TestPrices::test_get_prices_hourly` | old AAPL CSVs must exist | `tests/test_sqlite_backend.py::test_rollup_1h` |
| `tests/test_data_access.py::TestPrices::test_get_prices_daily_resampled` | old NVDA CSVs must exist | `tests/test_sqlite_backend.py::test_rollup_1d` |
| `tests/test_data_access.py::TestPrices::test_available_price_tickers` | repository CSV inventory must exceed 50 tickers | `tests/test_sqlite_backend.py::test_get_available_tickers`, `test_available_tickers_routing`, and the retained `/status` contract with deterministic counts |
| `tests/test_data_access.py::TestFundamentals::test_get_fundamentals` | removed IBKR fundamentals JSON must contain NVDA market cap | current SQLite/cache contracts plus retained fundamentals API/tool nodes |
| `tests/test_data_access.py::TestFundamentals::test_fundamentals_has_ratios` | removed IBKR fundamentals JSON must contain ratios | retained fundamentals API/tool nodes use a deterministic current result; SEC/cache behavior remains owned by `tests/test_fundamentals_sec_cache.py` |
| `tests/test_data_access.py::TestFundamentals::test_available_fundamentals_tickers` | removed directory inventory is a product authority | `tests/test_sqlite_backend.py::test_get_available_tickers` and `test_available_tickers_routing` own current local availability; the old directory-inventory capability retires |

This is node removal, not broad deletion of `tests/test_data_access.py`.
Surviving protocol, configuration, empty-result, cache, and schema nodes remain
untouched. The later physical-data retirement must audit those survivors again
against its own final tree.

### 4.2 Seventeen live nodes retained and rewired

The following IDs survive exactly:

| Domain | Node | Required deterministic proof |
|---|---|---|
| Prices | `tests/test_api.py::TestHealth::test_status` | HTTP 200, status/tool count, and exact seeded data-source count |
| Prices | `tests/test_api.py::TestPriceEndpoints::test_get_prices` | serialized 15-minute bars for NVDA |
| Prices | `tests/test_api.py::TestPriceEndpoints::test_price_change` | ticker, bar count, and calculated change fields |
| Prices | `tests/test_api.py::TestPriceEndpoints::test_sector_performance` | seeded sector members produce aggregate/best/worst shape |
| Prices | `tests/test_tools.py::TestPriceTools::test_get_ticker_prices` | `PriceQueryResult` conversion and bars |
| Prices | `tests/test_tools.py::TestPriceTools::test_get_price_change` | period statistics from deterministic bars |
| Prices | `tests/test_tools.py::TestPriceTools::test_get_sector_performance` | deterministic multi-ticker aggregation |
| Prices | `tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_price_change` | real dispatch and serialized tool result |
| News | `tests/test_api.py::TestNewsEndpoints::test_get_news` | HTTP/JSON news result for NVDA |
| News | `tests/test_api.py::TestNewsEndpoints::test_get_news_sentiment` | current scored-summary response while the route remains live |
| News | `tests/test_api.py::TestNewsEndpoints::test_search_news` | deterministic keyword search result |
| News | `tests/test_tools.py::TestNewsTools::test_get_ticker_news` | `NewsQueryResult`, count, ticker, and source breakdown |
| News | `tests/test_tools.py::TestNewsTools::test_get_news_sentiment_summary` | scored count, mean, and ratio calculations |
| News | `tests/test_tools.py::TestNewsTools::test_search_news_by_keyword` | keyword result through the tool boundary |
| News | `tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news` | real dispatch and serialized tool result |
| Fundamentals | `tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals` | HTTP/JSON current fundamentals shape with deterministic market cap |
| Fundamentals | `tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis` | `FundamentalsResult` conversion through the live tool |

An assertion may change only when the old assertion measured ambient inventory
rather than product behavior. The replacement must state the deterministic
fact explicitly; merely asserting "non-empty" against an opaque double is not
enough.

### 4.3 One date-rot node retained

`tests/test_app_records_store.py::test_report_insert_query_roundtrip` remains
the same node and continues to prove:

- insert returns an integer ID;
- query returns the parity column set;
- scalar fields round-trip;
- JSON tickers return as a list; and
- `created_at` preserves its format.

Only its clock input becomes explicit.

## 5. Hermetic Fixture Contract

### 5.1 Current-shape anchors

The implementation plan must map each fixture family to current tests:

| Fixture family | Minimum real-shape anchors |
|---|---|
| Price frame and rollups | `test_native_15min_passthrough`, `test_rollup_1h`, `test_rollup_1d` |
| Available tickers | `test_get_available_tickers`, `test_available_tickers_routing` |
| News rows/search/scores | `test_query_news_unscored`, current search tests, and `test_query_news_surfaces_normalized_scores_from_both_legacy_maps` while scores remain live |
| Fundamentals | `test_query_fundamentals_latest_snapshot`, stored-fundamentals API tests, and `tests/test_fundamentals_sec_cache.py` |

The anchors remain real backend tests. The 17 nodes prove the consumers above
that boundary.

### 5.2 Scope of overrides

- Dedicated fixtures or helpers must not be named `test_*`.
- API overrides are installed only for the owning tests and always removed.
- A module-wide override may not silently alter unrelated passing API nodes.
- Tool and agent tests receive a dedicated deterministic DAL instead of
  changing the existing module-wide ambient fixture for unrelated nodes.
- Tests must fail if the consumer stops forwarding ticker, interval, days,
  keyword, or sector inputs required by their current contract.
- No fixture may derive its expected value from the implementation value it is
  meant to test.

### 5.3 No hidden provider work

The fundamentals fixture must not call SEC EDGAR, Financial Datasets, Finnhub,
IBKR, or another provider. Provider integration belongs to provider-specific
tests. These nodes prove API/tool behavior over a current result shape.

## 6. Accounting

### 6.1 Exact node ledger

| Collection | Base | Added | Removed | Target |
|---|---:|---:|---:|---:|
| Canonical backend | 4,739 | 0 | 9 | 4,730 |
| Five owned test files | 132 | 0 | 9 | 123 |

The implementation plan must construct and pin the two target collection
hashes before edits. Expected final runtime accounting is:

```text
4658 passed
72 skipped
0 failed
4730 total
```

The 17 rewire IDs and the one date-fix ID must each occur exactly once before
and after. No test rename, skip, xfail, helper collection, or parametrization
expansion is permitted without a reviewed amendment.

### 6.2 Reverse-TDD accounting

The RED state already exists. For each implementation family:

1. record its exact failing IDs before the change;
2. change only that family;
3. prove exactly those IDs leave the non-passing set;
4. prove no other known failure changes classification; and
5. prove no previously passing node becomes non-passing.

Recommended independent families are:

| Family | Existing failures resolved |
|---|---:|
| retire nine ambient DAL nodes | 9, with collection `-9` |
| rewire seven news consumers | 7 |
| rewire eight price consumers | 8 |
| rewire two fundamentals consumers | 2 |
| fix one app-record clock | 1 |

Each family may be its own commit. The final plan decides commit boundaries but
may not mix product changes into them.

## 7. Verification Contract

### 7.1 Focused development

Non-ASGI focused tests may run in the managed sandbox. API tests that enter
FastAPI/AnyIO and every canonical census run must use the native boundary.

The implementation plan must include:

- the pinned `EIR-005` wakeup probe before every native canonical run;
- focused collection identity before and after;
- exact failed-node set comparisons after each family;
- the five owned test files as one focused gate; and
- a native canonical full run from a blank credential/data environment.

### 7.2 Final admission

Closure requires all of the following:

1. canonical collection is exactly 4,730 and matches its planned SHA;
2. focused collection is exactly 123 and matches its planned SHA;
3. the 17 live IDs and one date ID survive exactly once;
4. the nine retired IDs are absent;
5. the native full suite reports zero failed/error nodes;
6. no provider credential or historical data mount is present;
7. no product file changed;
8. protected current backend tests remain green; and
9. the data-bearing `test_fundamentals_via_dal` node passes against the current
   typed absence shape; and
10. `EIR-002` receives commit, command, and result closure evidence.

## 8. Protected Boundaries And Out Of Scope

This design does not authorize:

- changes under `src/`, `data_sources/`, or the frontend;
- a new runtime backend or dependency-injection API;
- FileBackend product changes;
- restoring `data_lake/`;
- network/provider calls;
- database or schema changes;
- production data reads or writes for acceptance;
- score-reader, score-route, or score-table retirement;
- scripts retirement;
- stale-price behavior changes owned by `EIR-006`;
- physical deletion or archive operations; or
- changes to current collection, scheduler, Coverage, or provider behavior.

## 9. Stop Conditions

Stop and amend the design if any one occurs:

1. one of the nine removed nodes is the only owner of a live behavior and
   Section 4.1's named successor cannot prove it;
2. a retained node requires weakening a user-visible contract merely to pass;
3. a provider key, network call, production database, or historical repository
   file is needed;
4. an existing injection seam cannot express the current result shape;
5. a product defect is needed to make a retained node truthful;
6. the canonical 27-node set or its SHA differs before edits;
7. collection accounting differs from exact `-9/+0`;
8. a current backend anchor becomes non-passing;
9. a score consumer is partially removed before its atomic retirement;
10. API admission is attempted in the known-incompatible sandbox; or
11. a physical data deletion is proposed without its own manifest and explicit
    approval.

## 10. Completion And Handoff

After independent design review, a RED-first implementation plan will pin
target node hashes, exact fixture shapes, family commands, native admission
commands, protected paths, and evidence accounting.

EIR-002 closes only when the 4,730-node native suite is green. `EIR-006`
continues independently until the valuation path stops presenting an
unqualified historical close as current. Root scripts retirement follows the
green baseline and retains its separate authority and deletion approvals.
