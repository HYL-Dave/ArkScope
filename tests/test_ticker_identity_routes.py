from __future__ import annotations

import socket
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient


_AT = "2026-08-23T00:00:00Z"
_SOURCE_REF = "0000000000-26-000001"


def _build_context(
    tmp_path,
    *,
    identity_schema: str = "exact",
    outcomes=("symbol_changed",),
    successor: str | None = "NEW",
):
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

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    profile = ProfileStateStore(profile_path)
    profile.import_lists(
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
            source_ref=_SOURCE_REF,
            filing_form="8-K",
            filing_items=("3.01",),
            evidence_url="https://www.sec.gov/Archives/example/old-8k.htm",
            description="Issuer reports a listing identity transition.",
            observed_at=_AT,
            kinds=(ObservationKind("listing_status_review", "2026-08-25"),),
        )
    )
    observation = market_store.get_observation("sec_edgar", _SOURCE_REF, "OLD")
    fingerprint = observation_fingerprint(observation)
    market_conn.close()

    profile_conn = sqlite3.connect(profile_path)
    investigation = SecurityLifecycleInvestigationStore(
        profile_conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal}",
    )
    case_id = investigation.ensure_case(
        source="sec_edgar",
        source_ref=_SOURCE_REF,
        ticker="OLD",
        at=_AT,
    )
    assessment_id = investigation.create_assessment(
        case_id=case_id,
        relevance="direct_tracked_security",
        confidence="high",
        author="human",
        conclusion="The tracked security has a reviewed listing event.",
        impact_summary="Preserve tracking intent under the reviewed outcome.",
        outcomes=outcomes,
        citations=[
            {
                "reference_kind": "observation",
                "cited_content_sha256": fingerprint,
            }
        ],
        observation_fingerprint_sha256=fingerprint,
        successor_ticker=successor,
        effective_date="2026-08-25",
        at=_AT,
    )
    investigation.accept_assessment(
        assessment_id,
        observation_fingerprint_sha256=fingerprint,
        acceptance_authority="human",
        at=_AT,
    )
    investigation.generate_action_proposals(
        case_id=case_id,
        observation_fingerprint_sha256=fingerprint,
        sources_by_ticker={"OLD": ("manual_lists",)},
        at=_AT,
    )
    if identity_schema == "exact":
        create_ticker_identity_schema(profile_conn)
    elif identity_schema == "partial":
        profile_conn.execute("CREATE TABLE ticker_identity_shadow (id INTEGER)")
        profile_conn.commit()
    profile_conn.close()

    service = TickerIdentityService(
        market_db_path=str(market_path),
        profile_db_path=str(profile_path),
        source_loader=lambda: {"OLD": ("manual_lists",)},
        clock=lambda: "2026-08-25T13:00:00Z",
        id_factory=(
            lambda counters={}: lambda prefix: (
                counters.__setitem__(prefix, counters.get(prefix, 0) + 1)
                or f"{prefix}_{counters[prefix]}"
            )
        )(),
    )
    return {
        "case_id": case_id,
        "market_path": market_path,
        "profile_path": profile_path,
        "service": service,
    }


def _client(context, monkeypatch, permission_calls):
    from src.api import dependencies
    from src.api.routes import ticker_identity as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[dependencies.get_ticker_identity_service] = (
        lambda: context["service"]
    )
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: permission_calls.append((action, detail)),
    )
    return TestClient(app)


