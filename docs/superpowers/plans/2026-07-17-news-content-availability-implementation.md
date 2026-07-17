# NEWS Content Availability Unit 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute this plan task by task. Use
> `superpowers:test-driven-development` for every behavior change and
> `superpowers:verification-before-completion` before review-ready claims.
> Steps use checkbox syntax for tracking; completed steps become `- [x]`.

> **Status:** DRAFT FOR INDEPENDENT PLAN REVIEW. Implementation has not
> started. Do not create the implementation worktree or edit product code until
> this plan is review-cleared.

**Goal:** Let the market NEWS feed filter and label `full`, `headline_only`,
and `unknown` content honestly, while distinguishing a real scheduled recovery
path from a terminal headline-only result and preserving the current legacy
feed/search authority.

**Architecture:** Add one code-reviewed classification module shared by pure
Python behavior and generated SQL expressions. The existing read-only
`SqliteBackend.query_news_feed()` dynamically joins whichever explicit legacy
migration/projection maps exist, derives content state before SQL
facets/pagination, and degrades missing normalized evidence to `unknown`.
`content` propagates additively through the existing backend -> DAL -> FastAPI
route. The market NEWS toolbar consumes the additive DTO, while an old sidecar
with missing fields stays on `all` and renders no guessed badge. No normalized
schema, writer, retry worker, entitlement, scheduler, or Seeking Alpha behavior
changes.

**Tech Stack:** Python 3.11, SQLite read-only queries, FastAPI/Pydantic,
pytest, React 18.3, TypeScript 5.5, Vitest/jsdom, and the existing local-first
NEWS feed.

## Authority, Base, and Exact Accounting

- Approved design authority:
  `docs/superpowers/specs/2026-07-17-news-content-availability-design.md`.
- Behavioral/A-B base: `012dc69` (`docs: approve news content availability
  design`). That commit is docs-only over the current product code.
- Current focused backend baseline, re-run on 2026-07-17:

  ```text
  pytest -q tests/test_sqlite_backend.py tests/test_news_pg_unreachable.py \
    tests/test_api.py::TestNewsFeed \
    tests/test_db_backend.py::test_retired_pg_domain_methods_do_not_query_dropped_tables
  75 passed in 6.07s
  ```

- Current canonical backend baseline from the immediately preceding reviewed
  merge is `4359` collected with `4248 passed / 30 failed / 74 skipped / 7
  errors` and `18 warnings`; those non-passing families are pre-existing.
- Current frontend baseline is `55 files / 527 tests`.
- Reviewed target accounting is exactly:
  - backend `+19/-0`: `16` nodes in new
    `tests/test_news_content_availability.py`, `2` nodes in new
    `tests/test_news_feed_content_route.py`, and `1` node added to
    `TestNewsFeed`;
  - focused backend `75 -> 94`;
  - canonical backend collect `4359 -> 4378` and, if existing families remain
    identical, passed `4248 -> 4267`;
  - frontend `+6/-0` in one new `News.test.tsx`, producing `56 files / 533
    tests`.
- Existing exact-shape tests may be evolved additively but must not be removed
  or renamed. Any node-ID delta other than exact `+19/-0` backend and `+6/-0`
  frontend is a stop condition.
- The user's unrelated modification in `config/tickers_core.json` is outside
  this unit. Never copy, stage, revert, rewrite, or include it in a commit.

## Implementation Ledger (2026-07-17)

- Behavioral A/B base: `012dc69`.
- Review-cleared branch base: `ef733c3`.
- Branch/worktree: `codex/news-content-availability-unit-2` at
  `/tmp/arkscope-news-content-availability`.
- Worktree setup required the repository's existing `git-crypt` key in the
  linked worktree git-dir before checkout; tracked files remained clean and
  the main worktree's BTSG edit was never copied.
- Baselines re-run before RED: focused backend `75 passed`; full backend
  `4359 collected`; frontend `55 files / 527 tests`; TypeScript typecheck PASS.
- Read-only real-DB baseline medians over five warm runs were `17.3ms` (7
  days), `84.2ms` (30 days), and `765.6ms` (3650 days), with dynamic totals
  `14,046 / 53,685 / 408,327`. These are diagnostics, not acceptance
  constants.
- Task 1 RED was the required collection error
  `ModuleNotFoundError: src.news_content_availability`. The minimal shared
  classifier/SQL authority then passed exactly `10` tests.
