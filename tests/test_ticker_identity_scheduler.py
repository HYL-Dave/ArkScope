from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import socket
import sqlite3
import threading

import pytest


class _GetOnly:
    def __init__(self, values: dict):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _build_due_context(tmp_path, *, with_portfolio_schema: bool = False):
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        observation_fingerprint,
    )
    from src.ticker_identity_schema import create_ticker_identity_schema
    from src.ticker_identity_service import TickerIdentityService
    from src.ticker_identity_transition import TransitionOptions

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    ProfileStateStore(profile_path).import_lists(
        [{"name": "Core", "kind": "custom", "tickers": ["OLD"]}]
    )
    if with_portfolio_schema:
        from src.portfolio_state import PortfolioStore

        PortfolioStore(profile_path)
    market_conn = sqlite3.connect(market_path)
    market_store = SecurityLifecycleStore(market_conn)
    market_store.upsert_observation(
        LifecycleObservation(
            ticker="OLD",
            cik="0000000000",
            issuer_name="Old Issuer Inc.",
            filing_date="2026-08-22",
            source="sec_edgar",
            source_ref="due-ref",
            filing_form="8-K",
            filing_items=("3.01",),
            evidence_url="https://www.sec.gov/Archives/example/due.htm",
            description="The tracked security will continue as NEW.",
            observed_at="2026-08-23T00:00:00Z",
            kinds=(ObservationKind("listing_status_review", "2026-08-25"),),
        )
    )
    observation = market_store.get_observation("sec_edgar", "due-ref", "OLD")
    fingerprint = observation_fingerprint(observation)
    market_conn.close()

    profile_conn = sqlite3.connect(profile_path)
    investigation = SecurityLifecycleInvestigationStore(profile_conn)
    case_id = investigation.ensure_case(
        source="sec_edgar",
        source_ref="due-ref",
        ticker="OLD",
        at="2026-08-23T00:00:00Z",
    )
    assessment_id = investigation.create_assessment(
        case_id=case_id,
        relevance="direct_tracked_security",
        confidence="high",
        author="human",
        conclusion="The tracked security continues as NEW.",
        impact_summary="Continue the user's tracking intent under NEW.",
        outcomes=("symbol_changed",),
        citations=(
            {
                "reference_kind": "observation",
                "cited_content_sha256": fingerprint,
            },
        ),
        observation_fingerprint_sha256=fingerprint,
        successor_ticker="NEW",
        effective_date="2026-08-25",
        at="2026-08-23T00:00:00Z",
    )
    investigation.accept_assessment(
        assessment_id,
        observation_fingerprint_sha256=fingerprint,
        acceptance_authority="human",
        at="2026-08-23T00:00:00Z",
    )
    investigation.generate_action_proposals(
        case_id=case_id,
        observation_fingerprint_sha256=fingerprint,
        sources_by_ticker={"OLD": ("manual_lists",)},
        at="2026-08-23T00:00:00Z",
    )
    create_ticker_identity_schema(profile_conn)
    profile_conn.close()

    service = TickerIdentityService(
        market_db_path=str(market_path),
        profile_db_path=str(profile_path),
        source_loader=lambda: {"OLD": ("manual_lists",)},
        clock=lambda: "2026-08-25T13:00:00Z",
    )
    options = TransitionOptions(execute_on="2026-08-25")
    preview = service.preview_case(case_id, options=options)
    transition = service.approve_case(
        case_id,
        options=options,
        preview_sha256=preview["preview_sha256"],
        before_write=lambda: None,
    )
    return service, profile_path, transition["transition_id"]


def _approved_preview_sha256(service, transition_id: str) -> str:
    rows = service.list_due_transitions(
        on_date="2026-08-25",
        limit=10,
        allow_automation_approved=True,
    )
    return next(
        str(row["approved_preview_sha256"])
        for row in rows
        if row["transition_id"] == transition_id
    )


def _scheduler_result(
    *,
    status: str,
    reason: str | None,
    recovery_eligible: bool = True,
    applied: int = 0,
    needs_review: int = 0,
    already_applied: int = 0,
    transition_ids: list[str] | None = None,
    failed_transition_ids: list[str] | None = None,
    deferred_transition_ids: list[str] | None = None,
) -> dict:
    ids = list(transition_ids or [])
    failed_ids = list(failed_transition_ids or [])
    deferred_ids = list(deferred_transition_ids or [])
    return {
        "status": status,
        "reason": reason,
        "recovery_eligible": recovery_eligible,
        "due": len(ids),
        "applied": applied,
        "needs_review": needs_review,
        "already_applied": already_applied,
        "transition_ids": ids,
        "failed_transition_ids": failed_ids,
        "deferred_transition_ids": deferred_ids,
    }


class _PolicyFilteringDueService:
    def __init__(self, *, include_attended: bool, fail_attended: bool = False):
        self.include_attended = include_attended
        self.fail_attended = fail_attended
        self.executed: list[str] = []

    def list_due_transitions(self, *, allow_automation_approved, **_kwargs):
        rows = [
            {
                "transition_id": "slt_automation",
                "approved_preview_sha256": "a" * 64,
                "approval_authority": "automation_policy",
            }
        ]
        if self.include_attended:
            rows.append(
                {
                    "transition_id": "slt_attended",
                    "approved_preview_sha256": "b" * 64,
                    "approval_authority": "attended_user",
                }
            )
        if allow_automation_approved:
            return rows
        return [row for row in rows if row["approval_authority"] == "attended_user"]

    def execute_transition(self, transition_id, *, before_write, **_kwargs):
        self.executed.append(transition_id)
        if transition_id == "slt_attended" and self.fail_attended:
            raise RuntimeError("private execution failure")
        before_write()
        return {"status": "applied"}


class _MixedFailureDueService:
    def __init__(self):
        self.executed: list[str] = []

    def list_due_transitions(self, **_kwargs):
        return [
            {
                "transition_id": "slt_deferred",
                "approved_preview_sha256": "a" * 64,
                "approval_authority": "automation_policy",
            },
            {
                "transition_id": "slt_authority",
                "approved_preview_sha256": "b" * 64,
                "approval_authority": "automation_policy",
            },
            {
                "transition_id": "slt_execution",
                "approved_preview_sha256": "c" * 64,
                "approval_authority": "attended_user",
            },
        ]

    def execute_transition(self, transition_id, *, before_write, **_kwargs):
        self.executed.append(transition_id)
        if transition_id == "slt_execution":
            raise RuntimeError("private execution failure")
        before_write()
        return {"status": "applied"}


