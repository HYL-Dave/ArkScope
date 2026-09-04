from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import quote, quote_plus

import pytest
import requests

import data_sources.lifecycle_provider_census_transport as census_transport
from data_sources.lifecycle_provider_census_transport import (
    MASSIVE_EVENTS_PREFIX,
    MASSIVE_LISTING_URL,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    CensusRequestBudget,
    CensusTransportFailure,
    LifecycleProviderCensusTransport,
)


_MISSING = object()


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
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def json_response(
    payload: object,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> FakeResponse:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return FakeResponse(
        status_code,
        body,
        headers=headers or {"Content-Type": "application/json; charset=utf-8"},
    )


def listing_fixture(
    ticker: str,
    active: bool,
    *,
    stable_id: str | None = "BBG_TEST_ARCH",
    next_url: object = _MISSING,
) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": ticker,
        "active": active,
        "market": "stocks",
    }
    if stable_id is not None:
        row["composite_figi"] = stable_id
    payload: dict[str, object] = {"status": "OK", "results": [row]}
    if next_url is not _MISSING:
        payload["next_url"] = next_url
    return payload


def event_fixture(
    source: str,
    successor: str,
    *,
    event_type: str = "ticker_change",
    effective_date: str = "2026-06-27",
    next_url: object = _MISSING,
) -> dict[str, object]:
    event: dict[str, object] = {
        "type": event_type,
        "date": effective_date,
    }
    if event_type == "ticker_change":
        event["ticker_change"] = {"ticker": successor}
    payload: dict[str, object] = {
        "status": "OK",
        "results": {"ticker": source, "events": [event]},
    }
    if next_url is not _MISSING:
        payload["next_url"] = next_url
    return payload


def budget(**kwargs: object) -> CensusRequestBudget:
    return CensusRequestBudget(**kwargs)


def transport_with_json(
    *payloads: object,
) -> tuple[LifecycleProviderCensusTransport, FakeSession]:
    session = FakeSession([json_response(payload) for payload in payloads])
    return LifecycleProviderCensusTransport(session=session), session


def transport_with_eodhd(
    *, active: object, delisted: object
) -> LifecycleProviderCensusTransport:
    return LifecycleProviderCensusTransport(
        session=FakeSession([json_response(active), json_response(delisted)])
    )


def eodhd_row(
    code: object,
    *,
    country: object = "USA",
    exchange: object = "NASDAQ",
) -> dict[str, object]:
    row = {"Code": code}
    if country is not _MISSING:
        row["Country"] = country
    if exchange is not _MISSING:
        row["Exchange"] = exchange
    return row


def assert_closed_failure(
    error: Exception, expected_code: str, *untrusted_values: str
) -> None:
    assert type(error) is CensusTransportFailure
    assert error.code == expected_code
    assert str(error) == expected_code
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = repr(error)
    for value in untrusted_values:
        assert value not in rendered


def test_massive_events_requires_stable_identifier_and_exact_ticker_change():
    transport, _session = transport_with_json(event_fixture("LC", "HAPN"))

    row = transport.fetch_massive_ticker_events(
        stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
    )

    assert row.events == (("LC", "HAPN", "2026-06-27"),)
    assert row.stable_id == "BBG_TEST_LC"
    assert row.source_locator == f"{MASSIVE_EVENTS_PREFIX}BBG_TEST_LC/events"


def test_massive_listing_returns_exact_normalized_secret_free_result():
    secret = "massive-secret-sentinel"
    payload = listing_fixture("ARCH", False, stable_id="BBG_TEST_ARCH")
    response_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )
    transport, session = transport_with_json(payload)

    row = transport.fetch_massive_listing(
        "ARCH", expected_active=False, api_key=secret, budget=budget()
    )

    assert (
        row.ticker,
        row.expected_active,
        row.found,
        row.active,
        row.stable_id,
    ) == ("ARCH", False, True, False, "BBG_TEST_ARCH")
    assert row.source_locator == (
        f"{MASSIVE_LISTING_URL}?ticker=ARCH&active=false&market=stocks&limit=2"
    )
    assert row.response_sha256 == hashlib.sha256(response_body).hexdigest()
    assert row.response_bytes == len(response_body)
    assert secret not in row.source_locator
    assert secret not in repr(row)
    assert session.calls[0]["url"] == MASSIVE_LISTING_URL
    assert session.calls[0]["params"] == {
        "ticker": "ARCH",
        "active": "false",
        "market": "stocks",
        "limit": 2,
        "apiKey": secret,
    }


