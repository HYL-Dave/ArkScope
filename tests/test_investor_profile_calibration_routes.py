"""Track A.5: calibration routes — handler-direct, no TestClient."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api.routes import investor_profile_calibration as routes
from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import CalibrationStore
from src.investor_profile_calibration_agent import CalibrationAgentResult


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    return CalibrationStore(db), InvestorProfileStore(db)


def test_start_session_requires_profile_state_gate(stores, monkeypatch):
    cstore, _pstore = stores
    calls = []
    monkeypatch.setattr(
        routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail))
    )

    data = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert calls[0][0] == "investor_profile_calibration_start"
    assert data["active_session"]["status"] == "active"


def test_start_session_conflict_without_explicit_supersede(stores, monkeypatch):
    cstore, _pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    with pytest.raises(HTTPException) as exc:
        routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "calibration_session_active"


def test_send_message_appends_user_assistant_and_inert_proposal(stores, monkeypatch):
    cstore, pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    sess = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)["active_session"]

    async def fake_responder(*, messages, provider, model):
        assert provider is None and model is None
        assert messages[-1]["role"] == "user"
        return CalibrationAgentResult(
            assistant_message="You sound growth-oriented but drawdown-sensitive.",
            profile_patch={
                "enabled": True,
                "risk_appetite": 8,
                "risk_capacity": 4,
                "default_stance": "complementary",
            },
            rationales={
                "risk_capacity": "User described likely selling after a 10% drawdown."
            },
        )

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    data = asyncio.run(
        routes.send_calibration_message(
            routes.CalibrationMessageBody(
                session_id=sess["id"], content="I chase AI stocks but panic at drawdowns."
            ),
            store=cstore,
        )
    )

    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert data["latest_proposal"]["status"] == "draft"
    assert data["latest_proposal"]["profile_patch"]["risk_mismatch"] == "appetite_above_capacity"
    assert pstore.get().enabled is False


def test_approve_proposal_uses_existing_profile_save_and_records_provenance(stores, monkeypatch):
    cstore, pstore = stores
    calls = []
    monkeypatch.setattr(
        routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail))
    )
    sess = cstore.start_session()
    proposal = cstore.create_proposal(
        session_id=sess.id,
        profile_patch={
            "enabled": True,
            "risk_appetite": 8,
            "risk_capacity": 4,
            "default_stance": "complementary",
        },
        rationales={},
    )

    data = routes.approve_calibration_proposal(
        proposal.id,
        routes.ApproveProposalBody(
            profile_patch={"enabled": True, "risk_appetite": 7, "risk_capacity": 4}
        ),
        store=cstore,
        profile_store=pstore,
    )

    assert calls[0][0] == "investor_profile_calibration_approve"
    assert data["proposal"]["status"] == "approved"
    assert data["proposal"]["approved_at"] is not None
    assert data["proposal"]["changed_fields"] == [
        "enabled",
        "risk_appetite",
        "risk_capacity",
        "risk_mismatch",
    ]
    assert data["profile"]["risk_mismatch"] == "appetite_above_capacity"
    assert pstore.get().risk_appetite == 7


def test_reject_proposal_keeps_profile_unchanged(stores, monkeypatch):
    cstore, pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    sess = cstore.start_session()
    proposal = cstore.create_proposal(session_id=sess.id, profile_patch={"enabled": True}, rationales={})

    data = routes.reject_calibration_proposal(proposal.id, store=cstore)

    assert data["proposal"]["status"] == "rejected"
    assert pstore.get().enabled is False


def test_calibration_router_mounts_on_real_app():
    from src.api.app import create_app

    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/profile/investor/calibration" in paths


def test_route_default_responder_is_live_seam_not_unavailable():
    assert routes._default_responder is routes.default_calibration_responder
    assert routes._default_responder is not routes.unavailable_responder
