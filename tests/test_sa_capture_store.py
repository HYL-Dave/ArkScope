"""Tests for the sa_capture.db schema + connection discipline (slice 3d prep-1)."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

import pytest

import src.sa_capture_store as scs


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "sa_capture.db")
    conn = scs.connect(path)
    yield conn, path
    conn.close()


# --- canonical encoding ---------------------------------------------------------

def test_canon_ts_one_format_lexicographic():
    # JS Z-string, PG '+00', naive, aware non-UTC — ALL land in the one format,
    # and lexicographic order == time order (mark-stale depends on this).
    a = scs.canon_ts("2026-06-13T01:00:00Z")
    b = scs.canon_ts("2026-06-13 03:00:00+00")
    c = scs.canon_ts(datetime(2026, 6, 13, 2, 0, 0))                       # naive → UTC
    d = scs.canon_ts(datetime(2026, 6, 13, 12, 0, 0,
                              tzinfo=timezone.utc).astimezone())           # aware local
    for v in (a, b, c, d):
        assert v is not None and v.endswith("+00:00") and len(v) == 25
    assert a < c < b                                  # 01:00 < 02:00 < 03:00
    assert scs.canon_ts(None) is None
    assert scs.canon_ts("garbage") is None


def test_canon_date():
    from datetime import date
    assert scs.canon_date(date(2026, 6, 13)) == "2026-06-13"
    assert scs.canon_date("2026-06-13") == "2026-06-13"
    assert scs.canon_date(datetime(2026, 6, 13, 5, 0)) == "2026-06-13"
    assert scs.canon_date(None) is None


# --- schema basics ----------------------------------------------------------------

def test_schema_tables_and_version(db):
    conn, _ = db
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ("sa_alpha_picks", "sa_refresh_meta", "sa_articles", "sa_article_comments",
              "sa_market_news", "sa_market_news_tickers", "sa_comment_signals",
              "sa_signal_ticker_mentions", "sa_signal_candidate_mentions",
              "schema_migrations"):
        assert t in tables, t
    assert conn.execute("PRAGMA user_version").fetchone()[0] == scs.SCHEMA_VERSION
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_reopen_fast_path_no_ddl(db, tmp_path):
    # second connect must take the user_version fast path (cheap per-message open)
    _, path = db
    c2 = scs.connect(path)
    assert c2.execute("PRAGMA user_version").fetchone()[0] == scs.SCHEMA_VERSION
    c2.close()


def test_concurrent_schema_creation_two_processes(tmp_path):
    # two REAL processes race first-run DDL — BEGIN IMMEDIATE must serialize them
    path = str(tmp_path / "race.db")
    code = (
        "import sys; sys.path.insert(0, '.');"
        "import src.sa_capture_store as s;"
        f"c = s.connect({path!r}); c.close(); print('ok')"
    )
    procs = [subprocess.Popen([sys.executable, "-c", code],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=str(scs._PROJECT_ROOT)) for _ in range(2)]
    outs = [p.communicate(timeout=60) for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    conn = scs.connect(path)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


# --- identity model (partial unique indexes, ports sql/014+015 final state) ------

def _pick(conn, symbol, status, picked="2026-01-01", closed=None, pick_id=None):
    conn.execute(
        "INSERT INTO sa_alpha_picks (id, symbol, company, picked_date, closed_date, "
        "portfolio_status) VALUES (?, ?, ?, ?, ?, ?)",
        (pick_id, symbol, symbol + " Inc", picked, closed, status))


def test_current_identity_rejects_duplicates(db):
    conn, _ = db
    _pick(conn, "AAPL", "current")
    with pytest.raises(sqlite3.IntegrityError):
        _pick(conn, "AAPL", "current")                 # same (symbol,picked,status)


def test_closed_identity_allows_distinct_close_events(db):
    conn, _ = db
    _pick(conn, "TSLA", "closed", closed="2026-02-01")
    _pick(conn, "TSLA", "closed", closed="2026-03-01")  # distinct close event: OK
    with pytest.raises(sqlite3.IntegrityError):
        _pick(conn, "TSLA", "closed", closed="2026-02-01")  # same event: rejected
    conn.rollback()
    # NULL closed_date stays NULL-distinct (same semantics as PG — documented hole)
    _pick(conn, "NVDA", "closed", closed=None)
    _pick(conn, "NVDA", "closed", closed=None)
    assert conn.execute("SELECT COUNT(*) FROM sa_alpha_picks "
                        "WHERE symbol='NVDA'").fetchone()[0] == 2


def test_dual_membership_current_and_closed(db):
    conn, _ = db
    _pick(conn, "AMD", "current")
    _pick(conn, "AMD", "closed", closed="2026-05-01")  # same pick in both tabs: OK
    assert conn.execute("SELECT COUNT(*) FROM sa_alpha_picks "
                        "WHERE symbol='AMD'").fetchone()[0] == 2


# --- FK cascade (load-bearing for comment dedupe) ---------------------------------

def _seed_comment_with_signal(conn):
    conn.execute("INSERT INTO sa_articles (id, article_id, url, title) "
                 "VALUES (1, 'a1', 'http://x', 'T')")
    conn.execute("INSERT INTO sa_article_comments (id, article_id, comment_id, comment_text) "
                 "VALUES (10, 'a1', 'c1', 'hello')")
    conn.execute("INSERT INTO sa_comment_signals (comment_row_id, article_id, comment_id, "
                 "rule_set_version, extracted_at) VALUES (10, 'a1', 'c1', 'v1', ?)",
                 (scs.now_ts(),))
    conn.execute("INSERT INTO sa_signal_ticker_mentions VALUES (10, 'AAPL')")
    conn.commit()


def test_cascade_purges_signals_and_mentions(db):
    conn, _ = db
    _seed_comment_with_signal(conn)
    conn.execute("DELETE FROM sa_article_comments WHERE id = 10")  # dedupe-style delete
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sa_signal_ticker_mentions").fetchone()[0] == 0
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_fk_enforced_on_unknown_article(db):
    conn, _ = db
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sa_article_comments (article_id, comment_id, comment_text) "
                     "VALUES ('nope', 'c9', 'x')")


# --- FTS5 mirrors maintained by triggers ------------------------------------------

def test_articles_fts_insert_update(db):
    conn, _ = db
    conn.execute("INSERT INTO sa_articles (id, article_id, url, title, body_markdown) "
                 "VALUES (1, 'a1', 'http://x', 'Nvidia surges', 'datacenter growth')")
    conn.commit()
    hit = conn.execute("SELECT rowid FROM sa_articles_fts WHERE sa_articles_fts "
                       "MATCH 'nvidia'").fetchall()
    assert [r[0] for r in hit] == [1]
    conn.execute("UPDATE sa_articles SET body_markdown = 'apple slumps' WHERE id = 1")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM sa_articles_fts WHERE sa_articles_fts "
                        "MATCH 'datacenter'").fetchone()[0] == 0  # old text gone
    assert conn.execute("SELECT COUNT(*) FROM sa_articles_fts WHERE sa_articles_fts "
                        "MATCH 'apple'").fetchone()[0] == 1


def test_market_news_fts_and_ticker_junction(db):
    conn, _ = db
    conn.execute("INSERT INTO sa_market_news (id, news_id, url, title, summary) "
                 "VALUES (5, 'n1', 'http://y', 'Fed holds rates', 'FOMC statement')")
    conn.execute("INSERT INTO sa_market_news_tickers VALUES (5, 'SPY'), (5, 'QQQ')")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM sa_market_news_fts WHERE sa_market_news_fts "
                        "MATCH 'fomc'").fetchone()[0] == 1
    # the '= ANY(tickers)' replacement: join through the junction
    rows = conn.execute(
        "SELECT n.news_id FROM sa_market_news n "
        "JOIN sa_market_news_tickers t ON t.news_row_id = n.id WHERE t.ticker = 'SPY'"
    ).fetchall()
    assert [r[0] for r in rows] == ["n1"]
    conn.execute("DELETE FROM sa_market_news WHERE id = 5")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM sa_market_news_tickers").fetchone()[0] == 0
