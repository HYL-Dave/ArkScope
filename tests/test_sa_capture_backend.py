"""Tests for SACaptureDatabaseBackend (slice 3d prep-2).

Hermetic: tmp_path SQLite DBs only. The fixture POISONS DatabaseBackend._get_conn
for every test, so ANY sa_* code path that touches PostgreSQL fails loudly with
AssertionError('PG touched') — the hard-cutover (no-PG-fallback, locked L1)
guarantee is therefore enforced suite-wide, not just in the dedicated test.
"""

from __future__ import annotations

import sqlite3

import pytest

import src.sa_capture_store as scs
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend
from src.tools.backends.sa_capture_backend import SACaptureDatabaseBackend

FAKE_DSN = "postgresql://fake:fake@127.0.0.1:9/fake"

T1 = "2026-06-13T01:00:00Z"            # JS-style Z suffix
T2 = "2026-06-13 02:00:00+00"          # PG-style short offset (canon_ts must unify)
T1_CANON = "2026-06-13T01:00:00+00:00"
T2_CANON = "2026-06-13T02:00:00+00:00"


def _poison_get_conn(self):
    raise AssertionError("PG touched")


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    # No sa_* call may ever reach PG — not even on empty local results (L1).
    monkeypatch.setattr(DatabaseBackend, "_get_conn", _poison_get_conn)
    return SACaptureDatabaseBackend(FAKE_DSN, sa_db=str(tmp_path / "sa_capture.db"))


def _pick(symbol="AAPL", picked="2026-01-02", **kw):
    p = {
        "symbol": symbol,
        "company": f"{symbol} Inc",
        "picked_date": picked,
        "closed_date": None,
        "return_pct": 12.5,
        "sector": "Tech",
        "sa_rating": "STRONG BUY",
        "holding_pct": 3.1,
        "raw_data": {"src": "test"},
    }
    p.update(kw)
    return p


def _news(news_id="n1", **kw):
    item = {
        "news_id": news_id,
        "url": f"https://sa/{news_id}",
        "title": "Fed holds rates steady",
        "published_at": "2026-06-10T12:00:00Z",
        "published_text": "Today, 8:00 AM",
        "tickers": ["SPY", "QQQ"],
        "category": "Macro",
        "summary": "FOMC keeps target range",
        "comments_count": 5,
        "raw_data": {"id": news_id},
    }
    item.update(kw)
    return item


def _article(article_id="a1", **kw):
    a = {
        "article_id": article_id,
        "url": f"https://sa/{article_id}",
        "title": "NVDA: Strong Buy on datacenter momentum",
        "ticker": "NVDA",
        "published_date": "2026-06-01",
        "article_type": "analysis",
        "comments_count": 2,
        "raw_data": {"k": 1},
    }
    a.update(kw)
    return a


def _comments():
    return [
        {"comment_id": "c1", "parent_comment_id": None, "commenter": "alice",
         "comment_text": "Great analysis", "upvotes": 3,
         "comment_date": "2026-06-02T10:00:00Z"},
        {"comment_id": "c2", "parent_comment_id": "c1", "commenter": "bob",
         "comment_text": "Agreed on margins", "upvotes": 1,
         "comment_date": "2026-06-02T11:00:00Z"},
    ]


# --- (1) isinstance gate + lazy PG -------------------------------------------------


def test_isinstance_gate_and_lazy_construction(backend):
    # The ~10 DAL gates require a real DatabaseBackend; construction with a fake
    # DSN + poisoned _get_conn proves PG is only ever contacted lazily (never for
    # sa_* on this class).
    assert isinstance(backend, DatabaseBackend)
    assert isinstance(backend, LocalMarketDatabaseBackend)


# --- (2) apply_sa_refresh end-to-end + canon_ts mark-stale ordering ----------------


