"""Finnhub HTTP client for calendar endpoints (P1.2 commit 3).

Wraps three calendar endpoints:

  - ``/calendar/economic``  — macro release events with actual / estimate /
    prev and UTC-precise timestamps.
  - ``/calendar/earnings``  — per-symbol earnings calendar (unfiltered query
    under-samples the universe — see docs §5.5).
  - ``/calendar/ipo``       — IPO pipeline with full 4-state status enum.

Design notes:

  - **UTC datetime**: Finnhub returns ``time`` as ``"YYYY-MM-DD HH:MM:SS"``
    with no tz suffix. Smoke §5.2 confirms UTC: FOMC Decision at 19:00 in
    the response == 14:00 ET on 2024-12-18. We attach ``timezone.utc``
    immediately at parse time so callers always get tz-aware datetimes.
  - **Rate limit**: 60 calls/minute on the free tier. ``inter_call_delay_s``
    defaults to 1.1 s (just over 1 req/s) to avoid hitting the budget even
    with clock skew.
  - **Impact / hour / status normalisation**: values are lowercased and
    validated against the CHECK-constraint sets defined in the schema. An
    unrecognised impact → ``""``. An unrecognised status → row skipped
    (``_ipo_from_json`` returns None).
  - **No DB writes**: pure HTTP/parse layer. Persistence lives in
    ``src/p1_2/finnhub_ingestion.py``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
DEFAULT_TIMEOUT_S = 30
INTER_CALL_DELAY_S = 1.1  # 60 req/min → ~1 req/s; +0.1 s for clock slack


def _load_env_file_once() -> None:
    """Best-effort load of config/.env (mirrors fred_client pattern)."""
    if os.environ.get("_FINNHUB_CAL_CLIENT_ENV_LOADED") == "1":
        return
    here = Path(__file__).resolve()
    env_path = here.parent.parent / "config" / ".env"
    try:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        os.environ["_FINNHUB_CAL_CLIENT_ENV_LOADED"] = "1"
    except Exception as exc:
        logger.debug("Finnhub calendar client .env load failed: %s", exc)


# ---------------------------------------------------------------------------
# Dataclasses returned by the client
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinnhubEconomicEvent:
    """One row from /calendar/economic.

    ``event_time`` is UTC-aware. ``actual`` / ``estimate`` / ``prev`` are
    None for upcoming events (Finnhub populates them post-release).
    """

    country: str         # 2-letter ISO, uppercased
    event: str
    event_time: datetime  # UTC-aware
    impact: str           # low / medium / high / ""
    unit: str             # "" for observances / holidays
    actual: Optional[float]
    estimate: Optional[float]
    prev: Optional[float]


@dataclass(frozen=True)
class FinnhubEarningsEvent:
    """One row from /calendar/earnings."""

    symbol: str
    report_date: date
    year: int
    quarter: int          # 1–4
    hour: str             # bmo / amc / dmh / ""
    eps_estimate: Optional[float]
    eps_actual: Optional[float]
    revenue_estimate: Optional[float]
    revenue_actual: Optional[float]


@dataclass(frozen=True)
class FinnhubIPOEvent:
    """One row from /calendar/ipo.

    ``symbol`` and ``exchange`` may be None for pre-listing rows —
    smoke §5.3 found ~56 % null exchange on the free-tier sample.
    """

    name: str
    ipo_date: date
    symbol: Optional[str]
    exchange: Optional[str]
    status: str           # priced / filed / expected / withdrawn
    number_of_shares: Optional[int]
    price: Optional[float]
    total_shares_value: Optional[float]


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


_FINNHUB_TIME_FMT = "%Y-%m-%d %H:%M:%S"

_VALID_IMPACT = frozenset(("low", "medium", "high", ""))
_VALID_HOUR = frozenset(("bmo", "amc", "dmh", ""))
_VALID_STATUS = frozenset(("priced", "filed", "expected", "withdrawn"))


def _parse_finnhub_time(raw: Any) -> Optional[datetime]:
    """Parse "YYYY-MM-DD HH:MM:SS" → UTC-aware datetime.

    Smoke §5.2: FOMC Decision at ``"2024-12-18 19:00:00"`` = 14:00 ET → UTC.
    Returns None for empty / malformed inputs.
    """
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), _FINNHUB_TIME_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        logger.debug("unexpected Finnhub time format: %r", raw)
        return None


def _parse_opt_float(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_opt_int(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_iso_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _normalize_impact(raw: Any) -> str:
    v = str(raw or "").lower().strip()
    return v if v in _VALID_IMPACT else ""


def _normalize_hour(raw: Any) -> str:
    v = str(raw or "").lower().strip()
    return v if v in _VALID_HOUR else ""


# ---------------------------------------------------------------------------
# Row parsers (return None when required fields are missing / invalid)
# ---------------------------------------------------------------------------


def _economic_from_json(row: Dict[str, Any]) -> Optional[FinnhubEconomicEvent]:
    country = str(row.get("country") or "").strip().upper()
    event = str(row.get("event") or "").strip()
    event_time = _parse_finnhub_time(row.get("time"))
    if not country or not event or event_time is None:
        return None
    return FinnhubEconomicEvent(
        country=country,
        event=event,
        event_time=event_time,
        impact=_normalize_impact(row.get("impact")),
        unit=str(row.get("unit") or ""),
        actual=_parse_opt_float(row.get("actual")),
        estimate=_parse_opt_float(row.get("estimate")),
        prev=_parse_opt_float(row.get("prev")),
    )


def _earnings_from_json(row: Dict[str, Any]) -> Optional[FinnhubEarningsEvent]:
    symbol = str(row.get("symbol") or "").strip().upper()
    report_date = _parse_iso_date(row.get("date"))
    year_raw = row.get("year")
    quarter_raw = row.get("quarter")
    if not symbol or report_date is None or year_raw is None or quarter_raw is None:
        return None
    try:
        year = int(year_raw)
        quarter = int(quarter_raw)
    except (TypeError, ValueError):
        return None
    if not (1 <= quarter <= 4):
        return None
    return FinnhubEarningsEvent(
        symbol=symbol,
        report_date=report_date,
        year=year,
        quarter=quarter,
        hour=_normalize_hour(row.get("hour")),
        eps_estimate=_parse_opt_float(row.get("epsEstimate")),
        eps_actual=_parse_opt_float(row.get("epsActual")),
        revenue_estimate=_parse_opt_float(row.get("revenueEstimate")),
        revenue_actual=_parse_opt_float(row.get("revenueActual")),
    )


def _ipo_from_json(row: Dict[str, Any]) -> Optional[FinnhubIPOEvent]:
    name = str(row.get("name") or "").strip()
    ipo_date = _parse_iso_date(row.get("date"))
    status_raw = str(row.get("status") or "").lower().strip()
    if not name or ipo_date is None or status_raw not in _VALID_STATUS:
        return None
    return FinnhubIPOEvent(
        name=name,
        ipo_date=ipo_date,
        symbol=str(row.get("symbol") or "").strip() or None,
        exchange=str(row.get("exchange") or "").strip() or None,
        status=status_raw,
        number_of_shares=_parse_opt_int(row.get("numberOfShares")),
        price=_parse_opt_float(row.get("price")),
        total_shares_value=_parse_opt_float(row.get("totalSharesValue")),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FinnhubCalendarClient:
    """Thin sync wrapper around Finnhub calendar REST endpoints.

    Construct without args to read ``FINNHUB_API_KEY`` from
    ``config/.env``; pass ``api_key=...`` for tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = FINNHUB_BASE,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        inter_call_delay_s: float = INTER_CALL_DELAY_S,
        session: Optional[requests.Session] = None,
    ) -> None:
        if api_key is None:
            _load_env_file_once()
            api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            raise ValueError(
                "FINNHUB_API_KEY not set. Add it to config/.env or pass api_key=..."
            )
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._delay = max(0.0, float(inter_call_delay_s))
        self._session = session or requests.Session()
        self._last_call_ts: float = 0.0

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        if self._delay > 0:
            elapsed = time.monotonic() - self._last_call_ts
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)
        merged = {**params, "token": self._api_key}
        url = f"{self._base}{path}"
        try:
            resp = self._session.get(url, params=merged, timeout=self._timeout)
            self._last_call_ts = time.monotonic()
        except requests.RequestException as exc:
            raise FinnhubError(f"GET {path} failed: {exc}") from exc
        if resp.status_code == 401:
            raise FinnhubError(
                f"Finnhub 401 Unauthorized on {path} — check FINNHUB_API_KEY"
            )
        if resp.status_code == 429:
            raise FinnhubError(f"Finnhub rate limit hit on {path}")
        if resp.status_code >= 400:
            raise FinnhubError(
                f"Finnhub HTTP {resp.status_code} on {path}: {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise FinnhubError(f"Finnhub non-JSON body on {path}: {exc}") from exc

    def get_economic_events(
        self,
        date_from: date,
        date_to: date,
    ) -> List[FinnhubEconomicEvent]:
        """Return economic calendar events for [date_from, date_to].

        Both historical (actual populated) and upcoming (actual=null)
        events are returned on the free tier — smoke §5.2 confirmed.
        Rows missing country / event / time are silently skipped.
        """
        body = self._get(
            "/calendar/economic",
            {"from": date_from.isoformat(), "to": date_to.isoformat()},
        )
        rows = (body or {}).get("economicCalendar") or []
        return [e for r in rows if (e := _economic_from_json(r)) is not None]

    def get_earnings_events(
        self,
        date_from: date,
        date_to: date,
        *,
        symbol: Optional[str] = None,
    ) -> List[FinnhubEarningsEvent]:
        """Return earnings calendar events for [date_from, date_to].

        Pass ``symbol=`` for per-symbol precision. An unfiltered query
        may under-sample: smoke §5.5 showed AAPL absent from the
        unfiltered window but present with ``symbol="AAPL"``.
        """
        params: Dict[str, Any] = {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        }
        if symbol:
            params["symbol"] = symbol.upper()
        body = self._get("/calendar/earnings", params)
        rows = (body or {}).get("earningsCalendar") or []
        return [e for r in rows if (e := _earnings_from_json(r)) is not None]

    def get_ipo_events(
        self,
        date_from: date,
        date_to: date,
    ) -> List[FinnhubIPOEvent]:
        """Return IPO pipeline events for [date_from, date_to].

        Rows with missing name / date or unrecognised status are skipped.
        """
        body = self._get(
            "/calendar/ipo",
            {"from": date_from.isoformat(), "to": date_to.isoformat()},
        )
        rows = (body or {}).get("ipoCalendar") or []
        return [e for r in rows if (e := _ipo_from_json(r)) is not None]


class FinnhubError(RuntimeError):
    """Raised when the Finnhub API returns an unrecoverable error."""