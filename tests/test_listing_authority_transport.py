from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import quote, quote_plus

import pytest
import requests

from data_sources.listing_authority_transport import (
    MASSIVE_TICKERS_URL,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    ListingAuthorityTransport,
    ListingRequestBudget,
    ListingTransportFailure,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        body: bytes = b"",
        *,
        headers: dict[str, str] | None = None,
        chunks: list[object] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else [body]
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, object]] = []
        self.closed = False

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        return response

    def close(self) -> None:
        self.closed = True


def _nasdaq_response(body: bytes = b"Symbol|Security Name\nAAPL|Apple Inc.\n") -> FakeResponse:
    return FakeResponse(body=body, headers={"Content-Type": "text/plain; charset=utf-8"})


def _massive_response(
    body: bytes = b'{"results":[{"ticker":"AAPL"}]}', *, chunks: list[object] | None = None
) -> FakeResponse:
    return FakeResponse(
        body=body,
        headers={"Content-Type": "application/json"},
        chunks=chunks,
    )


def _massive_call(
    transport: ListingAuthorityTransport,
    budget: ListingRequestBudget,
    ticker: str = "AAPL",
    *,
    expected_active: bool = True,
    market: str = "stocks",
) -> object:
    return transport.fetch_massive_ticker(
        ticker,
        expected_active=expected_active,
        market=market,
        api_key="secret-value",
        budget=budget,
    )


def _assert_closed_failure(
    error: Exception, expected_code: str, *untrusted_values: str
) -> None:
    assert type(error) is ListingTransportFailure
    assert error.code == expected_code
    assert str(error) == expected_code
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = repr(error)
    for value in untrusted_values:
        assert value not in rendered


def test_transport_allows_only_two_exact_nasdaq_files() -> None:
    """Rejecting a third directory request prevents per-case fetches."""
    session = FakeSession([_nasdaq_response(), _nasdaq_response()])
    transport = ListingAuthorityTransport(session=session)
    budget = ListingRequestBudget.lifecycle()

    first = transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)
    second = transport.fetch_nasdaq(OTHER_LISTED_URL, budget=budget)

    assert first.source_url == NASDAQ_LISTED_URL
    assert second.source_url == OTHER_LISTED_URL
    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)
    assert exc.value.code == "nasdaq_request_budget"
    assert len(session.calls) == 2


def test_nasdaq_allows_each_directory_at_most_once() -> None:
    """A repeated file cannot displace the required complementary directory."""
    session = FakeSession([_nasdaq_response()])
    transport = ListingAuthorityTransport(session=session)
    budget = ListingRequestBudget.lifecycle()

    transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)
    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)

    assert exc.value.code == "nasdaq_request_duplicate"
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "url",
    (
        "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/unknown.txt",
        "https://evil.example/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt?x=1",
    ),
)
def test_nasdaq_rejects_urls_outside_the_two_exact_files(url: str) -> None:
    """A broadened allowlist could let automation read arbitrary documents."""
    session = FakeSession()
    transport = ListingAuthorityTransport(session=session)

    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(url, budget=ListingRequestBudget.lifecycle())

    assert exc.value.code == "nasdaq_url_unsupported"
    assert session.calls == []


def test_nasdaq_rejects_redirects_and_wrong_content_type() -> None:
    """Redirects or HTML error pages cannot become an empty directory."""
    redirect = FakeResponse(302, headers={"Location": "https://example.test/"})
    wrong_type = FakeResponse(body=b"<html />", headers={"Content-Type": "text/html"})
    session = FakeSession([redirect, wrong_type])
    transport = ListingAuthorityTransport(session=session)

    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=ListingRequestBudget.lifecycle())
    assert exc.value.code == "nasdaq_redirect"
    assert redirect.closed is True

    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=ListingRequestBudget.lifecycle())
    assert exc.value.code == "nasdaq_content_type_mismatch"
    assert wrong_type.closed is True
    assert all(call["allow_redirects"] is False for call in session.calls)