def _run_mixed_failure_batch(monkeypatch):
    from src.service import ticker_identity_scheduler as scheduler

    service = _MixedFailureDueService()
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    authority_reads = 0

    def mutation_allowed():
        nonlocal authority_reads
        authority_reads += 1
        if authority_reads == 1:
            return False
        raise sqlite3.OperationalError("private config failure")

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=mutation_allowed,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )
    return service, result


def test_service_threads_authority_selection_to_due_store(tmp_path, monkeypatch):
    service, _profile_path, _transition_id = _build_due_context(tmp_path)

    class StoreProbe:
        def __init__(self):
            self.calls = []

        def list_due(
            self,
            *,
            on_date,
            limit,
            allow_automation_approved,
        ):
            self.calls.append((on_date, limit, allow_automation_approved))
            return []

    store = StoreProbe()
    monkeypatch.setattr(service, "_store", lambda _conn: store)

    assert service.list_due_transitions(
        on_date="2026-08-25",
        limit=1,
        allow_automation_approved=False,
    ) == []
    assert store.calls == [("2026-08-25", 1, False)]


def test_service_requires_explicit_automation_authority_selection(tmp_path):
    service, _profile_path, _transition_id = _build_due_context(tmp_path)

    with pytest.raises(TypeError, match="allow_automation_approved"):
        service.list_due_transitions(on_date="2026-08-25", limit=1)


def test_due_runner_requires_explicit_authority_selection():
    from src.service import ticker_identity_scheduler as scheduler

    with pytest.raises(TypeError, match="allow_automation_approved"):
        scheduler.run_due_ticker_identity_transitions(
            now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
        )
    with pytest.raises(TypeError, match="transition_mutation_allowed"):
        scheduler.run_due_ticker_identity_transitions(
            allow_automation_approved=False,
            now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
        )


def test_due_execution_records_needs_review_when_recomputed_preview_changed(tmp_path):
    service, profile_path, transition_id = _build_due_context(tmp_path)
    digest = _approved_preview_sha256(service, transition_id)
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "UPDATE watchlist_memberships SET position=9,updated_at=? "
            "WHERE ticker='OLD'",
            ("2026-08-25T12:59:59Z",),
        )

    permission_calls: list[str] = []
    result = service.execute_transition(
        transition_id,
        preview_sha256=digest,
        trigger="scheduler",
        before_write=lambda: permission_calls.append("write"),
    )

    assert result["status"] == "blocked"
    assert result["block_reasons"] == ["preview_changed"]
    assert result["transition"]["status"] == "needs_review"
    assert permission_calls == ["write"]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,block_reasons_json "
            "FROM ticker_identity_transition_attempts"
        ).fetchall() == [("blocked", '["preview_changed"]')]
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships WHERE ticker='OLD'"
        ).fetchone() == (None,)


def test_due_execution_rechecks_new_broker_position_after_service_preview(tmp_path):
    service, profile_path, transition_id = _build_due_context(
        tmp_path,
        with_portfolio_schema=True,
    )
    digest = _approved_preview_sha256(service, transition_id)

    def insert_broker_position() -> None:
        with sqlite3.connect(profile_path) as conn:
            account_id = conn.execute(
                "INSERT INTO portfolio_accounts "
                "(label,broker,sync_mode,base_currency,include_in_total,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    "Broker",
                    "ibkr",
                    "sync",
                    "USD",
                    1,
                    "2026-08-25T12:59:59Z",
                    "2026-08-25T12:59:59Z",
                ),
            ).lastrowid
            conn.execute(
                "INSERT INTO portfolio_positions "
                "(account_id,broker,symbol,asset_class,quantity,currency,"
                "source,sync_status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    account_id,
                    "ibkr",
                    "OLD",
                    "stock",
                    10,
                    "USD",
                    "ibkr",
                    "synced",
                    "2026-08-25T12:59:59Z",
                    "2026-08-25T12:59:59Z",
                ),
            )

    result = service.execute_transition(
        transition_id,
        preview_sha256=digest,
        trigger="scheduler",
        before_write=insert_broker_position,
    )

    assert result["status"] == "blocked"
    assert result["block_reasons"] == ["preview_changed"]
    assert result["transition"]["status"] == "needs_review"
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships WHERE ticker='OLD'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT COUNT(*) FROM portfolio_positions WHERE symbol='OLD' "
            "AND closed_at IS NULL"
        ).fetchone() == (1,)


def test_due_execution_durably_blocks_when_provider_observation_invalidates_assessment(
    tmp_path,
):
    service, profile_path, transition_id = _build_due_context(tmp_path)
    digest = _approved_preview_sha256(service, transition_id)
    with sqlite3.connect(tmp_path / "market_data.db") as conn:
        conn.execute(
            "UPDATE security_lifecycle_observations "
            "SET description='Changed provider observation' "
            "WHERE source='sec_edgar' AND source_ref='due-ref' AND ticker='OLD'"
        )

    permission_calls: list[str] = []
    result = service.execute_transition(
        transition_id,
        preview_sha256=digest,
        trigger="scheduler",
        before_write=lambda: permission_calls.append("write"),
    )

    assert result["status"] == "blocked"
    assert result["block_reasons"] == ["preview_changed"]
    assert result["transition"]["status"] == "needs_review"
    assert permission_calls == ["write"]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,block_reasons_json,observed_preview_sha256 "
            "FROM ticker_identity_transition_attempts WHERE transition_id=?",
            (transition_id,),
        ).fetchall() == [("blocked", '["preview_changed"]', None)]
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships WHERE ticker='OLD'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone() == (0,)


