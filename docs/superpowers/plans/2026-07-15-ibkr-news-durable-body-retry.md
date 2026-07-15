# IBKR News Durable Body Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: PLAN OPEN FOR REVIEW — 2026-07-15. IMPLEMENTATION NOT STARTED.**

**Goal:** Make every locally known, retryable IBKR article body eligible for a bounded automatic retry even after the article falls outside IBKR's rolling headline tail, while keeping fresh headline ingestion independent and provider identifiers inside the isolated worker.

**Architecture:** `NormalizedNewsStore` derives a deterministic retry batch and backlog summary directly from `news_articles` plus `news_article_bodies`; no queue table is added. The isolated IBKR worker passes local normalized article IDs to a new writer retry leg with its own 25-request budget, then performs the existing fresh ticker scan with the existing body budget. The child emits only sanitized leg statuses, counts, and the earliest retry timestamp; the scheduler persists that additive result and Settings renders run outcome separately from durable backlog.

**Tech Stack:** Python 3.11, SQLite, the existing normalized-news writer and sanitized subprocess boundary, IBKR/`ib_insync`, pytest, TypeScript 5.5, React 18, Vitest 4/jsdom.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md`, especially §4.
- Behavioral base for canonical A/B is `a113512` (`docs: close IBKR news partial-status hotfix`). The implementation branch must start from the review-cleared plan tip, but product diffs and test accounting use `a113512` because this plan/map commit is docs-only.
- The queue authority is a read projection over existing normalized SQLite rows. Do not add a retry queue table, migration, in-memory authority, profile-state queue, or scheduler continuation containing body IDs.
- Provider article IDs and licensed content stay inside `market_data.db`, `NormalizedNewsStore`, the writer, and the isolated IBKR worker. They must not enter child stdout, parent scheduler state, API payloads, logs, frontend types, DOM, screenshots, or review ledgers.
- The retry interface uses normalized local integer `article_id` values. `retry_body_ids` never means an IBKR provider ID.
- Retry and fresh work are orthogonal. A retry batch must not replace `tickers`, create a `WriterContinuation`, consume `WriterBudget.max_body_fetches`, or suppress `fetch_articles()`.
- Set `DEFAULT_MAX_RETRY_BODY_FETCHES = 25` in `src/news_normalized/ibkr_cli.py`. Keep existing fresh defaults `DEFAULT_MAX_ARTICLES = 50_000` and `DEFAULT_MAX_BODY_FETCHES = 50_000` unchanged.
- Preserve the approved 10172 policy exactly: first and second failures schedule six hours later; the third becomes terminal `unavailable`; manual Run respects `next_retry_at`; no force-retry command is added.
- Queue reads and provider calls must not hold `market_write_lock`. Each body/metadata/projection update keeps the existing short transaction and write-lock boundary.
- Existing same-source and shared IBKR Gateway lock order remains: source thread lock -> source file lock -> IBKR thread lock -> IBKR file lock -> child worker -> short market write lock.
- Lock-busy remains a retryable skip and must not commit a body attempt. Already committed metadata or body updates remain durable if a later operation fails.
- Aggregate status is deterministic: both legs `succeeded` -> `succeeded`; either leg `partial` or exactly one leg `failed` -> `partial`; both legs `failed` -> `failed`. A scheduled-later backlog alone never changes a successful run to partial.
- A retryable body failure during this run, including 10172, makes the retry leg and aggregate run partial even when the row now has a future `next_retry_at`.
- A retry/backlog query failure is not an empty queue. Fresh work still runs when possible; the retry leg is `failed`, aggregate status is at least `partial`, and sanitized `body_backlog.status` is `unavailable` when the post-run summary cannot be read.
- Preserve Hotfix A compatibility: old worker results without `body_backlog` still render count-only continuation labels. New results render body backlog separately and never gain a `補抓` action.
- Do not change provider configuration, scheduler cadence, news routing, PG-exit decisions, headline catch-up limits, agent tools/prompts, or any order/trading API.

---

## Grounded Baseline

- `NormalizedNewsStore._upsert_body()` already owns retry policy. It writes `next_retry_at = attempted_at + 6h` for 10172 attempts one and two and changes attempt three to `unavailable`.
- `write_news_batch()` currently reads `continuation.deferred_body_ids` before metadata, but any non-null continuation also replaces `work_tickers` with `continuation.deferred_tickers`. Reusing that interface for the durable queue would suppress fresh headline scans.
- The current writer uses one `body_fetch_attempts` counter for resumed and fresh body work. A separate durable retry limit therefore requires a separate input and counter, not a larger shared budget.
- `IBKRNormalizedProvider.fetch_body()` can rehydrate the provider code from the stored candidate and returns a sanitized `BodyCandidate(error_code=10172)` without raw provider text.
- `ibkr_cli.sanitize_worker_result()` allowlists only counters, error classes, and continuation counts; the parent scheduler reparses the allowlist before persisting it. This is the privacy boundary to extend, not bypass.
- `run_source("ibkr_news")` already holds the shared Gateway locks and launches `src.news_normalized.ibkr_cli --gateway-lock-held`. The child receives no continuation from the parent.
- Scheduler partial results from sanitized IBKR output persist with `continuation=None`, so automatic future runs are not blocked by the attended price-continuation gate.
- Frontend Hotfix A reads only durable `last_result.collect.continuation`. Baseline is `44 files / 419 tests`; the two affected suites currently total `40` tests.
- Backend full collection is `4275`. Focused baselines are: normalized store `25`, writer `19`, writer locking `4`, isolated worker `12`, scheduler `96`.

## Locked Interfaces

```python
@dataclass(frozen=True)
class BodyRetryBacklog:
    due_now: int
    scheduled_later: int
    never_attempted: int
    earliest_next_retry_at: Optional[str]