def test_nasdaq_enforces_file_and_aggregate_byte_caps() -> None:
    """Oversized snapshots cannot consume an unbounded tick budget."""
    file_too_large = _nasdaq_response()
    file_too_large.headers["Content-Length"] = str(8 * 1024 * 1024 + 1)
    first = _nasdaq_response(b"a" * (8 * 1024 * 1024))
    aggregate_too_large = _nasdaq_response(b"b" * (4 * 1024 * 1024 + 1))
    session = FakeSession([file_too_large, first, aggregate_too_large])
    transport = ListingAuthorityTransport(session=session)

    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=ListingRequestBudget.lifecycle())
    assert exc.value.code == "nasdaq_response_too_large"

    budget = ListingRequestBudget.lifecycle()
    payload = transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)
    assert len(payload.body) == 8 * 1024 * 1024
    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_nasdaq(OTHER_LISTED_URL, budget=budget)
    assert exc.value.code == "nasdaq_byte_budget"


def test_massive_query_secret_never_leaves_the_request_boundary() -> None:
    """Persisted payload and diagnostics must not disclose the provider key."""
    session = FakeSession([_massive_response()])
    transport = ListingAuthorityTransport(session=session)
    budget = ListingRequestBudget.lifecycle()

    payload = _massive_call(transport, budget, " aapl ")

    assert payload.source_url == (
        "https://api.massive.com/v3/reference/tickers?"
        "ticker=AAPL&active=true&market=stocks&limit=2"
    )
    assert session.calls == [
        {
            "url": MASSIVE_TICKERS_URL,
            "params": {
                "ticker": "AAPL",
                "active": "true",
                "market": "stocks",
                "limit": 2,
                "apiKey": "secret-value",
            },
            "headers": {"Accept": "application/json"},
            "timeout": (5, 20),
            "stream": True,
            "allow_redirects": False,
        }
    ]
    rendered = json.dumps({"payload": payload.source_url, "diagnostics": transport.diagnostics(budget)})
    assert "secret-value" not in rendered


def test_lifecycle_transport_redacts_massive_key_from_urllib3_debug_logs(
    caplog,
) -> None:
    key = "lifecycle massive key+/%"
    encoded_key = quote(key, safe="")
    form_encoded_key = quote_plus(key, safe="")
    connectionpool_logger = logging.getLogger("urllib3.connectionpool")
    caplog.set_level(logging.DEBUG, logger=connectionpool_logger.name)

    def log_secret_variants(phase: str) -> None:
        connectionpool_logger.debug(
            "%s raw=%s encoded=%s form=%s; other=retained",
            phase,
            key,
            encoded_key,
            form_encoded_key,
        )

    class LoggingResponse(FakeResponse):
        def iter_content(self, chunk_size: int):
            log_secret_variants("stream")
            yield from super().iter_content(chunk_size)

        def close(self) -> None:
            log_secret_variants("close")
            super().close()

    class LoggingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            params = kwargs["params"]
            assert isinstance(params, dict)
            assert params["apiKey"] == key
            log_secret_variants("request")
            return super().get(url, **kwargs)

    transport = ListingAuthorityTransport(
        session=LoggingSession(
            [
                LoggingResponse(
                    body=b'{"results":[{"ticker":"AAPL"}]}',
                    headers={"Content-Type": "application/json"},
                )
            ]
        ),
    )
    transport.fetch_massive_ticker(
        "AAPL",
        expected_active=True,
        market="stocks",
        api_key=key,
        budget=ListingRequestBudget.lifecycle(),
    )

    assert "other=retained" in caplog.text
    for variant in (key, encoded_key, form_encoded_key):
        assert variant not in caplog.text