def test_massive_listing_preserves_missing_stable_identity_for_runner():
    transport, _session = transport_with_json(
        listing_fixture("AAPL", True, stable_id=None)
    )

    row = transport.fetch_massive_listing(
        "AAPL", expected_active=True, api_key="secret", budget=budget()
    )

    assert row.found is True
    assert row.active is True
    assert row.stable_id is None


def test_massive_listing_empty_exact_result_is_complete_not_found():
    transport, _session = transport_with_json({"status": "OK", "results": []})

    row = transport.fetch_massive_listing(
        "TA", expected_active=False, api_key="secret", budget=budget()
    )

    assert (row.ticker, row.found, row.active, row.stable_id) == (
        "TA",
        False,
        None,
        None,
    )


def test_massive_event_budget_stops_before_fifteenth_request():
    b = CensusRequestBudget(max_massive_requests=14)
    for index in range(14):
        b.reserve_massive(("listing", str(index)))

    with pytest.raises(CensusTransportFailure, match="massive_request_budget"):
        b.reserve_massive(("events", "overflow"))

    assert b.massive_requests == 14


def test_census_budget_rejects_wider_or_invalid_provider_limits():
    cases = (
        {"max_massive_requests": 15},
        {"max_massive_requests": 0},
        {"max_massive_requests": True},
        {"max_nasdaq_requests": 3},
        {"max_eodhd_requests": 3},
    )

    for limits in cases:
        with pytest.raises(ValueError, match="census_request_budget"):
            CensusRequestBudget(**limits)


def test_census_budget_maxima_are_immutable_after_construction():
    b = budget()

    with pytest.raises(AttributeError, match="census_request_budget_limit"):
        b.max_massive_requests = 15
    with pytest.raises(AttributeError, match="census_request_budget_limit"):
        b.max_eodhd_requests = 3
    with pytest.raises(AttributeError, match="census_request_budget_limit"):
        b.max_nasdaq_requests = 3


def test_provider_request_budgets_are_independent():
    b = budget(max_massive_requests=1, max_nasdaq_requests=1)
    b.reserve_massive(("listing", "ARCH"))
    b.reserve_nasdaq(NASDAQ_LISTED_URL)

    with pytest.raises(CensusTransportFailure, match="massive_request_budget"):
        b.reserve_massive(("listing", "TA"))
    with pytest.raises(CensusTransportFailure, match="nasdaq_request_budget"):
        b.reserve_nasdaq(OTHER_LISTED_URL)

    assert (b.massive_requests, b.eodhd_requests, b.nasdaq_requests) == (1, 0, 1)


def test_secret_never_appears_in_failure_or_source_locator():
    secret = "massive-secret-sentinel"

    class FailingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"url": url, **kwargs})
            raise requests.Timeout(f"failed {url}?apiKey={kwargs['params']['apiKey']}")

    transport = LifecycleProviderCensusTransport(session=FailingSession())
    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key=secret, budget=budget()
        )

    assert_closed_failure(caught.value, "massive_transport_unavailable", secret)


def test_massive_debug_logs_redact_raw_and_encoded_credentials(caplog):
    key = "massive key+/%"
    encoded_key = quote(key, safe="")
    form_encoded_key = quote_plus(key, safe="")
    logger = logging.getLogger("urllib3.connectionpool")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    class LoggingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            logger.debug(
                "request raw=%s encoded=%s form=%s retained=yes",
                key,
                encoded_key,
                form_encoded_key,
            )
            return super().get(url, **kwargs)

    transport = LifecycleProviderCensusTransport(
        session=LoggingSession([json_response(listing_fixture("AAPL", True))])
    )
    transport.fetch_massive_listing(
        "AAPL", expected_active=True, api_key=key, budget=budget()
    )

    assert "retained=yes" in caplog.text
    for variant in (key, encoded_key, form_encoded_key):
        assert variant not in caplog.text


def test_request_url_containing_credential_is_rejected_before_http(monkeypatch):
    secret = "embedded-secret"
    session = FakeSession()
    monkeypatch.setattr(
        census_transport,
        "MASSIVE_LISTING_URL",
        f"https://api.massive.com/v3/reference/tickers?apiKey={secret}",
    )
    transport = LifecycleProviderCensusTransport(session=session)

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key=secret, budget=budget()
        )

    assert_closed_failure(caught.value, "request_url_credential", secret)
    assert session.calls == []


