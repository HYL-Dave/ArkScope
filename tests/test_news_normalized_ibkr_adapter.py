from contextlib import contextmanager, nullcontext
import json
import sqlite3
import traceback
from types import SimpleNamespace

from ib_insync import RequestError
import pytest

import data_sources.ibkr_source as ibkr_source
from data_sources.ibkr_source import IBKRDataSource, IBKRNewsArticleUnavailable
from scripts.diagnostics.probe_ibkr_news_bodies import (
    DEFAULT_PROBES,
    ProbeSpec,
    main as probe_main,
)
from src.news_normalized.ibkr_adapter import IBKRHeadline, IBKRNormalizedProvider
from src.news_normalized.models import (
    ArticleCandidate,
    BodyStatus,
    WriterBudget,
)
from src.news_normalized.store import NormalizedNewsStore
from src.news_normalized.writer import write_news_batch


class FakeGateway:
    def __init__(self):
        self.headlines = {}
        self.bodies = {}
        self.body_errors = {}
        self.body_calls = []

    def fetch_headlines(self, ticker, since_iso):
        return list(self.headlines.get(ticker, ()))

    def fetch_news_article_body_strict(self, provider_code, article_id):
        self.body_calls.append((provider_code, article_id))
        error = self.body_errors.pop((provider_code, article_id), None)
        if error:
            raise error
        return self.bodies.get((provider_code, article_id))


def test_ibkr_news_unavailable_exception_is_public():
    assert hasattr(ibkr_source, "IBKRNewsArticleUnavailable")


class BodyClient:
    def __init__(self, result=None, error=None, raise_request_errors=False):
        self.result = result
        self.error = error
        self.RaiseRequestErrors = raise_request_errors
        self.setting_seen = []

    def reqNewsArticle(self, provider_code, article_id):
        self.setting_seen.append(self.RaiseRequestErrors)
        if self.error is not None:
            raise self.error
        return self.result

    def disconnect(self):
        pass


def body_source(client):
    source = IBKRDataSource.__new__(IBKRDataSource)
    source._ib = client
    source._ensure_connected = lambda: None
    source._rate_limit_wait = lambda: None
    return source


@pytest.mark.parametrize(
    ("result", "expected"),
    [(None, None), (SimpleNamespace(articleText="text"), "text")],
)
def test_ibkr_strict_body_scopes_request_errors_and_restores_on_success(
    result, expected
):
    client = BodyClient(result=result, raise_request_errors=False)

    assert (
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")
        == expected
    )
    assert client.setting_seen == [True]
    assert client.RaiseRequestErrors is False


def test_ibkr_strict_body_translates_10172_without_leaking_provider_message():
    secret = "licensed provider payload"
    client = BodyClient(error=RequestError(4, 10172, secret))

    with pytest.raises(IBKRNewsArticleUnavailable) as caught:
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")

    rendered = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert caught.value.error_code == 10172
    assert secret not in str(caught.value)
    assert secret not in rendered
    assert caught.value.__suppress_context__ is True
    assert client.RaiseRequestErrors is False


def test_ibkr_strict_body_reraises_other_request_errors_and_restores():
    error = RequestError(5, 321, "other")
    client = BodyClient(error=error, raise_request_errors=True)

    with pytest.raises(RequestError) as caught:
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")

    assert caught.value is error
    assert client.setting_seen == [True]
    assert client.RaiseRequestErrors is True


def test_ibkr_strict_body_restores_after_transport_error():
    client = BodyClient(error=TimeoutError("timeout"))

    with pytest.raises(TimeoutError):
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")

    assert client.setting_seen == [True]
    assert client.RaiseRequestErrors is False


def headline(article_id, ticker):
    return IBKRHeadline(
        article_id=article_id,
        provider_code="DJ-N",
        title="Shared story",
        published_at="2026-06-27T10:00:00Z",
        observed_at="2026-06-27T10:01:00Z",
        ticker=ticker,
    )


