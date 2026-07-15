# IBKR News Partial Status and Durable Body Retry Design

> **Status:** APPROVED DESIGN; HOTFIX A LIVE — 2026-07-15; DURABLE RETRY PENDING. Hotfix A is merged and verified. The durable-retry follow-up remains a separate unit that requires its own reviewed implementation plan.

## 1. Purpose

Fix one misleading Settings state immediately, then remove the reliability dependency that caused
the state to remain ambiguous:

1. **Hotfix A:** stop rendering every scheduler `partial` result as price-style
   `部分完成（待補抓 0）`.
2. **Durable retry follow-up:** retry known IBKR article bodies from local normalized state rather
   than depending on the article remaining in IBKR's rolling 300-headline response.

The two changes are separate implementation units. Hotfix A may merge independently. The durable
retry follow-up requires its own reviewed implementation plan because it changes runtime ingestion
behavior.

This design does not reopen PostgreSQL news paths, alter the normalized-news authority, or claim to
recover headlines ArkScope never observed.

## 2. Ground Truth

### 2.1 Live reproduction on 2026-07-14

The desktop sidecar's latest `ibkr_news` schedule result was genuinely partial:

- `35,681` article observations scanned;
- `16` articles inserted;
- `16` bodies fetched;
- `0` errors in that run;
- sanitized continuation: `deferred_ticker_count=0`, `deferred_body_count=10`;
- durable scheduler continuation: `NULL`.

The ten deferred rows were not discarded. Local read-only inspection found ten recent
`news_article_bodies` rows with `last_error_code=10172`, one or two attempts, and six-hour retry
timestamps around 2026-07-15 03:26-03:30 Asia/Taipei.

The current UI nevertheless displayed `部分完成（待補抓 0）`. Its generic label helper reads only
`durable_state.continuation.deferred`, the actionable ticker continuation used by
`price_backfill`. The sanitized IBKR worker intentionally returns only body counts, so this field
is absent and the helper invents zero.

### 2.2 What is safe today

- Article metadata is committed before body retrieval.
- Successfully fetched bodies and legacy projections are durable.
- Error `10172` is persisted without provider text and follows the approved policy: at most three
  attempts, at least six hours apart, then terminal `unavailable`.
- The latest observed six-hour IBKR volume was at most `63` articles for one ticker, below the
  provider's 300-headline response cap. The current ten retries are therefore likely to reappear
  at their next due run under the present cadence.

"Likely" is not a correctness guarantee.

### 2.3 Proven reliability gap

The current path is:

`scheduler -> sanitized ibkr_cli subprocess -> fetch latest headlines -> writer -> count-only stdout`

`reqHistoricalNews` returns at most the 300 most-recent headlines per contract and ignores the
requested date range. The parent scheduler cannot reconstruct article IDs from sanitized counts,
and the child does not independently query due body rows. A known failed body is retried only if a
future headline scan happens to return that article again.

If more than 300 newer headlines displace it before the six-hour retry time, the body row remains
known locally but may never receive another automatic attempt. Existing local state also contains
historical unresolved rows (`178` pending and `59` failed at inspection time). Most predate the
current runtime and do not prove a new scheduler loss, but they prove there is no independent
consumer for the durable unresolved-body backlog.

### 2.4 Two distinct completeness boundaries

1. **Known metadata, missing body:** ArkScope has a stable provider article ID and can make retries
   durable. The follow-up in this design closes this gap.
2. **Unknown headline beyond the provider's 300-item tail:** ArkScope has no metadata or ID to
   retry. This design cannot reconstruct it. Normal scheduled cadence remains the mitigation;
   multi-week downtime still requires real-time capture, a provider-side cursor if one becomes
   available, or cross-provider/Flex-like backfill under a separate design.

The UI and documentation must never collapse these two cases into one "補抓" promise.

## 3. Hotfix A: Truthful Partial Presentation

### 3.1 Scope

Hotfix A is frontend-only and additive to the existing schedule DTO typing. It must not change:

- scheduler outcomes or continuation persistence;
- IBKR retry timing or attempt count;
- worker sanitization;
- Gateway calls;
- profile or market-data databases;
- the existing actionable price-backfill continuation.

### 3.2 Label precedence

For a durable `partial` result, presentation follows this order:

1. A persisted actionable `continuation.deferred[]` renders
   `部分完成（待補抓 N）` and may render the existing manual `補抓` command when `N > 0`.
2. A sanitized normalized-news continuation renders observed counts without an action promise:
   - body only: `部分完成（N 篇內文待後續處理）`;
   - ticker only: `部分完成（N 個標的待後續處理）`;
   - both: `部分完成（N 個標的、M 篇內文待後續處理）`;
   - cursor only: `部分完成（尚有資料待後續處理）`.
3. Any other partial result renders only `部分完成`.

The UI must never render `待補抓 0`. Sanitized/count-only IBKR continuation is not manually
resumable and must not gain a `補抓` button.

### 3.3 Data source and restart behavior

The count projection reads the durable result first and may use the process-local latest result
only as a same-run fallback. This preserves the truthful label after a desktop restart.

The API remains additive-compatible. TypeScript may describe the already-returned nested
`last_result.collect.continuation` shape; no backend response change is required for Hotfix A.

### 3.4 Tests

RED-first tests must prove:

