"""App-records PG→local migration routes (PG-exit 1c-api).

Exposes the migration as TWO explicit endpoints (gate #5): a read-only dry-run preview and an
explicit apply (backs up profile_state.db first, id-preserving, refuses on conflict). Both read
the LIVE PG side via PgAppRecordsSource — so they require a PG-backed DAL; in a PG-less/strict
runtime they return a clear 'PG not available' rather than failing opaquely.

NO use_local_records toggle here (gate #1): flipping local-on belongs AFTER a successful
migration, lest the local store's autoincrement collide with the id-preserving migrated rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_dal
from src.api.permissions import require_profile_state_write
from src.app_records_migrate import (
    PgAppRecordsSource,
    apply_migration,
    preview_migration,
)
from src.app_records_store import AppRecordsLocalStore, resolve_profile_state_db_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app-records", tags=["app-records"])


def _source(dal):
    source = PgAppRecordsSource(getattr(dal, "_backend", None))
    if not source.available:
        raise HTTPException(
            status_code=409,
            detail="App-records migration requires a reachable PostgreSQL backend (it reads the "
                   "PG rows). The current DAL has no PG connection.")
    return source


def _base(dal):
    return str(getattr(dal, "_base", "") or "") or None


@router.get("/migration/preview")
def migration_preview(dal=Depends(get_dal)):
    """DRY-RUN: per-table PG vs local counts, max ids, conflicts, missing files. Reads PG +
    local read-only; writes NOTHING (the local store is opened no-create — preview must not
    materialize profile_state.db). ``would_apply`` false ⇒ apply would refuse."""
    source = _source(dal)
    local = AppRecordsLocalStore(resolve_profile_state_db_path(dal), create=False)  # fix #1
    try:
        return preview_migration(source, local, base=_base(dal))
    except HTTPException:
        raise
    except Exception as e:  # fix #3: PG connect/SQL error → 409, not an opaque 500
        logger.warning("app-records migration preview failed: %s", e)
        raise HTTPException(status_code=409, detail=f"PG read failed: {e}")


@router.post("/migration/apply")
def migration_apply(dal=Depends(get_dal)):
    """APPLY (explicit, gated): backup profile_state.db → conflict guard → ATOMIC id-preserving
    inserts (all-or-nothing). 409 on a same-id-different-content conflict (nothing written) or
    when PG is unreadable."""
    require_profile_state_write("migrate_app_records", {})
    source = _source(dal)
    # create=False so the constructor doesn't DDL — apply_migration backs up FIRST, then creates
    # the tables (backup-before-write). Unique timestamped backup name so a re-run can never
    # clobber the original pre-migration snapshot (backup_profile_state_db also refuses to
    # overwrite as belt-and-suspenders).
    local = AppRecordsLocalStore(resolve_profile_state_db_path(dal), create=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    try:
        return apply_migration(source, local, base=_base(dal), backup=True, now_stamp=stamp)
    except HTTPException:
        raise
    except RuntimeError as e:        # conflict guard / incomplete-write
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:           # fix #3: PG connect/SQL error → 409
        logger.warning("app-records migration apply failed: %s", e)
        raise HTTPException(status_code=409, detail=f"migration failed: {e}")
