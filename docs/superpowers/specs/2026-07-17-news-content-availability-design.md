# NEWS Content Availability Mini-Design

> **Status:** IMPLEMENTED FOR REVIEW. The approved design remains the
> authority; independent implementation review is the remaining merge gate.

## 1. Purpose

Let the NEWS market-feed surface state and filter whether each result has a
locally stored provider body or only headline-level evidence, without
creating a second content authority or changing provider retry behavior.

This is Unit 2 of the bounded Data Sources follow-up. It is intentionally
separate from Alpha Picks article reconciliation and from any normalized-feed
cutover.

## 2. Ground Truth

### 2.1 The displayed feed and body authority are different projections

`GET /news/feed` currently reads the legacy-compatible `news` table and
`news_fts`. The UI renders one row per ticker mention. Provider body truth lives
in the normalized tables:

- `news_articles` owns one source article;
- `news_article_bodies.body_status` owns retrieval state;
- `news_legacy_migration_map` links migrated legacy rows to normalized
  articles; and
- `news_legacy_projection_map` links rows projected by current normalized
  writers.

One normalized article may project to several legacy ticker rows. Some legacy
rows may remain deliberately unmapped. The two table totals therefore are not
expected to match and a count difference is not, by itself, projection lag.

A read-only 2026-07-17 snapshot illustrates the cardinality rather than serving
as an acceptance constant: `407,867` legacy mention rows, `307,056` normalized
articles, and body states of `301,640 fetched`, `4,990 pending`, `8 failed`,
`166 empty`, and `252 unavailable`.

### 2.2 Existing search behavior

The market NEWS search path indexes legacy `title + description`; normalized
writers derive the legacy description from a bounded cleaned-body snippet.
Consequently:

- a headline-only row remains searchable by title and any metadata already in
  its description;
- text that exists only in a missing body cannot match; and
- this unit does not promise full normalized-body search beyond the existing
  legacy description projection.

Changing the search authority to `news_articles_fts` is a separate cutover and
must not be smuggled into this visibility slice.

### 2.3 Body status alone does not promise recovery

The durable retry queue is currently IBKR-only:
`select_ibkr_body_retries()` filters `news_articles.source='ibkr'`, and only the
IBKR worker supplies explicit retry article IDs. Finnhub and Polygon consume
body/summary text delivered in their ordinary provider payload; there is no
scheduled per-article body recovery path for their migrated `pending` rows.

A read-only 2026-07-17 snapshot made this distinction material: pending bodies
were `3,058 finnhub`, `1,862 polygon`, and `70 ibkr`; the `8 failed` rows were
IBKR. Treating every pending/failed row as retryable would therefore give 4,920
rows a recovery promise the runtime cannot fulfill. These counts are diagnostic
snapshots, not acceptance constants.

## 3. Locked Read Model

### 3.1 Derived at read time

Content availability is derived from the normalized `body_status` on every
feed read. No new column, table, trigger, cache, or background reconciliation is
introduced.

The mapping is exhaustive across body state and the independent provider
recovery-capability axis:

| Normalized evidence | `content_availability` | `content_recovery` | Product meaning |
|---|---|---|---|
| `fetched` | `full` | `null` | Provider body is stored locally |
| `pending` + source has a scheduled body-recovery path | `headline_only` | `retryable` | Body has not yet completed its bounded retrieval path |
| `pending` + source has no scheduled body-recovery path | `headline_only` | `terminal` | Provider payload supplied no body and ArkScope has no queued recovery action |
| `failed` + source has a scheduled body-recovery path | `headline_only` | `retryable` | A retryable provider/transport failure is recorded |
| `failed` + source has no scheduled body-recovery path | `headline_only` | `terminal` | Failure is recorded but no runtime worker can retry this article |
| `empty` | `headline_only` | `terminal` | Provider returned no body |
| `unavailable` | `headline_only` | `terminal` | Scheduled retrieval ended unavailable; explicit recovery may still replace it later |
| `expired` | `headline_only` | `terminal` | Provider/policy evidence says retrieval history is no longer available |
| no normalized map or body row | `unknown` | `null` | ArkScope lacks enough evidence to classify the legacy row |

`unknown` must never be folded into `headline_only`. Age, an empty legacy
description, or a missing URL is not substitute body-state evidence.

Recovery capability is a code-reviewed backend fact, not a DB flag inferred
from age, status, URL, or provider article ID. V1's capable set is exactly
`ibkr`. Adding another source requires wiring a real bounded recovery caller and
updating the capability contract and tests together. A derived `terminal` result
does not prevent a later normal provider ingestion or explicit future recovery
from replacing the underlying body state; it means there is no scheduled
recovery path now.