def test_apply_sa_refresh_marks_stale_and_updates_meta(backend):
    assert backend.apply_sa_refresh("current", [_pick("AAPL"), _pick("MSFT")], T1, T1) == 2
    assert {p["symbol"] for p in backend.query_sa_picks("current")} == {"AAPL", "MSFT"}

    # Second refresh with MSFT missing — mixed input formats (Z vs '+00') prove the
    # mark-stale TEXT compare runs on canon_ts-canonical values.
    assert backend.apply_sa_refresh("current", [_pick("AAPL")], T2, T2) == 1
    live = backend.query_sa_picks("current")
    assert [p["symbol"] for p in live] == ["AAPL"]
    assert live[0]["is_stale"] is False
    assert live[0]["last_seen_snapshot"] == T2_CANON

    everyone = {p["symbol"]: p for p in backend.query_sa_picks("current", include_stale=True)}
    assert everyone["MSFT"]["is_stale"] is True          # missing pick went stale
    assert everyone["MSFT"]["last_seen_snapshot"] == T1_CANON

    meta = backend.get_sa_refresh_meta()["current"]
    assert meta["ok"] is True
    assert meta["row_count"] == 1
    assert meta["snapshot_ts"] == T2_CANON
    assert meta["last_success_at"] == T2_CANON
    assert meta["last_error"] is None


def test_mark_stale_not_triggered_by_equal_snapshot(backend):
    # Strict '<' compare: re-running the SAME snapshot must not stale anything.
    backend.apply_sa_refresh("current", [_pick("AAPL")], T1, T1)
    backend.apply_sa_refresh("current", [_pick("AAPL")], T1, T1)
    assert backend.query_sa_picks("current")[0]["is_stale"] is False


# --- (3) closed scope: distinct close events coexist, same event upserts ----------


def test_closed_scope_distinct_events_and_idempotent_upsert(backend):
    e1 = _pick("TSLA", closed_date="2026-02-01")
    e2 = _pick("TSLA", closed_date="2026-03-01")
    assert backend.apply_sa_refresh("closed", [e1, e2], T1, T1) == 2
    assert len(backend.query_sa_picks("closed")) == 2

    # re-refresh of the same events: upsert via the closed partial index, no dupes
    assert backend.apply_sa_refresh("closed", [e1, e2], T2, T2) == 2
    rows = backend.query_sa_picks("closed")
    assert len(rows) == 2
    assert all(r["last_seen_snapshot"] == T2_CANON for r in rows)


# --- (4) upsert never clobbers detail ----------------------------------------------


def test_refresh_never_clobbers_detail_report(backend):
    backend.apply_sa_refresh("current", [_pick("NVDA")], T1, T1)
    assert backend.update_sa_pick_detail("NVDA", "2026-01-02", "DEEP DIVE") is True

    backend.apply_sa_refresh("current", [_pick("NVDA", return_pct=99.9)], T2, T2)
    d = backend.get_sa_pick_detail("NVDA")
    assert d["detail_report"] == "DEEP DIVE"       # survives the re-refresh
    assert d["detail_fetched_at"] is not None
    assert d["return_pct"] == 99.9                 # refreshed field did update
    assert d["raw_data"] == {"src": "test"}        # jsonb→dict parity (json.loads)
    assert d["is_stale"] is False


# --- (5) failure path: rollback + failure meta in a fresh transaction --------------


def test_failure_rolls_back_and_records_failure_meta(backend):
    backend.apply_sa_refresh("current", [_pick("AAPL")], T1, T1)

    bad = _pick("BAD")
    bad["symbol"] = None  # rejected before stale-marking transaction begins
    with pytest.raises(ValueError, match="symbol and picked_date"):
        backend.apply_sa_refresh("current", [_pick("GOOD2"), bad], T2, T2)

    rows = backend.query_sa_picks("current", include_stale=True)
    assert {r["symbol"] for r in rows} == {"AAPL"}          # GOOD2 rolled back
    assert rows[0]["is_stale"] is False                     # mark-stale rolled back
    assert rows[0]["last_seen_snapshot"] == T1_CANON

    meta = backend.get_sa_refresh_meta()["current"]
    assert meta["ok"] is False
    assert "symbol and picked_date" in meta["last_error"]
    assert meta["last_attempt_at"] == T2_CANON              # failed attempt recorded
    assert meta["last_success_at"] == T1_CANON              # success state preserved
    assert meta["snapshot_ts"] == T1_CANON
    assert meta["row_count"] == 1


