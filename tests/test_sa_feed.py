"""Layer C-1: get_sa_feed — unified SA articles + market-news evidence feed.

Verifies the dedicated UNION query: both types newest-first, item_type/ticker
filters, FTS5 vs LIKE-fallback search routing, the per-column-type days cutoff
(date-only articles not dropped by a timestamp cutoff), accurate total +
by_type/by_day facets, the item shape (has_detail/comments_count/detail_route),
no-PG in SA-local mode, and the degraded shapes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src import sa_capture_store as store
from src.tools import sa_tools


@pytest.fixture(autouse=True)
def _sa_enabled(monkeypatch):
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)


def _d(days_ago):
    return store.canon_date(datetime.now(timezone.utc) - timedelta(days=days_ago))


def _ts(days_ago):
    return store.canon_ts(datetime.now(timezone.utc) - timedelta(days=days_ago))


def _seed(db_path):
    conn = store.connect(str(db_path))
    try:
        conn.executemany(
            "INSERT INTO sa_articles (id, article_id, url, title, ticker, "
            "published_date, body_markdown, comments_count) VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "A1", "https://sa/a1", "NVDA datacenter momentum", "NVDA",
                 _d(2), "Long body about datacenter momentum and demand.", 5),
                (2, "A2", "https://sa/a2", "AAPL services flywheel", "AAPL",
                 _d(3), None, 0),  # no body → has_detail=False
            ],
        )
        conn.executemany(
            "INSERT INTO sa_market_news (id, news_id, url, title, published_at, "
            "summary, body_markdown, comments_count) VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "N1", "https://sa/n1", "Fed decision market reaction",
                 _ts(1), "Markets react to the Fed decision.", "Detail body.", 12),
                (2, "N2", "https://sa/n2", "NVDA chip demand surges",
                 _ts(4), "NVDA demand commentary.", None, 3),
            ],
        )
        conn.executemany(
            "INSERT INTO sa_market_news_tickers (news_row_id, ticker) VALUES (?,?)",
            [(1, "SPY"), (1, "QQQ"), (2, "NVDA")],
        )
        conn.commit()
    finally:
        conn.close()


def _dal(db_path):
    dal = MagicMock()
    backend = MagicMock()
    backend._sa_db = str(db_path)
    backend._get_conn.side_effect = AssertionError("SA feed must not touch PG in SA-local mode")
    dal._backend = backend
    return dal, backend


def _feed(db_path, **kw):
    dal, backend = _dal(db_path)
    res = sa_tools.get_sa_feed(dal, **kw)
    backend._get_conn.assert_not_called()
    return res


def test_feed_both_types_newest_first(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    res = _feed(db, days=30)
    assert res["available"] is True
    assert res["total"] == 4
    assert res["by_type"] == {"article": 2, "market_news": 2}
    # newest-first: N1 (-1d) > A1 (-2d) > A2 (-3d) > N2 (-4d)
    assert [i["id"] for i in res["items"]] == ["N1", "A1", "A2", "N2"]
    assert len(res["by_day"]) == 4


def test_feed_item_shape_and_detail_route(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    items = {i["id"]: i for i in _feed(db, days=30)["items"]}
    a1 = items["A1"]
    assert a1["type"] == "article" and a1["source"] == "seeking_alpha"
    assert a1["tickers"] == ["NVDA"] and a1["comments_count"] == 5
    assert a1["has_detail"] is True and a1["detail_route"] == "/sa/articles/A1"
    assert items["A2"]["has_detail"] is False and items["A2"]["detail_route"] is None
    n1 = items["N1"]
    assert n1["type"] == "market_news" and n1["tickers"] == ["QQQ", "SPY"]  # junction, sorted
    assert n1["comments_count"] == 12 and n1["detail_route"] is None  # no market-news detail endpoint


def test_feed_item_type_filter(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    arts = _feed(db, days=30, item_type="article")
    assert arts["total"] == 2 and {i["type"] for i in arts["items"]} == {"article"}
    news = _feed(db, days=30, item_type="market_news")
    assert news["total"] == 2 and {i["type"] for i in news["items"]} == {"market_news"}


def test_feed_ticker_filter_column_and_junction(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    res = _feed(db, days=30, ticker="nvda")  # case-insensitive
    ids = {i["id"] for i in res["items"]}
    assert ids == {"A1", "N2"}  # A1 via article.ticker column, N2 via junction
    assert res["total"] == 2


def test_feed_fts_search(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    res = _feed(db, days=30, q="datacenter")  # len>=3, simple → FTS5
    assert [i["id"] for i in res["items"]] == ["A1"]
    res2 = _feed(db, days=30, q="Fed")
    assert [i["id"] for i in res2["items"]] == ["N1"]


def test_feed_like_fallback_short_and_symbol(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    # len < 3 → LIKE (FTS tokenizes short tokens poorly)
    short = _feed(db, days=30, q="NV")
    assert {i["id"] for i in short["items"]} == {"A1", "N2"}  # both NVDA-titled
    # symbol present → LIKE
    sym = _feed(db, days=30, q="NVDA chip")  # 'NVDA chip' is simple→FTS; use a symbol case:
    # a dotted/symbol query routes to LIKE and must not raise
    res = _feed(db, days=30, q="da.ta")
    assert res["available"] is True  # no FTS-syntax crash


def test_feed_days_window_keeps_date_only_article_on_cutoff_day(tmp_path):
    """Reminder #1: an article dated exactly the cutoff DAY (date-only) must NOT be
    dropped by a timestamp cutoff — articles compare against canon_date, not canon_ts."""
    db = tmp_path / "sa.db"
    conn = store.connect(str(db))
    try:
        days = 7
        cutoff_day = store.canon_date(datetime.now(timezone.utc) - timedelta(days=days))
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title, ticker, published_date) "
            "VALUES (1, 'ACUT', 'https://sa/acut', 'Edge of window', 'MU', ?)", (cutoff_day,))
        conn.commit()
    finally:
        conn.close()
    res = _feed(db, days=days)
    assert any(i["id"] == "ACUT" for i in res["items"]), "date-only cutoff-day article was dropped"


def test_feed_pagination_accurate_total(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    page1 = _feed(db, days=30, limit=2, offset=0)
    page2 = _feed(db, days=30, limit=2, offset=2)
    assert page1["total"] == 4 and page2["total"] == 4  # total is over the full filtered set
    assert len(page1["items"]) == 2 and len(page2["items"]) == 2
    assert [i["id"] for i in page1["items"]] == ["N1", "A1"]
    assert [i["id"] for i in page2["items"]] == ["A2", "N2"]


def test_feed_empty_window(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    res = _feed(db, days=30, ticker="ZZZZ")
    assert res["total"] == 0 and res["items"] == []
    assert res["empty_reason"] == "no_items_in_window"


def test_feed_pg_mode_requires_local(tmp_path):
    dal = MagicMock()
    dal._backend = MagicMock(spec=["_get_conn"])  # no _sa_db
    res = sa_tools.get_sa_feed(dal, days=30)
    assert res["available"] is False and res["empty_reason"] == "requires_local_sa"
    assert "use_local_sa" not in res["error"]


def test_feed_clamps_params(tmp_path):
    db = tmp_path / "sa.db"; _seed(db)
    res = _feed(db, days=99999, limit=99999, offset=-5)
    assert res["days"] == 3650
    assert len(res["items"]) <= 200


def test_route_handler_happy_and_disabled(tmp_path, monkeypatch):
    """Spec §5: handler-level route smoke (NOT TestClient — see feedback_route_unit_tests)."""
    from fastapi import HTTPException

    from src.api.routes.seeking_alpha import sa_feed

    db = tmp_path / "sa.db"; _seed(db)
    dal, _ = _dal(db)
    res = sa_feed(q=None, ticker=None, item_type=None, days=30, limit=50, offset=0, dal=dal)
    assert res["available"] is True and res["total"] == 4 and len(res["items"]) == 4

    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: False)  # feature-disabled → 503
    with pytest.raises(HTTPException) as ei:
        sa_feed(q=None, ticker=None, item_type=None, days=30, limit=50, offset=0, dal=dal)
    assert ei.value.status_code == 503


def test_feed_snippet_is_clean_plain_text(tmp_path):
    """Display-text contract: /sa/feed `snippet` is cleaned plain text (no raw
    markdown / no SA byline-disclosure); the raw body_markdown is left untouched
    in the DB (FTS / detail / agent evidence still see the original)."""
    db = tmp_path / "sa.db"
    conn = store.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title, ticker, published_date, "
            "body_markdown, comments_count) VALUES (?,?,?,?,?,?,?,?)",
            (1, "A1", "https://sa/a1", "NVDA momentum", "NVDA", _d(1),
             "# NVDA momentum\n\n*Author: Seeking Alpha*\n\nAnalyst's Disclosure: none.\n\n"
             "NVIDIA posted **record** revenue on [AI demand](https://x/y).", 5))
        # body is only the title heading + byline → nothing new to show → snippet dropped
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title, ticker, published_date, "
            "body_markdown, comments_count) VALUES (?,?,?,?,?,?,?,?)",
            (2, "A2", "https://sa/a2", "Weekly recap", "MU", _d(2),
             "# Weekly recap\n\n*Author: Seeking Alpha*", 0))
        conn.execute(
            "INSERT INTO sa_market_news (id, news_id, url, title, published_at, summary, "
            "body_markdown, comments_count) VALUES (?,?,?,?,?,?,?,?)",
            (1, "N1", "https://sa/n1", "Apple news", _ts(1), "",
             "# Apple news\n\n![credit](u) Apple raised prices.", 2))
        conn.commit()
    finally:
        conn.close()
    items = {i["id"]: i for i in _feed(db, days=30)["items"]}
    # A1: leading `# {title}` heading dropped (no title dup), byline + disclosure gone,
    # emphasis/link flattened — snippet is the real lede, not a repeat of the title
    assert items["A1"]["snippet"] == "NVIDIA posted record revenue on AI demand."
    assert not items["A1"]["snippet"].startswith("NVDA momentum")  # title not duplicated
    assert "*" not in items["A1"]["snippet"] and "#" not in items["A1"]["snippet"]
    # A2: body is only the title heading + byline → nothing new → dropped to ""
    assert items["A2"]["snippet"] == ""
    # N1: market-news markdown cleaned + leading title heading dropped
    assert items["N1"]["snippet"] == "credit Apple raised prices."
    assert not items["N1"]["snippet"].startswith("Apple news")
    # raw body_markdown preserved in the DB (not mutated by the display cleanup)
    rconn = store.connect(str(db), read_only=True)
    try:
        raw = rconn.execute(
            "SELECT body_markdown FROM sa_articles WHERE article_id='A1'").fetchone()[0]
    finally:
        rconn.close()
    assert raw.startswith("# NVDA momentum") and "*Author:" in raw


def test_like_escapes_sql_wildcards(tmp_path):
    """A literal % in q must match literally, not as a SQL LIKE wildcard."""
    db = tmp_path / "sa.db"
    conn = store.connect(str(db))
    try:
        conn.executemany(
            "INSERT INTO sa_articles (id, article_id, url, title, published_date) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "P1", "https://x/p1", "Margins up 50% this quarter", _d(1)),
                (2, "P2", "https://x/p2", "Revenue hit 5000 units", _d(1)),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    res = _feed(db, days=30, q="50%")  # '%' → LIKE path; escaped → literal '50%'
    assert {i["id"] for i in res["items"]} == {"P1"}  # '5000' must NOT wildcard-match