def test_attended_retry_rechecks_expected_digest_inside_write_lock(
    tmp_path,
    monkeypatch,
):
    from src.ticker_identity_service import (
        TickerIdentityConflict,
        TickerIdentityService,
    )
    from src.ticker_identity_transition import TransitionOptions

    service, profile_path, transition_id = _build_due_context(tmp_path)
    old_digest = _approved_preview_sha256(service, transition_id)
    transition = service.list_due_transitions(
        on_date="2026-08-25",
        limit=10,
        allow_automation_approved=True,
    )[0]
    case_id = str(transition["case_id"])
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "UPDATE watchlist_memberships SET position=9,updated_at=? "
            "WHERE ticker='OLD'",
            ("2026-08-25T12:59:59Z",),
        )

    reapprover = TickerIdentityService(
        market_db_path=str(tmp_path / "market_data.db"),
        profile_db_path=str(profile_path),
        source_loader=lambda: {"OLD": ("manual_lists",)},
        clock=lambda: "2026-08-25T13:00:00Z",
    )
    options = TransitionOptions(execute_on="2026-08-25")
    new_preview = reapprover.preview_case(case_id, options=options)
    assert new_preview["preview_sha256"] != old_digest

    original_get_case = service._read_service.get_case
    raced = False

    def reapprove_before_recomposition(requested_case_id: str):
        nonlocal raced
        if not raced:
            raced = True
            updated = reapprover.approve_case(
                requested_case_id,
                options=options,
                preview_sha256=new_preview["preview_sha256"],
                before_write=lambda: None,
            )
            assert updated["transition_id"] == transition_id
        return original_get_case(requested_case_id)

    monkeypatch.setattr(
        service._read_service,
        "get_case",
        reapprove_before_recomposition,
    )
    permission_calls: list[str] = []
    with pytest.raises(TickerIdentityConflict, match="transition_preview_changed"):
        service.execute_transition(
            transition_id,
            preview_sha256=old_digest,
            trigger="attended_user",
            before_write=lambda: permission_calls.append("write"),
        )

    assert raced is True
    assert permission_calls == ["write"]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT approved_preview_sha256,status FROM ticker_identity_transitions "
            "WHERE transition_id=?",
            (transition_id,),
        ).fetchone() == (new_preview["preview_sha256"], "approved")
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts "
            "WHERE transition_id=?",
            (transition_id,),
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships WHERE ticker='OLD'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone() == (0,)


def test_due_runner_uses_new_york_date_is_bounded_and_isolates_failures(
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    class FakeService:
        def __init__(self):
            self.list_call = None
            self.executed = []

        def list_due_transitions(
            self,
            *,
            on_date,
            limit,
            allow_automation_approved,
        ):
            self.list_call = (on_date, limit, allow_automation_approved)
            return [
                {
                    "transition_id": f"slt_{index}",
                    "approved_preview_sha256": str(index % 10) * 64,
                    "approval_authority": "attended_user",
                }
                for index in range(12)
            ][:limit]

        def execute_transition(
            self,
            transition_id,
            *,
            preview_sha256,
            trigger,
            before_write,
        ):
            self.executed.append((transition_id, preview_sha256, trigger))
            if transition_id == "slt_1":
                return {
                    "status": "blocked",
                    "transition": {"status": "needs_review"},
                }
            if transition_id == "slt_2":
                raise RuntimeError("private provider detail")
            before_write()
            return {"status": "applied", "transition": {"status": "applied"}}

    service = FakeService()
    permission_calls = []
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda action, detail=None: permission_calls.append((action, detail)),
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        limit=10,
        now=datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc),
    )

    assert service.list_call == ("2026-08-23", 10, True)
    assert len(service.executed) == 10
    assert all(row[2] == "scheduler" for row in service.executed)
    assert result == {
        "status": "partial",
        "reason": "transition_execution_failed",
        "recovery_eligible": True,
        "due": 10,
        "applied": 8,
        "needs_review": 1,
        "already_applied": 0,
        "transition_ids": [f"slt_{index}" for index in range(10)],
        "failed_transition_ids": ["slt_2"],
        "deferred_transition_ids": [],
    }
    assert len(permission_calls) == 8