@dataclass(frozen=True)
class BodyRetrySelection:
    article_ids: tuple[int, ...]
    backlog: BodyRetryBacklog
```

Required `NormalizedNewsStore` signatures are:

- `candidate_by_article_id(self, article_id: int) -> Optional[ArticleCandidate]`
- `select_ibkr_body_retries(self, *, now: datetime, limit: int) -> BodyRetrySelection`
- `summarize_ibkr_body_backlog(self, *, now: datetime) -> BodyRetryBacklog`

Required writer change: add keyword-only `retry_body_ids: Iterable[int] = ()` to the existing
`write_news_batch()` signature, before `progress_cb`, and keep its return type `WriterResult`.

`WriterResult` gains additive `retry_status`, `fresh_status`, `retry_bodies_attempted`, `retry_bodies_fetched`, and `tickers_scanned` fields. The existing `status`, `errors`, `continuation`, and aggregate counters remain compatible.

Sanitized child output gains only:

```json
{
  "retry_bodies_attempted": 1,
  "retry_bodies_fetched": 0,
  "tickers_scanned": 2,
  "legs": {"retry": "partial", "fresh": "succeeded"},
  "body_backlog": {
    "status": "ok",
    "due_now": 0,
    "scheduled_later": 1,
    "never_attempted": 0,
    "earliest_next_retry_at": "2026-07-15T12:00:00Z"
  }
}
```

`body_backlog.status="unavailable"` carries no numeric fields and never means zero.

## File Structure

- Modify `src/news_normalized/models.py`: retry selection/backlog dataclasses and additive writer-result telemetry.
- Modify `src/news_normalized/store.py`: local-ID candidate rehydration and deterministic SQLite queue/backlog reads.
- Create `tests/test_news_normalized_retry_queue.py`: queue eligibility, order, budget, summary, and restart reconstruction.
- Modify `src/news_normalized/writer.py`: independent retry leg and deterministic aggregate status.
- Modify `tests/test_news_normalized_writer.py`: retry/fresh behavior and 10172 outcome tests.
- Modify `tests/test_news_normalized_writer_locking.py`: prove retry provider calls occur outside the market write lock.
- Modify `src/news_normalized/ibkr_cli.py`: 25-item retry budget, queue orchestration, fail-closed backlog handling, and sanitized output.
- Modify `tests/test_normalized_ibkr_worker.py`: child orchestration, 300-tail independence, privacy, restart, and failure tests.
- Modify `src/service/data_scheduler.py`: allowlist the additive leg/backlog result without accepting IDs.
- Modify `tests/test_data_scheduler.py`: persistence and outcome/backlog separation.
- Modify `apps/arkscope-web/src/api.ts`: additive sanitized DTO fields only.
- Modify `apps/arkscope-web/src/marketDataDisplay.ts`: structured backlog presentation and old-sidecar compatibility.
- Modify `apps/arkscope-web/src/marketDataDisplay.test.ts`: pure presentation tests.
- Modify `apps/arkscope-web/src/Settings.tsx`: render one compact non-actionable backlog line beside the existing run outcome.
- Modify `apps/arkscope-web/src/SettingsProviderConfig.test.ts`: mounted run/backlog separation tests.
- Modify after verification: this plan, the authority spec status, and `docs/design/PROJECT_PRIORITY_MAP.md`.

---

### Task 1: Deterministic SQLite Retry Projection

**Files:**
- Modify: `src/news_normalized/models.py:1-75`
- Modify: `src/news_normalized/store.py:1-240`
- Create: `tests/test_news_normalized_retry_queue.py`
- Verify unchanged policy: `tests/test_news_normalized_store.py:266-330`

**Interfaces:**
- Consumes: existing `news_articles.id/source/provider_article_id/publisher/published_at` and `news_article_bodies.body_status/fetch_attempts/next_retry_at`.
- Produces: `BodyRetryBacklog`, `BodyRetrySelection`, `candidate_by_article_id()`, `select_ibkr_body_retries()`, and `summarize_ibkr_body_backlog()`.

- [ ] **Step 1: Write six failing queue tests**

Create `tests/test_news_normalized_retry_queue.py` with a file-backed SQLite fixture and a helper that inserts synthetic IBKR candidates, then updates only body-state columns. Add exactly these tests:

- `test_ibkr_retry_selection_orders_due_pending_and_legacy`
- `test_ibkr_retry_selection_excludes_future_terminal_and_missing_identity`
- `test_ibkr_retry_selection_limit_does_not_truncate_backlog_counts`
- `test_ibkr_retry_backlog_reports_counts_and_earliest_retry`
- `test_ibkr_retry_selection_survives_connection_reopen`
- `test_ibkr_retry_selection_rejects_negative_limit`

The order test must create four eligible rows in deliberately scrambled insertion order and assert local integer article IDs in this order:

1. explicit due failed, oldest `next_retry_at`;
2. pending, oldest `published_at`;
3. failed with null or malformed `next_retry_at`;
4. local article ID tie-breaker.

The exclusion test must prove `fetched`, `empty`, `unavailable`, `expired`, future-due failed, missing provider ID, and missing publisher/provider code are absent. Do not assert or print provider IDs; compare returned local integer IDs.

The summary test must assert:

```python
assert summary == BodyRetryBacklog(
    due_now=3,
    scheduled_later=2,
    never_attempted=1,
    earliest_next_retry_at="2026-07-15T12:00:00Z",
)
```

The reopen test must close and reopen the same SQLite file and prove `selection.article_ids` and `selection.backlog` are identical. The validation test rejects both a negative limit and invocation while the caller already owns a transaction; it rolls back the test transaction before teardown.

- [ ] **Step 2: Run RED and verify the failure reason**

Run:

```bash
pytest tests/test_news_normalized_retry_queue.py tests/test_news_normalized_store.py -q
```

Expected: the six new tests fail because the dataclasses/store methods do not exist; the existing 25 store tests pass, including both 10172 policy pins.

- [ ] **Step 3: Add the retry data types and local-ID rehydration**

Add the two frozen dataclasses from **Locked Interfaces** to `models.py`. Refactor `candidate_by_provider_id()` so it resolves the provider key and delegates to a new `candidate_by_article_id()`; keep the returned `ArticleCandidate` shape byte-for-byte compatible.

```python
def candidate_by_provider_id(
    self, source: str, provider_article_id: str
) -> Optional[ArticleCandidate]:
    article_id = self._article_id_for_provider(source, provider_article_id)
    return self.candidate_by_article_id(article_id) if article_id is not None else None


