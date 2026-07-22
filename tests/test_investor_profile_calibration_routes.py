"""Track A.5: calibration routes - handler-direct, no TestClient."""

import asyncio
import json
import sqlite3
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import src.investor_profile_calibration_agent as calibration_agent
from src.api.routes import investor_profile_calibration as routes
from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import CalibrationStore
from src.investor_profile_calibration_policy import (
    CALIBRATION_TOPIC_IDS,
    OPENING_PROMPT_ID,
    OPENING_PROMPTS,
)
from src.investor_profile_calibration_schema import migrate_calibration_schema


@dataclass(frozen=True)
class _AgentResult:
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
    return _AgentResult(**values)


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    migrate_calibration_schema(db)
    return CalibrationStore(db), InvestorProfileStore(db)


def _allow_writes(monkeypatch):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)


def _start(cstore):
    return routes.start_calibration_session(
        routes.StartCalibrationBody(), store=cstore
    )["active_session"]


def _guided_loss_proposal(cstore, *, turn_id="proposal-turn", risk_appetite=7):
    session = cstore.start_session()
    cstore.begin_answer_turn(
        session_id=session.id,
        turn_id=turn_id,
        answer="I reassess the thesis before reacting to a loss.",
    )
    cstore.complete_turn(
        turn_id,
        result=_result(profile_patch={"risk_appetite": risk_appetite}),
    )
    return session, cstore.latest_proposal(session.id)


def test_start_session_requires_profile_state_gate(stores, monkeypatch):
    cstore, _pstore = stores
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )

    data = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert calls[0][0] == "investor_profile_calibration_start"
    assert data["active_session"]["status"] == "active"


def test_start_session_conflict_without_explicit_supersede(stores, monkeypatch):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    with pytest.raises(HTTPException) as exc:
        routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "calibration_session_active"


def test_send_message_appends_user_assistant_and_inert_proposal(stores, monkeypatch):
    cstore, pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)

    async def fake_responder(*, messages, provider, model, **runtime):
        assert provider is None and model is None
        assert messages[-1]["role"] == "user"
        return _result(
            assistant_message="You review the thesis before reacting to losses.",
            profile_patch={"risk_appetite": 7},
            rationales={"risk_appetite": "The answer described a deliberate review."},
        )

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    data = asyncio.run(
        routes.send_calibration_message(
            routes.CalibrationMessageBody(
                session_id=session["id"],
                turn_id="answer-1",
                content="I reassess before selling.",
            ),
            store=cstore,
        )
    )

    assert [m["role"] for m in data["messages"]][-2:] == ["user", "assistant"]
    assert data["latest_proposal"]["status"] == "draft"
    assert data["latest_proposal"]["profile_patch"]["risk_appetite"] == 7
    assert pstore.get().enabled is False


def test_send_message_wraps_responder_runtime_failure(stores, monkeypatch):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)

    async def failing_responder(**kwargs):
        raise RuntimeError("claude_code_oauth calibration no-tool path is not wired")

    monkeypatch.setattr(routes, "_default_responder", failing_responder)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="failed-answer",
                    content="Help calibrate me.",
                ),
                store=cstore,
            )
        )

    assert exc.value.status_code == 502
    assert exc.value.detail["code"] == "calibration_responder_failed"


def test_approve_proposal_uses_existing_profile_save_and_records_provenance(
    stores, monkeypatch
):
    cstore, pstore = stores
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )
    _session, proposal = _guided_loss_proposal(cstore)
    approve = cstore.approve_proposal

    def permission_checked_approve(*args, **kwargs):
        assert calls and calls[-1][0] == "investor_profile_calibration_approve"
        return approve(*args, **kwargs)

    monkeypatch.setattr(cstore, "approve_proposal", permission_checked_approve)

    data = routes.approve_calibration_proposal(
        proposal.id,
        routes.ApproveProposalBody(),
        store=cstore,
        profile_store=pstore,
    )

    assert calls[0][0] == "investor_profile_calibration_approve"
    assert data["proposal"]["status"] == "approved"
    assert data["proposal"]["approved_at"] is not None
    assert data["proposal"]["changed_fields"] == ["risk_appetite"]
    assert data["profile"]["risk_mismatch"] == "unclear"
    assert pstore.get().risk_appetite == 7


def test_reject_proposal_keeps_profile_unchanged(stores, monkeypatch):
    cstore, pstore = stores
    _allow_writes(monkeypatch)
    session = cstore.start_session()
    proposal = cstore.create_proposal(
        session_id=session.id, profile_patch={"enabled": True}, rationales={}
    )

    data = routes.reject_calibration_proposal(proposal.id, store=cstore)

    assert data["proposal"]["status"] == "rejected"
    assert pstore.get().enabled is False


