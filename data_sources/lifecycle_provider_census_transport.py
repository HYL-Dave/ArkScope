"""Bounded Massive/Nasdaq transport for the detached lifecycle census only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, quote_plus, urlencode, urlsplit

import requests

from data_sources.dependency_log_redaction import dependency_log_redaction


MASSIVE_LISTING_URL = "https://api.massive.com/v3/reference/tickers"
MASSIVE_EVENTS_PREFIX = "https://api.massive.com/vX/reference/tickers/"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

MAX_MASSIVE_REQUESTS = 14
MAX_EODHD_REQUESTS = 2
MAX_NASDAQ_REQUESTS = 2
MAX_MASSIVE_RESPONSE_BYTES = 1024 * 1024
MAX_MASSIVE_TOTAL_BYTES = 14 * 1024 * 1024
MAX_NASDAQ_FILE_BYTES = 8 * 1024 * 1024
MAX_NASDAQ_TOTAL_BYTES = 12 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15

_CANONICAL_MASSIVE_LISTING_URL = "https://api.massive.com/v3/reference/tickers"
_CANONICAL_MASSIVE_EVENTS_PREFIX = "https://api.massive.com/vX/reference/tickers/"
_NASDAQ_URLS = frozenset((NASDAQ_LISTED_URL, OTHER_LISTED_URL))
_CREDENTIAL_QUERY_NAMES = frozenset(
    {
        "apikey",
        "api-key",
        "api_key",
        "authorization",
        "access_token",
        "token",
    }
)
_TICKER = re.compile(r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*(?:\*)?$")
_STABLE_ID = re.compile(r"^BBG[A-Z0-9_]{8,29}$")
_MAX_FIELDS = frozenset(
    {"max_massive_requests", "max_eodhd_requests", "max_nasdaq_requests"}
)


class CensusTransportFailure(RuntimeError):
    """A normalized failure that never includes provider-controlled detail."""

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class CensusRequestBudget:
    """Run-scoped independent counters with fixed provider ceilings."""

    max_massive_requests: int = MAX_MASSIVE_REQUESTS
    max_eodhd_requests: int = 2
    max_nasdaq_requests: int = MAX_NASDAQ_REQUESTS
    massive_requests: int = 0
    eodhd_requests: int = 0
    nasdaq_requests: int = 0

    def __post_init__(self) -> None:
        limits = (
            (self.max_massive_requests, MAX_MASSIVE_REQUESTS),
            (self.max_eodhd_requests, MAX_EODHD_REQUESTS),
            (self.max_nasdaq_requests, MAX_NASDAQ_REQUESTS),
        )
        counters = (
            (self.massive_requests, self.max_massive_requests),
            (self.eodhd_requests, self.max_eodhd_requests),
            (self.nasdaq_requests, self.max_nasdaq_requests),
        )
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in limits
        ) or any(
            type(value) is not int or not 0 <= value <= maximum
            for value, maximum in counters
        ):
            raise ValueError("census_request_budget")
        self._massive_identities: set[tuple[str, ...]] = set()
        self._nasdaq_identities: set[str] = set()
        self._massive_body_bytes = 0
        self._nasdaq_body_bytes = 0

    def __setattr__(self, name: str, value: object) -> None:
        if name in _MAX_FIELDS and "_massive_identities" in self.__dict__:
            raise AttributeError("census_request_budget_limit")
        object.__setattr__(self, name, value)

    @staticmethod
    def _valid_identity(identity: object) -> bool:
        return (
            isinstance(identity, tuple)
            and len(identity) >= 2
            and all(
                isinstance(part, str)
                and bool(part)
                and len(part) <= 128
                and part == part.strip()
                and all(ord(character) >= 32 for character in part)
                for part in identity
            )
        )

    def reserve_massive(self, identity: tuple[str, ...]) -> None:
        if not self._valid_identity(identity):
            raise CensusTransportFailure("massive_request_identity_invalid")
        if self.massive_requests >= self.max_massive_requests:
            raise CensusTransportFailure("massive_request_budget")
        if identity in self._massive_identities:
            raise CensusTransportFailure("massive_request_duplicate")
        self._massive_identities.add(identity)
        self.massive_requests += 1

    def reserve_nasdaq(self, source_url: str) -> None:
        if self.nasdaq_requests >= self.max_nasdaq_requests:
            raise CensusTransportFailure("nasdaq_request_budget")
        if source_url in self._nasdaq_identities:
            raise CensusTransportFailure("nasdaq_request_duplicate")
        self._nasdaq_identities.add(source_url)
        self.nasdaq_requests += 1

    def record_massive_body(self, count: int) -> None:
        if (
            type(count) is not int
            or count < 0
            or self._massive_body_bytes + count > MAX_MASSIVE_TOTAL_BYTES
        ):
            raise CensusTransportFailure("massive_byte_budget")
        self._massive_body_bytes += count

    def record_nasdaq_body(self, count: int) -> None:
        if (
            type(count) is not int
            or count < 0
            or self._nasdaq_body_bytes + count > MAX_NASDAQ_TOTAL_BYTES
        ):
            raise CensusTransportFailure("nasdaq_byte_budget")
        self._nasdaq_body_bytes += count

    @property
    def massive_body_bytes(self) -> int:
        return self._massive_body_bytes

    @property
    def nasdaq_body_bytes(self) -> int:
        return self._nasdaq_body_bytes

    def diagnostics(self) -> dict[str, int]:
        return {
            "massive_requests": self.massive_requests,
            "massive_body_bytes": self.massive_body_bytes,
            "eodhd_requests": self.eodhd_requests,
            "nasdaq_requests": self.nasdaq_requests,
            "nasdaq_body_bytes": self.nasdaq_body_bytes,
        }


@dataclass(frozen=True)
class MassiveListingResult:
    ticker: str
    expected_active: bool
    found: bool
    active: bool | None
    stable_id: str | None
    delisted_date: str | None
    source_locator: str
    response_sha256: str
    response_bytes: int


@dataclass(frozen=True)
class MassiveTickerEventsResult:
    stable_id: str
    events: tuple[tuple[str, str, str], ...]
    source_locator: str
    response_sha256: str
    response_bytes: int


@dataclass(frozen=True)
class NasdaqDirectoryResult:
    source_locator: str
    body: bytes
    response_sha256: str
    response_bytes: int


@dataclass(frozen=True)
class _HttpPayload:
    body: bytes
    status_code: int
    content_type: str


def _normalized_api_key(api_key: object) -> str:
    if not isinstance(api_key, str) or not api_key.strip():
        raise CensusTransportFailure("massive_api_key_missing")
    return api_key.strip()


def _validate_ticker(value: object, *, code: str) -> str:
    if not isinstance(value, str) or _TICKER.fullmatch(value) is None:
        raise CensusTransportFailure(code)
    canonical_length = len(value[:-1] if value.endswith("*") else value)
    if canonical_length > 16:
        raise CensusTransportFailure(code)
    return value


def _validate_stable_id(value: object) -> str:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        raise CensusTransportFailure("massive_stable_id_invalid")
    return value


def _exact_date(value: object, *, code: str) -> str:
    parsed: date | None = None
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            pass
    if parsed is None or parsed.isoformat() != value:
        raise CensusTransportFailure(code)
    return value


def _optional_delisted_date(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 64:
        raise CensusTransportFailure("massive_delisted_date_invalid")
    parsed: date | None = None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        try:
            timestamp = value[:-1] + "+00:00" if value.endswith("Z") else value
            parsed = datetime.fromisoformat(timestamp).date()
        except ValueError:
            pass
    if parsed is None:
        raise CensusTransportFailure("massive_delisted_date_invalid")
    return parsed.isoformat()


def _credential_free_url(url: str, api_key: str | None) -> None:
    unsafe = False
    try:
        query_names = {
            name.casefold() for name, _value in parse_qsl(urlsplit(url).query)
        }
    except (TypeError, ValueError):
        query_names = set()
        unsafe = True
    if query_names & _CREDENTIAL_QUERY_NAMES:
        unsafe = True
    if api_key is not None:
        variants = (api_key, quote(api_key, safe=""), quote_plus(api_key, safe=""))
        if any(variant and variant in url for variant in variants):
            unsafe = True
    if unsafe:
        raise CensusTransportFailure("request_url_credential")


def _allowed_request_url(url: str) -> bool:
    if url == _CANONICAL_MASSIVE_LISTING_URL or url in _NASDAQ_URLS:
        return True
    if not url.startswith(_CANONICAL_MASSIVE_EVENTS_PREFIX) or not url.endswith(
        "/events"
    ):
        return False
    stable_id = url[len(_CANONICAL_MASSIVE_EVENTS_PREFIX) : -len("/events")]
    return _STABLE_ID.fullmatch(stable_id) is not None


def _json_body(body: bytes) -> object:
    payload: object = None
    failed = False
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        failed = True
    if failed:
        raise CensusTransportFailure("massive_invalid_json") from None
    return payload


def _validate_massive_envelope(body: bytes) -> Mapping[str, Any]:
    payload = _json_body(body)
    if not isinstance(payload, dict):
        raise CensusTransportFailure("massive_invalid_json")
    if payload.get("status") == "ERROR":
        raise CensusTransportFailure("massive_provider_error")
    if payload.get("status") != "OK":
        raise CensusTransportFailure("massive_invalid_json")
    if payload.get("next_url") not in (None, ""):
        raise CensusTransportFailure("massive_pagination_unsupported")
    return payload


class LifecycleProviderCensusTransport:
    """Fail-closed HTTP boundary kept outside all production scheduling paths."""

    def __init__(self, *, session: requests.Session) -> None:
        self._session = session

    @staticmethod
    def _content_type(response: Any) -> str:
        for name, value in getattr(response, "headers", {}).items():
            if str(name).casefold() == "content-type":
                return str(value).split(";", 1)[0].strip().lower()
        return ""

    @staticmethod
    def _read_bounded(
        response: Any,
        *,
        maximum_bytes: int,
        aggregate_remaining_bytes: int,
        code_prefix: str,
    ) -> bytes:
        raw_length = ""
        for name, value in getattr(response, "headers", {}).items():
            if str(name).casefold() == "content-length":
                raw_length = str(value).strip()
                break
        if raw_length.isdigit() and int(raw_length) > maximum_bytes:
            raise CensusTransportFailure(f"{code_prefix}_response_too_large")
        if raw_length.isdigit() and int(raw_length) > aggregate_remaining_bytes:
            raise CensusTransportFailure(f"{code_prefix}_byte_budget")

        chunks: list[bytes] = []
        total = 0
        failed = False
        try:
            iterator = response.iter_content(chunk_size=min(65_536, maximum_bytes + 1))
            for chunk in iterator:
                if not chunk:
                    continue
                if not isinstance(chunk, bytes):
                    raise CensusTransportFailure(f"{code_prefix}_transport_unavailable")
                total += len(chunk)
                if total > maximum_bytes:
                    raise CensusTransportFailure(f"{code_prefix}_response_too_large")
                if total > aggregate_remaining_bytes:
                    raise CensusTransportFailure(f"{code_prefix}_byte_budget")
                chunks.append(chunk)
        except CensusTransportFailure:
            raise
        except Exception:
            failed = True
        if failed:
            raise CensusTransportFailure(
                f"{code_prefix}_transport_unavailable"
            ) from None
        return b"".join(chunks)

    def _request(
        self,
        *,
        request_url: str,
        source_locator: str,
        params: Mapping[str, object] | None,
        api_key: str | None,
        expected_content_type: str,
        code_prefix: str,
        maximum_bytes: int,
        aggregate_remaining_bytes: int,
    ) -> _HttpPayload:
        _credential_free_url(request_url, api_key)
        _credential_free_url(source_locator, api_key)
        if not _allowed_request_url(request_url):
            raise CensusTransportFailure("request_url_unsupported")
        with dependency_log_redaction((api_key,)):
            return self._request_inside_redaction(
                request_url=request_url,
                params=params,
                api_key=api_key,
                expected_content_type=expected_content_type,
                code_prefix=code_prefix,
                maximum_bytes=maximum_bytes,
                aggregate_remaining_bytes=aggregate_remaining_bytes,
            )

    def _request_inside_redaction(
        self,
        *,
        request_url: str,
        params: Mapping[str, object] | None,
        api_key: str | None,
        expected_content_type: str,
        code_prefix: str,
        maximum_bytes: int,
        aggregate_remaining_bytes: int,
    ) -> _HttpPayload:
        request_params = dict(params) if params is not None else None
        if api_key is not None:
            request_params = dict(request_params or {})
            request_params["apiKey"] = api_key

        response: Any | None = None
        request_failed = False
        try:
            response = self._session.get(
                request_url,
                params=request_params,
                headers={"Accept": expected_content_type},
                timeout=REQUEST_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )
        except Exception:
            request_failed = True
        if request_failed:
            raise CensusTransportFailure(
                f"{code_prefix}_transport_unavailable"
            ) from None

        payload: _HttpPayload | None = None
        response_failed = False
        try:
            status_code = int(getattr(response, "status_code"))
            if 300 <= status_code < 400:
                raise CensusTransportFailure(
                    f"{code_prefix}_redirect", status_code=status_code
                )
            status_failures = {
                401: f"{code_prefix}_unauthorized",
                403: f"{code_prefix}_unauthorized",
                404: f"{code_prefix}_not_found",
                429: f"{code_prefix}_rate_limited",
            }
            if status_code in status_failures:
                raise CensusTransportFailure(
                    status_failures[status_code], status_code=status_code
                )
            if not 200 <= status_code < 300:
                raise CensusTransportFailure(
                    f"{code_prefix}_http_error", status_code=status_code
                )
            content_type = self._content_type(response)
            if content_type != expected_content_type:
                raise CensusTransportFailure(f"{code_prefix}_content_type_mismatch")
            body = self._read_bounded(
                response,
                maximum_bytes=maximum_bytes,
                aggregate_remaining_bytes=aggregate_remaining_bytes,
                code_prefix=code_prefix,
            )
            payload = _HttpPayload(
                body=body,
                status_code=status_code,
                content_type=content_type,
            )
        except CensusTransportFailure:
            raise
        except Exception:
            response_failed = True
        finally:
            try:
                response.close()
            except Exception:
                pass
        if response_failed or payload is None:
            raise CensusTransportFailure(
                f"{code_prefix}_transport_unavailable"
            ) from None
        return payload

    def fetch_massive_listing(
        self,
        ticker: str,
        *,
        expected_active: bool,
        api_key: str,
        budget: CensusRequestBudget,
    ) -> MassiveListingResult:
        requested_ticker = _validate_ticker(ticker, code="massive_ticker_invalid")
        if type(expected_active) is not bool:
            raise CensusTransportFailure("massive_active_invalid")
        key = _normalized_api_key(api_key)
        if not isinstance(budget, CensusRequestBudget):
            raise CensusTransportFailure("census_request_budget_invalid")

        active = "true" if expected_active else "false"
        canonical_params = (
            ("ticker", requested_ticker),
            ("active", active),
            ("market", "stocks"),
            ("limit", "2"),
        )
        source_locator = f"{MASSIVE_LISTING_URL}?{urlencode(canonical_params)}"
        _credential_free_url(MASSIVE_LISTING_URL, key)
        _credential_free_url(source_locator, key)
        if budget.massive_body_bytes >= MAX_MASSIVE_TOTAL_BYTES:
            raise CensusTransportFailure("massive_byte_budget")
        budget.reserve_massive(("listing", requested_ticker, active))
        payload = self._request(
            request_url=MASSIVE_LISTING_URL,
            source_locator=source_locator,
            params={
                "ticker": requested_ticker,
                "active": active,
                "market": "stocks",
                "limit": 2,
            },
            api_key=key,
            expected_content_type="application/json",
            code_prefix="massive",
            maximum_bytes=MAX_MASSIVE_RESPONSE_BYTES,
            aggregate_remaining_bytes=(
                MAX_MASSIVE_TOTAL_BYTES - budget.massive_body_bytes
            ),
        )
        budget.record_massive_body(len(payload.body))
        envelope = _validate_massive_envelope(payload.body)
        results = envelope.get("results")
        if not isinstance(results, list):
            raise CensusTransportFailure("massive_invalid_json")
        if len(results) > 1:
            stable_ids = [
                row.get("composite_figi")
                for row in results
                if isinstance(row, dict) and isinstance(row.get("composite_figi"), str)
            ]
            if len(stable_ids) != len(set(stable_ids)):
                raise CensusTransportFailure("massive_stable_identity_duplicate")
            raise CensusTransportFailure("massive_listing_ambiguous")

        digest = hashlib.sha256(payload.body).hexdigest()
        if not results:
            return MassiveListingResult(
                ticker=requested_ticker,
                expected_active=expected_active,
                found=False,
                active=None,
                stable_id=None,
                delisted_date=None,
                source_locator=source_locator,
                response_sha256=digest,
                response_bytes=len(payload.body),
            )

        row = results[0]
        if not isinstance(row, dict):
            raise CensusTransportFailure("massive_invalid_json")
        if row.get("ticker") != requested_ticker:
            raise CensusTransportFailure("massive_listing_ticker_mismatch")
        returned_active = row.get("active")
        if type(returned_active) is not bool or returned_active is not expected_active:
            raise CensusTransportFailure("massive_listing_active_mismatch")
        if row.get("market") != "stocks":
            raise CensusTransportFailure("massive_listing_market_mismatch")
        stable_id = row.get("composite_figi")
        if stable_id is not None:
            stable_id = _validate_stable_id(stable_id)
        delisted_date = _optional_delisted_date(row.get("delisted_utc"))
        if expected_active and delisted_date is not None:
            raise CensusTransportFailure("massive_listing_active_mismatch")
        return MassiveListingResult(
            ticker=requested_ticker,
            expected_active=expected_active,
            found=True,
            active=returned_active,
            stable_id=stable_id,
            delisted_date=delisted_date,
            source_locator=source_locator,
            response_sha256=digest,
            response_bytes=len(payload.body),
        )

    def fetch_massive_ticker_events(
        self,
        *,
        stable_id: str,
        api_key: str,
        budget: CensusRequestBudget,
    ) -> MassiveTickerEventsResult:
        requested_stable_id = _validate_stable_id(stable_id)
        key = _normalized_api_key(api_key)
        if not isinstance(budget, CensusRequestBudget):
            raise CensusTransportFailure("census_request_budget_invalid")
        request_url = f"{MASSIVE_EVENTS_PREFIX}{requested_stable_id}/events"
        _credential_free_url(request_url, key)
        if budget.massive_body_bytes >= MAX_MASSIVE_TOTAL_BYTES:
            raise CensusTransportFailure("massive_byte_budget")
        budget.reserve_massive(("events", requested_stable_id))
        payload = self._request(
            request_url=request_url,
            source_locator=request_url,
            params=None,
            api_key=key,
            expected_content_type="application/json",
            code_prefix="massive",
            maximum_bytes=MAX_MASSIVE_RESPONSE_BYTES,
            aggregate_remaining_bytes=(
                MAX_MASSIVE_TOTAL_BYTES - budget.massive_body_bytes
            ),
        )
        budget.record_massive_body(len(payload.body))
        envelope = _validate_massive_envelope(payload.body)
        results = envelope.get("results")
        if not isinstance(results, dict) or not isinstance(results.get("events"), list):
            raise CensusTransportFailure("massive_invalid_json")
        source_ticker = _validate_ticker(
            results.get("ticker"), code="massive_event_ticker_invalid"
        )

        normalized_events: list[tuple[str, str, str]] = []
        for event in results["events"]:
            if not isinstance(event, dict):
                raise CensusTransportFailure("massive_invalid_json")
            if event.get("type") != "ticker_change":
                raise CensusTransportFailure("massive_event_type_unsupported")
            effective_date = _exact_date(
                event.get("date"), code="massive_event_date_invalid"
            )
            ticker_change = event.get("ticker_change")
            if not isinstance(ticker_change, dict):
                raise CensusTransportFailure("massive_invalid_json")
            successor_ticker = _validate_ticker(
                ticker_change.get("ticker"), code="massive_event_ticker_invalid"
            )
            if successor_ticker == source_ticker:
                raise CensusTransportFailure("massive_event_ticker_invalid")
            normalized = (source_ticker, successor_ticker, effective_date)
            if normalized in normalized_events:
                raise CensusTransportFailure("massive_event_duplicate")
            normalized_events.append(normalized)

        return MassiveTickerEventsResult(
            stable_id=requested_stable_id,
            events=tuple(normalized_events),
            source_locator=request_url,
            response_sha256=hashlib.sha256(payload.body).hexdigest(),
            response_bytes=len(payload.body),
        )

    def fetch_nasdaq_directory(
        self, source_url: str, *, budget: CensusRequestBudget
    ) -> NasdaqDirectoryResult:
        if not isinstance(source_url, str) or source_url not in _NASDAQ_URLS:
            raise CensusTransportFailure("nasdaq_url_unsupported")
        if not isinstance(budget, CensusRequestBudget):
            raise CensusTransportFailure("census_request_budget_invalid")
        if budget.nasdaq_body_bytes >= MAX_NASDAQ_TOTAL_BYTES:
            raise CensusTransportFailure("nasdaq_byte_budget")
        budget.reserve_nasdaq(source_url)
        payload = self._request(
            request_url=source_url,
            source_locator=source_url,
            params=None,
            api_key=None,
            expected_content_type="text/plain",
            code_prefix="nasdaq",
            maximum_bytes=MAX_NASDAQ_FILE_BYTES,
            aggregate_remaining_bytes=(
                MAX_NASDAQ_TOTAL_BYTES - budget.nasdaq_body_bytes
            ),
        )
        budget.record_nasdaq_body(len(payload.body))
        return NasdaqDirectoryResult(
            source_locator=source_url,
            body=payload.body,
            response_sha256=hashlib.sha256(payload.body).hexdigest(),
            response_bytes=len(payload.body),
        )

    def diagnostics(self, budget: CensusRequestBudget) -> Mapping[str, int]:
        if not isinstance(budget, CensusRequestBudget):
            raise CensusTransportFailure("census_request_budget_invalid")
        return budget.diagnostics()

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass


__all__ = [
    "CensusRequestBudget",
    "CensusTransportFailure",
    "LifecycleProviderCensusTransport",
    "MASSIVE_EVENTS_PREFIX",
    "MASSIVE_LISTING_URL",
    "MAX_MASSIVE_REQUESTS",
    "MAX_NASDAQ_REQUESTS",
    "MassiveListingResult",
    "MassiveTickerEventsResult",
    "NASDAQ_LISTED_URL",
    "NasdaqDirectoryResult",
    "OTHER_LISTED_URL",
]