def candidate_by_article_id(self, article_id: int) -> Optional[ArticleCandidate]:
    row = self.conn.execute(
        "SELECT * FROM news_articles WHERE id=?", (int(article_id),)
    ).fetchone()
    if row is None:
        return None
    ticker_rows = self.conn.execute(
        "SELECT ticker,relation_kind FROM news_article_tickers WHERE article_id=? "
        "ORDER BY ticker",
        (row["id"],),
    ).fetchall()
    primary = next(
        (item["ticker"] for item in ticker_rows if item["relation_kind"] == "primary"),
        None,
    )
    related = tuple(item["ticker"] for item in ticker_rows)
    body_row = self.conn.execute(
        "SELECT * FROM news_article_bodies WHERE article_id=?", (row["id"],)
    ).fetchone()
    body = BodyCandidate()
    if body_row:
        body = BodyCandidate(
            status=BodyStatus(body_row["body_status"]),
            raw_body=body_row["raw_body"],
            raw_format=body_row["raw_format"],
            retrieval_method=body_row["retrieval_method"],
            retrieval_source=body_row["retrieval_source"],
            source_url=body_row["source_url"],
            fetched_at=body_row["fetched_at"],
            error=body_row["last_error"],
            error_code=body_row["last_error_code"],
            fetch_attempts=int(body_row["fetch_attempts"] or 0),
            next_retry_at=body_row["next_retry_at"],
        )
    return ArticleCandidate(
        source=row["source"],
        provider_article_id=row["provider_article_id"],
        title=row["canonical_title"],
        publisher=row["publisher"] or "",
        url=row["url"] or "",
        published_at=row["published_at"],
        primary_ticker=primary,
        related_tickers=related,
        content_kind=row["content_kind"],
        body=body,
    )
```

- [ ] **Step 4: Implement the deterministic read projection**

Validate `limit >= 0`. Normalize `now` to aware UTC and use SQLite `julianday()` so `Z` and `+00:00` values compare correctly. Treat null, blank, or unparsable retry timestamps as legacy due work, matching `_body_fetch_due()`'s existing fail-open parse behavior.

The selection query must use this eligibility and priority shape:

```sql
SELECT a.id
FROM news_articles AS a
JOIN news_article_bodies AS b ON b.article_id = a.id
WHERE a.source = 'ibkr'
  AND NULLIF(TRIM(a.provider_article_id), '') IS NOT NULL
  AND NULLIF(TRIM(a.publisher), '') IS NOT NULL
  AND (
    b.body_status = 'pending'
    OR (
      b.body_status = 'failed'
      AND (
        NULLIF(TRIM(b.next_retry_at), '') IS NULL
        OR julianday(b.next_retry_at) IS NULL
        OR julianday(b.next_retry_at) <= julianday(?)
      )
    )
  )
ORDER BY
  CASE
    WHEN b.body_status = 'failed'
      AND julianday(b.next_retry_at) IS NOT NULL
      AND julianday(b.next_retry_at) <= julianday(?) THEN 0
    WHEN b.body_status = 'pending' THEN 1
    ELSE 2
  END,
  CASE WHEN b.body_status = 'failed' THEN julianday(b.next_retry_at) END,
  julianday(a.published_at),
  a.id