# --- (6) get_sa_refresh_meta: TEXT passthrough (the .isoformat() fix) --------------


def test_get_sa_refresh_meta_returns_text_timestamps(backend):
    backend.apply_sa_refresh("current", [_pick("AAPL")], T1, T1)
    meta = backend.get_sa_refresh_meta()
    assert set(meta) == {"current"}
    cur = meta["current"]
    assert set(cur) == {"scope", "last_attempt_at", "last_success_at", "snapshot_ts",
                        "row_count", "ok", "last_error", "updated_at"}
    for k in ("last_attempt_at", "last_success_at", "snapshot_ts", "updated_at"):
        assert isinstance(cur[k], str), k  # TEXT as-is; no AttributeError, no {} fallback


# --- (7) market news: conflict semantics, junction, FTS, need_detail ---------------


def test_market_news_upsert_conflict_semantics(backend, monkeypatch):
    assert backend.upsert_sa_market_news([_news()]) == 1
    assert backend.save_sa_market_news_detail("n1", "body text") is True
    first = backend.query_sa_market_news()[0]
    assert first["tickers"] == ["SPY", "QQQ"]
    fetched_0, detail_0 = first["fetched_at"], first["detail_fetched_at"]

    # freeze "now" so the updated_at bump is observable at seconds resolution
    bumped = "2026-06-11T11:11:11+00:00"
    monkeypatch.setattr(scs, "now_ts", lambda: bumped)
    assert backend.upsert_sa_market_news(
        [_news(title="Fed signals cuts", tickers=["TLT"], comments_count=3, summary=None)]
    ) == 1

    row = backend.query_sa_market_news()[0]
    assert row["title"] == "Fed signals cuts"
    assert row["updated_at"] == bumped                       # conflict bumps updated_at
    assert row["fetched_at"] == fetched_0                    # ... but NOT fetched_at
    assert row["body_markdown"] == "body text"               # preserved on conflict
    assert row["detail_fetched_at"] == detail_0              # preserved on conflict
    assert row["comments_count"] == 5                        # GREATEST → max
    assert row["summary"] == "FOMC keeps target range"       # COALESCE keeps old
    assert row["tickers"] == ["TLT"]                         # junction replaced

    # empty incoming tickers → existing junction set kept (array_length CASE parity)
    backend.upsert_sa_market_news([_news(tickers=[])])
    assert backend.query_sa_market_news()[0]["tickers"] == ["TLT"]


def test_market_news_query_by_ticker_and_fts_keyword(backend):
    backend.upsert_sa_market_news([
        _news("n1", tickers=["SPY"], title="Fed holds rates", summary="FOMC statement",
              published_at="2026-06-10T12:00:00Z"),
        _news("n2", tickers=["NVDA"], title="Nvidia datacenter surge", summary="AI capex",
              published_at="2026-06-11T12:00:00Z"),
    ])
    by_ticker = backend.query_sa_market_news(ticker="nvda")  # upper-cased like PG path
    assert [r["news_id"] for r in by_ticker] == ["n2"]
    assert by_ticker[0]["tickers"] == ["NVDA"]

    by_kw = backend.query_sa_market_news(keyword="FOMC")
    assert [r["news_id"] for r in by_kw] == ["n1"]
    assert backend.query_sa_market_news(keyword="blockchain") == []

    # newest-first default ordering
    assert [r["news_id"] for r in backend.query_sa_market_news()] == ["n2", "n1"]


