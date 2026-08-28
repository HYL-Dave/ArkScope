from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from data_sources.listing_authority_transport import (
    MASSIVE_TICKERS_URL,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    ListingHttpPayload,
    ListingRequestBudget,
    ListingTransportFailure,
)


_AT = "2026-08-28T22:00:00Z"
_FIXTURES = Path(__file__).parent / "fixtures" / "listing_authority"


def _fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _context(ticker: str = "AAPL"):
    from src.security_lifecycle_sec_evidence import IdentityContext

    return IdentityContext(
        case_id="slc_listing",
        cik="0000320193",
        issuer_name="Fixture Issuer",
        current_ticker=ticker,
        ticker_aliases=(ticker,),
        ibkr_conids=(),
        filing_date="2026-08-28",
        accession="0000320193-26-000001",
        filing_form="8-K",
        filing_items=("8.01",),
        event_kinds=("symbol_change",),
        primary_start="2026-07-29",
        primary_end="2026-10-12",
        widened_start="2026-04-30",
        widened_end="2026-12-26",
    )


def _massive_url(ticker: str, active: bool, market: str) -> str:
    state = "true" if active else "false"
    return (
        f"{MASSIVE_TICKERS_URL}?ticker={ticker}&active={state}"
        f"&market={market}&limit=2"
    )


def _massive_record(
    body: bytes,
    ticker: str,
    *,
    expected_active: bool,
    market: str = "stocks",
):
    from src.security_lifecycle_listing_evidence import parse_massive_ticker

    return parse_massive_ticker(
        body,
        ticker,
        expected_active=expected_active,
        market=market,
        retrieved_at=_AT,
        source_url=_massive_url(ticker, expected_active, market),
    )


def _assert_failure(code: str, call) -> None:
    from src.security_lifecycle_listing_evidence import ListingEvidenceFailure

    with pytest.raises(ListingEvidenceFailure) as captured:
        call()
    assert captured.value.code == code
    assert str(captured.value) == code
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_nasdaq_parser_preserves_matching_component_and_per_file_hashes() -> None:
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    nasdaq = _fixture("nasdaqlisted.txt")
    other = _fixture("otherlisted.txt")
    snapshot = parse_nasdaq_directories(
        nasdaq_bytes=nasdaq,
        other_bytes=other,
        retrieved_at=_AT,
    )

    assert [
        (row.directory, row.listing_status, row.primary_exchange)
        for row in snapshot.lookup("aapl")
    ] == [("nasdaq_listed", "active", "XNAS")]
    assert [
        (row.directory, row.listing_status, row.primary_exchange)
        for row in snapshot.lookup("IBM")
    ] == [("other_listed", "active", "XNYS")]
    assert [
        (row.directory, row.listing_status, row.source_document_sha256)
        for row in snapshot.lookup("DOESNOTEXIST")
    ] == [
        ("nasdaq_listed", "not_found", hashlib.sha256(nasdaq).hexdigest()),
        ("other_listed", "not_found", hashlib.sha256(other).hexdigest()),
    ]
    assert snapshot.lookup("DOESNOTEXIST")[0].source_url == NASDAQ_LISTED_URL
    assert snapshot.lookup("DOESNOTEXIST")[1].source_url == OTHER_LISTED_URL


@pytest.mark.parametrize(
    ("name", "mutate", "code"),
    (
        (
            "missing_footer",
            lambda body: body.split(b"File Creation Time:", 1)[0],
            "listing_directory_schema_mismatch",
        ),
        (
            "stale_file",
            lambda body: body.replace(b"08282026|120000", b"08272026|120000"),
            "listing_directory_stale",
        ),
        (
            "changed_header",
            lambda body: body.replace(b"Symbol|Security Name", b"Ticker|Security Name"),
            "listing_directory_schema_mismatch",
        ),
        (
            "invalid_ticker",
            lambda body: body.replace(b"AAPL|", b"BAD TICKER|", 1),
            "listing_directory_schema_mismatch",
        ),
        (
            "duplicate_symbol",
            lambda body: body.replace(
                b"File Creation Time:",
                b"AAPL|Apple Duplicate|Q|N|N|100|N|N\nFile Creation Time:",
            ),
            "listing_directory_schema_mismatch",
        ),
        (
            "trailing_data",
            lambda body: body + b"UNPARSED|DATA\n",
            "listing_directory_schema_mismatch",
        ),
    ),
)
def test_nasdaq_parser_rejects_incomplete_stale_or_drifted_files(
    name, mutate, code
) -> None:
    del name
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    _assert_failure(
        code,
        lambda: parse_nasdaq_directories(
            nasdaq_bytes=mutate(_fixture("nasdaqlisted.txt")),
            other_bytes=_fixture("otherlisted.txt"),
            retrieved_at=_AT,
        ),
    )


