"""
Financial Datasets API client with a local-primary caching layer.

Wraps the paid Financial Datasets API (https://financialdatasets.ai)
with a caching layer to minimize API costs. Financial statements
rarely change (quarterly updates), so long TTLs are appropriate.

Cache modes (3c-C unification — the paid path uses the SAME cache contract as the
SEC metrics path):
  - ``cache_backend`` provided (the DAL's backend, normal app path): reads go
    ``cache_backend.get_financial_cache`` — which LocalMarketDatabaseBackend makes
    LOCAL-PRIMARY (local market DB first, PG legacy fallback + read-through
    promotion) — then the legacy file cache (read-only; a hit is promoted into the
    backend with its remaining TTL), then the API. Writes go ONLY to
    ``cache_backend.set_financial_cache`` (local-primary; never the client's own PG
    connection, no new file writes).
  - ``cache_backend=None`` (standalone scripts/tests): legacy behavior unchanged —
    env-``DATABASE_URL`` PG → file → API, writes to PG + file.

Usage:
    from data_sources.financial_datasets_client import FinancialDatasetsClient

    client = FinancialDatasetsClient(cache_backend=dal._backend)
    stmts = client.get_income_statements("AAPL", period="quarterly", limit=4)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import requests

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
    ):
        """``cache_backend`` is the DAL's data backend (duck-typed:
        ``get_financial_cache(cache_key)`` + ``set_financial_cache(...)``). When set,
        ALL cache writes go through it (local-primary via LocalMarketDatabaseBackend)
        and the client's own env-PG connection is never used. When None, the legacy
        standalone behavior (env-PG + file) is unchanged."""
        self.api_key = api_key or os.getenv("FINANCIAL_DATASETS_API_KEY")
        self._db_url = os.getenv("DATABASE_URL")
        self._cache_backend = cache_backend if (
            cache_backend is not None
            and hasattr(cache_backend, "get_financial_cache")
            and hasattr(cache_backend, "set_financial_cache")
        ) else None
        self._cache_days = {**_DEFAULT_TTL, **(cache_days or {})}

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
        """Backend (local-primary) → file (legacy, promoted) → None; or the legacy
        env-PG → file order when no cache_backend was provided."""
        # 1. The DAL backend cache (local market DB first w/ PG legacy fallback +
        #    promotion when routing is on — see LocalMarketDatabaseBackend).
        if self._cache_backend is not None:
            try:
                row = self._cache_backend.get_financial_cache(cache_key)
                if row is not None:
                    return row
            except Exception as e:
                logger.debug(f"backend cache read failed: {e}")
        elif self._db_url:  # legacy standalone: the client's own PG connection
            try:
                row = self._db_get(cache_key)
                if row is not None:
                    return row
            except Exception as e:
                logger.debug(f"DB cache read failed: {e}")

        # 2. File cache (legacy). With a cache_backend this is READ-ONLY fallback for
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
        goes through it (local-primary; never the client's own PG) — the local
        market DB plays the file cache's old offline role. The legacy file write
        happens ONLY if the backend write fails: the response is PAID, and with a
        single sink a silent write failure would mean every subsequent call re-pays
        (legacy mode had two independent sinks). The file fallback restores that
        second failure domain, and the next read self-heals it back into the
        backend via the file→backend promotion. Legacy standalone mode keeps the
        old PG + file dual write."""
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

        # legacy standalone: PG + file dual write
        if self._db_url:
            try:
                self._db_upsert(cache_key, ticker, data, now, expires)
            except Exception as e:
                logger.debug(f"DB cache write failed: {e}")
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
    # DB helpers
    # ------------------------------------------------------------------

    def _db_get(self, cache_key: str) -> Optional[Dict]:
        """Get cached data from DB if not expired."""
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(self._db_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT data FROM financial_data_cache "
                    "WHERE cache_key = %s AND expires_at > NOW()",
                    [cache_key],
                )
                row = cur.fetchone()
                return row["data"] if row else None

    def _db_upsert(
        self,
        cache_key: str,
        ticker: str,
        data: Dict,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Insert or update cache entry."""
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO financial_data_cache
                        (cache_key, source, ticker, data, fetched_at, expires_at)
                    VALUES (%s, 'financial_datasets', %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        data = EXCLUDED.data,
                        fetched_at = EXCLUDED.fetched_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    [
                        cache_key,
                        ticker.upper(),
                        psycopg2.extras.Json(data),
                        fetched_at,
                        expires_at,
                    ],
                )
            conn.commit()

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, **params: Any) -> Dict:
        """Make authenticated GET request to Financial Datasets API."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-API-Key": self.api_key}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Financial Datasets API error: {e}")
            return {}

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