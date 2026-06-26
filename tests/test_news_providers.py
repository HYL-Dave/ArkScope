"""2c: Parquet-free news provider adapters + the use_local_news toggle (hermetic).

The adapter wraps the real collectors' fetch+parse (no StorageManager/Parquet) and maps the
collector NewsArticle to the local news row contract: article_hash=dedup_hash,
description=description or content. The toggle gates scheduler routing (default-OFF).
"""
from __future__ import annotations

import sqlite3

import src.news_providers as np
from scripts.collection.collect_polygon_news import NewsArticle


def _article(**kw):
    base = dict(article_id="x", ticker="AAPL", title="Beat", published_at="2026-06-24T13:30:00+0000")
    base.update(kw)
    return NewsArticle(**base)


def test_article_to_raw_maps_real_collector_dataclass():
    a = _article(description="", content="full body text", url="http://u", publisher="Reuters",
                 dedup_hash="md5hash123")
    raw = np._article_to_raw(a)
    assert raw["article_hash"] == "md5hash123"            # dedup_hash → article_hash
    assert raw["description"] == "full body text"         # description empty → falls back to content
    assert raw["published_at"] == "2026-06-24T13:30:00+0000"
    assert raw["ticker"] == "AAPL" and raw["title"] == "Beat"
    assert raw["url"] == "http://u" and raw["publisher"] == "Reuters"


def test_article_to_raw_prefers_description_when_present():
    a = _article(description="short desc", content="long body", dedup_hash="h")
    assert np._article_to_raw(a)["description"] == "short desc"


def test_provider_fetch_uses_collector_fetch_parse_no_parquet():
    # provider.fetch_news → collector.fetch_news_range + parse_article → raw dicts; the fake
    # collector has NO save_articles, proving the direct path never writes Parquet.
    class _FakePolygon:
        def __init__(self): self.range_args = None
        def fetch_news_range(self, ticker, start, end, **kw):
            self.range_args = (ticker, start, end)
            return [{"id": "1"}, {"id": "2"}]
        def parse_article(self, raw, collected_at):
            return _article(article_id=raw["id"], dedup_hash="h" + raw["id"],
                            description="d" + raw["id"], content="c")
    fake = _FakePolygon()
    prov = np.make_news_provider("polygon", collector=fake)
    out = prov.fetch_news("AAPL", since_iso="2026-06-20T00:00:00+0000")
    assert [r["article_hash"] for r in out] == ["h1", "h2"]
    assert fake.range_args[0] == "AAPL" and str(fake.range_args[1]) == "2026-06-20"  # cursor date
    assert not hasattr(fake, "save_articles")  # no Parquet sink touched


def test_provider_skips_none_parse_results():
    # finnhub parse_article returns None for truncated articles → dropped, not crashing.
    class _FakeFinnhub:
        def fetch_news(self, ticker, start, end, **kw):
            return [{"id": "1"}, {"id": "2"}]
        def parse_article(self, raw, ticker, collected_at):
            return None if raw["id"] == "2" else _article(dedup_hash="h1")
    out = np.make_news_provider("finnhub", collector=_FakeFinnhub()).fetch_news("AAPL")
    assert [r["article_hash"] for r in out] == ["h1"]


def test_use_local_news_default_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_NEWS", raising=False)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "absent.db"))
    assert np.use_local_news_enabled() is False


def test_use_local_news_env_override_on(monkeypatch):
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_NEWS", "1")
    assert np.use_local_news_enabled() is True


def test_use_local_news_profile_setting_on(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_NEWS", raising=False)
    db = tmp_path / "profile_state.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE profile_settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT INTO profile_settings VALUES ('use_local_news', 'true')")
    c.commit(); c.close()
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))
    assert np.use_local_news_enabled() is True