def test_calibration_router_mounts_on_real_app():
    from src.api.app import create_app

    try:
        asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/profile/investor/calibration" in paths
    assert "/profile/investor/calibration/turns/{turn_id}/retry" in paths
    assert "/profile/investor/calibration/proposals/request" in paths


def test_route_default_responder_is_live_seam_not_unavailable():
    assert routes._default_responder is routes.default_calibration_responder
    assert routes._default_responder is not routes.unavailable_responder


def test_start_guided_session_returns_opening_prompt_without_responder_call(
    stores, monkeypatch
):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)

    async def forbidden_responder(**kwargs):
        raise AssertionError("session start must not call the Provider")

    monkeypatch.setattr(routes, "_default_responder", forbidden_responder)
    data = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert set(data) == {
        "active_session",
        "sessions",
        "messages",
        "pending_turn",
        "latest_proposal",
        "topic_catalog",
    }
    assert data["topic_catalog"] == list(CALIBRATION_TOPIC_IDS)
    assert data["pending_turn"] is None
    assert data["messages"] == [
        {
            **data["messages"][0],
            "role": "assistant",
            "content": OPENING_PROMPTS[OPENING_PROMPT_ID],
            "topic_id": "loss_response",
            "prompt_id": OPENING_PROMPT_ID,
        }
    ]


def test_turn_requires_client_turn_id_and_returns_retryable_state(stores, monkeypatch):
    with pytest.raises(ValidationError):
        routes.CalibrationMessageBody(content="A source answer.")

    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)

    async def failing_responder(**kwargs):
        raise RuntimeError("temporary Provider outage")

    monkeypatch.setattr(routes, "_default_responder", failing_responder)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="retryable-answer",
                    content="Keep this answer for retry.",
                ),
                store=cstore,
            )
        )

    state = routes.get_calibration_state(store=cstore)
    assert exc.value.detail["code"] == "calibration_responder_failed"
    assert state["pending_turn"]["id"] == "retryable-answer"
    assert state["pending_turn"]["status"] == "failed"
    assert state["pending_turn"]["attempt_count"] == 1
    assert [m["content"] for m in state["messages"]].count(
        "Keep this answer for retry."
    ) == 1


def test_completed_turn_retry_returns_same_state_without_second_provider_call(
    stores, monkeypatch
):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)
    localized_opening = "前端顯示的在地化問題不得進入模型上下文。"
    answer = "  Preserve my source answer byte-for-byte.  "
    model_question = "  Model question byte-for-byte?\n"
    with sqlite3.connect(cstore.db_path) as conn:
        conn.execute(
            "UPDATE investor_profile_calibration_messages SET content=? WHERE id=?",
            (localized_opening, session["current_question_message_id"]),
        )

    calls = []

    async def fake_responder(
        *, messages, current_topic_id, covered_topics, request_proposal, provider, model
    ):
        assert cstore._write_lock.acquire(blocking=False)
        cstore._write_lock.release()
        calls.append(messages)
        assert messages[0]["content"] == OPENING_PROMPTS[OPENING_PROMPT_ID]
        assert messages[-1] == {"role": "user", "content": answer}
        assert current_topic_id == "loss_response"
        assert covered_topics == ()
        assert request_proposal is False
        return _result(assistant_message=model_question)

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    body = routes.CalibrationMessageBody(
        session_id=session["id"], turn_id="stable-turn", content=answer
    )
    first = asyncio.run(routes.send_calibration_message(body, store=cstore))
    generated = first["messages"][-1]
    with sqlite3.connect(cstore.db_path) as conn:
        conn.execute(
            "UPDATE investor_profile_calibration_messages SET prompt_id=? WHERE id=?",
            ("future.prompt.v9", generated["id"]),
        )

    canonical = routes._canonical_messages(cstore.list_messages(session["id"]))
    assert canonical[0]["content"] == OPENING_PROMPTS[OPENING_PROMPT_ID]
    assert canonical[1]["content"] == answer
    assert canonical[2]["content"] == model_question

    repeated = asyncio.run(
        routes.retry_calibration_turn(
            "stable-turn",
            routes.CalibrationRetryBody(provider="anthropic", model="ignored-model"),
            store=cstore,
        )
    )
    assert len(calls) == 1
    assert repeated == routes.get_calibration_state(store=cstore)
    assert repeated["pending_turn"] is None
    assert [m["turn_id"] for m in repeated["messages"]].count("stable-turn") == 2