def test_transport_requires_an_injected_session():
    with pytest.raises(TypeError):
        LifecycleProviderCensusTransport()  # type: ignore[call-arg]


def test_transport_disables_redirects_and_uses_fifteen_second_timeout():
    transport, session = transport_with_json(
        listing_fixture("AAPL", True), event_fixture("LC", "HAPN")
    )
    b = budget()

    transport.fetch_massive_listing(
        "AAPL", expected_active=True, api_key="secret", budget=b
    )
    transport.fetch_massive_ticker_events(
        stable_id="BBG_TEST_LC", api_key="secret", budget=b
    )

    assert len(session.calls) == 2
    for call in session.calls:
        assert call["allow_redirects"] is False
        assert call["timeout"] == 15
        assert call["stream"] is True


def test_massive_events_rejects_ticker_identifier_before_request():
    transport, session = transport_with_json(event_fixture("LC", "HAPN"))

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_ticker_events(
            stable_id="LC", api_key="secret", budget=budget()
        )

    assert caught.value.code == "massive_stable_id_invalid"
    assert session.calls == []


def test_massive_events_reject_unknown_event_types():
    transport, _session = transport_with_json(
        event_fixture("ARCH", "CNR", event_type="merger")
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_ticker_events(
            stable_id="BBG_TEST_ARCH", api_key="secret", budget=budget()
        )

    assert caught.value.code == "massive_event_type_unsupported"


@pytest.mark.parametrize(
    "effective_date",
    ("2026-6-27", "2026-06-27T00:00:00Z", "2026-02-30", "not-a-date", None),
)
def test_massive_events_reject_malformed_dates(effective_date: object):
    transport, _session = transport_with_json(
        event_fixture("LC", "HAPN", effective_date=effective_date)  # type: ignore[arg-type]
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_ticker_events(
            stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
        )

    assert caught.value.code == "massive_event_date_invalid"


@pytest.mark.parametrize(
    ("source", "successor"),
    (("lc", "HAPN"), ("LC", "hapn"), ("LC ", "HAPN"), ("LC", "HAPN ")),
)
def test_massive_events_preserve_exact_case_sensitive_ticker_binding(
    source: str, successor: str
):
    transport, _session = transport_with_json(event_fixture(source, successor))

    with pytest.raises(CensusTransportFailure, match="massive_event_ticker_invalid"):
        transport.fetch_massive_ticker_events(
            stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
        )


def test_massive_listing_rejects_case_folded_or_wrong_active_rows():
    transport, _session = transport_with_json(
        listing_fixture("arch", False), listing_fixture("ARCH", True)
    )

    for expected_code in (
        "massive_listing_ticker_mismatch",
        "massive_listing_active_mismatch",
    ):
        with pytest.raises(CensusTransportFailure) as caught:
            transport.fetch_massive_listing(
                "ARCH", expected_active=False, api_key="secret", budget=budget()
            )
        assert caught.value.code == expected_code


def test_massive_rejects_duplicate_stable_identity_rows():
    row = listing_fixture("ARCH", False)["results"][0]  # type: ignore[index]
    transport, _session = transport_with_json(
        {"status": "OK", "results": [row, dict(row)]}
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key="secret", budget=budget()
        )

    assert caught.value.code == "massive_stable_identity_duplicate"


def test_massive_budget_rejects_repeated_stable_identity_without_second_call():
    transport, session = transport_with_json(event_fixture("LC", "HAPN"))
    b = budget()
    transport.fetch_massive_ticker_events(
        stable_id="BBG_TEST_LC", api_key="secret", budget=b
    )

    with pytest.raises(CensusTransportFailure, match="massive_request_duplicate"):
        transport.fetch_massive_ticker_events(
            stable_id="BBG_TEST_LC", api_key="secret", budget=b
        )

    assert len(session.calls) == 1


@pytest.mark.parametrize("next_url", ("https://api.massive.com/page/2", 1, True))
def test_massive_rejects_any_nonempty_next_url(next_url: object):
    transport, _session = transport_with_json(
        event_fixture("LC", "HAPN", next_url=next_url)
    )

    with pytest.raises(CensusTransportFailure, match="massive_pagination_unsupported"):
        transport.fetch_massive_ticker_events(
            stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
        )


@pytest.mark.parametrize("next_url", (_MISSING, None, ""))
def test_massive_accepts_only_absent_null_or_empty_next_url(next_url: object):
    fixture = event_fixture("LC", "HAPN", next_url=next_url)
    transport, _session = transport_with_json(fixture)

    result = transport.fetch_massive_ticker_events(
        stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
    )

    assert result.events == (("LC", "HAPN", "2026-06-27"),)


def test_massive_rejects_redirect_wrong_content_type_and_provider_error():
    redirect = FakeResponse(302, headers={"Location": "https://example.test"})
    wrong_type = FakeResponse(
        body=b"{}", headers={"Content-Type": "text/plain; charset=utf-8"}
    )
    provider_error = json_response({"status": "ERROR", "error": "raw-provider-secret"})
    session = FakeSession([redirect, wrong_type, provider_error])
    transport = LifecycleProviderCensusTransport(session=session)

    for ticker, expected_code in (
        ("ARCH", "massive_redirect"),
        ("LTHM", "massive_content_type_mismatch"),
        ("TA", "massive_provider_error"),
    ):
        with pytest.raises(CensusTransportFailure) as caught:
            transport.fetch_massive_listing(
                ticker, expected_active=False, api_key="secret", budget=budget()
            )
        assert_closed_failure(caught.value, expected_code, "raw-provider-secret")

    assert all(response.closed for response in (redirect, wrong_type, provider_error))


def test_massive_rejects_malformed_json_without_retaining_raw_body():
    raw_marker = "raw-provider-body"
    response = FakeResponse(
        body=f'{{"results":["{raw_marker}"'.encode("ascii"),
        headers={"Content-Type": "application/json"},
    )
    transport = LifecycleProviderCensusTransport(session=FakeSession([response]))

    with pytest.raises(Exception) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "massive_invalid_json", raw_marker)


def test_massive_normalizes_oversized_integer_json_value_error():
    body = b'{"status":"OK","results":[],"provider_value":' + b"9" * 5000 + b"}"
    response = FakeResponse(body=body, headers={"Content-Type": "application/json"})
    transport = LifecycleProviderCensusTransport(session=FakeSession([response]))

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "massive_invalid_json")


