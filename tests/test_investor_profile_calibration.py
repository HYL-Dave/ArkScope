"""Track A.5: Investor Profile calibration journal + proposal store."""

import asyncio
import json
import sqlite3
from dataclasses import FrozenInstanceError, asdict, dataclass

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
from src.investor_profile_calibration_policy import OPENING_PROMPT_ID, OPENING_PROMPTS


def _calibration_store(path):
    migrate_calibration_schema(path)
    return CalibrationStore(path)


@dataclass(frozen=True)
class _GuidedResult:
    assistant_message: str
    addressed_topic_id: str
    topic_covered: bool
    next_topic_id: str | None
    profile_patch: dict | None = None
    rationales: dict | None = None


def _result(**overrides):
    values = {
        "assistant_message": "What should we cover next?",
        "addressed_topic_id": "loss_response",
        "topic_covered": True,
        "next_topic_id": "financial_capacity",
        "profile_patch": None,
        "rationales": {},
    }
    values.update(overrides)
    return _GuidedResult(**values)


def _raw_proposal(db, proposal_id):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM investor_profile_calibration_proposals WHERE id=?",
            (proposal_id,),
        ).fetchone()
    assert row is not None
    return dict(row)


def test_start_session_enforces_single_active_and_explicit_supersede(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    first = store.start_session()
    assert first.status == "active"
    assert store.get_active_session().id == first.id

    with pytest.raises(ValueError, match="calibration_session_active"):
        store.start_session()

    store.begin_answer_turn(
        session_id=first.id,
        turn_id="completed-before-supersede",
        answer="Finish this turn before replacing the session.",
    )
    completed_before = store.complete_turn(
        "completed-before-supersede",
        result=_result(next_topic_id="financial_capacity"),
    )
    pending_answer = "This in-flight answer belongs only to the old session."
    store.begin_answer_turn(
        session_id=first.id,
        turn_id="pending-at-supersede",
        answer=pending_answer,
    )
    first_before = store.get_session(first.id)
    messages_before = store.list_messages(first.id)

    second = store.start_session(supersede_active=True)
    assert second.status == "active"
    first_after = store.get_session(first.id)
    assert first_after.status == "superseded"
    assert first_after.covered_topics == first_before.covered_topics == ["loss_response"]
    assert first_after.current_topic_id == first_before.current_topic_id == "financial_capacity"
    assert first_after.current_question_message_id == first_before.current_question_message_id
    assert store.get_active_session().id == second.id
    assert [s.id for s in store.list_sessions()] == [second.id, first.id]

    pending = store.get_turn("pending-at-supersede")
    assert pending.status == "failed"
    assert pending.error_code == "calibration_session_superseded"
    assert pending.diagnostic == "Calibration session was superseded before Provider completion."
    assert len(pending.diagnostic) <= 240
    assert pending_answer not in pending.diagnostic
    assert store.get_pending_turn(first.id) is None
    assert store.get_turn(completed_before.id).to_dict() == completed_before.to_dict()

    with pytest.raises(ValueError, match="calibration_turn_not_retryable"):
        store.retry_turn("pending-at-supersede")
    with pytest.raises(ValueError, match="calibration_turn_retry_required"):
        store.complete_turn(
            "pending-at-supersede",
            result=_result(
                addressed_topic_id="financial_capacity",
                next_topic_id="time_horizon",
            ),
        )
    assert store.get_session(first.id).to_dict() == first_after.to_dict()
    assert [message.to_dict() for message in store.list_messages(first.id)] == [
        message.to_dict() for message in messages_before
    ]


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


def test_start_guided_session_persists_opening_prompt_without_provider_call(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)

    session = store.start_session()
    messages = store.list_messages(session.id)

    assert session.interview_version == 2
    assert session.covered_topics == []
    assert session.current_topic_id == "loss_response"
    assert session.current_question_message_id == messages[0].id
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert messages[0].topic_id == "loss_response"
    assert messages[0].prompt_id == OPENING_PROMPT_ID
    assert messages[0].content == OPENING_PROMPTS[OPENING_PROMPT_ID]
    assert session.to_dict()["covered_topics"] == []
    assert messages[0].to_dict()["prompt_id"] == OPENING_PROMPT_ID

    broken_db = tmp_path / "opening-fault.db"
    broken = _calibration_store(broken_db)
    with sqlite3.connect(broken_db) as conn:
        conn.execute(
            "CREATE TRIGGER fail_guided_opening BEFORE INSERT ON "
            "investor_profile_calibration_messages BEGIN "
            "SELECT RAISE(FAIL, 'opening insert failed'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="opening insert failed"):
        broken.start_session()
    with sqlite3.connect(broken_db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM investor_profile_calibration_sessions"
        ).fetchone()[0] == 0


def test_begin_turn_is_idempotent_and_allows_only_one_pending_turn(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    session = store.start_session()

    first = store.begin_answer_turn(
        session_id=session.id,
        turn_id="turn-1",
        answer="I would wait and reassess.",
        provider="openai",
        model="test-model",
    )
    repeated = store.begin_answer_turn(
        session_id=session.id,
        turn_id="turn-1",
        answer="I would wait and reassess.",
        provider="openai",
        model="test-model",
    )

    assert first.call_provider is True
    assert repeated.call_provider is False
    assert first.turn.id == repeated.turn.id == "turn-1"
    assert len(store.list_messages(session.id)) == 2
    assert len(store.list_turns(session.id)) == 1
    with pytest.raises(FrozenInstanceError):
        first.call_provider = False

    other_instance = CalibrationStore(db)
    with pytest.raises(ValueError, match="calibration_turn_pending"):
        other_instance.begin_answer_turn(
            session_id=session.id,
            turn_id="turn-2",
            answer="A second answer must not be accepted yet.",
        )
    assert [turn.id for turn in store.list_turns(session.id)] == ["turn-1"]


def test_begin_turn_records_pre_provider_answer_and_frozen_topic(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    session = store.start_session()
    answer = "  我會先重新檢查 thesis，再決定。  "

    work = store.begin_answer_turn(
        session_id=session.id,
        turn_id="source-answer",
        answer=answer,
        provider="anthropic",
        model="model-a",
    )
    messages = store.list_messages(session.id)
    turn = store.get_turn("source-answer")

    assert turn is not None
    assert turn.status == "pending"
    assert turn.question_message_id == session.current_question_message_id
    assert turn.addressed_topic_id == "loss_response"
    assert messages[-1].content == answer
    assert messages[-1].turn_id == "source-answer"
    assert messages[-1].topic_id == "loss_response"
    assert messages[-1].prompt_id == OPENING_PROMPT_ID
    assert work.answer == answer
    assert work.current_topic_id == "loss_response"
    assert work.question_message_id == session.current_question_message_id
    assert work.to_dict() == {
        "turn_id": "source-answer",
        "status": "pending",
        "call_provider": True,
        "message_count": 2,
        "covered_topics": [],
        "current_topic_id": "loss_response",
    }


def test_complete_turn_advances_adaptive_uncovered_topic(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="adaptive-turn",
        answer="I would verify whether the thesis changed.",
    )

    completed = store.complete_turn(
        "adaptive-turn",
        result=_result(
            assistant_message="How should I challenge your investment process?",
            next_topic_id="assistant_style",
        ),
    )

    current = store.get_session(session.id)
    messages = store.list_messages(session.id)
    assert completed.status == "completed"
    assert completed.next_topic_id == "assistant_style"
    assert current.covered_topics == ["loss_response"]
    assert current.current_topic_id == "assistant_style"
    assert current.current_question_message_id == messages[-1].id
    assert messages[-1].role == "assistant"
    assert messages[-1].turn_id == "adaptive-turn"
    assert messages[-1].topic_id == "assistant_style"
    assert messages[-1].prompt_id is None
    assert [message.role for message in messages] == ["assistant", "user", "assistant"]


def test_complete_turn_rejects_wrong_addressed_topic_without_advancing(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="wrong-topic",
        answer="This source answer must remain persisted.",
    )
    before = store.get_session(session.id)

    with pytest.raises(ValueError, match="calibration_catalog_validation_failed"):
        store.complete_turn(
            "wrong-topic",
            result=_result(addressed_topic_id="financial_capacity"),
        )

    after = store.get_session(session.id)
    failed = store.get_turn("wrong-topic")
    messages = store.list_messages(session.id)
    assert failed.status == "failed"
    assert failed.error_code == "calibration_catalog_validation_failed"
    assert len(failed.diagnostic) <= 240
    assert after.covered_topics == before.covered_topics == []
    assert after.current_topic_id == before.current_topic_id == "loss_response"
    assert after.current_question_message_id == before.current_question_message_id
    assert [message.role for message in messages] == ["assistant", "user"]
    assert messages[-1].content == "This source answer must remain persisted."
    assert store.latest_proposal(session.id) is None

    secret = "non-mapping rationale value must not survive"
    rationale_cases = (
        ("empty-list-rationales", {"risk_appetite": 7}, []),
        ("list-rationales-without-patch", None, [{"secret": secret}]),
    )
    for case, profile_patch, rationales in rationale_cases:
        case_db = tmp_path / case / "profile_state.db"
        case_store = _calibration_store(case_db)
        InvestorProfileStore(case_db)
        case_session = case_store.start_session()
        turn_id = f"{case}-turn"
        case_store.begin_answer_turn(
            session_id=case_session.id,
            turn_id=turn_id,
            answer="Validate rationale structure before changing session state.",
        )

        with pytest.raises(ValueError, match="calibration_result_validation_failed"):
            case_store.complete_turn(
                turn_id,
                result=_result(profile_patch=profile_patch, rationales=rationales),
            )

        invalid = case_store.get_turn(turn_id)
        unchanged = case_store.get_session(case_session.id)
        assert invalid.status == "failed"
        assert invalid.error_code == "calibration_result_validation_failed"
        assert len(invalid.diagnostic) <= 240
        assert unchanged.covered_topics == []
        assert unchanged.current_topic_id == "loss_response"
        assert unchanged.current_question_message_id == case_session.current_question_message_id
        assert case_store.latest_proposal(case_session.id) is None
        assert [message.role for message in case_store.list_messages(case_session.id)] == [
            "assistant",
            "user",
        ]
        assert secret not in invalid.diagnostic


def test_complete_turn_rejects_unknown_or_covered_next_topic_without_advancing(tmp_path):
    for case, next_topic in (("unknown", "not_in_catalog"), ("covered", "loss_response")):
        store = _calibration_store(tmp_path / case / "profile_state.db")
        session = store.start_session()
        turn_id = f"{case}-next"
        store.begin_answer_turn(
            session_id=session.id,
            turn_id=turn_id,
            answer=f"Answer for {case} next topic.",
        )

        with pytest.raises(ValueError, match="calibration_catalog_validation_failed"):
            store.complete_turn(turn_id, result=_result(next_topic_id=next_topic))

        unchanged = store.get_session(session.id)
        assert unchanged.covered_topics == []
        assert unchanged.current_topic_id == "loss_response"
        assert unchanged.current_question_message_id == session.current_question_message_id
        assert store.get_turn(turn_id).status == "failed"
        assert [message.role for message in store.list_messages(session.id)] == [
            "assistant",
            "user",
        ]


def test_failed_turn_retains_answer_and_is_retryable_with_same_turn_id(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    session = store.start_session()
    answer = "Keep this exact answer for retry."
    initial = store.begin_answer_turn(
        session_id=session.id,
        turn_id="retry-me",
        answer=answer,
        provider="openai",
        model="first-model",
    )

    failed = store.fail_turn(
        "retry-me",
        error_code="calibration_responder_failed",
        diagnostic="provider detail " + ("x" * 1000),
    )
    assert failed.status == "failed"
    assert failed.attempt_count == 1
    assert len(failed.diagnostic) <= 240
    with pytest.raises(ValueError, match="calibration_turn_retry_required"):
        store.begin_answer_turn(
            session_id=session.id,
            turn_id="retry-me",
            answer=answer,
        )

    retried = store.retry_turn("retry-me", provider="anthropic", model="retry-model")
    assert retried.call_provider is True
    assert retried.turn.status == "pending"
    assert retried.turn.attempt_count == 2
    assert retried.turn.id == initial.turn.id
    assert retried.question_message_id == initial.question_message_id
    assert retried.current_topic_id == initial.current_topic_id
    assert retried.answer == initial.answer == answer
    assert [message.content for message in store.list_messages(session.id)].count(answer) == 1


def test_startup_reconciliation_marks_pending_turn_interrupted(tmp_path):
    store = _calibration_store(tmp_path / "profile_state.db")
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="interrupted-turn",
        answer="Persist me before process shutdown.",
    )

    assert store.reconcile_interrupted_turns() == 1
    assert store.reconcile_interrupted_turns() == 0
    interrupted = store.get_turn("interrupted-turn")
    assert interrupted.status == "interrupted"
    assert interrupted.error_code == "calibration_turn_interrupted"
    assert interrupted.attempt_count == 1
    assert store.get_pending_turn(session.id) is None

    retried = store.retry_turn("interrupted-turn")
    assert retried.turn.status == "pending"
    assert retried.turn.attempt_count == 2
    assert retried.answer == "Persist me before process shutdown."


def test_request_proposal_uses_covered_topics_without_synthetic_user_message(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    InvestorProfileStore(db)
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="cover-loss",
        answer="I would review the thesis.",
    )
    store.complete_turn("cover-loss", result=_result(next_topic_id="assistant_style"))
    before_user_ids = [m.id for m in store.list_messages(session.id) if m.role == "user"]

    work = store.begin_proposal_turn(
        session_id=session.id,
        turn_id="propose-now",
        provider="openai",
        model="test-model",
    )
    assert work.kind == "proposal_request"
    assert work.request_proposal is True
    assert work.covered_topics == ("loss_response",)
    assert [m.id for m in store.list_messages(session.id) if m.role == "user"] == before_user_ids

    store.complete_turn(
        "propose-now",
        result=_result(
            assistant_message="I prepared the supported part of your profile.",
            addressed_topic_id="assistant_style",
            topic_covered=True,
            next_topic_id=None,
            profile_patch={"risk_appetite": 7, "default_stance": "neutral"},
            rationales={"risk_appetite": "Source rationale", "default_stance": "drop"},
        ),
    )
    proposal = store.latest_proposal(session.id)
    assert proposal.profile_patch == {"risk_appetite": 7}
    assert proposal.covered_topics == ["loss_response"]
    assert [m.id for m in store.list_messages(session.id) if m.role == "user"] == before_user_ids


def test_create_guided_proposal_clamps_to_covered_fields_and_records_base_values(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    profile_store.save(
        {
            "enabled": True,
            "risk_appetite": 4,
            "risk_capacity": 5,
            "drawdown_tolerance_pct": 12,
            "freeform_notes": "user-owned note",
            "skill_mode": "suggest_only",
        }
    )
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="proposal-turn",
        answer="I can tolerate a larger drawdown if the thesis remains intact.",
    )
    rejected_secret = "rejected value must never be retained"

    store.complete_turn(
        "proposal-turn",
        result=_result(
            profile_patch={
                "risk_appetite": "7",
                "drawdown_tolerance_pct": "20",
                "risk_capacity": 9,
                "enabled": False,
                "freeform_notes": rejected_secret,
                "risk_mismatch": "none",
                "unknown_field": {"secret": rejected_secret},
            },
            rationales={
                "risk_appetite": "The user described a deliberate review.",
                "drawdown_tolerance_pct": "The user named a wider tolerance.",
                "risk_capacity": rejected_secret,
            },
        ),
    )

    proposal = store.latest_proposal(session.id)
    assert proposal.profile_patch == {
        "risk_appetite": 7,
        "drawdown_tolerance_pct": 20.0,
    }
    assert proposal.proposed_fields == ["risk_appetite", "drawdown_tolerance_pct"]
    assert proposal.covered_topics == ["loss_response"]
    assert proposal.rationales == {
        "risk_appetite": "The user described a deliberate review.",
        "drawdown_tolerance_pct": "The user named a wider tolerance.",
    }
    public = proposal.to_dict()
    assert "base_values" not in public
    assert "rejected_fields" not in public
    assert "raw_profile_patch" not in public

    row = _raw_proposal(db, proposal.id)
    assert row["profile_patch_json"] == (
        '{"risk_appetite":7,"drawdown_tolerance_pct":20.0}'
    )
    assert row["base_values_json"] == (
        '{"risk_appetite":4,"drawdown_tolerance_pct":12.0}'
    )
    assert row["covered_topics_json"] == '["loss_response"]'
    assert json.loads(row["rejected_fields_json"]) == sorted(
        ["enabled", "freeform_notes", "risk_capacity", "risk_mismatch", "unknown_field"]
    )
    assert row["raw_profile_patch_json"] == "{}"
    assert rejected_secret not in json.dumps(row, ensure_ascii=False)

    uncovered_list_db = tmp_path / "uncovered-malformed-list.db"
    uncovered_list_store = _calibration_store(uncovered_list_db)
    InvestorProfileStore(uncovered_list_db)
    uncovered_list_session = uncovered_list_store.start_session()
    uncovered_list_store.begin_answer_turn(
        session_id=uncovered_list_session.id,
        turn_id="uncovered-malformed-list",
        answer="Only the covered risk field belongs in this proposal.",
    )
    uncovered_completed = uncovered_list_store.complete_turn(
        "uncovered-malformed-list",
        result=_result(
            profile_patch={"risk_appetite": 7, "avoidances": [17]},
        ),
    )
    uncovered_proposal = uncovered_list_store.latest_proposal(
        uncovered_list_session.id
    )
    uncovered_row = _raw_proposal(uncovered_list_db, uncovered_proposal.id)
    assert uncovered_completed.status == "completed"
    assert uncovered_completed.error_code is None
    assert uncovered_proposal.profile_patch == {"risk_appetite": 7}
    assert uncovered_proposal.proposed_fields == ["risk_appetite"]
    assert json.loads(uncovered_row["rejected_fields_json"]) == ["avoidances"]
    assert uncovered_row["raw_profile_patch_json"] == "{}"
    assert "[17]" not in json.dumps(uncovered_proposal.to_dict(), ensure_ascii=False)
    assert "[17]" not in json.dumps(uncovered_row, ensure_ascii=False)

    invalid_list_cases = (
        (
            "preferred_edge",
            "investment_approach",
            [{"secret": "nested preferred-edge secret"}],
            "nested preferred-edge secret",
        ),
        ("avoidances", "risk_avoidances", [17], None),
        (
            "behavioral_flags",
            "behavioral_patterns",
            ["anchoring", {"secret": "nested behavioral-flags secret"}],
            "nested behavioral-flags secret",
        ),
    )
    for field, topic_id, invalid_value, secret_marker in invalid_list_cases:
        invalid_db = tmp_path / f"invalid-{field}.db"
        invalid_store = _calibration_store(invalid_db)
        InvestorProfileStore(invalid_db)
        invalid_session = invalid_store.start_session()
        invalid_store.begin_answer_turn(
            session_id=invalid_session.id,
            turn_id=f"advance-{field}",
            answer="Advance to the list-backed calibration topic.",
        )
        invalid_store.complete_turn(
            f"advance-{field}",
            result=_result(next_topic_id=topic_id),
        )
        invalid_store.begin_answer_turn(
            session_id=invalid_session.id,
            turn_id=f"invalid-{field}",
            answer="Reject malformed structured proposal values.",
        )

        with pytest.raises(ValueError, match="calibration_proposal_validation_failed"):
            invalid_store.complete_turn(
                f"invalid-{field}",
                result=_result(
                    addressed_topic_id=topic_id,
                    next_topic_id="financial_capacity",
                    profile_patch={field: invalid_value},
                ),
            )

        invalid_turn = invalid_store.get_turn(f"invalid-{field}")
        invalid_session_state = invalid_store.get_session(invalid_session.id)
        invalid_messages = invalid_store.list_messages(invalid_session.id)
        assert invalid_turn.status == "failed"
        assert invalid_turn.error_code == "calibration_proposal_validation_failed"
        assert len(invalid_turn.diagnostic) <= 240
        assert str(invalid_value) not in invalid_turn.diagnostic
        assert invalid_session_state.covered_topics == ["loss_response"]
        assert invalid_session_state.current_topic_id == topic_id
        assert invalid_store.latest_proposal(invalid_session.id) is None
        assert [message.role for message in invalid_messages] == [
            "assistant",
            "user",
            "assistant",
            "user",
        ]
        exposed = {
            "session": invalid_session_state.to_dict(),
            "turn": invalid_turn.to_dict(),
            "messages": [message.to_dict() for message in invalid_messages],
        }
        with sqlite3.connect(invalid_db) as conn:
            conn.row_factory = sqlite3.Row
            persisted = {
                "turn": dict(
                    conn.execute(
                        "SELECT * FROM investor_profile_calibration_turns WHERE id=?",
                        (invalid_turn.id,),
                    ).fetchone()
                ),
                "proposal_count": conn.execute(
                    "SELECT COUNT(*) FROM investor_profile_calibration_proposals "
                    "WHERE session_id=?",
                    (invalid_session.id,),
                ).fetchone()[0],
            }
        assert persisted["proposal_count"] == 0
        if secret_marker is not None:
            assert secret_marker not in json.dumps(exposed, ensure_ascii=False)
            assert secret_marker not in json.dumps(persisted, ensure_ascii=False)

    calibration_only_db = tmp_path / "calibration-only.db"
    migrate_calibration_schema(calibration_only_db)
    calibration_only_store = CalibrationStore(calibration_only_db)
    calibration_only_session = calibration_only_store.start_session()
    calibration_only_store.begin_answer_turn(
        session_id=calibration_only_session.id,
        turn_id="calibration-only-proposal",
        answer="Use default profile values as this proposal's exact base.",
    )
    calibration_only_completed = calibration_only_store.complete_turn(
        "calibration-only-proposal",
        result=_result(
            profile_patch={
                "risk_appetite": "6",
                "drawdown_tolerance_pct": "18",
            },
        ),
    )
    calibration_only_proposal = calibration_only_store.latest_proposal(
        calibration_only_session.id
    )
    calibration_only_row = _raw_proposal(
        calibration_only_db, calibration_only_proposal.id
    )
    assert calibration_only_completed.status == "completed"
    assert calibration_only_proposal.profile_patch == {
        "risk_appetite": 6,
        "drawdown_tolerance_pct": 18.0,
    }
    assert calibration_only_row["base_values_json"] == (
        '{"risk_appetite":null,"drawdown_tolerance_pct":null}'
    )
    with sqlite3.connect(calibration_only_db) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='investor_profile'"
        ).fetchone() is None

    malformed_tables = (
        ("lowercase", "CREATE TABLE investor_profile (id TEXT PRIMARY KEY)"),
        ("uppercase", "CREATE TABLE INVESTOR_PROFILE (id TEXT PRIMARY KEY)"),
    )
    for case, ddl in malformed_tables:
        malformed_db = tmp_path / f"malformed-profile-{case}.db"
        malformed_store = _calibration_store(malformed_db)
        with sqlite3.connect(malformed_db) as conn:
            conn.execute(ddl)
        malformed_session = malformed_store.start_session()
        turn_id = f"malformed-profile-proposal-{case}"
        malformed_store.begin_answer_turn(
            session_id=malformed_session.id,
            turn_id=turn_id,
            answer="A malformed profile table must fail closed.",
        )
        with pytest.raises(sqlite3.OperationalError):
            malformed_store.complete_turn(
                turn_id,
                result=_result(profile_patch={"risk_appetite": 6}),
            )
        assert malformed_store.get_turn(turn_id).status == "pending"
        assert malformed_store.get_session(malformed_session.id).covered_topics == []
        assert malformed_store.latest_proposal(malformed_session.id) is None


def test_all_illegal_proposal_fields_create_no_proposal(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    InvestorProfileStore(db)
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="illegal-proposal",
        answer="Keep the answer even if the patch is unusable.",
    )

    completed = store.complete_turn(
        "illegal-proposal",
        result=_result(
            profile_patch={
                "enabled": True,
                "risk_capacity": 8,
                "freeform_notes": "never retain me",
                "risk_mismatch": "none",
                "unknown": "never retain me either",
            },
            rationales={"enabled": "not legal"},
        ),
    )

    assert completed.status == "completed"
    assert store.latest_proposal(session.id) is None
    assert store.get_session(session.id).covered_topics == ["loss_response"]
    assert [m.role for m in store.list_messages(session.id)] == [
        "assistant",
        "user",
        "assistant",
    ]


def test_pending_proposal_blocks_second_draft_for_session(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    InvestorProfileStore(db)
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="first-draft",
        answer="I would wait and reassess.",
    )
    store.complete_turn(
        "first-draft",
        result=_result(profile_patch={"risk_appetite": 7}),
    )
    first = store.latest_proposal(session.id)
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="second-draft",
        answer="My finances can absorb moderate volatility.",
    )
    before = store.get_session(session.id)

    with pytest.raises(ValueError, match="calibration_proposal_pending"):
        store.complete_turn(
            "second-draft",
            result=_result(
                addressed_topic_id="financial_capacity",
                next_topic_id="time_horizon",
                profile_patch={"risk_capacity": 6},
            ),
        )

    assert store.latest_proposal(session.id).id == first.id
    assert len([p for p in store.list_proposals(session.id) if p.status == "draft"]) == 1
    assert store.get_turn("second-draft").status == "failed"
    after = store.get_session(session.id)
    assert after.covered_topics == before.covered_topics
    assert after.current_topic_id == before.current_topic_id
    assert after.current_question_message_id == before.current_question_message_id


def test_approve_partial_patch_preserves_uncovered_and_denied_profile_fields(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    before = profile_store.save(
        {
            "enabled": True,
            "primary_preset": "value",
            "risk_appetite": 4,
            "risk_capacity": 3,
            "holding_horizon": "multi_year",
            "drawdown_tolerance_pct": 15,
            "concentration_limit_pct": 18,
            "preferred_edge": ["quality"],
            "avoidances": ["leverage"],
            "behavioral_flags": ["anchoring"],
            "freeform_notes": "must remain user-owned",
            "default_stance": "neutral",
            "skill_mode": "suggest_only",
        }
    )
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="partial-approval",
        answer="I can accept a little more volatility.",
    )
    store.complete_turn(
        "partial-approval",
        result=_result(profile_patch={"risk_appetite": 8}),
    )
    proposal = store.latest_proposal(session.id)

    profile, approved = store.approve_proposal(proposal.id, profile_store=profile_store)

    assert profile.risk_appetite == 8
    assert profile.risk_mismatch == "appetite_above_capacity"
    for field in (
        "enabled",
        "primary_preset",
        "risk_capacity",
        "holding_horizon",
        "drawdown_tolerance_pct",
        "concentration_limit_pct",
        "preferred_edge",
        "avoidances",
        "behavioral_flags",
        "freeform_notes",
        "default_stance",
        "skill_mode",
    ):
        assert getattr(profile, field) == getattr(before, field), field
    assert approved.status == "approved"
    assert approved.changed_fields == ["risk_appetite", "risk_mismatch"]
    assert profile_store.get() == profile


def test_approve_compares_list_base_values_as_sets(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    profile_store.save(
        {
            "preferred_edge": ["quality", "valuation"],
            "avoidances": ["leverage", "illiquidity"],
            "behavioral_flags": ["FOMO", "anchoring"],
        }
    )
    session = store.start_session()

    turns = (
        ("loss", "loss_response", "risk_avoidances"),
        ("avoid", "risk_avoidances", "behavioral_patterns"),
        ("behavior", "behavioral_patterns", "investment_approach"),
    )
    for turn_id, addressed, next_topic in turns:
        store.begin_answer_turn(
            session_id=session.id,
            turn_id=turn_id,
            answer=f"Source answer for {addressed}.",
        )
        store.complete_turn(
            turn_id,
            result=_result(
                addressed_topic_id=addressed,
                next_topic_id=next_topic,
            ),
        )
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="approach",
        answer="I prefer catalysts and can name the biases to watch.",
    )
    store.complete_turn(
        "approach",
        result=_result(
            addressed_topic_id="investment_approach",
            next_topic_id="assistant_style",
            profile_patch={
                "preferred_edge": ["catalyst"],
                "avoidances": ["opaque accounting"],
                "behavioral_flags": ["recency"],
            },
        ),
    )
    proposal = store.latest_proposal(session.id)

    profile_store.save(
        {
            "preferred_edge": ["valuation", "quality"],
            "avoidances": ["illiquidity", "leverage"],
            "behavioral_flags": ["anchoring", "FOMO"],
        }
    )
    profile, approved = store.approve_proposal(proposal.id, profile_store=profile_store)

    assert approved.status == "approved"
    assert approved.conflict_fields == []
    assert profile.preferred_edge == ["catalyst"]
    assert profile.avoidances == ["opaque accounting"]
    assert profile.behavioral_flags == ["recency"]


def test_approve_conflict_keeps_proposal_pending_and_writes_nothing(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    profile_store.save({"risk_appetite": 4, "risk_capacity": 4})
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="conflicting-proposal",
        answer="I would hold through a larger drawdown.",
    )
    store.complete_turn(
        "conflicting-proposal",
        result=_result(profile_patch={"risk_appetite": 8}),
    )
    proposal = store.latest_proposal(session.id)
    profile_store.save({"risk_appetite": 5, "freeform_notes": "new user note"})
    profile_before = asdict(profile_store.get())
    row_before = _raw_proposal(db, proposal.id)

    with pytest.raises(ValueError, match="proposal_conflict"):
        store.approve_proposal(proposal.id, profile_store=profile_store)

    assert asdict(profile_store.get()) == profile_before
    conflicted = store.get_proposal(proposal.id)
    assert conflicted.status == "draft"
    assert conflicted.conflict_fields == ["risk_appetite"]
    assert conflicted.conflicted_at is not None
    assert conflicted.changed_fields == []
    row_after = _raw_proposal(db, proposal.id)
    for key in row_before:
        if key not in {"conflicted_at", "conflict_fields_json"}:
            assert row_after[key] == row_before[key], key


def test_approve_profile_and_proposal_roll_back_together_on_fault(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    profile_store.save({"risk_appetite": 4, "risk_capacity": 4})
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="atomic-proposal",
        answer="A larger drawdown would still be tolerable.",
    )
    store.complete_turn(
        "atomic-proposal",
        result=_result(profile_patch={"risk_appetite": 8}),
    )
    proposal = store.latest_proposal(session.id)
    profile_before = asdict(profile_store.get())
    proposal_before = _raw_proposal(db, proposal.id)

    def fail_after_profile_write(conn, *, proposal_id, changed_fields, approved_at):
        assert proposal_id == proposal.id
        assert "risk_appetite" in changed_fields
        assert conn.execute(
            "SELECT risk_appetite FROM investor_profile WHERE id='default'"
        ).fetchone()[0] == 8
        raise RuntimeError("fault after profile write")

    monkeypatch.setattr(store, "_mark_proposal_approved_on_connection", fail_after_profile_write)
    with pytest.raises(RuntimeError, match="fault after profile write"):
        store.approve_proposal(proposal.id, profile_store=profile_store)

    assert asdict(profile_store.get()) == profile_before
    assert _raw_proposal(db, proposal.id) == proposal_before


def test_reject_guided_proposal_keeps_profile_and_audit_unchanged(tmp_path):
    db = tmp_path / "profile_state.db"
    store = _calibration_store(db)
    profile_store = InvestorProfileStore(db)
    profile_store.save({"risk_appetite": 4, "freeform_notes": "keep this"})
    session = store.start_session()
    store.begin_answer_turn(
        session_id=session.id,
        turn_id="reject-proposal",
        answer="I might tolerate more volatility.",
    )
    store.complete_turn(
        "reject-proposal",
        result=_result(profile_patch={"risk_appetite": 7}),
    )
    proposal = store.latest_proposal(session.id)
    profile_before = asdict(profile_store.get())
    row_before = _raw_proposal(db, proposal.id)

    rejected = store.reject_proposal(proposal.id)

    assert rejected.status == "rejected"
    assert asdict(profile_store.get()) == profile_before
    row_after = _raw_proposal(db, proposal.id)
    for key in row_before:
        if key not in {"status", "rejected_at"}:
            assert row_after[key] == row_before[key], key


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
