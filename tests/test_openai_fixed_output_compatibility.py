"""Real SDK request-shape coverage for the 5.6 fixed-output repair."""

import json
import httpx
import pytest
from openai import APIStatusError, BadRequestError, OpenAI

from src import card_synthesis as cs
from src.auth_drivers.live_resolver import LiveAuthResolution
from src.evidence_packet import EvidencePacket


MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6")
CUSTOM_MODELS = ("gpt-7-custom", "gpt-5.4-mini", "gpt-5.2")
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"translated_text": {"type": "string"}},
          "required": ["translated_text"]}


def payload(operation):
    if operation == "synthesis":
        return {"conclusion": "Insufficient evidence.", "counter_thesis": [],
                "confidence_level": "low", "claims": []}
    return {"translated_text": "Revenue increased."}


def invoke(operation, model, effort="low"):
    if operation == "synthesis":
        return cs._synthesize_openai(
            EvidencePacket(ticker="TEST", generated_at="2026-09-08T00:00:00Z", items=[]),
            model, effort=effort, model_timeout_s=42,
        )[0].model_dump()
    return cs._translate_openai(model, "Translate into English.", "Revenue rose.",
                                SCHEMA, "English", effort=effort, model_timeout_s=42)


def response(operation, model):
    return {"id": "resp_test", "object": "response", "created_at": 1,
            "model": model, "status": "completed", "error": None,
            "output": [{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                        "status": "completed", "name": "emit_result_card" if operation == "synthesis" else "emit_translation",
                        "arguments": json.dumps(payload(operation))}]}


def install(monkeypatch, handler):
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth",
                        lambda _: LiveAuthResolution("openai", "db_api_key", "local:test"))
    client = OpenAI(api_key="test-not-a-credential", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("src.auth_drivers.live_resolver.live_openai_client", lambda: client)
    return client


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("operation", ["synthesis", "translation"])
@pytest.mark.parametrize("effort", ["default", "none", "low", "medium", "high", "xhigh", "max"])
def test_56_fixed_tasks_preserve_effort_and_use_responses(monkeypatch, model, operation, effort):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=response(operation, "gpt-5.6-sol" if model == "gpt-5.6" else model))

    with install(monkeypatch, handler):
        result = invoke(operation, model, effort)
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == model
    assert body.get("reasoning") == (None if effort == "default" else {"effort": effort})
    assert body["store"] is False and body["parallel_tool_calls"] is False
    assert body["tools"][0]["strict"] is False
    assert body["tools"][0]["parameters"] == (cs._CARD_TOOL_SCHEMA if operation == "synthesis" else SCHEMA)
    assert body["tool_choice"] == {"type": "function", "name": body["tools"][0]["name"]}
    assert not {"messages", "reasoning_effort", "temperature", "top_p"} & body.keys()
    assert all(result[key] == value for key, value in payload(operation).items())


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("operation", ["synthesis", "translation"])
def test_56_provider_rejection_never_retries_or_changes_model_effort_or_credential(monkeypatch, model, operation):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(400, json={"error": {"type": "invalid_request_error", "message": "unsupported request"}})

    with install(monkeypatch, handler), pytest.raises(BadRequestError):
        invoke(operation, model, "xhigh")
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer test-not-a-credential"
    body = json.loads(requests[0].content)
    assert body["model"] == model and body["reasoning"] == {"effort": "xhigh"}


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("operation", ["synthesis", "translation"])
def test_56_subscription_does_not_construct_api_key_client(monkeypatch, model, operation):
    calls = []
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth",
                        lambda _: LiveAuthResolution("openai", "oauth_driver_unwired", "local:test"))
    monkeypatch.setattr("src.auth_drivers.live_resolver.live_openai_client",
                        lambda: pytest.fail("OAuth may not fall through to API key"))
    monkeypatch.setattr("src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
                        lambda **kw: calls.append(kw) or payload(operation))
    invoke(operation, model, "high")
    assert len(calls) == 1
    assert (calls[0]["model"], calls[0]["effort"], calls[0]["auth_mode"]) == (model, "high", "chatgpt_oauth")


@pytest.mark.parametrize("requested,observed,accepted", [
    ("gpt-5.6", "gpt-5.6-sol", True),
    ("gpt-5.6", "gpt-5.6-sol-2026-09-08", True),
    ("gpt-5.6", "gpt-5.6-luna", False),
    ("gpt-5.6", "gpt-5.6-sol-unreviewed", False),
    ("gpt-5.6-luna", "gpt-5.6-luna-2026-09-08", True),
    ("gpt-5.6-luna-2026-09-08", "gpt-5.6-luna-2026-09-09", False),
    ("gpt-5.6-luna-2026-09-08", "gpt-5.6-luna", False),
])
def test_56_model_receipt_accepts_only_official_alias_and_allowed_snapshot(monkeypatch, requested, observed, accepted):
    with install(monkeypatch, lambda _: httpx.Response(200, json=response("translation", observed))):
        if accepted:
            assert invoke("translation", requested) == payload("translation")
        else:
            with pytest.raises(RuntimeError, match="different model"):
                invoke("translation", requested)


@pytest.mark.parametrize("model", CUSTOM_MODELS)
@pytest.mark.parametrize("operation", ["synthesis", "translation"])
@pytest.mark.parametrize("effort", ["default", "high"])
def test_custom_fixed_tasks_use_responses_without_changing_contract(monkeypatch, model, operation, effort):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=response(operation, model))

    with install(monkeypatch, handler):
        result = invoke(operation, model, effort)
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == model
    assert body.get("reasoning") == (None if effort == "default" else {"effort": effort})
    assert body["store"] is False and body["parallel_tool_calls"] is False
    assert body["max_output_tokens"] == (8192 if operation == "synthesis" else 4096)
    assert body["tools"][0]["strict"] is False
    assert body["tools"][0]["parameters"] == (cs._CARD_TOOL_SCHEMA if operation == "synthesis" else SCHEMA)
    assert all(result[key] == value for key, value in payload(operation).items())


@pytest.mark.parametrize("operation", ["synthesis", "translation"])
@pytest.mark.parametrize("status", [400, 429, 500])
def test_custom_fixed_task_rejection_never_falls_back(monkeypatch, operation, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "unsupported reasoning effort", "type": "invalid_request_error"}})

    with install(monkeypatch, handler), pytest.raises(APIStatusError):
        invoke(operation, "gpt-7-custom", "high")
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer test-not-a-credential"
    assert json.loads(requests[0].content)["reasoning"] == {"effort": "high"}


@pytest.mark.parametrize("operation", ["synthesis", "translation"])
@pytest.mark.parametrize("fault", ["incomplete", "model", "refusal", "schema", "extra_call"])
def test_custom_fixed_task_never_accepts_invalid_output(monkeypatch, operation, fault):
    raw = response(operation, "gpt-7-custom")
    if fault == "incomplete":
        raw["status"] = "incomplete"
        raw["incomplete_details"] = {"reason": "max_output_tokens"}
    elif fault == "model":
        raw["model"] = "gpt-7-custom-2026-09-08"
    elif fault == "refusal":
        raw["output"] = [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                          "content": [{"type": "refusal", "refusal": "Cannot comply."}]}]
    elif fault == "schema":
        raw["output"][0]["arguments"] = "{}"
    else:
        raw["output"].append(dict(raw["output"][0], id="fc_extra", call_id="call_extra"))
    with install(monkeypatch, lambda _: httpx.Response(200, json=raw)), pytest.raises((RuntimeError, ValueError)):
        invoke(operation, "gpt-7-custom")