def test_massive_normalizes_deep_json_recursion_error():
    body = b"[" * 2000 + b"0" + b"]" * 2000
    response = FakeResponse(body=body, headers={"Content-Type": "application/json"})
    transport = LifecycleProviderCensusTransport(session=FakeSession([response]))

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "massive_invalid_json")


def test_massive_enforces_one_mib_response_and_fourteen_mib_aggregate_caps():
    oversized = FakeResponse(
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(1024 * 1024 + 1),
        }
    )
    transport = LifecycleProviderCensusTransport(session=FakeSession([oversized]))

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_massive_listing(
            "ARCH", expected_active=False, api_key="secret", budget=budget()
        )
    assert caught.value.code == "massive_response_too_large"

    b = budget()
    for _index in range(14):
        b.record_massive_body(1024 * 1024)
    with pytest.raises(CensusTransportFailure, match="massive_byte_budget"):
        b.record_massive_body(1)


def test_eodhd_active_and_delisted_sets_require_complete_requested_accounting():
    transport = transport_with_eodhd(active=[eodhd_row("AAPL")], delisted=[])

    result = transport.fetch_eodhd_symbol_sets(
        symbols=("AAPL", "TA"), api_key="secret", budget=budget()
    )

    assert result.active == ("AAPL",)
    assert result.delisted == ()
    assert result.unreported == ("TA",)
    assert result.complete is False