@pytest.mark.parametrize(
    ("allow_automation_approved", "transition_id"),
    [
        (False, "slt_attended"),
        (True, "slt_automation"),
    ],
)
def test_due_runner_forwards_authority_selection_and_executes_returned_transition(
    allow_automation_approved,
    transition_id,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    class FakeService:
        def __init__(self):
            self.list_calls = []
            self.executed = []

        def list_due_transitions(
            self,
            *,
            on_date,
            limit,
            allow_automation_approved,
        ):
            self.list_calls.append(
                (on_date, limit, allow_automation_approved)
            )
            selected = (
                "slt_automation"
                if allow_automation_approved
                else "slt_attended"
            )
            return [
                {
                    "transition_id": selected,
                    "approved_preview_sha256": "a" * 64,
                    "approval_authority": (
                        "automation_policy"
                        if allow_automation_approved
                        else "attended_user"
                    ),
                }
            ]

        def execute_transition(self, selected_id, *, before_write, **_kwargs):
            before_write()
            self.executed.append(selected_id)
            return {"status": "applied"}

    service = FakeService()
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=allow_automation_approved,
        transition_mutation_allowed=lambda: allow_automation_approved,
        limit=1,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert service.list_calls == [
        ("2026-08-25", 1, allow_automation_approved)
    ]
    assert service.executed == [transition_id]
    assert result["transition_ids"] == [transition_id]
    assert result["applied"] == 1


def test_due_runner_never_executes_transition_with_unknown_approval_authority(
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    class FakeService:
        def __init__(self):
            self.executed = []

        def list_due_transitions(self, **_kwargs):
            return [
                {
                    "transition_id": "slt_unknown_authority",
                    "approved_preview_sha256": "a" * 64,
                    "approval_authority": "foreign_authority",
                }
            ]

        def execute_transition(self, transition_id, *, before_write, **_kwargs):
            before_write()
            self.executed.append(transition_id)
            return {"status": "applied"}

    service = FakeService()
    permission_calls = []
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *args, **kwargs: permission_calls.append((args, kwargs)),
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        limit=1,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert service.executed == []
    assert permission_calls == []
    assert result == {
        "status": "partial",
        "reason": "transition_execution_failed",
        "recovery_eligible": True,
        "due": 1,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_unknown_authority"],
        "failed_transition_ids": ["slt_unknown_authority"],
        "deferred_transition_ids": [],
    }


def _run_automation_write_boundary(monkeypatch, mutation_allowed):
    from src.service import ticker_identity_scheduler as scheduler

    writes = []

    class FakeService:
        def list_due_transitions(self, **_kwargs):
            return [
                {
                    "transition_id": "slt_automation",
                    "approved_preview_sha256": "a" * 64,
                    "approval_authority": "automation_policy",
                }
            ]

        def execute_transition(
            self,
            transition_id,
            *,
            preview_sha256,
            trigger,
            before_write,
        ):
            del transition_id, preview_sha256, trigger
            before_write()
            writes.append("profile_mutated")
            return {"status": "applied"}

    monkeypatch.setattr(scheduler, "_service", FakeService)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=mutation_allowed,
        limit=1,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    return writes, result


def test_due_runner_defers_when_automation_mutation_is_disabled_at_write_boundary(
    monkeypatch,
):
    writes, result = _run_automation_write_boundary(monkeypatch, lambda: False)

    assert writes == []
    assert result == {
        "status": "deferred",
        "reason": "transition_mutation_disabled",
        "recovery_eligible": True,
        "due": 1,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_automation"],
        "failed_transition_ids": [],
        "deferred_transition_ids": ["slt_automation"],
    }


def test_due_runner_reports_transient_mutation_authority_failure_separately(
    monkeypatch,
):
    def unavailable():
        raise sqlite3.OperationalError("private config failure")

    writes, result = _run_automation_write_boundary(monkeypatch, unavailable)

    assert writes == []
    assert result == {
        "status": "partial",
        "reason": "transition_mutation_authority_unavailable",
        "recovery_eligible": True,
        "due": 1,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_automation"],
        "failed_transition_ids": ["slt_automation"],
        "deferred_transition_ids": [],
    }


def test_due_runner_uses_execution_reason_for_heterogeneous_failure_causes(
    monkeypatch,
):
    service, result = _run_mixed_failure_batch(monkeypatch)

    assert service.executed == [
        "slt_deferred",
        "slt_authority",
        "slt_execution",
    ]
    assert result == {
        "status": "partial",
        "reason": "transition_execution_failed",
        "recovery_eligible": True,
        "due": 3,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [
            "slt_deferred",
            "slt_authority",
            "slt_execution",
        ],
        "failed_transition_ids": ["slt_authority", "slt_execution"],
        "deferred_transition_ids": ["slt_deferred"],
    }


def test_attended_user_transition_ignores_automation_mutation_authority(
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    authority_reads = []

    class FakeService:
        def list_due_transitions(self, **_kwargs):
            return [
                {
                    "transition_id": "slt_attended",
                    "approved_preview_sha256": "a" * 64,
                    "approval_authority": "attended_user",
                }
            ]

        def execute_transition(self, transition_id, *, before_write, **_kwargs):
            before_write()
            return {"status": "applied", "transition_id": transition_id}

    def unavailable():
        authority_reads.append("read")
        raise sqlite3.OperationalError("private config failure")

    monkeypatch.setattr(scheduler, "_service", FakeService)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=unavailable,
        limit=1,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert authority_reads == []
    assert result == {
        "status": "succeeded",
        "reason": None,
        "recovery_eligible": False,
        "due": 1,
        "applied": 1,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_attended"],
        "failed_transition_ids": [],
        "deferred_transition_ids": [],
    }


@pytest.mark.parametrize(
    "malformed_result",
    [
        None,
        {"status": "blocked", "transition": None},
        _GetOnly({"status": "applied"}),
    ],
)
def test_due_runner_isolates_malformed_transition_results_and_retains_ids(
    malformed_result,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    class FakeService:
        def __init__(self):
            self.executed = []

        def list_due_transitions(
            self,
            *,
            on_date,
            limit,
            allow_automation_approved,
        ):
            del on_date, limit, allow_automation_approved
            return [
                {
                    "transition_id": "slt_bad",
                    "approved_preview_sha256": "a" * 64,
                    "approval_authority": "attended_user",
                },
                {
                    "transition_id": "slt_later",
                    "approved_preview_sha256": "b" * 64,
                    "approval_authority": "attended_user",
                },
            ]

        def execute_transition(self, transition_id, **_kwargs):
            self.executed.append(transition_id)
            if transition_id == "slt_bad":
                return malformed_result
            return {"status": "applied"}

    service = FakeService()
    monkeypatch.setattr(scheduler, "_service", lambda: service)

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert service.executed == ["slt_bad", "slt_later"]
    assert result == {
        "status": "partial",
        "reason": "transition_execution_failed",
        "recovery_eligible": True,
        "due": 2,
        "applied": 1,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_bad", "slt_later"],
        "failed_transition_ids": ["slt_bad"],
        "deferred_transition_ids": [],
    }


def test_due_runner_is_provider_free_and_concurrent_ticks_apply_once(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    service, profile_path, transition_id = _build_due_context(tmp_path)
    barrier = threading.Barrier(2)
    original_list_due = service.list_due_transitions

    def synchronized_list_due(
        *,
        on_date,
        limit,
        allow_automation_approved,
    ):
        rows = original_list_due(
            on_date=on_date,
            limit=limit,
            allow_automation_approved=allow_automation_approved,
        )
        barrier.wait(timeout=5)
        return rows

    service.list_due_transitions = synchronized_list_due
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network_not_allowed")
        ),
    )
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _index: scheduler.run_due_ticker_identity_transitions(
                    allow_automation_approved=True,
                    transition_mutation_allowed=lambda: True,
                    now=now
                ),
                range(2),
            )
        )

    assert sorted((row["applied"], row["already_applied"]) for row in results) == [
        (0, 1),
        (1, 0),
    ]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_links WHERE transition_id=?",
            (transition_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT status,COUNT(*) FROM ticker_identity_transition_attempts "
            "GROUP BY status ORDER BY status"
        ).fetchall() == [("already_applied", 1), ("applied", 1)]


def test_deferred_transition_is_reapplied_after_policy_is_re_enabled(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_decision_policy import (
        AUTOMATION_POLICY_VERSION,
        RULE_VERSIONS,
    )
    from src.service import ticker_identity_scheduler as scheduler

    service, profile_path, transition_id = _build_due_context(tmp_path)
    rule_id = "lifecycle.simple_symbol_continuation"
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "UPDATE ticker_identity_transitions SET approval_authority=?,"
            "automation_policy_version=?,rule_id=?,rule_version=? "
            "WHERE transition_id=?",
            (
                "automation_policy",
                AUTOMATION_POLICY_VERSION,
                rule_id,
                RULE_VERSIONS[rule_id],
                transition_id,
            ),
        )
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    deferred = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: False,
        now=now,
    )

    assert deferred["status"] == "deferred"
    assert deferred["deferred_transition_ids"] == [transition_id]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status FROM ticker_identity_transitions WHERE transition_id=?",
            (transition_id,),
        ).fetchone() == ("approved",)
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts "
            "WHERE transition_id=?",
            (transition_id,),
        ).fetchone() == (0,)

    applied = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=now,
    )

    assert applied["status"] == "succeeded"
    assert applied["applied"] == 1
    assert applied["failed_transition_ids"] == []
    assert applied["deferred_transition_ids"] == []
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status FROM ticker_identity_transitions WHERE transition_id=?",
            (transition_id,),
        ).fetchone() == ("applied",)


