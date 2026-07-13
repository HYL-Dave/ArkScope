"""Portfolio capture orchestration and redacted review projections."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Callable, ContextManager, Literal

from data_sources.ibkr_client_id import ibkr_client_id_for
from src.ibkr_gateway_lock import FileLock, ibkr_gateway_lock
from src.portfolio_capture_types import (
    BrokerCaptureResult,
    CaptureCommitResult,
    CaptureRun,
    CaptureRunNotReviewable,
    CaptureRunState,
    CaptureRunSuperseded,
    CaptureTrigger,
    PortfolioCaptureBusy,
    ProviderReadiness,
)
from src.portfolio_ibkr import (
    BrokerSnapshot,
    PortfolioSyncPreview,
    preview_or_apply_ibkr_snapshot,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore, portfolio_account_hash


DEFAULT_CAPTURE_INTERVAL_MINUTES = 15


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CaptureStart:
    accepted: bool
    run: CaptureRun | None
    state: CaptureRunState
    error_code: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class EffectiveCaptureSettings:
    enabled: bool
    interval_minutes: int
    source: Literal["default", "database"]
    provider_configured: bool


@dataclass(frozen=True)
class PortfolioCaptureStatus:
    settings: EffectiveCaptureSettings
    provider_issue: ProviderReadiness | None
    running: bool
    next_due_at: str | None
    latest_run: CaptureRun | None
    recent_runs: tuple[CaptureRun, ...]
    review_run_id: int | None
    review: CaptureReviewPreview | None


@dataclass(frozen=True)
class CaptureReviewChange:
    kind: str
    account_id: int | None
    account_label: str | None
    broker_account_id_hash: str | None
    broker_con_id: str
    symbol: str
    quantity: float
    before: dict[str, Any] | None
    after: dict[str, Any] | None


@dataclass(frozen=True)
class CaptureReviewPreview:
    run_id: int
    changes: tuple[CaptureReviewChange, ...]
    applies: bool


PORTFOLIO_CAPTURE_FILE_LOCK = FileLock("portfolio_capture")


class PortfolioCaptureService:
    def __init__(
        self,
        *,
        observations: PortfolioObservationStore,
        portfolio: PortfolioStore,
        reader: Callable[[], BrokerCaptureResult],
        provider_readiness: Callable[[], ProviderReadiness],
        write_allowed: Callable[[str, dict[str, Any]], bool],
        capture_process_lock: FileLock = PORTFOLIO_CAPTURE_FILE_LOCK,
        gateway_lock: Callable[[float], ContextManager[None]] = ibkr_gateway_lock,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.observations = observations
        self.portfolio = portfolio
        self.reader = reader
        self.provider_readiness = provider_readiness
        self.write_allowed = write_allowed
        self.capture_process_lock = capture_process_lock
        self.gateway_lock = gateway_lock
        self.clock = clock
        self._capture_lock = threading.Lock()
        self._next_due_at: datetime | None = None
        self._worker_thread: threading.Thread | None = None

    def status(self) -> PortfolioCaptureStatus:
        readiness = self._readiness()
        settings = self._effective_settings(readiness)
        if settings.enabled and self._next_due_at is None:
            self._initialize_due(self._now(), settings.interval_minutes)

        recent_runs = tuple(self.observations.list_runs(limit=20))
        review_run_id = self.observations.latest_reviewable_run_id()
        review = self.preview_run(review_run_id) if review_run_id is not None else None
        return PortfolioCaptureStatus(
            settings=settings,
            provider_issue=None if readiness.configured else readiness,
            running=self._capture_lock.locked(),
            next_due_at=(
                self._next_due_at.astimezone(timezone.utc).isoformat()
                if self._next_due_at is not None
                else None
            ),
            latest_run=recent_runs[0] if recent_runs else None,
            recent_runs=recent_runs,
            review_run_id=review_run_id,
            review=review,
        )

    def update_settings(
        self, *, enabled: bool, interval_minutes: int
    ) -> PortfolioCaptureStatus:
        settings = self.observations.set_settings(
            enabled=enabled, interval_minutes=interval_minutes
        )
        self._next_due_at = (
            self._now() + timedelta(minutes=settings.interval_minutes)
            if settings.enabled
            else None
        )
        return self.status()

    def trigger(
        self, trigger: CaptureTrigger, *, background: bool = True
    ) -> CaptureStart:
        if not self._capture_lock.acquire(blocking=False):
            return self._blocked_start("already_running", "A portfolio capture is active.")

        process_held = False
        execution_owns_locks = False
        try:
            try:
                allowed = self.write_allowed(
                    "portfolio_capture", {"trigger": trigger}
                )
            except Exception:
                allowed = False
            if not allowed:
                return self._blocked_start(
                    "permission_denied",
                    "Profile-state write permission was denied.",
                )

            readiness = self._readiness()
            if not readiness.configured:
                run = self.observations.record_blocked(
                    trigger=trigger,
                    effective_client_id=ibkr_client_id_for("portfolio_capture"),
                    error_code=readiness.code or "provider_config_missing",
                    error_detail=self._provider_detail(readiness),
                )
                self._set_due_after_terminal()
                return self._start_from_run(run, accepted=True)

            if not self.capture_process_lock.acquire(timeout=0):
                return self._blocked_start(
                    "already_running",
                    "Portfolio capture is active in another process.",
                )
            process_held = True
            run = self.observations.create_run(
                trigger=trigger,
                effective_client_id=ibkr_client_id_for("portfolio_capture"),
            )

            if background:
                worker = threading.Thread(
                    target=self._execute,
                    args=(run,),
                    name=f"portfolio-capture-{run.id}",
                    daemon=True,
                )
                self._worker_thread = worker
                try:
                    worker.start()
                except Exception as exc:
                    failed = self.observations.finish_run(
                        run.id,
                        state="failed",
                        error_code="capture_thread_start_failed",
                        error_detail=self._safe_exception_detail(
                            "Capture worker startup failed", exc
                        ),
                    )
                    self._set_due_after_terminal()
                    return self._start_from_run(failed, accepted=True)
                execution_owns_locks = True
                process_held = False
                return self._start_from_run(run, accepted=True)

            execution_owns_locks = True
            process_held = False
            return self._execute(run)
        finally:
            if not execution_owns_locks:
                self._release_capture_ownership(process_held=process_held)

    def preview_run(self, run_id: int) -> CaptureReviewPreview:
        snapshot = self.observations.position_snapshot_for_run(run_id)
        review_snapshot = self._snapshot_for_mode(snapshot, "ibkr_review")
        preview = preview_or_apply_ibkr_snapshot(
            self.portfolio, review_snapshot, apply=False
        )
        return self._review_projection(run_id, preview)

    def apply_review_run(self, run_id: int) -> CaptureReviewPreview:
        if not self._capture_lock.acquire(blocking=False):
            raise PortfolioCaptureBusy("portfolio capture ownership is active")
        process_held = False
        try:
            if not self.capture_process_lock.acquire(timeout=0):
                raise PortfolioCaptureBusy(
                    "portfolio capture ownership is active in another process"
                )
            process_held = True

            requested = self.observations.get_run(run_id)
            if requested.position_leg_state != "complete":
                raise CaptureRunNotReviewable(
                    "capture run has no complete broker-position set"
                )
            if self.observations.latest_reviewable_run_id() != run_id:
                raise CaptureRunSuperseded(
                    "a newer complete broker-position observation is reviewable"
                )

            snapshot = self.observations.position_snapshot_for_run(run_id)
            review_snapshot = self._snapshot_for_mode(snapshot, "ibkr_review")
            preview = preview_or_apply_ibkr_snapshot(
                self.portfolio, review_snapshot, apply=True
            )
            return self._review_projection(run_id, preview)
        finally:
            self._release_capture_ownership(process_held=process_held)

    def reconcile_startup(self) -> list[int]:
        if not self._capture_lock.acquire(blocking=False):
            return []
        process_held = False
        try:
            if not self.capture_process_lock.acquire(timeout=0):
                return []
            process_held = True
            return self.observations.reconcile_interrupted()
        finally:
            self._release_capture_ownership(process_held=process_held)

    def scheduler_tick(
        self, *, startup: bool = False, now: datetime | None = None
    ) -> CaptureStart | None:
        if self._capture_lock.locked():
            return None
        readiness = self._readiness()
        settings = self._effective_settings(readiness)
        if not settings.enabled or not readiness.configured:
            return None

        current = self._as_utc(now or self._now())
        if self._next_due_at is None:
            self._initialize_due(current, settings.interval_minutes)
        if self._next_due_at is not None and current < self._next_due_at:
            return None
        return self.trigger("startup" if startup else "scheduled", background=True)

    def _execute(self, run: CaptureRun) -> CaptureStart:
        try:
            try:
                gateway_context: AbstractContextManager[None] = self.gateway_lock(0)
                with gateway_context:
                    return self._execute_with_gateway(run)
            except TimeoutError:
                blocked = self.observations.finish_run(
                    run.id,
                    state="blocked",
                    error_code="gateway_busy",
                    error_detail="The shared IBKR Gateway lock is busy.",
                )
                self._set_due_after_terminal()
                return self._start_from_run(blocked, accepted=True)
            except Exception as exc:
                current = self.observations.get_run(run.id)
                if current.state == "running":
                    current = self.observations.finish_run(
                        run.id,
                        state="failed",
                        error_code="capture_failed",
                        error_detail=self._safe_exception_detail(
                            "Capture orchestration failed", exc
                        ),
                    )
                    self._set_due_after_terminal()
                return self._start_from_run(current, accepted=True)
        finally:
            self._release_capture_ownership(process_held=True)

    def _execute_with_gateway(self, run: CaptureRun) -> CaptureStart:
        try:
            result = self.reader()
        except Exception as exc:
            failed = self.observations.finish_run(
                run.id,
                state="failed",
                error_code="provider_read_failed",
                error_detail=self._safe_exception_detail("Provider read failed", exc),
            )
            self._set_due_after_terminal()
            return self._start_from_run(failed, accepted=True)

        try:
            committed = self.observations.commit_capture(run.id, result)
        except Exception as exc:
            failed = self.observations.finish_run(
                run.id,
                state="failed",
                error_code="observation_commit_failed",
                error_detail=self._safe_exception_detail(
                    "Observation commit failed", exc
                ),
            )
            self._set_due_after_terminal()
            return self._start_from_run(failed, accepted=True)

        apply_error: Exception | None = None
        if result.position_leg.state == "complete":
            try:
                stored_snapshot = self.observations.position_snapshot_for_run(run.id)
                auto_snapshot = self._snapshot_for_mode(stored_snapshot, "ibkr_auto")
                if auto_snapshot.accounts:
                    preview_or_apply_ibkr_snapshot(
                        self.portfolio, auto_snapshot, apply=True
                    )
            except Exception as exc:
                apply_error = exc

        state, error_code, error_detail = self._terminal_result(
            result, committed, apply_error
        )
        finished = self.observations.finish_run(
            run.id,
            state=state,
            error_code=error_code,
            error_detail=error_detail,
        )
        self._set_due_after_terminal()
        return self._start_from_run(finished, accepted=True)

    def _terminal_result(
        self,
        result: BrokerCaptureResult,
        committed: CaptureCommitResult,
        apply_error: Exception | None,
    ) -> tuple[Literal["succeeded", "partial", "failed"], str | None, str | None]:
        legs = (result.account_leg, result.execution_leg, result.position_leg)
        states = tuple(leg.state for leg in legs)
        has_valid_leg = any(state in {"complete", "partial"} for state in states)
        if apply_error is not None:
            return (
                "partial",
                "canonical_apply_failed",
                self._safe_exception_detail("Canonical apply failed", apply_error),
            )
        if (
            all(state == "complete" for state in states)
            and not committed.data_conflict_count
        ):
            return "succeeded", None, None
        if has_valid_leg:
            if committed.data_conflict_count:
                return (
                    "partial",
                    "data_conflict",
                    f"{committed.data_conflict_count} broker data conflict(s) were preserved.",
                )
            first_issue = next(
                (leg for leg in legs if leg.state in {"partial", "failed"}), None
            )
            return (
                "partial",
                (
                    first_issue.error_code
                    if first_issue and first_issue.error_code
                    else "capture_partial"
                ),
                first_issue.detail if first_issue else None,
            )
        first_issue = next(
            (leg for leg in legs if leg.error_code or leg.detail), None
        )
        return (
            "failed",
            (
                first_issue.error_code
                if first_issue and first_issue.error_code
                else "capture_failed"
            ),
            first_issue.detail if first_issue else None,
        )

    def _snapshot_for_mode(self, snapshot: BrokerSnapshot, mode: str) -> BrokerSnapshot:
        allowed = {
            account.broker_account_id
            for account in self.portfolio.list_accounts(
                include_archived=True,
                ensure_manual=False,
            )
            if account.broker == "ibkr"
            and account.broker_account_id
            and account.sync_mode == mode
        }
        return BrokerSnapshot(
            accounts=[
                account for account in snapshot.accounts if account.account_id in allowed
            ],
            positions=[
                position
                for position in snapshot.positions
                if position.account_id in allowed
            ],
        )

    def _review_projection(
        self, run_id: int, preview: PortfolioSyncPreview
    ) -> CaptureReviewPreview:
        accounts_by_raw = {
            account.broker_account_id: account
            for account in self.portfolio.list_accounts(
                include_archived=True,
                ensure_manual=False,
            )
            if account.broker == "ibkr" and account.broker_account_id
        }
        changes: list[CaptureReviewChange] = []
        for change in preview.changes:
            account = accounts_by_raw.get(change.broker_account_id)
            account_hash = (
                account.broker_account_id_hash
                if account is not None
                else portfolio_account_hash(change.broker_account_id)
            )
            label = account.label if account is not None else None
            if label and change.broker_account_id in label:
                label = f"IBKR · {account_hash[:8]}"
            changes.append(
                CaptureReviewChange(
                    kind=change.kind,
                    account_id=change.account_id,
                    account_label=label,
                    broker_account_id_hash=account_hash,
                    broker_con_id=change.broker_con_id,
                    symbol=change.symbol,
                    quantity=change.quantity,
                    before=change.before,
                    after=change.after,
                )
            )
        return CaptureReviewPreview(
            run_id=run_id, changes=tuple(changes), applies=preview.applies
        )

    def _effective_settings(
        self, readiness: ProviderReadiness
    ) -> EffectiveCaptureSettings:
        stored = self.observations.get_stored_settings()
        if stored is None:
            return EffectiveCaptureSettings(
                enabled=readiness.configured,
                interval_minutes=DEFAULT_CAPTURE_INTERVAL_MINUTES,
                source="default",
                provider_configured=readiness.configured,
            )
        return EffectiveCaptureSettings(
            enabled=stored.enabled,
            interval_minutes=stored.interval_minutes,
            source="database",
            provider_configured=readiness.configured,
        )

    def _readiness(self) -> ProviderReadiness:
        try:
            return self.provider_readiness()
        except Exception:
            return ProviderReadiness(
                configured=False,
                code="provider_readiness_failed",
                status="unavailable",
            )

    def _initialize_due(self, now: datetime, interval_minutes: int) -> None:
        last_success = self.observations.last_successful_finished_at()
        self._next_due_at = (
            self._as_utc(last_success) + timedelta(minutes=interval_minutes)
            if last_success is not None
            else self._as_utc(now)
        )

    def _set_due_after_terminal(self) -> None:
        stored = self.observations.get_stored_settings()
        interval = (
            stored.interval_minutes
            if stored is not None
            else DEFAULT_CAPTURE_INTERVAL_MINUTES
        )
        self._next_due_at = self._now() + timedelta(minutes=interval)

    def _now(self) -> datetime:
        return self._as_utc(self.clock())

    def _release_capture_ownership(self, *, process_held: bool) -> None:
        try:
            if process_held:
                self.capture_process_lock.release()
        finally:
            self._capture_lock.release()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _provider_detail(readiness: ProviderReadiness) -> str:
        parts = [
            part
            for part in (readiness.status, readiness.provider, readiness.field)
            if part
        ]
        return ": ".join(parts) or "IBKR provider configuration is incomplete."

    @staticmethod
    def _safe_exception_detail(prefix: str, exc: Exception) -> str:
        return f"{prefix} ({type(exc).__name__})."

    @staticmethod
    def _blocked_start(code: str, detail: str) -> CaptureStart:
        return CaptureStart(
            accepted=False,
            run=None,
            state="blocked",
            error_code=code,
            error_detail=detail,
        )

    @staticmethod
    def _start_from_run(run: CaptureRun, *, accepted: bool) -> CaptureStart:
        return CaptureStart(
            accepted=accepted,
            run=run,
            state=run.state,
            error_code=run.error_code,
            error_detail=run.error_detail,
        )