def test_invalid_next_topic_returns_typed_catalog_validation_failure_and_retryable_turn(
    tmp_path, monkeypatch
):
    _allow_writes(monkeypatch)
    for case, next_topic in (
        ("unknown", "model_invented_topic"),
        ("already-covered", "loss_response"),
    ):
        db = tmp_path / case / "profile_state.db"
        migrate_calibration_schema(db)
        cstore = CalibrationStore(db)
        InvestorProfileStore(db)
        session = _start(cstore)

        async def invalid_responder(next_topic=next_topic, **kwargs):
            return _result(next_topic_id=next_topic)

        monkeypatch.setattr(routes, "_default_responder", invalid_responder)
        monkeypatch.setattr(
            cstore,
            "fail_turn",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("complete_turn already terminalized this failure")
            ),
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                routes.send_calibration_message(
                    routes.CalibrationMessageBody(
                        session_id=session["id"],
                        turn_id=f"{case}-turn",
                        content="Persist this source answer.",
                    ),
                    store=cstore,
                )
            )

        state = routes.get_calibration_state(store=cstore)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "calibration_catalog_validation_failed"
        assert next_topic not in json.dumps(exc.value.detail)
        assert state["pending_turn"]["status"] == "failed"
        assert state["pending_turn"]["error_code"] == (
            "calibration_catalog_validation_failed"
        )
        assert state["active_session"]["covered_topics"] == []
        assert state["active_session"]["current_topic_id"] == "loss_response"
        assert [message["role"] for message in state["messages"]] == [
            "assistant",
            "user",
        ]


def test_retry_interrupted_turn_reuses_answer_and_turn_id(stores, monkeypatch):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)
    answer = "This exact persisted answer must be retried."
    work = cstore.begin_answer_turn(
        session_id=session["id"],
        turn_id="interrupted-turn",
        answer=answer,
        provider="openai",
        model="first-model",
    )
    answer_message_id = next(
        message.id for message in work.messages if message.role == "user"
    )
    cstore.fail_turn(
        "interrupted-turn",
        error_code="calibration_responder_failed",
        diagnostic="Provider call failed.",
    )
    newer_answer = "This newer failed answer must become stale after advancement."
    cstore.begin_answer_turn(
        session_id=session["id"],
        turn_id="newer-failed-turn",
        answer=newer_answer,
    )
    cstore.fail_turn(
        "newer-failed-turn",
        error_code="calibration_responder_failed",
        diagnostic="Provider call failed.",
    )
    assert cstore.get_turn("interrupted-turn").status == "failed"
    assert cstore.get_turn("newer-failed-turn").status == "failed"
    assert routes.get_calibration_state(store=cstore)["pending_turn"]["id"] == (
        "newer-failed-turn"
    )

    async def fake_responder(
        *, messages, current_topic_id, covered_topics, request_proposal, provider, model
    ):
        assert {"role": "user", "content": answer} in messages
        assert {"role": "user", "content": newer_answer} in messages
        assert provider == "anthropic"
        assert model == "retry-model"
        return _result()

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    state = asyncio.run(
        routes.retry_calibration_turn(
            "interrupted-turn",
            routes.CalibrationRetryBody(provider="anthropic", model="retry-model"),
            store=cstore,
        )
    )

    retried = cstore.get_turn("interrupted-turn")
    stale = cstore.get_turn("newer-failed-turn")
    user_messages = [
        message
        for message in cstore.list_messages(session["id"])
        if message.role == "user"
    ]
    plain_state = routes.get_calibration_state(store=cstore)
    assert retried.status == "completed"
    assert retried.attempt_count == 2
    assert stale.status == "failed"
    assert state["pending_turn"] is None
    assert plain_state["pending_turn"] is None
    assert plain_state["active_session"]["current_topic_id"] == "financial_capacity"
    assert [(message.turn_id, message.content) for message in user_messages] == [
        ("interrupted-turn", answer),
        ("newer-failed-turn", newer_answer),
    ]
    assert user_messages[0].id == answer_message_id


