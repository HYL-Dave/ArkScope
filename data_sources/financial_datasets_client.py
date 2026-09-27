"""Local-first paid observations with explicit stored/auto/refresh controls."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from urllib.parse import parse_qsl, urlsplit

import requests

from src.fundamentals.execution import check_financial_work
from src.fundamentals.reuse import (
    Observation, ReuseFailure, instant as _instant, policy, reuse_or_acquire, storage_scope,
)

from .financial_datasets_governance import (
    FinancialDatasetsFailure, FinancialDatasetsGovernor, FinancialDatasetsPolicy,
)
from .financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)

logger = logging.getLogger(__name__)

# Cache TTL defaults (days)
_DEFAULT_TTL = {
    "annual": 180,
    "quarterly": 90,
    "ttm": 30,
}

_FILE_CACHE_DIR = Path("data/cache/financial_datasets")


def validate_freshness(freshness, max_age_seconds):
    try:
        return policy(freshness, max_age_seconds)
    except ReuseFailure as exc:
        raise FinancialDatasetsFailure("financial_datasets_freshness_invalid") from exc


def _valid_rows(data, response_key, ticker, period):
    rows = data.get(response_key) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return False
    for item in rows:
        if not isinstance(item, dict) or item.get("ticker") != ticker.upper() or item.get("period") != period:
            return False
        if any(not isinstance(item.get(key), str) or not item[key] for key in ("report_period", "fiscal_period", "currency")):
            return False
        try:
            if date.fromisoformat(item["report_period"]).isoformat() != item["report_period"]:
                return False
        except ValueError:
            return False
    return True


class FinancialDatasetsClient:
    """Paid financial statements with acquisition-dated local reuse by default."""

    BASE_URL = "https://api.financialdatasets.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_days: Optional[Dict[str, int]] = None,
        cache_backend: Optional[Any] = None,
        request_policy: Optional[Dict[str, Any]] = None,
        governor: Optional[FinancialDatasetsGovernor] = None,
    ):
        """Use the explicitly supplied local cache owner when present."""
        self.api_key = api_key or os.getenv("FINANCIAL_DATASETS_API_KEY")
        self._cache_backend = cache_backend
        self._cache_days = {**_DEFAULT_TTL, **(cache_days or {})}
        self._request_policy = dict(request_policy) if isinstance(request_policy, dict) else request_policy
        self._governor = governor
        self.observations: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_income_statements(
        self,
        ticker: str,
        period: str = "quarterly",
        limit: int = 4,
        *, freshness: str = "auto", max_age_seconds: Optional[int] = None,
    ) -> List[IncomeStatement]:
        """Get income statements. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/income-statements",
            cache_prefix="income",
            ticker=ticker,
            period=period,
            limit=limit,
            freshness=freshness, max_age_seconds=max_age_seconds,
        )
        return [
            self._to_dataclass(IncomeStatement, d)
            for d in raw.get("income_statements", [])
        ]

    def get_balance_sheets(
        self,
        ticker: str,
        period: str = "quarterly",
        limit: int = 1,
        *, freshness: str = "auto", max_age_seconds: Optional[int] = None,
    ) -> List[BalanceSheet]:
        """Get balance sheets. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/balance-sheets",
            cache_prefix="balance",
            ticker=ticker,
            period=period,
            limit=limit,
            freshness=freshness, max_age_seconds=max_age_seconds,
        )
        return [
            self._to_dataclass(BalanceSheet, d)
            for d in raw.get("balance_sheets", [])
        ]

    def get_cash_flow_statements(
        self,
        ticker: str,
        period: str = "quarterly",
        limit: int = 4,
        *, freshness: str = "auto", max_age_seconds: Optional[int] = None,
    ) -> List[CashFlowStatement]:
        """Get cash flow statements. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/cash-flow-statements",
            cache_prefix="cashflow",
            ticker=ticker,
            period=period,
            limit=limit,
            freshness=freshness, max_age_seconds=max_age_seconds,
        )
        return [
            self._to_dataclass(CashFlowStatement, d)
            for d in raw.get("cash_flow_statements", [])
        ]

    # ------------------------------------------------------------------
    # Caching layer
    # ------------------------------------------------------------------

    def _cached_request(
        self,
        endpoint: str,
        cache_prefix: str,
        ticker: str,
        period: str,
        limit: int,
        freshness: str,
        max_age_seconds: Optional[int],
    ) -> Dict[str, Any]:
        """Honor caller freshness before consulting the separate paid policy."""
        check_financial_work()
        if (not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", ticker)
                or period not in _DEFAULT_TTL or type(limit) is not int or not 0 < limit < 2**31):
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        reuse_policy = validate_freshness(freshness, max_age_seconds)
        ticker = ticker.upper()
        legacy_key = f"{cache_prefix}_{ticker.upper()}_{period}"
        cache_key = f"fd_v1_{legacy_key}_{limit}"
        response_key = {"income": "income_statements", "balance": "balance_sheets",
                        "cashflow": "cash_flow_statements"}[cache_prefix]
        def read(max_age, not_before=None):
            return self._get_cache(cache_key, legacy_key, ticker, period, limit,
                                   response_key, freshness, max_age, not_before=not_before)

        def acquire():
            check_financial_work()
            if not self.api_key:
                raise FinancialDatasetsFailure("financial_datasets_api_key_missing")
            ttl_days = self._cache_days[period]
            if type(ttl_days) is not int or ttl_days < 0:
                raise FinancialDatasetsFailure("financial_datasets_cache_policy_invalid")
            try:
                datetime.now(timezone.utc) + timedelta(days=ttl_days)
            except OverflowError as exc:
                raise FinancialDatasetsFailure("financial_datasets_cache_policy_invalid") from exc
            data = self._request(endpoint, ticker=ticker, period=period, limit=limit)
            if not _valid_rows(data, response_key, ticker, period):
                raise FinancialDatasetsFailure("financial_datasets_response_invalid")
            fetched = datetime.now(timezone.utc)
            data = {**data, response_key: data[response_key][:limit]}
            check_financial_work()
            persisted = self._set_cache(cache_key, period, ticker, self._envelope(data, ticker, period, limit), now=fetched)
            return Observation(data, fetched, fetched, "refreshed", persisted)

        try:
            observation = reuse_or_acquire(reuse_policy,
                [storage_scope(self._cache_backend) if self._cache_backend is not None else str(_FILE_CACHE_DIR.resolve()),
                 "financial_datasets", cache_key], read, acquire)
        except ReuseFailure as exc:
            code = ("financial_datasets_cache_miss" if exc.code == "financial_stored_data_unavailable"
                    else exc.code.replace("financial_", "financial_datasets_", 1))
            raise FinancialDatasetsFailure(code) from exc
        data = observation.data
        self.observations.append(observation.describe("financial_datasets", response_key, reuse_policy,
            report_periods=[item["report_period"] for item in data[response_key]]))
        return data

    @staticmethod
    def _envelope(data, ticker, period, limit):
        return {"fd_cache_version": 1, "ticker": ticker.upper(), "period": period,
                "requested_limit": limit, "payload": data}

    def _cache_entries(self, key):
        if self._cache_backend is not None:
            try:
                row = self._cache_backend.get_financial_cache_entry(key)
                if isinstance(row, dict) and row.get("source") == "financial_datasets":
                    yield row, False
            except Exception as exc:
                logger.debug("FD cache metadata read failed (%s)", type(exc).__name__)
        try:
            row = json.loads((_FILE_CACHE_DIR / f"{key}.json").read_text())
            if isinstance(row, dict) and row.get("source", "financial_datasets") == "financial_datasets":
                yield row, True
        except (OSError, ValueError):
            pass

    def _get_cache(self, key, legacy_key, ticker, period, limit, response_key, freshness, max_age, *, not_before=None):
        for candidate in (key, legacy_key):
            for row, from_file in self._cache_entries(candidate):
                fetched = _instant(row.get("fetched_at"))
                expires = _instant(row.get("expires_at"))
                if fetched is None or expires is None or expires < fetched or row.get("ticker") != ticker.upper():
                    continue
                checked_at = datetime.now(timezone.utc)
                age = (checked_at - fetched).total_seconds()
                if (age < 0 or (max_age is not None and age > max_age)
                        or (not_before is not None and fetched < not_before)):
                    continue
                data = row.get("data")
                if candidate == key:
                    if (not isinstance(data, dict) or type(data.get("fd_cache_version")) is not int
                            or data["fd_cache_version"] != 1 or type(data.get("requested_limit")) is not int):
                        continue
                    if (data.get("ticker"), data.get("period"), data.get("requested_limit")) != (ticker.upper(), period, limit):
                        continue
                    data = data.get("payload")
                if not _valid_rows(data, response_key, ticker, period):
                    continue
                rows = data[response_key]
                # Old keys omitted request limit. A short response cannot prove
                # that a larger requested history was ever fetched.
                if candidate == legacy_key and len(rows) < limit:
                    continue
                data = {**data, response_key: rows[:limit]}
                if from_file and self._cache_backend is not None and freshness == "auto":
                    try:
                        self._cache_backend.set_financial_cache(
                            key, ticker, self._envelope(data, ticker, period, limit), source="financial_datasets",
                            fetched_at=fetched.isoformat(), expires_at=expires.isoformat(),
                        )
                    except Exception as exc:
                        logger.debug("FD cache promotion failed (%s)", type(exc).__name__)
                return Observation(data, fetched, checked_at)
        return None

    def retained_limit(self, ticker: str, period: str, prefix: str, requested: int, *, end_month=None) -> int:
        """Select one newest eligible retained response, independent of new preferences.

        This is inventory for the common stored reader, not permission for an
        undersized response to satisfy a larger auto/refresh request.
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", ticker):
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        ticker = ticker.upper()
        legacy = f"{prefix}_{ticker}_{period}"
        head = f"fd_v1_{legacy}_"
        response_key = {"income": "income_statements", "balance": "balance_sheets",
                        "cashflow": "cash_flow_statements"}[prefix]
        keys = set()
        if self._cache_backend is not None:
            try:
                stored = self._cache_backend.list_financial_cache_keys(ticker, "financial_datasets")
                if isinstance(stored, list):
                    keys.update(k for k in stored if isinstance(k, str))
            except (AttributeError, OSError):
                pass
        keys.update(path.stem for path in _FILE_CACHE_DIR.glob(f"{head}*.json"))
        limits = {requested}
        for key in keys:
            suffix = key.removeprefix(head)
            if key.startswith(head) and re.fullmatch(r"[1-9][0-9]{0,9}", suffix) and int(suffix) < 2**31:
                limits.add(int(suffix))
        for row, _ in self._cache_entries(legacy):
            data = row.get("data")
            if _valid_rows(data, response_key, ticker, period) and data[response_key]:
                limits.add(len(data[response_key]))
        candidates = []
        for limit in limits:
            observed = self._get_cache(f"{head}{limit}", legacy, ticker, period, limit, response_key, "stored", None)
            if observed is not None and (end_month is None or any(
                    row["report_period"][:7] == end_month for row in observed.data[response_key])):
                candidates.append((observed.fetched_at, limit))
        return max(candidates)[1] if candidates else requested

    def _set_cache(
        self, cache_key: str, period: str, ticker: str, data: Dict, *, now: Optional[datetime] = None,
    ) -> bool:
        """Persist a paid observation, with a file fallback on backend failure.

        Its acquisition timestamp is immutable during subsequent promotion.
        Retention TTL metadata does not decide whether a caller may reuse it.
        """
        ttl_days = self._cache_days.get(period, 90)
        now = now or datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)

        if self._cache_backend is not None:
            ok = False
            try:
                ok = bool(self._cache_backend.set_financial_cache(
                    cache_key, ticker, data,
                    ttl_days=ttl_days, source="financial_datasets",
                    fetched_at=now.isoformat(), expires_at=expires.isoformat(),
                ))
            except Exception as e:
                logger.debug(f"backend cache write raised: {e}")
            if ok:
                return True
            logger.warning(
                f"paid FD response for {cache_key} was NOT cached by the backend — "
                "writing a file copy for explicitly requested stored/auto reads")
            return self._write_file_cache(cache_key, ticker, data, now, expires)

        return self._write_file_cache(cache_key, ticker, data, now, expires)

    def _write_file_cache(
        self, cache_key: str, ticker: str, data: Dict,
        now: datetime, expires: datetime,
    ) -> bool:
        temporary = None
        try:
            _FILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _FILE_CACHE_DIR / f"{cache_key}.json"
            document = json.dumps({
                "fetched_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "source": "financial_datasets",
                "ticker": ticker,
                "data": data,
            }, indent=2, default=str)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=_FILE_CACHE_DIR, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(document)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            return True
        except Exception as e:
            logger.debug(f"File cache write failed: {e}")
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.debug("FD temporary cache cleanup failed")

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, **params: Any) -> Dict:
        """Consume self-contained cursors; every page has separate paid admission."""
        response_keys = {
            "/financials/income-statements": "income_statements",
            "/financials/balance-sheets": "balance_sheets",
            "/financials/cash-flow-statements": "cash_flow_statements",
        }
        if endpoint not in response_keys:
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        policy = FinancialDatasetsPolicy.from_config(self._request_policy)
        governor = self._governor or FinancialDatasetsGovernor()
        url = f"{self.BASE_URL}{endpoint}"
        response_key = response_keys[endpoint]
        rows, seen_periods, visited = [], set(), set()
        page_params = params
        while True:
            check_financial_work()
            visited.add(url)
            data = self._request_page(url, policy, governor, page_params)
            if not _valid_rows(data, response_key, params["ticker"], params["period"]):
                raise FinancialDatasetsFailure("financial_datasets_response_invalid")
            page_rows = data[response_key]
            for row in page_rows:
                identity = row["report_period"]
                if identity in seen_periods:
                    raise FinancialDatasetsFailure("financial_datasets_pagination_invalid")
                seen_periods.add(identity)
            rows.extend(page_rows)
            next_url = data.get("next_page_url")
            if len(rows) >= params["limit"] or next_url is None:
                # A cursor is ephemeral, not part of the retained observation.
                return {response_key: rows[:params["limit"]]}
            if not page_rows or not self._valid_page_url(next_url, endpoint) or next_url in visited:
                raise FinancialDatasetsFailure("financial_datasets_pagination_invalid")
            url, page_params = next_url, None

    def _valid_page_url(self, url, endpoint):
        if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            return False
        try:
            parsed, base = urlsplit(url), urlsplit(self.BASE_URL)
            query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
            return (parsed.scheme == base.scheme == "https" and parsed.netloc == base.netloc
                    and parsed.path == endpoint and not parsed.fragment
                    and len(query) == 1 and query[0][0] == "cursor" and bool(query[0][1]))
        except ValueError:
            return False

    def _request_page(self, url, policy, governor, params):
        """Admit one metered dispatch. No redirects or implicit retries."""
        check_financial_work()
        governor.reserve(self.api_key, policy)
        check_financial_work()
        headers = {"X-API-Key": self.api_key}

        resp = None
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30, allow_redirects=False)
            check_financial_work()
            if resp.status_code == 429:
                retry = resp.headers.get("Retry-After")
                if isinstance(retry, str):
                    try:
                        seconds = float(retry)
                    except ValueError:
                        try:
                            seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                        except (TypeError, ValueError, OverflowError):
                            seconds = 0
                    governor.defer(self.api_key, seconds)
                raise FinancialDatasetsFailure("financial_datasets_rate_limited")
            if resp.status_code in (301, 302, 303, 307, 308):
                raise FinancialDatasetsFailure("financial_datasets_redirect_refused")
            if resp.status_code == 402:
                raise FinancialDatasetsFailure("financial_datasets_payment_required")
            if resp.status_code in (401, 403):
                raise FinancialDatasetsFailure("financial_datasets_access_denied")
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise FinancialDatasetsFailure("financial_datasets_request_failed") from exc
        finally:
            if resp is not None:
                resp.close()

    # ------------------------------------------------------------------
    # Dataclass conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dataclass(cls: Type, data: Dict) -> Any:
        """Convert FD JSON dict to a dataclass instance.

        Only picks fields that exist in the dataclass definition,
        ignoring extra keys from the API response.
        """
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)
