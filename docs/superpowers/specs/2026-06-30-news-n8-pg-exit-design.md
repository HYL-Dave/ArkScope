# News N8 PG-Exit Design

Date: 2026-06-30
Status: Approved design; implementation not started

## 1. Purpose

Complete PostgreSQL exit for the **news domain** without coupling that infrastructure change to
the separate normalized-read product migration.

N8 is split into two independently gated phases:

- **N8a -- news PG-exit:** all providers write to normalized local SQLite and atomically maintain
  the current local legacy projection. Existing readers remain behaviorally unchanged. News PG
  sync and the news portion of the PG mirror retire, news-specific hard-local reads become
  mandatory, and a PG-unreachable E2E proves the domain is local.
- **N8b -- normalized-read upgrade:** readers deliberately adopt deduplicated articles, M:N ticker
  relations, cleaned full bodies, and normalized FTS. This is a data-model and product-semantic
  change, not a prerequisite for PG exit.

N8a completes news-domain PG exit only. ArkScope-wide PG exit still requires the remaining price,
IV, fundamentals, SEC/dead-path, mirror, and dual-mode UI work in
`docs/design/PG_EXIT_COMPLETION_PLAN.md`.

## 2. Grounded Current State

### 2.1 Storage and migration

N7 live-migrated the union of legacy SQLite news and the Polygon, Finnhub, and IBKR Parquet
corpora into normalized tables in `data/market_data.db`:

- 371,575 legacy `news` rows remain unchanged;
- 287,016 normalized `news_articles` exist;
- 370,635 legacy rows are mapped and 940 are reviewed rejections;
- all 371,575 current legacy rows are accounted for by `news_legacy_migration_map`;
- 7,100 normalized articles have no legacy mapping and therefore represent normalized-only
  evidence, predominantly from Parquet: IBKR 6,233, Finnhub 649, Polygon 218;
- normalized and legacy maximum timestamps both currently end at
  `2026-06-27T11:11:00+0000`.

The normalized database is therefore more complete than the active legacy read surface. N8a must
not back-project those 7,100 historical articles. They become visible only through the reviewed
N8b read cutover.

### 2.2 Runtime routing

- Polygon and Finnhub currently write directly to local legacy `news`/`news_fts`.
- IBKR still runs collector -> Parquet -> `migrate_to_supabase --news` -> PostgreSQL -> local
  incremental mirror.
- Normalized tables are populated but unrouted.
- `e49cabc` implemented strict local-only market reads, but the live profile currently has
  `use_local_market=true` and no `use_local_market_strict=true`. A fresh DAL resolves to
  `SACaptureDatabaseBackend(strict=False)`. Some empty/error news reads can therefore still fall
  back to PostgreSQL.

### 2.3 Full text

The normalized model already stores:

- original evidence in `news_article_bodies.raw_body`;
- deterministic cleaned text in `news_article_bodies.body_text`;
- one searchable document per article in `news_search_documents` and `news_articles_fts`;
- non-active body variants separately in `news_article_body_variants`.

This is the intended authority. Parquet is no longer a runtime data authority after N8a; it remains
a frozen archive/tool input until a later explicit decommission decision.

## 3. Scope

### 3.1 N8a in scope

1. Route Polygon, Finnhub, and IBKR through the existing normalized common writer.
2. Add a deterministic local legacy projection maintained by the same SQLite transaction.
3. Preserve full normalized bodies while keeping the legacy projection snippet-sized.
4. Add an explicit writer-routing setting and cutover status surface.
5. Reconcile any pre-cutover legacy delta and refuse cutover if it is not zero.
6. Run a bounded live smoke for all three providers, including IBKR 10172 retry behavior.
7. Remove news `--news` PG sync and exclude news from local incremental mirror work.
8. Keep IV, fundamentals, and other unfinished mirror domains unchanged.
9. Persist news-specific hard-local mode and remove news read fallback to PostgreSQL without
   changing unfinished price, IV, or fundamentals fallback policy.
10. Prove normal news ingest and reads with no `DATABASE_URL` and unreachable PostgreSQL.

### 3.2 N8b in scope

1. Add normalized readers behind a separate default-off toggle.
2. Define and test M:N ticker and global-feed response semantics.
3. Verify count, filtering, pagination, FTS, body display, and archive-filter parity.
4. Cut reads to normalized SQLite only after browser/API/tool smoke tests pass.
5. Keep the legacy projection until N9.

### 3.3 Explicitly out of scope

- Changing, deleting, or migrating `scripts/scoring/score_ibkr_news.py`.
- Adding `news_article_scores` or committing to any future LLM scoring policy.
- Deleting Parquet, legacy `news`, legacy `news_fts`, or the N7 backup.
- Implementing automatic archive/retention or deleting old article bodies.
- Language/story grouping, quality ranking, or Tavily/web-search fallback.
- Retiring IV/fundamentals mirror work.
- Claiming ArkScope-wide PG exit.

The existing scorer is a substantial manual Parquet/OpenAI tool, but it is not called by the
scheduler, API, or readers and never touches PostgreSQL. It is orthogonal to N8a.

