# All-Source News Article Normalization Design

Date: 2026-06-28
Status: Proposed for user review
Scope: Polygon, Finnhub, and IBKR news in `market_data.db`

## 1. Context

ArkScope's current local `news` table stores one row per ticker mention. That shape was useful as a
PG mirror, but it is the wrong authority for direct-local news:

- the same provider article is stored once per ticker;
- the ticker-derived `article_hash` identifies a mention, not an article;
- full bodies would be duplicated and indexed once per ticker;
- provider article IDs and related-ticker lists are available upstream but are not retained by the
  direct-local row contract;
- IBKR body retrieval has resumable state in Parquet, but not in the local runtime store;
- the remaining `ibkr_news` collector still requires PG -> mirror and therefore blocks retirement
  of the mirror's news domain.

The live database currently contains about 371k mention rows. Read-only audits found approximately
91k redundant cross-ticker rows across all sources, concentrated in Finnhub and IBKR. The IBKR
Parquet corpus contains 322,033 mention rows but only 83,092 distinct provider article IDs.

The earlier claim that roughly one third of unique IBKR articles lacked bodies was incorrect. It
counted arbitrary flattened ticker rows. Aggregating every row by provider article ID shows:

- 82,771 of 83,092 distinct articles have a non-empty body;
- 321 distinct article IDs have no body in any row;
- 67,371 article IDs have a mixture of body-bearing and empty ticker rows, demonstrating why the
  article must be aggregated before body completeness is judged;
- 18 provider article IDs have multiple observed titles; inspected samples are title revisions or
  formatting corrections, not unrelated ID reuse.

The approved direction is an all-source normalized model. IBKR-only normalization is rejected
because it would preserve two authorities and require a second migration for Polygon/Finnhub.

## 2. Goals

1. Store one canonical article per provider story, independent of ticker count.
2. Preserve all ticker relationships and observed title revisions.
3. Store an exact raw body once and a deterministic cleaned body once.
4. Search one document per article using canonical title plus cleaned body text.
5. Capture provider-native article IDs in every direct writer going forward.
6. Support legacy rows without a recoverable provider ID through an auditable fallback identity.
7. Make body retrieval bounded, resumable, and honest about terminal versus retryable absence.
8. Migrate through preview, fingerprint, backup, one transaction, and post-apply validation.
9. Enable all three news sources to write direct-local so the mirror's news domain can retire.

## 3. Non-Goals

This project reserves contracts but does not implement:

- cross-language or cross-provider story clustering;
- automatic age-based archival or physical deletion;
- editorial quality ranking;
- Tavily or other web-recovery tools;
- removal of the legacy `news` table in the same migration;
- IV, fundamentals, SEC, or the remaining non-news PG-exit work.

The columns needed for later story grouping and archive filtering are included now so those features
do not require another article-table rewrite.

## 4. Identity Model

### 4.1 Source-scoped identity

The strongest identity is `(source, provider_article_id)`. Provider IDs are not compared across
sources. Different-language editions and cross-provider syndication remain separate articles unless
a future `story_group_id` process explicitly groups them.

Legacy rows may not have a recoverable provider ID, especially direct Polygon/Finnhub rows written
after the Parquet bypass. Every candidate therefore also receives a deterministic fallback
candidate key:

```text
SHA-256(source | normalized publisher | normalized title | UTC publication timestamp)
```

Normalization is versioned and consists of Unicode NFKC, HTML entity decoding, whitespace
collapse, and Unicode case-folding. Timestamp precision is preserved when available; a date-only
source remains date-only. The fallback deliberately excludes ticker so cross-ticker mentions can
collapse. It is an identity candidate, not a body digest, and is named
`fallback_identity_hash`; `body_sha256` is reserved for actual body bytes.

Provider IDs and eligible normalized stable URLs are **strong keys**. Polygon URLs are never
strong keys because that source can reuse one URL across provider articles; they remain metadata.
The derived fallback is a **weak key**: it may identify candidates, but repeated same-title
bulletins can collide and it must never force an automatic merge by itself.

### 4.2 Why a COALESCE unique key is insufficient