def test_request_proposal_uses_dedicated_route_without_fake_user_message(
    stores, monkeypatch
):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = cstore.start_session()
    cstore.begin_answer_turn(
        session_id=session.id,
        turn_id="cover-loss",
        answer="I review the thesis before reacting.",
    )
    cstore.complete_turn("cover-loss", result=_result())
    user_ids_before = [
        message.id for message in cstore.list_messages(session.id) if message.role == "user"
    ]

    async def fake_responder(
        *, messages, current_topic_id, covered_topics, request_proposal, provider, model
    ):
        assert current_topic_id == "financial_capacity"
        assert covered_topics == ("loss_response",)
        assert request_proposal is True
        return _result(
            assistant_message="I prepared the supported part of your profile.",
            addressed_topic_id="financial_capacity",
            topic_covered=True,
            next_topic_id=None,
            profile_patch={
                "risk_appetite": 8,
                "risk_capacity": 9,
                "enabled": True,
                "risk_mismatch": "none",
                "unknown_field": "denied proposal value",
            },
            rationales={"risk_appetite": "Supported source rationale."},
        )

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    state = asyncio.run(
        routes.request_calibration_proposal(
            routes.CalibrationProposalRequestBody(
                session_id=session.id,
                turn_id="propose-now",
                provider="openai",
                model="proposal-model",
            ),
            store=cstore,
        )
    )

    user_ids_after = [
        message.id for message in cstore.list_messages(session.id) if message.role == "user"
    ]
    assert user_ids_after == user_ids_before
    assert state["active_session"] is None
    assert state["latest_proposal"]["profile_patch"] == {"risk_appetite": 8}
    assert "denied proposal value" not in json.dumps(state)

    reloaded = routes.get_calibration_state(store=cstore)
    assert reloaded["active_session"] is None
    assert reloaded["sessions"][0]["id"] == session.id
    assert reloaded["messages"] == state["messages"]
    assert reloaded["latest_proposal"] == state["latest_proposal"]


def test_approve_schema_rejects_client_profile_patch():
    with pytest.raises(ValidationError):
        routes.ApproveProposalBody(profile_patch={"risk_appetite": 10})

    assert routes.ApproveProposalBody().model_dump() == {}
    assert routes.ApproveProposalBody.model_config["extra"] == "forbid"


def test_approve_conflict_returns_409_and_keeps_pending_proposal(stores, monkeypatch):
    cstore, pstore = stores
    _allow_writes(monkeypatch)
    pstore.save({"risk_appetite": 4})
    _session, proposal = _guided_loss_proposal(
        cstore, turn_id="conflicting-proposal", risk_appetite=7
    )
    pstore.save({"risk_appetite": 6})

    with pytest.raises(HTTPException) as exc:
        routes.approve_calibration_proposal(
            proposal.id,
            routes.ApproveProposalBody(),
            store=cstore,
            profile_store=pstore,
        )

    pending = cstore.get_proposal(proposal.id)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "proposal_conflict"
    assert pstore.get().risk_appetite == 6
    assert pending.status == "draft"
    assert pending.conflict_fields == ["risk_appetite"]


def test_missing_provider_configuration_uses_existing_typed_error_family(
    stores, monkeypatch
):
    from src.auth_drivers import factory, live_resolver, token_store

    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)
    monkeypatch.setattr(
        routes, "_default_responder", calibration_agent.live_calibration_responder
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    resolution = {"source": "env_fallback", "credential_id": None}

    def fake_resolve(provider):
        return live_resolver.LiveAuthResolution(
            provider=provider,
            source=resolution["source"],
            credential_id=resolution["credential_id"],
        )

    def forbidden_provider_call(*args, **kwargs):
        raise AssertionError("credential absence must be detected before provider setup")

    monkeypatch.setattr(live_resolver, "resolve_live_auth", fake_resolve)
    monkeypatch.setattr(live_resolver, "live_openai_client", forbidden_provider_call)
    monkeypatch.setattr(live_resolver, "live_anthropic_client", forbidden_provider_call)
    monkeypatch.setattr(factory, "build_driver", forbidden_provider_call)

    failures = []
    cases = [
        ("openai", "missing-openai-env", "Keep the OpenAI answer."),
        ("anthropic", "missing-anthropic-env", "Keep the Anthropic answer."),
    ]
    for provider, turn_id, answer in cases:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(
                routes.send_calibration_message(
                    routes.CalibrationMessageBody(
                        session_id=session["id"],
                        turn_id=turn_id,
                        content=answer,
                        provider=provider,
                    ),
                    store=cstore,
                )
            )
        failures.append((turn_id, answer, caught.value))

    token_loads = []

    class EmptyTokenStore:
        def load(self, **kwargs):
            token_loads.append(kwargs)
            return None

    resolution.update(source="oauth_driver_unwired", credential_id="local:71")
    monkeypatch.setattr(token_store, "get_token_store", lambda: EmptyTokenStore())
    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="missing-oauth-token",
                    content="Keep the OAuth answer.",
                    provider="openai",
                ),
                store=cstore,
            )
        )
    failures.append(("missing-oauth-token", "Keep the OAuth answer.", caught.value))

    journal = cstore.list_messages(session["id"])
    for turn_id, answer, error in failures:
        failed = cstore.get_turn(turn_id)
        assert error.status_code == 503
        assert error.detail["code"] == "provider_config_missing"
        assert error.detail["message"] == (
            "Configure an AI provider before retrying this calibration turn."
        )
        assert error.detail["diagnostic"] == failed.diagnostic
        assert failed.error_code == "provider_config_missing"
        assert "[REDACTED]" in failed.diagnostic
        assert any(message.content == answer for message in journal)
        assert "local:71" not in json.dumps(error.detail)
    assert token_loads == [
        {
            "provider": "openai",
            "auth_mode": "chatgpt_oauth",
            "credential_id": "local:71",
        }
    ]


