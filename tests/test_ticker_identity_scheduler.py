from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import socket
import sqlite3
import threading


def _build_due_context(tmp_path):
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
        "due": 10,
        "applied": 8,
        "needs_review": 1,
        "already_applied": 0,
        "transition_ids": [f"slt_{index}" for index in range(10)],
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
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
    }
    assert not profile_path.exists()
    assert not market_path.exists()
