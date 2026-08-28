"""Bounded HTTP transport for Nasdaq Trader and Massive listing authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

import requests


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
MASSIVE_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"

MAX_NASDAQ_REQUESTS = 2
MAX_MASSIVE_REQUESTS = 4
MAX_NASDAQ_FILE_BYTES = 8 * 1024 * 1024
MAX_NASDAQ_TOTAL_BYTES = 12 * 1024 * 1024
MAX_MASSIVE_RESPONSE_BYTES = 1024 * 1024
MAX_MASSIVE_TOTAL_BYTES = 4 * 1024 * 1024

_NASDAQ_URLS = frozenset((NASDAQ_LISTED_URL, OTHER_LISTED_URL))
_MASSIVE_MARKETS = frozenset(("stocks", "otc"))
_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")


class ListingTransportFailure(RuntimeError):
    """A closed, secret-safe listing-authority transport failure."""

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class ListingRequestBudget:
    """Tick-scoped independent request and response budgets."""

    nasdaq_request_count: int = 0
    nasdaq_body_bytes: int = 0
    massive_request_count: int = 0
    massive_body_bytes: int = 0
    _nasdaq_urls: set[str] = field(default_factory=set)
    _massive_identities: set[tuple[str, bool, str]] = field(default_factory=set)

    @classmethod
    def lifecycle(cls) -> "ListingRequestBudget":
        return cls()

    def reserve_nasdaq_request(self, source_url: str) -> None:
        if self.nasdaq_request_count >= MAX_NASDAQ_REQUESTS:
            raise ListingTransportFailure("nasdaq_request_budget")
        if source_url in self._nasdaq_urls:
            raise ListingTransportFailure("nasdaq_request_duplicate")
        self._nasdaq_urls.add(source_url)
        self.nasdaq_request_count += 1

    def record_nasdaq_body(self, count: int) -> None:
        if count < 0 or self.nasdaq_body_bytes + count > MAX_NASDAQ_TOTAL_BYTES:
            raise ListingTransportFailure("nasdaq_byte_budget")
        self.nasdaq_body_bytes += count

    def reserve_massive_request(self, identity: tuple[str, bool, str]) -> None:
        if identity in self._massive_identities:
            raise ListingTransportFailure("massive_request_duplicate")
        if self.massive_request_count >= MAX_MASSIVE_REQUESTS:
            raise ListingTransportFailure("massive_request_budget")
        self._massive_identities.add(identity)
        self.massive_request_count += 1

    def record_massive_body(self, count: int) -> None:
        if count < 0 or self.massive_body_bytes + count > MAX_MASSIVE_TOTAL_BYTES:
            raise ListingTransportFailure("massive_byte_budget")
        self.massive_body_bytes += count

    def diagnostics(self) -> dict[str, int]:
        return {
            "nasdaq_request_count": self.nasdaq_request_count,
            "nasdaq_body_bytes": self.nasdaq_body_bytes,
            "massive_request_count": self.massive_request_count,
            "massive_body_bytes": self.massive_body_bytes,
        }


@dataclass(frozen=True)
class ListingHttpPayload:
    source_url: str
    retrieved_at: str
    status_code: int
    content_type: str
    body: bytes


class ListingAuthorityTransport:
    """Fail-closed bounded client using an injected or owned requests session."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session if session is not None else requests.Session()
        self._now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _content_type(response: Any) -> str:
        headers = getattr(response, "headers", {})
        for name, value in headers.items():
            if str(name).lower() == "content-type":
                return str(value).split(";", 1)[0].strip().lower()
        return ""

    @staticmethod
    def _read_bounded(
        response: Any,
        maximum: int,
        *,
        code_prefix: str,
        aggregate_maximum: int | None = None,
        aggregate_overflow_code: str | None = None,
    ) -> bytes:
        headers = getattr(response, "headers", {})
        raw_length = ""
        for name, value in headers.items():
            if str(name).lower() == "content-length":
                raw_length = str(value).strip()
                break
        if raw_length.isdigit() and int(raw_length) > maximum:
            raise ListingTransportFailure(f"{code_prefix}_response_too_large")
        if (
            raw_length.isdigit()
            and aggregate_maximum is not None
            and int(raw_length) > aggregate_maximum
        ):
            raise ListingTransportFailure(
                aggregate_overflow_code or f"{code_prefix}_response_too_large"
            )

        chunks: list[bytes] = []
        total = 0
        try:
            iterator = response.iter_content(chunk_size=min(65_536, maximum + 1))
            for chunk in iterator:
                if not chunk:
                    continue
                if not isinstance(chunk, bytes):
                    raise ListingTransportFailure(f"{code_prefix}_transport_unavailable")
                total += len(chunk)
                if total > maximum:
                    raise ListingTransportFailure(f"{code_prefix}_response_too_large")
                if aggregate_maximum is not None and total > aggregate_maximum:
                    raise ListingTransportFailure(
                        aggregate_overflow_code or f"{code_prefix}_response_too_large"
                    )
                chunks.append(chunk)
        except ListingTransportFailure:
            raise
        except requests.RequestException:
            raise ListingTransportFailure(f"{code_prefix}_transport_unavailable") from None
        except (OSError, TypeError, ValueError) as exc:
            raise ListingTransportFailure(f"{code_prefix}_transport_unavailable") from exc
        return b"".join(chunks)

    @staticmethod
    def _retrieved_at(now: datetime) -> str:
        if not isinstance(now, datetime):
            raise ListingTransportFailure("listing_clock_unavailable")
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        if not isinstance(ticker, str):
            raise ListingTransportFailure("massive_ticker_invalid")
        value = ticker.strip().upper()
        if not _TICKER_PATTERN.fullmatch(value):
            raise ListingTransportFailure("massive_ticker_invalid")
        return value

    @staticmethod
    def _normalize_market(market: str) -> str:
        if not isinstance(market, str):
            raise ListingTransportFailure("massive_market_invalid")
        value = market.strip().lower()
        if value not in _MASSIVE_MARKETS:
            raise ListingTransportFailure("massive_market_invalid")
        return value

    def _request(
        self,
        *,
        source_url: str,
        request_url: str,
        params: Mapping[str, Any] | None,
        expected_content_type: str,
        code_prefix: str,
        status_codes: Mapping[int, str],
        maximum_bytes: int,
        aggregate_maximum_bytes: int | None = None,
        aggregate_overflow_code: str | None = None,
    ) -> ListingHttpPayload:
        try:
            response = self._session.get(
                request_url,
                params=dict(params) if params is not None else None,
                headers={"Accept": expected_content_type},
                timeout=(5, 20),
                stream=True,
                allow_redirects=False,
            )
        except (requests.RequestException, OSError, TimeoutError):
            raise ListingTransportFailure(f"{code_prefix}_transport_unavailable") from None

        try:
            status_code = int(getattr(response, "status_code"))
            if 300 <= status_code < 400:
                raise ListingTransportFailure(f"{code_prefix}_redirect", status_code=status_code)
            failure_code = status_codes.get(status_code)
            if failure_code is not None:
                raise ListingTransportFailure(failure_code, status_code=status_code)
            if not 200 <= status_code < 300:
                raise ListingTransportFailure(f"{code_prefix}_http_error", status_code=status_code)
            content_type = self._content_type(response)
            if content_type != expected_content_type:
                raise ListingTransportFailure(f"{code_prefix}_content_type_mismatch")
            body = self._read_bounded(
                response,
                maximum_bytes,
                code_prefix=code_prefix,
                aggregate_maximum=aggregate_maximum_bytes,
                aggregate_overflow_code=aggregate_overflow_code,
            )
            return ListingHttpPayload(
                source_url=source_url,
                retrieved_at=self._retrieved_at(self._now()),
                status_code=status_code,
                content_type=content_type,
                body=body,
            )
        except ListingTransportFailure:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise ListingTransportFailure(f"{code_prefix}_transport_unavailable") from exc
        finally:
            try:
                response.close()
            except (AttributeError, OSError, TypeError):
                pass

    def fetch_nasdaq(
        self, source_url: str, *, budget: ListingRequestBudget
    ) -> ListingHttpPayload:
        """Fetch one exact Nasdaq directory inside the shared tick budget."""
        if str(source_url) not in _NASDAQ_URLS:
            raise ListingTransportFailure("nasdaq_url_unsupported")
        budget.reserve_nasdaq_request(str(source_url))
        remaining = MAX_NASDAQ_TOTAL_BYTES - budget.nasdaq_body_bytes
        if remaining <= 0:
            raise ListingTransportFailure("nasdaq_byte_budget")
        payload = self._request(
            source_url=str(source_url),
            request_url=str(source_url),
            params=None,
            expected_content_type="text/plain",
            code_prefix="nasdaq",
            status_codes={},
            maximum_bytes=MAX_NASDAQ_FILE_BYTES,
            aggregate_maximum_bytes=remaining,
            aggregate_overflow_code="nasdaq_byte_budget",
        )
        budget.record_nasdaq_body(len(payload.body))
        return payload

    def fetch_massive_ticker(
        self,
        ticker: str,
        *,
        expected_active: bool,
        market: str,
        api_key: str,
        budget: ListingRequestBudget,
    ) -> ListingHttpPayload:
        """Fetch one exact Massive ticker lookup without persisting its key."""
        normalized_ticker = self._normalize_ticker(ticker)
        if type(expected_active) is not bool:
            raise ListingTransportFailure("massive_active_invalid")
        normalized_market = self._normalize_market(market)
        if not isinstance(api_key, str) or not api_key.strip():
            raise ListingTransportFailure("massive_api_key_missing")
        key = api_key.strip()

        identity = (normalized_ticker, expected_active, normalized_market)
        budget.reserve_massive_request(identity)
        active = "true" if expected_active else "false"
        canonical_params = (
            ("ticker", normalized_ticker),
            ("active", active),
            ("market", normalized_market),
            ("limit", "2"),
        )
        source_url = f"{MASSIVE_TICKERS_URL}?{urlencode(canonical_params)}"
        remaining = MAX_MASSIVE_TOTAL_BYTES - budget.massive_body_bytes
        if remaining <= 0:
            raise ListingTransportFailure("massive_byte_budget")
        payload = self._request(
            source_url=source_url,
            request_url=MASSIVE_TICKERS_URL,
            params={
                "ticker": normalized_ticker,
                "active": active,
                "market": normalized_market,
                "limit": 2,
                "apiKey": key,
            },
            expected_content_type="application/json",
            code_prefix="massive",
            status_codes={
                401: "massive_unauthorized",
                403: "massive_unauthorized",
                404: "massive_not_found",
                429: "massive_rate_limited",
            },
            maximum_bytes=min(MAX_MASSIVE_RESPONSE_BYTES, remaining),
        )
        self._validate_massive_payload(payload.body, normalized_ticker)
        budget.record_massive_body(len(payload.body))
        return payload

    @staticmethod
    def _validate_massive_payload(body: bytes, ticker: str) -> None:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ListingTransportFailure("massive_invalid_json") from exc
        if not isinstance(payload, dict):
            raise ListingTransportFailure("massive_invalid_json")
        if str(payload.get("status", "")).upper() == "ERROR":
            raise ListingTransportFailure("massive_provider_error")
        if not isinstance(payload.get("results"), list):
            raise ListingTransportFailure("massive_invalid_json")
        exact_rows = [
            row
            for row in payload["results"]
            if isinstance(row, dict) and str(row.get("ticker", "")).strip().upper() == ticker
        ]
        if len(exact_rows) > 1:
            raise ListingTransportFailure("massive_response_ambiguous")

    def diagnostics(self, budget: ListingRequestBudget) -> Mapping[str, int]:
        return budget.diagnostics()

    def close(self) -> None:
        self._session.close()