Do not use only:

```sql
UNIQUE(source, COALESCE(provider_article_id, fallback_identity_hash))
```

A legacy row created under the fallback and a later row carrying the provider ID have different
COALESCE values and can coexist. Instead, an article owns multiple identity keys:

- strong `provider_id` when known;
- strong normalized URL when the source treats it as stable;
- weak `fallback` for every article.

`news_article_keys` enforces source-wide uniqueness only for strong keys. Weak fallback values may
belong to multiple articles. Ingestion resolves all available keys before writing:

1. a strong key matches: update that article and attach newly discovered keys;
2. no strong key matches and exactly one weak-key candidate is metadata-compatible: update it and
   attach the newly discovered strong key;
3. no compatible candidate exists: create an article and attach all available keys;
4. strong keys disagree or weak candidates are ambiguous: preserve existing canonical articles,
   quarantine the incoming candidate durably, and perform no silent merge.

This allows a fallback-only legacy article to acquire its provider ID later without duplication.

### 4.3 Title revisions

Multiple titles under one provider ID remain one article. Every distinct observed title is stored.
The canonical title is chosen in this order:

1. title observed on the row that supplied the canonical fetched body;
2. latest observed title;
3. deterministic earliest observation when timestamps are unavailable.

Changing the canonical title updates the search document but does not change article identity.

## 5. Schema

All tables live in `market_data.db`.

### 5.1 `news_articles`

One row per source article:

```sql
CREATE TABLE news_articles (
    id                       INTEGER PRIMARY KEY,
    source                   TEXT NOT NULL,
    provider_article_id      TEXT,
    canonical_title          TEXT NOT NULL,
    publisher                TEXT,
    url                      TEXT,
    published_at             TEXT NOT NULL,
    content_kind             TEXT NOT NULL DEFAULT 'unknown',
    language                 TEXT,
    story_group_id           TEXT,
    archived_at              TEXT,
    sentiment_score          REAL CHECK (
        sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5
    ),
    sentiment_source         TEXT,
    sentiment_scale          TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_news_articles_provider_id
ON news_articles(source, provider_article_id)
WHERE provider_article_id IS NOT NULL;
```

`content_kind` distinguishes `full_text`, `summary`, `brief`, `headline_only`, and `unknown`.
Body length alone never decides whether provider content is complete.

### 5.2 `news_article_keys`

```sql
CREATE TABLE news_article_keys (
    id           INTEGER PRIMARY KEY,
    article_id   INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    source       TEXT NOT NULL,
    key_kind     TEXT NOT NULL CHECK (key_kind IN ('provider_id', 'url', 'fallback')),
    key_value    TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    UNIQUE (article_id, key_kind, key_value)
);

CREATE INDEX idx_news_article_keys_article ON news_article_keys(article_id);
CREATE INDEX idx_news_article_keys_lookup
ON news_article_keys(source, key_kind, key_value);
CREATE UNIQUE INDEX idx_news_article_keys_strong
ON news_article_keys(source, key_kind, key_value)
WHERE key_kind IN ('provider_id', 'url');
```

The store verifies that `news_article_keys.source == news_articles.source` for the referenced row.
Fallback compatibility requires matching source, normalized publisher/title/timestamp, and no
contradictory stable URL, provider ID, or non-empty body digest. Ambiguity is recorded instead of
resolved by longest text or insertion order.

### 5.3 `news_article_tickers`

```sql
CREATE TABLE news_article_tickers (
    article_id       INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    ticker           TEXT NOT NULL,
    relation_kind    TEXT NOT NULL DEFAULT 'related',
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    PRIMARY KEY (article_id, ticker)
);
```

Ticker aliases are canonicalized before insertion. `relation_kind` is `primary`, `related`, or
`observed_via`, with precedence `primary > related > observed_via`. Repeated fetches update
observation timestamps without duplicating the article or relationship.

### 5.4 `news_article_titles`

```sql
CREATE TABLE news_article_titles (
    id               INTEGER PRIMARY KEY,
    article_id       INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    title            TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    observed_at      TEXT,
    observed_with_body INTEGER NOT NULL DEFAULT 0 CHECK (observed_with_body IN (0, 1)),
    UNIQUE (article_id, title)
);
```

