import sqlite3

import pytest


def corpus(tmp_path, *, kind="full_text", body="Issuer OLD common stock ceased trading on September 1, 2026."):
    from src.news_normalized.schema import ARTICLE_SCHEMA
    path = tmp_path / "news.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(ARTICLE_SCHEMA)
        conn.execute("INSERT INTO news_articles(id,source,canonical_title,publisher,url,published_at,content_kind,created_at,updated_at) "
            "VALUES(1,'provider','OLD listing notice','Issuer','https://issuer.example/notice','2026-09-01',?,'2026-09-01','2026-09-01')", (kind,))
        conn.execute("INSERT INTO news_article_tickers VALUES(1,'OLD','primary','2026-09-01','2026-09-01')")
        conn.execute("INSERT INTO news_article_bodies(article_id,body_status,body_text,fetched_at) VALUES(1,'fetched',?,'2026-09-02')", (body,))
    return path


def test_local_news_unavailable_is_not_an_empty_success(tmp_path):
    from src.lifecycle_investigation.news import LocalNews
    result = LocalNews(tmp_path / "missing.db", tmp_path / "missing-sa.db").search(ticker="OLD")
    assert result["status"] == "unavailable"
    assert result["items"] == [] and result["gaps"]


@pytest.mark.parametrize("kind,expected", [("full_text", "full_text"), ("summary", "summary"), ("unknown", "unknown")])
def test_news_preview_is_not_full_body_evidence(tmp_path, kind, expected):
    from src.lifecycle_investigation.news import LocalNews
    news = LocalNews(corpus(tmp_path, kind=kind), None)
    result = news.search(ticker="OLD")
    assert result["status"] == "ok"
    item = news.read(result["items"][0]["candidate_id"])
    assert item["coverage"] == expected
    assert "body_text" not in result["items"][0]
    assert "raw_body" not in str(item) and "article_id" not in str(item)


def test_lifecycle_news_snapshot_survives_collector_update(tmp_path):
    from src.lifecycle_investigation.news import LocalNews
    path = corpus(tmp_path)
    news = LocalNews(path, None)
    item = news.read(news.search(ticker="OLD")["items"][0]["candidate_id"])
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE news_article_bodies SET body_text='changed'")
    assert "ceased trading" in item["text"]
    assert item["text_sha256"] != news.read(news.search(ticker="OLD")["items"][0]["candidate_id"])["text_sha256"]


def test_local_search_is_exact_ticker_scoped_and_closed(tmp_path):
    from src.lifecycle_investigation.news import LocalNews
    path = corpus(tmp_path)
    before = path.read_bytes()
    news = LocalNews(path, None)
    assert news.search(ticker="OL")["items"] == []
    with pytest.raises(ValueError, match="local_candidate_unknown"):
        news.read("1")
    assert path.read_bytes() == before


def test_sa_news_body_coverage_dates_and_pagination_are_exact_and_do_not_read_research_notes(tmp_path):
    from src import sa_capture_store
    from src.lifecycle_investigation.news import LocalNews
    path = tmp_path / "sa.db"
    sa_capture_store.connect(str(path)).close()
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE private_research_notes(body TEXT)")
        conn.execute("INSERT INTO private_research_notes VALUES ('SECRET PRIVATE NOTE')")
        for i, ticker in enumerate(("OLD", "OLD", "OLD", "OTHER"), 1):
            conn.execute("INSERT INTO sa_market_news(id,news_id,url,title,published_at,summary,body_markdown,detail_fetched_at,fetched_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (i, f"news-{i}", f"https://seekingalpha.com/news/{i}-notice", f"Public notice {i}", f"2026-09-0{i}",
                 "Summary only", "Complete public text" if i == 2 else None, "2026-09-08" if i == 2 else None, "2026-09-08"))
            conn.execute("INSERT INTO sa_market_news_tickers VALUES (?,?)", (i, ticker))
    before = path.read_bytes()
    reader = LocalNews(None, path)
    first = reader.search(ticker="OLD", since="2026-09-02", until="2026-09-03", limit=1)
    assert first["next_offset"] == 1 and first["items"][0]["title"] == "Public notice 3"
    assert reader.read(first["items"][0]["candidate_id"])["coverage"] == "summary"
    second = reader.search(ticker="OLD", since="2026-09-02", until="2026-09-03", limit=1, offset=1)
    body = reader.read(second["items"][0]["candidate_id"])
    assert body["coverage"] == "full_text" and body["text"] == "Complete public text"
    assert second["next_offset"] is None
    assert not reader.search(ticker="TA")["items"]
    assert not reader.search(ticker="OLD", query="SECRET PRIVATE NOTE")["items"]
    assert "raw_data" not in body and "news_id" not in body and "detail_fetched_at" not in body
    assert path.read_bytes() == before


def test_archived_or_reidentified_candidate_cannot_be_used_as_the_original_source(tmp_path):
    from src.lifecycle_investigation.news import LocalNews
    path = corpus(tmp_path)
    reader = LocalNews(path, None)
    identity = reader.search(ticker="OLD")["items"][0]["candidate_id"]
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE news_articles SET canonical_title='Different story'")
    with pytest.raises(ValueError, match="local_candidate_changed"):
        reader.read(identity)