- Task 2 RED retained the ten pure passes and produced exactly six failures:
  missing `content_counts`/item fields or the unsupported `content` keyword.
  Dynamic dual/single/no-map SQL classification then passed the new file at
  `16/16`; the combined owner plus existing SQLite backend is `84 passed`.
- Task 3 RED produced exactly three failures: the route and local compatibility
  backend rejected the new `content` keyword, while the HTTP route accepted an
  invalid value with `200`. The additive route/DAL/backend/smoke propagation,
  typed validation, and full empty-response shape then passed the exact focused
  gate at `94 passed`.

## Locked Decisions

1. **Derived at read time only.** Add no availability column, cache, table,
   trigger, migration, repair job, or background reconciliation.
2. **Two independent axes.** `content_availability` comes from body evidence;
   `content_recovery` additionally requires a real code-reviewed source
   recovery path.
3. **V1 recovery set is exactly IBKR.** Finnhub/Polygon `pending` or `failed`
   is `headline_only + terminal`, because no scheduled per-article body caller
   exists for those sources. Do not infer capability from age, URL, provider
   ID, status, attempts, or database contents.
4. **One classification authority.** A new pure module owns the six-state
   mapping, exact source capability set, fresh zero-count shape, and SQL CASE
   generation. Python and SQL tests must prove they cannot drift.
5. **Explicit maps only.** Resolve legacy identity solely through
   `news_legacy_migration_map` and `news_legacy_projection_map`, with migration
   map first under `COALESCE`. Never guess by title, URL, ticker, time, or row
   order.
6. **Partial schema is compatible.** Join each map only if it exists. If the
   normalized article/body core is absent, both maps are absent, a map row has
   no article, or a body row is absent, that affected feed row is `unknown`.
   A valid legacy feed must remain available.
7. **SQL-before-pagination.** The selected content predicate participates in
   `total`, source facets, day facets, and item selection before
   `LIMIT/OFFSET`. Python post-filtering is forbidden.
8. **Content facet excludes only itself.** `content_counts` respects search,
   ticker, source, and days, but intentionally ignores the current `content`
   selector so the toolbar continues to show the other available cohorts.
9. **Deterministic page order.** Browse uses
   `published_at DESC, news.id DESC`; FTS search keeps BM25 first and then uses
   `published_at DESC, news.id DESC`. The ID tie-breaker is the only deliberate
   ordering refinement.
10. **Additive API.** `content` defaults to `all`; invalid values receive
    FastAPI's typed `422`. Every new-backend response includes fresh
    `content_counts`; every item includes both derived fields.
11. **Reverse version skew is honest.** If a new frontend receives no
    `content_counts`, it hides the content filter, restores internal selection
    to `all`, and renders no content badge. Missing item fields are not treated
    as `headline_only`.
12. **Presentation is informational.** `full` has no badge;
    `headline_only + retryable` displays `僅標題 · 內文待處理`;
    `headline_only + terminal` displays `僅標題 · 來源未提供內文`;
    explicit `unknown` displays `內文狀態不明`.
13. **Market mode only.** Seeking Alpha request shape, filtering, rows, and
    persistence remain byte-identical. The market selection may remain in
    memory while viewing SA but is never sent to the SA endpoint.
14. **No recovery action.** Add no retry button, retry timer, provider article
    ID, raw body status, attempts, provider diagnostics, polling, toast, or
    `aria-live` region.
15. **No retry/runtime drift.** Normalized schema, writer, store, IBKR worker,
    provider adapter, entitlement policy, scheduler cadence, and body budgets
    are byte-identical to the behavioral base.

## Required Shared Interface

Create `src/news_content_availability.py` with this public surface:

```python
from typing import Literal

ContentAvailability = Literal["full", "headline_only", "unknown"]
ContentRecovery = Literal["retryable", "terminal"]
ContentFilter = Literal["all", "full", "headline_only", "unknown"]

RECOVERY_CAPABLE_BODY_SOURCES = frozenset({"ibkr"})

def classify_news_content(
    body_status: str | None,
    source: str | None,
) -> tuple[ContentAvailability, ContentRecovery | None]: ...

def news_content_sql(
    body_status_sql: str,
    source_sql: str,
) -> tuple[str, str]: ...

def empty_content_counts() -> dict[str, int]: ...
```

`news_content_sql()` receives internal SQL expressions chosen by
`SqliteBackend`, never request/user input. It returns one availability CASE and
one recovery CASE generated from the same status/source constants used by the
pure function. `empty_content_counts()` returns a new mutable dictionary each
call with all three keys at zero.

