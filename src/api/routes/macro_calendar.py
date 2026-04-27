"""Macro/calendar API routes (P1.2 commit 5).

Currently exposes only ``/macro/health``. Read endpoints + agent tool
surface land in commit 6 — this file is intentionally narrow so the
health module can ship without coupling to read-side decisions still
in design.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.agents.config import get_agent_config
from src.api.dependencies import get_dal
from src.service.macro_calendar_health import compute_macro_calendar_health

router = APIRouter(prefix="/macro", tags=["macro_calendar"])

_DISABLED_MSG = (
    "macro_calendar.enabled is false in config. Enable it in "
    "config/user_profile.yaml to activate the FRED + Finnhub calendar layer."
)


@router.get("/health")
def macro_calendar_health(
    response: Response,
    strict: bool = Query(False, description="Return 503 when severity != ok."),
    dal=Depends(get_dal),
):
    """Return macro_calendar pipeline health.

    Two layers reported separately so callers can tell job-cadence
    staleness from table-level coverage gaps:

      - ``jobs``    last successful run per ingestion job vs expected
                    cadence (hourly / 4h / daily / weekly)
      - ``tables``  ``MAX(fetched_at)`` + row_count per macro/cal table

    Severity ladder: ``ok`` / ``warning`` / ``critical``. Default returns
    200 with the structured payload regardless. ``?strict=true`` upgrades
    any non-``ok`` severity to HTTP 503 for healthcheck-style probes.
    """
    if not get_agent_config().macro_calendar_enabled:
        raise HTTPException(status_code=503, detail=_DISABLED_MSG)

    report = compute_macro_calendar_health(dal)
    if strict and report.get("severity") != "ok":
        response.status_code = 503
    return report