### 5.5 `news_article_bodies`

Exactly one provider-authoritative body state is stored per article:

```sql
CREATE TABLE news_article_bodies (
    article_id          INTEGER PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE,
    body_status         TEXT NOT NULL CHECK (
        body_status IN ('pending', 'fetched', 'empty', 'failed', 'unavailable', 'expired')
    ),
    raw_body            TEXT,
    raw_ref             TEXT,
    raw_format          TEXT,
    body_text           TEXT,
    body_sha256         TEXT,
    cleaner_version     TEXT,
    retrieval_method    TEXT,
    retrieval_source    TEXT,
    source_url          TEXT,
    fetch_attempts      INTEGER NOT NULL DEFAULT 0,
    last_attempt_at     TEXT,
    next_retry_at       TEXT,
    fetched_at          TEXT,
    last_error          TEXT,
    last_error_code     INTEGER,
    unavailable_at      TEXT,
    cleaned_at          TEXT,
    clean_error         TEXT
);
```

`raw_body` preserves the exact provider/legacy payload and is never rendered or indexed.
`raw_ref` is reserved for a future cold-storage reference; it remains NULL in this project and no
offload path is implemented. A future archive operation may replace an old `raw_body` with an
atomically verified `raw_ref`, but a fetched body must always have at least one of them and retain
`body_sha256`. `body_text` remains in SQLite and is the only full-text body used by FTS, agents,
snippets, and UI. Web recovery must not silently overwrite a provider body; a future recovery
design must preserve separate provenance and explicitly choose a canonical evidence source.

### 5.6 Cold body variants

When one provider article has multiple distinct raw bodies, `news_article_bodies` retains the
deterministically selected active body and `news_article_body_variants` retains every other digest.
Cold variants preserve raw and cleaned evidence but are never rendered, indexed, or scored. The
selection policy and table contract are fixed by the N7 migration design.

### 5.7 Search projection and FTS

`news_search_documents(article_id PRIMARY KEY, title, body_text)` is a rebuildable projection.
`news_articles_fts` is an external-content FTS5 index over that projection. The store updates the
projection in the same transaction whenever canonical title or cleaned body changes; projection
triggers keep FTS synchronized.

Search behavior:

- one result per article;
- raw body is never indexed;
- ticker filtering joins `news_article_tickers`;
- default queries exclude `archived_at IS NOT NULL` once archive controls are implemented;
- legacy API responses may expose one primary ticker plus a ticker list, but must not recreate one
  result row per ticker.

### 5.8 `news_ingest_conflicts`

Identity ambiguity must survive process restarts without contaminating canonical articles:

```sql
CREATE TABLE news_ingest_conflicts (
    id                        INTEGER PRIMARY KEY,
    source                    TEXT NOT NULL,
    conflict_kind             TEXT NOT NULL,
    candidate_fingerprint     TEXT NOT NULL,
    candidate_payload_json    TEXT NOT NULL,
    existing_article_ids_json TEXT,
    status                    TEXT NOT NULL DEFAULT 'open',
    created_at                TEXT NOT NULL,
    resolved_at               TEXT,
    resolution                TEXT,
    UNIQUE (source, conflict_kind, candidate_fingerprint)
);
```

The quarantine payload may retain the exact incoming candidate, including raw content when needed
to prevent loss, but it is never logged, rendered, or indexed. Resolution either attaches the
candidate to an existing article, creates a separate article, or records an explicit discard
tombstone. Resolved quarantine payloads may later be compacted under a separate retention policy.

## 6. Body State and Retry Contract

The body status enum is fixed:

- `pending`: never attempted and eligible for a bounded fetch;
- `fetched`: provider returned non-empty content; raw is stored and cleaning is attempted;
- `empty`: request succeeded and provider explicitly returned no body; terminal;
- `failed`: transport/provider error; retryable with backoff while below the attempt cap;
- `unavailable`: repeated explicit provider-unavailable responses after bounded retry; terminal
  for scheduled work but reversible by an explicit successful re-probe;
