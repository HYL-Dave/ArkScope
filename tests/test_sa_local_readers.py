"""Current local SA reader and backfill contracts.

Covers:
  (a) each reader returns the reviewed dict shape from sa_capture.db;
  (b) health split: capture metrics from SQLite while the job_runs lookup
      uses the local job-runs store; missing extension-run history falls back
      to capture-side ``last_fetched_at``;
  (c) comment_signal_backfill writes through the sa_capture.db store.

Hermetic: tmp_path sa_capture.db seeded via sa_capture_store.connect();
no external service is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest

import src.sa_capture_store as scs
from src.sa.comment_signals import RULE_SET_VERSION
from src.tools.backends.sa_capture_backend import SACaptureBackend


# ---------------------------------------------------------------------------
# Seed: one sa_capture.db covering all five consumers
# ---------------------------------------------------------------------------


def _seed(db_path: str) -> datetime:
    """Seed relative to the real clock (the readers compute their own NOW)."""
    now = datetime.now(timezone.utc)

    def ts(**kw):
        return scs.canon_ts(now - timedelta(**kw))

    def d(days):
        return (now - timedelta(days=days)).date().isoformat()

    conn = scs.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO sa_articles (id, article_id, url, title, ticker, author, "
            "published_date, article_type, body_markdown, comments_count, "
            "fetched_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "a1", "https://sa/a1", "NVDA: datacenter momentum", "NVDA",
                 "AuthorOne", d(2), "analysis", "Body for a1. " * 10, 5,
                 ts(days=2), ts(days=2)),
                (2, "a2", "https://sa/a2", "NVDA: follow-up", "NVDA",
                 "AuthorTwo", d(3), "analysis", None, 1, ts(days=3), ts(days=3)),
                (3, "a3", "https://sa/a3", "AAPL: services flywheel", "AAPL",
                 "AuthorThree", d(1), "analysis", "Body for a3", 0,
                 ts(days=1), ts(days=1)),
            ],
        )
        comments = [
            (1, "a1", "cm1", "userA", "NVDA earnings beat. " * 30, 10, ts(days=1)),
            (2, "a1", "cm2", "userB", "NVDA margin expansion", 2, ts(days=1, hours=1)),
            (3, "a1", "cm3", "userC", "NVDA guidance strong", 1, ts(days=2)),
            (4, "a1", "cm4", "userD", "NVDA valuation rich", 0, ts(days=2, hours=1)),
            (5, "a2", "cm5", "userE", "NVDA supply risk view", 3, ts(days=1, hours=2)),
            (6, "a2", "cm6", "userF", "Possible NVDA lawsuit?", 0, ts(days=1, hours=3)),
            (7, "a1", "cm7", "userG", "Old NVDA take", 50, ts(days=80)),
            (8, "a1", "cm8", "userH", "Stale-version NVDA take", 5, ts(days=1, hours=4)),
        ]
        conn.executemany(
            "INSERT INTO sa_article_comments (id, article_id, comment_id, "
            "commenter, comment_text, upvotes, comment_date, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(*c, scs.now_ts()) for c in comments],
        )

        def sig(rid, score, ver=RULE_SET_VERSION, nv=0, kb="{}"):
            row = comments[rid - 1]
            return (rid, row[1], row[2], kb, score, nv, ver, scs.now_ts())

        conn.executemany(
            "INSERT INTO sa_comment_signals (comment_row_id, article_id, "
            "comment_id, keyword_buckets, high_value_score, needs_verification, "
            "rule_set_version, extracted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                sig(1, 8.0, kb='{"earnings": ["beat"]}'),
                sig(2, 7.0),
                sig(3, 6.5),
                sig(4, 5.0),          # 4th ticker-kind comment on a1 → digest cap
                sig(5, 5.5),
                sig(6, 6.0, nv=1, kb='{"risk": ["lawsuit"]}'),  # candidate-only
                sig(7, 9.5),          # outside 7d window (80d old)
                sig(8, 9.0, ver="vOLD"),  # wrong rule_set_version → always excluded
            ],
        )
        conn.executemany(
            "INSERT INTO sa_signal_ticker_mentions (comment_row_id, ticker) "
            "VALUES (?, ?)",
            [(1, "NVDA"), (2, "NVDA"), (3, "NVDA"), (4, "NVDA"), (5, "NVDA"),
             (7, "NVDA"), (8, "NVDA")],
        )
        conn.executemany(
            "INSERT INTO sa_signal_candidate_mentions (comment_row_id, ticker) "
            "VALUES (?, ?)",
            [(1, "NVDA"), (6, "NVDA")],  # row 1 in BOTH → kind 'ticker' wins
        )
        conn.executemany(
            "INSERT INTO sa_market_news (id, news_id, url, title, published_at, "
            "published_text, category, summary, comments_count, body_markdown, "
            "detail_fetched_at, fetched_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "n1", "https://sa/n1", "NVDA pops on earnings", ts(hours=1),
                 "Today", "Tech", "NVDA beats estimates. " * 5, 25, "Body n1",
                 ts(hours=1), ts(hours=1), ts(hours=1)),
                (2, "n2", "https://sa/n2", "NVDA minor note", ts(hours=2),
                 "Today", "Tech", "Small note", 3, None, None,
                 ts(hours=1), ts(hours=1)),
                (3, "n3", "https://sa/n3", "AAPL roundup", ts(hours=30),
                 "Yesterday", "Tech", "AAPL news", 50, "Body n3",
                 ts(hours=30), ts(hours=30), ts(hours=30)),
            ],
        )
        conn.executemany(
            "INSERT INTO sa_market_news_tickers (news_row_id, ticker) VALUES (?, ?)",
            [(1, "NVDA"), (1, "SPY"), (2, "NVDA"), (3, "AAPL")],
        )
        pick_rows = [
            # PLTR: no canonical/detail AND no PLTR article → unresolved
            (1, "PLTR", "Palantir", d(30), 0, None, None,
             ts(hours=1), ts(hours=1), ts(hours=1)),
            # NVDA: no canonical/detail BUT article a1 matches → resolved
            (2, "NVDA", "NVIDIA", d(40), 0, None, None,
             ts(hours=1), ts(hours=1), ts(hours=1)),
            # MSFT: has detail_report → not a candidate
            (3, "MSFT", "Microsoft", d(50), 0, None, "existing detail",
             ts(hours=1), ts(hours=1), ts(hours=1)),
            # TSLA: stale → excluded
            (4, "TSLA", "Tesla", d(60), 1, None, None,
             ts(hours=1), ts(hours=1), ts(hours=1)),
        ]
        expanded_pick_rows = []
        for row in pick_rows:
            _, symbol, _, picked_date, *_ = row
            conn.execute(
                "INSERT OR IGNORE INTO sa_pick_lineages"
                " (symbol_key, picked_date, created_at) VALUES (?, ?, ?)",
                (symbol.strip().upper(), picked_date, scs.now_ts()),
            )
            lineage_id = conn.execute(
                "SELECT lineage_id FROM sa_pick_lineages"
                " WHERE symbol_key=? AND picked_date=?",
                (symbol.strip().upper(), picked_date),
            ).fetchone()[0]
            expanded_pick_rows.append((row[0], lineage_id, *row[1:]))
        conn.executemany(
            "INSERT INTO sa_alpha_picks (id, lineage_id, symbol, company, picked_date, "
            "portfolio_status, is_stale, canonical_article_id, detail_report, "
            "last_seen_snapshot, fetched_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'current', ?, ?, ?, ?, ?, ?)",
            expanded_pick_rows,
        )
        conn.commit()
    finally:
        conn.close()
    return now


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sa_db(tmp_path):
    path = str(tmp_path / "sa_capture.db")
    _seed(path)
    return path


@pytest.fixture()
def local_backend(sa_db, tmp_path):
    return SACaptureBackend(
        sa_db=sa_db,
        market_db=str(tmp_path / "market_data.db"),
        base_path=tmp_path,
    )


@pytest.fixture()
def local_dal(local_backend):
    return SimpleNamespace(_backend=local_backend)


@pytest.fixture()
def invalid_dal():
    return SimpleNamespace(_backend=object())


@pytest.fixture()
def sa_enabled(monkeypatch):
    monkeypatch.setattr("src.tools.sa_tools._is_sa_enabled", lambda: True)
    monkeypatch.setattr("src.tools.sa_digest_tools._is_sa_enabled", lambda: True)


def test_absent_sa_db_refresh_meta_is_honest_empty(tmp_path):
    path = tmp_path / "missing.db"
    backend = SACaptureBackend(
        sa_db=str(path), market_db=str(tmp_path / "market_data.db"), base_path=tmp_path
    )

    assert backend.get_sa_refresh_meta() == {}
    assert not path.exists()


def test_absent_sa_db_market_news_query_is_honest_empty(tmp_path):
    path = tmp_path / "missing.db"
    backend = SACaptureBackend(
        sa_db=str(path), market_db=str(tmp_path / "market_data.db"), base_path=tmp_path
    )

    assert backend.query_sa_market_news(limit=5) == []
    assert not path.exists()




def test_absent_sa_db_health_query_degrades_honestly(tmp_path):
    from src.service.sa_market_news_health import _query_capture_stats_local

    path = tmp_path / "missing.db"
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)

    out = _query_capture_stats_local(str(path), now=now)

    assert out["rows_24h_fetched"] == 0
    assert out["items_24h_published"] == 0
    assert out["items_7d"] == 0
    assert out["detail_present_7d"] == 0
    assert out["last_fetched_at"] is None
    assert out["last_published_at"] is None
    assert not path.exists()


# ---------------------------------------------------------------------------
# 1. list_high_value_comments (sa_tools)
# ---------------------------------------------------------------------------


HVC_KEYS = {
    "comment_row_id", "article_id", "comment_id", "commenter", "upvotes",
    "comment_date", "preview", "high_value_score", "ticker_mentions",
    "candidate_mentions", "keyword_buckets", "needs_verification",
    "rule_set_version",
}


class TestHighValueCommentsLocal:
    def test_shape_lists_and_ordering(self, local_dal, sa_enabled):
        from src.tools.sa_tools import list_high_value_comments

        out = list_high_value_comments(local_dal, window_days=7, min_score=2.0,
                                       limit=50)
        assert "error" not in out
        assert out["count"] == 6  # rows 1-6; row 7 out of window, row 8 old version
        assert out["rule_set_version"] == RULE_SET_VERSION
        scores = [c["high_value_score"] for c in out["comments"]]
        assert scores == sorted(scores, reverse=True) == [8.0, 7.0, 6.5, 6.0, 5.5, 5.0]
        first = out["comments"][0]
        assert set(first.keys()) == HVC_KEYS
        assert isinstance(first["ticker_mentions"], list)
        assert isinstance(first["candidate_mentions"], list)
        assert first["ticker_mentions"] == ["NVDA"]
        assert first["candidate_mentions"] == ["NVDA"]  # row 1 is in both junctions
        # Stored JSON is decoded before returning the public shape.
        assert first["keyword_buckets"] == {"earnings": ["beat"]}
        assert isinstance(first["needs_verification"], bool)
        assert isinstance(first["comment_date"], str)
        assert len(first["preview"]) <= 300

    def test_ticker_filter_via_junction(self, local_dal, sa_enabled):
        from src.tools.sa_tools import list_high_value_comments

        out = list_high_value_comments(local_dal, window_days=7, ticker="nvda",
                                       min_score=2.0, limit=50)
        # candidate-only row 6 must be excluded by the ticker_mentions filter
        ids = [c["comment_row_id"] for c in out["comments"]]
        assert ids == [1, 2, 3, 5, 4]  # 8.0, 7.0, 6.5, 5.5, 5.0
        assert out["ticker_filter"] == "NVDA"

        none = list_high_value_comments(local_dal, window_days=7, ticker="ZZZZ",
                                        min_score=2.0, limit=50)
        assert none["count"] == 0 and none["comments"] == []

    def test_window_and_rule_version_semantics(self, local_dal, sa_enabled):
        from src.tools.sa_tools import list_high_value_comments

        wide = list_high_value_comments(local_dal, window_days=90, min_score=2.0,
                                        limit=50)
        ids = [c["comment_row_id"] for c in wide["comments"]]
        assert ids[0] == 7          # 80d-old 9.5 enters at window=90
        assert 8 not in ids         # stale rule_set_version always excluded



# ---------------------------------------------------------------------------
# 2-4. get_sa_digest (sa_digest_tools — articles / news / comments)
# ---------------------------------------------------------------------------


ARTICLE_KEYS = {"article_id", "title", "author", "published_date", "url",
                "article_type", "comments_count", "summary_excerpt"}
NEWS_KEYS = {"news_id", "title", "url", "published_at", "tickers", "category",
             "comments_count", "summary_excerpt"}
COMMENT_KEYS = {"comment_id", "article_id", "article_url", "commenter",
                "comment_date", "upvotes", "preview", "high_value_score",
                "keyword_buckets", "needs_verification"}


class TestDigestLocal:
    def test_articles_shape_order_and_missing_note(self, local_dal,
                                                   sa_enabled):
        from src.tools.sa_digest_tools import get_sa_digest

        out = get_sa_digest(local_dal, "NVDA", days=14)
        arts = out["recent_articles"]
        assert [a["article_id"] for a in arts] == ["a1", "a2"]  # published DESC
        assert set(arts[0].keys()) == ARTICLE_KEYS
        assert isinstance(arts[0]["comments_count"], int)
        assert isinstance(arts[0]["published_date"], str)
        # a2 has no body → data_quality.missing notes 1 of 2
        assert any("body_markdown unavailable for 1 of 2" in m
                   for m in out["data_quality"]["missing"])

    def test_news_junction_tickers_and_gate(self, local_dal, sa_enabled):
        from src.tools.sa_digest_tools import get_sa_digest

        out = get_sa_digest(local_dal, "NVDA", days=14)
        news = out["high_discussion_news"]
        assert [n["news_id"] for n in news] == ["n1"]  # n2 below gate, n3 ≠ NVDA
        assert set(news[0].keys()) == NEWS_KEYS
        assert news[0]["tickers"] == ["NVDA", "SPY"]  # rebuilt list, insert order
        assert isinstance(news[0]["tickers"], list)

    def test_comments_kind_split_and_per_article_cap(self, local_dal,
                                                     sa_enabled):
        from src.tools.sa_digest_tools import get_sa_digest

        out = get_sa_digest(local_dal, "NVDA", days=14, min_comment_score=2.0)
        hv = out["high_value_comments"]
        ticker_ids = [c["comment_id"] for c in hv["ticker_mentions"]]
        # a1 has 4 ticker-kind comments → per-article cap 3 keeps cm1/cm2/cm3,
        # drops cm4 (5.0); a2 contributes cm5. Ordered by score DESC.
        assert ticker_ids == ["cm1", "cm2", "cm3", "cm5"]
        assert [c["comment_id"] for c in hv["candidate_mentions"]] == ["cm6"]
        row = hv["ticker_mentions"][0]
        assert set(row.keys()) == COMMENT_KEYS
        assert row["keyword_buckets"] == {"earnings": ["beat"]}
        assert row["article_url"] == "https://sa/a1"
        cand = hv["candidate_mentions"][0]
        assert cand["needs_verification"] is True  # kept, not filtered
        assert out["data_quality"]["errors"] == []

    def test_pack_is_json_serializable(self, local_dal, sa_enabled):
        from src.tools.sa_digest_tools import get_sa_digest

        out = get_sa_digest(local_dal, "NVDA", days=14)
        json.dumps(out)
        assert out["data_quality"]["rows"] == {
            "articles": 2, "news": 1, "comments_ticker": 4, "comments_candidate": 1,
        }


# ---------------------------------------------------------------------------
# Health split (sa_market_news_health)
# ---------------------------------------------------------------------------


class TestHealthSplit:
    def test_local_capture_metrics_without_extension_run_uses_capture_signal(self, local_dal):
        from src.service.sa_market_news_health import compute_market_news_health

        report = compute_market_news_health(local_dal)
        assert report["severity"] == "ok"
        assert report["ok"] is True
        codes = [r["code"] for r in report["reasons"]]
        assert "pipeline_signal_unavailable" not in codes
        # Capture-side metrics still computed from sa_capture.db:
        assert report["freshness"]["pipeline_signal"] == "last_fetched_at"
        assert report["freshness"]["extension_last_success_at"] is None
        assert report["freshness"]["last_fetch_age_seconds"] < 2 * 3600
        assert report["feed_health"]["rows_24h_fetched"] == 2     # n1 + n2
        assert report["feed_health"]["items_24h_published"] == 2  # n1 + n2
        assert report["feed_health"]["items_7d"] == 3
        assert report["detail_health"]["rows_with_detail_7d"] == 2  # n1 + n3


    def test_local_job_runs_failure_degrades_pipeline_signal(self, local_dal, monkeypatch):
        from src.service import sa_market_news_health as health

        monkeypatch.setattr(
            health,
            "_query_extension_run",
            lambda dal: (_ for _ in ()).throw(RuntimeError("local job_runs down")),
        )

        report = health.compute_market_news_health(local_dal)

        assert report["severity"] == "warning"
        assert report["ok"] is False
        codes = [r["code"] for r in report["reasons"]]
        assert "pipeline_signal_unavailable" in codes
        assert report["freshness"]["pipeline_signal"] == "last_fetched_at"

    def test_local_backend_uses_extension_signal(self, invalid_dal):
        from src.service.sa_market_news_health import compute_market_news_health

        report = compute_market_news_health(invalid_dal)
        assert report["severity"] == "critical"
        assert any(r["code"] == "db_unavailable" for r in report["reasons"])
        assert "SA capture local backend unavailable" in report["reasons"][0]["message"]


# ---------------------------------------------------------------------------
# comment_signal_backfill guard (locked L3)
# ---------------------------------------------------------------------------


class TestBackfillRouting:
    def test_routes_to_sqlite(self, local_dal, sa_db):
        from src import sa_capture_store as scs
        from src.sa.comment_signal_backfill import run_backfill

        # a fresh rule_set_version makes every seeded comment pending → forces writes
        res = run_backfill(local_dal, rule_set_version="test-port")
        assert "error" not in res
        assert res["rule_set_version"] == "test-port"
        assert res["extracted_count"] >= 1

        conn = scs.connect(sa_db, read_only=True)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM sa_comment_signals WHERE rule_set_version = 'test-port'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == res["extracted_count"]
