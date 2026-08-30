"""Application service for governed ticker identity transitions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Iterator, Mapping
from zoneinfo import ZoneInfo

from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    verify_profile_connection,
)
from src.ticker_identity_schema import (
    ATTEMPT_TRIGGERS,
    TickerIdentitySchemaMismatch,
    identity_schema_present,
    verify_ticker_identity_connection,
)
from src.ticker_identity_transition import (
    TickerIdentityTransitionStore,
    TransitionOptions,
    build_transition_preview,
)
from src.tools.security_lifecycle_tools import SecurityLifecycleReadService


TICKER_IDENTITY_STORE_UNAVAILABLE_REASONS = frozenset(
    {
        "identity_schema_absent",
        "identity_schema_mismatch",
        "profile_schema_mismatch",
        "profile_store_missing",
        "profile_store_unavailable",
    }
)


class TickerIdentityStoreUnavailable(RuntimeError):
    """The profile store cannot satisfy the exact ticker identity contract."""

    def __init__(
        self,
        store: str = "profile",
        *,
        reason: str = "profile_store_unavailable",
    ):
        if reason not in TICKER_IDENTITY_STORE_UNAVAILABLE_REASONS:
            raise ValueError("ticker_identity_store_unavailable_reason")
        super().__init__(store)
        self.store = store
        self.reason = reason


class TickerIdentityConflict(RuntimeError):
    """An attended command no longer matches its reviewed preview."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TickerIdentityService:
    """Compose lifecycle authority with profile-owned transition state."""

    def __init__(
        self,
        *,
        market_db_path: str,
        profile_db_path: str,
        source_loader: Callable[
            [], Mapping[str, Iterable[str]] | None
        ] | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ):
        read_kwargs = {
            "market_db_path": market_db_path,
            "profile_db_path": profile_db_path,
        }
        if source_loader is not None:
            read_kwargs["source_loader"] = source_loader
        self._read_service = SecurityLifecycleReadService(**read_kwargs)
        self.profile_db_path = profile_db_path
        self._clock = clock
        self._id_factory = id_factory

    @contextmanager
    def _profile_connection(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        path = Path(self.profile_db_path)
        conn: sqlite3.Connection | None = None
        try:
            if not path.is_file():
                raise TickerIdentityStoreUnavailable(reason="profile_store_missing")
            mode = "rw" if write else "ro"
            conn = sqlite3.connect(
                f"file:{path.resolve()}?mode={mode}",
                uri=True,
                timeout=10.0,
                check_same_thread=False,
            )
            verify_profile_connection(conn)
            if not identity_schema_present(conn):
                raise TickerIdentityStoreUnavailable(reason="identity_schema_absent")
            verify_ticker_identity_connection(conn)
        except TickerIdentityStoreUnavailable:
            if conn is not None:
                conn.close()
            raise
        except LifecycleSchemaMismatch:
            if conn is not None:
                conn.close()
            raise TickerIdentityStoreUnavailable(
                reason="profile_schema_mismatch"
            ) from None
        except TickerIdentitySchemaMismatch:
            if conn is not None:
                conn.close()
            raise TickerIdentityStoreUnavailable(
                reason="identity_schema_mismatch"
            ) from None
        except (OSError, sqlite3.Error):
            if conn is not None:
                conn.close()
            raise TickerIdentityStoreUnavailable() from None
        try:
            yield conn
        finally:
            conn.close()

    def _store(self, conn: sqlite3.Connection) -> TickerIdentityTransitionStore:
        return TickerIdentityTransitionStore(
            conn,
            clock=self._clock,
            id_factory=self._id_factory,
        )

    def _new_york_date(self) -> str:
        if self._clock is None:
            instant = datetime.now(timezone.utc)
        else:
            raw = self._clock()
            try:
                instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise ValueError("clock") from exc
            if instant.tzinfo is None:
                raise ValueError("clock")
        return instant.astimezone(ZoneInfo("America/New_York")).date().isoformat()

    def _preview_with_connection(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: str,
        options: TransitionOptions,
    ) -> dict:
        case = self._read_service.get_case(case_id)
        assessment = case.get("current_assessment")
        if not isinstance(assessment, Mapping):
            raise ValueError("accepted_assessment_required")
        fingerprint = case.get("observation_fingerprint_sha256")
        if not isinstance(fingerprint, str):
            raise ValueError("source_observation_missing")
        sources = (
            case.get("active_sources", ())
            if case.get("source_context") == "available"
            else None
        )
        return build_transition_preview(
            conn,
            case=case,
            assessment=assessment,
            proposals=case.get("proposals", ()),
            observation_fingerprint_sha256=fingerprint,
            sources=sources,
            options=options,
        )

    def preview_case(self, case_id: str, *, options: TransitionOptions) -> dict:
        with self._profile_connection(write=False) as conn:
            return self._preview_with_connection(
                conn,
                case_id=case_id,
                options=options,
            )

    def list_due_transitions(
        self,
        *,
        on_date: str,
        limit: int,
        allow_automation_approved: bool = True,
    ) -> list[dict]:
        with self._profile_connection(write=False) as conn:
            return self._store(conn).list_due(
                on_date=on_date,
                limit=limit,
                allow_automation_approved=allow_automation_approved,
            )

    def list_transition_activity(
        self,
        *,
        limit: int,
        unacknowledged_only: bool = False,
    ) -> dict:
        with self._profile_connection(write=False) as conn:
            return self._store(conn).list_activity(
                limit=limit,
                unacknowledged_only=unacknowledged_only,
            )

    def acknowledge_transition_activity(
        self,
        activity_id: str,
        *,
        before_write: Callable[[], None],
    ) -> dict:
        with self._profile_connection(write=True) as conn:
            store = self._store(conn)
            store.get_activity(activity_id)
            before_write()
            at = self._clock() if self._clock is not None else datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
            return store.acknowledge_activity(activity_id, at=at)

    def approve_case(
        self,
        case_id: str,
        *,
        options: TransitionOptions,
        preview_sha256: str,
        before_write: Callable[[], None],
    ) -> dict:
        with self._profile_connection(write=True) as conn:
            preview = self._preview_with_connection(
                conn,
                case_id=case_id,
                options=options,
            )
            if preview["preview_sha256"] != preview_sha256:
                raise TickerIdentityConflict("transition_preview_changed")
            if preview["eligible"] is not True:
                raise ValueError("preview_ineligible")
            before_write()
            try:
                return self._store(conn).approve(
                    preview=preview,
                    approved_preview_sha256=preview_sha256,
                )
            except ValueError as exc:
                if str(exc) == "preview_changed":
                    raise TickerIdentityConflict(
                        "transition_preview_changed"
                    ) from None
                raise

    def approve_automation_case(
        self,
        case_id: str,
        *,
        request: Mapping[str, object],
    ) -> dict:
        effective_date = str(request.get("effective_date") or "")
        with self._profile_connection(write=True) as conn:
            preview = self._preview_with_connection(
                conn,
                case_id=case_id,
                options=TransitionOptions(execute_on=effective_date),
            )
            expected = {
                "transition_kind": str(request.get("transition_kind") or ""),
                "source_ticker": str(request.get("source_ticker") or "").upper(),
                "successor_ticker": (
                    str(request["successor_ticker"]).upper()
                    if request.get("successor_ticker")
                    else None
                ),
                "execute_on": effective_date,
                "outcomes": sorted(
                    {str(value) for value in request.get("outcomes") or ()}
                ),
            }
            observed = {
                key: preview.get(key)
                for key in (
                    "transition_kind",
                    "source_ticker",
                    "successor_ticker",
                    "execute_on",
                    "outcomes",
                )
            }
            if observed != expected or preview.get("eligible") is not True:
                raise TickerIdentityConflict("transition_preview_changed")
            try:
                return self._store(conn).approve_automation(
                    preview=preview,
                    approved_preview_sha256=str(preview["preview_sha256"]),
                )
            except ValueError as exc:
                if str(exc) in {
                    "preview_changed",
                    "automation_authority_changed",
                }:
                    raise TickerIdentityConflict("transition_preview_changed") from None
                raise

    def cancel_transition(
        self,
        transition_id: str,
        *,
        before_write: Callable[[], None],
    ) -> dict:
        with self._profile_connection(write=True) as conn:
            store = self._store(conn)
            transition = store.get(transition_id)
            if transition["status"] not in {
                "approved",
                "needs_review",
                "cancelled",
            }:
                raise ValueError("transition_not_cancellable")
            before_write()
            return store.cancel(transition_id)

    def execute_transition(
        self,
        transition_id: str,
        *,
        preview_sha256: str,
        trigger: str = "attended_user",
        before_write: Callable[[], None],
    ) -> dict:
        if trigger not in ATTEMPT_TRIGGERS:
            raise ValueError("trigger")
        with self._profile_connection(write=True) as conn:
            store = self._store(conn)
            transition = store.get(transition_id)
            if transition["status"] not in {"approved", "applied"}:
                raise ValueError("transition_not_retryable")
            if preview_sha256 != transition["approved_preview_sha256"]:
                raise TickerIdentityConflict("transition_preview_changed")
            if transition["status"] == "applied":
                before_write()
                try:
                    return store.apply(
                        transition_id,
                        current_preview={"preview_sha256": preview_sha256},
                        expected_preview_sha256=preview_sha256,
                        trigger=trigger,
                    )
                except ValueError as exc:
                    if str(exc) == "request_preview_changed":
                        raise TickerIdentityConflict(
                            "transition_preview_changed"
                        ) from None
                    raise
            if (
                transition["status"] == "approved"
                and str(transition["execute_on"]) > self._new_york_date()
            ):
                raise ValueError("transition_not_due")
            try:
                preview = self._preview_with_connection(
                    conn,
                    case_id=str(transition["case_id"]),
                    options=TransitionOptions(
                        execute_on=str(transition["execute_on"]),
                        priority_resolution=transition["priority_resolution"],
                        unhide_successor=bool(transition["unhide_successor"]),
                    ),
                )
            except ValueError as exc:
                if str(exc) not in {
                    "accepted_assessment_required",
                    "source_observation_missing",
                }:
                    raise
                preview = None
            before_write()
            try:
                return store.apply(
                    transition_id,
                    current_preview=preview,
                    expected_preview_sha256=preview_sha256,
                    trigger=trigger,
                )
            except ValueError as exc:
                if str(exc) == "request_preview_changed":
                    raise TickerIdentityConflict(
                        "transition_preview_changed"
                    ) from None
                raise

    def reverse_transition(
        self,
        transition_id: str,
        *,
        before_write: Callable[[], None],
    ) -> dict:
        with self._profile_connection(write=True) as conn:
            store = self._store(conn)
            transition = store.get(transition_id)
            if transition["status"] != "applied":
                raise ValueError("transition_not_reversible")
            before_write()
            return store.reverse(transition_id, trigger="attended_user")

    def lineage_for_ticker(self, ticker: str) -> dict:
        with self._profile_connection(write=False) as conn:
            return self._store(conn).lineage_for_ticker(ticker)


def read_ticker_identity_lineage(profile_db_path: str, ticker: str) -> dict:
    """Read compact lineage without creating the optional identity component."""

    path = Path(profile_db_path)
    conn: sqlite3.Connection | None = None
    try:
        if not path.is_file():
            raise TickerIdentityStoreUnavailable(reason="profile_store_missing")
        conn = sqlite3.connect(
            f"file:{path.resolve()}?mode=ro",
            uri=True,
            timeout=10.0,
            check_same_thread=False,
        )
        if not identity_schema_present(conn):
            return {"predecessors": [], "successors": []}
        verify_ticker_identity_connection(conn)
        lineage = TickerIdentityTransitionStore(conn).lineage_for_ticker(ticker)
    except TickerIdentityStoreUnavailable:
        raise
    except TickerIdentitySchemaMismatch:
        raise TickerIdentityStoreUnavailable(
            reason="identity_schema_mismatch"
        ) from None
    except (OSError, sqlite3.Error):
        raise TickerIdentityStoreUnavailable() from None
    finally:
        if conn is not None:
            conn.close()
    return {
        "predecessors": [
            {
                "ticker": item["source_ticker"],
                "transition_id": item["transition_id"],
            }
            for item in lineage["predecessors"]
        ],
        "successors": [
            {
                "ticker": item["successor_ticker"],
                "transition_id": item["transition_id"],
            }
            for item in lineage["successors"]
        ],
    }


__all__ = [
    "TICKER_IDENTITY_STORE_UNAVAILABLE_REASONS",
    "TickerIdentityConflict",
    "TickerIdentityService",
    "TickerIdentityStoreUnavailable",
    "read_ticker_identity_lineage",
]