- `expired`: provider confirmed or policy concluded the article is outside retrievable history;
  terminal.

Only `pending` and eligible `failed` rows are retried. `fetched`, `empty`, `unavailable`, and
`expired` are not.
The retry cap, backoff, and retention window are configuration, not schema constants. IBKR's
approximately 30-day body window remains unconfirmed until the approved five-article probe runs.

N6.1 preserves IBKR request error 10172 as typed `unavailable` evidence and temporarily maps it to
retryable `failed`. N7 must resolve unavailable cohorts into a bounded retry or terminal policy
using the post-fix five-article probe before N8 routes IBKR ingest. Shipping N8 with unbounded 10172
retries is not permitted.

The approved N7 policy permits at most three 10172 attempts separated by at least six hours, then
transitions to terminal `unavailable`. It never infers `expired` from 10172 or age alone.

The existing 321 body-missing IBKR IDs are not deleted or pre-classified by age during migration.
The preview reports likely recent/old cohorts, but the probe must distinguish:

- body still retrievable;
- provider returns a successful empty response;
- explicit unavailable/expired response;
- transient request failure.

If later policy discards low-value metadata-only records, ArkScope retains a minimal tombstone
(`source`, known identity keys, discard reason, timestamp) so old imports cannot recreate them.

## 7. Cleaning Contract

Cleaning is a pure deterministic function:

```text
clean(raw_body, raw_format, source, cleaner_version) -> body_text
```

Required behavior:

- decode HTML entities;
- remove scripts, styles, tracking markup, and non-content metadata;
- flatten headings, links, lists, and tables while preserving readable block boundaries;
- apply narrowly scoped provider boilerplate rules;
- normalize whitespace without joining unrelated paragraphs;
- never execute or trust external HTML;
- never truncate the stored cleaned body; snippet truncation is a read/display concern;
- produce identical output for identical input and `cleaner_version`.

The golden corpus is stratified across IBKR publisher prefixes (`DJ-N`, `DJ-RTA`, `BRFUPDN`, and
others present in the corpus), Polygon, Finnhub, HTML entities, tables, alerts beginning with `!`,
plain text, malformed HTML, empty payloads, and title/body repetition. Raw fixtures must be handled
in accordance with provider licensing and must not be emitted into test logs.

A cleaner upgrade increments `cleaner_version` and re-cleans from `raw_body`; it never re-fetches
solely to change presentation.

## 8. Direct Writer Contract

All source adapters return one normalized provider article containing:

- source and provider article ID when available;
- every available identity key;
- canonical candidate metadata;
- primary and related tickers;
- raw body or summary when supplied;
- retrieval outcome and provenance.

The common writer:

1. holds `market_write_lock` for SQLite writes;
2. IBKR additionally holds the shared `ibkr_gateway_lock` around Gateway operations;
3. resolves all identity keys before mutation;
4. upserts the article, title observations, and ticker relationships in one transaction;
5. stores raw body once and derives `body_text` through the versioned cleaner;
6. updates the search projection and FTS transactionally;
7. records provider telemetry and per-ticker failures;
8. uses bounded article/body budgets and returns a durable continuation when partial;
9. never drops an article because body retrieval failed.

Polygon and Finnhub adapters must begin retaining their actual `article_id` and
`related_tickers`; the current `_article_to_raw` contract discards both and must be replaced.
IBKR uses provider article IDs as the primary identity and fetches a body once even when the same
article is observed through many tickers.

Cursoring remains source/provider-specific. A source cursor may cause boundary refetches, but
identity-key resolution makes those idempotent. Cursor advancement must not skip an article whose
metadata was stored while its body remains pending.

## 9. Offline Migration Preview

The migration is local-only and does not read PG. Inputs are:

- the live legacy SQLite `news` table, which is the runtime metadata/sentiment authority;
- Polygon, Finnhub, and IBKR Parquet files as enrichment evidence for provider IDs, ticker lists,
  raw bodies, and body-fetch state.

The planner performs no writes. It emits:

- total legacy rows scanned and rows accounted for;
- planned canonical article, ticker-link, title, and body counts by source;
- provider-ID coverage and fallback-only blast radius by source;
- cross-ticker rows collapsed;
- unmatched SQLite and Parquet records;
- provider-ID, strong-key, weak-key ambiguity, metadata, body-variant, and sentiment conflicts;
- body-status candidate counts without prematurely converting age into `expired`;
- FTS document count and expected searchable-body coverage;
- a canonical, order-independent SHA-256 fingerprint of the complete plan.

Matching uses provider IDs first, then stable normalized URL, then compatible source-scoped
fallback candidates. Ticker aliases are applied before relation comparison. If strong keys point
to different articles, unrelated records share a provider ID, weak candidates are ambiguous, or
non-empty body variants cannot be resolved deterministically, the plan reports a conflict rather
than silently merging. Strong-key conflicts block apply; reviewed weak-key ambiguities remain
separate articles and are counted explicitly.

For duplicate legacy sentiment values, one identical non-null value may be retained. Distinct
non-null values are a blocking conflict unless an explicit reviewed resolution is added.

## 10. Apply and Cutover Safety

Live apply remains separately gated even though it is local-only:

1. acquire `market_write_lock`;
2. recompute the plan against current inputs;
3. require the reviewed expected fingerprint;
4. create a no-clobber SQLite backup before DDL;
5. create/additive-fill the normalized tables in one transaction;
6. validate all invariants before commit;
7. rollback everything on any mismatch;
8. reopen read-only after commit, re-plan, and prove idempotence.

Required post-conditions:

- every legacy row is mapped or explicitly rejected with a reviewed reason;
- every known provider ID and stable URL maps to at most one article per source;
- every article has a fallback key, while ambiguous fallback values remain explicitly reported;
- no duplicate `(article_id, ticker)` or title observation;
- fetched bodies have `raw_body` or `raw_ref` and a body digest;
- in the initial migration every fetched body is inline (`raw_body` non-empty, `raw_ref` NULL);
- raw bodies never appear in the search projection;
- search projection and FTS rowids have no missing/orphan rows;
- source, article, ticker, title, body, and conflict counts match the reviewed plan;
- a second preview has zero unexplained work.

The legacy `news` table and its FTS index are retained as a frozen rollback source through the
cutover. They are not dual-written after cutover and are not dropped in this project.

## 11. Read Compatibility and Cutover

Before cutover, existing reads continue using `news`. New store queries return the old public row
shape where required, but internally join normalized articles and ticker relationships. Call sites
must not infer that one database row equals one ticker mention.

Cutover is atomic at the routing level:

1. Polygon and Finnhub direct writers switch to the normalized store.
2. IBKR direct writer passes hermetic tests, the five-article probe, and a bounded live smoke.
3. Feed, ticker, FTS, sentiment, agent, and health reads switch to the normalized store.
4. The old `news` table becomes read-only rollback data.
5. `ibkr_news` stops PG sync and the mirror's news branch retires only after all three source
   writers are direct-local and verified.

The current Parquet readers are explicit cutover dependencies, not reasons to preserve Parquet as
the new authority:

- `scripts/scoring/score_ibkr_news.py` remains the Parquet-producing/manual scorer for now. S-G
  added `scripts/scoring/import_news_scores_local.py` as the normalized SQLite import path and
  live-applied the reviewed PG score cutover on 2026-07-03. Local `news_article_scores` is now the
  runtime score authority; PG `news_scores` is archive-only and an N9 drop candidate after final
  reader grep. Live proof: fingerprint
  `34607859293ae7ee20726448e1b733fe55b2cf9fc720a31f6c97a853dec76ab3`, `491,808` local score
  rows inserted/updated, `604` N7-rejected legacy rows skipped, and `14` missing legacy IDs
  skipped.
- `FileBackend` still reads Parquet when the DAL has no DSN. It is not the sidecar's primary news
  path, but its fallback must be replaced by the normalized local store or formally retired before
  historical Parquet files and their reader code can be deleted.

