# Layer C-1 — SA Evidence Feed + News-surface SA filter

> **Status:** PLAN LOCKED 2026-06-14 (gpt-5.5 + user refined). Execute in ONE clean round (not at the tail of a long session — the cut spans backend query shape, News UI, and a shared agent primitive).
> **Scope:** a SA evidence feed/search endpoint + agent tool, and a Seeking Alpha source/filter inside the EXISTING News (新聞·事件) surface. NOT a new page.
> **Predecessors:** SA hard cutover (SA_CUTOVER_3D_RUNBOOK) + follow-up #1 (comment-signal port Layer A, get_sa_comment_focus Layer B, v1.2 stopwords) — all done.

## 1. Why

Follow-up #1 made SA *comment* intelligence agent-queryable (`get_sa_comment_focus`), but SA *articles / market-news / Alpha-Picks* content still has no unified, searchable, clickable surface in the app, and the agent has no single SA evidence-feed primitive. C-1 fills "where do I see SA content" + "stable agent evidence query" with the smallest useful surface. C-2 (AI Research) depends on these primitives, so they come first.

## 2. Backend — `GET /sa/feed` + `get_sa_feed` tool

- New tool `get_sa_feed(dal, q=None, ticker=None, item_type=None, days=30, limit=50, offset=0)` in `src/tools/sa_tools.py`; SA-local dispatch on `backend._sa_db` (mirrors the other SA readers); PG mode → `requires_local_sa` degraded shape (same as `get_sa_comment_focus`).
- **DEDICATED query — do NOT compose `get_sa_articles` + `get_sa_market_news`.** A two-reader merge gives unreliable total/ordering/pagination. UNION-normalize `sa_articles` + `sa_market_news` in one query.
- `item_type ∈ {article, market_news, None=both}`. Alpha-Picks-specific articles are NOT a third type in v1 — surface as `article` + a badge; revisit only if the data model reliably distinguishes them.
- **Normalized item shape:**
  ```json
  {
    "type": "article | market_news",
    "id": "<article_id | news_id>",
    "title": "...",
    "tickers": [],
    "published_at": "...",
    "url": "...",
    "source": "seeking_alpha",
    "snippet": "...",
    "has_detail": true,
    "comments_count": 0,
    "detail_route": "/sa/articles/<article_id>"
  }
  ```
  - `has_detail` + `comments_count` let the UI tell "clickable detail" from "metadata only" (article: body_markdown present; market_news: body_markdown present).
  - `detail_route`: stable hint so the frontend doesn't reconstruct type/id. Article → `/sa/articles/{article_id}`. **market_news has no detail endpoint yet** → `detail_route=null`, click falls back to `url` (a `/sa/market-news/{id}` endpoint is out of C-1 scope).
- **Filters:**
  - `ticker` → column (`sa_articles.ticker`) / junction (`sa_market_news_tickers`), NOT text search.
  - `days` → published window (`published_date` / `published_at`), lexicographic compare on canonical UTC TEXT.
  - `q` search semantics (FTS5 mirrors exist: `sa_articles_fts`, `sa_market_news_fts`):
    - empty → pure time sort.
    - `len(q) < 3` OR contains special symbols → **LIKE fallback** (SA is full of short tickers/abbrevs; FTS is unfriendly to short tokens).
    - normal text → FTS5 tokenized AND.
- **Returns (mirror `/news/feed`):** `{available, items[], total, by_type{}, by_day{}, window_days, query}` — newest-first, paginated (limit/offset over the merged ordered list), accurate total/facets.
- **Route:** `GET /sa/feed` in `src/api/routes/seeking_alpha.py`, param signature mirroring `/news/feed`.
- Detail/comments are NOT reimplemented — the feed links to existing `/sa/articles/{id}`, `get_sa_comment_focus`, `list_high_value_comments`.

## 3. Agent tool

Register `get_sa_feed` in all THREE places (see `reference_agent_tool_registration` memory): ToolRegistry (`_register_sa_tools`) + OpenAI bridge wrapper + Anthropic bridge schema/import/dispatch. Returns the evidence feed (NO summary — the agent composes). Future AI Research (C-2) consumes the same primitive. Bump the suite's tool-count assertions +1 (registry, both bridges, news category, name sets, `tools_registered`).

## 4. Frontend — `News.tsx` SA filter (v1; needs visual verification via run/verify)

- Source filter: **All / Market providers / Seeking Alpha** (no new page).
- When Seeking Alpha: SA item-type filter **All / Analysis Articles / Market News** (display labels — never raw `article`/`market_news`).
- Reuse the existing q / ticker / days / load-more controls.
- Item card: ticker chips, date, **source badge**, **comments_count**, snippet.
- Click → external `url` or existing `detail_route` (NO modal in v1).

## 5. Tests (backend — app-free)

- `get_sa_feed` unit on a seeded `sa_capture.db`: item_type filter; ticker filter (column + junction); q FTS path + LIKE-fallback path + short-token/symbol path; days window; pagination (limit/offset + **accurate total**); facets (by_type/by_day); has_detail/comments_count/detail_route correctness per type; no-PG (SA-local poison-`_get_conn`); empty + PG-mode `requires_local_sa`.
- `/sa/feed` route: **handler-level** smoke (call the route handler directly with a fake DAL — NOT TestClient; see `feedback_route_unit_tests`).

## 6. Execution order (one clean round)

1. `get_sa_feed` query + tests.
2. `/sa/feed` route.
3. Register `get_sa_feed` (ToolRegistry + OpenAI + Anthropic bridges) + count-assert bumps.
4. News surface SA filter.
5. GUI visual check (run the app).

Then **C-2 (AI Research / Chat surface)** — the open-ended-question entry; needs these evidence primitives so it isn't "just a chat box".

## 7. Out of scope (C-1)

- AI Research / Chat surface → **C-2**.
- ticker-detail SA sections (recent articles, Alpha Picks status, high-value comments, per-ticker comment focus) → **C-3**.
- candidate soft-catalog confidence/filter (the DD/DB/AU/SB/SA ambiguous-symbol layer beyond v1.2 stopwords).
- `extract_sa_comment_signals` scheduling → decide after the Monday soak final health check.
