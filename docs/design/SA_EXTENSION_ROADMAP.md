# Seeking Alpha Extension Roadmap

Last updated: 2026-06-27

## Goal

Extend the current Seeking Alpha extension beyond Alpha Picks article/comments so it can collect a broader but still practical set of SA signals.

Primary design principle:

- prioritize **recent, high-value, low-latency** data first
- avoid large historical backfills unless they clearly support a specific training use case
- let datasets accumulate over time through regular sync

This roadmap assumes the existing Alpha Picks pipeline remains the foundation and new sources are added incrementally.

## Current baseline

Already implemented today:

- Alpha Picks portfolio sync
- Alpha Picks articles metadata
- Alpha Picks article body capture
- Alpha Picks comments capture
- bounded quick/full/deep-backfill refresh modes

Current content-capture limitations for Alpha Picks article bodies are documented in `docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md`.

## P0 prerequisite: capture runtime stability and embedded-browser readiness

This roadmap now has a runtime prerequisite before adding broader SA surfaces or replacing the external browser path.

Why:

- The Firefox/extension workflow is a protected runtime surface, but long-running browser sessions can become memory-heavy and slow.
- A future embedded browser is already a deferred product direction, but it should not inherit the extension's lifecycle leaks, duplicate listeners, unbounded queues, or login/session fragility.
- Seeking Alpha capture must remain user-driven and durable while the runtime moves from "external browser extension" toward an app-owned capture backend.

Required prework:

1. **Runtime telemetry**
   - Record browser kind, extension version, capture mode, session id, active tab/url class, native-port open/close counts, message queue depth, batch sizes, scrape duration, cleanup timestamp, and failure reason.
   - When available, sample browser/renderer memory or at least process RSS around quick/full/deep refresh runs.
   - Surface this as local diagnostic state, not as remote telemetry.

2. **Lifecycle hardening**
   - Content-script injection must be idempotent per tab/frame.
   - `MutationObserver`, timers, DOM listeners, native messaging ports, and in-memory caches must be explicitly disconnected on navigation, tab close, refresh completion, and cancellation.
   - Scrapers must not keep long-lived DOM node references, whole-page HTML snapshots, or unbounded arrays once a batch is sent.
   - Native-host writes stay short, bounded, and retryable; failures must be visible but must not make the browser retain large pending payloads indefinitely.

3. **Capture-core extraction**
   - Split SA capture into a shared, testable core protocol plus thin adapters:
     - Chrome/Firefox extension adapter.
     - Future embedded-browser adapter.
     - Native/app-owned write adapter.
   - The core protocol owns normalized capture messages, batch boundaries, cancellation, dedupe keys, and evidence provenance.
   - Browser-specific code owns only page access, session/login state, and user gesture plumbing.

4. **Soak and restart acceptance**
   - Run a multi-hour soak with repeated SA navigation, quick/full refresh, tab close/reopen, browser restart, and native-host reconnect.
   - Acceptance: no duplicate content scripts/listeners, no stuck native ports, bounded queue sizes, stable or recoverable memory growth, no lost committed captures, and clear recovery instructions if a temporary extension disappears after browser restart.

5. **Embedded-browser gate**
   - Before adopting an embedded browser backend, decide the browser engine strategy, SA login-profile persistence, extension-support model, renderer recycle policy, memory budget, and compliance/ToS posture.
   - If the chosen embedded browser cannot safely run the existing extension as-is, it must use the shared capture core through a dedicated embedded adapter instead of copying extension internals.

Implementation order:

1. Add diagnostics to the existing Firefox/Chrome extension and native-host path.
2. Fix lifecycle leaks exposed by the diagnostics.
3. Extract the capture-core protocol behind the current extension.
4. Only then spike the embedded-browser adapter.

This prerequisite is intentionally before broader source expansion. New SA surfaces can still be added later, but the capture runtime must first be observable and bounded.

## Product framing

Not all SA surfaces need the same retention policy.

### Bucket A: recent feed data

Examples:

- `https://seekingalpha.com/market-news`
- `https://seekingalpha.com/latest-articles`