After replacements pass, obsolete Parquet writers/readers, PG migration commands, mirror branches,
tests, and documentation are removed incrementally. Deletion requires a call-site/scheduler/docs
audit and a replacement regression test; "legacy" alone is not sufficient evidence that a script
is dead.

Rollback before old-table retirement routes reads/writes back to the legacy chain and restores the
pre-migration database if normalized writes occurred. No fallback may silently combine old and new
authorities in one query.

## 12. Provider-Dependent Gates

The following work is offline and may proceed while IB Gateway is unavailable:

- schema and identity core;
- cleaner and golden-corpus tests;
- read-only migration preview and fingerprinting;
- hermetic common writer and fake provider;
- Polygon/Finnhub adapter changes and tests;
- IBKR adapter tests against a fake Gateway response.

Two actions require a functioning Gateway:

1. the approved five-article probe for recent/old/alert body behavior;
2. the final bounded IBKR direct-writer live smoke.

The current Gateway incident is operationally separate: TCP accepts the IB greeting but returns no
protocol bytes. It does not change this schema design and must not be worked around by guessing body
status semantics.

## 13. Delivery Slices

Each slice is separately committed and reviewed:

1. **N1 — identity, schema, and cleaner core (hermetic).** Pure identity resolution, additive
   schema builders, body state machine, deterministic cleaner, and golden corpus.
2. **N2 — read-only all-source migration preview.** Full inventory, conflicts, fallback blast
   radius, canonical plan, and fingerprint; no live writes.
3. **N3 — common normalized writer (hermetic).** Fake providers, bounded body work, continuation,
   identity enrichment, store-once body, search parity, and failure isolation.
4. **N4 — Polygon/Finnhub adapters.** Preserve provider IDs and related tickers; route only in
   tests until the migration/cutover gate.
5. **N5 — IBKR adapter (offline portion).** Shared Gateway lock, metadata/body budgets, fake
   responses, retry state, and no per-ticker body duplication.
6. **N6 — provider probe and policy freeze (outward gated).** Run the five approved article IDs,
   record response classes without logging licensed content, and confirm retention/retry config.
7. **N7 — live migration apply (local-write gated).** Reviewed fingerprint, backup, transaction,
   validation, and idempotent post-check.
8. **N8 — all-source cutover and live smokes (runtime/outward gated).** Switch reads and all three
   writers, move active scoring to normalized SQLite, validate feed/FTS/sentiment/telemetry, then
   retire only the news PG-sync/mirror domain.
9. **N9 — news legacy decommission.** Replace or retire `FileBackend` news fallback, freeze/archive
   the Parquet corpus, and delete only verified-dead news Parquet/PG/mirror scripts and copy that no
   scheduler, app route, tool, scorer, test, or maintained document still references.

Archive policy, story grouping, quality ranking, and web recovery remain separate later specs.

## 14. Acceptance Criteria

- One provider article is stored once regardless of ticker count.
- Provider IDs are retained by all direct writers; fallback-only rows are counted and auditable.
- A compatible fallback-only article can acquire a provider ID without creating a second article;
  ambiguous weak matches remain separate and visible rather than being falsely merged.
- The 18 known IBKR multi-title IDs remain one article with title history.
- Raw body is preserved exactly once, never rendered, and never indexed.
- `raw_ref` is reserved for later cold offload; this project keeps raw bodies inline and does not
  introduce a second writable authority.
- Cleaned body is deterministic, versioned, and is the only body used by FTS/agent/UI.
- Body states distinguish pending, fetched, terminal empty, retryable failed, terminal unavailable,
  and expired.
- Search returns one article result with ticker relationships, not duplicate ticker rows.
- Preview fingerprint and apply fingerprint match; conflicts block writes.
- Apply is backup-first, one-transaction, rollback-all, and idempotent.
- Polygon, Finnhub, and IBKR ingest direct-local with no PG news sync.
- Active scoring consumes normalized SQLite, so post-cutover articles do not silently remain
  unscored because Parquet stopped receiving writes.
- The mirror's news domain is removed only after all-source live verification.
- With PG unreachable, normal news ingest, search, feed, and article reads still work.