The exhaustive behavior is:

```text
fetched                              -> full          / null
pending|failed + source in {ibkr}   -> headline_only / retryable
pending|failed + any other source   -> headline_only / terminal
empty|unavailable|expired           -> headline_only / terminal
missing/unrecognized evidence       -> unknown       / null
```

## Required Backend/API Shape

The additive route is:

```text
GET /news/feed?content=all|full|headline_only|unknown
```

Every new-backend response shape, including unavailable/strict fallback, is:

```python
{
    "available": bool,
    "items": list,
    "total": int,
    "sources": dict,
    "days": dict,
    "content_counts": {
        "full": int,
        "headline_only": int,
        "unknown": int,
    },
}
```

Each item additionally carries:

```python
{
    "content_availability": "full" | "headline_only" | "unknown",
    "content_recovery": "retryable" | "terminal" | None,
}
```

`content_counts` is computed with the common non-content WHERE clause. The
selected `content` predicate is then added to the separate total/source/day/item
queries. Do not calculate any of these values from the returned page.

## File Map

- Create `src/news_content_availability.py`: pure mapping, capability set,
  generated SQL CASE expressions, and fresh zero facet.
- Modify `src/tools/backends/sqlite_backend.py`: dynamic normalized-map joins,
  SQL classification/filter/facet/item projection, deterministic tie-breaker.
- Modify `src/tools/backends/local_market_backend.py`: propagate `content` and
  preserve the additive full fallback shape.
- Modify `src/tools/backends/db_backend.py`: retired compatibility method accepts
  `content` and returns the additive empty shape.
- Modify `src/tools/data_access.py`: propagate `content` and return the
  additive FileBackend fallback shape.
- Modify `src/api/routes/news.py`: typed query parameter and propagation.
- Modify `src/smoke/pg_unreachable_e2e.py`: direct-route adapter explicitly
  passes parsed `content`; it must not accidentally pass a FastAPI `Query`
  object.
- Create `tests/test_news_content_availability.py`: `16` pure/SQL/backend nodes.
- Create `tests/test_news_feed_content_route.py`: direct route and local-backend
  propagation nodes.
- Modify `tests/test_sqlite_backend.py`: evolve existing additive shape/order
  assertions only; no node rename/removal.
- Modify `tests/test_news_pg_unreachable.py`: evolve additive compatibility
  assertions if needed; no new node is budgeted.
- Modify `tests/test_db_backend.py`: evolve retired empty-shape assertion only.
- Modify `tests/test_api.py`: evolve exact response shape and add one invalid
  content node.
- Modify `apps/arkscope-web/src/api.ts`: optional version-skew fields and
  `content` request parameter.
- Modify `apps/arkscope-web/src/News.tsx`: market-only filter and row labels.
- Create `apps/arkscope-web/src/News.test.tsx`: six mounted contracts.
- Do not modify CSS, UI primitives, normalized-news runtime owners, scheduler
  owners, or `config/tickers_core.json`.
- At review-ready only, update this plan's ledger/status, the authority spec
  status, and `docs/design/PROJECT_PRIORITY_MAP.md`.

---

### Task 0: Isolated Worktree and Baseline Freeze

**Files:**
- Modify: this plan's implementation ledger only after the worktree exists.
- Do not copy: `config/tickers_core.json`.

- [x] **Step 1: Create an isolated implementation branch only after plan review**

Use `superpowers:using-git-worktrees`. Start from the review-cleared docs tip,
not from a dirty file copy. Suggested branch:
`codex/news-content-availability-unit-2`.

Record:

```text
behavioral A/B base: 012dc69
review-cleared branch base: <commit>
worktree path: <path>
```

Verify `git status --short` inside the new worktree is empty. The main
worktree's BTSG change remains only in the main worktree.

- [x] **Step 2: Re-run and record grounded baselines before RED**

```bash
pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_news_pg_unreachable.py \
  tests/test_api.py::TestNewsFeed \
  tests/test_db_backend.py::test_retired_pg_domain_methods_do_not_query_dropped_tables

pytest --collect-only -q > /tmp/arkscope-news-content-base-collect.txt

cd apps/arkscope-web
npm test -- --run
npm run typecheck
```

Expected focused backend: `75 passed`. Expected frontend: `55 files / 527
tests`. If collection differs from the approved base before product edits,
stop and reconcile the branch base rather than adjusting the ledger.