## 4. Architecture

### 4.1 One provider fetch, two local representations

The normalized common writer becomes the only provider-ingest authority. For each fetched
candidate it performs, in one connection and one transaction:

1. resolve/upsert normalized identity, title, ticker relations, and body;
2. update normalized FTS projection;
3. derive and upsert the legacy local projection;
4. commit both representations together;
5. update provider telemetry only after the data transaction succeeds.

No provider is fetched twice. No projection writer reads PostgreSQL or Parquet. A projection
failure rolls back the corresponding normalized write; it must never leave one representation
ahead of the other.

The legacy projection is not a second authority. It is a compatibility view materialized into the
existing tables until N8b and N9 retire their consumers.

### 4.2 Legacy projection contract

For each normalized article and each canonical ticker relation, project at most one legacy row:

- `ticker`: canonical relation ticker;
- `title`: normalized canonical title;
- `source`, `url`, `publisher`, `published_at`: normalized article fields;
- `description`: cleaned display snippet, never the full `raw_body`;
- `article_hash`: the shared canonical legacy hash for
  `(ticker, canonical_title, published_at)`.

Projection is idempotent on `article_hash`. Existing rows are updated only for deterministic
metadata/snippet corrections; a hash collision with incompatible identity is an error and rolls
back. Existing legacy FTS triggers remain responsible for `news_fts` synchronization.

An article with no ticker remains valid in normalized storage but is not projected into the legacy
table. The result reports `projection_skipped_no_ticker`; this is not silently discarded.

The projector is forward-only. It does not backfill the 7,100 normalized-only historical articles,
because doing so would change current reader counts during N8a.

### 4.3 Full-body contract

Normalized ingest never truncates provider bodies before persistence:

- `raw_body` preserves provider bytes as text evidence;
- `body_text` is cleaned with a pinned `cleaner_version` and is the only body indexed by FTS;
- the legacy `description` receives only `clean_snippet(body_text)` or the provider summary;
- terminal/failed/unavailable body states remain governed by the N7 bounded retry policy;
- body-fetch failure never discards already durable metadata.

This keeps full-text management and search local without multiplying bodies across ticker rows.

### 4.4 Writer routing and rollback

Introduce a dedicated three-state resolver for normalized writes:

- explicit environment override;
- explicit profile setting;
- default **OFF** until the gated live cutover.

The existing `use_local_news` setting currently means direct-local versus PG/mirror. It must not be
silently repurposed. During implementation it remains the pre-cutover rollback lever. After N8a
live validation, the UI can no longer offer a route back through PostgreSQL; rollback is normalized
writer plus local legacy projection, not PG sync.

The normalized read toggle is separate and remains default **OFF** throughout N8a.

### 4.5 Provider-specific routing

- **Polygon/Finnhub:** replace `backfill_news_direct` routing with their existing normalized
  provider adapters plus the common writer. Provider IDs and related tickers are preserved.
- **IBKR:** preserve subprocess isolation for `ib_insync` event-loop and client-ID hygiene, but
  replace the child process's Parquet -> PG behavior with the normalized IBKR adapter and common
  writer. The scheduler parent continues to hold the shared Gateway lock; the child is explicitly
  told that the lock is already held and must not acquire it again. The child owns one connection,
  disconnects in `finally`, and process exit clears its event-loop state. Metadata is durable
  before body retrieval; 10172 follows bounded retry and terminal-unavailable policy.

All three use normalized cursors. Telemetry remains in `provider_sync_runs` and
`provider_sync_meta`, with partial status when per-ticker/body failures occur.

## 5. Delta and Cutover Protocol

N8a must not assume the N7 snapshot stayed current.

### 5.1 Read-only preflight

Before routing any live writer:

1. count legacy rows absent from `news_legacy_migration_map`;
2. compare per-source latest timestamps and source counts;
3. report normalized articles, legacy rows, unmapped legacy rows, and normalized-only rows;
4. produce a deterministic delta fingerprint;
5. perform no schema or data writes.

### 5.2 Delta handling

- If the unmapped legacy count is zero, record that gate and proceed.
- If nonzero, build and review an incremental plan using the same identity/body policies as N7.
- The cutover refuses to run until the incremental plan is applied and a second preview reports
  zero pre-cutover delta.
- A time window, `MAX(published_at)`, or operator assertion alone is not sufficient evidence.

### 5.3 Live cutover order

In a quiet window with scheduler/manual ingest paused:

1. run and record the zero-delta gate;
2. take a unique no-clobber backup;
3. enable normalized writers while normalized reads remain off;
4. run bounded Polygon and Finnhub smokes;
5. run a bounded IBKR metadata/body/10172 smoke;
6. verify normalized/projection parity and idempotent reruns;
7. disable news PG sync and news mirror work;
8. persist the news PG-exit marker, which makes news hard-local without enabling global market
   strict mode;
9. run PG-unreachable news E2E;
10. resume the scheduler only after every gate passes.

If any pre-retirement smoke fails, revert writer routing before resuming. Once PG sync is retired,
rollback remains fully local through the legacy projection.

## 6. Strict-Local Read Contract