def test_preview_approve_cancel_flow_is_typed_and_uses_profile_permission(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    permission_calls: list[tuple[str, dict | None]] = []
    client = _client(context, monkeypatch, permission_calls)

    preview = client.get(
        f"/security-lifecycle/cases/{context['case_id']}/transition-preview"
    )
    assert preview.status_code == 200
    assert preview.json()["eligible"] is True
    digest = preview.json()["preview_sha256"]
    approved = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/approve-transition",
        json={"execute_on": "2026-08-25", "preview_sha256": digest},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    transition_id = approved.json()["transition_id"]
    assert permission_calls == [
        (
            "security_lifecycle_approve_ticker_transition",
            {"case_id": context["case_id"]},
        )
    ]

    cancelled = client.post(
        f"/security-lifecycle/transitions/{transition_id}/cancel"
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert permission_calls[-1] == (
        "security_lifecycle_cancel_ticker_transition",
        {"transition_id": transition_id},
    )


def test_invalid_stale_and_ineligible_requests_stop_before_permission(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path / "valid")
    permission_calls: list[tuple[str, dict | None]] = []
    client = _client(context, monkeypatch, permission_calls)
    preview = client.get(
        f"/security-lifecycle/cases/{context['case_id']}/transition-preview"
    ).json()

    malformed = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/approve-transition",
        json={
            "execute_on": "2026-08-25",
            "preview_sha256": preview["preview_sha256"],
            "unexpected": True,
        },
    )
    assert malformed.status_code == 422
    assert permission_calls == []

    stale = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/approve-transition",
        json={"execute_on": "2026-08-25", "preview_sha256": "f" * 64},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "transition_preview_changed"
    assert permission_calls == []

    ineligible_context = _build_context(
        tmp_path / "ineligible",
        outcomes=("venue_transfer",),
        successor=None,
    )
    ineligible_calls: list[tuple[str, dict | None]] = []
    ineligible_client = _client(ineligible_context, monkeypatch, ineligible_calls)
    ineligible_preview = ineligible_client.get(
        "/security-lifecycle/cases/"
        f"{ineligible_context['case_id']}/transition-preview"
    ).json()
    response = ineligible_client.post(
        "/security-lifecycle/cases/"
        f"{ineligible_context['case_id']}/approve-transition",
        json={
            "execute_on": "2026-08-25",
            "preview_sha256": ineligible_preview["preview_sha256"],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "preview_ineligible"
    assert ineligible_calls == []


def test_missing_or_partial_identity_schema_is_typed_unavailable_and_never_created(
    tmp_path,
    monkeypatch,
):
    for schema_state in ("absent", "partial"):
        context = _build_context(tmp_path / schema_state, identity_schema=schema_state)
        permission_calls: list[tuple[str, dict | None]] = []
        client = _client(context, monkeypatch, permission_calls)

        response = client.get(
            "/security-lifecycle/cases/"
            f"{context['case_id']}/transition-preview"
        )

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "ticker_identity_profile_store_unavailable",
            "store": "profile",
        }
        assert permission_calls == []
        with sqlite3.connect(context["profile_path"]) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name LIKE 'ticker_identity_%'"
                )
            }
        assert tables == (set() if schema_state == "absent" else {"ticker_identity_shadow"})