def test_market_news_need_detail_and_recent_ids_roundtrip(backend):
    backend.upsert_sa_market_news([
        _news("n1", published_at="2026-06-10T12:00:00Z"),
        _news("n2", published_at="2026-06-11T12:00:00Z"),
    ])
    backend.save_sa_market_news_detail("n2", "full body")

    need = backend.query_sa_market_news_need_detail()
    assert [r["news_id"] for r in need] == ["n1"]            # n2 has a fresh body
    assert set(need[0]) == {"news_id", "url"}

    # negative cache window → cutoff in the future → even fresh detail re-qualifies
    assert {r["news_id"] for r in
            backend.query_sa_market_news_need_detail(detail_cache_hours=-1)} == {"n1", "n2"}

    assert backend.query_sa_market_news_need_detail(exclude_news_ids=["n1"]) == []
    assert [r["news_id"] for r in
            backend.query_sa_market_news_need_detail(news_ids=["n1"])] == ["n1"]
    assert backend.query_sa_market_news_need_detail(limit=0) == []

    assert backend.query_sa_market_news_recent_ids() == ["n2", "n1"]


def test_invalidate_dirty_market_news_detail(backend):
    backend.upsert_sa_market_news([_news("n1"), _news("n2"), _news("n3")])
    backend.save_sa_market_news_detail("n1", "Perfectly clean article body.")
    backend.save_sa_market_news_detail("n2", "stuff\n\n### Recommended For You\nlinks")
    backend.save_sa_market_news_detail("n3", "# Title\n\n# Another title")  # regex branch
    assert backend.invalidate_dirty_sa_market_news_detail() == 2
    dirty = {r["news_id"] for r in backend.query_sa_market_news_need_detail()}
    assert dirty == {"n2", "n3"}                              # n1's body survived


# --- (8) articles: meta upsert, FTS query, save+comments, dedupe cascade -----------


def test_articles_meta_upsert_and_query(backend):
    assert backend.upsert_sa_articles_meta([
        _article("a1"),
        _article("a2", title="Quick note", ticker="AAPL",
                 published_date="2026-06-05", article_type="news",
                 comments_count=0, raw_data=None),
    ]) == 2

    # conflict: COALESCE keeps ticker/published_date/type when incoming is None
    backend.upsert_sa_articles_meta([
        _article("a1", title="NVDA thesis updated", url="https://sa/a1b",
                 ticker=None, published_date=None, article_type=None,
                 comments_count=7, raw_data=None),
    ])
    rows = backend.query_sa_articles(ticker="NVDA")
    assert len(rows) == 1
    a1 = rows[0]
    assert a1["title"] == "NVDA thesis updated"
    assert a1["url"] == "https://sa/a1b"
    assert a1["ticker"] == "NVDA"
    assert a1["published_date"] == "2026-06-01"
    assert a1["article_type"] == "analysis"
    assert a1["comments_count"] == 7
    assert a1["has_content"] is False
    assert a1["stored_comments_count"] == 0

    assert [r["article_id"] for r in backend.query_sa_articles(keyword="updated")] == ["a1"]
    assert [r["article_id"] for r in backend.query_sa_articles(article_type="news")] == ["a2"]
    # newest first
    assert [r["article_id"] for r in backend.query_sa_articles()] == ["a2", "a1"]


def test_save_article_with_comments_shape_and_pick_sync(backend):
    # Historical node name retained for collection accounting. The v2 contract
    # deliberately proves capture no longer mutates pick/article links in the
    # same transaction; reconciliation is a separate call.
    backend.apply_sa_refresh("current", [_pick("NVDA", picked="2026-06-01")], T1, T1)
    backend.upsert_sa_articles_meta([_article("a1")])

    res = backend.save_article_with_comments("a1", "## Thesis\nbody", _comments())
    assert res["ok"] is True
    assert res["prepared_comments"] == 2
    assert res["stored_comments_total"] == 2
    assert res["net_new_comments"] == 2
    assert "synced_picks" not in res

    art = backend.get_sa_article_with_comments("a1")
    assert art["body_markdown"] == "## Thesis\nbody"
    assert art["raw_data"] == {"k": 1}                       # jsonb→dict parity
    assert isinstance(art["comments"], list)
    assert [c["comment_id"] for c in art["comments"]] == ["c1", "c2"]
    assert art["comments"][1]["parent_comment_id"] == "c1"

    pick = backend.get_sa_pick_detail("NVDA")
    assert pick["detail_report"] is None
    assert pick["canonical_article_id"] is None

    # comments-only refresh: one new comment, totals move by exactly one
    extra = _comments() + [
        {"comment_id": "c3", "parent_comment_id": None, "commenter": "carol",
         "comment_text": "What about valuation?", "upvotes": 0,
         "comment_date": "2026-06-03T09:00:00Z"},
    ]
    stats = backend.update_article_comments("a1", extra)
    assert stats["stored_comments_total"] == 3
    assert stats["net_new_comments"] == 1

    missing = backend.get_sa_article_with_comments("nope")
    assert missing is None


