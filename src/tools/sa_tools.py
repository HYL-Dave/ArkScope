"""
Seeking Alpha Alpha Picks tool functions.

7 tools: get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
         get_sa_articles, get_sa_article_detail, get_sa_market_news,
         list_high_value_comments
All require DAL. Alpha Picks tools are category="portfolio"; market news + comments are category="news".
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISABLED_MSG = (
    "Seeking Alpha Alpha Picks is not enabled. "
    "To enable: set seeking_alpha.enabled: true in config/user_profile.yaml "
    "and install the SA Alpha Picks Chrome extension (see extensions/sa_alpha_picks/)"
)


def _is_sa_enabled() -> bool:
    """Check if SA Alpha Picks is enabled in config."""
    try:
        from src.agents.config import get_agent_config
        return get_agent_config().sa_enabled
    except Exception:
        return False


def _get_client(dal):
    """Create SAAlphaPicksClient with config values."""
    from src.agents.config import get_agent_config
    from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

    config = get_agent_config()
    return SAAlphaPicksClient(
        dal=dal,
        cache_hours=config.sa_cache_hours,
        detail_cache_days=config.sa_detail_cache_days,
    )


def get_sa_alpha_picks(
    dal: Any, status: str = "all", sector: Optional[str] = None
) -> Dict:
    """Get SA Alpha Picks portfolio (cached, auto-refresh if stale).

    Returns current and/or closed picks with freshness metadata.
    is_partial = not (freshness.current.ok and freshness.closed.ok).
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        result = client.get_portfolio()

        if "error" in result and result["error"]:
            return result

        # Filter by status
        response = {}
        if status in ("all", "current"):
            response["current"] = result.get("current", [])
        if status in ("all", "closed"):
            response["closed"] = result.get("closed", [])

        # Filter by sector if specified
        if sector:
            sector_lower = sector.lower()
            for key in ("current", "closed"):
                if key in response:
                    response[key] = [
                        p for p in response[key]
                        if (p.get("sector") or "").lower().startswith(sector_lower)
                    ]

        response["freshness"] = result.get("freshness", {})
        response["is_partial"] = result.get("is_partial", False)
        if result.get("stale_warning"):
            response["stale_warning"] = result["stale_warning"]
        if result.get("refresh_hint"):
            response["refresh_hint"] = result["refresh_hint"]
        return response

    except Exception as e:
        logger.error("get_sa_alpha_picks error: %s", e)
        return {"error": str(e)}


def get_sa_pick_detail(
    dal: Any, symbol: str, picked_date: Optional[str] = None
) -> Dict:
    """Get detail for a specific Alpha Pick.

    picked_date=None: latest current (non-stale first), then stale, then hint.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        result = client.get_pick_detail(symbol, picked_date)

        if result is None:
            # Check if symbol exists in closed
            closed = dal.get_sa_portfolio(portfolio_status="closed", symbol=symbol)
            if closed:
                latest = sorted(closed, key=lambda x: x.get("picked_date", ""), reverse=True)[0]
                return {
                    "error": None,
                    "detail": None,
                    "hint": (
                        f"{symbol} is not in current Alpha Picks. "
                        f"It was picked on {latest.get('picked_date', '?')} (now closed). "
                        f"Use: /ap {symbol} {latest.get('picked_date', '')}"
                    ),
                }
            return {"error": f"{symbol} not found in Alpha Picks"}

        return result

    except Exception as e:
        logger.error("get_sa_pick_detail error: %s", e)
        return {"error": str(e)}


def refresh_sa_alpha_picks(dal: Any) -> Dict:
    """Return current SA data state + refresh instructions (read-only status).

    Actual refresh is done by the Chrome extension. This returns cached data
    with a refresh_hint directing the user to click the extension.

    Read-only: this does NOT modify ``config/tickers_core.json`` or any
    profile/universe state. The research-universe sync from Alpha Picks is owned
    by the SA native host on extension-refresh success (a PROTECTED pipeline
    path), not by this status tool. An explicit, gated "follow Alpha Picks"
    action (``profile_state_write``) is a desktop-phase tool — see
    ARKSCOPE_TOOL_CATALOG §1.5.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        return client.refresh_portfolio()
    except Exception as e:
        logger.error("refresh_sa_alpha_picks error: %s", e)
        return {"error": str(e)}


