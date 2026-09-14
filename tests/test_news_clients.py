"""Live news client contracts, independent of retired CLI/storage owners."""

import builtins
import importlib.util
import json
import logging
import sys
from dataclasses import fields
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from src.news_clients import finnhub as cfn, polygon as cpn


@pytest.mark.parametrize("module,config,client", [
    (cpn, "CollectionConfig", "PolygonNewsCollector"),
    (cfn, "FinnhubConfig", "FinnhubNewsCollector"),
])
def test_clients_expose_only_transport_parser_and_credential_contract(module, config, client):
    assert callable(getattr(module, client))
    assert callable(module.load_env)
    assert {field.name for field in fields(getattr(module, config))}.isdisjoint({
        "data_dir", "checkpoint_dir", "default_start",
    })
    for name in ("main", "collect_news", "run_incremental", "StorageManager",
                 "CheckpointManager", "load_tickers", "generate_months"):
        assert not hasattr(module, name), name


@pytest.mark.parametrize("source", ["polygon", "finnhub"])
def test_fresh_client_import_does_not_configure_logging_write_files_or_start_provider(
    source, monkeypatch,
):
    path = Path(__file__).resolve().parents[1] / "src" / "news_clients" / f"{source}.py"
    spec = importlib.util.spec_from_file_location(f"_fresh_news_{source}", path)
    module = importlib.util.module_from_spec(spec)
    before = list(logging.getLogger().handlers)
    real_open = builtins.open

    def forbidden(*args, **kwargs):
        pytest.fail("import attempted logging/filesystem/provider setup")

    def read_only_open(file, mode="r", *args, **kwargs):
        assert not set(mode) & set("wax+"), (file, mode)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(logging, "basicConfig", forbidden)
    monkeypatch.setattr(logging, "FileHandler", forbidden)
    monkeypatch.setattr(requests, "Session", forbidden)
    spec.loader.exec_module(module)
    assert logging.getLogger().handlers == before


@pytest.mark.parametrize("source,module,key", [
    ("polygon", cpn, "MASSIVE_API_KEY"), ("finnhub", cfn, "FINNHUB_API_KEY"),
])
def test_normalized_client_missing_key_fails_before_constructing_session(
    source, module, key, monkeypatch,
):
    from src.service.data_scheduler import _make_normalized_news_provider

    monkeypatch.setattr(module, "load_env", lambda: "")
    monkeypatch.setattr(requests, "Session", lambda: pytest.fail("constructed before key check"))
    with pytest.raises(RuntimeError, match=key):
        _make_normalized_news_provider(source)


def test_massive_news_transport_builds_requests_on_the_current_api_host(monkeypatch):
    observed = {}

    class Session:
        def get(self, url, *, params, timeout):
            observed.update(url=url, params=params, timeout=timeout)
            return SimpleNamespace(status_code=200, json=lambda: {"results": []})

    monkeypatch.setattr(requests, "Session", Session)
    client = cpn.PolygonNewsCollector("test-key", cpn.CollectionConfig())
    monkeypatch.setattr(client.rate_limiter, "wait", lambda: None)
    assert client.fetch_news_range("AAPL", date(2026, 8, 1), date(2026, 8, 2)) == []
    assert observed["url"] == "https://api.massive.com/v2/reference/news"
    assert observed["params"]["apiKey"] == "test-key"