def test_due_runner_with_no_identity_component_creates_nothing(tmp_path, monkeypatch):
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "profile_state.db"
    market_path = tmp_path / "market_data.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "unavailable",
        "reason": "profile_store_missing",
        "recovery_eligible": True,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
        "deferred_transition_ids": [],
    }
    assert not profile_path.exists()
    assert not market_path.exists()


def test_due_runner_reports_existing_profile_without_identity_schema_as_not_installed(
    tmp_path,
    monkeypatch,
):
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "profile_state.db"
    market_path = tmp_path / "market_data.db"
    ProfileStateStore(profile_path)
    with sqlite3.connect(profile_path) as conn:
        SecurityLifecycleInvestigationStore(conn)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "not_installed",
        "reason": "identity_schema_absent",
        "recovery_eligible": True,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
        "deferred_transition_ids": [],
    }
    assert profile_path.is_file()
    assert not market_path.exists()


def test_due_runner_reports_malformed_identity_schema_as_unavailable(
    tmp_path,
    monkeypatch,
):
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "profile_state.db"
    market_path = tmp_path / "market_data.db"
    ProfileStateStore(profile_path)
    with sqlite3.connect(profile_path) as conn:
        SecurityLifecycleInvestigationStore(conn)
        conn.execute("CREATE TABLE ticker_identity_broken (value TEXT)")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "unavailable",
        "reason": "identity_schema_mismatch",
        "recovery_eligible": True,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
        "deferred_transition_ids": [],
    }
    assert not market_path.exists()


def test_bounded_result_accepts_disjoint_failure_and_deferral_accounting():
    from src.service import ticker_identity_scheduler as scheduler

    result = _scheduler_result(
        status="partial",
        reason="transition_mutation_authority_unavailable",
        applied=1,
        transition_ids=["slt_applied", "slt_failed", "slt_deferred"],
        failed_transition_ids=["slt_failed"],
        deferred_transition_ids=["slt_deferred"],
    )

    assert scheduler._bounded_result(result) == result


def test_bounded_result_accepts_successes_alongside_only_deferrals():
    from src.service import ticker_identity_scheduler as scheduler

    result = _scheduler_result(
        status="deferred",
        reason="transition_mutation_disabled",
        applied=1,
        transition_ids=["slt_applied", "slt_deferred"],
        deferred_transition_ids=["slt_deferred"],
    )

    assert scheduler._bounded_result(result) == result


def test_failure_helper_rejects_policy_only_disabled_reason():
    from src.service import ticker_identity_scheduler as scheduler

    with pytest.raises(ValueError, match="reason"):
        scheduler.ticker_identity_scheduler_failure(
            "transition_mutation_disabled"
        )


@pytest.mark.parametrize(
    ("result", "field"),
    [
        (
            _scheduler_result(
                status="partial",
                reason="transition_execution_failed",
                transition_ids=["slt_shared"],
                failed_transition_ids=["slt_shared"],
                deferred_transition_ids=["slt_shared"],
            ),
            "deferred_transition_ids",
        ),
        (
            _scheduler_result(
                status="deferred",
                reason="transition_mutation_disabled",
                transition_ids=["slt_due"],
                deferred_transition_ids=["slt_not_due"],
            ),
            "deferred_transition_ids",
        ),
        (
            _scheduler_result(
                status="partial",
                reason="transition_execution_failed",
            ),
            "failed_transition_ids",
        ),
        (
            _scheduler_result(
                status="succeeded",
                reason=None,
                transition_ids=["slt_failed"],
                failed_transition_ids=["slt_failed"],
            ),
            "failed_transition_ids",
        ),
        (
            _scheduler_result(
                status="deferred",
                reason="transition_mutation_disabled",
            ),
            "deferred_transition_ids",
        ),
        (
            _scheduler_result(
                status="succeeded",
                reason=None,
                transition_ids=["slt_deferred"],
                deferred_transition_ids=["slt_deferred"],
            ),
            "deferred_transition_ids",
        ),
        (
            _scheduler_result(
                status="deferred",
                reason="transition_execution_failed",
                transition_ids=["slt_deferred"],
                deferred_transition_ids=["slt_deferred"],
            ),
            "reason",
        ),
        (
            _scheduler_result(
                status="unavailable",
                reason="transition_mutation_disabled",
            ),
            "reason",
        ),
        (
            _scheduler_result(
                status="not_installed",
                reason="transition_mutation_disabled",
            ),
            "reason",
        ),
    ],
)
def test_bounded_result_rejects_invalid_failure_and_deferral_states(result, field):
    from src.service import ticker_identity_scheduler as scheduler

    with pytest.raises(ValueError, match=field):
        scheduler._bounded_result(result)


def test_stored_result_reads_legacy_summary_without_deferred_field():
    from src.service import ticker_identity_scheduler as scheduler

    current = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=["slt_failed"],
        failed_transition_ids=["slt_failed"],
    )
    legacy = dict(current)
    legacy.pop("deferred_transition_ids")

    assert scheduler._stored_result(json.dumps(legacy)) == current


def test_bounded_result_defaults_missing_legacy_recovery_eligible_to_true():
    from src.service import ticker_identity_scheduler as scheduler

    legacy = _scheduler_result(status="succeeded", reason=None)
    legacy.pop("recovery_eligible", None)

    assert scheduler._bounded_result(legacy)["recovery_eligible"] is True


def test_present_non_boolean_recovery_eligible_is_rejected():
    from src.service import ticker_identity_scheduler as scheduler

    malformed = _scheduler_result(status="succeeded", reason=None)
    malformed["recovery_eligible"] = 1

    with pytest.raises(ValueError, match="recovery_eligible"):
        scheduler._bounded_result(malformed)


