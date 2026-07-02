import sqlite3
from datetime import date

from src.news_normalized.schema import ensure_news_normalized_schema
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend
from src.tools.data_access import DataAccessLayer
from src.tools.news_tools import (
    get_news_brief,
    get_news_sentiment_summary,
    search_news_advanced,
)
from src.tools.signal_tools import detect_anomalies


def _create_scored_market_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
        "description TEXT, url TEXT, publisher TEXT, source TEXT NOT NULL, published_at TEXT NOT NULL, "
        "article_hash TEXT);"
        "CREATE VIRTUAL TABLE news_fts USING fts5(title, description, content='news', "
        "content_rowid='id', tokenize='porter unicode61');"
    )
    ensure_news_normalized_schema(conn)
    pub = f"{date.today().isoformat()}T00:00:00+0000"
    conn.executemany(
        "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, "AAPL", "Apple scored historical", "earnings", "u1", "p", "ibkr", pub, "h1"),
            (2, "AAPL", "Apple projection risk", "supply", "u2", "p", "ibkr", pub, "h2"),
            (3, "AAPL", "Apple unscored", "services", "u3", "p", "ibkr", pub, "h3"),
        ],
    )
    conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
    conn.executemany(
        "INSERT INTO news_articles "
        "(id,source,canonical_title,published_at,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        [
            (101, "ibkr", "Apple scored historical", pub, "now", "now"),
            (102, "ibkr", "Apple projection risk", pub, "now", "now"),
            (103, "ibkr", "Apple unscored", pub, "now", "now"),
        ],
    )
    conn.execute(
        "INSERT INTO news_normalization_runs "
        "(id,policy_version,input_fingerprint,resolved_fingerprint,"
        "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, "test", "input", "resolved", "reject", "{}", "backup.db", "now"),
    )
    conn.execute(
        "INSERT INTO news_legacy_migration_map "
        "(legacy_news_id,article_id,resolution_kind,migration_run_id,migration_fingerprint) "
        "VALUES (?,?,?,?,?)",
        (1, 101, "mapped", 1, "resolved"),
    )
    conn.execute(
        "INSERT INTO news_legacy_projection_map "
        "(article_id,ticker,legacy_news_id,projected_at) VALUES (?,?,?,?)",
        (102, "AAPL", 2, "now"),
    )
    conn.executemany(
        "INSERT INTO news_article_scores "
        "(article_id,score_type,model,reasoning_effort,score,scored_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            (101, "sentiment", "gpt_5_2", "high", 4.0, "2026-07-01T00:00:00Z", "now", "now"),
            (101, "risk", "gpt_5_2", "high", 2.0, "2026-07-01T00:00:00Z", "now", "now"),
            (102, "risk", "o4_mini", "", 1.5, "2026-07-01T00:00:00Z", "now", "now"),
        ],
    )
    conn.commit()
    conn.close()
    return path


def _dal_with_pg_poison(monkeypatch, db):
    def boom(self, *args, **kwargs):
        raise AssertionError("PG score path should not be called")

    monkeypatch.setattr(DatabaseBackend, "query_news", boom)
    monkeypatch.setattr(DatabaseBackend, "query_news_search", boom)
    monkeypatch.setattr(DatabaseBackend, "query_news_stats", boom)
    backend = LocalMarketDatabaseBackend(
        "postgresql://fake/db",
        market_db=str(db),
        strict=True,
        news_strict=True,
    )
    return DataAccessLayer(backend=backend)


def test_news_sentiment_summary_uses_local_scores_with_pg_poisoned(tmp_path, monkeypatch):
    dal = _dal_with_pg_poison(monkeypatch, _create_scored_market_db(tmp_path / "m.db"))

    summary = get_news_sentiment_summary(dal, ticker="AAPL", days=30)

    assert summary["article_count"] == 2
    assert summary["scored_count"] == 1
    assert summary["sentiment_mean"] == 4.0
    assert summary["risk_mean"] == 1.75


def test_search_news_advanced_filters_local_sentiment_and_risk(tmp_path, monkeypatch):
    dal = _dal_with_pg_poison(monkeypatch, _create_scored_market_db(tmp_path / "m.db"))

    result = search_news_advanced(
        dal,
        query="Apple",
        tickers=None,
        days=30,
        scored_only=True,
        min_sentiment=4,
        max_risk=2,
    )

    assert result.count == 1
    assert result.articles[0].title == "Apple scored historical"


def test_news_brief_uses_local_score_stats_with_pg_poisoned(tmp_path, monkeypatch):
    dal = _dal_with_pg_poison(monkeypatch, _create_scored_market_db(tmp_path / "m.db"))

    brief = get_news_brief(dal, tickers=["AAPL"], days=30)

    assert brief["ticker_count"] == 1
    assert brief["briefs"][0]["scored_count"] == 2
    assert brief["briefs"][0]["avg_sentiment"] == 4.0
    assert brief["briefs"][0]["avg_risk"] == 1.75


def test_detect_anomalies_sees_local_scored_news(tmp_path, monkeypatch):
    dal = _dal_with_pg_poison(monkeypatch, _create_scored_market_db(tmp_path / "m.db"))

    result = detect_anomalies(dal, ticker="AAPL", days=30)

    assert result["ticker"] == "AAPL"
    assert "No scored news articles available" not in result.get("error", "")
    assert "sentiment_anomaly" in result