@pytest.mark.parametrize("precise", [False, True])
def test_massive_nonempty_pages_preserve_timestamp_and_pagination(precise, monkeypatch):
    observed = []
    pages = iter([
        {"results": [{"id": "first"}], "next_url": "https://api.massive.com/v2/reference/news?cursor=next"},
        {"results": [{"id": "second"}]},
    ])

    class Session:
        def get(self, url, *, params, timeout):
            observed.append((url, dict(params), timeout))
            return SimpleNamespace(status_code=200, json=lambda: next(pages))

    monkeypatch.setattr(requests, "Session", Session)
    client = cpn.PolygonNewsCollector("test-key", cpn.CollectionConfig())
    monkeypatch.setattr(client.rate_limiter, "wait", lambda: None)
    start = datetime(2026, 8, 1, 12, 34, 56, tzinfo=timezone.utc) if precise else None
    assert client.fetch_news_range("AAPL", date(2026, 8, 1), date(2026, 8, 2), start) == [
        {"id": "first"}, {"id": "second"},
    ]
    assert observed[0] == ("https://api.massive.com/v2/reference/news", {
        "ticker": "AAPL", "published_utc.gte": "2026-08-01T12:34:56Z" if precise else "2026-08-01",
        "published_utc.lte": "2026-08-02T23:59:59Z", "limit": 1000,
        "sort": "published_utc", "order": "asc", "apiKey": "test-key",
    }, 30)
    assert observed[1] == (
        "https://api.massive.com/v2/reference/news?cursor=next", {"apiKey": "test-key"}, 30,
    )
    assert client.stats["total_requests"] == 2


def test_finnhub_transport_preserves_requested_window_without_old_cli_clamp(monkeypatch):
    observed = []

    class Session:
        def get(self, url, *, params, timeout):
            observed.append((url, params, timeout))
            return SimpleNamespace(status_code=200, json=lambda: [{"id": 11}])

    monkeypatch.setattr(requests, "Session", Session)
    client = cfn.FinnhubNewsCollector("test-key", cfn.FinnhubConfig())
    monkeypatch.setattr(client.rate_limiter, "wait", lambda: None)
    assert client.fetch_news("NVDA", date(2026, 8, 1), date(2026, 8, 15)) == [{"id": 11}]
    assert observed == [("https://finnhub.io/api/v1/company-news", {
        "symbol": "NVDA", "from": "2026-08-01", "to": "2026-08-15", "token": "test-key",
    }, 30)]


def test_massive_parser_preserves_native_metadata_and_fallback_id():
    client = cpn.PolygonNewsCollector.__new__(cpn.PolygonNewsCollector)
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    raw = {"title": "Headline", "description": "Summary", "tickers": ["MSFT", "AAPL"],
           "published_utc": "2026-08-01T12:00:00Z", "publisher": {"name": "Wire"},
           "article_url": "https://example.test/story", "author": "Author", "keywords": ["growth"],
           "insights": [{"sentiment": "positive"}]}
    article = client.parse_article(raw, now)
    assert article.ticker == "MSFT" and article.source_api == "polygon"
    assert article.article_id == article.dedup_hash
    assert article.description == article.content == "Summary"
    assert article.published_at == raw["published_utc"] and article.collected_at == now.isoformat()
    assert json.loads(article.related_tickers) == ["MSFT", "AAPL"]
    assert json.loads(article.tags) == ["growth"]
    assert (article.publisher, article.author, article.url) == ("Wire", "Author", raw["article_url"])
    assert (article.source_sentiment, article.source_sentiment_label) == (1.0, "positive")
    assert client.parse_article({**raw, "id": 123}, now).article_id == "123"


@pytest.mark.parametrize("size,kept", [(99, True), (100, False), (500, False), (501, True)])
def test_finnhub_parser_preserves_truncation_filter_and_metadata(size, kept):
    client = cfn.FinnhubNewsCollector.__new__(cfn.FinnhubNewsCollector)
    client.stats = {"by_source": {}}
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    article = client.parse_article({
        "id": 42, "datetime": 1, "headline": "Headline", "summary": "x" * size,
        "source": "Yahoo", "related": ["MSFT", "AAPL"], "category": "one,two",
    }, "AAPL", now)
    if not kept:
        assert article is None
        assert client.stats == {"by_source": {}, "skipped_truncated": 1}
        return
    assert article.article_id == "42" and article.source_api == "finnhub"
    assert article.ticker == "AAPL" and article.published_at == "1970-01-01T00:00:01Z"
    assert article.content == "x" * size and article.content_length == size
    assert json.loads(article.related_tickers) == ["MSFT", "AAPL"]
    assert json.loads(article.tags) == ["one", "two"]
    assert article.source_sentiment is None and article.source_sentiment_label == ""
    assert client.stats == {"by_source": {"Yahoo": 1}}