- price continuation still renders `待補抓 2` and remains actionable;
- the reproduced IBKR shape renders `10 篇內文待後續處理` and is not actionable;
- combined ticker/body counts are represented without raw IDs;
- generic partial never renders a numeric zero;
- Settings wiring prefers durable result data so restart does not erase the explanation.

## 4. Durable Retry Follow-up

### 4.1 Authority and privacy boundary

The normalized SQLite body rows are the durable retry authority. No second queue table is needed
for V1: the queue is a deterministic read projection over `news_articles` joined to
`news_article_bodies`.

Provider article IDs remain inside `market_data.db` and the isolated IBKR worker. They must not
appear in parent-process stdout, scheduler state, API payloads, logs, tests, or UI. The existing
sanitized count contract remains in force.

### 4.2 Queue eligibility

The worker selects a bounded deterministic batch of IBKR rows that are locally known and still
retryable:

- article source is `ibkr`;
- provider article ID and provider code are available;
- body state is `pending`, or body state is `failed` and its retry time is absent or due;
- terminal `fetched`, `empty`, `unavailable`, and `expired` rows are excluded;
- a failed row with a future `next_retry_at` is backlog metadata, not runnable work.

Ordering is deterministic and protects explicit retry promises from historical debt:

1. failed rows whose explicit `next_retry_at` is due, oldest due time first;
2. never-attempted pending rows, oldest article first;
3. legacy failed rows without a retry timestamp, oldest article first;
4. stable local article ID as the final tie-breaker.

The implementation plan must set a conservative separate per-run retry budget and live-gate it;
retry work must not consume or starve the independent fresh-headline budget.

Historical pending/failed rows are eligible in bounded batches. This is deliberate debt drainage,
not a one-shot unbounded backfill.

### 4.3 Fresh ingestion and retry are orthogonal

One worker run performs both bounded legs under the existing read-only Gateway client and shared
Gateway lock:

1. process the due-body batch from SQLite;
2. scan current headlines for configured tickers and ingest new metadata/bodies.

The writer interface must keep `retry_body_ids` separate from a ticker continuation. Reusing
`WriterContinuation(deferred_body_ids=...)` as-is would suppress fresh ticker scanning because the
current writer treats any continuation as the complete work scope.

Neither leg may hold the market SQLite write lock while waiting on the Gateway. Existing short
write-lock discipline remains authoritative.

### 4.4 Run result and backlog are separate facts

The follow-up must stop overloading one `partial` bit with two meanings:

- **run outcome:** what happened to work that was eligible during this run;
- **body backlog:** counts of due-now, scheduled-later, never-attempted, and the earliest next retry.

A run that completed every currently eligible operation may be `succeeded` while reporting a
nonzero scheduled-later backlog. A body request that fails during this run makes the run
`partial`, including a retryable 10172 that is durably scheduled for a later attempt; the backlog
explains the next retry. A future-due backlog with no eligible body failure in this run does not
downgrade a succeeded run. The UI presents both facts; it does not claim the scheduler is blocked.

Manual `Run` respects `next_retry_at`. A force-retry command is out of scope because bypassing the
six-hour policy can waste Gateway calls and undermine the bounded 10172 contract.

### 4.5 Failure and lifecycle rules

- Each body update is idempotent under the existing provider article identity.
- The third 10172 still becomes terminal `unavailable`.
- A worker crash leaves durable rows eligible for the next run; no in-memory queue is authoritative.
- Lock-busy remains a retryable skip and must not consume an attempt.
- Provider/body failures cannot roll back already committed article metadata.
- A backlog-query failure fails closed for the retry leg but must not fabricate an empty queue.
- Retry and fresh-headline legs report independently. Both complete means `succeeded`; exactly one
  failed or remained incomplete means `partial`; both failed means `failed`. A future-due backlog
  is not an incomplete leg. Existing pre-leg Gateway/market-lock blocking and skip semantics remain
  unchanged.

### 4.6 Verification

The reviewed implementation plan must include tests proving:

1. a due body is attempted even when `fetch_headlines()` returns no article;
2. a due body older than a synthetic 300-headline tail is still attempted;
3. an eligible body that receives retryable 10172 during this run deterministically marks the run
   partial even though the next retry is durably scheduled;
4. future-due rows are not attempted and do not by themselves mark the run partial;
5. retry and fresh-headline budgets cannot starve each other;
6. crash/restart reconstructs the same due queue from SQLite;
7. third-10172 terminal behavior is unchanged;
8. raw provider article IDs never cross sanitized stdout/API/log boundaries;
9. existing market-writer and Gateway locks retain their order and timeout behavior;
10. focused normalized-news/scheduler suites, no-PG smoke, and canonical backend A/B pass;
11. a single-sidecar live gate observes a due retry or a controlled synthetic local row without
    exposing licensed content.

## 5. Sequencing

1. Written review is complete.
2. Open and execute the small Hotfix A implementation plan; stop review-ready and merge it
   independently.
3. Open a separate durable-retry implementation plan immediately afterward.
4. Resume Portfolio 1.1 Slice 3 after this bounded news reliability interruption; Slice 2 is
   already merged/live. Split the durable-retry work further first if its plan review requires it.

Hotfix A is not evidence that body retry is reliable. Durable retry is not evidence that headlines
missed before ArkScope observed them can be recovered.