- [x] **Step 3: Capture the read-only performance baseline**

Against the real `data/market_data.db`, use `SqliteBackend.query_news_feed()`
without writing or starting a provider. Warm once, then record at least five
runs and median latency for `days=7`, `30`, and `3650`, `limit=50`.

The plan-opening observations were approximately `16.1ms`, `80.7ms`, and
`754.0ms`; they are diagnostics, not acceptance constants. Do not expose
titles, URLs, provider IDs, or body text in the ledger.

---

### Task 1: One Pure Classification Authority

**Files:**
- Create: `src/news_content_availability.py`
- Create: `tests/test_news_content_availability.py`

- [x] **Step 1: Write the ten failing pure-contract nodes**

Create `tests/test_news_content_availability.py` with one nine-case
`pytest.mark.parametrize` and one exact-capability test. The nine cases are:

```python
(
    ("fetched", "finnhub", "full", None),
    ("pending", "ibkr", "headline_only", "retryable"),
    ("failed", "ibkr", "headline_only", "retryable"),
    ("pending", "finnhub", "headline_only", "terminal"),
    ("failed", "polygon", "headline_only", "terminal"),
    ("empty", "polygon", "headline_only", "terminal"),
    ("unavailable", "ibkr", "headline_only", "terminal"),
    ("expired", "ibkr", "headline_only", "terminal"),
    (None, None, "unknown", None),
)
```

Name the tests:

```text
test_classify_news_content[... nine IDs ...]
test_recovery_capable_sources_are_exactly_ibkr
```

Also assert two calls to `empty_content_counts()` return equal but distinct
dictionaries so callers cannot share mutable response state. Keep that
assertion inside the exact-capability test; it does not add an eleventh node.

- [x] **Step 2: Prove RED for the missing authority**

```bash
pytest -q tests/test_news_content_availability.py
```

Expected RED: collection/import fails only because
`src.news_content_availability` does not exist. Do not pre-create a stub.

- [x] **Step 3: Implement the pure mapping and generated SQL**

Implement the required shared interface. Generate both CASE expressions from
the same reviewed status/source constants. The SQL expressions must return
only the three availability literals, the two recovery literals, or SQL
`NULL`; unrecognized/missing status returns `unknown/null`.

Do not import SQLite, schema code, provider workers, or FastAPI in this module.

- [x] **Step 4: Prove GREEN and commit**

```bash
pytest -q tests/test_news_content_availability.py
```

Expected: `10 passed`.

Suggested commit:

```text
feat: define news content availability contract
```

---

### Task 2: SQL-Derived Feed Classification and Filtering

**Files:**
- Modify: `src/tools/backends/sqlite_backend.py`
- Extend: `tests/test_news_content_availability.py`
- Modify: `tests/test_sqlite_backend.py`

- [x] **Step 1: Add the six failing backend integration nodes**

Extend the new test file with exactly these six tests:

```text
test_feed_classifies_all_statuses_through_both_maps_without_duplicate_rows
test_content_filter_precedes_total_facets_and_pagination_with_stable_order
test_content_counts_ignore_only_content_axis_and_respect_other_filters
test_missing_or_partial_normalized_schema_degrades_affected_rows_to_unknown
test_headline_only_search_uses_existing_legacy_title_and_description_only
test_unavailable_feed_returns_additive_zero_shape
```

Build a deterministic nine-row legacy fixture covering the nine pure mapping
cases. Map rows `1,3,5,7` through migration, rows `2,4,6,8` through projection,
and leave row `9` unmapped. Use duplicate timestamps on at least two rows to
pin the `n.id DESC` tie-breaker. Expected all-content facet:

```python
{"full": 1, "headline_only": 7, "unknown": 1}
```

Create the normalized tables through `ensure_news_normalized_schema()`, insert
one valid `news_normalization_runs` owner before migration-map rows, and seed
one normalized article/body per mapped legacy row. Do not hand-author a
reduced schema that could let invalid production shapes pass.

The tests must prove:

- both map paths resolve and the returned legacy row count remains nine;
- IBKR pending/failed is retryable, while Finnhub/Polygon pending/failed is
  terminal;
- `content=headline_only` changes total/source/day/items before limit/offset;
- `content_counts` remains the all-content distribution under the same
  q/ticker/source/days filters;
- no normalized tables produces available legacy rows classified `unknown`;
- dropping one map table leaves rows from the surviving map classified and
  affects only the missing-map cohort;
