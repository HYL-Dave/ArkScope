"""Track A.5: Investor Profile calibration journal + proposal store."""

import pytest

from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import (
    CalibrationStore,
    normalize_proposal_payload,
)
from src.investor_profile_calibration_agent import (
    CALIBRATION_SYSTEM_PROMPT,
    CalibrationAgentResult,
    parse_calibration_model_json,
)


def test_start_session_enforces_single_active_and_explicit_supersede(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    first = store.start_session()
    assert first.status == "active"
    assert store.get_active_session().id == first.id

    with pytest.raises(ValueError, match="calibration_session_active"):
        store.start_session()

    second = store.start_session(supersede_active=True)
    assert second.status == "active"
    assert store.get_session(first.id).status == "superseded"
    assert store.get_active_session().id == second.id
    assert [s.id for s in store.list_sessions()] == [second.id, first.id]


def test_messages_are_append_only_and_role_checked(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    sess = store.start_session()
    m1 = store.append_message(sess.id, role="user", content="I chase AI stocks.")
    m2 = store.append_message(
        sess.id, role="assistant", content="What drawdown would make you sell?"
    )

    assert [m.content for m in store.list_messages(sess.id)] == [m1.content, m2.content]
    with pytest.raises(ValueError, match="invalid calibration role"):
        store.append_message(sess.id, role="system", content="hidden")
    with pytest.raises(ValueError, match="content is required"):
        store.append_message(sess.id, role="user", content="   ")


def test_create_proposal_is_inert_and_server_derives_mismatch(tmp_path):
    db = tmp_path / "profile_state.db"
    cstore = CalibrationStore(db)
    pstore = InvestorProfileStore(db)
    sess = cstore.start_session()

    proposal = cstore.create_proposal(
        session_id=sess.id,
        profile_patch={
            "enabled": True,
            "risk_appetite": 9,
            "risk_capacity": 4,
            "default_stance": "complementary",
        },
        rationales={
            "risk_capacity": "User said a 10% drawdown would likely trigger selling."
        },
    )

    assert proposal.status == "draft"
    assert proposal.profile_patch["risk_mismatch"] == "appetite_above_capacity"
    assert "risk_mismatch" not in proposal.raw_profile_patch
    assert pstore.get().enabled is False


def test_reject_and_approve_proposal_status_are_terminal(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    sess = store.start_session()
    proposal = store.create_proposal(
        session_id=sess.id,
        profile_patch={"enabled": True, "risk_appetite": 8, "risk_capacity": 4},
        rationales={},
    )

    rejected = store.reject_proposal(proposal.id)
    assert rejected.status == "rejected"
    with pytest.raises(ValueError, match="proposal_not_draft"):
        store.mark_proposal_approved(proposal.id, changed_fields=["risk_appetite"])


def test_normalize_proposal_rejects_agent_supplied_mismatch():
    with pytest.raises(ValueError, match="risk_mismatch"):
        normalize_proposal_payload({"risk_mismatch": "none"}, rationales={})


def test_calibration_prompt_forbids_research_advice_and_tools():
    p = CALIBRATION_SYSTEM_PROMPT.lower()
    assert "do not give investment advice" in p
    assert "do not recommend securities" in p
    assert "no market data" in p
    assert "profile proposal" in p


def test_parse_calibration_json_followup_without_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"What drawdown would make you sell?","proposal":null}'
    )
    assert result == CalibrationAgentResult(
        assistant_message="What drawdown would make you sell?",
        profile_patch=None,
        rationales={},
    )


def test_parse_calibration_json_with_proposal_rejects_direct_mismatch():
    with pytest.raises(ValueError, match="risk_mismatch"):
        parse_calibration_model_json(
            '{"assistant_message":"Draft ready","proposal":{"profile_patch":{"risk_mismatch":"none"},"rationales":{}}}'
        )


def test_parse_calibration_json_with_default_stance_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"Draft ready","proposal":{"profile_patch":'
        '{"enabled":true,"risk_appetite":8,"risk_capacity":4,"default_stance":"complementary"},'
        '"rationales":{"default_stance":"User asked to be challenged."}}}'
    )
    assert result.profile_patch["default_stance"] == "complementary"
    assert result.rationales["default_stance"] == "User asked to be challenged."
