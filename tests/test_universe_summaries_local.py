"""get_universe_summaries must read the LOCAL market DB — the PG path died with
N9 batch-1 (PG `news` dropped) and its single try aborted price summaries too."""
import sqlite3
from datetime import datetime, timedelta, timezone

from src.tools.analysis_tools import get_universe_summaries


def _ts(hours_ago: float = 0.0, days_ago: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago, days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def _seed(tmp_path, *, with_news_table: bool = True):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE prices (ticker TEXT NOT NULL, datetime TEXT NOT NULL,
        interval TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume INTEGER,
        PRIMARY KEY (ticker, datetime, interval))""")
    rows = [
        ("AAPL", _ts(hours_ago=2), "15min", 9.0, 11.5, 8.5, 10.0, 50),
        ("AAPL", _ts(hours_ago=1), "15min", 10.0, 11.5, 9.5, 11.0, 100),
        ("AAPL", _ts(days_ago=30), "15min", 1.0, 1.0, 1.0, 1.0, 999),  # outside window
        ("HAPN", _ts(hours_ago=3), "15min", 20.0, 21.0, 19.0, 20.5, 10),
    ]
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", rows)
    if with_news_table:
        conn.execute("CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT, published_at TEXT)")
        conn.executemany(
            "INSERT INTO news (ticker, published_at) VALUES (?,?)",
            [("AAPL", _ts(hours_ago=5)), ("AAPL", _ts(days_ago=2)),
             ("AAPL", _ts(days_ago=30)),                    # outside window
             ("msft", _ts(hours_ago=1))],                   # news-only ticker, lowercase
        )
    conn.commit()
    conn.close()
    return db


def test_summaries_read_local_db_never_pg(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(_seed(tmp_path)))
    out = get_universe_summaries(None, days=7)  # dal unused — must not touch any backend

    aapl = out["AAPL"]
    assert aapl["latest_close"] == 11.0        # newest in-window close
    assert aapl["change_pct"] == 22.22         # (11 - 9) / 9, oldest in-window open
    assert aapl["total_volume"] == 150 and aapl["bars"] == 2
    assert aapl["news_count_7d"] == 2          # 30d-old article excluded
    assert out["HAPN"]["news_count_7d"] == 0
    assert out["MSFT"]["latest_close"] is None and out["MSFT"]["news_count_7d"] == 1


def test_missing_db_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "nope.db"))
    assert get_universe_summaries(None) == {}


def test_news_failure_keeps_price_summaries(tmp_path, monkeypatch):
    # Independent degradation — the old PG path returned {} for EVERYTHING when
    # the news query failed (the exact live incident after the N9 drop).
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(_seed(tmp_path, with_news_table=False)))
    out = get_universe_summaries(None, days=7)
    assert out["AAPL"]["latest_close"] == 11.0
    assert out["AAPL"]["news_count_7d"] == 0