- a headline token finds a headline-only row, while a term absent from all
  stored legacy title/description text cannot match; and
- a missing legacy `news` table returns the full additive unavailable shape
  with a fresh zero `content_counts`.

- [x] **Step 2: Prove RED for missing SQL classification**

```bash
pytest -q tests/test_news_content_availability.py
```

Expected: the first ten pure tests remain green; all six new backend tests
fail because `query_news_feed()` lacks `content`, classification fields, and
the additive facet.

- [x] **Step 3: Add a dynamic read-only projection builder**

Inside `SqliteBackend`, inspect `sqlite_master` using the already-open
read-only connection. Build:

```text
joins
article expression
availability expression
recovery expression
```

Rules:

- normalized classification is enabled only when `news_articles`,
  `news_article_bodies`, and at least one explicit map table exist;
- both maps -> join both and use `COALESCE(m.article_id, p.article_id)`;
- migration only -> join migration and use `m.article_id`;
- projection only -> join projection and use `p.article_id`;
- no usable normalized shape -> add no normalized join and use SQL literals
  `'unknown'` and `NULL`;
- when enabled, join article/body by the resolved article ID and classify from
  `b.body_status` plus normalized `a.source`.

Do not call `_news_score_tables_available()` or `_score_map_joins()` as an
availability proxy: score-table requirements and the unconditional dual-map
join have different compatibility semantics.

- [x] **Step 4: Refactor `query_news_feed()` around one common non-content filter**

Add `content: ContentFilter = "all"` to the method. Keep the existing FTS/LIKE
decision and parameterization. Build one common FROM/JOIN and one common WHERE
for q/ticker/source/days.

Execute:

1. one grouped `content_counts` query over the common WHERE without content;
2. total, sources, days, and item queries over common WHERE plus the selected
   availability predicate when `content != "all"`;
3. item SELECT with both derived expressions.

Initialize the three facet keys through `empty_content_counts()` before
overlaying grouped rows. Never infer a missing key from the selected page.

Preserve current BM25 weighting. Add only the deterministic ID tie-breaker to
the current orders.

- [x] **Step 5: Evolve existing feed assertions without changing node IDs**

In `tests/test_sqlite_backend.py`:

- add `content_counts` to additive full-shape expectations;
- assert the existing pre-normalized `market_db` rows are `unknown`, not
  headline-only;
- preserve all existing browse/search/source/ticker/relevance/cleanup intent;
- do not rewrite the old fixture to create normalized tables merely to make
  the new feature look populated.

- [x] **Step 6: Prove the 16-node backend owner green and commit**

```bash
pytest -q tests/test_news_content_availability.py tests/test_sqlite_backend.py
```

The new file must report exactly `16 passed`; the full selected set must have
no changed/removed existing node IDs.

Suggested commit:

```text
feat: derive news content facets in SQL
```

---

### Task 3: Additive Route, DAL, and Compatibility Propagation

**Files:**
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `src/tools/backends/db_backend.py`
- Modify: `src/tools/data_access.py`
- Modify: `src/api/routes/news.py`
- Modify: `src/smoke/pg_unreachable_e2e.py`
- Create: `tests/test_news_feed_content_route.py`
- Modify: `tests/test_news_pg_unreachable.py`
- Modify: `tests/test_db_backend.py`
- Modify: `tests/test_api.py`

- [x] **Step 1: Write the three failing propagation/API nodes**

Create two tests in `tests/test_news_feed_content_route.py`:

```text
test_news_feed_route_forwards_content_to_dal
test_local_backend_propagates_content_without_postgres_fallback
```

Call `news.news_feed(...)` with every ordinary parameter explicitly supplied,
including `content="headline_only"`, and assert the fake receives the exact
value. This protects handler-direct callers from a FastAPI `Query` object
leaking into DAL code.

For the second test, use the real `LocalMarketDatabaseBackend` over a temporary
SQLite feed and poison `DatabaseBackend.query_news_feed`. Assert
`content="headline_only"` reaches the local backend and PostgreSQL is never
called.

Add to `TestNewsFeed`:

```text
test_feed_rejects_invalid_content
```

Request `/news/feed?content=body_or_guess` and assert typed `422`; do not test a
custom error string.

- [x] **Step 2: Prove RED for missing route propagation/validation**

```bash
pytest -q \
  tests/test_news_feed_content_route.py \
  tests/test_api.py::TestNewsFeed::test_feed_rejects_invalid_content
```