def test_eodhd_calls_only_us_status_endpoint_twice_with_same_sorted_manifest():
    secret = "eodhd-secret-sentinel"
    active = [eodhd_row("AAPL")]
    delisted = [eodhd_row("TA", exchange="NYSE"), eodhd_row("ARCH")]
    active_body = json.dumps(active, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )
    delisted_body = json.dumps(delisted, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )
    session = FakeSession([json_response(active), json_response(delisted)])
    transport = LifecycleProviderCensusTransport(session=session)
    b = budget()

    result = transport.fetch_eodhd_symbol_sets(
        symbols=("TA", "AAPL", "ARCH"), api_key=secret, budget=b
    )

    assert result.requested == ("AAPL", "ARCH", "TA")
    assert result.active == ("AAPL",)
    assert result.delisted == ("ARCH", "TA")
    assert result.unreported == ()
    assert result.complete is True
    assert result.active_response_sha256 == hashlib.sha256(active_body).hexdigest()
    assert result.delisted_response_sha256 == hashlib.sha256(delisted_body).hexdigest()
    assert result.active_response_bytes == len(active_body)
    assert result.delisted_response_bytes == len(delisted_body)
    assert result.active_source_locator.endswith(
        "?symbols=AAPL%2CARCH%2CTA&fmt=json&delisted=0"
    )
    assert result.delisted_source_locator.endswith(
        "?symbols=AAPL%2CARCH%2CTA&fmt=json&delisted=1"
    )
    assert secret not in repr(result)
    assert len(session.calls) == 2
    for index, call in enumerate(session.calls):
        assert call["url"] == census_transport.EODHD_EXCHANGE_SYMBOL_LIST_URL
        assert call["params"] == {
            "symbols": "AAPL,ARCH,TA",
            "fmt": "json",
            "delisted": index,
            "api_token": secret,
        }
        assert call["allow_redirects"] is False
        assert call["timeout"] == 15
        assert call["stream"] is True
    assert b.diagnostics() == {
        "massive_requests": 0,
        "massive_body_bytes": 0,
        "eodhd_requests": 2,
        "eodhd_body_bytes": len(active_body) + len(delisted_body),
        "nasdaq_requests": 0,
        "nasdaq_body_bytes": 0,
    }
    assert secret not in json.dumps(b.diagnostics(), sort_keys=True)


