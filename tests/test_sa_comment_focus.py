"""Layer B of follow-up #1: get_sa_comment_focus — deterministic cross-ticker
SA comment-attention aggregation over sa_capture.db.

Verifies accurate GROUP BY counts, deterministic ranking, traceable samples
(comment/article ids + url), keyword-bucket aggregation, candidate_watch, the
empty_reason taxonomy (backlog vs min_score vs no-comments), PG-mode degrade,
and param clamping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src import sa_capture_store as store
from src.sa import comment_signal_backfill as bf
from src.tools import sa_tools


@pytest.fixture(autouse=True)
def _sa_enabled(monkeypatch):
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)


def _ts(days_ago):
    return store.canon_ts(datetime.now(timezone.utc) - timedelta(days=days_ago))


def _seed(db_path, *, days_ago=2):
    """1 article (with url) + comments dated `days_ago` mentioning NVDA/AMD/XYZ."""
    conn = store.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title) "
            "VALUES (1, 'A1', 'https://seekingalpha.com/x/A1', 'T1')"
        )
        cd = _ts(days_ago)
        conn.executemany(
            "INSERT INTO sa_article_comments "
            "(id, article_id, comment_id, comment_text, upvotes, comment_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "A1", "c1", "NVDA earnings beat consensus estimate, strong guidance", 25, cd),
                (2, "A1", "c2", "NVDA margin expansion is real", 6, cd),
                (3, "A1", "c3", "AMD downgrade, hold rating from analyst", 4, cd),
                (4, "A1", "c4", "Watching XYZ for a swing trade", 1, cd),
                (5, "A1", "c5", "AMD earnings next week, could be a catalyst", 3, cd),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _dal(db_path, tickers=("NVDA", "AMD")):
    dal = MagicMock()
    backend = MagicMock()
    backend._sa_db = str(db_path)
    backend._get_conn.side_effect = AssertionError("focus must not touch PG in SA-local mode")
    dal._backend = backend
    wl = MagicMock()
    wl.tickers = list(tickers)
    dal.get_watchlist.return_value = wl
    return dal, backend


def _focus(db_path, **kw):
    dal, backend = _dal(db_path)
    bf.run_backfill(dal)  # populate signals first
    backend._get_conn.reset_mock()  # only assert PG-untouched for the focus call
    res = sa_tools.get_sa_comment_focus(dal, **kw)
    backend._get_conn.assert_not_called()
    return res


def test_focus_ranks_tickers_with_traceable_samples(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    res = _focus(db, window_days=14, min_score=0.0, limit=10)

    assert res["signal_type"].startswith("deterministic_rule_based")
    assert res["rule_set_version"] == bf.RULE_SET_VERSION
    assert res["generated_at"]
    assert res["empty_reason"] is None
    assert res["comment_count"] >= 4

    syms = [t["ticker"] for t in res["top_tickers"]]
    assert "NVDA" in syms and "AMD" in syms
    nvda = next(t for t in res["top_tickers"] if t["ticker"] == "NVDA")
    assert nvda["mention_count"] == 2          # c1 + c2
    assert nvda["sum_score"] > 0 and nvda["avg_score"] > 0
    s = nvda["samples"][0]
    for k in ("comment_row_id", "comment_id", "article_id", "url", "comment_date",
              "high_value_score", "preview"):
        assert k in s
    assert s["url"] == "https://seekingalpha.com/x/A1"  # traceable via the article join


def test_focus_deterministic_ranking(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    r1 = _focus(db, window_days=14, min_score=0.0)
    # sum_score desc, then mention_count desc, then ticker asc
    rows = r1["top_tickers"]
    keys = [(-t["sum_score"], -t["mention_count"], t["ticker"]) for t in rows]
    assert keys == sorted(keys)


def test_focus_candidate_watch_has_samples(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    res = _focus(db, window_days=14, min_score=0.0)
    cands = {c["ticker"] for c in res["candidate_watch"]}
    assert "XYZ" in cands  # off-universe token → candidate
    xyz = next(c for c in res["candidate_watch"] if c["ticker"] == "XYZ")
    assert xyz["samples"] and xyz["samples"][0]["comment_id"] == "c4"


def test_focus_keyword_buckets_aggregated(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    res = _focus(db, window_days=14, min_score=0.0)
    buckets = {b["bucket"]: b for b in res["top_keyword_buckets"]}
    assert "earnings" in buckets
    # earnings comments mention NVDA (c1) and AMD (c5) → tickers aggregated
    assert "NVDA" in buckets["earnings"]["tickers"] or "AMD" in buckets["earnings"]["tickers"]
    assert buckets["earnings"]["comment_count"] >= 1


def test_focus_empty_reason_backlog_pending(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)  # recent comments but NO backfill run → signals absent
    dal, _ = _dal(db)
    res = sa_tools.get_sa_comment_focus(dal, window_days=14, min_score=0.0)
    assert res["comment_count"] == 0
    assert res["top_tickers"] == []
    assert res["empty_reason"] == "extraction_backlog_pending"
    assert res["data_quality"]["pending_extraction_in_window"] >= 5


def test_focus_empty_reason_min_score_too_high(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    res = _focus(db, window_days=14, min_score=999.0)
    assert res["comment_count"] == 0
    assert res["empty_reason"] == "no_comment_above_min_score"


def test_focus_empty_reason_no_comments_in_window(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db, days_ago=40)  # comments older than the window
    res = _focus(db, window_days=1, min_score=0.0)
    assert res["comment_count"] == 0
    assert res["empty_reason"] == "no_comments_in_window"


def test_focus_pg_mode_requires_local(tmp_path):
    dal = MagicMock()
    backend = MagicMock(spec=["_get_conn"])  # PG-mode: no _sa_db attribute
    dal._backend = backend
    res = sa_tools.get_sa_comment_focus(dal, window_days=14)
    assert res["empty_reason"] == "requires_local_sa"
    assert "error" in res and res["top_tickers"] == []


def test_focus_clamps_params(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    res = _focus(db, window_days=9999, min_score=-5.0, limit=9999)
    assert res["window_days"] == 90
    assert res["min_score"] == 0.0
    assert len(res["top_tickers"]) <= 50


def test_focus_multi_ticker_counted_once_each_and_sample_cap(tmp_path):
    """A comment mentioning two universe tickers +1's BOTH (count-once-per-ticker);
    a ticker with >2 mentions still yields at most sample_per(=2) samples."""
    db = tmp_path / "sa.db"
    conn = store.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title) "
            "VALUES (1, 'A1', 'https://x/A1', 'T1')")
        cd = _ts(2)
        conn.executemany(
            "INSERT INTO sa_article_comments "
            "(id, article_id, comment_id, comment_text, upvotes, comment_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "A1", "c1", "NVDA earnings beat, strong guidance", 30, cd),
                (2, "A1", "c2", "NVDA margin expansion is real", 10, cd),
                (3, "A1", "c3", "NVDA downgrade rating risk", 5, cd),
                (4, "A1", "c4", "NVDA and AMD both look strong into earnings", 8, cd),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    res = _focus(db, window_days=14, min_score=0.0, limit=10)
    tk = {t["ticker"]: t for t in res["top_tickers"]}
    assert tk["NVDA"]["mention_count"] == 4   # c1, c2, c3, c4
    assert tk["AMD"]["mention_count"] == 1    # only c4 (the multi-ticker comment)
    assert len(tk["NVDA"]["samples"]) == 2    # sample_per cap holds with 4 mentions
