"""FRED (Federal Reserve Economic Data) HTTP client.

Wraps the four endpoints P1.2 ingestion needs:

  - ``/fred/series``               — series metadata
  - ``/fred/series/observations``  — values, with optional ALFRED vintages
  - ``/fred/release/dates``        — scheduled release dates per release id
  - ``/fred/releases``             — release catalog (rarely needed; static)

Design notes:

  - **Offset-aware datetime parsing** for ``last_updated``. FRED returns
    timestamps with offset suffixes like ``-05`` (CST/EST) — naïve
    ``datetime.fromisoformat`` mishandles them on Python < 3.11. We use
    ``dateutil.parser`` so the result is always tz-aware UTC-equivalent.
  - **Missing-value coercion**: FRED encodes missing observations as the
    literal string ``"."``. Callers always get ``None`` instead.
  - **Vintage-aware observations**: the ``realtime_start`` /
    ``realtime_end`` / ``vintage_dates`` parameters thread through
    unchanged. Spec §3.2 requires we never invent a ``realtime_start``,
    so this client just returns whatever FRED gives us.
  - **No DB writes**: pure HTTP/parse layer. Persistence lives in
    ``src/p1_2/fred_ingestion.py``.

Rate limit (smoke §6): 2 req/s on the free tier, no daily cap. We keep a
small ``time.sleep`` inter-call delay so a batched ingestion won't blow
through the limit.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
DEFAULT_TIMEOUT_S = 30
INTER_CALL_DELAY_S = 0.55  # 2 req/s minus a small safety margin


def _load_env_file_once() -> None:
    """Best-effort load of config/.env into os.environ.

    Mirrors the pattern used by other ``data_sources/`` modules so a smoke
    script can import this module without an explicit env step.
    """
    if os.environ.get("_FRED_CLIENT_ENV_LOADED") == "1":
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
        os.environ["_FRED_CLIENT_ENV_LOADED"] = "1"
    except Exception as exc:  # pragma: no cover
        logger.debug("FRED client .env load failed: %s", exc)


@dataclass(frozen=True)
class FREDObservation:
    """One raw FRED observation row.

    ``value`` is ``None`` when FRED returned ``'.'`` (missing).
    ``realtime_start`` / ``realtime_end`` define the vintage window: the
    value was the published version between those dates inclusive of
    start and exclusive of end.
    """

    observation_date: date
    value: Optional[float]
    realtime_start: date
    realtime_end: date


@dataclass(frozen=True)
class FREDSeriesMetadata:
    """Schema-aligned subset of /fred/series response."""

    series_id: str
    title: str
    frequency: str           # 'd'/'w'/'bw'/'m'/'q'/'sa'/'a'
    units: str
    seasonal_adjustment: Optional[str]
    last_updated: Optional[datetime]  # tz-aware


@dataclass(frozen=True)
class FREDReleaseDate:
    release_id: int
    release_date: date


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_value(raw: Any) -> Optional[float]:
    """FRED uses '.' to mean missing. Coerce to None; otherwise float."""
    if raw is None or raw == "" or raw == ".":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_iso_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return date.fromisoformat(str(raw))


def _parse_offset_aware_dt(raw: Any) -> Optional[datetime]:
    """Parse FRED's '2026-04-10 08:08:04-05' style timestamp.

    Python 3.11+ ``datetime.fromisoformat`` handles `-05` natively, but we
    can't rely on that across the codebase. ``dateutil.parser.parse``
    handles every form we've seen plus exotic edge cases. Result is always
    tz-aware. Returns None for empty / unparseable inputs.
    """
    if raw is None or raw == "":
        return None
    try:
        # dateutil is already a transitive dep via pandas / pendulum.
        from dateutil import parser as _du_parser
        dt = _du_parser.parse(str(raw))
    except Exception:
        try:
            # Fallback: try Python's own ISO parser for "+00:00"-style strings.
            return datetime.fromisoformat(str(raw))
        except Exception:
            return None
    if dt.tzinfo is None:
        # Treat naive as UTC — FRED never returns naive in practice but
        # we'd rather over-specify than silently drift.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _observation_from_json(row: Dict[str, Any]) -> FREDObservation:
    return FREDObservation(
        observation_date=_parse_iso_date(row["date"]),
        value=_parse_value(row.get("value")),
        realtime_start=_parse_iso_date(row["realtime_start"]),
        realtime_end=_parse_iso_date(row["realtime_end"]),
    )


def _metadata_from_json(row: Dict[str, Any]) -> FREDSeriesMetadata:
    return FREDSeriesMetadata(
        series_id=str(row["id"]),
        title=str(row.get("title") or ""),
        frequency=str(row.get("frequency_short") or row.get("frequency") or ""),
        units=str(row.get("units") or row.get("units_short") or ""),
        seasonal_adjustment=row.get("seasonal_adjustment_short")
                             or row.get("seasonal_adjustment"),
        last_updated=_parse_offset_aware_dt(row.get("last_updated")),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FREDClient:
    """Thin sync wrapper around the FRED REST API.

    Construct without args to read ``FRED_API_KEY`` from
    ``config/.env``; pass ``api_key=...`` for tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = FRED_BASE,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        inter_call_delay_s: float = INTER_CALL_DELAY_S,
        session: Optional[requests.Session] = None,
    ) -> None:
        if api_key is None:
            _load_env_file_once()
            api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            raise ValueError(
                "FRED_API_KEY not set. Add it to config/.env or pass api_key=..."
            )
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._delay = max(0.0, float(inter_call_delay_s))
        self._session = session or requests.Session()
        self._last_call_ts: float = 0.0

    # -- raw GET ----------------------------------------------------------

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._delay > 0:
            elapsed = time.monotonic() - self._last_call_ts
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)
        merged = {**params, "api_key": self._api_key, "file_type": "json"}
        url = f"{self._base}{path}"
        try:
            resp = self._session.get(url, params=merged, timeout=self._timeout)
            self._last_call_ts = time.monotonic()
        except requests.RequestException as exc:
            raise FREDError(f"GET {path} failed: {exc}") from exc
        if resp.status_code == 429:
            raise FREDError(f"FRED rate limit hit on {path}")
        if resp.status_code >= 400:
            raise FREDError(
                f"FRED HTTP {resp.status_code} on {path}: {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise FREDError(f"FRED non-JSON body on {path}: {exc}") from exc

    # -- public endpoints -------------------------------------------------

    def get_series_metadata(self, series_id: str) -> Optional[FREDSeriesMetadata]:
        body = self._get("/series", {"series_id": series_id})
        rows = body.get("seriess") or []
        if not rows:
            return None
        return _metadata_from_json(rows[0])

    def get_observations(
        self,
        series_id: str,
        *,
        observation_start: Optional[date] = None,
        observation_end: Optional[date] = None,
        realtime_start: Optional[date] = None,
        realtime_end: Optional[date] = None,
        vintage_dates: Optional[Sequence[date]] = None,
        limit: Optional[int] = None,
        sort_order: str = "asc",
        output_type: Optional[int] = None,
    ) -> List[FREDObservation]:
        """Return observations for ``series_id``.

        Vintage selection: ``realtime_start`` + ``realtime_end`` give a
        single as-of vintage; ``vintage_dates`` gives a comma-separated
        list of explicit snapshots; ``output_type`` controls the row
        shape:

          - 1 (default): "By Real-Time Period" — one row per
            [realtime_start, realtime_end) window. The natural
            full-revision history shape; this is what our parser
            expects and what ``full_vintages`` ingestion uses.
          - 2 / 3: wide-format rows with ``SERIES_YYYYMMDD`` keys.
            **Not supported by this client's parser** — requesting
            these raises ``ValueError`` at call time.
          - 4: "Initial Release Only" — one row matching the first
            publication realtime window. Used by ``latest_only``
            ingestion.

        See ``docs/design/P1_2_PROVIDER_DISCOVERY.md`` §6.3 for the
        live-call evidence behind this mapping.
        """
        params: Dict[str, Any] = {
            "series_id": series_id,
            "sort_order": sort_order,
        }
        if observation_start is not None:
            params["observation_start"] = observation_start.isoformat()
        if observation_end is not None:
            params["observation_end"] = observation_end.isoformat()
        if realtime_start is not None:
            params["realtime_start"] = realtime_start.isoformat()
        if realtime_end is not None:
            params["realtime_end"] = realtime_end.isoformat()
        if vintage_dates:
            params["vintage_dates"] = ",".join(d.isoformat() for d in vintage_dates)
        if limit is not None:
            params["limit"] = int(limit)
        if output_type is not None:
            if output_type not in (1, 4):
                raise ValueError(
                    "Only output_type=1 (real-time periods) and =4 "
                    "(initial release) are supported by this client; "
                    "=2/=3 return wide-format rows the parser doesn't handle."
                )
            params["output_type"] = int(output_type)
        body = self._get("/series/observations", params)
        return [
            _observation_from_json(r)
            for r in (body.get("observations") or [])
        ]

    def get_release_dates(
        self,
        release_id: int,
        *,
        limit: int = 200,
        sort_order: str = "desc",
    ) -> List[FREDReleaseDate]:
        body = self._get(
            "/release/dates",
            {
                "release_id": int(release_id),
                "limit": int(limit),
                "sort_order": sort_order,
                "include_release_dates_with_no_data": "false",
            },
        )
        return [
            FREDReleaseDate(
                release_id=int(r["release_id"]),
                release_date=_parse_iso_date(r["date"]),
            )
            for r in (body.get("release_dates") or [])
        ]


class FREDError(RuntimeError):
    """Raised when the FRED API returns an unrecoverable error."""