def test_eodhd_rejects_active_and_delisted_overlap():
    transport = transport_with_eodhd(
        active=[eodhd_row("AAPL")], delisted=[eodhd_row("AAPL")]
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_status_overlap")


@pytest.mark.parametrize("delisted", (False, True))
def test_eodhd_rejects_duplicate_codes(delisted: bool):
    duplicate = [eodhd_row("AAPL"), eodhd_row("AAPL")]
    transport = transport_with_eodhd(
        active=[] if delisted else duplicate,
        delisted=duplicate if delisted else [],
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_code_duplicate")


def test_eodhd_rejects_unexpected_code():
    transport = transport_with_eodhd(active=[eodhd_row("MSFT")], delisted=[])

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_code_unexpected", "MSFT")


@pytest.mark.parametrize(
    "row",
    (None, [], {}, {"Code": None}, {"Code": "aapl"}, {"Code": "AAPL "}),
)
def test_eodhd_rejects_malformed_rows(row: object):
    transport = transport_with_eodhd(active=[row], delisted=[])

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_row_invalid", "aapl", "AAPL ")


@pytest.mark.parametrize("lane", ("active", "delisted"))
@pytest.mark.parametrize(
    "country",
    (
        pytest.param(_MISSING, id="missing"),
        pytest.param(None, id="null"),
        pytest.param("", id="empty"),
        pytest.param("USA ", id="not-exact"),
        pytest.param("CAN", id="foreign"),
        pytest.param(123, id="non-string"),
    ),
)
def test_eodhd_rejects_invalid_country_provenance(lane: str, country: object):
    row = eodhd_row("AAPL", country=country)
    transport = transport_with_eodhd(
        active=[row] if lane == "active" else [],
        delisted=[row] if lane == "delisted" else [],
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_country_invalid")


@pytest.mark.parametrize("lane", ("active", "delisted"))
@pytest.mark.parametrize(
    "exchange",
    (
        pytest.param(_MISSING, id="missing"),
        pytest.param(None, id="null"),
        pytest.param("", id="empty"),
        pytest.param(" ", id="blank"),
        pytest.param(" NASDAQ", id="leading-space"),
        pytest.param("NAS\0DAQ", id="non-printable"),
        pytest.param("X" * 129, id="too-long"),
        pytest.param(123, id="non-string"),
    ),
)
def test_eodhd_rejects_invalid_exchange_provenance(lane: str, exchange: object):
    row = eodhd_row("AAPL", exchange=exchange)
    transport = transport_with_eodhd(
        active=[row] if lane == "active" else [],
        delisted=[row] if lane == "delisted" else [],
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_exchange_invalid")


def test_eodhd_accepts_open_bounded_printable_exchange_vocabulary():
    boundary_venue = "FUTURE-US-VENUE-" + "X" * 112
    assert len(boundary_venue) == 128
    transport = transport_with_eodhd(
        active=[eodhd_row("AAPL", exchange=boundary_venue)],
        delisted=[eodhd_row("TA", exchange="ANOTHER US VENUE")],
    )

    result = transport.fetch_eodhd_symbol_sets(
        symbols=("AAPL", "TA"), api_key="secret", budget=budget()
    )

    assert result.active == ("AAPL",)
    assert result.delisted == ("TA",)


def test_eodhd_rejects_non_us_exchange_endpoint_before_http(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(
        census_transport,
        "EODHD_EXCHANGE_SYMBOL_LIST_URL",
        "https://eodhd.com/api/exchange-symbol-list/LSE",
    )
    transport = LifecycleProviderCensusTransport(session=session)

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )

    assert_closed_failure(caught.value, "request_url_unsupported")
    assert session.calls == []


def test_eodhd_budget_stops_before_more_than_two_requests():
    session = FakeSession([json_response([eodhd_row("AAPL")]), json_response([])])
    transport = LifecycleProviderCensusTransport(session=session)
    b = budget()
    transport.fetch_eodhd_symbol_sets(symbols=("AAPL",), api_key="secret", budget=b)

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(symbols=("TA",), api_key="secret", budget=b)

    assert_closed_failure(caught.value, "eodhd_request_budget")
    assert b.eodhd_requests == 2
    assert len(session.calls) == 2


def test_eodhd_rejects_redirect_and_oversized_body():
    redirect = FakeResponse(
        302,
        headers={"Location": census_transport.EODHD_EXCHANGE_SYMBOL_LIST_URL},
    )
    oversized = FakeResponse(
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(1024 * 1024 + 1),
        }
    )
    transport = LifecycleProviderCensusTransport(
        session=FakeSession([redirect, oversized])
    )

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )
    assert_closed_failure(caught.value, "eodhd_redirect")
    assert redirect.closed is True

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key="secret", budget=budget()
        )
    assert_closed_failure(caught.value, "eodhd_response_too_large")
    assert oversized.closed is True


def test_eodhd_api_token_is_added_only_inside_dependency_log_redaction(monkeypatch):
    secret = "eodhd key+/%"
    state = {"active": False, "entries": 0}

    class RedactionGuard:
        def __init__(self, values: object) -> None:
            assert tuple(values) == (secret,)  # type: ignore[arg-type]

        def __enter__(self):
            assert state["active"] is False
            state["active"] = True
            state["entries"] += 1

        def __exit__(self, exc_type, exc, traceback):
            state["active"] = False

    class GuardedSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            assert state["active"] is True
            assert kwargs["params"]["api_token"] == secret  # type: ignore[index]
            assert "apiKey" not in kwargs["params"]  # type: ignore[operator]
            return super().get(url, **kwargs)

    monkeypatch.setattr(census_transport, "dependency_log_redaction", RedactionGuard)
    transport = LifecycleProviderCensusTransport(
        session=GuardedSession([json_response([eodhd_row("AAPL")]), json_response([])])
    )

    transport.fetch_eodhd_symbol_sets(
        symbols=("AAPL",), api_key=secret, budget=budget()
    )

    assert state == {"active": False, "entries": 2}


def test_eodhd_debug_logs_redact_raw_and_encoded_credentials(caplog):
    key = "eodhd key+/%"
    encoded_key = quote(key, safe="")
    form_encoded_key = quote_plus(key, safe="")
    logger = logging.getLogger("urllib3.connectionpool")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    class LoggingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            logger.debug(
                "eodhd raw=%s encoded=%s form=%s retained=yes",
                key,
                encoded_key,
                form_encoded_key,
            )
            return super().get(url, **kwargs)

    transport = LifecycleProviderCensusTransport(
        session=LoggingSession([json_response([eodhd_row("AAPL")]), json_response([])])
    )
    transport.fetch_eodhd_symbol_sets(symbols=("AAPL",), api_key=key, budget=budget())

    assert "retained=yes" in caplog.text
    for variant in (key, encoded_key, form_encoded_key):
        assert variant not in caplog.text


def test_eodhd_transport_failure_is_closed_and_secret_free():
    secret = "eodhd-secret-sentinel"

    class FailingSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"url": url, **kwargs})
            raise requests.Timeout(
                f"failed {url}?api_token={kwargs['params']['api_token']}"
            )

    session = FailingSession()
    transport = LifecycleProviderCensusTransport(session=session)

    with pytest.raises(CensusTransportFailure) as caught:
        transport.fetch_eodhd_symbol_sets(
            symbols=("AAPL",), api_key=secret, budget=budget()
        )

    assert_closed_failure(caught.value, "eodhd_transport_unavailable", secret)
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "url",
    (
        "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/unknown.txt",
        "https://evil.example/dynamic/SymDir/nasdaqlisted.txt",
        f"{NASDAQ_LISTED_URL}?page=2",
    ),
)
def test_nasdaq_directory_endpoint_allowlist_is_exact(url: str):
    session = FakeSession()
    transport = LifecycleProviderCensusTransport(session=session)

    with pytest.raises(CensusTransportFailure, match="nasdaq_url_unsupported"):
        transport.fetch_nasdaq_directory(url, budget=budget())

    assert session.calls == []


