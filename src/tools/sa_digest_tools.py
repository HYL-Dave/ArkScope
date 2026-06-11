"""Agent tool for SA Digest / Reading Workflow v1 (P1.3 commit 1).

Single read-only tool: ``get_sa_digest(ticker, days, max_articles, max_news,
max_comments, min_comment_score)`` returns a deterministic evidence pack
composed from three existing SA tables:

  - ``sa_articles``                 (sql/008) — Alpha Picks articles
  - ``sa_market_news``              (sql/009) — market-news feed
  - ``sa_comment_signals``          (sql/012) — Stage 1 rule-based scores
    JOIN ``sa_article_comments``    (sql/008) — comment bodies
    LEFT JOIN ``sa_articles``       (sql/008) — for ``article_url``

Per spec ``docs/design/P1_3_SPEC.md`` §3-§6:

  - Each source has its own try/except so a partial failure does not
    blank the entire digest. Errors land in ``data_quality.errors[]``
    with a source-prefixed message and the digest still ships best-effort
    rows for the other sources.
  - ``needs_verification=true`` comments are RETURNED, not filtered. The
    flag travels through to the agent which is expected to treat them
    as opinion needing audit.
  - Mention-kind classification: a comment whose ticker appears in BOTH
    ``ticker_mentions`` and ``candidate_mentions`` is classified as
    ``'ticker'`` (stronger signal wins).
  - LEFT JOIN ``sa_articles`` keeps a comment with a pruned parent
    article row alive (``article_url=NULL``); this surfaces as a
    ``data_quality.missing[]`` line rather than dropping the row.
  - The comments query uses a layered CTE: per-article cap (3) is
    applied BEFORE the per-kind ``rn_per_kind`` is computed, so the
    per-kind side can never underfill due to over-3 rows from one
    article eating the budget.

The output is structured JSON-serializable Python (no Decimal/datetime
leaks). The calling agent produces any Chinese decision summary on top
of this evidence pack — the tool itself does NOT call an LLM.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables — kept as module constants so tests can lock the values.
# ---------------------------------------------------------------------------

PER_ARTICLE_COMMENT_CAP = 3        # ≤3 comments per article (anti-domination)
NEWS_DISCUSSION_GATE = 10          # comments_count >= this for high_discussion_news
EXCERPT_LEN = 500                  # chars for article body / news summary / comment preview

_DAYS_MIN, _DAYS_MAX = 1, 90
_MAX_ARTICLES_MIN, _MAX_ARTICLES_MAX = 1, 20
_MAX_NEWS_MIN, _MAX_NEWS_MAX = 1, 20
_MAX_COMMENTS_MIN, _MAX_COMMENTS_MAX = 1, 30


_DISABLED_MSG = (
    "Seeking Alpha layer is disabled. Set seeking_alpha.enabled: true in "
    "config/user_profile.yaml to use get_sa_digest."
)
_BACKEND_MSG = (
    "get_sa_digest requires the PostgreSQL DAL backend; current DAL has "
    "no _get_conn (probably FileBackend)."
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def get_sa_digest(
    dal: Any,
    ticker: str,
    days: int = 14,
    max_articles: int = 5,
    max_news: int = 5,
    max_comments: int = 8,
    min_comment_score: float = 4.0,
) -> Dict[str, Any]:
    """Return a deterministic SA evidence pack for one ticker.

    See ``docs/design/P1_3_SPEC.md`` §3-§6 for the contract. Output keys
    are stable; empty sources return ``[]`` rather than being omitted.

    Args:
        dal: DAL whose ``_backend`` exposes ``_get_conn``.
        ticker: Symbol (case-insensitive); upper-cased internally.
        days: Lookback window 1..90 (default 14).
        max_articles: Cap on ``recent_articles[]`` 1..20 (default 5).
        max_news: Cap on ``high_discussion_news[]`` 1..20 (default 5).
        max_comments: Per-kind cap on comments 1..30 (default 8). Total
            comments across both kinds is at most ``2 * max_comments``.
        min_comment_score: Stage 1 ``high_value_score`` floor 0..10
            (default 4.0). ``needs_verification`` is NOT filtered.
    """
    # 1. Feature gate
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    # 2. Backend availability — non-Postgres DAL gracefully degrades
    backend = getattr(dal, "_backend", None)
    if backend is None or not hasattr(backend, "_get_conn"):
        return _empty_pack(
            ticker, days,
            error=_BACKEND_MSG,
        )

    # 3. Validate / clamp params
    sym = (ticker or "").strip().upper()
    if not sym:
        return _empty_pack(
            "", days,
            error="ticker is required.",
        )

    days = _clamp(int(days), _DAYS_MIN, _DAYS_MAX)
    max_articles = _clamp(int(max_articles), _MAX_ARTICLES_MIN, _MAX_ARTICLES_MAX)
    max_news = _clamp(int(max_news), _MAX_NEWS_MIN, _MAX_NEWS_MAX)
    max_comments = _clamp(int(max_comments), _MAX_COMMENTS_MIN, _MAX_COMMENTS_MAX)
    # Stage 1 high_value_score is bounded 0..10; clamp so out-of-range
    # input either returns no rows or includes everything, never errors.
    min_comment_score = _clamp_float(float(min_comment_score), 0.0, 10.0)

    # 4. Window
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(days=days)
    window = {
        "start": window_start.isoformat(),
        "end": now.isoformat(),
        "days": days,
    }

    errors: List[str] = []
    missing: List[str] = []

    # 5. Per-source queries — independent try/except so one failure does
    #    not zero out the whole digest.
    articles = _query_articles(
        backend, sym, window_start, max_articles, errors, missing,
    )
    news = _query_news(
        backend, sym, window_start, max_news, errors,
    )
    ticker_comments, candidate_comments = _query_comments(
        backend, sym, days, min_comment_score, max_comments, errors, missing,
    )

    rows_count = {
        "articles": len(articles),
        "news": len(news),
        "comments_ticker": len(ticker_comments),
        "comments_candidate": len(candidate_comments),
    }

    source_notes = _build_source_notes(
        ticker=sym,
        days=days,
        max_articles=max_articles,
        max_news=max_news,
        max_comments=max_comments,
        min_comment_score=min_comment_score,
        rows_count=rows_count,
    )

    return {
        "ticker": sym,
        "window": window,
        "recent_articles": articles,
        "high_discussion_news": news,
        "high_value_comments": {
            "ticker_mentions": ticker_comments,
            "candidate_mentions": candidate_comments,
        },
        "data_quality": {
            "rows": rows_count,
            "errors": errors,
            "missing": missing,
        },
        "source_notes": source_notes,
    }


# ---------------------------------------------------------------------------
# Source queries
# ---------------------------------------------------------------------------


def _query_articles(
    backend: Any,
    ticker: str,
    window_start: datetime,
    max_articles: int,
    errors: List[str],
    missing: List[str],
) -> List[Dict[str, Any]]:
    """SELECT from sa_articles. Best-effort; appends to errors on failure.

    3d prep-3 dispatch: SA-local mode (``backend._sa_db`` set) reads
    sa_capture.db; None/absent = PG mode with the SQL below untouched.
    """
    sql = f"""
        SELECT
            article_id,
            title,
            author,
            published_date,
            url,
            article_type,
            comments_count,
            LEFT(COALESCE(body_markdown, title), {EXCERPT_LEN}) AS summary_excerpt,
            (body_markdown IS NULL) AS body_missing
        FROM sa_articles
        WHERE UPPER(ticker) = %(ticker)s
          AND published_date >= %(window_start_date)s
        ORDER BY published_date DESC NULLS LAST, fetched_at DESC
        LIMIT %(max_articles)s
    """
    sa_db = getattr(backend, "_sa_db", None)
    try:
        if sa_db is not None:
            rows = _query_articles_local(sa_db, ticker, window_start, max_articles)
        else:
            rows = _fetch_dicts(
                backend,
                sql,
                {
                    "ticker": ticker,
                    "window_start_date": window_start.date(),
                    "max_articles": max_articles,
                },
            )
    except Exception as exc:
        logger.error("get_sa_digest articles query failed: %s", exc)
        errors.append(f"articles: query failed ({exc})")
        return []

    body_missing = sum(1 for r in rows if r.pop("body_missing", False))
    if rows and body_missing:
        missing.append(
            f"body_markdown unavailable for {body_missing} of {len(rows)} "
            f"articles (extension hasn't fetched detail)"
        )

    return [_normalize_article_row(r) for r in rows]


def _query_news(
    backend: Any,
    ticker: str,
    window_start: datetime,
    max_news: int,
    errors: List[str],
) -> List[Dict[str, Any]]:
    """SELECT from sa_market_news with comments_count >= NEWS_DISCUSSION_GATE.

    3d prep-3 dispatch: SA-local mode (``backend._sa_db`` set) reads
    sa_capture.db; None/absent = PG mode with the SQL below untouched.
    """
    sql = f"""
        SELECT
            news_id,
            title,
            url,
            published_at,
            tickers,
            category,
            comments_count,
            LEFT(summary, {EXCERPT_LEN}) AS summary_excerpt
        FROM sa_market_news
        WHERE %(ticker)s = ANY(tickers)
          AND published_at >= %(window_start)s
          AND comments_count >= %(gate)s
        ORDER BY comments_count DESC, published_at DESC
        LIMIT %(max_news)s
    """
    sa_db = getattr(backend, "_sa_db", None)
    try:
        if sa_db is not None:
            rows = _query_news_local(sa_db, ticker, window_start, max_news)
        else:
            rows = _fetch_dicts(
                backend,
                sql,
                {
                    "ticker": ticker,
                    "window_start": window_start,
                    "gate": NEWS_DISCUSSION_GATE,
                    "max_news": max_news,
                },
            )
    except Exception as exc:
        logger.error("get_sa_digest news query failed: %s", exc)
        errors.append(f"news: query failed ({exc})")
        return []

    return [_normalize_news_row(r) for r in rows]


def _query_comments(
    backend: Any,
    ticker: str,
    days: int,
    min_comment_score: float,
    max_comments: int,
    errors: List[str],
    missing: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Layered-CTE query — per-article cap applied BEFORE per-kind cap."""
    try:
        from src.sa.comment_signals import RULE_SET_VERSION as _CURRENT_VERSION
    except Exception as exc:
        logger.error("Could not import RULE_SET_VERSION: %s", exc)
        errors.append(f"comments: import error ({exc})")
        return [], []

    sql = """
        WITH base AS (
            SELECT
                c.id AS comment_row_id,
                c.article_id,
                c.comment_id,
                c.commenter,
                c.upvotes,
                c.comment_date,
                LEFT(c.comment_text, %(excerpt_len)s) AS preview,
                s.high_value_score,
                s.ticker_mentions,
                s.candidate_mentions,
                s.keyword_buckets,
                s.needs_verification,
                a.url AS article_url,
                CASE
                  WHEN %(ticker)s = ANY(s.ticker_mentions) THEN 'ticker'
                  ELSE 'candidate'
                END AS mention_kind
            FROM sa_comment_signals s
            JOIN sa_article_comments c ON c.id = s.comment_row_id
            LEFT JOIN sa_articles a    ON a.article_id = c.article_id
            WHERE c.comment_date >= NOW() - (%(days)s || ' days')::INTERVAL
              AND s.high_value_score >= %(min_score)s
              AND s.rule_set_version  = %(version)s
              AND (
                %(ticker)s = ANY(s.ticker_mentions)
                OR %(ticker)s = ANY(s.candidate_mentions)
              )
        ),
        per_article AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY mention_kind, article_id
                    ORDER BY high_value_score DESC, comment_date DESC
                ) AS rn_per_article
            FROM base
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY mention_kind
                    ORDER BY high_value_score DESC, comment_date DESC
                ) AS rn_per_kind
            FROM per_article
            WHERE rn_per_article <= %(per_article_cap)s
        )
        SELECT *
        FROM ranked
        WHERE rn_per_kind <= %(max_comments)s
        ORDER BY mention_kind, high_value_score DESC, comment_date DESC
    """
    # 3d prep-3 dispatch: SA-local mode (backend._sa_db set) reads
    # sa_capture.db; None/absent = PG mode with the SQL above untouched.
    sa_db = getattr(backend, "_sa_db", None)
    try:
        if sa_db is not None:
            rows = _query_comments_local(
                sa_db, ticker, days, min_comment_score, max_comments,
                _CURRENT_VERSION,
            )
        else:
            rows = _fetch_dicts(
                backend,
                sql,
                {
                    "ticker": ticker,
                    "days": days,
                    "min_score": min_comment_score,
                    "version": _CURRENT_VERSION,
                    "excerpt_len": EXCERPT_LEN,
                    "per_article_cap": PER_ARTICLE_COMMENT_CAP,
                    "max_comments": max_comments,
                },
            )
    except Exception as exc:
        logger.error("get_sa_digest comments query failed: %s", exc)
        errors.append(f"comments: query failed ({exc})")
        return [], []

    ticker_list: List[Dict[str, Any]] = []
    candidate_list: List[Dict[str, Any]] = []
    url_missing = 0
    for r in rows:
        kind = r.pop("mention_kind", None)
        # rn_* helper columns are not part of the public schema
        r.pop("rn_per_article", None)
        r.pop("rn_per_kind", None)
        if r.get("article_url") is None:
            url_missing += 1
        normalized = _normalize_comment_row(r)
        if kind == "ticker":
            ticker_list.append(normalized)
        else:
            candidate_list.append(normalized)

    total = len(ticker_list) + len(candidate_list)
    if total and url_missing:
        missing.append(
            f"article_url unavailable for {url_missing} of {total} comments "
            f"(parent sa_articles row pruned)"
        )

    return ticker_list, candidate_list


