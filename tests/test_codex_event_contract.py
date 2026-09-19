"""Shared Codex guards survive removal of the translation-only adapter."""

from copy import deepcopy

import pytest

from src.auth_drivers import codex_event_contract as contract


IDENTITY = {"thread_id": "thread", "turn_id": "turn", "model": "gpt-5.6-luna"}


def _event(method, **params):
    return {"method": method, "params": {"threadId": "thread", "turnId": "turn", **params}}


CONTROL_EVENTS = [
    _event("turn/moderationMetadata", metadata={}),
    _event("model/safetyBuffering/updated", model=IDENTITY["model"],
           reasons=[], useCases=[], showBufferingUi=False, fasterModel=None),
    _event("model/verification", verifications=[]),
    _event("thread/name/updated", threadName="Fixture"),
]


@pytest.mark.parametrize("event", CONTROL_EVENTS)
def test_passive_control_events_keep_the_execution_identity(event):
    assert contract._validate_turn_control(event, **IDENTITY) is True


@pytest.mark.parametrize("event", CONTROL_EVENTS + [
    _event("model/rerouted"), _event("error"),
])
def test_control_event_cannot_cross_threads(event):
    event = deepcopy(event)
    event["params"]["threadId"] = "another-thread"
    with pytest.raises(contract.CodexEventError, match="^protocol_incompatible$"):
        contract._validate_turn_control(event, **IDENTITY)


@pytest.mark.parametrize("event", CONTROL_EVENTS[:3] + [
    _event("model/rerouted"), _event("error"),
])
def test_control_event_cannot_cross_turns(event):
    event = deepcopy(event)
    event["params"]["turnId"] = "another-turn"
    with pytest.raises(contract.CodexEventError, match="^protocol_incompatible$"):
        contract._validate_turn_control(event, **IDENTITY)


@pytest.mark.parametrize("event", [
    _event("model/rerouted", fromModel=IDENTITY["model"], toModel="gpt-5.6-sol",
           reason="highRiskCyberActivity"),
    _event("model/verification", verifications=["trustedAccessForCyber"]),
])
def test_restriction_or_model_fallback_is_not_success(event):
    with pytest.raises(contract.CodexEventError, match="^model_unavailable$"):
        contract._validate_turn_control(event, **IDENTITY)


@pytest.mark.parametrize(("info", "code"), [
    ("contextWindowExceeded", "context_window_exceeded"),
    ("usageLimitExceeded", "subscription_usage_unavailable"),
    ("unauthorized", "reauth_required"),
    ("serverOverloaded", "provider_call_failed"),
    ({"responseStreamDisconnected": {"httpStatusCode": 503}}, "provider_call_failed"),
])
def test_provider_errors_are_closed_codes_not_raw_text(info, code):
    event = _event("error", willRetry=False, error={
        "message": "secret-sentinel raw provider message", "codexErrorInfo": info,
    })
    with pytest.raises(contract.CodexEventError) as caught:
        contract._validate_turn_control(event, **IDENTITY)
    assert caught.value.code == str(caught.value) == code


def _settings_event():
    return _event("thread/settings/updated", threadSettings={
        "approvalPolicy": "never", "approvalsReviewer": "user", "cwd": "/owned",
        "effort": "high", "model": IDENTITY["model"], "modelProvider": "openai",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
    })


@pytest.mark.parametrize(("key", "value"), [
    ("model", "gpt-5.6-sol"), ("effort", "low"), ("cwd", "/other"),
    ("sandboxPolicy", {"type": "readOnly", "networkAccess": True}),
])
def test_settings_cannot_expand_or_change_selected_authority(key, value):
    event = _settings_event()
    assert contract._validate_turn_telemetry(event, **IDENTITY, cwd="/owned", effort="high")
    event["params"]["threadSettings"][key] = value
    with pytest.raises(contract.CodexEventError, match="^protocol_incompatible$"):
        contract._validate_turn_telemetry(event, **IDENTITY, cwd="/owned", effort="high")


@pytest.mark.parametrize("method", [
    "item/reasoning/summaryPartAdded", "item/reasoning/summaryTextDelta",
    "item/reasoning/textDelta", "thread/tokenUsage/updated", "thread/status/changed",
])
def test_known_telemetry_does_not_become_output(method):
    event = _event(method, itemId="item", summaryIndex=0, contentIndex=0,
                   delta="text", tokenUsage={}, status={"type": "active", "activeFlags": []})
    assert contract._validate_turn_telemetry(event, **IDENTITY, cwd="/owned", effort="high")


def test_safety_buffering_cannot_replace_the_model():
    event = deepcopy(CONTROL_EVENTS[1])
    event["params"]["model"] = "gpt-5.6-sol"
    with pytest.raises(contract.CodexEventError, match="^protocol_incompatible$"):
        contract._validate_turn_control(event, **IDENTITY)