def test_nasdaq_directory_returns_bounded_payload_and_metadata():
    body = b"Symbol|Security Name\nAAPL|Apple Inc.\n"
    response = FakeResponse(
        body=body, headers={"Content-Type": "text/plain; charset=utf-8"}
    )
    session = FakeSession([response])
    transport = LifecycleProviderCensusTransport(session=session)

    result = transport.fetch_nasdaq_directory(NASDAQ_LISTED_URL, budget=budget())

    assert result.source_locator == NASDAQ_LISTED_URL
    assert result.body == body
    assert result.response_bytes == len(body)
    assert result.response_sha256 == hashlib.sha256(body).hexdigest()
    assert session.calls[0]["headers"] == {"Accept": "text/plain"}


def test_nasdaq_rejects_redirects_and_wrong_content_type():
    redirect = FakeResponse(301, headers={"Location": OTHER_LISTED_URL})
    wrong_type = FakeResponse(body=b"<html>", headers={"Content-Type": "text/html"})
    transport = LifecycleProviderCensusTransport(
        session=FakeSession([redirect, wrong_type])
    )

    for source_url, expected_code in (
        (NASDAQ_LISTED_URL, "nasdaq_redirect"),
        (OTHER_LISTED_URL, "nasdaq_content_type_mismatch"),
    ):
        with pytest.raises(CensusTransportFailure) as caught:
            transport.fetch_nasdaq_directory(source_url, budget=budget())
        assert caught.value.code == expected_code


def test_nasdaq_preserves_eight_mib_file_and_twelve_mib_aggregate_caps():
    file_too_large = FakeResponse(
        headers={
            "Content-Type": "text/plain",
            "Content-Length": str(8 * 1024 * 1024 + 1),
        }
    )
    first = FakeResponse(
        body=b"a" * (8 * 1024 * 1024), headers={"Content-Type": "text/plain"}
    )
    aggregate_too_large = FakeResponse(
        body=b"b" * (4 * 1024 * 1024 + 1),
        headers={"Content-Type": "text/plain"},
    )
    transport = LifecycleProviderCensusTransport(
        session=FakeSession([file_too_large, first, aggregate_too_large])
    )

    with pytest.raises(CensusTransportFailure, match="nasdaq_response_too_large"):
        transport.fetch_nasdaq_directory(NASDAQ_LISTED_URL, budget=budget())

    b = budget()
    transport.fetch_nasdaq_directory(NASDAQ_LISTED_URL, budget=b)
    with pytest.raises(CensusTransportFailure, match="nasdaq_byte_budget"):
        transport.fetch_nasdaq_directory(OTHER_LISTED_URL, budget=b)


def test_transport_closes_injected_session_and_every_response():
    response = json_response(listing_fixture("AAPL", True))
    session = FakeSession([response])
    transport = LifecycleProviderCensusTransport(session=session)

    transport.fetch_massive_listing(
        "AAPL", expected_active=True, api_key="secret", budget=budget()
    )
    transport.close()

    assert response.closed is True
    assert session.closed is True


def test_shadow_transport_is_not_imported_by_scheduler():
    source = Path("src/service/security_lifecycle_automation_scheduler.py").read_text()
    assert "lifecycle_provider_census_transport" not in source