### 3.2 Legacy-to-normalized join

The feed query resolves normalized identity only through the two explicit map
tables, using one deterministic dual-map expression:

```text
COALESCE(migration_map.article_id, projection_map.article_id)
```

It must not guess an article by title, URL, ticker, date, or row order. Both map
tables have unique legacy-row ownership, so the join must preserve one feed row
per existing legacy mention.

### 3.3 Additive API contract

`GET /news/feed` adds an optional query parameter:

```text
content=all | full | headline_only | unknown
```

The default is `all`. Each result adds:

```json
{
  "content_availability": "full | headline_only | unknown",
  "content_recovery": "retryable | terminal | null"
}
```

The response adds a same-filter facet computed before pagination:

```json
{
  "content_counts": {
    "full": 0,
    "headline_only": 0,
    "unknown": 0
  }
}
```

The content predicate must be part of the SQL filter used by `total`, source
facets, day facets, and `LIMIT/OFFSET`. Filtering an already paginated Python
list is forbidden because it would make totals and subsequent pages false.

The fields are additive. A new frontend connected to an old sidecar treats
their absence as `unknown`, keeps the filter at `all`, and does not render a
false badge. An old frontend ignores the new fields.

## 4. Product Presentation

The market NEWS toolbar gains one compact filter:

- `全部`;
- `有內文`;
- `僅標題`; and
- `狀態不明` only when the backend facet reports a nonzero unknown cohort.

Rows use established status vocabulary rather than exposing raw enum values:

- `full`: no warning badge is required; an optional quiet `有內文` label is
  acceptable if visual review shows the distinction otherwise disappears;
- `headline_only + retryable`: `僅標題 · 內文待處理`;
- `headline_only + terminal`: `僅標題 · 來源未提供內文`; and
- `unknown`: `內文狀態不明`, never `僅標題`.

The distinction is informational. NEWS does not gain a force-retry button,
provider-ID disclosure, retry time, attempt count, or body-status diagnostic.
Data Sources remains the owner of aggregate queue/retry explanation.

The Seeking Alpha mode is unchanged. Its data lives in `sa_capture.db` and has
a different article/body contract; this mini-design applies only to the market
provider feed.

## 5. Failure and Compatibility Rules

- A missing normalized schema or map table degrades affected rows to `unknown`;
  it must not make `/news/feed` unavailable when the legacy feed remains valid.
- A malformed/unsupported `content` value receives the normal typed `422`
  response; it must not silently become `all`.
- Read failure in the derived join preserves the established feed failure
  contract. It must not fabricate `content_counts` full of zeroes.
- Provider retry policy, entitlement filtering, scheduler cadence, body
  attempts, and normalized writer transactions are byte-identical in this
  unit.
- No licensed body or provider article identifier crosses the existing API
  boundary.

## 6. Non-Goals

- normalized NEWS feed/FTS cutover;
- body preview or article-reader UI;
- force retry or per-article recovery actions;
- changing terminal/retryable policy;
- Seeking Alpha availability classification;
- backfilling unmapped legacy rows; or
- adding another persisted availability flag.

## 7. Verification Contract

The implementation plan must include RED-first coverage proving:

1. all six body statuses, both provider-capability polarities for
   `pending`/`failed`, and the unmapped case produce the locked mapping,
   including `finnhub + pending -> terminal`;
2. migration-map and projection-map rows both resolve, without duplicate feed
   rows;
3. `content` filtering occurs before total/facets/pagination and preserves
   stable ordering;
4. `unknown` is never reported as headline-only;
5. title search still finds a headline-only row, while a term absent from all
   stored title/description text does not;
6. missing additive fields under an old-sidecar fixture leave the UI on `全部`
   and render no false badge;
7. no force-retry action, provider ID, raw body state, or polling announcement
   is introduced;
8. market-feed focused tests, full frontend, typecheck/build, no-PG smoke, and
   canonical backend A/B pass with exact test accounting; and
9. a read-only live check compares API facets with direct normalized-state
   aggregates without treating dynamic row totals as fixed constants; and
10. the implementation plan times the derived query against the real roughly
    400k-row legacy feed as a read-only sanity gate, recording rather than
    inventing a performance threshold before a baseline exists.

## 8. Sequence

Written review comes first. After approval, this unit receives its own small
implementation plan and completes before P2.8 Slice 3. Alpha Picks article
reconciliation and DB-universe/JSON retirement remain design-only until after
Slice 3.
