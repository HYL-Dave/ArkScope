from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import socket
import sqlite3
import threading

import pytest


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
    rows = service.list_due_transitions(on_date="2026-08-25", limit=10)
    return next(
        str(row["approved_preview_sha256"])
        for row in rows
        if row["transition_id"] == transition_id
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
    transition = service.list_due_transitions(on_date="2026-08-25", limit=10)[0]
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

        def list_due_transitions(self, *, on_date, limit):
            self.list_call = (on_date, limit)
            return [
                {
                    "transition_id": f"slt_{index}",
                    "approved_preview_sha256": str(index % 10) * 64,
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
        limit=10,
        now=datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc),
    )

    assert service.list_call == ("2026-08-23", 10)
    assert len(service.executed) == 10
    assert all(row[2] == "scheduler" for row in service.executed)
    assert result == {
        "status": "partial",
        "reason": "transition_execution_failed",
        "due": 10,
        "applied": 8,
        "needs_review": 1,
        "already_applied": 0,
        "transition_ids": [f"slt_{index}" for index in range(10)],
        "failed_transition_ids": ["slt_2"],
    }
    assert len(permission_calls) == 8


def test_due_runner_is_provider_free_and_concurrent_ticks_apply_once(
    tmp_path,
    monkeypatch,
):
    from src.service import ticker_identity_scheduler as scheduler

    service, profile_path, transition_id = _build_due_context(tmp_path)
    barrier = threading.Barrier(2)
    original_list_due = service.list_due_transitions

    def synchronized_list_due(*, on_date, limit):
        rows = original_list_due(on_date=on_date, limit=limit)
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


def test_due_runner_with_no_identity_component_creates_nothing(tmp_path, monkeypatch):
    from src.service import ticker_identity_scheduler as scheduler

    profile_path = tmp_path / "profile_state.db"
    market_path = tmp_path / "market_data.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))

    result = scheduler.run_due_ticker_identity_transitions(
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "unavailable",
        "reason": "profile_store_missing",
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
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
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "not_installed",
        "reason": "identity_schema_absent",
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
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
        now=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    )

    assert result == {
        "status": "unavailable",
        "reason": "identity_schema_mismatch",
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }
    assert not market_path.exists()


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
