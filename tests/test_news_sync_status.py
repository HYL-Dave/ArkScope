from __future__ import annotations

import sqlite3

from src.market_data_direct import _ensure_provider_sync_tables


def _db(path):
    conn = sqlite3.connect(path)
    _ensure_provider_sync_tables(conn)
    return conn


def test_absent_db_is_read_only_and_has_no_direct_status(tmp_path):
    from src.news_sync_status import read_news_sync_status

    path = tmp_path / "absent.db"
    assert read_news_sync_status(path) is None
    assert not path.exists()


def test_combines_latest_provider_runs_with_current_ticker_errors(tmp_path):
    from src.news_sync_status import read_news_sync_status

    path = tmp_path / "market.db"
    conn = _db(path)
    conn.executemany(
        "INSERT INTO provider_sync_runs "
        "(provider,domain,interval,started_at,finished_at,tickers_scanned,gaps_found,rows_added,status,error) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("polygon", "news", "news", "2026-06-27T01:00:00+00:00", "2026-06-27T01:01:00+00:00", 2, 0, 5, "succeeded", None),
            ("polygon", "news", "news", "2026-06-27T02:00:00+00:00", "2026-06-27T02:01:00+00:00", 2, 0, 0, "succeeded", None),
            ("finnhub", "news", "news", "2026-06-27T03:00:00+00:00", "2026-06-27T03:01:00+00:00", 1, 0, 0, "failed", "provider unavailable"),
            ("ibkr", "prices", "15min", "2026-06-27T04:00:00+00:00", "2026-06-27T04:01:00+00:00", 1, 1, 26, "succeeded", None),
        ],
    )
    conn.executemany(
        "INSERT INTO provider_sync_meta "
        "(provider,ticker,interval,last_success,last_bar_datetime,last_error,rows_added,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            ("polygon", "BAD", "news", None, None, "HTTP 403", 0, "2026-06-27T02:01:00+00:00"),
            ("polygon", "AAPL", "news", "2026-06-27T02:01:00+00:00", "2026-06-27T00:00:00+00:00", None, 0, "2026-06-27T02:01:00+00:00"),
            ("finnhub", "MSFT", "prices", None, None, "wrong domain", 0, "2026-06-27T03:01:00+00:00"),
        ],
    )
    conn.commit()
    conn.close()

    out = read_news_sync_status(path)

    assert out is not None
    assert out["status"] == "failed"
    assert out["last_success"] == "2026-06-27T02:01:00+00:00"
    assert out["last_attempt"] == "2026-06-27T03:01:00+00:00"
    assert out["updated_at"] == out["last_attempt"]
    assert out["rows_added"] == 0
    assert set(out["providers"]) == {"polygon", "finnhub"}

    polygon = out["providers"]["polygon"]
    assert polygon["status"] == "partial"
    assert polygon["last_error"] == "BAD: HTTP 403"
    assert polygon["ticker_errors"] == [{"ticker": "BAD", "error": "HTTP 403", "updated_at": "2026-06-27T02:01:00+00:00"}]

    finnhub = out["providers"]["finnhub"]
    assert finnhub["status"] == "failed"
    assert finnhub["last_error"] == "provider unavailable"
    assert finnhub["ticker_errors"] == []
    assert "wrong domain" not in out["last_error"]


def test_successful_run_with_ticker_failure_is_partial_not_clean(tmp_path):
    from src.news_sync_status import read_news_sync_status

    path = tmp_path / "market.db"
    conn = _db(path)
    conn.execute(
        "INSERT INTO provider_sync_runs "
        "(provider,domain,interval,started_at,finished_at,tickers_scanned,gaps_found,rows_added,status,error) "
        "VALUES ('polygon','news','news','2026-06-27T01:00:00+00:00','2026-06-27T01:01:00+00:00',2,0,1,'succeeded',NULL)"
    )
    conn.execute(
        "INSERT INTO provider_sync_meta "
        "(provider,ticker,interval,last_success,last_bar_datetime,last_error,rows_added,updated_at) "
        "VALUES ('polygon','LC','news',NULL,NULL,'contract unresolved',0,'2026-06-27T01:01:00+00:00')"
    )
    conn.commit()
    conn.close()

    out = read_news_sync_status(path)

    assert out is not None
    assert out["status"] == "partial"
    assert out["providers"]["polygon"]["status"] == "partial"
    assert "LC: contract unresolved" in out["last_error"]

