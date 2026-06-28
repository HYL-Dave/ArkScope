# News Normalization N7 Migration Design

**Date:** 2026-06-29
**Status:** Approved design, written for review
**Scope:** N7 conflict resolution, resolved preview, and local live apply

## 1. Purpose

N1-N5 built the normalized all-source news foundation without changing live routing. N6/N6.1
confirmed that IBKR body requests can return content or explicit error 10172 and now preserve that
distinction without leaking provider text.

N7 converts the read-only preview into a deterministic, applyable migration plan. It resolves each
known conflict class, produces a new reviewed fingerprint, and populates normalized tables in one
backup-first transaction. N7 does not route runtime reads or writers; that remains N8.

## 2. Grounded Input State

The current read-only input fingerprint is:

```text
55aa79c33ebed92658dc8af232d12ae465d4d19c8ef3bf4556f2e0ed6c5442cc
```

It is an input-audit baseline, not an apply fingerprint. The current conflicts are:

- 718 body-variant groups: 709 IBKR and 9 Polygon;
- 63 Polygon conflict records representing 48 shared URLs;
- 35 apparent provider-ID reuse groups: 31 Finnhub and 4 Polygon;
- 924 IBKR weak legacy identity ambiguities.

Read-only audit established that all 35 apparent provider-ID reuse groups have one normalized title
and URL and differ only in provider timestamps. Of the 48 shared URLs, 35 join two provider IDs
with the same normalized title and publication date; the other 13 differ in title or date.

Any drift in these counts or classifications invalidates the resolved fingerprint and returns N7
to preview review.

## 3. Delivery Strategy

Use controlled overlap:

1. lock the N7 schema, resolution rules, apply engine, and resolved preview;
2. review the new resolved fingerprint;
3. while live apply waits at its explicit gate, N8 may build hermetic readers, scorers, and routing
   adapters against the locked schema;
4. N8 runtime cutover may not run until N7 live apply and post-commit validation pass.

N7 and N8 are never one live transaction or rollback unit.

## 4. Schema Refinements

The live database still has no normalized-news tables, so N7 may refine the additive create schema
without migrating an earlier normalized schema.

### 4.1 Explicit unavailable body state

`news_article_bodies.body_status` becomes:

```text
pending | fetched | empty | failed | unavailable | expired
```

The table adds `last_error_code INTEGER` and `unavailable_at TEXT`. `empty` remains a successful
provider response with no body. `expired` remains a stronger policy claim and is never inferred by
N7 from age or 10172 alone.

### 4.2 Cold body variants

The active body stays in `news_article_bodies`. Every other distinct non-empty body is stored in:

```sql
CREATE TABLE news_article_body_variants (
    id                INTEGER PRIMARY KEY,
    article_id        INTEGER NOT NULL
                      REFERENCES news_articles(id) ON DELETE CASCADE,
    body_sha256       TEXT NOT NULL,
    raw_body          TEXT NOT NULL,
    raw_format        TEXT,
    body_text         TEXT,
    cleaner_version   TEXT,
    retrieval_method  TEXT,
    retrieval_source  TEXT,
    source_url        TEXT,
    fetched_at        TEXT,
    evidence_ref      TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (article_id, body_sha256)
);
```

Cold variants are not rendered, indexed, or scored. Only the active cleaned body feeds FTS,
agents, UI, and sentiment/risk scoring.

### 4.3 Durable legacy accountability

`news_legacy_migration_map` stores one row per legacy `news.id`: legacy ID, nullable normalized
article ID, resolution kind, nullable reviewed rejection reason, and migration fingerprint. It has
no foreign key to `news` so N9 can later retire that table.

A migration-run table stores input fingerprint, resolved fingerprint, applied counts, backup path,
and apply timestamp. Resolution metadata must never contain licensed body text.

## 5. Deterministic Conflict Policies

### 5.1 Provider timestamp drift: 35 groups

Rows sharing one source/provider ID remain one article because normalized title and URL agree.
Canonical `published_at` is the earliest normalized timestamp. Titles and ticker relations are
retained. The 35 groups become `provider_timestamp_drift` resolutions, not blockers.

### 5.2 Polygon shared URLs: 48 URLs

For the 35 URLs whose groups share normalized title and publication date:

- merge into one article;
- use the lexicographically smallest provider ID in the canonical display column;
- attach every provider ID as a strong key to that article;
- retain all ticker and title observations and one strong URL key.

The store must accept any provider-ID key already attached to the article rather than rejecting it
because it differs from the canonical display column.

For the 13 URLs whose title or date differs:

- preserve separate provider-ID articles;
- retain the URL as metadata;
- omit it from strong URL keys for every member of that collision set;
- resolve future candidates by provider ID or compatible fallback, never that URL alone.

### 5.3 IBKR weak ambiguities: 924 legacy rows

Do not merge provider-ID groups, duplicate relations across candidates, or invent a third article.
Preserve provider-backed articles and mark each ambiguous legacy row as a reviewed rejection:

```text
resolution_kind = weak_identity_rejected
reason = multiple metadata-compatible provider articles
```

The legacy row remains in the frozen old table through N9. Reviewed rejections do not block apply;
any new weak ambiguity class or count does.

### 5.4 Body variants: 718 groups

Clean each distinct raw body with the pinned cleaner. Select the active body by this total order:

1. successful cleaner result with non-empty `body_text`;
2. greater cleaned-text character count;
3. greater raw-body character count;
4. later normalized `content_fetched_at`, with missing time last;
5. lexicographically smaller SHA-256 digest.

