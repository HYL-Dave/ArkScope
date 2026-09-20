"""Financial Datasets requests with explicit stored/auto/refresh semantics.

The default refresh bypasses saved data and still requires paid admission.
Stored reads never dispatch or promote files. Auto requires an explicit maximum
acquisition age, independent of the statement's fiscal period. Cache retention
settings do not assert freshness. Paid responses retain the local/file fallback;
observations expose original acquisition time without claiming latest filings.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import requests

from .financial_datasets_governance import (
    FinancialDatasetsFailure, FinancialDatasetsGovernor, FinancialDatasetsPolicy,
)
from .sec_edgar_financials import (
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
    if (freshness not in ("stored", "auto", "refresh")
            or (max_age_seconds is not None and (type(max_age_seconds) is not int or max_age_seconds < 0))
            or (freshness == "auto" and max_age_seconds is None)
            or (freshness == "refresh" and max_age_seconds is not None)):
        raise FinancialDatasetsFailure("financial_datasets_freshness_invalid")


def _instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


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
    """Paid financial statements with opt-in, acquisition-dated cache reads."""

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
        *, freshness: str = "refresh", max_age_seconds: Optional[int] = None,
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
        *, freshness: str = "refresh", max_age_seconds: Optional[int] = None,
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
        *, freshness: str = "refresh", max_age_seconds: Optional[int] = None,
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
        if (not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", ticker)
                or period not in _DEFAULT_TTL or type(limit) is not int or limit < 1):
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        validate_freshness(freshness, max_age_seconds)
        legacy_key = f"{cache_prefix}_{ticker.upper()}_{period}"
        cache_key = f"fd_v1_{legacy_key}_{limit}"
        response_key = {"income": "income_statements", "balance": "balance_sheets",
                        "cashflow": "cash_flow_statements"}[cache_prefix]
        if freshness != "refresh":
            cached = self._get_cache(cache_key, legacy_key, ticker, period, limit,
                                     response_key, freshness, max_age_seconds)
            if cached is not None:
                data, fetched, checked_at = cached
                self._observe(response_key, data, fetched, "stored", freshness, max_age_seconds, now=checked_at)
                return data
            if freshness == "stored":
                raise FinancialDatasetsFailure("financial_datasets_cache_miss")

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
        self._set_cache(cache_key, period, ticker, self._envelope(data, ticker, period, limit), now=fetched)
        self._observe(response_key, data, fetched, "refreshed", freshness, max_age_seconds)
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

    def _get_cache(self, key, legacy_key, ticker, period, limit, response_key, freshness, max_age):
        for candidate in (key, legacy_key):
            for row, from_file in self._cache_entries(candidate):
                fetched = _instant(row.get("fetched_at"))
                expires = _instant(row.get("expires_at"))
                if fetched is None or expires is None or expires < fetched or row.get("ticker") != ticker.upper():
                    continue
                checked_at = datetime.now(timezone.utc)
                age = (checked_at - fetched).total_seconds()
                if age < 0 or (max_age is not None and age > max_age):
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
                return data, fetched, checked_at
        return None

    def _observe(self, dataset, data, fetched, retrieval, freshness, max_age, *, now=None):
        now = now or datetime.now(timezone.utc)
        age = (now - fetched).total_seconds()
        self.observations.append({
            "provider": "financial_datasets", "dataset": dataset, "retrieval": retrieval,
            "freshness_mode": freshness, "fetched_at": fetched.isoformat(), "evaluated_at": now.isoformat(),
            "age_seconds": age, "max_age_seconds": max_age,
            "within_max_age": None if max_age is None else 0 <= age <= max_age,
            "latest_period_verified": False,
            "report_periods": [item["report_period"] for item in data[dataset] if isinstance(item.get("report_period"), str)],
        })

    def _set_cache(
        self, cache_key: str, period: str, ticker: str, data: Dict, *, now: Optional[datetime] = None,
    ) -> None:
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
                return
            logger.warning(
                f"paid FD response for {cache_key} was NOT cached by the backend — "
                "writing a file copy for explicitly requested stored/auto reads")
            self._write_file_cache(cache_key, ticker, data, now, expires)
            return

        self._write_file_cache(cache_key, ticker, data, now, expires)

    def _write_file_cache(
        self, cache_key: str, ticker: str, data: Dict,
        now: datetime, expires: datetime,
    ) -> None:
        try:
            _FILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _FILE_CACHE_DIR / f"{cache_key}.json"
            path.write_text(json.dumps({
                "fetched_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "source": "financial_datasets",
                "ticker": ticker,
                "data": data,
            }, indent=2, default=str))
        except Exception as e:
            logger.debug(f"File cache write failed: {e}")

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, **params: Any) -> Dict:
        """Admit one metered dispatch. No redirects or implicit retries."""
        response_keys = {
            "/financials/income-statements": "income_statements",
            "/financials/balance-sheets": "balance_sheets",
            "/financials/cash-flow-statements": "cash_flow_statements",
        }
        if endpoint not in response_keys:
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        policy = FinancialDatasetsPolicy.from_config(self._request_policy)
        governor = self._governor or FinancialDatasetsGovernor()
        governor.reserve(self.api_key, policy)
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-API-Key": self.api_key}

        resp = None
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30, allow_redirects=False)
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
            data = resp.json()
            rows = data.get(response_keys[endpoint]) if isinstance(data, dict) else None
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise FinancialDatasetsFailure("financial_datasets_response_invalid")
            return data
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