- [x] **Step 3: Propagate the selector through every compatibility layer**

- Import `ContentFilter` in the route and declare
  `content: ContentFilter = Query("all")`.
- Add `content="all"` to DAL and all three backend method signatures.
- Forward it through LocalMarket -> Sqlite and LocalMarket -> retired
  compatibility fallback paths.
- Add `content_counts` to DataAccess/FileBackend, LocalMarket exception, strict
  local, and retired DB empty shapes using a fresh dictionary per response.
- Update the direct no-PG smoke dispatcher to pass
  `content=qstr("content", "all") or "all"` explicitly.
- Keep the retired PG method non-querying and local hard-exit behavior
  unchanged.

- [x] **Step 4: Evolve exact-shape tests and smoke contracts**

- `TestNewsFeed.test_feed_route_not_captured_by_ticker_route` now expects the
  six top-level keys including `content_counts`, and item additive fields when
  present.
- `tests/test_db_backend.py` expects the fresh zero facet.
- Strict/fallback tests retain `available=False` and no PG call while accepting
  the additive shape.
- The no-PG smoke still requests ordinary `content=all` behavior and asserts
  `pg_attempts: []` later; it does not seed normalized state.

- [x] **Step 5: Run the exact backend accounting gate and commit**

```bash
pytest -q \
  tests/test_news_content_availability.py \
  tests/test_news_feed_content_route.py \
  tests/test_sqlite_backend.py \
  tests/test_news_pg_unreachable.py \
  tests/test_api.py::TestNewsFeed \
  tests/test_db_backend.py::test_retired_pg_domain_methods_do_not_query_dropped_tables
```

Expected: `94 passed`, exactly `+19/-0` over the approved `75`.

Suggested commit:

```text
feat: expose additive news content filters
```

---

### Task 4: Market NEWS Filter and Honest Row Labels

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/News.tsx`
- Create: `apps/arkscope-web/src/News.test.tsx`

- [ ] **Step 1: Write exactly six failing mounted tests**

Use the existing Vitest/jsdom React harness patterns and mock only `./api`.
Create exactly:

```text
shows content facet counts and only honest non-full row labels
changing the content filter replaces page one and sends the selector
hides status-unknown option when its facet count is zero
old-sidecar responses hide the filter and never guess row labels
load more preserves the selected content filter
seeking alpha mode has no market content filter or market content labels
```

Fixture requirements:

- one full row;
- one retryable headline-only row;
- one terminal headline-only row;
- one explicit unknown row;
- an old-sidecar response that omits all additive fields;
- a separate SA response.

Use visible labels and request arguments as assertions. Do not assert private
React state or implementation class names.

- [ ] **Step 2: Prove RED on the current NEWS UI**

```bash
cd apps/arkscope-web
npm test -- --run src/News.test.tsx
```

Expected: six tests fail because the API type, selector, compatibility gate,
and labels do not exist.

- [ ] **Step 3: Add additive version-skew-safe API types**

Add:

```ts
export type NewsContentAvailability = "full" | "headline_only" | "unknown";
export type NewsContentRecovery = "retryable" | "terminal";
export type NewsContentFilter = "all" | NewsContentAvailability;
```

Make new response/item fields optional at the TypeScript boundary:

```ts
content_availability?: NewsContentAvailability;
content_recovery?: NewsContentRecovery | null;
content_counts?: Record<NewsContentAvailability, number>;
```

Add optional `content` to `getNewsFeed()`. Omit it from the URL for `all`; send
it for the other three values. Do not alter timeout, auth, or SA client code.

- [ ] **Step 4: Implement the market-only filter and labels**

- Add `content` state initialized to `all` and include it in the market request
  plus the existing request-sequence dependency set.
- Render a compact `select` titled `內文狀態` only when the current market
  response has `content_counts`.
- Always offer `全部`, `有內文`, and `僅標題`; offer `狀態不明` only when
  `unknown > 0`. Option text includes the facet counts exactly as
  `全部 (sum)`, `有內文 (full)`, `僅標題 (headline_only)`, and, when present,
  `狀態不明 (unknown)`.
- A content change uses the existing load path at offset zero with
  `append=false`; it must replace rather than append stale rows.
- If an accepted market response lacks `content_counts`, restore `content` to
  `all`, hide the selector, and render no content label.
- Render labels with the established `.list-chip` class. Do not add CSS or a
  new status primitive.
- `full` and absent fields render no label. Never interpret absent as unknown.
- SA mode does not render/send/read market content state.

- [ ] **Step 5: Prove focused GREEN and commit**

```bash
cd apps/arkscope-web
npm test -- --run src/News.test.tsx
```

Expected: exactly `1 file / 6 tests`.

Suggested commit:

```text
feat: surface news content availability
```

---

### Task 5: Automated Equivalence, Privacy, and Scope Gates

**Files:**
- Verify all implementation files.
- Do not edit excluded owners to make gates pass.

- [ ] **Step 1: Run focused and full frontend gates**

```bash
cd apps/arkscope-web
npm test -- --run src/News.test.tsx
npm test -- --run
npm run typecheck
npm run build
```

Expected full result: `56 files / 533 tests`, exact `+6/-0`.

- [ ] **Step 2: Run focused backend and no-PG gates**

```bash
pytest -q \
  tests/test_news_content_availability.py \
  tests/test_news_feed_content_route.py \
  tests/test_sqlite_backend.py \
  tests/test_news_pg_unreachable.py \
  tests/test_api.py::TestNewsFeed \
  tests/test_db_backend.py::test_retired_pg_domain_methods_do_not_query_dropped_tables