LIMIT ?
```

The summary query uses the same source/identity filter and returns:

- `due_now`: pending + due failed + failed with absent/unparseable retry time;
- `scheduled_later`: failed with a valid future retry time;
- `never_attempted`: pending with `fetch_attempts = 0`;
- `earliest_next_retry_at`: minimum valid future retry time.

`select_ibkr_body_retries()` must execute its selection and summary inside one short explicit read transaction so the chosen IDs and counts describe one SQLite snapshot. Reject an already-active caller transaction, commit/rollback the read transaction before returning, and assert `conn.in_transaction is False`; no transaction or cursor may survive into Gateway I/O. `summarize_ibkr_body_backlog()` is one aggregate SELECT and leaves no transaction open. `limit=0` returns no selected IDs but still returns complete backlog counts.

- [ ] **Step 5: Run GREEN and unchanged-policy tests**

Run:

```bash
pytest tests/test_news_normalized_retry_queue.py tests/test_news_normalized_store.py -q
```

Expected: `31 passed` (`25 + 6`).

- [ ] **Step 6: Commit Task 1**

```bash
git add src/news_normalized/models.py src/news_normalized/store.py tests/test_news_normalized_retry_queue.py
git commit -m "feat: derive durable IBKR body retry queue"
```

---

### Task 2: Independent Writer Retry Leg

**Files:**
- Modify: `src/news_normalized/models.py:55-75`
- Modify: `src/news_normalized/writer.py:1-410`
- Modify: `tests/test_news_normalized_writer.py`
- Modify: `tests/test_news_normalized_writer_locking.py`

**Interfaces:**
- Consumes: local integer IDs from `BodyRetrySelection.article_ids` and `NormalizedNewsStore.candidate_by_article_id()`.
- Produces: the new `write_news_batch()` keyword `retry_body_ids=()`, additive leg/counter fields, and `combine_writer_leg_statuses(retry_status, fresh_status)`.

- [ ] **Step 1: Write six failing writer tests**

Add exactly five tests to `tests/test_news_normalized_writer.py`:

- `test_writer_retry_leg_runs_without_matching_headline`
- `test_writer_retry_leg_precedes_but_does_not_replace_fresh_scan`
- `test_writer_retry_budget_is_independent_from_fresh_body_budget`
- `test_retryable_10172_marks_retry_leg_and_run_partial_without_retry_continuation`
- `test_writer_leg_status_matrix`

Add exactly one test to `tests/test_news_normalized_writer_locking.py`:

Name the locking test `test_retry_body_lock_busy_occurs_after_fetch_and_does_not_increment_attempt`.

Required assertions:

- a selected old local article ID is fetched when `fetch_articles()` returns `[]`;
- event order is `retry body -> fresh metadata -> fresh body`;
- one retry request plus one fresh-body request both execute when `WriterBudget.max_body_fetches == 1`;
- retry failure 10172 persists its next retry, sets `retry_status="partial"`, keeps `fresh_status="succeeded"`, sets aggregate `status="partial"`, and does **not** put the retry row into `continuation.deferred_body_ids`;
- the status matrix pins both succeeded -> succeeded, exactly one non-succeeded -> partial, both partial -> partial, and both failed -> failed;
- the retry provider call observes the injected market write lock as not held; the following update-lock acquisition raises the exact lock-busy error; after reopening SQLite, `fetch_attempts`, `last_attempt_at`, and `next_retry_at` are unchanged.

- [ ] **Step 2: Run RED and verify the failure reason**

```bash
pytest tests/test_news_normalized_writer.py tests/test_news_normalized_writer_locking.py -q
```

Expected: six new tests fail because `retry_body_ids` and leg telemetry do not exist; the existing `23` tests pass.

- [ ] **Step 3: Extend `WriterResult` additively**

Add defaults so existing providers and constructor call sites remain valid:

```python
@dataclass(frozen=True)
class WriterResult:
    status: str
    articles_seen: int
    articles_inserted: int
    bodies_fetched: int
    errors: Dict[str, str]
    continuation: Optional[WriterContinuation]
    legacy_rows_inserted: int = 0
    legacy_rows_updated: int = 0
    projection_skipped_no_ticker: int = 0
    retry_status: str = "succeeded"
    fresh_status: str = "succeeded"
    retry_bodies_attempted: int = 0
    retry_bodies_fetched: int = 0
    tickers_scanned: int = 0
```

Add a single status combiner:

```python
def combine_writer_leg_statuses(retry_status: str, fresh_status: str) -> str:
    if retry_status == "failed" and fresh_status == "failed":
        return "failed"
    if retry_status != "succeeded" or fresh_status != "succeeded":
        return "partial"
    return "succeeded"
```

- [ ] **Step 4: Split retry and fresh execution state**

Add keyword-only `retry_body_ids: Iterable[int] = ()`. Deduplicate local IDs with stable order. Process those IDs before the existing ticker loop with a separate `retry_bodies_attempted` counter; do not increment fresh `body_fetch_attempts`.

For each local retry ID:

1. rehydrate with `candidate_by_article_id()`;
2. skip a missing or terminal row without a provider call, recording an internal retry error only for missing rows;
3. recheck `_body_fetch_due()` defensively;
4. call `provider.fetch_body()` outside `write_lock()`;
5. persist through the existing `update_body()` short-lock helper;
6. count fetched bodies in both aggregate and retry counters;
7. record failures in `retry_errors` using only `retry:<local_id>` keys;
8. never append a retry item to the fresh `WriterContinuation`.

Rename the current shared deferred-body list to `fresh_deferred_body_ids`. Keep existing continuation semantics for non-IBKR/manual normalized continuations. At return:

```python
retry_status = "partial" if retry_errors else "succeeded"
fresh_status = "partial" if continuation_out is not None or fresh_errors else "succeeded"
status = combine_writer_leg_statuses(retry_status, fresh_status)
errors = {**retry_errors, **fresh_errors}
```

Market-lock exceptions still raise immediately and therefore cannot increment durable attempts.

- [ ] **Step 5: Run GREEN and generic-provider regressions**

```bash
pytest tests/test_news_normalized_writer.py tests/test_news_normalized_writer_locking.py tests/test_news_normalized_provider_adapters.py -q
```

Expected: writer files collect `29` tests (`19 + 5`, `4 + 1`); all selected suites pass and old continuation tests remain unchanged.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/news_normalized/models.py src/news_normalized/writer.py tests/test_news_normalized_writer.py tests/test_news_normalized_writer_locking.py
git commit -m "feat: separate normalized news body retry leg"
```

---

### Task 3: Isolated Worker Queue Orchestration and Sanitization

**Files:**
- Modify: `src/news_normalized/ibkr_cli.py:1-205`
- Modify: `tests/test_normalized_ibkr_worker.py`
- Read-only seam: `src/news_normalized/ibkr_adapter.py`
- Read-only seam: `src/news_normalized/ibkr_runtime.py`

**Interfaces:**
- Consumes: Task 1 queue methods, Task 2 `retry_body_ids`, and the existing child-owned SQLite connection/Gateway lifetime.
- Produces: `--max-retry-body-fetches`, `DEFAULT_MAX_RETRY_BODY_FETCHES=25`, sanitized `legs`, retry counters, and `body_backlog`.

- [ ] **Step 1: Write ten failing worker tests**

Add exactly these tests to `tests/test_normalized_ibkr_worker.py`:

- `test_ibkr_worker_accepts_separate_nonnegative_retry_budget`
- `test_ibkr_worker_rejects_negative_retry_budget`
- `test_worker_selects_due_bodies_and_passes_local_ids_separately`
- `test_due_body_older_than_three_hundred_headlines_is_still_attempted`
- `test_retry_queue_query_failure_keeps_fresh_scan_and_marks_partial`
- `test_post_run_backlog_failure_is_unavailable_not_zero`
- `test_future_due_backlog_keeps_worker_succeeded`
- `test_retryable_10172_reports_partial_and_scheduled_backlog`
- `test_retry_and_fresh_limits_are_independent`
- `test_sanitized_retry_result_contains_no_provider_ids_or_body_content`

Use real `NormalizedNewsStore` for the 300-tail, future-due, and 10172 tests; use seam fakes only for client construction and provider calls. The 300-tail test seeds one old due local article plus 300 newer returned headlines, runs with retry limit `1`, fresh article limit `300`, and asserts the old local row was attempted before all fresh headline events.

The queue-query-failure fake must raise from `select_ibkr_body_retries()` but return a normal post-run summary. Assert fresh `fetch_articles()` still executes, `retry_status="failed"`, `fresh_status="succeeded"`, and aggregate `status="partial"`.

The post-summary-failure fake must let selection and both legs succeed, then raise from `summarize_ibkr_body_backlog()`. Assert aggregate partial plus exactly `{"status": "unavailable"}`; do not accept zero counts.

- [ ] **Step 2: Run RED and verify the failure reason**

```bash
pytest tests/test_normalized_ibkr_worker.py -q
```

Expected: ten new tests fail because the retry CLI argument, queue calls, and output fields do not exist; the existing 12 tests pass.

- [ ] **Step 3: Add the independent child budget**

```python
DEFAULT_MAX_RETRY_BODY_FETCHES = 25

parser.add_argument(
    "--max-retry-body-fetches",
    type=int,
    default=DEFAULT_MAX_RETRY_BODY_FETCHES,
    help="Maximum due local article-body retries before the independent fresh scan.",
)
```

Reject any negative article, fresh-body, or retry-body budget. Thread the new value through `main()` to `_run_worker()`; keep all existing callers explicit in tests.

- [ ] **Step 4: Orchestrate queue -> writer -> post-run backlog**

Inside the existing child-owned connection and before `write_news_batch()`:

```python
retry_query_failed = False
try:
    selection = store.select_ibkr_body_retries(
        now=datetime.now(timezone.utc),
        limit=max_retry_body_fetches,
    )
    retry_body_ids = selection.article_ids
except Exception:
    retry_query_failed = True
    retry_body_ids = ()

result = write_news_batch(
    store,
    provider,
    tickers,
    WriterBudget(max_articles, max_body_fetches),
    retry_body_ids=retry_body_ids,
    project_legacy=True,
    write_lock_factory=market_write_lock,
)
data = asdict(result)
```

If the initial query failed, set `data["retry_status"]="failed"`, recompute aggregate status with `combine_writer_leg_statuses()`, and add one generic internal error key `retry_queue`; never serialize its exception text.

Always attempt a post-run `summarize_ibkr_body_backlog(now=completed_at)`, where `completed_at` is a fresh aware UTC timestamp taken after writer completion. On success attach:

```python
data["body_backlog"] = {
    "status": "ok",
    "due_now": backlog.due_now,
    "scheduled_later": backlog.scheduled_later,
    "never_attempted": backlog.never_attempted,
    "earliest_next_retry_at": backlog.earliest_next_retry_at,
}
```

On failure attach only `{"status": "unavailable"}`, mark the retry leg failed, and recompute aggregate status. Do not abort or roll back fresh work that already committed.

- [ ] **Step 5: Extend the stdout allowlist**

Add `retry_bodies_attempted`, `retry_bodies_fetched`, and `tickers_scanned` to `_COUNT_KEYS`. Add strict helpers that accept only leg values `succeeded|partial|failed`, non-negative integer backlog counts, and parseable ISO timestamps no longer than 64 characters.

`sanitize_worker_result()` may emit only existing keys plus:

```python
payload["legs"] = {
    "retry": retry_status,
    "fresh": fresh_status,
}
payload["body_backlog"] = sanitize_body_backlog(data.get("body_backlog"))
```

If an internal `retry_queue` error exists, include `RetryBacklogError` in `error_classes`; provider/body errors continue to map to `ProviderError`. Do not serialize internal error keys or values.

Update `sanitize_worker_error()` with zero values for the three new counters. Keep raw stderr suppression and generic failure behavior unchanged.

- [ ] **Step 6: Run GREEN, module-startup, and privacy tests**

```bash
pytest tests/test_normalized_ibkr_worker.py tests/test_news_normalized_ibkr_adapter.py -q
```