def test_preview_is_provider_free_and_retry_then_reverse_use_explicit_commands(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    permission_calls: list[tuple[str, dict | None]] = []
    client = _client(context, monkeypatch, permission_calls)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network_not_allowed")
        ),
    )
    preview = client.get(
        f"/security-lifecycle/cases/{context['case_id']}/transition-preview"
    )
    assert preview.status_code == 200
    digest = preview.json()["preview_sha256"]
    approved = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/approve-transition",
        json={"execute_on": "2026-08-25", "preview_sha256": digest},
    ).json()

    applied = client.post(
        f"/security-lifecycle/transitions/{approved['transition_id']}/retry",
        json={"preview_sha256": digest},
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
    reversed_response = client.post(
        f"/security-lifecycle/transitions/{approved['transition_id']}/reverse"
    )
    assert reversed_response.status_code == 200
    assert reversed_response.json()["status"] == "reversed"
    assert [action for action, _detail in permission_calls] == [
        "security_lifecycle_approve_ticker_transition",
        "security_lifecycle_retry_ticker_transition",
        "security_lifecycle_reverse_ticker_transition",
    ]


def test_transition_state_and_due_date_are_validated_before_permission(
    tmp_path,
    monkeypatch,
):
    future = _build_context(tmp_path / "future")
    future_calls: list[tuple[str, dict | None]] = []
    future_client = _client(future, monkeypatch, future_calls)
    preview = future_client.get(
        f"/security-lifecycle/cases/{future['case_id']}/transition-preview",
        params={"execute_on": "2026-08-26"},
    ).json()
    approved = future_client.post(
        f"/security-lifecycle/cases/{future['case_id']}/approve-transition",
        json={
            "execute_on": "2026-08-26",
            "preview_sha256": preview["preview_sha256"],
        },
    ).json()
    calls_after_approval = list(future_calls)

    early = future_client.post(
        f"/security-lifecycle/transitions/{approved['transition_id']}/retry",
        json={"preview_sha256": preview["preview_sha256"]},
    )
    assert early.status_code == 422
    assert early.json()["detail"]["code"] == "transition_not_due"
    not_applied = future_client.post(
        f"/security-lifecycle/transitions/{approved['transition_id']}/reverse"
    )
    assert not_applied.status_code == 422
    assert not_applied.json()["detail"]["code"] == "transition_not_reversible"
    assert future_calls == calls_after_approval

    applied = _build_context(tmp_path / "applied")
    applied_calls: list[tuple[str, dict | None]] = []
    applied_client = _client(applied, monkeypatch, applied_calls)
    applied_preview = applied_client.get(
        f"/security-lifecycle/cases/{applied['case_id']}/transition-preview"
    ).json()
    applied_transition = applied_client.post(
        f"/security-lifecycle/cases/{applied['case_id']}/approve-transition",
        json={
            "execute_on": "2026-08-25",
            "preview_sha256": applied_preview["preview_sha256"],
        },
    ).json()
    applied_client.post(
        "/security-lifecycle/transitions/"
        f"{applied_transition['transition_id']}/retry",
        json={"preview_sha256": applied_preview["preview_sha256"]},
    )
    calls_after_apply = list(applied_calls)
    too_late = applied_client.post(
        "/security-lifecycle/transitions/"
        f"{applied_transition['transition_id']}/cancel"
    )
    assert too_late.status_code == 422
    assert too_late.json()["detail"]["code"] == "transition_not_cancellable"
    assert applied_calls == calls_after_apply


def test_case_detail_exposes_durable_transition_state_without_changing_preview(
    tmp_path,
):
    from src.ticker_identity_transition import TransitionOptions, profile_snapshot_sha256
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService

    context = _build_context(tmp_path)
    options = TransitionOptions(execute_on="2026-08-25")
    preview = context["service"].preview_case(context["case_id"], options=options)
    transition = context["service"].approve_case(
        context["case_id"],
        options=options,
        preview_sha256=preview["preview_sha256"],
        before_write=lambda: None,
    )

    detail = SecurityLifecycleReadService(
        market_db_path=str(context["market_path"]),
        profile_db_path=str(context["profile_path"]),
        source_loader=lambda: {"OLD": ("manual_lists",)},
    ).get_case(context["case_id"])

    assert detail["ticker_transition"] == {
        "transition_id": transition["transition_id"],
        "kind": "symbol_continuation",
        "status": "approved",
        "source_ticker": "OLD",
        "successor_ticker": "NEW",
        "execute_on": "2026-08-25",
        "approved_preview_sha256": preview["preview_sha256"],
        "approved_preview": preview,
        "approval_authority": "attended_user",
        "automation_policy_version": None,
        "rule_id": None,
        "rule_version": None,
        "decision_provenance_sha256": transition[
            "decision_provenance_sha256"
        ],
        "updated_at": "2026-08-25T13:00:00Z",
        "latest_attempt": None,
        "reverse_readiness": None,
        "activity_history": [],
        "activity_count": 0,
        "unacknowledged_activity_count": 0,
    }
    assert profile_snapshot_sha256(preview) == preview["preview_sha256"]


def test_activity_routes_list_acknowledge_and_keep_reverse_separate(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    permission_calls: list[tuple[str, dict | None]] = []
    client = _client(context, monkeypatch, permission_calls)
    preview = client.get(
        f"/security-lifecycle/cases/{context['case_id']}/transition-preview"
    ).json()
    transition = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/approve-transition",
        json={
            "execute_on": "2026-08-25",
            "preview_sha256": preview["preview_sha256"],
        },
    ).json()
    assert client.post(
        f"/security-lifecycle/transitions/{transition['transition_id']}/retry",
        json={"preview_sha256": preview["preview_sha256"]},
    ).status_code == 200

    listed = client.get(
        "/security-lifecycle/transition-activity",
        params={"limit": 10, "unacknowledged_only": True},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["unacknowledged_count"] == 1
    item = listed.json()["items"][0]
    calls_before_missing = list(permission_calls)

    missing = client.post(
        "/security-lifecycle/transition-activity/missing/acknowledge"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "transition_activity_not_found"
    assert permission_calls == calls_before_missing

    acknowledged = client.post(
        "/security-lifecycle/transition-activity/"
        f"{item['activity_id']}/acknowledge"
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"] == "2026-08-25T13:00:00Z"
    assert permission_calls[-1] == (
        "security_lifecycle_acknowledge_transition_activity",
        {"activity_id": item["activity_id"]},
    )

    with sqlite3.connect(context["profile_path"]) as conn:
        assert conn.execute(
            "SELECT status FROM ticker_identity_transitions WHERE transition_id=?",
            (transition["transition_id"],),
        ).fetchone() == ("applied",)
    reversed_response = client.post(
        f"/security-lifecycle/transitions/{transition['transition_id']}/reverse"
    )
    assert reversed_response.status_code == 200
    assert reversed_response.json()["status"] == "reversed"
    history = client.get("/security-lifecycle/transition-activity?limit=10").json()
    assert [row["activity_type"] for row in history["items"]] == [
        "reversed",
        "applied",
    ]
    assert history["items"][1]["acknowledged_at"] == "2026-08-25T13:00:00Z"


def test_case_detail_includes_transition_authority_and_activity_history(tmp_path):
    from src.ticker_identity_transition import TransitionOptions
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService

    context = _build_context(tmp_path)
    options = TransitionOptions(execute_on="2026-08-25")
    preview = context["service"].preview_case(context["case_id"], options=options)
    transition = context["service"].approve_case(
        context["case_id"],
        options=options,
        preview_sha256=preview["preview_sha256"],
        before_write=lambda: None,
    )
    context["service"].execute_transition(
        transition["transition_id"],
        preview_sha256=preview["preview_sha256"],
        before_write=lambda: None,
    )

    detail = SecurityLifecycleReadService(
        market_db_path=str(context["market_path"]),
        profile_db_path=str(context["profile_path"]),
        source_loader=lambda: {"OLD": ("manual_lists",)},
    ).get_case(context["case_id"])
    projected = detail["ticker_transition"]

    assert projected["approval_authority"] == "attended_user"
    assert projected["decision_provenance_sha256"] == transition[
        "decision_provenance_sha256"
    ]
    assert projected["reverse_readiness"]["reversible"] is True
    assert projected["activity_count"] == 1
    assert projected["unacknowledged_activity_count"] == 1
    assert projected["activity_history"][0]["activity_type"] == "applied"
    assert projected["activity_history"][0]["case_id"] == context["case_id"]
    assert "before_snapshot_json" not in projected
    assert "user_owned_changes_json" not in projected["activity_history"][0]


def test_activity_read_failure_is_typed_without_creating_schema(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path, identity_schema="absent")
    permission_calls: list[tuple[str, dict | None]] = []
    client = _client(context, monkeypatch, permission_calls)

    response = client.get("/security-lifecycle/transition-activity")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "ticker_identity_profile_store_unavailable",
        "store": "profile",
    }
    assert permission_calls == []
    with sqlite3.connect(context["profile_path"]) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'ticker_identity_%'"
        ).fetchall() == []
