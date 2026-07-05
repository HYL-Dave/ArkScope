import json
import sqlite3
from pathlib import Path

import pytest


def _make_market_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            provider_article_id TEXT,
            canonical_title TEXT NOT NULL,
            publisher TEXT,
            url TEXT,
            published_at TEXT NOT NULL,
            content_kind TEXT NOT NULL DEFAULT 'headline_only',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE news_article_tickers (
            article_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            relation_kind TEXT NOT NULL DEFAULT 'related',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY (article_id, ticker)
        );
        CREATE TABLE provider_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            domain TEXT NOT NULL,
            interval TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            tickers_scanned INTEGER DEFAULT 0,
            gaps_found INTEGER DEFAULT 0,
            rows_added INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            error TEXT
        );
        """
    )
    rows = [
        ("AAPL", "2026-07-04T01:00:00Z"),
        ("AAPL", "2026-07-03T01:00:00Z"),
        ("AAPL", "2026-06-26T01:00:00Z"),
        ("AAPL", "2026-06-20T01:00:00Z"),
        ("AAPL", "2026-06-10T01:00:00Z"),
        ("AAPL", "2026-05-20T01:00:00Z"),
        ("MSFT", "2026-07-01T01:00:00Z"),
        ("MSFT", "2026-06-15T01:00:00Z"),
        ("IBM", "2026-05-01T01:00:00Z"),
    ]
    for idx, (ticker, published_at) in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO news_articles "
            "(id,source,provider_article_id,canonical_title,published_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (idx, "ibkr", f"DJ-N${idx}", f"Story {idx}", published_at, published_at, published_at),
        )
        conn.execute(
            "INSERT INTO news_article_tickers "
            "(article_id,ticker,relation_kind,first_seen_at,last_seen_at) VALUES (?,?,?,?,?)",
            (idx, ticker, "related", published_at, published_at),
        )
    conn.execute(
        "INSERT INTO provider_sync_runs "
        "(provider,domain,interval,started_at,finished_at,tickers_scanned,rows_added,status,error) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "ibkr",
            "news",
            "news",
            "2026-07-05T16:10:00+00:00",
            "2026-07-05T16:19:00+00:00",
            2,
            0,
            "succeeded",
            None,
        ),
    )
    conn.commit()
    conn.close()


def _make_profile_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE scheduler_state (
            source TEXT PRIMARY KEY,
            last_attempt TEXT,
            last_status TEXT,
            last_error TEXT,
            continuation TEXT,
            last_result TEXT,
            updated_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO scheduler_state "
        "(source,last_attempt,last_status,last_error,continuation,last_result,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "ibkr_news",
            "2026-07-05T16:10:00+0000",
            "succeeded",
            None,
            None,
            json.dumps(
                {
                    "ticker_count": 2,
                    "collect": {
                        "articles_seen": 3,
                        "articles_inserted": 0,
                    },
                }
            ),
            "2026-07-05T16:19:00+0000",
        ),
    )
    conn.commit()
    conn.close()


def test_build_report_shape_and_caveats(tmp_path):
    from src.audit.ibkr_news_catchup_audit import build_report

    market_db = tmp_path / "market.db"
    profile_db = tmp_path / "profile.db"
    _make_market_db(market_db)
    _make_profile_db(profile_db)

    report = build_report(market_db, profile_db, as_of="2026-07-05")

    assert report["ok"] is True
    assert report["source"] == "ibkr"
    assert report["windows"]["7d"]["max_rows"] == 2
    assert report["windows"]["30d"]["max_rows"] == 5
    assert report["windows"]["30d"]["tickers_ge_300"] == 0
    assert report["top_tickers"][0]["ticker"] == "AAPL"
    assert report["scheduler_state"]["last_status"] == "succeeded"
    assert report["provider_runs"][0]["status"] == "succeeded"
    assert report["risk"]["current_cadence"] == "ok"
    assert report["risk"]["long_quiet_window"] == "ok"
    assert any("lower bound" in item for item in report["caveats"])
    assert any("stable" in item for item in report["caveats"])


def test_report_includes_observed_quiet_window_gap_check(tmp_path):
    from src.audit.ibkr_news_catchup_audit import build_report

    market_db = tmp_path / "market.db"
    profile_db = tmp_path / "profile.db"
    _make_market_db(market_db)
    _make_profile_db(profile_db)

    report = build_report(market_db, profile_db, as_of="2026-07-05")

    gap = report["gap_checks"][0]
    assert gap["label"] == "observed_quiet_window_2026_06_25_to_2026_07_05"
    assert gap["start_date"] == "2026-06-25"
    assert gap["end_date"] == "2026-07-05"
    assert gap["max_rows"] == 3
    assert gap["tickers_ge_300"] == 0
    assert gap["assessment"] == "below_cap"


def test_missing_db_does_not_create_file(tmp_path):
    from src.audit.ibkr_news_catchup_audit import build_report

    market_db = tmp_path / "missing-market.db"
    profile_db = tmp_path / "missing-profile.db"

    with pytest.raises(sqlite3.OperationalError):
        build_report(market_db, profile_db, as_of="2026-07-05")

    assert not market_db.exists()
    assert not profile_db.exists()


def test_audit_source_has_no_gateway_access_or_write_sql():
    source = Path("src/audit/ibkr_news_catchup_audit.py").read_text()

    for forbidden in (
        "IBKRDataSource",
        "IBKRRuntimeGateway",
        "ib_insync",
        "reqHistoricalNews",
    ):
        assert forbidden not in source
    for forbidden_sql in (
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "CREATE ",
        "DROP ",
        "REPLACE ",
    ):
        assert forbidden_sql not in source.upper()


def test_report_records_writer_budget_is_not_bottleneck(tmp_path):
    from src.audit.ibkr_news_catchup_audit import build_report

    market_db = tmp_path / "market.db"
    profile_db = tmp_path / "profile.db"
    _make_market_db(market_db)
    _make_profile_db(profile_db)

    report = build_report(market_db, profile_db, as_of="2026-07-05")

    assert "50000" in report["writer_budget_note"]
    assert "provider-side 300/ticker" in report["writer_budget_note"]