Expected: worker file `22 passed`; adapter privacy/error tests remain green. The module-startup test still proves stdout is exactly one sorted JSON object.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/news_normalized/ibkr_cli.py tests/test_normalized_ibkr_worker.py
git commit -m "feat: run durable retries in isolated IBKR news worker"
```

---

### Task 4: Parent Scheduler Allowlist and Durable Outcome

**Files:**
- Modify: `src/service/data_scheduler.py:300-590,980-1040,1240-1285`
- Modify: `tests/test_data_scheduler.py:1024-1495,2470-2690`

**Interfaces:**
- Consumes: Task 3 sanitized stdout only.
- Produces: additive `collect.legs` and `collect.body_backlog` in process-local and durable scheduler results; no article IDs or manual continuation.

- [ ] **Step 1: Write five failing scheduler tests**

Add exactly:

- `test_worker_stdout_parse_preserves_retry_legs_and_body_backlog`
- `test_worker_stdout_parser_rejects_malformed_body_backlog_values`
- `test_ibkr_success_persists_scheduled_backlog_without_partial`
- `test_ibkr_retry_failure_persists_partial_without_manual_continuation`
- `test_ibkr_backlog_unavailable_is_partial_without_fake_zero`

The success fixture must return `status="succeeded"`, both legs succeeded, and `scheduled_later=2`; assert scheduler/durable status remains succeeded, `continuation is None`, and the backlog survives `status_snapshot()`.

The retry-failure fixture must return aggregate partial, retry partial, fresh succeeded, and a future backlog; assert durable partial with `continuation=None` so the next scheduled run is not blocked by attended continuation logic.

The malformed parser cases include negative, float, string, infinity-equivalent JSON rejection, invalid timestamp, unknown leg status, and `status="unavailable"` with forged counts. They must fail closed to unavailable or omit invalid optional data, never coerce to a numeric zero promise.

- [ ] **Step 2: Run RED and verify the failure reason**

```bash
pytest tests/test_data_scheduler.py -q
```

Expected: five new tests fail because the parent parser drops `legs/body_backlog`; the existing 96 tests pass.

- [ ] **Step 3: Add strict parent-side parsers**

Add the three retry counters to `_SANITIZED_WORKER_COUNT_KEYS`. Add helpers with these exact signatures:

- `_safe_nonnegative_int(value: Any) -> Optional[int]`
- `_safe_iso_timestamp(value: Any) -> Optional[str]`
- `_parse_body_backlog(value: Any) -> Optional[Dict[str, Any]]`
- `_parse_worker_legs(value: Any) -> Optional[Dict[str, str]]`

Rules:

- `unavailable` returns exactly `{"status": "unavailable"}`;
- `ok` requires integer counts `>= 0`; malformed required counts make the whole backlog unavailable;
- earliest retry is optional and must parse as an ISO timestamp;
- unknown leg values are dropped as one unit;
- all unknown nested keys, local IDs, provider IDs, and error detail are discarded.

Attach only parsed results in `_parse_sanitized_worker_stdout()`.

- [ ] **Step 4: Preserve existing scheduler status mechanics**

Do not add a continuation path. `writer_partial = collect.status == "partial"` remains the aggregate authority. A succeeded worker with scheduled backlog therefore persists succeeded; a partial worker persists partial with `continuation=None`; a nonzero future backlog never enters `_pending_continuation()`.

Strengthen the existing worker argv test to assert it contains no `--retry-body-ids`, provider article ID, or body payload. The only new CLI behavior is the child's default 25-item retry budget.

- [ ] **Step 5: Run GREEN and lock/timeout regressions**

```bash
pytest tests/test_data_scheduler.py -q
```

Expected: `101 passed`; existing Gateway-lock, market-lock-busy, timeout, and invalid-stdout tests remain green.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "feat: persist sanitized IBKR body retry telemetry"
```

---

### Task 5: Separate Run Outcome from Body Backlog in Settings

**Files:**
- Modify: `apps/arkscope-web/src/api.ts:2145-2210`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts:100-205`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts:175-290`
- Modify: `apps/arkscope-web/src/Settings.tsx:85-105,1605-1685`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts:170-315,520-545`

**Interfaces:**
- Consumes: durable `ScheduleRunResult.collect.body_backlog` and optional leg statuses from Task 4.
- Produces: `schedulerBodyBacklogPresentation(durable)` and one non-actionable mounted backlog line.

- [ ] **Step 1: Write seven failing frontend tests**

Add exactly five tests in `marketDataDisplay.test.ts`:

```ts
it("keeps a succeeded run successful when bodies are scheduled later", () => {});
it("describes due and never-attempted bodies without a manual action", () => {});
it("renders backlog-query failure as unavailable rather than zero", () => {});
it("separates new body backlog from the partial run label", () => {});
it("fails closed on malformed backlog counts", () => {});
```

Add exactly two mounted tests in `SettingsProviderConfig.test.ts`:

```ts
it("renders succeeded IBKR run and scheduled body backlog as separate facts", async () => {});
it("renders partial retry outcome with backlog and no continuation button", async () => {});
```

The succeeded fixture shows `上次成功` plus `內文佇列：2 篇已排程稍後重試` and the formatted earliest timestamp. The partial fixture shows a generic partial run state plus `1 篇已排程稍後重試`; it must contain ordinary `Run`, no `補抓`, no provider ID, and no `待補抓 0`.

- [ ] **Step 2: Run RED and verify the failure reason**

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
```

Expected: seven new cases fail because backlog types/presentation/rendering do not exist; the current 40 Hotfix A tests pass.

- [ ] **Step 3: Describe the additive sanitized DTO**

Add:

```ts
export interface ScheduleBodyBacklog {
  status: "ok" | "unavailable";
  due_now?: number;
  scheduled_later?: number;
  never_attempted?: number;
  earliest_next_retry_at?: string | null;
}

export interface ScheduleWorkerLegs {
  retry: "succeeded" | "partial" | "failed";
  fresh: "succeeded" | "partial" | "failed";
}
```

Extend only `ScheduleRunResult.collect` with optional `legs`, `body_backlog`, and the three retry/ticker counters. Do not add a request, endpoint, provider ID, or body field.

- [ ] **Step 4: Add a pure backlog presentation helper**

Return `null` when the new field is absent or all valid counts are zero. Return a warning presentation for unavailable state. For valid backlog:

```ts
export interface SchedulerBodyBacklogPresentation {
  label: string;
  tone: "muted" | "warn";
  earliestNextRetryAt: string | null;
}
```

Exact copy rules:

- due only: `內文佇列：N 篇目前可處理`;
- due with never-attempted subset: `內文佇列：N 篇目前可處理（其中 M 篇尚未嘗試）`;
- scheduled only: `內文佇列：N 篇已排程稍後重試`;
- both: join the due and scheduled clauses with ` · `;
- unavailable: `內文待處理狀態暫時無法讀取`.

Counts must be finite non-negative integers. `never_attempted` is displayed only when positive and no greater than `due_now`.

When `body_backlog` exists, `schedulerStateLabel()` must stop folding `deferred_body_count` into the run label. It may still show deferred ticker/cursor information. When `body_backlog` is absent, retain every Hotfix A count-only behavior for old-sidecar compatibility.

- [ ] **Step 5: Render one compact non-actionable line**

Import the helper into Settings. In `renderLastRun()` compute the backlog from `s.durable_state`. Render it beneath the existing status/action row:

```tsx
{bodyBacklog && (
  <div className={`tiny ${bodyBacklog.tone === "warn" ? "refresh-err" : "muted"}`}>
    {bodyBacklog.label}
    {bodyBacklog.earliestNextRetryAt
      ? ` · 最早 ${formatSystemTimestamp(bodyBacklog.earliestNextRetryAt)}`
      : ""}
  </div>
)}
```

Do not add `aria-live`, a progress bar, a badge that implies blocked state, a button, polling, CSS, or an IBKR-specific branch outside the data-driven presence of `body_backlog`.

- [ ] **Step 6: Run GREEN and full frontend gates**

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
npm test
npm run typecheck
npm run build
```

Expected: focused `47 passed`; full frontend `44 files / 426 tests`, exactly `+7/-0`; typecheck/build pass with only the existing chunk-size warning.

- [ ] **Step 7: Commit Task 5**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "feat: show durable IBKR body retry backlog"
```

---

### Task 6: Cross-Boundary Verification, Live Gate, and Review Handoff

**Files:**
- Verify: all Task 1-5 files
- Modify after evidence: `docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md`
- Modify after evidence: `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md`
- Modify after evidence: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: final Tasks 1-5 implementation.
- Produces: review-ready evidence only. No merge, LIVE claim, or Portfolio Slice 3 work.

- [ ] **Step 1: Run the exact focused backend ledger**

```bash
pytest tests/test_news_normalized_store.py tests/test_news_normalized_retry_queue.py tests/test_news_normalized_writer.py tests/test_news_normalized_writer_locking.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -q
```

Expected: `183 passed`, exactly baseline `156 + 27`.

- [ ] **Step 2: Run the explicit reliability gates**

```bash
pytest \
  tests/test_news_normalized_retry_queue.py::test_ibkr_retry_selection_survives_connection_reopen \
  tests/test_news_normalized_writer.py::test_writer_retry_leg_runs_without_matching_headline \
  tests/test_normalized_ibkr_worker.py::test_due_body_older_than_three_hundred_headlines_is_still_attempted \
  tests/test_normalized_ibkr_worker.py::test_retryable_10172_reports_partial_and_scheduled_backlog \
  tests/test_news_normalized_store.py::test_third_10172_becomes_terminal_unavailable \
  tests/test_news_normalized_writer_locking.py::test_retry_body_lock_busy_occurs_after_fetch_and_does_not_increment_attempt \
  tests/test_data_scheduler.py::test_ibkr_success_persists_scheduled_backlog_without_partial \
  tests/test_data_scheduler.py::test_ibkr_retry_failure_persists_partial_without_manual_continuation \
  -q
```

Expected: `8 passed`.

- [ ] **Step 3: Run privacy, authority, and scope ratchets**

The following commands must return zero matches:

```bash
rg -n "retry_body_ids|provider_article_id|raw_body|body_text" \
  src/service/data_scheduler.py \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/marketDataDisplay.ts \
  apps/arkscope-web/src/Settings.tsx

rg -n "CREATE TABLE.*retry|news_body_retry_queue|body_retry_queue" \
  src/news_normalized src/service/data_scheduler.py

rg -n "force.?retry|placeOrder|cancelOrder|modifyOrder|exerciseOption" \
  src/news_normalized src/service/data_scheduler.py

rg -n "psycopg|postgres|PG_DSN|DATABASE_URL" \
  src/news_normalized/ibkr_cli.py src/news_normalized/store.py src/news_normalized/writer.py
```

The first gate deliberately excludes child-internal store/writer modules, where local `article_id` and rehydrated provider identity are required. Also assert the child default appears exactly once:

```bash
rg -n "DEFAULT_MAX_RETRY_BODY_FETCHES = 25" src/news_normalized/ibkr_cli.py
```

Expected: exactly one match.

- [ ] **Step 4: Run full automated verification**

```bash
pytest -q
cd apps/arkscope-web
npm test
npm run typecheck
npm run build
cd ../..
python src/smoke/pg_unreachable_e2e.py
```

In an environment with the known bare-profile failure family, record the raw full result without claiming clean PASS; canonical A/B in Step 6 is the regression authority. Frontend must be `44 files / 426 tests`; smoke must print `ok: true` and `pg_attempts: []`.

Run a responsive visual gate for the affected Data Sources schedule row after the automated suite. Use a fixture sidecar plus Vite and the existing headless-Chrome/CDP workflow; do not edit the real profile DB to manufacture a state. Capture both `succeeded + scheduled backlog` and `partial + backlog unavailable` at `1440x900`, `1024x768`, and `390x844`. At every viewport:

- the run-status line and body-backlog line remain visually distinct;
- long timestamps and explanatory text wrap without covering the macro/SA panels, progress indicators, or adjacent rows;
- the page has no horizontal document overflow (the schedule table may retain its own bounded scroll owner);
- the backlog line has no retry button or other false action affordance; and
- no provider identifier, title, body, or licensed provider error appears in the DOM or screenshot.