These are most useful when recent. Full historical backfill is optional. A rolling window plus ongoing daily collection is usually enough.

### Bucket B: daily snapshot data

Examples:

- `https://seekingalpha.com/etfs-and-funds/etf-tables/key_markets`
- right-rail structured widgets such as Factor Grades

These are more like state snapshots than event streams. They should be stored as periodic snapshots, not article text.

### Bucket C: deep article enrichment

Examples:

- article-body images
- Factor Grades attached to article pages
- symbol page widgets

These are useful but secondary compared with getting the main feeds working reliably.

## Recommended priority

### P1: Market News

Source:

- `https://seekingalpha.com/market-news`

Why first:

- high signal for recent developments
- lighter than full article-body scraping
- naturally useful for recent monitoring and later time-series accumulation
- should be fast enough for regular sync

Recommended scope v1:

- headline
- URL
- article/news ID
- published timestamp
- ticker list if visible
- short summary text if visible
- source/category labels if visible
- comment count if available

Recommended retention model:

- recent-first only
- rolling window, e.g. last 7-30 days in active refresh
- older data accumulates naturally as the system runs over time

Recommended refresh:

- quick: last few screens / latest items only
- full: deeper same-day or recent-window sync
- no deep historical crawl initially

Storage shape:

- new table, e.g. `sa_market_news`
- optional child table for news tickers if many-to-many is needed

### P2: Latest Articles (platform-wide analyst articles)

Source:

- `https://seekingalpha.com/latest-articles`

Why second:

- broad analyst coverage across the platform
- useful for idea flow and sentiment
- likely much noisier and higher-volume than Alpha Picks

Recommended scope v1:

- metadata first, not full-body first
- title
- URL
- article ID
- author
- published timestamp
- article type/category
- ticker list if visible
- comment count if visible

Recommended scope v2:

- selective detail fetch only for:
  - watchlist tickers
  - unusually high-comment articles
  - user-manual fetch

Reasoning:

- full-body capture of all latest articles will create a large noisy corpus quickly
- metadata-first keeps cost and complexity under control
- detail fetch can be demand-driven

Storage shape:

- new table, e.g. `sa_latest_articles`
- if body capture is later enabled, reuse the existing article-body/comment pipeline concepts

### P3: Key Markets snapshot

Source:

- `https://seekingalpha.com/etfs-and-funds/etf-tables/key_markets`

Why third:

- useful daily market-state snapshot
- likely low frequency requirement (daily is enough)
- may overlap with other providers, so urgency is lower than news/article feeds

Recommended scope v1:

- capture table rows exactly as visible
- persist snapshot timestamp
- preserve raw values and normalized values where feasible

Recommended refresh:

- once per day
- optionally manual refresh on demand

Storage shape:

- snapshot table, e.g. `sa_key_markets_snapshots`
- possibly one header table + one row table

Important note:

- if another provider already gives equivalent data more reliably, this source may be optional rather than core

### P4: Factor Grades

Why not first:

- useful, but not mandatory
- not every article has it
- it is a structured sidebar widget, not part of article-body capture

Recommended scope:

- scrape as separate structured data
- do not mix it into body Markdown

Potential uses:

- quick stock quality snapshot
- historical grade drift if sampled regularly
- article context enrichment

Storage shape:

- separate structured table keyed by ticker + scraped_at

### P5: Article-body image metadata

Current status:

- body images are not explicitly captured today

Recommended scope:

- `src`
- `alt`
- nearby caption text
- maybe image order within article

Why low-medium priority:

- useful in some cases
- but many images add little if the text already explains the argument
- URL-only storage has some value, but not guaranteed archival durability

## Recommended implementation order

### Phase SA-R1: Market News v1 — implemented 2026-04-07

Delivered:

- list scraper
- new DB table
- DAL methods
- one tool for querying recent news (`get_sa_market_news`)
- quick/full refresh semantics tuned for recent items only

Success criteria:

- fast incremental sync
- stable dedupe by news ID or canonical URL
- useful recent corpus for monitoring and later model training