# ---------------------------------------------------------------------------
# Source notes (the human-readable part of the evidence pack)
# ---------------------------------------------------------------------------


def _build_source_notes(
    *,
    ticker: str,
    days: int,
    max_articles: int,
    max_news: int,
    max_comments: int,
    min_comment_score: float,
    rows_count: Dict[str, int],
) -> List[str]:
    notes: List[str] = []
    notes.append(
        f"Articles up to {days}d back from sa_articles, ordered by "
        f"published_date DESC (cap {max_articles})."
    )
    notes.append(
        f"News restricted to comments_count >= {NEWS_DISCUSSION_GATE}, ordered "
        f"by comments_count DESC (cap {max_news})."
    )
    try:
        from src.sa.comment_signals import RULE_SET_VERSION as _v
    except Exception:
        _v = "?"
    notes.append(
        f"Comments from sa_comment_signals (rule_set_version={_v}) with "
        f"high_value_score >= {min_comment_score}; "
        f"<= {PER_ARTICLE_COMMENT_CAP} per article and <= {max_comments} per "
        f"mention kind to avoid single-thread or single-bucket domination."
    )
    notes.append(
        "needs_verification=true comments are kept (not filtered) — agent "
        "should treat as investor opinion, not fact."
    )

    # Empty-source per-line callouts (so silence is not mistaken for absence
    # of a signal).
    if rows_count["articles"] == 0:
        notes.append(f"No articles in {days}d window for {ticker}.")
    if rows_count["news"] == 0:
        notes.append(
            f"No high-discussion news (>= {NEWS_DISCUSSION_GATE} comments) "
            f"in {days}d window for {ticker}."
        )
    if rows_count["comments_ticker"] == 0 and rows_count["comments_candidate"] == 0:
        notes.append(
            f"No high-value comments (score >= {min_comment_score}) in "
            f"{days}d window mentioning {ticker}."
        )

    return notes


