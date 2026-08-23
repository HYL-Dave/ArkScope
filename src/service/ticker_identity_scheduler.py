"""Bounded provider-free execution of approved ticker identity transitions."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from zoneinfo import ZoneInfo

from src.api.permissions import require_profile_state_write
from src.ticker_identity_service import (
    TickerIdentityService,
    TickerIdentityStoreUnavailable,
)


logger = logging.getLogger(__name__)
_DEFAULT_LIMIT = 10


def _service() -> TickerIdentityService:
    from src.app_records_store import resolve_profile_state_db_path
    from src.market_data_admin import resolve_market_db_path

    return TickerIdentityService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=resolve_profile_state_db_path(None),
    )


def _new_york_date(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    return now.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def _empty_summary() -> dict:
    return {
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
    }


def run_due_ticker_identity_transitions(
    *,
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Run a bounded due batch without importing or calling data providers."""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("limit")
    instant = now or datetime.now(timezone.utc)
    on_date = _new_york_date(instant)
    service = _service()
    try:
        due = service.list_due_transitions(on_date=on_date, limit=limit)
    except TickerIdentityStoreUnavailable:
        return _empty_summary()

    summary = _empty_summary()
    summary["due"] = len(due)
    summary["transition_ids"] = [str(row["transition_id"]) for row in due]
    for transition in due:
        transition_id = str(transition["transition_id"])
        try:
            result = service.execute_transition(
                transition_id,
                preview_sha256=str(transition["approved_preview_sha256"]),
                trigger="scheduler",
                before_write=lambda transition_id=transition_id: (
                    require_profile_state_write(
                        "execute_approved_ticker_transition",
                        {"transition_id": transition_id},
                    )
                ),
            )
        except Exception as exc:  # one plan must never stop later plans
            logger.warning(
                "ticker transition execution failed transition_id=%s code=%s",
                transition_id,
                type(exc).__name__,
            )
            continue
        status = str(result.get("status") or "")
        if status == "applied":
            summary["applied"] += 1
        elif status == "already_applied":
            summary["already_applied"] += 1
        elif (
            status == "blocked"
            and result.get("transition", {}).get("status") == "needs_review"
        ):
            summary["needs_review"] += 1
    return summary


__all__ = ["run_due_ticker_identity_transitions"]