Record screenshot paths and DOM overflow measurements in the implementation ledger, then remove temporary fixture/profile artifacts.

- [ ] **Step 5: Run one-Gateway live gate without mutating the real market DB**

Close the normal desktop/sidecar so exactly one Gateway consumer remains. Use SQLite backup to copy the real `market_data.db` to `/tmp/arkscope-ibkr-retry-live.db`. An internal probe may choose one locally known IBKR pending/failed row and make only the copied row due; it must print local integer IDs/counts only, never provider ID, title, body, or licensed error text.

Run the branch worker against the copied DB and real provider configuration with:

```bash
ARKSCOPE_MARKET_DB=/tmp/arkscope-ibkr-retry-live.db \
python -m src.news_normalized.ibkr_cli \
  --tickers AAPL \
  --max-retry-body-fetches 1 \
  --max-articles 1 \
  --max-body-fetches 0
```

Acceptance:

1. stdout is one sanitized JSON object and stderr contains no provider payload;
2. `retry_bodies_attempted == 1`;
3. `tickers_scanned == 1`, proving fresh work still ran;
4. `legs.retry` truthfully reflects fetched/empty/10172/provider failure and `legs.fresh` reflects the ticker scan;
5. the copied row's durable attempt/status changes exactly once or becomes terminal under the existing third-10172 rule;
6. `body_backlog` is `ok` with honest counts or `unavailable`, never fabricated zeros;
7. the real `market_data.db` digest/counts are unchanged; and
8. remove the copied DB/probe artifacts and restart the normal desktop after the gate.

If no real retryable row exists, copy one terminal-free IBKR row into the disposable DB and reset only that copy's body state to pending. Do not create a provider identity, call with a fabricated provider ID, edit the real DB, or expose licensed content.

- [ ] **Step 6: Run canonical full base/head A/B**

Use clean virgin archives of behavioral base `a113512` and final code head under identical environment isolation. Run sequential single-process full pytest. Acceptance:

- bidirectional pre-existing failure/error test-ID diff is empty;
- skip/warning/error families are identical;
- full collection is `4275 -> 4302`, exactly `+27/-0`;
- passed delta is exactly `+27`; and
- frontend is `44/419 -> 44/426`, exactly `+7/-0`.

If this environment reproduces the known `TestClient`/lifespan hang, record it and stop for reviewer canonical A/B. Do not replace the authority with file-isolated or partial results while claiming canonical PASS.

- [ ] **Step 7: Reconcile the ledger and stop review-ready**

Add an `Implementation Ledger` beneath the plan status containing:

- branch, plan base, behavioral base, code head, and docs head;
- every task's RED reason and GREEN command;
- exact focused/full collection delta;
- queue order, restart, 300-tail, independent-budget, 10172, lock, privacy, no-PG, and frontend evidence;
- live copied-DB evidence and the exact naturally observed provider outcome;
- confirmation that real DB and provider identifiers were untouched/unexposed; and
- every deliberate deviation from this reviewed plan.

Change plan status to `IMPLEMENTED FOR REVIEW`; change the authority spec/map to `DURABLE RETRY IMPLEMENTED FOR REVIEW` but not LIVE; commit and stop:

```bash
git add docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark IBKR durable body retry review-ready"
```

---

## Exact Test Ledger

### Backend

| File | Baseline | Added | Final |
| --- | ---: | ---: | ---: |
| `tests/test_news_normalized_store.py` | 25 | 0 | 25 |
| `tests/test_news_normalized_retry_queue.py` | 0 | 6 | 6 |
| `tests/test_news_normalized_writer.py` | 19 | 5 | 24 |
| `tests/test_news_normalized_writer_locking.py` | 4 | 1 | 5 |
| `tests/test_normalized_ibkr_worker.py` | 12 | 10 | 22 |
| `tests/test_data_scheduler.py` | 96 | 5 | 101 |
| **Focused total** | **156** | **27** | **183** |
| **Full repository** | **4275** | **27** | **4302** |

### Frontend

| File | Added |
| --- | ---: |
| `apps/arkscope-web/src/marketDataDisplay.test.ts` | 5 |
| `apps/arkscope-web/src/SettingsProviderConfig.test.ts` | 2 |
| **Frontend total** | **+7/-0; 44 files / 419 -> 426** |

## Stop Conditions

Stop and report before proceeding if any of these becomes necessary:

1. a second queue table or profile-state retry authority;
2. provider article IDs in stdout, scheduler/API/frontend state, logs, screenshots, or ledgers;
3. a writer continuation that suppresses the fresh ticker scan;
4. sharing the fresh body budget with durable retry work;
5. changing the 10172 attempt count, six-hour interval, or terminal state;
6. bypassing `next_retry_at` through manual Run or adding force retry;
7. holding `market_write_lock` while waiting on Gateway/provider I/O;
8. changing scheduler cadence, provider config, normalized-news authority, PG-exit routing, tools/prompts, or trading APIs;
9. mutating the real market DB to manufacture live evidence; or
10. needing to recover headlines ArkScope never observed.

## Reviewer Focus

1. SQL eligibility/order and consistent summary membership.
2. Local integer retry IDs versus provider identity privacy.
3. Retry/fresh budget independence and no fresh-scan suppression.
4. Query-failure behavior: fresh leg continues and unavailable never becomes zero.
5. Deterministic leg/aggregate status, especially retryable 10172 and future-due-only backlog.
6. No retry items in `WriterContinuation` or parent attended-mode state.
7. Sanitized child and parent allowlists reject IDs, body content, malformed counts, and unknown statuses.
8. Market/Gateway lock ordering and zero committed attempt on lock-busy.
9. New-sidecar run/backlog separation plus old-sidecar Hotfix A compatibility.
10. Exact `+27` backend / `+7` frontend ledger and copied-DB live proof.