# ---------------------------------------------------------------------------
# Helpers — cursor wrapper, normalization, clamping
# ---------------------------------------------------------------------------


def _fetch_dicts(backend: Any, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run query and return list-of-dicts. RealDictCursor pattern."""
    from psycopg2 import extras as _pg_extras

    conn = backend._get_conn()
    with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# SA-local (sa_capture.db) variants — slice 3d prep-3.
#
# Dispatch: each _query_* checks ``getattr(backend, "_sa_db", None)``;
# None/absent = PG mode (the SQL above, byte-identical). The variants below
# return rows in the SAME dict shape the PG queries produced, so the shared
# normalizers run unchanged. Dialect sweep (runbook §1): named %(x)s → ?;
# LEFT(s,n) → substr(s,1,n); NOW()-INTERVAL / date params → Python-computed
# canonical TEXT cutoffs (lexicographic == time order); TEXT[] ``= ANY()`` →
# junction joins; jsonb → json.loads; RealDictCursor → sqlite3.Row.
# ---------------------------------------------------------------------------


def _fetch_dicts_local(sa_db: str, sql: str, params: tuple) -> List[Dict[str, Any]]:
    """SQLite twin of _fetch_dicts: read-only sa_capture.db, positional params."""
    from src import sa_capture_store as _store

    conn = _store.connect(sa_db, read_only=True)
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _query_articles_local(
    sa_db: str, ticker: str, window_start: datetime, max_articles: int
) -> List[Dict[str, Any]]:
    """sa_articles rows from sa_capture.db (PG row shape, incl. body_missing).

    published_date is canonical 'YYYY-MM-DD' TEXT — the >= compare and the
    DESC ordering are lexicographic, which equals date order. NULLS LAST is
    SQLite's native DESC behavior (and the WHERE already excludes NULLs).
    """
    sql = f"""
        SELECT
            article_id,
            title,
            author,
            published_date,
            url,
            article_type,
            comments_count,
            substr(COALESCE(body_markdown, title), 1, {EXCERPT_LEN}) AS summary_excerpt,
            (body_markdown IS NULL) AS body_missing
        FROM sa_articles
        WHERE UPPER(ticker) = ?
          AND published_date >= ?
        ORDER BY published_date DESC, fetched_at DESC
        LIMIT ?
    """
    return _fetch_dicts_local(
        sa_db, sql, (ticker, window_start.date().isoformat(), max_articles)
    )


def _query_news_local(
    sa_db: str, ticker: str, window_start: datetime, max_news: int
) -> List[Dict[str, Any]]:
    """sa_market_news rows from sa_capture.db (PG row shape).

    ``%(ticker)s = ANY(tickers)`` → membership in the sa_market_news_tickers
    junction; the ``tickers`` TEXT[] column is re-assembled into a Python list
    per row from the same junction (one query, not N+1).
    """
    from src import sa_capture_store as _store

    sql = f"""
        SELECT
            n.id AS _row_id,
            n.news_id,
            n.title,
            n.url,
            n.published_at,
            n.category,
            n.comments_count,
            substr(n.summary, 1, {EXCERPT_LEN}) AS summary_excerpt
        FROM sa_market_news n
        WHERE n.id IN (SELECT news_row_id FROM sa_market_news_tickers WHERE ticker = ?)
          AND n.published_at >= ?
          AND n.comments_count >= ?
        ORDER BY n.comments_count DESC, n.published_at DESC
        LIMIT ?
    """
    conn = _store.connect(sa_db, read_only=True)
    try:
        rows = [dict(r) for r in conn.execute(
            sql,
            (ticker, _store.canon_ts(window_start), NEWS_DISCUSSION_GATE, max_news),
        ).fetchall()]
        row_ids = [r["_row_id"] for r in rows]
        tickers_by_row: Dict[int, List[str]] = {}
        if row_ids:
            placeholders = ",".join("?" * len(row_ids))
            for jr in conn.execute(
                f"SELECT news_row_id, ticker FROM sa_market_news_tickers "
                f"WHERE news_row_id IN ({placeholders}) ORDER BY rowid",
                tuple(row_ids),
            ):
                tickers_by_row.setdefault(jr["news_row_id"], []).append(jr["ticker"])
        for r in rows:
            r["tickers"] = tickers_by_row.get(r.pop("_row_id"), [])
        return rows
    finally:
        conn.close()


def _query_comments_local(
    sa_db: str,
    ticker: str,
    days: int,
    min_comment_score: float,
    max_comments: int,
    rule_set_version: str,
) -> List[Dict[str, Any]]:
    """Layered-CTE comments query against sa_capture.db (PG row shape).

    Same CTE structure (ROW_NUMBER OVER is fine in SQLite 3.25+); the
    ``= ANY(mentions)`` membership tests — both the mention_kind CASE and the
    WHERE filter — become EXISTS probes on the junction tables. The mention
    arrays themselves are NOT selected: the digest normalizer never emits
    them (mention_kind carries the classification), matching the PG output.
    """
    import json as _json

    from src import sa_capture_store as _store

    cutoff = _store.canon_ts(datetime.now(tz=timezone.utc) - timedelta(days=days))
    sql = """
        WITH base AS (
            SELECT
                c.id AS comment_row_id,
                c.article_id,
                c.comment_id,
                c.commenter,
                c.upvotes,
                c.comment_date,
                substr(c.comment_text, 1, ?) AS preview,
                s.high_value_score,
                s.keyword_buckets,
                s.needs_verification,
                a.url AS article_url,
                CASE
                  WHEN EXISTS (
                      SELECT 1 FROM sa_signal_ticker_mentions tm
                      WHERE tm.comment_row_id = s.comment_row_id
                        AND tm.ticker = ?
                  ) THEN 'ticker'
                  ELSE 'candidate'
                END AS mention_kind
            FROM sa_comment_signals s
            JOIN sa_article_comments c ON c.id = s.comment_row_id
            LEFT JOIN sa_articles a    ON a.article_id = c.article_id
            WHERE c.comment_date >= ?
              AND s.high_value_score >= ?
              AND s.rule_set_version  = ?
              AND (
                EXISTS (
                    SELECT 1 FROM sa_signal_ticker_mentions tm2
                    WHERE tm2.comment_row_id = s.comment_row_id
                      AND tm2.ticker = ?
                )
                OR EXISTS (
                    SELECT 1 FROM sa_signal_candidate_mentions cm
                    WHERE cm.comment_row_id = s.comment_row_id
                      AND cm.ticker = ?
                )
              )
        ),
        per_article AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY mention_kind, article_id
                    ORDER BY high_value_score DESC, comment_date DESC
                ) AS rn_per_article
            FROM base
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY mention_kind
                    ORDER BY high_value_score DESC, comment_date DESC
                ) AS rn_per_kind
            FROM per_article
            WHERE rn_per_article <= ?
        )
        SELECT *
        FROM ranked
        WHERE rn_per_kind <= ?
        ORDER BY mention_kind, high_value_score DESC, comment_date DESC
    """
    rows = _fetch_dicts_local(
        sa_db,
        sql,
        (
            EXCERPT_LEN,
            ticker,
            cutoff,
            min_comment_score,
            rule_set_version,
            ticker,
            ticker,
            PER_ARTICLE_COMMENT_CAP,
            max_comments,
        ),
    )
    # jsonb → dict parity (psycopg2 decoded keyword_buckets automatically).
    for r in rows:
        kb = r.get("keyword_buckets")
        if isinstance(kb, str):
            try:
                r["keyword_buckets"] = _json.loads(kb)
            except ValueError:
                pass
    return rows


def _normalize_article_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "article_id":      r.get("article_id"),
        "title":           r.get("title"),
        "author":          r.get("author"),
        "published_date":  _iso(r.get("published_date")),
        "url":             r.get("url"),
        "article_type":    r.get("article_type"),
        "comments_count":  _to_int(r.get("comments_count")),
        "summary_excerpt": _truncated(r.get("summary_excerpt")),
    }


def _normalize_news_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "news_id":         r.get("news_id"),
        "title":           r.get("title"),
        "url":             r.get("url"),
        "published_at":    _iso(r.get("published_at")),
        "tickers":         list(r.get("tickers") or []),
        "category":        r.get("category"),
        "comments_count":  _to_int(r.get("comments_count")),
        "summary_excerpt": _truncated(r.get("summary_excerpt")),
    }


def _normalize_comment_row(r: Dict[str, Any]) -> Dict[str, Any]:
    score = r.get("high_value_score")
    return {
        "comment_id":          r.get("comment_id"),
        "article_id":          r.get("article_id"),
        "article_url":         r.get("article_url"),
        "commenter":           r.get("commenter"),
        "comment_date":        _iso(r.get("comment_date")),
        "upvotes":             _to_int(r.get("upvotes")),
        "preview":             _truncated(r.get("preview")),
        "high_value_score":    float(score) if score is not None else None,
        "keyword_buckets":     r.get("keyword_buckets") or {},
        "needs_verification":  bool(r.get("needs_verification")),
    }


def _empty_pack(ticker: str, days: int, *, error: str) -> Dict[str, Any]:
    """Degraded-mode pack — backend unavailable or invalid input."""
    now = datetime.now(tz=timezone.utc)
    return {
        "ticker": (ticker or "").upper(),
        "window": {
            "start": (now - timedelta(days=days)).isoformat(),
            "end":   now.isoformat(),
            "days":  days,
        },
        "recent_articles": [],
        "high_discussion_news": [],
        "high_value_comments": {"ticker_mentions": [], "candidate_mentions": []},
        "data_quality": {
            "rows": {
                "articles": 0,
                "news": 0,
                "comments_ticker": 0,
                "comments_candidate": 0,
            },
            "errors": [error],
            "missing": [],
        },
        "source_notes": [
            "Digest could not be assembled — see data_quality.errors[].",
        ],
    }


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _truncated(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    if len(s) >= EXCERPT_LEN:
        # The SQL already LEFT(...)'d to EXCERPT_LEN; the trailing ellipsis is
        # informational — readers can see the excerpt is truncated.
        return s[:EXCERPT_LEN].rstrip() + "..."
    return s


def _is_sa_enabled() -> bool:
    """Mirror the existing src/tools/sa_tools.py gate."""
    try:
        from src.agents.config import get_agent_config
        return bool(get_agent_config().sa_enabled)
    except Exception:
        return False