def candidate(article_id="DJ-N$2"):
    return ArticleCandidate(
        source="ibkr",
        provider_article_id=article_id,
        title="Story",
        publisher="DJ-N",
        published_at="2026-06-27T10:00:00Z",
        primary_ticker="AAPL",
    )


def test_ibkr_adapter_fetches_one_body_for_article_seen_through_many_tickers(
    monkeypatch,
):
    gateway = FakeGateway()
    gateway.headlines = {
        "AAPL": [headline("DJ-N$1", "AAPL")],
        "MSFT": [headline("DJ-N$1", "MSFT")],
    }
    gateway.bodies[("DJ-N", "DJ-N$1")] = "<p>body</p>"
    lock_entries = []

    @contextmanager
    def counting_lock():
        lock_entries.append("enter")
        yield

    monkeypatch.setattr(
        "src.news_normalized.ibkr_adapter.ibkr_gateway_lock", counting_lock
    )
    conn = sqlite3.connect(":memory:")
    store = NormalizedNewsStore(conn)

    result = write_news_batch(
        store,
        IBKRNormalizedProvider(gateway),
        ["AAPL", "MSFT"],
        WriterBudget(10, 10),
    )

    assert lock_entries == ["enter"]
    assert gateway.body_calls == [("DJ-N", "DJ-N$1")]
    assert result.articles_inserted == 1
    assert conn.execute("SELECT COUNT(*) FROM news_article_tickers").fetchone()[0] == 2
    assert conn.execute("SELECT content_kind FROM news_articles").fetchone()[0] == "full_text"
    conn.close()


def test_ibkr_failed_body_is_retryable_and_not_cached():
    gateway = FakeGateway()
    key = ("DJ-N", "DJ-N$2")
    gateway.body_errors[key] = TimeoutError("timeout")
    provider = IBKRNormalizedProvider(gateway)

    first = provider.fetch_body(candidate())
    gateway.bodies[key] = "recovered"
    second = provider.fetch_body(candidate())

    assert first.status is BodyStatus.FAILED
    assert "timeout" in first.error
    assert second.status is BodyStatus.FETCHED
    assert gateway.body_calls == [key, key]


def test_ibkr_successful_empty_response_is_terminal_empty():
    provider = IBKRNormalizedProvider(FakeGateway())

    body = provider.fetch_body(candidate())

    assert body.status is BodyStatus.EMPTY
    assert body.raw_body is None


def test_ibkr_strict_body_method_propagates_but_compatibility_method_catches():
    source = body_source(BodyClient(error=TimeoutError("gateway timeout")))

    with pytest.raises(TimeoutError):
        source.fetch_news_article_body_strict("DJ-N", "DJ-N$2")
    assert source.fetch_news_article_body("DJ-N", "DJ-N$2") is None


def test_probe_output_never_contains_body_or_exception_payload(capsys):
    secret = "LICENSED-ARTICLE-SECRET-7f3c"

    class Source:
        def fetch_news_article_body_strict(self, provider, article_id):
            if article_id == "ok":
                return f"<p>{secret}</p>"
            raise RuntimeError(f"failure contains {secret}")

        def disconnect(self):
            pass

    probes = (
        ProbeSpec("normal", "DJ-RTA", "ok"),
        ProbeSpec("error", "DJ-N", "bad"),
    )

    exit_code = probe_main(
        [],
        source_factory=Source,
        probes=probes,
        lock_factory=nullcontext,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert secret not in captured.out
    assert secret not in captured.err
    payload = json.loads(captured.out)
    assert payload[0] == {
        "html_tags": 2,
        "label": "normal",
        "length": len(f"<p>{secret}</p>"),
        "present": True,
        "provider": "DJ-RTA",
        "response_class": "body",
    }
    assert payload[1]["response_class"] == "error"
    assert payload[1]["error_type"] == "RuntimeError"


def test_probe_has_five_reviewed_default_cases():
    assert len(DEFAULT_PROBES) == 5
    assert {item.label for item in DEFAULT_PROBES} == {
        "recent_body",
        "recent_missing",
        "old_body",
        "old_missing",
        "alert",
    }