N8a keeps existing legacy read semantics but removes PostgreSQL as a possible news source. It does
**not** enable the existing global `use_local_market_strict` switch because that switch also
changes prices, IV, and fundamentals before their PG-exit slices are complete. Instead, the news
PG-exit marker forces local-market routing on for news and makes only news methods hard-local:

- `query_news`, `query_news_search`, `query_news_stats`, and `query_news_feed` must return local
  results or honest local empty/unavailable states;
- no empty result may trigger `DatabaseBackend.query_news*`;
- malformed/missing local schema is surfaced as a local availability error, not concealed by PG;
- Settings/status must report news hard-local effective, not merely implemented;
- tests must fail if a PG news method is called.

When `DATABASE_URL` is absent, DAL construction must still select the local market/SA composite
when local databases and their routing markers are present. The PostgreSQL base may remain an
unconnected compatibility superclass for existing `isinstance(DatabaseBackend)` call sites, but
an empty DSN must fail clearly if an unfinished non-local method actually tries to connect. News
methods must never reach that base.

Other unfinished domains may still use PG until their own slices complete. The N8a E2E therefore
asserts news-domain isolation specifically and does not mislabel the whole application PG-free.

## 7. N8b Normalized Read Contract

N8b is independently designed and gated because normalized semantics intentionally differ:

- one article may relate to multiple tickers;
- per-ticker feeds show an article once;
- global feeds show one article, not one row per ticker;
- related tickers are represented explicitly instead of selecting an arbitrary duplicate row;
- total counts decrease through deduplication;
- the 7,100 normalized-only historical articles become eligible for display;
- FTS searches canonical title plus cleaned full body;
- raw bodies and cold variants are never returned by default APIs.

Existing response DTOs with one `ticker` field cannot represent this faithfully. N8b must either
extend them with `primary_ticker` and `related_tickers` or add a versioned normalized response. It
must not flatten M:N data back into duplicate global-feed rows merely to preserve an old shape.

## 8. Archive and Retention Boundary

Full text remains in SQLite. Archive is a later policy slice, with these locked semantics:

- `archived_at` controls whether an article appears in ordinary reads/search;
- `body_status='expired'` means provider content is no longer retrievable and must **not** be used
  as an archive flag;
- `raw_body` may later become `NULL` after verified cold offload, with `raw_ref` identifying the
  immutable archive object;
- `body_text` may remain for archive search even when raw evidence is offloaded;
- removing `body_text` from hot FTS requires an explicit archive index/rebuild design;
- no age-based deletion is automatic or implicit.

A future archive operation requires preview/apply separation, counts and size estimates,
no-clobber backup, transactional metadata updates, post-apply FTS validation, and an explicit
operator-selected retention policy.

## 9. Validation

### 9.1 Hermetic tests

- provider candidate -> normalized rows -> legacy projection parity;
- one article with N ticker relations -> one normalized row and N idempotent legacy rows;
- normalized and projection writes roll back together on injected failure;
- title/body correction updates both FTS projections without duplication;
- no-ticker article persists normalized and reports projection skip;
- Polygon URL remains non-strong source-wide;
- IBKR 10172 retry stops at the N7 bound and preserves metadata;
- writer rerun inserts zero duplicates;
- strict-local news methods never invoke PG;
- news mirror retirement leaves IV/fundamentals mirror behavior unchanged.

### 9.2 Live gates

- zero pre-cutover delta with deterministic fingerprint;
- unique backup exists and passes `PRAGMA quick_check`;
- all three providers add or idempotently observe bounded real rows;
- normalized/projection source/ticker/latest-time parity is explained and within the projection
  contract;
- both FTS indexes have zero missing/orphan rows;
- normalized body states satisfy N7 invariants;
- `DATABASE_URL` absent and PG host unreachable do not block news reads or ingest;
- browser/API/tool news flows work with strict local effective;
- scheduler resumes without invoking `migrate_to_supabase --news` or news mirror work.

## 10. Completion Criteria

### N8a complete

- Polygon, Finnhub, and IBKR ingest never require PostgreSQL.
- Normalized and legacy projection writes are local and atomic.
- News PG sync and news mirror processing are unreachable in normal scheduling.
- Existing readers remain behaviorally stable and cannot fall back to PG, including when no
  `DATABASE_URL` is configured.
- PG-unreachable news E2E passes.
- N7 backup and legacy tables remain available for recovery.

### N8b complete

- All intended readers use normalized data behind an exercised rollback toggle.
- M:N, dedup, full-body FTS, counts, and 7,100 normalized-only articles have reviewed semantics.
- Browser/API/tool validation passes.
- Legacy projection is no longer needed by active readers, but deletion remains N9.

## 11. Documentation Corrections

Implementation must update the older planning documents that still claim N6/N7 are pending or
that scorer migration is a prerequisite:

- `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`;
- `docs/design/PG_EXIT_COMPLETION_PLAN.md`.

The corrected statement is: scorer migration is not part of PG exit; N7 is live; N8a exits news
from PG while preserving legacy read semantics; N8b is the normalized-read product upgrade.
