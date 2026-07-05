"""PG-exit Step 2a — direct-local news writer (hermetic: fake provider, temp DB, no PG).

provider → local market_data.db `news` + `news_fts`, no PG / no Parquet round-trip. Dedup on the
opaque article_hash (MD5 today — treated as a stable key, NOT assumed SHA-256), UTC-normalized
published_at, FTS searchable, provider_sync telemetry, per-ticker failure isolation, source-scoped
incremental cursor. 2a is the writer only — NO scheduler routing, NO live-DB migration (2b/2c).
"""

from __future__ import annotations

import sqlite3

import pytest

import src.news_direct as nd


class _FakeNewsProvider:
    """Injectable provider: fetch_news(ticker, since_iso) → list of raw article dicts.
    Records the `since` it was asked for (to assert the cursor)."""
    def __init__(self, by_ticker):
        self._by = by_ticker
        self.since_seen = {}

    def fetch_news(self, ticker, since_iso=None):
        self.since_seen[ticker] = since_iso
        return list(self._by.get(ticker, []))


def _article(ticker, title, published_at, *, h=None, desc="body", url="u", publisher="pub"):
    return {"ticker": ticker, "title": title, "published_at": published_at,
            "description": desc, "url": url, "publisher": publisher,
            "article_hash": h or f"{ticker}|{title}|{published_at[:10]}"}


def _news_db(tmp_path):
    return str(tmp_path / "market_data.db")


def _rows(db, where=""):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(f"SELECT * FROM news {where} ORDER BY published_at").fetchall()]
    finally:
        c.close()


def test_writes_articles_to_local_news(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    prov = _FakeNewsProvider({"AAPL": [
        _article("AAPL", "Beat", "2026-06-24T13:30:00Z", h="h1"),
        _article("AAPL", "Raise", "2026-06-24T14:00:00Z", h="h2")]})
    res = nd.backfill_news_direct(["AAPL"], source="polygon", provider=prov, db_path=db)
    assert res["articles_added"] == 2 and res["tickers_scanned"] == 1 and res["errors"] == {}
    rows = _rows(db)
    assert [r["title"] for r in rows] == ["Beat", "Raise"]
    assert all(r["source"] == "polygon" for r in rows)
    assert rows[0]["published_at"] == "2026-06-24T13:30:00+0000"   # UTC-normalized ('Z' → +0000)


def test_dedup_idempotent_on_article_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    arts = [_article("AAPL", "Beat", "2026-06-24T13:30:00Z", h="h1")]
    nd.backfill_news_direct(["AAPL"], source="polygon", provider=_FakeNewsProvider({"AAPL": arts}), db_path=db)
    # re-run with the SAME hash (even different title) → no duplicate row (INSERT OR IGNORE on hash)
    again = [_article("AAPL", "Beat (edited)", "2026-06-24T13:30:00Z", h="h1")]
    res = nd.backfill_news_direct(["AAPL"], source="polygon", provider=_FakeNewsProvider({"AAPL": again}), db_path=db)
    assert res["articles_added"] == 0
    assert len(_rows(db)) == 1


def test_direct_dedups_against_mirror_sha_row(tmp_path, monkeypatch):
    # S3.0 coexistence: a mirror-origin row uses the canonical SHA-256 hash; a later DIRECT fetch of
    # the SAME article (through make_news_provider -> _article_to_raw, which now computes that same
    # canonical SHA) must dedup -> NO duplicate row. (Before S3.0 the direct path used the
    # collector's MD5 dedup_hash, so the same article re-entered as a duplicate.)
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    from src.news_identity import canonical_article_hash as canonical
    import src.news_providers as npv
    from scripts.collection.collect_polygon_news import NewsArticle

    tk, title, pub = "AAPL", "Massive News for Apple Stock Investors!", "2026-06-27T00:20:57+0000"
    sha = canonical(tk, title, pub[:10])

    # create the schema via a first direct write of an UNRELATED article, then raw-insert a
    # MIRROR-STYLE row (canonical SHA hash) for the article under test.
    nd.backfill_news_direct(["NVDA"], source="polygon",
                            provider=_FakeNewsProvider({"NVDA": [_article("NVDA", "x", "2026-06-20T00:00:00Z", h="other")]}),
                            db_path=db)
    c = sqlite3.connect(db)
    c.execute("INSERT INTO news (ticker,title,description,url,publisher,source,published_at,article_hash) "
              "VALUES (?,?,?,?,?,?,?,?)", (tk, title, "body", "u", "pub", "polygon", pub, sha))
    c.commit(); c.close()

    # a DIRECT fetch of the same article through the real provider adapter (-> _article_to_raw -> SHA)
    class _FakeCollector:
        def fetch_news_range(self, ticker, start, end, **kw):
            return [{"id": "1"}]
        def parse_article(self, raw, collected_at):
            return NewsArticle(article_id="1", ticker=tk, title=title, published_at=pub,
                               description="body", url="u", publisher="pub", dedup_hash="md5_ignored")
    prov = npv.make_news_provider("polygon", collector=_FakeCollector())
    res = nd.backfill_news_direct(["AAPL"], source="polygon", provider=prov, db_path=db)
    assert res["articles_added"] == 0                      # deduped against the mirror SHA row
    assert len(_rows(db, "WHERE ticker='AAPL'")) == 1       # the mirror row only; no MD5 duplicate


def test_fts_search_finds_written_articles(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    prov = _FakeNewsProvider({"NVDA": [
        _article("NVDA", "Nvidia earnings beat", "2026-06-24T13:30:00Z", h="n1", desc="record datacenter revenue")]})
    nd.backfill_news_direct(["NVDA"], source="polygon", provider=prov, db_path=db)
    c = sqlite3.connect(db)
    try:
        # external-content FTS5 must be populated → MATCH finds the row by title AND body
        hit_title = c.execute("SELECT n.title FROM news_fts f JOIN news n ON n.id=f.rowid "
                              "WHERE news_fts MATCH 'earnings'").fetchone()
        hit_body = c.execute("SELECT COUNT(*) FROM news_fts WHERE news_fts MATCH 'datacenter'").fetchone()[0]
    finally:
        c.close()
    assert hit_title and hit_title[0] == "Nvidia earnings beat"
    assert hit_body == 1


def test_fts_synced_by_trigger_no_double_write(tmp_path, monkeypatch):
    # 2b: news_fts is populated by the AFTER INSERT trigger (not a manual insert) → exactly one fts
    # row per news row (no double-index), and a deduped re-run adds neither a news nor an fts row.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    arts = [_article("AAPL", "Beat", "2026-06-24T13:30:00Z", h="h1"),
            _article("AAPL", "Raise", "2026-06-24T14:00:00Z", h="h2")]
    nd.backfill_news_direct(["AAPL"], source="polygon", provider=_FakeNewsProvider({"AAPL": arts}), db_path=db)
    nd.backfill_news_direct(["AAPL"], source="polygon", provider=_FakeNewsProvider({"AAPL": arts}), db_path=db)  # all dup
    c = sqlite3.connect(db)
    try:
        news_n = c.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        fts_n = c.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0]
        match_n = c.execute("SELECT COUNT(*) FROM news_fts WHERE news_fts MATCH 'beat OR raise'").fetchone()[0]
    finally:
        c.close()
    assert news_n == 2 and fts_n == 2 and match_n == 2   # one fts row per news row, no double-index