Store the selected body as active and all other distinct digests as cold variants. Selection inputs
and the chosen digest enter the fingerprint; preview and logs never emit raw text. N8 applies this
same policy when a provider returns a new body variant and refreshes FTS only if active digest
changes.

### 5.5 Sentiment conflicts

The current preview has no sentiment blockers. Identical non-null values may collapse. Any future
distinct values block apply; N7 never averages or silently chooses one.

## 6. IBKR Unavailable and Retry Policy

For IBKR 10172:

1. record `failed`, `last_error_code=10172`, and attempt time;
2. allow at most three total attempts separated by at least six hours;
3. after the third 10172, transition to terminal `unavailable`, set `unavailable_at`, and clear
   `next_retry_at`;
4. only an explicit successful operator re-probe may move `unavailable` to `fetched`.

Other failures retain their own bounded retry policy. Successful empty becomes terminal `empty`.

Migration does not invent 10172 evidence. Raw content means `fetched`; no body and no attempts means
`pending`; no body with recorded failures means `failed` with preserved evidence. Missing error
codes stay NULL and receive one bounded N8 classification attempt. N7 assigns neither
`unavailable` nor `expired` solely from age or missing content.

## 7. Resolved Preview Contract

The planner first builds an immutable resolved plan, then apply consumes that exact plan. Preview
emits no body text and includes:

- input fingerprint and policy version;
- mapped and reviewed-rejected legacy counts;
- timestamp-drift, URL-merge, and URL-demotion counts;
- active/cold variant counts by source;
- pending/failed/fetched body-state counts;
- normalized article, key, ticker, title, body, FTS, and migration-map counts;
- remaining blockers;
- an order-independent resolved fingerprint over evidence, policies, canonical choices, mappings,
  rejections, and selected body digests.

`would_apply` is true only when no unreviewed conflict remains, exactly the reviewed weak rows are
rejected, every legacy row is accounted for, each variant group has one active body, and a second
preview reproduces the fingerprint. The current `55aa79...` cannot authorize apply.

## 8. Apply Safety

Live apply is separately gated and requires the exact reviewed resolved fingerprint:

1. verify inputs and disk space;
2. acquire the shared `market_write_lock`;
3. recompute and match input and resolved fingerprints;
4. create a unique no-clobber backup while holding the lock;
5. begin `IMMEDIATE` transaction;
6. write schema, migration run, articles, keys, relations, titles, bodies, variants, FTS, and legacy
   mappings;
7. validate all post-conditions before commit and rollback everything on mismatch;
8. commit, reopen read-only, revalidate, and prove idempotent zero-change reapply;
9. retain backup until N8 reads, scoring, one ingest per source, and PG-unreachable smoke pass.

Apply never deletes or modifies legacy `news`, legacy FTS, or Parquet inputs.

## 9. Post-conditions

- SQLite `quick_check` is `ok` and counts match the plan.
- Every legacy row has exactly one mapped or reviewed-rejected result.
- Strong provider-ID and eligible URL keys have one owner.
- Demoted URLs have no strong URL key.
- No duplicate article/ticker or article/title relation exists.
- Each fetched article has one active digest; active and cold digests do not overlap.
- Raw bodies are absent from search documents and FTS.
- FTS has no missing or orphan rows.
- Body status and retry fields satisfy state invariants.
- No unresolved conflict or unaccounted legacy row remains.
- Re-preview and reapply are zero-change and fingerprint-stable.

## 10. Testing Strategy

- Pure policy tests cover timestamp drift, URL merge/demotion, weak rejection, body ranking, and
  unavailable transitions.
- Schema tests cover variants, migration map, and structured body errors.
- Planner fixtures cover every conflict class and count-drift refusal.
- Temporary SQLite apply tests prove backup-first, transaction rollback, fingerprint refusal, FTS
  integrity, and idempotence.
- A real-input preview proves input size/mtime/inode stability and yields the reviewed fingerprint.
- Tests never connect to IBKR or write live data.
- Live apply waits for independent review of code, counts, fingerprint, and backup path.

## 11. N8 Boundary

Once N7 schema and preview are reviewed, N8 may build hermetic compatibility reads, SQLite scoring,
writer routing behind an inert gate, active-body replacement, and telemetry readers. N8 may not
run a live smoke, switch routing, stop PG sync, or retire the mirror until N7 live apply passes.

Final N8 order: scorer, writers, bounded IBKR smoke, reads, news PG-sync/mirror retirement, then
PG-unreachable E2E.

## 12. Non-goals

- No runtime routing or PG/mirror retirement in N7.
- No deletion of legacy SQLite or Parquet inputs.
- No archive retention, cross-language grouping, quality ranking, or web recovery.
- No age-based `expired` inference.
- No changes to unrelated market-data domains.

## 13. Acceptance Criteria

- Resolved preview has zero unreviewed blockers and a new stable fingerprint.
- All 35 timestamp-drift groups remain one article each without false recency.
- The 35 exact URL duplicates merge; the 13 semantic URL sets remain separate and demoted.
- All 924 weak rows are reviewed rejections, never guessed mappings.
- All 718 variant groups retain one active body and every distinct cold variant.
- Repeated 10172 becomes `unavailable` after bounded retry, never `empty` or inferred `expired`.
- Every legacy row is durably mapped or reviewed-rejected.
- Apply is backup-first, fingerprint-gated, atomic, rollback-all, and idempotent.
- Legacy inputs remain untouched through N8/N9.
- N8 live cutover remains impossible until N7 live validation succeeds.