def test_nasdaq_parser_rejects_unknown_exchange_and_cross_file_duplicates() -> None:
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    unknown_exchange = _fixture("otherlisted.txt").replace(b"|N|IBM|", b"|?|IBM|")
    _assert_failure(
        "listing_directory_schema_mismatch",
        lambda: parse_nasdaq_directories(
            nasdaq_bytes=_fixture("nasdaqlisted.txt"),
            other_bytes=unknown_exchange,
            retrieved_at=_AT,
        ),
    )

    duplicate = _fixture("otherlisted.txt").replace(b"IBM|", b"AAPL|", 1)
    _assert_failure(
        "listing_directory_schema_mismatch",
        lambda: parse_nasdaq_directories(
            nasdaq_bytes=_fixture("nasdaqlisted.txt"),
            other_bytes=duplicate,
            retrieved_at=_AT,
        ),
    )


def test_nasdaq_parser_enforces_a_bounded_row_count() -> None:
    from src.security_lifecycle_listing_evidence import (
        MAX_NASDAQ_DIRECTORY_ROWS,
        parse_nasdaq_directories,
    )

    header = _fixture("nasdaqlisted.txt").splitlines()[0]
    rows = [
        f"T{index:06d}|Fixture {index}|Q|N|N|100|N|N".encode("ascii")
        for index in range(MAX_NASDAQ_DIRECTORY_ROWS + 1)
    ]
    oversized = b"\n".join([header, *rows, b"File Creation Time: 08282026|120000", b""])

    _assert_failure(
        "listing_directory_schema_mismatch",
        lambda: parse_nasdaq_directories(
            nasdaq_bytes=oversized,
            other_bytes=_fixture("otherlisted.txt"),
            retrieved_at=_AT,
        ),
    )


def test_nasdaq_parser_maps_all_approved_other_listed_exchanges() -> None:
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    other = b"\n".join(
        (
            _fixture("otherlisted.txt").splitlines()[0],
            b"AMX|American fixture|A|AMX|N|100|N|AMX",
            b"NYS|NYSE fixture|N|NYS|N|100|N|NYS",
            b"ARC|Arca fixture|P|ARC|N|100|N|ARC",
            b"BZX|Cboe fixture|Z|BZX|N|100|N|BZX",
            b"IEX|IEX fixture|V|IEX|N|100|N|IEX",
            b"File Creation Time: 08282026|120000",
            b"",
        )
    )
    snapshot = parse_nasdaq_directories(
        nasdaq_bytes=_fixture("nasdaqlisted.txt"),
        other_bytes=other,
        retrieved_at=_AT,
    )

    assert {
        ticker: snapshot.lookup(ticker)[0].primary_exchange
        for ticker in ("AMX", "NYS", "ARC", "BZX", "IEX")
    } == {
        "AMX": "XASE",
        "NYS": "XNYS",
        "ARC": "ARCX",
        "BZX": "BATS",
        "IEX": "IEXG",
    }