python src/smoke/pg_unreachable_e2e.py
```

Expected: `94 passed`; smoke `ok:true` and `pg_attempts:[]`.

- [ ] **Step 3: Run static boundary ratchets**

Against behavioral base `012dc69`, require byte identity for:

```text
src/news_normalized/
src/data_scheduler.py
data_sources/
apps/arkscope-web/src/styles.css
apps/arkscope-web/src/ui/
config/tickers_core.json
```

Also require:

- no provider article ID, raw body text, raw body status, attempt count, or
  retry timestamp in `src/api/routes/news.py`, `api.ts`, or `News.tsx`;
- no force/retry action text or implementation in `News.tsx`;
- no new `aria-live`, polling interval, toast, or CSS selector;
- exact `RECOVERY_CAPABLE_BODY_SOURCES == {"ibkr"}` in one code-reviewed
  authority;
- no Python post-filter over returned feed items.

`config/tickers_core.json` in the main worktree is known dirty. The
implementation branch must be byte-identical to base; never use a command that
reverts the user's main-worktree edit.

- [ ] **Step 4: Verify exact test accounting**

Collect base and head node IDs from symmetric trees and assert:

```text
backend added=19 removed=0
frontend added=6 removed=0
```

Map every added node to the names in Tasks 1-4. Do not accept a passing total
with renamed or removed tests.

---

### Task 6: Read-Only Performance, Live API, and Visual Gates

**Files:**
- No production DB writes.
- Temporary scripts/screenshots live only under `/tmp`.

- [ ] **Step 1: Inspect the real query plan without mutation**

On real `data/market_data.db`, run `EXPLAIN QUERY PLAN` for representative
all/full/headline-only queries. Record only table/index/operator summaries.

Expected normalized lookups use the existing PK/UNIQUE indexes for migration
map, projection map, article, and body. A `SCAN` of an entire normalized map or
body table per feed query is a stop condition; do not add an unreviewed schema
index inside this unit.

- [ ] **Step 2: Repeat the read-only timing sanity**

Warm once and record at least five runs/median for `days=7`, `30`, and `3650`
under `content=all`, plus one representative `headline_only` query. Compare
with Task 0 in the ledger.

There is deliberately no invented millisecond threshold. Record the measured
delta and query plan. If the joined query is plainly unusable or shows an
unexpected full normalized-table scan, stop for review instead of hiding the
cost or adding a cache/column.

- [ ] **Step 3: Compare live API facets to direct read-only aggregates**

Start a scheduler-disabled branch sidecar with a disposable profile DB and the
real market DB as read-only authority. Query `/news/feed` for all four content
values and compare aggregate counts with a direct read-only SQL probe using
the same date/source filters.

Record only aggregate counts and timings. Dynamic totals are evidence, not
fixed test constants. Do not print titles, URLs, provider IDs, or body text.

- [ ] **Step 4: Run real-browser visual checks**

At `1440x900`, `1024x768`, and `390x844`, verify:

- market mode shows one compact content selector;
- retryable, terminal, and unknown wording is readable without overlap;
- full rows carry no warning badge;
- selecting each cohort updates totals and pagination honestly;
- load more retains the selected cohort;
- no horizontal overflow or duplicate filter appears; and
- SA mode has no content selector or market content badges.

Use screenshots and DOM assertions. Do not fabricate normalized rows in the
production database; fixture-backed visual evidence may cover any cohort not
naturally present and must be labeled as such.

- [ ] **Step 5: Stop all temporary services**

Record exact PIDs/ports and confirm branch sidecar, Vite, Chrome, and temporary
profile artifacts are stopped/removed. Do not stop the user's normal desktop
or Gateway process unless the user explicitly asked.

---

### Task 7: Canonical A/B and Review-Ready Closeout

**Files:**
- Modify: this plan
- Modify: `docs/superpowers/specs/2026-07-17-news-content-availability-design.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Run canonical backend A/B from symmetric virgin archives**