def test_stored_result_degrades_unknown_result_version_without_rejecting():
    from src.service import ticker_identity_scheduler as scheduler

    current = _scheduler_result(
        status="partial",
        reason="transition_mutation_authority_unavailable",
        transition_ids=["slt_failed"],
        failed_transition_ids=["slt_failed"],
    )
    future = {**current, "result_version": 999}

    assert scheduler._stored_result(json.dumps(future)) == current


def test_present_malformed_deferred_field_is_rejected():
    from src.service import ticker_identity_scheduler as scheduler

    malformed = _scheduler_result(status="succeeded", reason=None)
    malformed["deferred_transition_ids"] = "slt_not_a_list"

    with pytest.raises(ValueError, match="deferred_transition_ids"):
        scheduler._bounded_result(malformed)
    assert scheduler._stored_result(json.dumps(malformed)) is None


def test_scheduler_failure_witness_does_not_create_missing_profile_database(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "missing" / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    result = {
        "status": "unavailable",
        "reason": "profile_store_missing",
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }

    persisted = scheduler.record_ticker_identity_scheduler_result(
        result,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert persisted is False
    assert not profile_path.exists()


def test_scheduler_failure_witness_cannot_recreate_profile_deleted_before_rw_open(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "profile_state.db"
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            """
            CREATE TABLE job_runs (
                id INTEGER PRIMARY KEY,
                job_name TEXT NOT NULL,
                status TEXT NOT NULL,
                trigger_source TEXT NOT NULL,
                payload TEXT NOT NULL,
                result TEXT,
                message TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    original_connect = sqlite3.connect

    def delete_at_open(database, *args, **kwargs):
        target = str(database)
        if "mode=rw" in target:
            profile_path.unlink(missing_ok=True)
            return original_connect(database, *args, **kwargs)
        connection = original_connect(database, *args, **kwargs)
        if "mode=ro" in target:
            profile_path.unlink()
        return connection

    monkeypatch.setattr(scheduler.sqlite3, "connect", delete_at_open)

    persisted = scheduler.record_ticker_identity_scheduler_result(
        _scheduler_result(
            status="unavailable",
            reason="profile_store_unavailable",
        ),
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert persisted is False
    assert not profile_path.exists()


def test_scheduler_failure_witness_deduplicates_concurrent_identical_failures(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    original_list_runs = JobRunsLocalStore.list_runs
    legacy_read_barrier = threading.Barrier(2)
    start_barrier = threading.Barrier(2)

    def synchronized_list_runs(store, **kwargs):
        rows = original_list_runs(store, **kwargs)
        legacy_read_barrier.wait(timeout=5)
        return rows

    monkeypatch.setattr(JobRunsLocalStore, "list_runs", synchronized_list_runs)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        applied=1,
        transition_ids=["slt_ok", "slt_failed"],
        failed_transition_ids=["slt_failed"],
    )
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    def record_failure(_index):
        start_barrier.wait(timeout=5)
        return scheduler.record_ticker_identity_scheduler_result(
            failure,
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        persisted = list(executor.map(record_failure, range(2)))

    assert persisted == [True, True]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE job_name=?",
            ("ticker_identity.transitions",),
        ).fetchone() == (1,)


def test_scheduler_recovery_uses_insertion_order_when_clock_moves_backward(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    failure = _scheduler_result(
        status="unavailable",
        reason="profile_store_unavailable",
    )
    healthy = _scheduler_result(status="succeeded", reason=None)

    assert scheduler.record_ticker_identity_scheduler_result(
        failure,
        now=datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc),
    )
    assert scheduler.record_ticker_identity_scheduler_result(
        healthy,
        now=datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc),
    )
    assert scheduler.record_ticker_identity_scheduler_result(
        healthy,
        now=datetime(2026, 8, 25, 9, 1, tzinfo=timezone.utc),
    )

    runs = telemetry.list_runs(job_name="ticker_identity.transitions", limit=10)
    assert [(row["status"], row["message"]) for row in runs] == [
        ("succeeded", "ticker_identity_scheduler_recovered"),
        ("failed", "ticker_identity_scheduler_failure"),
    ]


def test_scheduler_concurrent_healthy_ticks_record_one_recovery(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    failure = _scheduler_result(
        status="unavailable",
        reason="profile_store_unavailable",
    )
    healthy = _scheduler_result(status="succeeded", reason=None)
    failed_at = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
    assert scheduler.record_ticker_identity_scheduler_result(
        failure,
        now=failed_at,
    )
    barrier = threading.Barrier(2)

    def record_recovery(_index):
        barrier.wait(timeout=5)
        return scheduler.record_ticker_identity_scheduler_result(
            healthy,
            now=failed_at,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        persisted = list(executor.map(record_recovery, range(2)))

    assert persisted == [True, True]
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            ("failed", "ticker_identity_scheduler_failure"),
            ("succeeded", "ticker_identity_scheduler_recovered"),
        ]


def test_policy_deferral_after_a_real_failure_never_records_recovery(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=["slt_failed"],
        failed_transition_ids=["slt_failed"],
    )
    deferred = _scheduler_result(
        status="deferred",
        reason="transition_mutation_disabled",
        transition_ids=["slt_deferred"],
        deferred_transition_ids=["slt_deferred"],
    )

    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    assert scheduler.record_ticker_identity_scheduler_result(deferred, now=now)

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "transition_execution_failed",
            )
        ]

    healthy = _scheduler_result(status="succeeded", reason=None)
    assert scheduler.record_ticker_identity_scheduler_result(healthy, now=now)
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "transition_execution_failed",
            ),
            (
                "succeeded",
                "ticker_identity_scheduler_recovered",
                None,
            ),
        ]


def test_heterogeneous_failure_batch_persists_execution_failure_incident(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    _service, result = _run_mixed_failure_batch(monkeypatch)

    assert scheduler.record_ticker_identity_scheduler_result(
        result,
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    with sqlite3.connect(profile_path) as conn:
        row = conn.execute(
            "SELECT status,error,result FROM job_runs WHERE job_name=?",
            ("ticker_identity.transitions",),
        ).fetchone()
    assert row[:2] == ("failed", "transition_execution_failed")
    assert json.loads(row[2]) == result


def test_filtered_automation_only_success_never_recovers_prior_incident(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=["slt_automation"],
        failed_transition_ids=["slt_automation"],
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    service = _PolicyFilteringDueService(include_attended=False)
    monkeypatch.setattr(scheduler, "_service", lambda: service)

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(result, now=now)

    assert service.executed == []
    assert result["status"] == "succeeded"
    assert result["recovery_eligible"] is False
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "transition_execution_failed",
            )
        ]


def test_filtered_automation_with_attended_success_never_recovers_prior_incident(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=["slt_automation"],
        failed_transition_ids=["slt_automation"],
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    service = _PolicyFilteringDueService(include_attended=True)
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(result, now=now)

    assert service.executed == ["slt_attended"]
    assert result["status"] == "succeeded"
    assert result["applied"] == 1
    assert result["recovery_eligible"] is False
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "transition_execution_failed",
            )
        ]


def test_filtered_automation_with_attended_failure_still_records_failure(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    service = _PolicyFilteringDueService(
        include_attended=True,
        fail_attended=True,
    )
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    result = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(result, now=now)

    assert result["status"] == "partial"
    assert result["reason"] == "transition_execution_failed"
    assert result["recovery_eligible"] is False
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,error FROM job_runs WHERE job_name=?",
            ("ticker_identity.transitions",),
        ).fetchall() == [("failed", "transition_execution_failed")]


def test_scheduler_wide_recovery_is_independent_of_automation_policy_filter(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="unavailable",
        reason="profile_store_unavailable",
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    service = _PolicyFilteringDueService(include_attended=False)
    monkeypatch.setattr(scheduler, "_service", lambda: service)

    recovered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert recovered["status"] == "succeeded"
    assert recovered["recovery_eligible"] is False
    assert scheduler.record_ticker_identity_scheduler_result(recovered, now=now)

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "profile_store_unavailable",
            ),
            ("succeeded", "ticker_identity_scheduler_recovered", None),
        ]


def test_manual_transition_settlement_recovers_the_scheduler_incident(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    service, profile_path, transition_id = _build_due_context(tmp_path)
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )
    preview_sha256 = _approved_preview_sha256(service, transition_id)
    real_execute = service.execute_transition

    def fail_execution(*_args, **_kwargs):
        raise RuntimeError("private execution failure")

    monkeypatch.setattr(service, "execute_transition", fail_execution)
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert failure["failed_transition_ids"] == [transition_id]
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)

    monkeypatch.setattr(service, "execute_transition", real_execute)
    manual_result = real_execute(
        transition_id,
        preview_sha256=preview_sha256,
        before_write=lambda: None,
    )
    assert manual_result["status"] == "applied"
    recovered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert recovered["status"] == "succeeded"
    assert recovered["due"] == 0
    assert recovered["recovery_eligible"] is False
    assert scheduler.record_ticker_identity_scheduler_result(recovered, now=now)

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "ticker_identity_scheduler_failure",
                "transition_execution_failed",
            ),
            ("succeeded", "ticker_identity_scheduler_recovered", None),
        ]


def test_recovery_tracks_all_unresolved_transition_ids_across_failure_churn(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    service, profile_path, automation_transition_id = _build_due_context(tmp_path)
    attended_transition_id = "slt_attended_second"
    with sqlite3.connect(profile_path) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(
            conn.execute(
                "SELECT * FROM ticker_identity_transitions WHERE transition_id=?",
                (automation_transition_id,),
            ).fetchone()
        )
        row["transition_id"] = attended_transition_id
        row["transition_dedupe_key"] = (
            str(row["transition_dedupe_key"]) + ":attended-second"
        )
        columns = tuple(row)
        conn.execute(
            "INSERT INTO ticker_identity_transitions ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            tuple(row[column] for column in columns),
        )
        conn.execute(
            "UPDATE ticker_identity_transitions SET approval_authority='automation_policy',"
            "automation_policy_version='test-policy',rule_id='test-rule',"
            "rule_version='1' WHERE transition_id=?",
            (automation_transition_id,),
        )
        conn.commit()

    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    assert scheduler.record_ticker_identity_scheduler_result(
        _scheduler_result(
            status="partial",
            reason="transition_execution_failed",
            transition_ids=[automation_transition_id, attended_transition_id],
            failed_transition_ids=[
                automation_transition_id,
                attended_transition_id,
            ],
        ),
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(
        _scheduler_result(
            status="partial",
            reason="transition_execution_failed",
            transition_ids=[attended_transition_id],
            failed_transition_ids=[attended_transition_id],
        ),
        now=now,
    )
    service.cancel_transition(
        attended_transition_id,
        before_write=lambda: None,
    )

    filtered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert filtered["status"] == "succeeded"
    assert filtered["due"] == 0
    assert scheduler.record_ticker_identity_scheduler_result(filtered, now=now)
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            ("failed", "ticker_identity_scheduler_failure"),
            ("failed", "ticker_identity_scheduler_failure"),
            ("failed", "ticker_identity_scheduler_failure"),
        ]

    service.cancel_transition(
        automation_transition_id,
        before_write=lambda: None,
    )
    recovered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(recovered, now=now)
    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            ("failed", "ticker_identity_scheduler_failure"),
            ("failed", "ticker_identity_scheduler_failure"),
            ("failed", "ticker_identity_scheduler_failure"),
            ("succeeded", "ticker_identity_scheduler_recovered"),
        ]


@pytest.mark.parametrize(
    "legacy_version",
    (None, 999),
    ids=("absent-version", "unknown-version"),
)
def test_legacy_recovery_is_revalidated_before_becoming_an_incident_boundary(
    tmp_path,
    monkeypatch,
    legacy_version,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    service, profile_path, transition_id = _build_due_context(tmp_path)
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=[transition_id],
        failed_transition_ids=[transition_id],
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)

    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "UPDATE ticker_identity_transitions SET approval_authority='automation_policy',"
            "automation_policy_version='test-policy',rule_id='test-rule',"
            "rule_version='1' WHERE transition_id=?",
            (transition_id,),
        )
        legacy_recovery = _scheduler_result(status="succeeded", reason=None)
        if legacy_version is not None:
            legacy_recovery["incident_reconciliation_version"] = legacy_version
        at = now.isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO job_runs ("
            "job_name,status,trigger_source,payload,result,message,error,"
            "started_at,finished_at,duration_ms,created_at,updated_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "ticker_identity.transitions",
                "succeeded",
                "scheduler",
                "{}",
                json.dumps(legacy_recovery, sort_keys=True, separators=(",", ":")),
                "ticker_identity_scheduler_recovered",
                None,
                at,
                at,
                None,
                at,
                at,
            ),
        )
        conn.commit()

    filtered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert filtered["status"] == "succeeded"
    assert filtered["due"] == 0
    assert scheduler.record_ticker_identity_scheduler_result(filtered, now=now)

    with sqlite3.connect(profile_path) as conn:
        rows = conn.execute(
            "SELECT status,message,result FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall()
    assert [(row[0], row[1]) for row in rows] == [
        ("failed", "ticker_identity_scheduler_failure"),
        ("succeeded", "ticker_identity_scheduler_recovered"),
        ("failed", "ticker_identity_scheduler_failure"),
    ]
    assert json.loads(rows[-1][2])["failed_transition_ids"] == [transition_id]


def test_missing_failed_transition_row_never_proves_recovery(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    service, profile_path, transition_id = _build_due_context(tmp_path)
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=[transition_id],
        failed_transition_ids=[transition_id],
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "DELETE FROM ticker_identity_transitions WHERE transition_id=?",
            (transition_id,),
        )
        conn.commit()

    healthy = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert healthy["status"] == "succeeded"
    assert healthy["due"] == 0
    assert scheduler.record_ticker_identity_scheduler_result(healthy, now=now)

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,message FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [("failed", "ticker_identity_scheduler_failure")]


def test_re_enabled_eligible_success_recovers_filtered_automation_incident(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    failure = _scheduler_result(
        status="partial",
        reason="transition_execution_failed",
        transition_ids=["slt_automation"],
        failed_transition_ids=["slt_automation"],
    )
    assert scheduler.record_ticker_identity_scheduler_result(failure, now=now)
    service = _PolicyFilteringDueService(include_attended=False)
    monkeypatch.setattr(scheduler, "_service", lambda: service)
    monkeypatch.setattr(
        scheduler,
        "require_profile_state_write",
        lambda *_args, **_kwargs: None,
    )

    filtered = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=False,
        transition_mutation_allowed=lambda: False,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(filtered, now=now)
    eligible = scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=now,
    )
    assert scheduler.record_ticker_identity_scheduler_result(eligible, now=now)

    assert filtered["recovery_eligible"] is False
    assert eligible["recovery_eligible"] is True
    assert service.executed == ["slt_automation"]
    with sqlite3.connect(profile_path) as conn:
        rows = conn.execute(
            "SELECT status,message,result FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall()
    assert [(row[0], row[1]) for row in rows] == [
        ("failed", "ticker_identity_scheduler_failure"),
        ("succeeded", "ticker_identity_scheduler_recovered"),
    ]
    assert json.loads(rows[1][2])["transition_ids"] == ["slt_automation"]
    assert json.loads(rows[1][2])["recovery_eligible"] is True


def test_repeated_deferral_across_ticks_writes_no_witness_each_time(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    deferred = _scheduler_result(
        status="deferred",
        reason="transition_mutation_disabled",
        transition_ids=["slt_deferred"],
        deferred_transition_ids=["slt_deferred"],
    )

    for offset in range(2):
        assert scheduler.record_ticker_identity_scheduler_result(
            deferred,
            now=datetime(2026, 8, 25, 13, 0, offset, tzinfo=timezone.utc),
        )

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE job_name=?",
            ("ticker_identity.transitions",),
        ).fetchone() == (0,)


def test_scheduler_witness_write_failure_never_logs_raw_database_text(
    tmp_path,
    monkeypatch,
    caplog,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            """
            CREATE TRIGGER reject_ticker_identity_witness
            BEFORE INSERT ON job_runs
            WHEN NEW.job_name = 'ticker_identity.transitions'
            BEGIN
                SELECT RAISE(ABORT, 'private customer detail');
            END
            """
        )
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))

    persisted = scheduler.record_ticker_identity_scheduler_result(
        _scheduler_result(
            status="unavailable",
            reason="profile_store_unavailable",
        ),
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    assert persisted is False
    assert "private customer detail" not in caplog.text
    assert "profile_store_unavailable" in caplog.text
    with sqlite3.connect(profile_path, timeout=0.1, isolation_level=None) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()


def test_scheduler_failure_incident_ignores_successful_companion_churn(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    base = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    for index in range(5):
        assert scheduler.record_ticker_identity_scheduler_result(
            _scheduler_result(
                status="partial",
                reason="transition_execution_failed",
                applied=1,
                transition_ids=[f"slt_ok_{index}", "slt_stuck"],
                failed_transition_ids=["slt_stuck"],
            ),
            now=base,
        )

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE job_name=?",
            ("ticker_identity.transitions",),
        ).fetchone() == (1,)


def test_scheduler_failure_incident_ignores_deferred_companion_churn(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    base = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)

    for index in range(2):
        assert scheduler.record_ticker_identity_scheduler_result(
            _scheduler_result(
                status="partial",
                reason="transition_execution_failed",
                applied=1,
                transition_ids=[
                    f"slt_ok_{index}",
                    "slt_stuck",
                    f"slt_deferred_{index}",
                ],
                failed_transition_ids=["slt_stuck"],
                deferred_transition_ids=[f"slt_deferred_{index}"],
            ),
            now=base,
        )

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,error FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [("failed", "transition_execution_failed")]


def test_scheduler_malformed_summary_records_failure_instead_of_recovery(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    now = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    assert scheduler.record_ticker_identity_scheduler_result(
        _scheduler_result(
            status="unavailable",
            reason="profile_store_unavailable",
        ),
        now=now,
    )
    impossible_success = _scheduler_result(
        status="succeeded",
        reason=None,
        transition_ids=["slt_unaccounted"],
    )

    assert scheduler.record_ticker_identity_scheduler_result(
        impossible_success,
        now=now,
    )

    with sqlite3.connect(profile_path) as conn:
        assert conn.execute(
            "SELECT status,error,message FROM job_runs WHERE job_name=? ORDER BY id",
            ("ticker_identity.transitions",),
        ).fetchall() == [
            (
                "failed",
                "profile_store_unavailable",
                "ticker_identity_scheduler_failure",
            ),
            (
                "failed",
                "ticker_identity_scheduler_failed",
                "ticker_identity_scheduler_failure",
            ),
        ]