def test_comment_dedupe_cascade_leaves_no_orphan_signals(backend):
    backend.upsert_sa_articles_meta([_article("a1")])
    # Seed a null-date duplicate, its dated twin, a child pointing at the dupe, and
    # a signal row on the dupe (signal WRITES are the paused job — direct SQL here).
    conn = scs.connect(backend._sa_db)
    now = scs.now_ts()
    conn.execute(
        "INSERT INTO sa_article_comments (id, article_id, comment_id, commenter, "
        "comment_text, upvotes, comment_date, fetched_at) "
        "VALUES (101, 'a1', 'dup', 'alice', 'same text', 0, NULL, ?)", (now,))
    conn.execute(
        "INSERT INTO sa_article_comments (id, article_id, comment_id, commenter, "
        "comment_text, upvotes, comment_date, fetched_at) "
        "VALUES (102, 'a1', 'keep', 'alice', 'same text', 2, '2026-06-02T10:00:00+00:00', ?)",
        (now,))
    conn.execute(
        "INSERT INTO sa_article_comments (id, article_id, comment_id, commenter, "
        "comment_text, upvotes, comment_date, fetched_at) "
        "VALUES (103, 'a1', 'child', 'carol', 'reply', 0, '2026-06-02T12:00:00+00:00', ?)",
        (now,))
    conn.execute("UPDATE sa_article_comments SET parent_comment_id = 'dup' WHERE id = 103")
    conn.execute(
        "INSERT INTO sa_comment_signals (comment_row_id, article_id, comment_id, "
        "keyword_buckets, high_value_score, needs_verification, rule_set_version, "
        "extracted_at) VALUES (101, 'a1', 'dup', '{}', 1.0, 0, 'v1', ?)", (now,))
    conn.execute("INSERT INTO sa_signal_ticker_mentions VALUES (101, 'NVDA')")
    conn.commit()
    conn.close()

    backend.save_article_with_comments("a1", "body", [])

    art = backend.get_sa_article_with_comments("a1")
    by_id = {c["comment_id"]: c for c in art["comments"]}
    assert set(by_id) == {"keep", "child"}                   # 'dup' deleted
    assert by_id["child"]["parent_comment_id"] == "keep"     # re-parented to canonical

    check = scs.connect(backend._sa_db)
    assert check.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 0
    assert check.execute("SELECT COUNT(*) FROM sa_signal_ticker_mentions").fetchone()[0] == 0
    assert check.execute("PRAGMA foreign_key_check").fetchall() == []
    check.close()


def test_cleanup_mixed_null_date_comment_duplicates(backend):
    backend.upsert_sa_articles_meta([_article("a1")])
    conn = scs.connect(backend._sa_db)
    now = scs.now_ts()
    for cid, cdate in (("x1", None), ("x2", "2026-06-02T10:00:00+00:00")):
        conn.execute(
            "INSERT INTO sa_article_comments (article_id, comment_id, commenter, "
            "comment_text, upvotes, comment_date, fetched_at) "
            "VALUES ('a1', ?, 'dave', 'duplicated body', 0, ?, ?)", (cid, cdate, now))
    conn.commit()
    conn.close()

    out = backend.cleanup_mixed_null_date_comment_duplicates()
    assert out == {"groups_processed": 1, "comments_deleted": 1,
                   "parent_links_repointed": 0}
    art = backend.get_sa_article_with_comments("a1")
    assert [c["comment_id"] for c in art["comments"]] == ["x2"]  # dated row kept