def test_massive_enforces_exact_ticker_dedupe_and_four_request_budget() -> None:
    """Exact lookups remain bounded even when callers repeat or fan out."""
    session = FakeSession([_massive_response()] * 4)
    transport = ListingAuthorityTransport(session=session)
    budget = ListingRequestBudget.lifecycle()

    _massive_call(transport, budget, "AAPL")
    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, budget, " aapl ")
    assert exc.value.code == "massive_request_duplicate"

    _massive_call(transport, budget, "MSFT")
    _massive_call(transport, budget, "NVDA")
    _massive_call(transport, budget, "TSLA", expected_active=False, market="otc")
    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, budget, "AMZN")
    assert exc.value.code == "massive_request_budget"
    assert len(session.calls) == 4


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    (
        ({"ticker": None}, "massive_ticker_invalid"),
        ({"market": None}, "massive_market_invalid"),
        ({"api_key": None}, "massive_api_key_missing"),
    ),
)
def test_massive_rejects_missing_or_non_text_lookup_inputs(
    kwargs: dict[str, object], expected_code: str
) -> None:
    """Coercing absent inputs could send an unintended exact lookup."""
    transport = ListingAuthorityTransport(session=FakeSession())
    arguments: dict[str, object] = {
        "ticker": "AAPL",
        "expected_active": True,
        "market": "stocks",
        "api_key": "secret-value",
        "budget": ListingRequestBudget.lifecycle(),
    }
    arguments.update(kwargs)

    with pytest.raises(ListingTransportFailure) as exc:
        transport.fetch_massive_ticker(**arguments)

    assert exc.value.code == expected_code


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    ((401, "massive_unauthorized"), (403, "massive_unauthorized"), (404, "massive_not_found"), (429, "massive_rate_limited")),
)
def test_massive_normalizes_provider_statuses_without_response_bodies(
    status_code: int, expected_code: str
) -> None:
    """Provider responses must become closed transport failures."""
    response = FakeResponse(status_code, b"credential=secret-value", headers={"Content-Type": "application/json"})
    transport = ListingAuthorityTransport(session=FakeSession([response]))

    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    assert exc.value.code == expected_code
    assert "credential" not in str(exc.value)
    assert "secret-value" not in str(exc.value)
    assert response.closed is True


def test_massive_rejects_oversized_wrong_type_and_malformed_bodies() -> None:
    """A non-JSON, oversized, or malformed payload cannot reach the parser."""
    oversized = _massive_response()
    oversized.headers["Content-Length"] = str(1024 * 1024 + 1)
    wrong_type = FakeResponse(body=b"{}", headers={"Content-Type": "text/plain"})
    malformed = _massive_response(chunks=[b'{"results":', "not-bytes"])
    session = FakeSession([oversized, wrong_type, malformed])
    transport = ListingAuthorityTransport(session=session)

    for expected_code in (
        "massive_response_too_large",
        "massive_content_type_mismatch",
        "massive_transport_unavailable",
    ):
        with pytest.raises(ListingTransportFailure) as exc:
            _massive_call(transport, ListingRequestBudget.lifecycle())
        assert exc.value.code == expected_code


def test_massive_rejects_malformed_json_and_multiple_exact_rows() -> None:
    """An ambiguous or invalid exact lookup must fail before evidence parsing."""
    malformed = _massive_response(b"{not json")
    ambiguous = _massive_response(b'{"results":[{"ticker":"AAPL"},{"ticker":"AAPL"}]}')
    transport = ListingAuthorityTransport(session=FakeSession([malformed, ambiguous]))

    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())
    assert exc.value.code == "massive_invalid_json"

    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())
    assert exc.value.code == "massive_response_ambiguous"


def test_massive_invalid_json_does_not_retain_decoder_document() -> None:
    """A JSONDecodeError document must not survive in the closed failure chain."""
    raw_marker = "raw-provider-body"
    api_key_marker = "apiKey=credential-value"
    body = f'{{"results":["{raw_marker}","{api_key_marker}"'.encode("ascii")
    transport = ListingAuthorityTransport(session=FakeSession([_massive_response(body)]))

    with pytest.raises(Exception) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    _assert_closed_failure(
        exc.value,
        "massive_invalid_json",
        raw_marker,
        api_key_marker,
    )


def test_massive_rejects_provider_error_envelopes() -> None:
    """A 200 provider error envelope cannot become an empty ticker result."""
    response = _massive_response(b'{"status":"ERROR","error":"secret-value"}')
    transport = ListingAuthorityTransport(session=FakeSession([response]))

    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    assert exc.value.code == "massive_provider_error"
    assert "secret-value" not in str(exc.value)