def test_provider_sync_telemetry_news_domain(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    nd.backfill_news_direct(["AAPL"], source="polygon",
                            provider=_FakeNewsProvider({"AAPL": [_article("AAPL", "X", "2026-06-24T13:30:00Z", h="h1")]}),
                            db_path=db)
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    try:
        run = c.execute("SELECT * FROM provider_sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        meta = c.execute("SELECT * FROM provider_sync_meta WHERE provider='polygon' AND ticker='AAPL'").fetchone()
    finally:
        c.close()
    assert run["domain"] == "news" and run["status"] == "succeeded" and run["rows_added"] == 1
    assert meta["interval"] == "news" and meta["last_error"] is None
    assert meta["last_bar_datetime"] == "2026-06-24T13:30:00+0000"   # cursor = newest published_at


def test_per_ticker_failure_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)

    class _PartlyBroken(_FakeNewsProvider):
        def fetch_news(self, ticker, since_iso=None):
            if ticker == "BAD":
                raise RuntimeError("provider 500")
            return super().fetch_news(ticker, since_iso)

    prov = _PartlyBroken({"AAPL": [_article("AAPL", "ok", "2026-06-24T13:30:00Z", h="h1")], "BAD": []})
    res = nd.backfill_news_direct(["AAPL", "BAD"], source="polygon", provider=prov, db_path=db)
    assert res["articles_added"] == 1                  # AAPL still written
    assert "BAD" in res["errors"] and "provider 500" in res["errors"]["BAD"]
    assert len(_rows(db)) == 1                          # batch not aborted by BAD


def test_incremental_cursor_is_source_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    # seed an existing polygon article; a finnhub run for the same ticker must NOT inherit
    # polygon's cursor (source-scoped — decision 4).
    nd.backfill_news_direct(["AAPL"], source="polygon",
                            provider=_FakeNewsProvider({"AAPL": [_article("AAPL", "P", "2026-06-24T13:30:00Z", h="p1")]}),
                            db_path=db)
    finn = _FakeNewsProvider({"AAPL": [_article("AAPL", "F", "2026-06-20T10:00:00Z", h="f1")]})
    nd.backfill_news_direct(["AAPL"], source="finnhub", provider=finn, db_path=db)
    assert finn.since_seen["AAPL"] is None             # no prior finnhub article → cursor None
    # second polygon run sees polygon's own latest as the cursor
    poly2 = _FakeNewsProvider({"AAPL": []})
    nd.backfill_news_direct(["AAPL"], source="polygon", provider=poly2, db_path=db)
    assert poly2.since_seen["AAPL"] == "2026-06-24T13:30:00+0000"   # polygon's newest, not finnhub's


def test_skips_articles_missing_required_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    arts = [
        _article("AAPL", "good", "2026-06-24T13:30:00Z", h="h1"),
        {"ticker": "AAPL", "title": "", "published_at": "2026-06-24T14:00:00Z", "article_hash": "h2"},  # no title
        {"ticker": "AAPL", "title": "no hash", "published_at": "2026-06-24T15:00:00Z"},                  # no hash
    ]
    res = nd.backfill_news_direct(["AAPL"], source="polygon",
                                  provider=_FakeNewsProvider({"AAPL": arts}), db_path=db)
    assert res["articles_added"] == 1                  # only the valid one
    assert [r["title"] for r in _rows(db)] == ["good"]


def test_no_pg_dependency():
    import src.news_direct as mod
    assert not hasattr(mod, "psycopg2")


# --- 2a.1: cursor semantic + timestamp-normalization coverage (review gaps) ----------

def test_norm_published_offset_fractional_and_space():
    # the writer's published_at normalizer (not just 'Z'): offsets → UTC, fractional dropped,
    # space-separated tolerated, date-only tolerated, garbage → None (row skipped).
    assert nd._norm_published("2026-06-24T13:30:00Z") == "2026-06-24T13:30:00+0000"
    assert nd._norm_published("2026-06-24T13:30:00+00:00") == "2026-06-24T13:30:00+0000"
    assert nd._norm_published("2026-06-24T09:30:00-04:00") == "2026-06-24T13:30:00+0000"  # ET→UTC
    assert nd._norm_published("2026-06-24T13:30:00.500Z") == "2026-06-24T13:30:00+0000"   # fractional
    assert nd._norm_published("2026-06-24 13:30:00") == "2026-06-24T13:30:00+0000"        # space
    assert nd._norm_published("not-a-date") is None and nd._norm_published("") is None


def test_offset_articles_written_normalized(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    prov = _FakeNewsProvider({"AAPL": [_article("AAPL", "ET", "2026-06-24T09:30:00-04:00", h="e1")]})
    nd.backfill_news_direct(["AAPL"], source="polygon", provider=prov, db_path=db)
    assert _rows(db)[0]["published_at"] == "2026-06-24T13:30:00+0000"   # -04:00 → UTC


def test_exact_inclusive_cursor_keeps_same_second_sibling(tmp_path, monkeypatch):
    # the deliberate semantic: exact-inclusive cursor + dedup, NOT latest+1s. A sibling published
    # in the SAME second as the stored boundary (different hash) must be picked up, not skipped.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _news_db(tmp_path)
    nd.backfill_news_direct(["AAPL"], source="polygon",
                            provider=_FakeNewsProvider({"AAPL": [_article("AAPL", "first", "2026-06-24T13:30:00Z", h="a1")]}),
                            db_path=db)
    # 2nd run: provider returns the boundary article again (dedup) + a same-second sibling (new hash)
    prov2 = _FakeNewsProvider({"AAPL": [
        _article("AAPL", "first", "2026-06-24T13:30:00Z", h="a1"),       # boundary → deduped
        _article("AAPL", "sibling", "2026-06-24T13:30:00Z", h="a2")]})   # same second, NEW
    res = prov2 and nd.backfill_news_direct(["AAPL"], source="polygon", provider=prov2, db_path=db)
    assert prov2.since_seen["AAPL"] == "2026-06-24T13:30:00+0000"   # EXACT cursor (not +1s)
    assert res["articles_added"] == 1                               # only the sibling
    assert {r["title"] for r in _rows(db)} == {"first", "sibling"}  # sibling NOT skipped