def test_sanitize_corrupted_comments_counts(backend):
    backend.upsert_sa_articles_meta([
        _article("a1", ticker="X", published_date="2025-04-01",
                 article_type="news", comments_count=202542, raw_data=None),
        _article("a2", ticker="Y", published_date="2025-04-01",
                 article_type="news", comments_count=250, raw_data=None),
    ])
    assert backend.sanitize_corrupted_sa_comments_counts() == 1
    arts = {a["article_id"]: a for a in backend.query_sa_articles(limit=10)}
    assert arts["a1"]["comments_count"] == 42                # '2025' year prefix stripped
    assert arts["a2"]["comments_count"] == 250               # sane value untouched


def test_audit_unresolved_symbols_exact_and_like_fallback(backend):
    # Historical node name retained for collection accounting. The compatibility
    # audit is now a read-only alias for event-scoped review; it never performs
    # the retired exact/prefix/full-text mutation.
    backend.apply_sa_refresh("current", [
        _pick("NVDA", picked="2026-06-01"),
        _pick("TSM", picked="2026-06-01"),
        _pick("ZZZQ", picked="2026-06-01"),
    ], T1, T1)
    backend.upsert_sa_articles_meta([
        _article("a1"),                                       # ticker NVDA, analysis
        _article("a2", title="Why TSM wins the foundry war", ticker=None,
                 published_date="2026-06-03"),
    ])
    backend.save_article_with_comments("a1", "NVDA body", [])
    backend.save_article_with_comments("a2", "TSM thesis body", [])

    conn = scs.connect(backend._sa_db)
    before = [tuple(row) for row in conn.execute(
        "SELECT id, canonical_article_id, detail_report FROM sa_alpha_picks ORDER BY id"
    )]
    conn.close()

    out = backend.audit_unresolved_symbols()
    assert out["unresolved_symbols"] == ["NVDA", "TSM", "ZZZQ"]
    assert out["resolved_by_fulltext"] == 0
    assert out["review_queue"]["total"] == 3
    conn = scs.connect(backend._sa_db)
    after = [tuple(row) for row in conn.execute(
        "SELECT id, canonical_article_id, detail_report FROM sa_alpha_picks ORDER BY id"
    )]
    conn.close()
    assert after == before


# --- (9) NO-PG-FALLBACK proof -------------------------------------------------------


def test_no_pg_fallback_even_on_empty_results(backend, monkeypatch):
    # Belt-and-braces on top of the fixture's _get_conn poison: poison the base
    # class sa_* methods themselves; empty local results must NEVER reach them.
    def _raise(self, *a, **k):
        raise AssertionError("PG touched")

    for name in ("query_sa_picks", "get_sa_pick_detail", "query_sa_market_news",
                 "get_sa_refresh_meta", "query_sa_articles"):
        monkeypatch.setattr(DatabaseBackend, name, _raise)

    scs.connect(backend._sa_db).close()  # create the (empty) schema

    assert backend.query_sa_picks() == []
    assert backend.query_sa_picks(portfolio_status="current", symbol="AAPL") == []
    assert backend.get_sa_pick_detail("AAPL") is None
    assert backend.get_sa_refresh_meta() == {}
    assert backend.query_sa_market_news() == []
    assert backend.query_sa_market_news(ticker="AAPL", keyword="anything") == []
    assert backend.query_sa_market_news_recent_ids() == []
    assert backend.query_sa_market_news_need_detail() == []
    assert backend.query_sa_articles() == []
    assert backend.get_sa_article_with_comments("missing") is None
    assert backend.audit_unresolved_symbols() == {
        "unresolved_symbols": [],
        "resolved_by_fulltext": 0,
        "review_queue": {"events": [], "total": 0},
    }
    assert backend.invalidate_dirty_sa_market_news_detail() == 0
    assert backend.sanitize_corrupted_sa_comments_counts() == 0
    assert backend.cleanup_mixed_null_date_comment_duplicates() == {
        "groups_processed": 0, "comments_deleted": 0, "parent_links_repointed": 0}