def test_nasdaq_parser_accepts_valid_status_codes_and_excludes_test_symbols() -> None:
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    header = _fixture("nasdaqlisted.txt").splitlines()[0]
    nasdaq = b"\n".join(
        (
            header,
            b"STATC|Combined status C|Q|N|C|100|N|N",
            b"STATJ|Combined status J|G|N|J|100|N|N",
            b"STATK|Combined status K|S|N|K|100|N|N",
            b"TESTQ|Nasdaq test symbol|Q|Y|N|100|N|N",
            b"File Creation Time: 08282026|120000",
            b"",
        )
    )
    other_header = _fixture("otherlisted.txt").splitlines()[0]
    other = b"\n".join(
        (
            other_header,
            b"TESTN|NYSE test symbol|N|TESTN|N|100|Y|TESTN",
            b"File Creation Time: 08282026|120000",
            b"",
        )
    )

    snapshot = parse_nasdaq_directories(
        nasdaq_bytes=nasdaq,
        other_bytes=other,
        retrieved_at=_AT,
    )

    statuses = [
        snapshot.lookup(ticker)[0].listing_status
        for ticker in ("STATC", "STATJ", "STATK")
    ]
    assert statuses == [
        "active",
        "active",
        "active",
    ]
    assert [row.listing_status for row in snapshot.lookup("TESTQ")] == [
        "not_found",
        "not_found",
    ]
    assert [row.listing_status for row in snapshot.lookup("TESTN")] == [
        "not_found",
        "not_found",
    ]


def test_nasdaq_parser_rejects_a_file_dated_after_the_exchange_local_day() -> None:
    from src.security_lifecycle_listing_evidence import parse_nasdaq_directories

    _assert_failure(
        "listing_directory_stale",
        lambda: parse_nasdaq_directories(
            nasdaq_bytes=_fixture("nasdaqlisted.txt"),
            other_bytes=_fixture("otherlisted.txt"),
            retrieved_at="2026-08-28T02:00:00Z",
        ),
    )


def test_massive_parser_requires_explicit_intent_and_normalizes_inactive_date() -> None:
    record = _massive_record(
        _fixture("massive-inactive.json"), "OLD", expected_active=False
    )

    assert record.listing_status == "inactive"
    assert record.delisted_utc == "2026-08-01"
    assert record.source_as_of == _AT
    assert record.provider_last_updated_utc == "2026-08-28T12:00:00Z"
    assert (
        record.source_document_sha256
        == hashlib.sha256(_fixture("massive-inactive.json")).hexdigest()
    )


def test_massive_parser_returns_one_not_found_record_for_an_empty_exact_lookup() -> None:
    body = b'{"results":[],"status":"OK","request_id":"fixture-empty"}'
    record = _massive_record(body, "MISS", expected_active=True)

    assert record.ticker == "MISS"
    assert record.listing_status == "not_found"
    assert record.expected_active is True
    assert record.snapshot_complete is True
    assert record.source_document_sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (
            lambda payload: payload["results"][0].pop("delisted_utc"),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__(
                "delisted_utc", "2026-08-29T00:00:00Z"
            ),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__("ticker", "OTHER"),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload.__setitem__("next_url", "https://secret.example"),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__("cik", "not-a-cik"),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__(
                "last_updated_utc", "secret-provider-timestamp"
            ),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__(
                "composite_figi", "INVALID"
            ),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__("active", True),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"][0].__setitem__("market", "otc"),
            "listing_status_unresolved",
        ),
        (
            lambda payload: payload["results"].append(dict(payload["results"][0])),
            "listing_status_unresolved",
        ),
    ),
)
def test_massive_parser_rejects_ambiguous_or_contradictory_inactive_rows(
    mutation, code
) -> None:
    payload = json.loads(_fixture("massive-inactive.json"))
    mutation(payload)
    body = json.dumps(payload, separators=(",", ":")).encode()

    _assert_failure(
        code,
        lambda: _massive_record(body, "OLD", expected_active=False),
    )


