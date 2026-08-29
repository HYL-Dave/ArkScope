"""Strict normalization for current listing-authority evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from data_sources.listing_authority_transport import (
    MASSIVE_TICKERS_URL,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    ListingAuthorityTransport,
    ListingRequestBudget,
    ListingTransportFailure,
)
from src.market_sessions import latest_completed_market_date, normalize_now_et
from src.security_lifecycle_schema import AUTOMATION_BLOCKER_CODES
from src.security_lifecycle_sec_evidence import IdentityContext


LISTING_STATUSES = frozenset({"active", "inactive", "not_found", "unverified"})
LISTING_BLOCKER_CODES = frozenset(
    {
        "listing_directory_unavailable",
        "listing_directory_schema_mismatch",
        "listing_directory_stale",
        "listing_status_unresolved",
        "listing_authority_conflict",
        "massive_credential_missing",
        "massive_access_denied",
        "massive_rate_limited",
        "massive_reference_unavailable",
    }
)
if not LISTING_BLOCKER_CODES <= AUTOMATION_BLOCKER_CODES:  # pragma: no cover
    raise RuntimeError("listing_blocker_schema_mismatch")

MAX_NASDAQ_DIRECTORY_ROWS = 100_000

_ADAPTER_VERSION = "listing-authority-v1"
_RULE_VERSION = "1"
_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")
_CIK = re.compile(r"^\d{10}$")
_FIGI = re.compile(r"^BBG[A-Z0-9]{9}$")
_EXCHANGE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_SECURITY_TYPE = re.compile(r"^[A-Z][A-Z0-9_-]{0,19}$")
_RFC3339_TIMESTAMP = re.compile(
    r"^(?P<second>\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d{1,9}))?"
    r"(?P<timezone>[Zz]|[+-]\d{2}:\d{2})$"
)
_FOOTER = re.compile(r"^File Creation Time: (\d{8})\|(\d{6})$")
_NASDAQ_HEADER = (
    "Symbol",
    "Security Name",
    "Market Category",
    "Test Issue",
    "Financial Status",
    "Round Lot Size",
    "ETF",
    "NextShares",
)
_OTHER_HEADER = (
    "ACT Symbol",
    "Security Name",
    "Exchange",
    "CQS Symbol",
    "ETF",
    "Round Lot Size",
    "Test Issue",
    "NASDAQ Symbol",
)
_NASDAQ_MARKET_CATEGORIES = frozenset({"Q", "G", "S"})
_NASDAQ_FINANCIAL_STATUSES = frozenset({"C", "D", "E", "G", "H", "J", "K", "N", "Q"})
_OTHER_EXCHANGES = {
    "A": "XASE",
    "N": "XNYS",
    "P": "ARCX",
    "Z": "BATS",
    "V": "IEXG",
}
_MASSIVE_MARKETS = frozenset({"stocks", "otc"})
_FACT_VENUES = {
    "XNAS": "NASDAQ",
    "NASDAQ": "NASDAQ",
    "XNYS": "NYSE",
    "NYSE": "NYSE",
    "XASE": "NYSE AMERICAN",
    "ARCX": "NYSE ARCA",
    "BATS": "CBOE BZX",
    "IEXG": "IEX",
    "OTC": "OTC",
}
_FACT_SECURITY_CLASSES = {
    "CS": "common_stock",
    "ETF": "exchange_traded_fund",
}


class ListingEvidenceFailure(ValueError):
    """Closed parser failure safe to persist as a listing blocker."""

    def __init__(self, code: str) -> None:
        if code not in LISTING_BLOCKER_CODES:
            raise ValueError("listing_failure_code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ListingRecord:
    authority: str
    adapter: str
    directory: str | None
    ticker: str
    listing_status: str
    expected_active: bool
    market: str
    primary_exchange: str | None
    security_type: str | None
    issuer_cik: str | None
    composite_figi: str | None
    delisted_utc: str | None
    source_as_of: str
    provider_last_updated_utc: str | None
    snapshot_complete: bool
    source_url: str
    source_document_sha256: str
    retrieved_at: str
    file_created_at: str | None = None


@dataclass(frozen=True)
class ListingEvidence:
    evidence_id: str
    source_family: str
    adapter: str
    kind: str
    source_url: str
    title: str
    publisher: str
    domain: str
    source_published_at: str | None
    retrieved_at: str
    excerpt: str
    content_sha256: str
    source_document_sha256: str
    source_locator: Mapping[str, Any]
    evidence_dedupe_key: str


@dataclass(frozen=True)
class ListingFact:
    evidence_id: str
    fact_type: str
    normalized_value: Any
    source_span_start: int
    source_span_end: int
    cited_text_sha256: str
    extractor_rule_id: str
    extractor_rule_version: str


@dataclass(frozen=True)
class ListingEvidenceResult:
    evidence: tuple[ListingEvidence, ...]
    facts: tuple[ListingFact, ...]
    blockers: tuple[str, ...]
    diagnostics: Mapping[str, int]


@dataclass(frozen=True)
class _NasdaqComponent:
    directory: str
    source_url: str
    source_document_sha256: str
    source_as_of: str
    file_created_at: str
    retrieved_at: str
    rows: Mapping[str, tuple[str | None, str | None]]
    symbols: frozenset[str]

    def record(self, ticker: str) -> ListingRecord:
        row = self.rows.get(ticker)
        status = "active" if row is not None else "not_found"
        primary_exchange, security_type = row or (None, None)
        return ListingRecord(
            authority="nasdaq_trader",
            adapter="nasdaq_symbol_directory",
            directory=self.directory,
            ticker=ticker,
            listing_status=status,
            expected_active=True,
            market="stocks",
            primary_exchange=primary_exchange,
            security_type=security_type,
            issuer_cik=None,
            composite_figi=None,
            delisted_utc=None,
            source_as_of=self.source_as_of,
            provider_last_updated_utc=None,
            snapshot_complete=True,
            source_url=self.source_url,
            source_document_sha256=self.source_document_sha256,
            retrieved_at=self.retrieved_at,
            file_created_at=self.file_created_at,
        )


@dataclass(frozen=True)
class NasdaqDirectorySnapshot:
    nasdaq_listed: _NasdaqComponent
    other_listed: _NasdaqComponent

    def lookup(self, ticker: str) -> tuple[ListingRecord, ...]:
        normalized = _normalized_ticker(ticker)
        for component in (self.nasdaq_listed, self.other_listed):
            if normalized in component.rows:
                return (component.record(normalized),)
        return (
            self.nasdaq_listed.record(normalized),
            self.other_listed.record(normalized),
        )


def _timestamp(name: str, value: object) -> tuple[str, datetime]:
    del name
    if not isinstance(value, str) or not value or len(value) > 64 or "\0" in value:
        raise ListingEvidenceFailure("listing_status_unresolved")
    match = _RFC3339_TIMESTAMP.fullmatch(value)
    if match is None:
        raise ListingEvidenceFailure("listing_status_unresolved")
    fraction = match.group("fraction")
    fractional = "" if fraction is None else f".{fraction[:6]}"
    zone = match.group("timezone")
    parseable = (
        f"{match.group('second').upper()}{fractional}"
        f"{'+00:00' if zone.lower() == 'z' else zone}"
    )
    parsed: datetime | None = None
    invalid = False
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        invalid = True
    if invalid or parsed is None:
        raise ListingEvidenceFailure("listing_status_unresolved") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ListingEvidenceFailure("listing_status_unresolved")
    normalized = (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return normalized, parsed.astimezone(timezone.utc)


def _normalized_ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ListingEvidenceFailure("listing_status_unresolved")
    normalized = value.strip().upper()
    if _TICKER.fullmatch(normalized) is None:
        raise ListingEvidenceFailure("listing_status_unresolved")
    return normalized


def _nasdaq_failure() -> ListingEvidenceFailure:
    return ListingEvidenceFailure("listing_directory_schema_mismatch")


def _decode_nasdaq(body: object) -> list[str]:
    if not isinstance(body, bytes) or not body or b"\0" in body:
        raise _nasdaq_failure()
    invalid = False
    text = ""
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError:
        invalid = True
    if invalid:
        raise _nasdaq_failure() from None
    lines = text.splitlines()
    if len(lines) < 2:
        raise _nasdaq_failure()
    return lines


def _file_creation(footer: str, *, retrieved_at: str) -> tuple[str, str, str]:
    match = _FOOTER.fullmatch(footer)
    if match is None:
        raise _nasdaq_failure()
    created: datetime | None = None
    invalid = False
    try:
        created = datetime.strptime("".join(match.groups()), "%m%d%Y%H%M%S")
    except ValueError:
        invalid = True
    if invalid or created is None:
        raise _nasdaq_failure() from None
    normalized_retrieved_at, retrieved = _timestamp("retrieved_at", retrieved_at)
    latest = latest_completed_market_date(retrieved)
    if (
        latest is None
        or created.date() < latest
        or created.date() > normalize_now_et(retrieved).date()
    ):
        raise ListingEvidenceFailure("listing_directory_stale")
    return created.date().isoformat(), created.isoformat(), normalized_retrieved_at


def _required_directory_text(value: str, *, maximum: int) -> str:
    normalized = value.strip()
    if (
        not normalized
        or "\0" in normalized
        or len(normalized.encode("utf-8")) > maximum
    ):
        raise _nasdaq_failure()
    return normalized


def _parse_nasdaq_component(
    *,
    body: bytes,
    directory: str,
    source_url: str,
    retrieved_at: str,
) -> _NasdaqComponent:
    lines = _decode_nasdaq(body)
    expected_header = _NASDAQ_HEADER if directory == "nasdaq_listed" else _OTHER_HEADER
    if tuple(lines[0].split("|")) != expected_header:
        raise _nasdaq_failure()
    source_rows = lines[1:-1]
    if not source_rows or len(source_rows) > MAX_NASDAQ_DIRECTORY_ROWS:
        raise _nasdaq_failure()
    source_as_of, file_created_at, normalized_retrieved_at = _file_creation(
        lines[-1], retrieved_at=retrieved_at
    )

    parsed_rows: dict[str, tuple[str | None, str | None]] = {}
    symbols: set[str] = set()
    for line in source_rows:
        fields = line.split("|")
        if len(fields) != len(expected_header):
            raise _nasdaq_failure()
        invalid_ticker = False
        ticker = ""
        try:
            ticker = _normalized_ticker(fields[0])
        except ListingEvidenceFailure:
            invalid_ticker = True
        if invalid_ticker:
            raise _nasdaq_failure() from None
        if ticker in symbols:
            raise _nasdaq_failure()
        symbols.add(ticker)
        _required_directory_text(fields[1], maximum=500)
        if directory == "nasdaq_listed":
            (
                market_category,
                test_issue,
                financial_status,
                round_lot,
                etf,
                next_shares,
            ) = fields[2:]
            if (
                market_category not in _NASDAQ_MARKET_CATEGORIES
                or test_issue not in {"Y", "N"}
                or financial_status not in _NASDAQ_FINANCIAL_STATUSES
                or not round_lot.isdigit()
                or int(round_lot) <= 0
                or etf not in {"Y", "N"}
                or next_shares not in {"Y", "N"}
            ):
                raise _nasdaq_failure()
            if test_issue == "N":
                security_type = "ETF" if etf == "Y" else None
                parsed_rows[ticker] = ("XNAS", security_type)
        else:
            exchange, cqs_symbol, etf, round_lot, test_issue, nasdaq_symbol = fields[2:]
            if (
                exchange not in _OTHER_EXCHANGES
                or not cqs_symbol.strip()
                or not nasdaq_symbol.strip()
                or etf not in {"Y", "N"}
                or not round_lot.isdigit()
                or int(round_lot) <= 0
                or test_issue not in {"Y", "N"}
            ):
                raise _nasdaq_failure()
            if test_issue == "N":
                security_type = "ETF" if etf == "Y" else None
                parsed_rows[ticker] = (_OTHER_EXCHANGES[exchange], security_type)

    return _NasdaqComponent(
        directory=directory,
        source_url=source_url,
        source_document_sha256=hashlib.sha256(body).hexdigest(),
        source_as_of=source_as_of,
        file_created_at=file_created_at,
        retrieved_at=normalized_retrieved_at,
        rows=MappingProxyType(parsed_rows),
        symbols=frozenset(symbols),
    )


def _parse_nasdaq_snapshot(
    *,
    nasdaq_bytes: bytes,
    nasdaq_retrieved_at: str,
    other_bytes: bytes,
    other_retrieved_at: str,
) -> NasdaqDirectorySnapshot:
    nasdaq = _parse_nasdaq_component(
        body=nasdaq_bytes,
        directory="nasdaq_listed",
        source_url=NASDAQ_LISTED_URL,
        retrieved_at=nasdaq_retrieved_at,
    )
    other = _parse_nasdaq_component(
        body=other_bytes,
        directory="other_listed",
        source_url=OTHER_LISTED_URL,
        retrieved_at=other_retrieved_at,
    )
    if nasdaq.symbols & other.symbols:
        raise _nasdaq_failure()
    return NasdaqDirectorySnapshot(nasdaq, other)


def parse_nasdaq_directories(
    *, nasdaq_bytes: bytes, other_bytes: bytes, retrieved_at: str
) -> NasdaqDirectorySnapshot:
    """Parse both complete Nasdaq files into one immutable lookup snapshot."""

    return _parse_nasdaq_snapshot(
        nasdaq_bytes=nasdaq_bytes,
        nasdaq_retrieved_at=retrieved_at,
        other_bytes=other_bytes,
        other_retrieved_at=retrieved_at,
    )


def _massive_failure() -> ListingEvidenceFailure:
    return ListingEvidenceFailure("listing_status_unresolved")


def _massive_source_url(ticker: str, expected_active: bool, market: str) -> str:
    active = "true" if expected_active else "false"
    return (
        f"{MASSIVE_TICKERS_URL}?ticker={ticker}&active={active}"
        f"&market={market}&limit=2"
    )


def _optional_timestamp(value: object) -> str | None:
    if value is None:
        return None
    return _timestamp("provider_timestamp", value)[0]


def _delisted_date(value: object, *, lookup_date: date) -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or "\0" in value:
        raise _massive_failure()
    parsed_date: date | None = None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        pass
    if parsed_date is None:
        invalid = False
        try:
            parsed_date = _timestamp("delisted_utc", value)[1].date()
        except ListingEvidenceFailure:
            invalid = True
        if invalid or parsed_date is None:
            raise _massive_failure() from None
    if parsed_date > lookup_date:
        raise _massive_failure()
    return parsed_date.isoformat()


def parse_massive_ticker(
    body: bytes,
    ticker: str,
    *,
    expected_active: bool,
    market: str,
    retrieved_at: str,
    source_url: str,
) -> ListingRecord:
    """Parse one exact Massive lookup with explicit active-state intent."""

    normalized_ticker = _normalized_ticker(ticker)
    if type(expected_active) is not bool or market not in _MASSIVE_MARKETS:
        raise _massive_failure()
    canonical_url = _massive_source_url(normalized_ticker, expected_active, market)
    if source_url != canonical_url or not isinstance(body, bytes) or not body:
        raise _massive_failure()
    normalized_retrieved_at, retrieved = _timestamp("retrieved_at", retrieved_at)

    payload: object = None
    invalid_json = False
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid_json = True
    if invalid_json:
        raise _massive_failure() from None
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "OK"
        or "next_url" in payload
        or not isinstance(payload.get("results"), list)
        or len(payload["results"]) > 1
    ):
        raise _massive_failure()

    document_sha256 = hashlib.sha256(body).hexdigest()
    results = payload["results"]
    if not results:
        return ListingRecord(
            authority="massive",
            adapter="massive_reference",
            directory=None,
            ticker=normalized_ticker,
            listing_status="not_found",
            expected_active=expected_active,
            market=market,
            primary_exchange=None,
            security_type=None,
            issuer_cik=None,
            composite_figi=None,
            delisted_utc=None,
            source_as_of=normalized_retrieved_at,
            provider_last_updated_utc=None,
            snapshot_complete=True,
            source_url=canonical_url,
            source_document_sha256=document_sha256,
            retrieved_at=normalized_retrieved_at,
        )

    row = results[0]
    if not isinstance(row, dict):
        raise _massive_failure()
    returned_ticker = row.get("ticker")
    active = row.get("active")
    returned_market = row.get("market")
    if (
        not isinstance(returned_ticker, str)
        or returned_ticker.strip().upper() != normalized_ticker
        or type(active) is not bool
        or active is not expected_active
        or returned_market != market
    ):
        raise _massive_failure()

    primary_exchange = row.get("primary_exchange")
    if primary_exchange is not None and (
        not isinstance(primary_exchange, str)
        or _EXCHANGE.fullmatch(primary_exchange) is None
    ):
        raise _massive_failure()
    if expected_active and primary_exchange is None:
        raise _massive_failure()
    security_type = row.get("type")
    if security_type is not None and (
        not isinstance(security_type, str)
        or _SECURITY_TYPE.fullmatch(security_type) is None
    ):
        raise _massive_failure()
    issuer_cik = row.get("cik")
    if issuer_cik is not None and (
        not isinstance(issuer_cik, str) or _CIK.fullmatch(issuer_cik) is None
    ):
        raise _massive_failure()
    composite_figi = row.get("composite_figi")
    if composite_figi is not None and (
        not isinstance(composite_figi, str) or _FIGI.fullmatch(composite_figi) is None
    ):
        raise _massive_failure()
    provider_last_updated = _optional_timestamp(row.get("last_updated_utc"))

    delisted_value = row.get("delisted_utc")
    if expected_active:
        if delisted_value is not None:
            raise _massive_failure()
        status = "active"
        delisted_utc = None
    else:
        if delisted_value is None:
            raise _massive_failure()
        status = "inactive"
        delisted_utc = _delisted_date(delisted_value, lookup_date=retrieved.date())

    return ListingRecord(
        authority="massive",
        adapter="massive_reference",
        directory=None,
        ticker=normalized_ticker,
        listing_status=status,
        expected_active=expected_active,
        market=market,
        primary_exchange=primary_exchange,
        security_type=security_type,
        issuer_cik=issuer_cik,
        composite_figi=composite_figi,
        delisted_utc=delisted_utc,
        source_as_of=normalized_retrieved_at,
        provider_last_updated_utc=provider_last_updated,
        snapshot_complete=True,
        source_url=canonical_url,
        source_document_sha256=document_sha256,
        retrieved_at=normalized_retrieved_at,
    )


def _canonical_excerpt(record: ListingRecord) -> str:
    return json.dumps(
        {
            "authority": record.authority,
            "directory": record.directory,
            "ticker": record.ticker,
            "listing_status": record.listing_status,
            "market": record.market,
            "primary_exchange": record.primary_exchange,
            "security_type": record.security_type,
            "issuer_cik": record.issuer_cik,
            "delisted_utc": record.delisted_utc,
            "source_as_of": record.source_as_of,
            "provider_last_updated_utc": record.provider_last_updated_utc,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _evidence(record: ListingRecord) -> ListingEvidence:
    excerpt = _canonical_excerpt(record)
    content_sha256 = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    identity = hashlib.sha256(
        (
            f"{record.adapter}\0{record.source_url}\0{record.ticker}\0"
            f"{record.listing_status}\0{record.source_document_sha256}\0{content_sha256}"
        ).encode("utf-8")
    ).hexdigest()
    locator = MappingProxyType(
        {
            "locator_kind": "listing_directory_snapshot",
            "adapter": record.adapter,
            "authority": record.authority,
            "directory": record.directory,
            "candidate_ticker": record.ticker,
            "expected_active_state": record.expected_active,
            "listing_status": record.listing_status,
            "market": record.market,
            "primary_exchange": record.primary_exchange,
            "security_type": record.security_type,
            "issuer_cik": record.issuer_cik,
            "composite_figi": record.composite_figi,
            "delisted_utc": record.delisted_utc,
            "source_as_of": record.source_as_of,
            "provider_last_updated_utc": record.provider_last_updated_utc,
            "snapshot_complete": record.snapshot_complete,
            "source_document_sha256": record.source_document_sha256,
            "adapter_version": _ADAPTER_VERSION,
        }
    )
    nasdaq = record.adapter == "nasdaq_symbol_directory"
    return ListingEvidence(
        evidence_id=f"listing-{identity[:32]}",
        source_family="listing_authority",
        adapter=record.adapter,
        kind="listing_directory_snapshot",
        source_url=record.source_url,
        title=(
            f"Nasdaq Trader {record.directory} exact symbol lookup"
            if nasdaq
            else "Massive exact ticker reference lookup"
        ),
        publisher="Nasdaq Trader" if nasdaq else "Massive",
        domain="nasdaqtrader.com" if nasdaq else "api.massive.com",
        source_published_at=record.file_created_at if nasdaq else None,
        retrieved_at=record.retrieved_at,
        excerpt=excerpt,
        content_sha256=content_sha256,
        source_document_sha256=record.source_document_sha256,
        source_locator=locator,
        evidence_dedupe_key=f"listing:{identity}",
    )


def _facts(
    evidence: ListingEvidence, record: ListingRecord, context: IdentityContext
) -> tuple[ListingFact, ...]:
    inactive_massive = (
        record.adapter == "massive_reference"
        and record.listing_status == "inactive"
    )
    if record.listing_status != "active" and not inactive_massive:
        return ()
    values: list[tuple[str, str]] = []
    if record.listing_status == "active":
        venue = _FACT_VENUES.get(record.primary_exchange or "")
        if record.ticker == context.current_ticker:
            values.append(("source_ticker", record.ticker))
            if venue is not None:
                values.append(("source_venue", venue))
        else:
            values.append(("successor_ticker", record.ticker))
            if venue is not None:
                values.append(("destination_venue", venue))
    security_class = _FACT_SECURITY_CLASSES.get(record.security_type or "")
    if security_class is not None:
        values.append(("security_class", security_class))
    if record.adapter == "massive_reference" and record.issuer_cik is not None:
        values.append(("issuer_cik", record.issuer_cik))
    excerpt_bytes = evidence.excerpt.encode("utf-8")
    return tuple(
        ListingFact(
            evidence_id=evidence.evidence_id,
            fact_type=fact_type,
            normalized_value=value,
            source_span_start=0,
            source_span_end=len(excerpt_bytes),
            cited_text_sha256=evidence.content_sha256,
            extractor_rule_id=f"{record.adapter}.exact_ticker",
            extractor_rule_version=_RULE_VERSION,
        )
        for fact_type, value in values
    )


def _result(
    *,
    context: IdentityContext,
    records: tuple[ListingRecord, ...],
    blockers: tuple[str, ...],
    diagnostics: Mapping[str, int],
) -> ListingEvidenceResult:
    evidence_rows = tuple(_evidence(record) for record in records)
    fact_rows = tuple(
        fact
        for evidence, record in zip(evidence_rows, records)
        for fact in _facts(evidence, record, context)
    )
    return ListingEvidenceResult(
        evidence=evidence_rows,
        facts=fact_rows,
        blockers=tuple(dict.fromkeys(blockers)),
        diagnostics=MappingProxyType(dict(diagnostics)),
    )


_MASSIVE_FAILURE_BLOCKERS = {
    "massive_api_key_missing": "massive_credential_missing",
    "massive_unauthorized": "massive_access_denied",
    "massive_rate_limited": "massive_rate_limited",
}


class ListingAuthoritySession:
    """Tick-scoped lazy Nasdaq snapshot plus deduplicated Massive lookups."""

    def __init__(
        self,
        *,
        transport: ListingAuthorityTransport,
        budget: ListingRequestBudget,
        retrieved_at: str,
        massive_api_key: str | None,
    ) -> None:
        _timestamp("retrieved_at", retrieved_at)
        self._transport = transport
        self._budget = budget
        self._massive_api_key = (
            massive_api_key.strip()
            if isinstance(massive_api_key, str) and massive_api_key.strip()
            else None
        )
        self._nasdaq_loaded = False
        self._nasdaq_snapshot: NasdaqDirectorySnapshot | None = None
        self._nasdaq_blocker: str | None = None
        self._massive: dict[
            tuple[str, bool, str], tuple[ListingRecord | None, str | None]
        ] = {}
        self._closed = False

    def _load_nasdaq(self) -> tuple[NasdaqDirectorySnapshot | None, str | None]:
        if self._nasdaq_loaded:
            return self._nasdaq_snapshot, self._nasdaq_blocker
        self._nasdaq_loaded = True
        try:
            nasdaq = self._transport.fetch_nasdaq(
                NASDAQ_LISTED_URL, budget=self._budget
            )
            other = self._transport.fetch_nasdaq(OTHER_LISTED_URL, budget=self._budget)
        except ListingTransportFailure:
            self._nasdaq_blocker = "listing_directory_unavailable"
            return None, self._nasdaq_blocker
        try:
            self._nasdaq_snapshot = _parse_nasdaq_snapshot(
                nasdaq_bytes=nasdaq.body,
                nasdaq_retrieved_at=nasdaq.retrieved_at,
                other_bytes=other.body,
                other_retrieved_at=other.retrieved_at,
            )
        except ListingEvidenceFailure as exc:
            self._nasdaq_blocker = exc.code
        return self._nasdaq_snapshot, self._nasdaq_blocker

    def _lookup_massive(
        self, ticker: str, *, expected_active: bool, market: str
    ) -> tuple[ListingRecord | None, str | None]:
        identity = (ticker, expected_active, market)
        cached = self._massive.get(identity)
        if cached is not None:
            return cached
        if self._massive_api_key is None:
            result = (None, "massive_credential_missing")
            self._massive[identity] = result
            return result
        try:
            payload = self._transport.fetch_massive_ticker(
                ticker,
                expected_active=expected_active,
                market=market,
                api_key=self._massive_api_key,
                budget=self._budget,
            )
        except ListingTransportFailure as exc:
            result = (
                None,
                _MASSIVE_FAILURE_BLOCKERS.get(
                    exc.code, "massive_reference_unavailable"
                ),
            )
            self._massive[identity] = result
            return result
        try:
            record = parse_massive_ticker(
                payload.body,
                ticker,
                expected_active=expected_active,
                market=market,
                retrieved_at=payload.retrieved_at,
                source_url=payload.source_url,
            )
        except ListingEvidenceFailure:
            result = (None, "massive_reference_unavailable")
        else:
            result = (record, None)
        self._massive[identity] = result
        return result

    def lookup(
        self,
        *,
        context: IdentityContext,
        candidate_tickers: tuple[str, ...],
        require_explicit_inactive: bool,
    ) -> ListingEvidenceResult:
        if self._closed:
            raise RuntimeError("listing_session_closed")
        if not isinstance(context, IdentityContext):
            raise ValueError("listing_identity_context")
        if (
            type(candidate_tickers) is not tuple
            or type(require_explicit_inactive) is not bool
        ):
            raise ValueError("listing_lookup_intent")
        candidates = tuple(
            dict.fromkeys(_normalized_ticker(item) for item in candidate_tickers)
        )
        if not candidates:
            raise ValueError("listing_candidate_tickers")

        snapshot, nasdaq_blocker = self._load_nasdaq()
        records: list[ListingRecord] = []
        blockers: list[str] = []
        if nasdaq_blocker is not None:
            blockers.append(nasdaq_blocker)
        for ticker in candidates:
            nasdaq_records = snapshot.lookup(ticker) if snapshot is not None else ()
            records.extend(nasdaq_records)
            if any(record.listing_status == "active" for record in nasdaq_records):
                continue

            if require_explicit_inactive:
                record, blocker = self._lookup_massive(
                    ticker, expected_active=False, market="stocks"
                )
                if record is not None:
                    records.append(record)
                if blocker is not None:
                    blockers.append(blocker)
                continue

            for market in ("stocks", "otc"):
                record, blocker = self._lookup_massive(
                    ticker, expected_active=True, market=market
                )
                if record is not None:
                    records.append(record)
                    if record.listing_status == "active":
                        break
                if blocker is not None:
                    blockers.append(blocker)
                    break

        return _result(
            context=context,
            records=tuple(records),
            blockers=tuple(blockers),
            diagnostics=self._budget.diagnostics(),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._massive_api_key = None
        self._transport.close()


__all__ = [
    "LISTING_BLOCKER_CODES",
    "LISTING_STATUSES",
    "MAX_NASDAQ_DIRECTORY_ROWS",
    "ListingAuthoritySession",
    "ListingEvidence",
    "ListingEvidenceFailure",
    "ListingEvidenceResult",
    "ListingFact",
    "ListingRecord",
    "NasdaqDirectorySnapshot",
    "parse_massive_ticker",
    "parse_nasdaq_directories",
]
