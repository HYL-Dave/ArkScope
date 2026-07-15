"""Provider-free portfolio activity and annotation routes."""

from __future__ import annotations

from dataclasses import asdict
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_portfolio_activity_store
from src.api.permissions import require_profile_state_write
from src.portfolio_activity import (
    ActivityFilters,
    ActivitySource,
    ActivityState,
    ActivityTargetNotFound,
    PortfolioActivityStore,
)


router = APIRouter(prefix="/portfolio/activity", tags=["portfolio"])


class PortfolioActivityAnnotationBody(BaseModel):
    intent_label: Literal[
        "profit_take",
        "stop_loss",
        "rebalance",
        "thesis_broken",
        "cash_need",
        "other",
    ] | None = None
    note: str = ""


def _invalid_activity(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "invalid_portfolio_activity", "detail": str(exc)},
    )


def _missing_activity_target() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "portfolio_activity_not_found"},
    )


def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "portfolio_activity_unavailable", "action": "retry"},
    )


@router.get("")
def get_activity(
    date_from_et: str | None = None,
    date_to_et: str | None = None,
    account_id: int | None = None,
    symbol: str | None = None,
    source: ActivitySource | None = None,
    state: ActivityState | None = None,
    recent: bool = False,
    limit: int = 100,
    cursor: str | None = None,
    store: PortfolioActivityStore = Depends(get_portfolio_activity_store),
) -> dict:
    filters = ActivityFilters(
        date_from_et=date_from_et,
        date_to_et=date_to_et,
        account_id=account_id,
        symbol=symbol,
        source=source,
        state=state,
        recent=recent,
        limit=limit,
        cursor=cursor,
    )
    try:
        return asdict(store.list_activity(filters))
    except sqlite3.Error as exc:
        raise _storage_unavailable() from exc
    except ValueError as exc:
        raise _invalid_activity(exc) from exc


@router.put("/annotations/{activity_id}")
def put_annotation(
    activity_id: str,
    body: PortfolioActivityAnnotationBody,
    store: PortfolioActivityStore = Depends(get_portfolio_activity_store),
) -> dict:
    require_profile_state_write(
        "portfolio_activity_annotation_write",
        {"activity_id": activity_id, "action": "replace"},
    )
    try:
        return asdict(
            store.put_annotation(
                activity_id,
                intent_label=body.intent_label,
                note=body.note,
            )
        )
    except ActivityTargetNotFound as exc:
        raise _missing_activity_target() from exc
    except sqlite3.Error as exc:
        raise _storage_unavailable() from exc
    except ValueError as exc:
        raise _invalid_activity(exc) from exc


@router.delete("/annotations/{activity_id}")
def delete_annotation(
    activity_id: str,
    store: PortfolioActivityStore = Depends(get_portfolio_activity_store),
) -> dict:
    require_profile_state_write(
        "portfolio_activity_annotation_write",
        {"activity_id": activity_id, "action": "delete"},
    )
    try:
        deleted = store.delete_annotation(activity_id)
    except ActivityTargetNotFound as exc:
        raise _missing_activity_target() from exc
    except sqlite3.Error as exc:
        raise _storage_unavailable() from exc
    except ValueError as exc:
        raise _invalid_activity(exc) from exc
    return {"activity_id": activity_id, "deleted": deleted}
