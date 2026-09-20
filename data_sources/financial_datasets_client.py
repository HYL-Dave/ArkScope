"""
Financial Datasets API client with a local-primary caching layer.

Wraps the paid Financial Datasets API (https://financialdatasets.ai)
with a caching layer to minimize API costs. Financial statements
rarely change (quarterly updates), so long TTLs are appropriate.

Cache modes (3c-C unification — the paid path uses the SAME cache contract as the
SEC metrics path):
  - ``cache_backend`` provided (the DAL's backend, normal app path): reads go
    ``cache_backend.get_financial_cache`` in the local market DB, then the legacy
    file cache (read-only; a hit is promoted into the backend with its remaining
    TTL), then the API. Writes go to ``cache_backend.set_financial_cache``. The
    healthy path writes no files — but if the backend write FAILS
    (False/raise), the legacy file cache is written as a deliberate fallback: the
    response is PAID, and with a single sink a silent write failure would mean every
    subsequent call re-pays. Do NOT remove that fallback; the next read self-heals
    it into the backend via the file→backend promotion.
  - ``cache_backend=None`` (standalone scripts/tests): file → API, with file writes.

Usage:
    from data_sources.financial_datasets_client import FinancialDatasetsClient

    client = FinancialDatasetsClient(cache_backend=dal._backend)
    stmts = client.get_income_statements("AAPL", period="quarterly", limit=4)

Without an explicit request_policy this only serves caches. Paid misses need
enabled=True, daily_request_limit and the account's requests_per_minute. The
governor counts attempted HTTP requests, not dollars or provider credit balance.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import fields
from datetime import datetime, timedelta, timezone
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


class FinancialDatasetsClient:
    """Financial Datasets API client with a local-primary caching layer."""

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_income_statements(
        self,
        ticker: str,
        period: str = "quarterly",
        limit: int = 4,
    ) -> List[IncomeStatement]:
        """Get income statements. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/income-statements",
            cache_prefix="income",
            ticker=ticker,
            period=period,
            limit=limit,
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
    ) -> List[BalanceSheet]:
        """Get balance sheets. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/balance-sheets",
            cache_prefix="balance",
            ticker=ticker,
            period=period,
            limit=limit,
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
    ) -> List[CashFlowStatement]:
        """Get cash flow statements. Returns dataclass instances."""
        raw = self._cached_request(
            endpoint="/financials/cash-flow-statements",
            cache_prefix="cashflow",
            ticker=ticker,
            period=period,
            limit=limit,
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
    ) -> Dict[str, Any]:
        """Check cache → call API → store in cache."""
        if (not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", ticker)
                or period not in _DEFAULT_TTL or type(limit) is not int or limit < 1):
            raise FinancialDatasetsFailure("financial_datasets_query_invalid")
        cache_key = f"{cache_prefix}_{ticker.upper()}_{period}"

        # 1. Try cache
        cached = self._get_cache(cache_key, period)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        # 2. Call API
        if not self.api_key:
            logger.warning("No FINANCIAL_DATASETS_API_KEY — skipping API call")
            return {}

        data = self._request(endpoint, ticker=ticker, period=period, limit=limit)

        # 3. Store in cache
        if data:
            self._set_cache(cache_key, period, ticker, data)

        return data

    def _get_cache(self, cache_key: str, period: str) -> Optional[Dict]:
        """Local cache owner → file fallback → miss."""
        if self._cache_backend is not None:
            try:
                row = self._cache_backend.get_financial_cache(cache_key)
                if row is not None:
                    return row
            except Exception as e:
                logger.debug(f"backend cache read failed: {e}")
        # File cache. With a cache_backend this is a read-only fallback for
        #    pre-unification entries; a hit is promoted into the backend with its
        #    remaining TTL so the file cache migrates into the local-primary store.
        ttl_days = self._cache_days.get(period, 90)
        path = _FILE_CACHE_DIR / f"{cache_key}.json"
        if path.exists():
            try:
                content = json.loads(path.read_text())
                fetched = datetime.fromisoformat(content["fetched_at"])
                if fetched.tzinfo is None:
                    fetched = fetched.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - fetched).days
                if age_days < ttl_days:
                    data = content["data"]
                    if self._cache_backend is not None:
                        # Promotion failure is debug-only: the file hit is still
                        # returned (no paid call), and behavior degrades to exactly
                        # the legacy file-cache lifetime. NOTE: the promoted row's
                        # expires_at is preserved via the remaining TTL, but its
                        # fetched_at resets to now (the backend's set() does not
                        # forward timestamps) — metadata-only skew; expiry, the only
                        # field reads consult, stays correct.
                        try:
                            remaining = max(1, ttl_days - age_days)
                            self._cache_backend.set_financial_cache(
                                cache_key, content.get("ticker", ""), data,
                                ttl_days=remaining, source="financial_datasets",
                            )
                        except Exception as e:
                            logger.debug(f"file→backend cache promotion skipped: {e}")
                    return data
            except Exception as e:
                logger.debug(f"File cache read failed: {e}")

        return None

    def _set_cache(
        self, cache_key: str, period: str, ticker: str, data: Dict,
    ) -> None:
        """Cache a fresh API response (best-effort). With a cache_backend the write
        goes through the local market DB. The legacy file write
        happens ONLY if the backend write fails: the response is PAID, and with a
        single sink a silent write failure would mean every subsequent call re-pays
        (legacy mode had two independent sinks). The file fallback restores that
        second failure domain, and the next read self-heals it back into the
        backend via the file→backend promotion. Standalone mode writes the file."""
        ttl_days = self._cache_days.get(period, 90)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)

        if self._cache_backend is not None:
            ok = False
            try:
                ok = bool(self._cache_backend.set_financial_cache(
                    cache_key, ticker, data,
                    ttl_days=ttl_days, source="financial_datasets",
                ))
            except Exception as e:
                logger.debug(f"backend cache write raised: {e}")
            if ok:
                return
            logger.warning(
                f"paid FD response for {cache_key} was NOT cached by the backend — "
                "writing the legacy file cache so the next call does not re-pay")
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