@pytest.mark.parametrize(
    "body",
    (
        b"not-json secret-provider-surplus",
        b"[]",
        b'{"status":"ERROR","results":[]}',
        b'{"status":"OK","results":"not-a-list"}',
    ),
)
def test_massive_parser_closes_malformed_payloads_without_retaining_content(
    body,
) -> None:
    from src.security_lifecycle_listing_evidence import ListingEvidenceFailure

    with pytest.raises(ListingEvidenceFailure) as captured:
        _massive_record(body, "OLD", expected_active=False)
    assert captured.value.code == "listing_status_unresolved"
    assert "secret-provider-surplus" not in repr(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


class FakeListingTransport:
    def __init__(self, payloads: dict[object, ListingHttpPayload | Exception]) -> None:
        self.payloads = dict(payloads)
        self.calls: list[object] = []
        self.closed = False

    def fetch_nasdaq(self, source_url: str, *, budget: ListingRequestBudget):
        self.calls.append(source_url)
        budget.reserve_nasdaq_request(source_url)
        value = self.payloads[source_url]
        if isinstance(value, Exception):
            raise value
        budget.record_nasdaq_body(len(value.body))
        return value

    def fetch_massive_ticker(
        self,
        ticker: str,
        *,
        expected_active: bool,
        market: str,
        api_key: str,
        budget: ListingRequestBudget,
    ):
        del api_key
        identity = (ticker, expected_active, market)
        self.calls.append(identity)
        budget.reserve_massive_request(identity)
        value = self.payloads[identity]
        if isinstance(value, Exception):
            raise value
        budget.record_massive_body(len(value.body))
        return value

    def diagnostics(self, budget: ListingRequestBudget):
        return budget.diagnostics()

    def close(self) -> None:
        self.closed = True


class SurplusDiagnosticTransport(FakeListingTransport):
    @staticmethod
    def diagnostics(_budget: ListingRequestBudget):
        return {"api_key": "secret-provider-surplus"}


def _payload(source_url: str, body: bytes, content_type: str) -> ListingHttpPayload:
    return ListingHttpPayload(
        source_url=source_url,
        retrieved_at=_AT,
        status_code=200,
        content_type=content_type,
        body=body,
    )


def _session_payloads() -> dict[object, ListingHttpPayload | Exception]:
    empty_stocks = b'{"results":[],"status":"OK","request_id":"empty-stocks"}'
    return {
        NASDAQ_LISTED_URL: _payload(
            NASDAQ_LISTED_URL, _fixture("nasdaqlisted.txt"), "text/plain"
        ),
        OTHER_LISTED_URL: _payload(
            OTHER_LISTED_URL, _fixture("otherlisted.txt"), "text/plain"
        ),
        ("OTCM", True, "stocks"): _payload(
            _massive_url("OTCM", True, "stocks"),
            empty_stocks,
            "application/json",
        ),
        ("OTCM", True, "otc"): _payload(
            _massive_url("OTCM", True, "otc"),
            _fixture("massive-otc.json"),
            "application/json",
        ),
        ("OLD", False, "stocks"): _payload(
            _massive_url("OLD", False, "stocks"),
            _fixture("massive-inactive.json"),
            "application/json",
        ),
    }


def test_listing_session_is_lazy_reuses_snapshot_and_memoizes_massive_lookup() -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = FakeListingTransport(_session_payloads())
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key="fixture-key",
    )
    assert transport.calls == []

    first = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("OTCM",),
        require_explicit_inactive=False,
    )
    second = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("OTCM",),
        require_explicit_inactive=False,
    )

    assert transport.calls == [
        NASDAQ_LISTED_URL,
        OTHER_LISTED_URL,
        ("OTCM", True, "stocks"),
        ("OTCM", True, "otc"),
    ]
    assert first.evidence == second.evidence
    assert first.diagnostics == {
        "massive_body_bytes": 256,
        "massive_request_count": 2,
        "nasdaq_body_bytes": len(_fixture("nasdaqlisted.txt"))
        + len(_fixture("otherlisted.txt")),
        "nasdaq_request_count": 2,
    }
    assert [
        (row.adapter, json.loads(row.excerpt)["listing_status"])
        for row in first.evidence
    ] == [
        ("nasdaq_symbol_directory", "not_found"),
        ("nasdaq_symbol_directory", "not_found"),
        ("massive_reference", "not_found"),
        ("massive_reference", "active"),
    ]
    assert {fact.fact_type for fact in first.facts} == {
        "destination_venue",
        "issuer_cik",
        "security_class",
        "successor_ticker",
    }

    session.close()
    assert transport.closed is True