def test_calibration_failure_hides_provider_detail_outside_diagnostic_field(
    stores, monkeypatch
):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)
    planted = (
        "credential_id=cred-production",
        "provider response body: BUY ACME",
        "rejected value: forbidden-field",
        "tok=AbCdEf0123456789Secret",
    )
    raw_detail = "; ".join(planted)
    fail_calls = []
    fail_turn = cstore.fail_turn

    def recording_fail_turn(*args, **kwargs):
        fail_calls.append((args, kwargs))
        return fail_turn(*args, **kwargs)

    monkeypatch.setattr(cstore, "fail_turn", recording_fail_turn)

    async def failing_responder(**kwargs):
        raise RuntimeError(raw_detail)

    monkeypatch.setattr(routes, "_default_responder", failing_responder)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="private-failure",
                    content="Persist this answer.",
                ),
                store=cstore,
            )
        )

    failed = cstore.get_turn("private-failure")
    public_without_diagnostic = {
        key: value for key, value in exc.value.detail.items() if key != "diagnostic"
    }
    assert exc.value.status_code == 502
    assert public_without_diagnostic == {
        "code": "calibration_responder_failed",
        "message": "Calibration responder failed. Retry this turn.",
    }
    assert exc.value.detail["diagnostic"] == failed.diagnostic
    assert failed.error_code == "calibration_responder_failed"
    assert len(fail_calls) == 1
    assert len(failed.diagnostic) <= 240
    assert failed.diagnostic == "Provider call failed."
    exposed = json.dumps(
        {"turn": failed.to_dict(), "http_detail": exc.value.detail},
        ensure_ascii=False,
    )
    for raw_value in (*planted, raw_detail):
        assert raw_value not in failed.diagnostic
        assert raw_value not in exposed

    raw_model_body = json.dumps(
        {
            "assistant_message": raw_detail,
            "addressed_topic_id": "loss_response",
            "topic_covered": "not-a-boolean",
            "next_topic_id": None,
            "profile_patch": None,
            "rationales": {},
        }
    )

    async def malformed_provider_result(**kwargs):
        assert kwargs["input_messages"][-1] == {
            "role": "user",
            "content": "Preserve this malformed-result answer.",
        }
        return raw_model_body

    monkeypatch.setattr(
        calibration_agent, "_call_calibration_llm", malformed_provider_result
    )
    monkeypatch.setattr(
        routes, "_default_responder", calibration_agent.live_calibration_responder
    )
    calls_before = len(fail_calls)
    with pytest.raises(HTTPException) as parse_exc:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="malformed-result",
                    content="Preserve this malformed-result answer.",
                    provider="openai",
                ),
                store=cstore,
            )
        )

    malformed = cstore.get_turn("malformed-result")
    assert parse_exc.value.status_code == 400
    assert parse_exc.value.detail["code"] == "calibration_result_validation_failed"
    assert parse_exc.value.detail["message"] == (
        "Calibration response failed validation. Retry this turn."
    )
    assert parse_exc.value.detail["diagnostic"] == malformed.diagnostic
    assert malformed.error_code == "calibration_result_validation_failed"
    assert malformed.diagnostic == "Calibration result failed structured validation."
    assert len(fail_calls) == calls_before + 1
    assert any(
        message.role == "user"
        and message.turn_id == "malformed-result"
        and message.content == "Preserve this malformed-result answer."
        for message in cstore.list_messages(session["id"])
    )
    parse_exposed = json.dumps(
        {"turn": malformed.to_dict(), "http_detail": parse_exc.value.detail},
        ensure_ascii=False,
    )
    assert raw_model_body not in parse_exposed
    for raw_value in planted:
        assert raw_value not in parse_exposed