Operational follow-ups completed after SA-R1:

- `News Catchup` mode now splits queue budget into `current` and bounded `backfill`
- `backfill` is constrained to **known news published within the last 24 hours**
- Market News auto-sync supports `Auto` cadence with ET windows derived from observed publish density

Supporting analysis/tooling now lives in:

- `src/service/sa_market_news_density.py`
  - pure analysis helpers for ET bucket aggregation, interval recommendation, and merged schedule windows
  - intended as the reusable logic layer if auto-sync tuning is later exposed via API or jobs
- `scripts/analysis/analyze_sa_market_news_density.py`
  - operator-facing script to inspect recent SA market-news publish density from PostgreSQL
  - use this before changing `MARKET_NEWS_AUTO_SYNC_WINDOWS_ET` so cadence changes stay data-backed

Recommended operator workflow for future tuning:

1. Run `python scripts/analysis/analyze_sa_market_news_density.py --days 30 --bucket-minutes 60`
2. Review weekday/weekend ET windows and top density buckets
3. Update extension auto-sync windows only if the observed density profile materially changed
4. Keep the analysis helper/script as the source of truth for schedule recalibration

### Phase SA-R2: Latest Articles metadata v1

Deliver:

- metadata-only scraper
- ticker extraction if visible
- query tool for recent analyst articles

Success criteria:

- manageable volume
- no immediate explosion in storage or scrape time
- supports filtering by ticker/keyword/date

### Phase SA-R3: Key Markets daily snapshot

Deliver:

- daily snapshot scraper
- normalized storage
- simple retrieval tool

Success criteria:

- one clean daily snapshot
- stable parsing across minor DOM changes

### Phase SA-R4: Factor Grades structured capture

Deliver:

- dedicated structured scraper
- storage keyed by ticker + scraped_at

Success criteria:

- no coupling to article body pipeline
- easy daily or per-article refresh

### Phase SA-R5: Selective article enrichment

Deliver:

- article image metadata capture
- optional HTML+Markdown dual storage only if needed later

Success criteria:

- added value without materially increasing scrape fragility

## Data model guidance

Do not force all new SA sources into `sa_articles`.

Recommended rule:

- article-like longform content -> article tables
- feed items / news -> news tables
- daily market snapshots -> snapshot tables
- sidebar grades/widgets -> structured metric tables

This keeps the semantics clear and avoids overloading one storage shape for everything.

## Refresh strategy guidance

### Quick Refresh

Use for:

- latest market news
- latest items from recent article feeds
- incremental updates only

### Full Scan

Use for:

- deeper recent-window sync
- bounded backlog cleanup
- metadata reconciliation

### Deep Backfill

Use only where historical backlog truly matters.

Not every SA surface needs deep backfill. In particular:

- market news should probably remain recent-window only
- latest-articles should start metadata-first and recent-first
- daily snapshot pages should usually not backfill deeply at all

## Risks and constraints

### DOM fragility

SA layout can change. Feed/list pages are usually easier to keep stable than complex article detail pages.

### Access control

Some resources may require active authenticated session state. Public CDN image URLs have some value, but not guaranteed long-term durability.

### Volume explosion

`latest-articles` can grow quickly. Metadata-first is the safest initial policy.

### Data overlap

Some surfaces may overlap with existing providers. Only keep SA sources where they add unique signal, timeliness, or convenience.

## Recommended near-term plan

If only one new SA surface is implemented next, it should be:

1. `market-news`

After that:

2. `latest-articles` metadata-first
3. `key_markets` daily snapshot
4. `Factor Grades` structured capture
5. article image metadata

## Decision summary

- Use a **separate roadmap document** for detailed planning.
- Keep `docs/design/AGENT_EVOLUTION_TRACKER.md` as a short summary + pointer.
- Prefer **recent-window accumulation** over large immediate backfills for general SA feeds.
- Treat Factor Grades as a separate structured source, not part of article body scraping.
- Treat image URL capture as optional enrichment, not a prerequisite for the broader SA expansion.