def test_transport_redacts_timeout_exception_and_closes_injected_session() -> None:
    """Request exceptions cannot expose a credential-bearing request URL."""
    class TimeoutSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            del kwargs
            raise requests.Timeout(f"timed out {url}?apiKey=secret-value")

    session = TimeoutSession()
    transport = ListingAuthorityTransport(session=session)
    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    assert exc.value.code == "massive_transport_unavailable"
    assert "secret-value" not in str(exc.value)
    assert exc.value.__cause__ is None
    assert exc.value.__context__ is None
    transport.close()
    assert session.closed is True


def test_transport_redacts_streaming_request_exceptions() -> None:
    """Chunked request failures cannot leak an exception URL or provider key."""
    class FailingResponse(FakeResponse):
        def iter_content(self, chunk_size: int):
            del chunk_size
            raise requests.ConnectionError("https://api.massive.com/?apiKey=secret-value")

    response = FailingResponse(headers={"Content-Type": "application/json"})
    transport = ListingAuthorityTransport(session=FakeSession([response]))

    with pytest.raises(ListingTransportFailure) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    assert exc.value.code == "massive_transport_unavailable"
    assert "secret-value" not in str(exc.value)
    assert exc.value.__cause__ is None
    assert exc.value.__context__ is None
    assert response.closed is True


def test_transport_redacts_generic_session_oserror() -> None:
    """A generic session failure must not retain a credential-bearing URL."""
    api_key_marker = "apiKey=generic-session-secret"

    class FailingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            del url, kwargs
            raise OSError(f"https://api.massive.com/tickers?{api_key_marker}")

    transport = ListingAuthorityTransport(session=FailingSession())

    with pytest.raises(Exception) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    _assert_closed_failure(
        exc.value,
        "massive_transport_unavailable",
        api_key_marker,
    )


@pytest.mark.parametrize("error_type", (OSError, TypeError, ValueError))
def test_transport_redacts_generic_streaming_exceptions(error_type: type[Exception]) -> None:
    """Generic body-stream failures must not retain raw provider content."""
    raw_marker = f"raw-stream-body-{error_type.__name__}"

    class FailingResponse(FakeResponse):
        def iter_content(self, chunk_size: int):
            del chunk_size
            raise error_type(raw_marker)

    response = FailingResponse(headers={"Content-Type": "application/json"})
    transport = ListingAuthorityTransport(session=FakeSession([response]))

    with pytest.raises(Exception) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    _assert_closed_failure(
        exc.value,
        "massive_transport_unavailable",
        raw_marker,
    )
    assert response.closed is True


@pytest.mark.parametrize("error_type", (OSError, TypeError, ValueError))
def test_transport_redacts_generic_response_content_exceptions(
    error_type: type[Exception],
) -> None:
    """Generic response metadata failures must not retain provider details."""
    api_key_marker = f"apiKey=response-{error_type.__name__}"

    class FailingHeaders:
        def items(self):
            raise error_type(api_key_marker)

    response = FakeResponse()
    response.headers = FailingHeaders()
    transport = ListingAuthorityTransport(session=FakeSession([response]))

    with pytest.raises(Exception) as exc:
        _massive_call(transport, ListingRequestBudget.lifecycle())

    _assert_closed_failure(
        exc.value,
        "massive_transport_unavailable",
        api_key_marker,
    )
    assert response.closed is True


def test_fixture_payloads_are_ascii_and_real_shaped() -> None:
    """Fixture corruption must not hide an incompatible provider payload shape."""
    root = Path(__file__).parent / "fixtures" / "listing_authority"
    for name in ("nasdaqlisted.txt", "otherlisted.txt"):
        body = (root / name).read_bytes()
        assert body.isascii()
        assert b"File Creation Time:" in body
    for name in ("massive-active.json", "massive-otc.json", "massive-inactive.json"):
        payload = json.loads((root / name).read_text(encoding="ascii"))
        assert isinstance(payload["results"], list)