Compare behavioral base `012dc69` with the code tip sequentially in the same
review environment. Expected:

```text
failure/error identity sets: bidirectionally empty diff
passed: 4248 -> 4267 (+19)
collect node IDs: +19/-0
skips/warnings/errors: unchanged
```

If the local environment reproduces the known full-suite TestClient hang,
record it and stop short of claiming canonical A/B; independent review must
run the authority comparison. Focused/file-isolated evidence is not mislabeled
as canonical.

- [ ] **Step 2: Reconcile the implementation ledger**

Record branch/base/code tip, each RED cause, each GREEN command/result, exact
node accounting, performance/query-plan evidence, live aggregate evidence,
visual screenshots, static gates, and process cleanup. No placeholders or
unverified claims remain.

- [ ] **Step 3: Mark review-ready, not LIVE**

- Change the spec header to `IMPLEMENTED FOR REVIEW` while retaining Unit 2's
  design authority.
- Add a newest-first map entry with code tip, exact accounting, compatibility,
  performance, live/visual evidence, and any bounded observations.
- Change this plan status to `IMPLEMENTED FOR REVIEW`.
- Commit docs separately after the code tip.
- Stop and request independent implementation review. Do not merge, mark LIVE,
  start Alpha Picks/universe implementation, or start P2.8 Slice 3 yet.

## Reviewer Focus

1. The pure mapping and generated SQL share one exact recovery-capable source
   set; Finnhub/Polygon pending/failed never receive a retry promise.
2. Partial/missing normalized schema degrades only affected rows to `unknown`
   and cannot take down an otherwise valid legacy feed.
3. Content selection is in SQL before total/source/day/pagination; content
   facet excludes only its own axis.
4. Both explicit map paths preserve one legacy feed row each; no fuzzy identity
   join or duplicate rows appear.
5. Reverse version skew hides, rather than fabricates, availability UI.
6. SA mode, legacy search authority, retry workers/policy, entitlement,
   scheduler, normalized schema/writer, and provider privacy remain unchanged.
7. Real-data query plans use indexed normalized lookups; measured performance
   is recorded honestly without inventing a threshold or adding a second
   authority.
8. Exact accounting is backend `+19/-0`, frontend `+6/-0`, with no renamed or
   removed tests.

## Stop Conditions

Stop and report before widening scope if any of these occurs:

- classification requires a schema/index/cache/background mutation;
- Finnhub or Polygon is discovered to have a real scheduled per-article body
  recovery caller not represented in the approved design;
- only Python post-filtering can satisfy the requested facet/pagination shape;
- map joins duplicate legacy rows or require fuzzy identity;
- partial normalized schema makes the legacy feed unavailable;
- an old-sidecar response cannot degrade without a false badge/filter;
- query plan scans full normalized map/body tables or measured real-data
  latency is plainly unusable;
- a retry/provider/scheduler/SA/CSS owner must change;
- test accounting differs from exact `+19/-0` backend or `+6/-0` frontend; or
- any step would stage/revert the user's `config/tickers_core.json` edit.

## Post-Review Merge Closeout

Only after independent GREEN and user merge approval:

1. fast-forward merge the reviewed docs tip;
2. re-run focused `94`, frontend `56/533`, typecheck/build, no-PG smoke, static
   boundaries, and merged-tree read-only API sanity;
3. restart the desktop app so the additive sidecar/UI contract is active;
4. obtain the user's mounted NEWS visual confirmation;
5. mark the spec `LIVE`, close Unit 2 in the map/memory, and remove the
   implementation worktree/branch after confirming no unique changes remain;
6. resume the approved sequence at P2.8 Slice 3. Alpha Picks reconciliation
   and DB-universe/JSON retirement remain design-only until after Slice 3.
