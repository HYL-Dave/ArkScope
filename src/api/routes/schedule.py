"""
Schedule routes (slice 3e-D v1) — per-source data-collection scheduling.

The app/sidecar owns scheduling (locked user directive: no cron). Each source is
independent: its own enable flag + interval (profile_settings), parallel
execution where safe (IBKR sources serialize behind one Gateway lock). All
sources are DISABLED by default — nothing fetches until the user opts in.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.permissions import require_db_write, require_profile_state_write
from src.service.data_scheduler import (
    SOURCES,
    _SOURCE_LOCKS,
    job_name,
    run_source,
    set_source_config,
    status_snapshot,
)

router = APIRouter(tags=["schedule"])


@router.get("/schedule")
def get_schedule():
    """Per-source schedule config + runtime state (PURE READ)."""
    return {"sources": status_snapshot()}


class ScheduleUpdate(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = None


@router.put("/schedule/{source}")
def put_schedule(source: str, body: ScheduleUpdate):
    """Persist one source's enable flag / interval (profile_settings keys
    ``schedule.<source>.*`` — locked fork F3)."""
    if source not in SOURCES:
        raise HTTPException(status_code=404, detail=f"unknown source {source!r}")
    if body.enabled is None and body.interval_minutes is None:
        raise HTTPException(status_code=400, detail="nothing to update")
    require_profile_state_write("set_schedule", {
        "source": source, "enabled": body.enabled,
        "interval_minutes": body.interval_minutes,
    })
    cfg = set_source_config(source, enabled=body.enabled,
                            interval_minutes=body.interval_minutes)
    return {"source": source, **cfg}


@router.post("/schedule/run/{source}")
def run_now(source: str):
    """Run one source immediately (Run now), same path as the scheduler —
    collect → PG sync → local refresh — with trigger_source='api'.

    Fire-and-return: a collection can take minutes (IBKR over the universe), so
    the run executes on a background thread; the UI polls GET /schedule for the
    per-source ``running`` flag, ``last_result`` (every outcome INCLUDING skips —
    a cross-process skip writes no job_runs row, so this is the only place the UI
    can see "the CLI is already running this source"), and the job_runs row.
    "started" therefore means accepted-and-dispatched, not running-for-sure: the
    in-process lock check below is a fast path only; the thread re-checks both
    locks (in-process + cross-process flock) and may record a skip.
    """
    if source not in SOURCES:
        raise HTTPException(status_code=404, detail=f"unknown source {source!r}")
    from src.provider_config_runtime import require_provider_config_ready

    require_provider_config_ready("schedule_run_now")
    # EVERY source writes a database when run — provider sources end in PG sync +
    # local mirror refresh, and local_incremental writes market_data.db directly —
    # so the choke-point applies unconditionally (was provider-fetch-only, which
    # let local_incremental bypass require_db_write).
    require_db_write("schedule_run_now", {"source": source})
    if _SOURCE_LOCKS[source].locked():
        return {"source": source, "status": "skipped", "reason": "already running"}
    threading.Thread(target=run_source, args=(source, "api"),
                     name=f"runnow-{source}", daemon=True).start()
    return {"source": source, "status": "started", "job_name": job_name(source)}
