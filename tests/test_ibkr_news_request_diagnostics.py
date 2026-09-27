"""Real ib_insync completion/error paths with an offline broker transport."""

from datetime import datetime
import socket

import pytest

from data_sources import ibkr_source
from src.news_normalized.ibkr_runtime import IBKRNewsCoverageIncomplete, IBKRRuntimeGateway


@pytest.fixture
def source(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("news_diagnostics_test_must_not_use_network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    obj = ibkr_source.IBKRDataSource(host="offline", client_id=778)
    obj._ensure_event_loop()
    obj._ib = ibkr_source.IB()
    obj._ib.client._apiReady = True
    obj._connected = True
    obj.REQUEST_DELAY = 0
    yield obj
    obj._ib.client._apiReady = False
    obj.disconnect()


def fetch(source):
    return source._fetch_news_page(123, "FLY", datetime(2026, 9, 26), datetime(2026, 9, 27), "AAPL")


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("message,expected", [
    ("Error validating request: Not subscribed for 'FLY' provider", "ibkr_news_subscription_denied"),
    ("PRIVATE_PROVIDER_TEXT", "ibkr_news_request_failed"),
])
def test_request_denial_is_typed_and_restores_callback_and_error_policy(source, monkeypatch, strict, message, expected):
    ib = source._ib
    ib.RaiseRequestErrors = strict

    def rejected(req_id, *args):
        ib.wrapper.error(req_id, 321, message, "")

    monkeypatch.setattr(ib.client, "reqHistoricalNews", rejected)
    callback = ib.wrapper.historicalNewsEnd
    page = fetch(source)
    assert page.error_code == expected
    assert page.has_more is None
    assert page.articles == ()
    assert ib.RaiseRequestErrors is strict
    assert ib.client.reqHistoricalNews is rejected
    assert ib.wrapper.historicalNewsEnd == callback
    assert "PRIVATE_PROVIDER_TEXT" not in str(page)


def test_late_unrelated_end_does_not_complete_current_request(source, monkeypatch):
    ib = source._ib

    def response(req_id, *args):
        ib.wrapper.historicalNewsEnd(req_id, True)
        ib.wrapper.historicalNewsEnd(req_id + 999, False)

    monkeypatch.setattr(ib.client, "reqHistoricalNews", response)
    page = fetch(source)
    assert page.has_more is True
    assert page.error_code is None


def test_successful_empty_response_is_not_denied(source, monkeypatch):
    ib = source._ib
    monkeypatch.setattr(ib.client, "reqHistoricalNews", lambda req_id, *args: ib.wrapper.historicalNewsEnd(req_id, False))
    page = fetch(source)
    assert page.has_more is False and page.articles == ()
    assert page.error_code is None


def test_timeout_preserves_partial_headlines_and_late_end_cannot_claim_completion(source, monkeypatch):
    ib = source._ib
    calls = []

    def partial(req_id, *args):
        calls.append(req_id)
        ib.wrapper.historicalNews(req_id, "20260926 13:00:00", "FLY", "FLY$one", "Stored partial headline")
        ib.wrapper.historicalNewsEnd(req_id + 999, False)

    monkeypatch.setattr(ib.client, "reqHistoricalNews", partial)
    page = fetch(source)
    assert page.error_code == "ibkr_news_request_timeout"
    assert page.has_more is None
    assert [article.title for article in page.articles] == ["Stored partial headline"]
    assert len(calls) == 1


@pytest.mark.parametrize("code", ["ibkr_news_request_timeout", "ibkr_news_subscription_denied", "ibkr_news_request_failed"])
def test_runtime_emits_partial_articles_before_request_outcome(code):
    from tests.test_normalized_ibkr_worker import _runtime_news_article
    page = ibkr_source.IBKRNewsPage(
        articles=(_runtime_news_article("saved", datetime(2026, 9, 26)),), has_more=None, error_code=code,
    )

    class Source:
        def fetch_news_page_strict(self, *args, **kwargs):
            return page

    iterator = iter(IBKRRuntimeGateway(Source()).fetch_headlines("AAPL", None))
    assert next(iterator).article_id == "DJ-N$saved"
    with pytest.raises(IBKRNewsCoverageIncomplete, match=code):
        next(iterator)