# --- (10) read shapes match the PG methods (key-set parity) ------------------------

# Key sets transcribed from the PG method sources in db_backend.py.
PG_QUERY_SA_PICKS_KEYS = {
    "symbol", "company", "picked_date", "closed_date", "portfolio_status",
    "is_stale", "return_pct", "sector", "sa_rating", "holding_pct",
    "has_detail", "last_seen_snapshot", "fetched_at", "updated_at",
}
# get_sa_pick_detail is SELECT * — PG table columns (sql/007 + canonical_article_id)
PG_PICK_DETAIL_KEYS = {
    "id", "symbol", "company", "picked_date", "closed_date", "portfolio_status",
    "is_stale", "return_pct", "sector", "sa_rating", "holding_pct",
    "detail_report", "detail_fetched_at", "raw_data", "last_seen_snapshot",
    "canonical_article_id", "fetched_at", "updated_at",
}
PG_MARKET_NEWS_KEYS = {
    "news_id", "url", "title", "published_at", "published_text", "tickers",
    "category", "summary", "comments_count", "body_markdown",
    "detail_fetched_at", "fetched_at", "updated_at",
}
PG_QUERY_SA_ARTICLES_KEYS = {
    "article_id", "url", "title", "ticker", "published_date", "article_type",
    "comments_count", "has_content", "detail_fetched_at", "comments_fetched_at",
    "stored_comments_count",
}
# get_sa_article_with_comments is SELECT * plus the injected "comments"; v2 adds
# source-specific provider observations while preserving every legacy key.
PG_ARTICLE_WITH_COMMENTS_KEYS = {
    "id", "article_id", "url", "title", "ticker", "author", "published_date",
    "article_type", "body_markdown", "comments_count", "detail_fetched_at",
    "comments_fetched_at", "raw_data", "fetched_at", "updated_at", "comments",
    "list_ticker", "list_ticker_observed_at", "detail_ticker",
    "detail_ticker_observed_at",
}
PG_COMMENT_KEYS = {
    "comment_id", "parent_comment_id", "commenter", "comment_text",
    "upvotes", "comment_date",
}
PG_REFRESH_META_KEYS = {
    "scope", "last_attempt_at", "last_success_at", "snapshot_ts",
    "row_count", "ok", "last_error", "updated_at",
}


def test_read_shapes_match_pg_key_sets(backend):
    backend.apply_sa_refresh("current", [_pick("NVDA", picked="2026-06-01")], T1, T1)
    backend.upsert_sa_market_news([_news()])
    backend.upsert_sa_articles_meta([_article("a1")])
    backend.save_article_with_comments("a1", "body", _comments())

    assert set(backend.query_sa_picks()[0]) == PG_QUERY_SA_PICKS_KEYS
    assert set(backend.get_sa_pick_detail("NVDA")) == PG_PICK_DETAIL_KEYS

    news = backend.query_sa_market_news()[0]
    assert set(news) == PG_MARKET_NEWS_KEYS
    assert isinstance(news["tickers"], list)                 # PG TEXT[] → Python list

    assert set(backend.query_sa_articles()[0]) == PG_QUERY_SA_ARTICLES_KEYS

    art = backend.get_sa_article_with_comments("a1")
    assert set(art) == PG_ARTICLE_WITH_COMMENTS_KEYS
    assert isinstance(art["raw_data"], dict)                 # jsonb→dict parity
    assert set(art["comments"][0]) == PG_COMMENT_KEYS

    assert set(backend.get_sa_refresh_meta()["current"]) == PG_REFRESH_META_KEYS