def test_listing_evidence_uses_exact_canonical_excerpt_bytes_and_cited_spans() -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = FakeListingTransport(_session_payloads())
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key=None,
    )
    result = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("AAPL",),
        require_explicit_inactive=False,
    )

    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.excerpt == (
        '{"authority":"nasdaq_trader","delisted_utc":null,'
        '"directory":"nasdaq_listed","issuer_cik":null,'
        '"listing_status":"active","market":"stocks",'
        '"primary_exchange":"XNAS","provider_last_updated_utc":null,'
        '"security_type":null,"source_as_of":"2026-08-28",'
        '"ticker":"AAPL"}'
    )
    encoded = evidence.excerpt.encode()
    assert evidence.content_sha256 == hashlib.sha256(encoded).hexdigest()
    assert (
        evidence.source_document_sha256
        == hashlib.sha256(_fixture("nasdaqlisted.txt")).hexdigest()
    )
    assert evidence.source_locator == {
        "adapter_version": "listing-authority-v1",
        "authority": "nasdaq_trader",
        "candidate_ticker": "AAPL",
        "composite_figi": None,
        "delisted_utc": None,
        "directory": "nasdaq_listed",
        "issuer_cik": None,
        "listing_status": "active",
        "market": "stocks",
        "primary_exchange": "XNAS",
        "provider_last_updated_utc": None,
        "security_type": None,
        "snapshot_complete": True,
        "source_as_of": "2026-08-28",
        "source_document_sha256": evidence.source_document_sha256,
    }
    assert evidence.source_published_at == "2026-08-28T12:00:00"
    assert {fact.fact_type: fact.normalized_value for fact in result.facts} == {
        "source_ticker": "AAPL",
        "source_venue": "NASDAQ",
    }
    for fact in result.facts:
        assert (fact.source_span_start, fact.source_span_end) == (0, len(encoded))
        assert fact.cited_text_sha256 == evidence.content_sha256


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        (
            ListingTransportFailure("massive_api_key_missing"),
            "massive_credential_missing",
        ),
        (ListingTransportFailure("massive_unauthorized"), "massive_access_denied"),
        (ListingTransportFailure("massive_rate_limited"), "massive_rate_limited"),
        (
            ListingTransportFailure("massive_transport_unavailable"),
            "massive_reference_unavailable",
        ),
    ),
)
def test_listing_session_maps_massive_failures_to_closed_secret_free_blockers(
    failure, expected
) -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    payloads = _session_payloads()
    payloads[("OLD", False, "stocks")] = failure
    transport = FakeListingTransport(payloads)
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key="fixture-key",
    )

    result = session.lookup(
        context=_context("OLD"),
        candidate_tickers=("OLD",),
        require_explicit_inactive=True,
    )

    assert result.blockers == (expected,)
    assert all(type(value) is int for value in result.diagnostics.values())
    assert "fixture-key" not in repr(result)


def test_listing_session_requires_massive_credentials_only_when_fallback_is_needed() -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = FakeListingTransport(_session_payloads())
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key=None,
    )

    nasdaq_result = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("AAPL",),
        require_explicit_inactive=False,
    )
    fallback_result = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("OTCM",),
        require_explicit_inactive=False,
    )

    assert nasdaq_result.blockers == ()
    assert fallback_result.blockers == ("massive_credential_missing",)
    assert transport.calls == [NASDAQ_LISTED_URL, OTHER_LISTED_URL]


def test_listing_session_applies_explicit_inactive_intent_to_the_queried_candidate() -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = FakeListingTransport(_session_payloads())
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key="fixture-key",
    )

    result = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("OLD",),
        require_explicit_inactive=True,
    )

    assert ("OLD", False, "stocks") in transport.calls
    assert [
        json.loads(row.excerpt)["listing_status"]
        for row in result.evidence
        if row.adapter == "massive_reference"
    ] == ["inactive"]


def test_listing_session_diagnostics_are_derived_only_from_the_bounded_budget() -> None:
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = SurplusDiagnosticTransport(_session_payloads())
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_AT,
        massive_api_key=None,
    )

    result = session.lookup(
        context=_context("AAPL"),
        candidate_tickers=("AAPL",),
        require_explicit_inactive=False,
    )

    assert result.diagnostics == {
        "massive_body_bytes": 0,
        "massive_request_count": 0,
        "nasdaq_body_bytes": len(_fixture("nasdaqlisted.txt"))
        + len(_fixture("otherlisted.txt")),
        "nasdaq_request_count": 2,
    }
    assert "secret-provider-surplus" not in repr(result)