def get_sa_articles(
    dal: Any,
    ticker: Optional[str] = None,
    keyword: Optional[str] = None,
    article_type: Optional[str] = None,
    limit: int = 10,
) -> Dict:
    """Search SA Alpha Picks articles.

    Returns article list with title, date, ticker, type, comments_count.
    Use get_sa_article_detail for full content + comments.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        articles = dal.get_sa_articles(
            ticker=ticker, keyword=keyword,
            article_type=article_type, limit=limit,
        )
        return {"articles": articles, "count": len(articles)}
    except Exception as e:
        logger.error("get_sa_articles error: %s", e)
        return {"error": str(e)}


def get_sa_article_detail(dal: Any, article_id: str) -> Dict:
    """Get full SA article content + comments.

    Returns body_markdown + comment tree for a specific article.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        result = dal.get_sa_article_detail(article_id)
        if not result:
            return {"error": f"Article {article_id} not found"}
        return result
    except Exception as e:
        logger.error("get_sa_article_detail error: %s", e)
        return {"error": str(e)}


def get_sa_market_news(
    dal: Any,
    ticker: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> Dict:
    """Search recent Seeking Alpha market-news items.

    Returns metadata-only feed items captured from /market-news: title, URL,
    tickers, publish time text, summary, and comment count. When detail pages
    have been fetched, results also include `body_markdown` and `detail_fetched_at`.
    The Chrome extension performs the refresh; this tool reads the local DB cache.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        items = dal.get_sa_market_news(ticker=ticker, keyword=keyword, limit=limit)
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error("get_sa_market_news error: %s", e)
        return {"error": str(e)}


def list_high_value_comments(
    dal: Any,
    window_days: int = 7,
    ticker: Optional[str] = None,
    min_score: float = 2.0,
    limit: int = 20,
) -> Dict:
    """List high-scoring SA comments within a time window.

    Reads from sa_comment_signals (rule-based extraction; see
    docs/design/SA_COMMENT_INTELLIGENCE_PLAN.md §5.1). Comments are ranked
    by ``high_value_score`` (0..10 weighted sum of ticker mentions, keyword
    bucket hits, external links, and log(upvotes)).

    Args:
        window_days: lookback window using ``comment_date`` (1..90).
        ticker: optional filter — only comments whose ``ticker_mentions``
            includes this symbol (case-insensitive).
        min_score: cutoff (default 2.0). Anything below is filtered out.
        limit: max comments returned (1..50).

    Returns:
        ``{count, window_days, min_score, comments: [{...}]}`` where each
        comment dict carries: comment_id, article_id, commenter, comment_date,
        upvotes, preview (first 300 chars), high_value_score, ticker_mentions,
        candidate_mentions, keyword_buckets, needs_verification.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    backend = getattr(dal, "_backend", None)
    if backend is None or not hasattr(backend, "_get_conn"):
        return {
            "error": "DB unavailable; high-value comments require the database backend.",
            "comments": [],
            "count": 0,
        }

    try:
        from src.sa.comment_signals import RULE_SET_VERSION as _CURRENT_VERSION
        window_days = max(1, min(int(window_days), 90))
        limit = max(1, min(int(limit), 50))
        min_score = float(min_score)

        # 3d prep-3 dispatch: SA-local mode is duck-typed via backend._sa_db
        # (None/absent = PG mode, existing SQL untouched). Raw _get_conn()
        # bypasses the DatabaseBackend method layer, so after the SA cutover
        # this PG query would silently read the FROZEN PG — route it locally.
        sa_db = getattr(backend, "_sa_db", None)
        if sa_db is not None:
            rows = _query_high_value_comments_local(
                sa_db,
                window_days=window_days,
                min_score=min_score,
                rule_set_version=_CURRENT_VERSION,
                ticker=ticker,
                limit=limit,
            )
        else:
            conn = backend._get_conn()
            params: List[Any] = [window_days, min_score, _CURRENT_VERSION]
            ticker_clause = ""
            if ticker:
                ticker_clause = " AND %s = ANY(s.ticker_mentions)"
                params.append(ticker.upper())
            params.append(limit)

            sql = f"""
                SELECT
                    c.id AS comment_row_id,
                    c.article_id,
                    c.comment_id,
                    c.commenter,
                    c.upvotes,
                    c.comment_date,
                    LEFT(c.comment_text, 300) AS preview,
                    s.high_value_score,
                    s.ticker_mentions,
                    s.candidate_mentions,
                    s.keyword_buckets,
                    s.needs_verification,
                    s.rule_set_version
                FROM sa_comment_signals s
                JOIN sa_article_comments c ON c.id = s.comment_row_id
                WHERE c.comment_date >= NOW() - (%s || ' days')::INTERVAL
                  AND s.high_value_score >= %s
                  AND s.rule_set_version = %s
                  {ticker_clause}
                ORDER BY s.high_value_score DESC, c.comment_date DESC
                LIMIT %s
            """
            from psycopg2 import extras as _pg_extras
            with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()

        comments: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            cd = d.get("comment_date")
            if cd is not None and hasattr(cd, "isoformat"):
                d["comment_date"] = cd.isoformat()
            score = d.get("high_value_score")
            if score is not None:
                d["high_value_score"] = float(score)
            comments.append(d)

        return {
            "count": len(comments),
            "window_days": window_days,
            "min_score": min_score,
            "rule_set_version": _CURRENT_VERSION,
            "ticker_filter": ticker.upper() if ticker else None,
            "comments": comments,
        }
    except Exception as e:
        logger.error("list_high_value_comments error: %s", e)
        return {"error": str(e), "comments": [], "count": 0}


def _query_high_value_comments_local(
    sa_db: str,
    *,
    window_days: int,
    min_score: float,
    rule_set_version: str,
    ticker: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    """SQLite (sa_capture.db) variant of the high-value-comments query (3d prep-3).

    PG-isms translated (runbook §1):
      - ``%s = ANY(s.ticker_mentions)`` → junction membership on
        sa_signal_ticker_mentions (TEXT[] columns were replaced by junctions, L8);
      - ``NOW() - (N || ' days')::INTERVAL`` → Python-computed canonical cutoff
        (comment_date is canonical UTC ISO TEXT; lexicographic == time order);
      - LEFT(s, n) → substr(s, 1, n); RealDictCursor → sqlite3.Row.

    Returns rows in the PG dict shape: ticker_mentions / candidate_mentions are
    re-assembled into Python LISTS from the junction tables (psycopg2 TEXT[]
    parity), keyword_buckets json.loads'd (jsonb parity), needs_verification a
    Python bool. RULE_SET_VERSION filter + ordering semantics are identical.
    """
    from src import sa_capture_store as store

    cutoff = store.canon_ts(
        datetime.now(timezone.utc) - timedelta(days=window_days)
    )
    params: List[Any] = [cutoff, min_score, rule_set_version]
    ticker_clause = ""
    if ticker:
        ticker_clause = (
            " AND EXISTS (SELECT 1 FROM sa_signal_ticker_mentions tm "
            "WHERE tm.comment_row_id = s.comment_row_id AND tm.ticker = ?)"
        )
        params.append(ticker.upper())
    params.append(limit)

    conn = store.connect(sa_db, read_only=True)
    try:
        rows = conn.execute(
            f"""
            SELECT
                c.id AS comment_row_id,
                c.article_id,
                c.comment_id,
                c.commenter,
                c.upvotes,
                c.comment_date,
                substr(c.comment_text, 1, 300) AS preview,
                s.high_value_score,
                s.keyword_buckets,
                s.needs_verification,
                s.rule_set_version
            FROM sa_comment_signals s
            JOIN sa_article_comments c ON c.id = s.comment_row_id
            WHERE c.comment_date >= ?
              AND s.high_value_score >= ?
              AND s.rule_set_version = ?
              {ticker_clause}
            ORDER BY s.high_value_score DESC, c.comment_date DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        # Re-assemble the TEXT[] columns as Python lists (one query per junction,
        # not N+1) — returned dicts must carry LISTS like psycopg2 did.
        row_ids = [r["comment_row_id"] for r in rows]
        mentions: Dict[str, Dict[int, List[str]]] = {"ticker": {}, "candidate": {}}
        if row_ids:
            placeholders = ",".join("?" * len(row_ids))
            for kind, table in (
                ("ticker", "sa_signal_ticker_mentions"),
                ("candidate", "sa_signal_candidate_mentions"),
            ):
                for jr in conn.execute(
                    f"SELECT comment_row_id, ticker FROM {table} "
                    f"WHERE comment_row_id IN ({placeholders}) ORDER BY rowid",
                    tuple(row_ids),
                ):
                    mentions[kind].setdefault(
                        jr["comment_row_id"], []
                    ).append(jr["ticker"])

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            rid = d["comment_row_id"]
            d["ticker_mentions"] = mentions["ticker"].get(rid, [])
            d["candidate_mentions"] = mentions["candidate"].get(rid, [])
            kb = d.get("keyword_buckets")
            if isinstance(kb, str):
                try:
                    d["keyword_buckets"] = json.loads(kb)
                except ValueError:
                    pass
            d["needs_verification"] = bool(d["needs_verification"])
            out.append(d)
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cross-ticker comment FOCUS (follow-up #1 Layer B) — an agent research primitive
# ---------------------------------------------------------------------------

_FOCUS_SIGNAL_TYPE = "deterministic_rule_based (NOT LLM sentiment)"
# A comment naming >= this many distinct tickers (universe + candidate) is
# "radar-style" — one such comment props up many tickers' rankings at once.
# data_quality.broad_comment_count surfaces how many are in the window so an
# agent can tell a broad-based focus from a few multi-ticker round-up posts.
_FOCUS_BROAD_COMMENT_TICKERS = 8


def _empty_focus(window_days, min_score, *, error=None, rule_set_version=None,
                 empty_reason=None):
    out = {
        "window_days": window_days,
        "min_score": min_score,
        "rule_set_version": rule_set_version,
        "signal_type": _FOCUS_SIGNAL_TYPE,
        "generated_at": None,  # contract: key always present (success path sets it)
        "comment_count": 0,
        "top_tickers": [],
        "top_keyword_buckets": [],
        "candidate_watch": [],
        "data_quality": {},
        "empty_reason": empty_reason,
    }
    if error:
        out["error"] = error
    return out


def get_sa_comment_focus(
    dal: Any,
    window_days: int = 14,
    min_score: float = 2.0,
    limit: int = 10,
) -> Dict:
    """What the SA comment crowd is focused on lately — cross-ticker, DETERMINISTIC.

    A rule-based aggregation over sa_comment_signals (NOT LLM sentiment): ranks
    tickers by recent high-value-comment attention, the keyword buckets driving
    the discussion, and off-universe *candidate* tickers gaining mentions. Built
    for an agent answering "what is Seeking Alpha discussing recently" — every
    figure is traceable to comment/article ids (+ url) so the agent can cite it.

    Args:
        window_days: lookback over ``comment_date`` (1..90, default 14).
        min_score: ``high_value_score`` floor (default 2.0; clamped >= 0).
        limit: max tickers / candidates / buckets returned (1..50, default 10).

    Returns (keys always present; empty sources → [] with an ``empty_reason``):
        window_days, min_score, rule_set_version, signal_type, generated_at,
        comment_count, top_tickers[], top_keyword_buckets[], candidate_watch[],
        data_quality{}, empty_reason. Ranking is deterministic
        (sum_score desc, mention_count desc, ticker asc). Each sample carries
        comment_row_id, comment_id, article_id, url, comment_date,
        high_value_score, preview. Each top_keyword_buckets entry carries
        {bucket, comment_count, tickers, candidate_tickers} (off-universe
        mentions kept separate). data_quality.broad_comment_count flags
        radar-style multi-ticker round-up comments that can skew the ranking.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        from src.sa.comment_signals import RULE_SET_VERSION as ver

        # clamp BEFORE any return so every path (incl. degraded) echoes clamped params
        window_days = max(1, min(int(window_days), 90))
        limit = max(1, min(int(limit), 50))
        min_score = max(0.0, float(min_score))

        backend = getattr(dal, "_backend", None)
        if backend is None or not hasattr(backend, "_get_conn"):
            return _empty_focus(
                window_days, min_score, rule_set_version=ver,
                empty_reason="backend_unavailable",
                error="DB unavailable; SA comment focus requires the database backend.")

        sa_db = getattr(backend, "_sa_db", None)
        if sa_db is None:
            # Post-3d-cutover primitive: SA is local-first, so focus reads
            # sa_capture.db directly. PG mode = pre-flip / rollback only.
            return _empty_focus(
                window_days, min_score, rule_set_version=ver,
                empty_reason="requires_local_sa",
                error="get_sa_comment_focus requires the local sa_capture.db "
                      "(use_local_sa); SA is local-first after the 3d cutover.")

        from src import sa_capture_store as store

        data = _focus_local(
            sa_db, window_days=window_days, min_score=min_score,
            rule_set_version=ver, limit=limit,
        )
        return {
            "window_days": window_days,
            "min_score": min_score,
            "rule_set_version": ver,
            "signal_type": _FOCUS_SIGNAL_TYPE,
            "generated_at": store.now_ts(),
            "comment_count": data["comment_count"],
            "top_tickers": data["top_tickers"],
            "top_keyword_buckets": data["top_keyword_buckets"],
            "candidate_watch": data["candidate_watch"],
            "data_quality": data["data_quality"],
            "empty_reason": data["empty_reason"],
        }
    except Exception as e:
        logger.error("get_sa_comment_focus error: %s", e)
        return _empty_focus(window_days, min_score, empty_reason="error", error=str(e))


def _focus_local(
    sa_db: str,
    *,
    window_days: int,
    min_score: float,
    rule_set_version: str,
    limit: int,
    sample_per: int = 2,
    kw_cap: int = 900,  # < 999 so the IN(...) placeholder list is safe on pre-3.32 SQLite too
) -> Dict[str, Any]:
    """SQLite aggregation for get_sa_comment_focus. Counts come from SQL GROUP BY
    over the junction tables (accurate — NOT capped to a top-N comment sample);
    keyword buckets are parsed from the window's high-value signals (capped at
    kw_cap for memory). Reads only sa_capture.db."""
    from src import sa_capture_store as store

    cutoff = store.canon_ts(datetime.now(timezone.utc) - timedelta(days=window_days))
    where = ("c.comment_date >= ? AND s.high_value_score >= ? "
             "AND s.rule_set_version = ?")
    wp = (cutoff, min_score, rule_set_version)

    conn = store.connect(sa_db, read_only=True)
    try:
        comment_count = conn.execute(
            f"SELECT COUNT(*) FROM sa_comment_signals s "
            f"JOIN sa_article_comments c ON c.id = s.comment_row_id WHERE {where}",
            wp).fetchone()[0]
        comments_in_window = conn.execute(
            "SELECT COUNT(*) FROM sa_article_comments WHERE comment_date >= ?",
            (cutoff,)).fetchone()[0]
        pending_in_window = conn.execute(
            "SELECT COUNT(*) FROM sa_article_comments c WHERE c.comment_date >= ? "
            "AND NOT EXISTS (SELECT 1 FROM sa_comment_signals s "
            "WHERE s.comment_row_id = c.id AND s.rule_set_version = ?)",
            (cutoff, rule_set_version)).fetchone()[0]

        def _agg(junction):
            return conn.execute(
                f"SELECT m.ticker, COUNT(*) n, ROUND(SUM(s.high_value_score), 2) sm, "
                f"ROUND(AVG(s.high_value_score), 2) av FROM {junction} m "
                f"JOIN sa_comment_signals s ON s.comment_row_id = m.comment_row_id "
                f"JOIN sa_article_comments c ON c.id = s.comment_row_id WHERE {where} "
                f"GROUP BY m.ticker ORDER BY sm DESC, n DESC, m.ticker ASC LIMIT ?",
                wp + (limit,)).fetchall()

        def _samples(junction, syms):
            out = {s: [] for s in syms}
            if not syms:
                return out
            ph = ",".join("?" * len(syms))
            for r in conn.execute(
                f"SELECT m.ticker, c.id comment_row_id, c.comment_id, s.article_id, "
                f"c.comment_date, s.high_value_score, substr(c.comment_text, 1, 200) preview, "
                f"a.url FROM {junction} m "
                f"JOIN sa_comment_signals s ON s.comment_row_id = m.comment_row_id "
                f"JOIN sa_article_comments c ON c.id = s.comment_row_id "
                f"LEFT JOIN sa_articles a ON a.article_id = s.article_id "
                f"WHERE m.ticker IN ({ph}) AND {where} "
                f"ORDER BY m.ticker, s.high_value_score DESC, c.comment_date DESC, c.id DESC",
                tuple(syms) + wp,
            ):
                lst = out[r["ticker"]]
                if len(lst) < sample_per:
                    lst.append({
                        "comment_row_id": r["comment_row_id"],
                        "comment_id": r["comment_id"],
                        "article_id": r["article_id"],
                        "url": r["url"],
                        "comment_date": r["comment_date"],
                        "high_value_score": float(r["high_value_score"]),
                        "preview": r["preview"],
                    })
            return out

        def _rows(agg, junction):
            samples = _samples(junction, [r["ticker"] for r in agg])
            return [{
                "ticker": r["ticker"],
                "mention_count": r["n"],
                "sum_score": float(r["sm"]),
                "avg_score": float(r["av"]),
                "samples": samples.get(r["ticker"], []),
            } for r in agg]

        top_tickers = _rows(_agg("sa_signal_ticker_mentions"), "sa_signal_ticker_mentions")
        candidate_watch = _rows(_agg("sa_signal_candidate_mentions"), "sa_signal_candidate_mentions")

        # keyword buckets: parse JSON of the window's high-value signals (capped),
        # associating each bucket with the tickers mentioned in the same comments.
        kb_rows = conn.execute(
            f"SELECT s.comment_row_id, s.keyword_buckets FROM sa_comment_signals s "
            f"JOIN sa_article_comments c ON c.id = s.comment_row_id WHERE {where} "
            f"ORDER BY s.high_value_score DESC, s.comment_row_id DESC LIMIT ?",
            wp + (kw_cap,)).fetchall()
        kb_ids = [r["comment_row_id"] for r in kb_rows]
        ment: Dict[int, List[str]] = {}
        ment_cand: Dict[int, List[str]] = {}
        if kb_ids:
            ph = ",".join("?" * len(kb_ids))
            for tbl, acc in (("sa_signal_ticker_mentions", ment),
                             ("sa_signal_candidate_mentions", ment_cand)):
                for jr in conn.execute(
                    f"SELECT comment_row_id, ticker FROM {tbl} "
                    f"WHERE comment_row_id IN ({ph})", tuple(kb_ids)):
                    acc.setdefault(jr["comment_row_id"], []).append(jr["ticker"])
        buckets: Dict[str, Dict[str, Any]] = {}
        broad_comment_count = 0
        for r in kb_rows:
            rid = r["comment_row_id"]
            try:
                kb = json.loads(r["keyword_buckets"] or "{}")
            except ValueError:
                kb = {}
            tks = ment.get(rid, [])
            cands = ment_cand.get(rid, [])
            if len(tks) + len(cands) >= _FOCUS_BROAD_COMMENT_TICKERS:
                broad_comment_count += 1  # radar-style multi-ticker comment
            for name in kb:
                b = buckets.setdefault(name, {"count": 0, "tickers": set(), "cand": set()})
                b["count"] += 1
                b["tickers"].update(tks)
                b["cand"].update(cands)  # off-universe discussion is complete in the bucket view
        top_keyword_buckets = sorted(
            ({"bucket": k, "comment_count": v["count"],
              "tickers": sorted(v["tickers"]),
              "candidate_tickers": sorted(v["cand"])}
             for k, v in buckets.items()),
            key=lambda x: (-x["comment_count"], x["bucket"]))[:limit]

        empty_reason = None
        if comment_count == 0:
            if pending_in_window > 0:
                empty_reason = "extraction_backlog_pending"
            elif comments_in_window > 0:
                empty_reason = "no_comment_above_min_score"
            else:
                empty_reason = "no_comments_in_window"

        return {
            "comment_count": comment_count,
            "top_tickers": top_tickers,
            "candidate_watch": candidate_watch,
            "top_keyword_buckets": top_keyword_buckets,
            "data_quality": {
                "comments_in_window": comments_in_window,
                "scored_at_min_score": comment_count,
                "pending_extraction_in_window": pending_in_window,
                # how many scanned high-value comments name >= 8 tickers (radar-style
                # round-ups that inflate many rankings at once) — lets the agent tell
                # a broad-based focus from a few multi-ticker posts.
                "broad_comment_count": broad_comment_count,
                "keyword_scan_capped_at": kw_cap if len(kb_rows) >= kw_cap else None,
            },
            "empty_reason": empty_reason,
        }
    finally:
        conn.close()
