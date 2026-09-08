"""Real SDK/HTTP contracts for credential probes and no-tool calibration."""

import asyncio
import json

import httpx
import pytest
from openai import APIError, OpenAI

from src import investor_profile_calibration_agent as calibration
from src import model_credentials
from src.auth_drivers.live_resolver import LiveAuthResolution


MODEL = "gpt-5.6-luna"
CALIBRATION_RESULT = {
    "assistant_message": "How long do you intend to hold?",
    "addressed_topic_id": "time_horizon",
    "topic_covered": False,
    "next_topic_id": None,
    "profile_patch": None,
    "rationales": {},
}
HISTORY = [{"role": "user", "content": "I am planning for retirement."},
           {"role": "assistant", "content": "When?"},
           {"role": "user", "content": "In ten years."}]


def text_response(text, *, model=MODEL):
    return {"id": "resp_test", "object": "response", "created_at": 1,
            "model": model, "status": "completed", "error": None,
            "output": [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}]}]}


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(model_credentials, "ensure_env_loaded", lambda: None)
    store = model_credentials.CredentialStore(tmp_path / "profile_state.db")
    credential = store.add(provider="openai", auth_type="api_key", alias="fixture", secret="test-selected-key")
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth",
                        lambda _: LiveAuthResolution("openai", "db_api_key", f"local:{credential.id}"))
    clients = []

    def install(handler):
        def construct(**kwargs):
            client = OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
            clients.append(client)
            return client

        monkeypatch.setattr("openai.OpenAI", construct)
        monkeypatch.setattr("src.auth_drivers.live_resolver.live_openai_client",
                            lambda: construct(api_key="test-selected-key"))

    def invoke(operation, *, model=MODEL, effort="high"):
        if operation == "probe":
            return model_credentials.test_model("openai", model, effort,
                                                credential_id=f"local:{credential.id}", store=store)
        return asyncio.run(calibration._call_calibration_llm(
            provider="openai", model=model, instructions="Return JSON only.", input_messages=HISTORY))

    yield install, invoke
    for client in clients:
        client.close()


@pytest.mark.parametrize("operation", ["probe", "calibration"])
@pytest.mark.parametrize("model", [MODEL, "gpt-7-custom"])
def test_remaining_openai_entrypoints_use_responses_and_selected_key(boundary, operation, model):
    install, invoke = boundary
    requests = []
    expected = "OK" if operation == "probe" else json.dumps(CALIBRATION_RESULT)

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=text_response(expected, model=model))

    install(handler)
    result = invoke(operation, model=model)
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == "Bearer test-selected-key"
    body = json.loads(requests[0].content)
    assert body["model"] == model and body["store"] is False
    assert not {"messages", "response_format", "reasoning_effort", "max_completion_tokens", "previous_response_id", "tools"} & body.keys()
    if operation == "probe":
        assert result.status == "ok" and result.warning is None and result.fallback_effort is None
        assert body["reasoning"] == {"effort": "high"}
        assert body["max_output_tokens"] == 16
    else:
        assert result == expected
        parsed = calibration.parse_calibration_model_json(result)
        assert parsed.profile_patch is None and parsed.topic_covered is False
        assert body["input"] == [{"role": "system", "content": "Return JSON only."}, *HISTORY]
        assert body["text"] == {"format": {"type": "json_object"}}
        assert "reasoning" not in body


@pytest.mark.parametrize("effort", ["default", "none", "xhigh"])
def test_probe_preserves_explicit_effort_without_inventing_a_default(boundary, effort):
    install, invoke = boundary
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=text_response("OK"))

    install(handler)
    assert invoke("probe", effort=effort).status == "ok"
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body.get("reasoning") == (None if effort == "default" else {"effort": effort})


@pytest.mark.parametrize("operation", ["probe", "calibration"])
@pytest.mark.parametrize("failure", [400, 429, 500, "timeout"])
def test_openai_failures_never_retry_or_change_billing_or_effort(boundary, operation, failure):
    install, invoke = boundary
    requests = []

    def handler(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        return httpx.Response(failure, json={"error": {"message": "unsupported reasoning effort", "type": "invalid_request_error"}})

    install(handler)
    if operation == "probe":
        result = invoke(operation)
        assert result.status == "error" and result.fallback_effort is None
    else:
        with pytest.raises(APIError):
            invoke(operation)
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer test-selected-key"
    body = json.loads(requests[0].content)
    assert body["model"] == MODEL
    if operation == "probe":
        assert body["reasoning"] == {"effort": "high"}


@pytest.mark.parametrize("operation", ["probe", "calibration"])
@pytest.mark.parametrize("fault", ["failed", "error", "model", "refusal", "empty", "tool", "partial_message"])
def test_no_tool_responses_reject_invalid_results(boundary, operation, fault):
    install, invoke = boundary
    raw = text_response("OK" if operation == "probe" else json.dumps(CALIBRATION_RESULT))
    if fault == "failed":
        raw["status"] = "failed"
    elif fault == "error":
        raw["error"] = {"code": "server_error", "message": "fixture error"}
    elif fault == "model":
        raw["model"] = "gpt-5.6-terra"
    elif fault == "refusal":
        raw["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot comply."}]
    elif fault == "empty":
        raw["output"] = []
    elif fault == "tool":
        raw["output"].append({"type": "function_call", "id": "fc_test", "call_id": "call_test",
                              "status": "completed", "name": "unrequested", "arguments": "{}"})
    else:
        raw["output"][0]["status"] = "incomplete"
    install(lambda _: httpx.Response(200, json=raw))
    if operation == "probe":
        result = invoke(operation)
        assert result.status == "error"
    else:
        with pytest.raises(RuntimeError):
            invoke(operation)


@pytest.mark.parametrize("operation", ["probe", "calibration"])
@pytest.mark.parametrize("reason", ["max_output_tokens", "content_filter", None])
def test_incomplete_probe_is_only_an_access_observation_not_task_completion(boundary, operation, reason):
    install, invoke = boundary
    raw = text_response("" if operation == "probe" else json.dumps(CALIBRATION_RESULT))
    raw["status"] = "incomplete"
    raw["incomplete_details"] = {"reason": reason} if reason else None
    raw["output"] = []
    install(lambda _: httpx.Response(200, json=raw))
    if operation == "probe":
        result = invoke(operation)
        if reason == "max_output_tokens":
            assert result.status == "ok" and result.warning
            assert "not verified" in result.warning
            assert result.fallback_effort is None
        else:
            assert result.status == "error"
    else:
        with pytest.raises(RuntimeError):
            invoke(operation)


@pytest.mark.parametrize("operation", ["probe", "calibration"])
def test_no_tool_responses_accept_reasoning_and_official_alias_receipts(boundary, operation):
    install, invoke = boundary
    expected = "OK" if operation == "probe" else json.dumps(CALIBRATION_RESULT)
    raw = text_response(expected, model="gpt-5.6-sol-2026-09-08")
    raw["output"].insert(0, {"type": "reasoning", "id": "reason_test", "summary": []})
    install(lambda _: httpx.Response(200, json=raw))
    result = invoke(operation, model="gpt-5.6")
    assert result.status == "ok" if operation == "probe" else result == expected
