"""Track A.5: Investor Profile calibration journal + proposal store."""

import asyncio
import json

import pytest

from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import (
    CalibrationStore,
    normalize_proposal_payload,
)
from src.investor_profile_calibration_schema import migrate_calibration_schema
from src.investor_profile_calibration_agent import (
    CALIBRATION_SYSTEM_PROMPT,
    CalibrationAgentResult,
    parse_calibration_model_json,
)


def _calibration_store(path):
    migrate_calibration_schema(path)
    return CalibrationStore(path)


def test_start_session_enforces_single_active_and_explicit_supersede(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
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
    store = _calibration_store(tmp_path / "profile_state.db")
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
    cstore = _calibration_store(db)
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
    store = _calibration_store(tmp_path / "profile_state.db")
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


def test_calibration_prompt_pins_every_enum_value():
    """Live 2026-07-10: two models emitted holding_horizon "years" because the
    prompt showed one example per field but never the allowed sets — the whole
    turn was rejected. Every enum member must appear in the prompt verbatim."""
    from src.investor_profile import HOLDING_HORIZONS, PRESETS, STANCES

    for value in (*HOLDING_HORIZONS, *PRESETS, *STANCES):
        assert value in CALIBRATION_SYSTEM_PROMPT, value


def test_parse_calibration_json_strips_model_supplied_risk_mismatch():
    """Live 2026-07-10: gpt-5.4-mini emitted risk_mismatch despite the prompt ban,
    failing the whole turn. The responder strips it (server re-derives anyway);
    the API-level rejection for direct callers is unchanged."""
    result = parse_calibration_model_json(
        json.dumps(
            {
                "assistant_message": "draft ready",
                "proposal": {
                    "profile_patch": {
                        "risk_appetite": 7,
                        "risk_mismatch": "appetite_above_capacity",
                    },
                    "rationales": {},
                },
            }
        )
    )
    assert result.profile_patch is not None
    assert "risk_mismatch" not in result.profile_patch
    assert result.profile_patch["risk_appetite"] == 7


def test_parse_calibration_json_followup_without_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"What drawdown would make you sell?","proposal":null}'
    )
    assert result == CalibrationAgentResult(
        assistant_message="What drawdown would make you sell?",
        profile_patch=None,
        rationales={},
    )


def test_parse_calibration_json_tolerates_model_mismatch_and_discards_its_value():
    """Contract updated by live verification 2026-07-10: a model-supplied
    risk_mismatch no longer fails the turn — parse discards the model's value and
    the server derives the real one on save (direct API callers are still hard-
    rejected: see test_normalize_proposal_rejects_agent_supplied_mismatch)."""
    result = parse_calibration_model_json(
        '{"assistant_message":"Draft ready","proposal":{"profile_patch":'
        '{"risk_appetite":8,"risk_capacity":4,"risk_mismatch":"none"},"rationales":{}}}'
    )
    assert result.profile_patch is not None
    assert "risk_mismatch" not in result.profile_patch
    assert result.profile_patch["risk_appetite"] == 8


def test_parse_calibration_json_with_default_stance_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"Draft ready","proposal":{"profile_patch":'
        '{"enabled":true,"risk_appetite":8,"risk_capacity":4,"default_stance":"complementary"},'
        '"rationales":{"default_stance":"User asked to be challenged."}}}'
    )
    assert result.profile_patch["default_stance"] == "complementary"
    assert result.rationales["default_stance"] == "User asked to be challenged."


def test_responder_request_contains_no_tool_or_market_language(monkeypatch):
    import src.investor_profile_calibration_agent as mod

    captured = {}

    async def fake_call(*, provider, model, instructions, input_messages):
        captured.update(
            {
                "provider": provider,
                "model": model,
                "instructions": instructions,
                "input_messages": input_messages,
            }
        )
        return '{"assistant_message":"What is your maximum tolerable drawdown?","proposal":null}'

    monkeypatch.setattr(mod, "_call_calibration_llm", fake_call)
    result = asyncio.run(
        mod.live_calibration_responder(
            messages=[{"role": "user", "content": "I want growth."}],
            provider="openai",
            model="gpt-5.4-mini",
        )
    )
    assert result.assistant_message.startswith("What")
    blob = captured["instructions"].lower()
    assert "no market data" in blob
    assert "tool" not in captured
