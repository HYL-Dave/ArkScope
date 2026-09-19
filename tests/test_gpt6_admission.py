"""GPT-6 request compatibility, without live credentials or provider calls."""

import json

import httpx
import pytest
from openai import BadRequestError, OpenAI

from src import card_synthesis as cs
from src.auth_drivers.live_resolver import LiveAuthResolution
from src.evidence_packet import EvidencePacket
from src.model_capabilities import capability_for
from src.model_routing import default_model_for, task_route_admission_detail


MODEL = "gpt-6-astra"

@pytest.mark.parametrize("auth", ["api_key", "chatgpt_oauth"])
@pytest.mark.parametrize("task", ["card_synthesis", "ai_research", "lifecycle_investigation"])
def test_astra_task_admission_exposes_supported_efforts_without_replacing_defaults(auth, task):
    assert capability_for(MODEL) is not None
    for effort in ("low", "medium", "high", "xhigh", "max"):
        assert task_route_admission_detail("openai", MODEL, effort, task=task, auth_mode=auth) is None
    for effort in ("none", "minimal", "ultra"):
        assert task_route_admission_detail("openai", MODEL, effort, task=task, auth_mode=auth) is not None
    assert capability_for(MODEL).context_limit == 1_050_000
    assert capability_for(MODEL).max_output == 128_000
    assert default_model_for("openai", task) == "gpt-5.6-luna"


def _payload(operation):
    assert operation == "synthesis"
    return {"conclusion": "Insufficient evidence.", "counter_thesis": [],
            "confidence_level": "low", "claims": []}


def _invoke(operation, model=MODEL):
    assert operation == "synthesis"
    return cs._synthesize_openai(
        EvidencePacket(ticker="TEST", generated_at="2026-09-08T00:00:00Z", items=[]),
        model, effort="low", model_timeout_s=42,
    )[0].model_dump()


def _response(operation, **changes):
    return {"id": "resp_test", "object": "response", "created_at": 1,
            "model": MODEL, "status": "completed", "error": None,
            "output": [{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                        "status": "completed", "name": "emit_result_card",
                        "arguments": json.dumps(_payload(operation))}], **changes}


def _install_api(monkeypatch, handler):
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth",
                        lambda _: LiveAuthResolution(provider="openai", source="db_api_key", credential_id="local:test"))
    client = OpenAI(api_key="test-not-a-credential", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("src.auth_drivers.live_resolver.live_openai_client", lambda: client)
    return client


@pytest.mark.parametrize("operation", ["synthesis"])
def test_astra_fixed_tasks_use_responses_with_one_forced_output_and_preserve_input(monkeypatch, operation):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=_response(operation))

    with _install_api(monkeypatch, handler):
        result = _invoke(operation)
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == MODEL
    assert body["reasoning"] == {"effort": "low"}
    assert body["store"] is False
    assert body["parallel_tool_calls"] is False
    assert body["max_output_tokens"] == 8192
    tool = body["tools"][0]
    assert body["tool_choice"] == {"type": "function", "name": tool["name"]}
    # Preserve optional card fields instead of letting Responses normalize them.
    assert tool["strict"] is False
    assert tool["parameters"] == cs._CARD_TOOL_SCHEMA
    assert not {"temperature", "top_p", "logprobs", "top_logprobs", "reasoning_effort", "messages"} & body.keys()
    assert [item["role"] for item in body["input"]] == ["system", "user"]
    assert "TEST" in body["input"][1]["content"]
    assert all(result[key] == value for key, value in _payload(operation).items())


@pytest.mark.parametrize("operation", ["synthesis"])
@pytest.mark.parametrize("failure", ["incomplete", "refusal", "no_call", "wrong_call", "two_calls", "non_object", "malformed", "other_model"])
def test_astra_invalid_output_is_rejected_without_retry_or_transport_fallback(monkeypatch, operation, failure):
    response = _response(operation)
    if failure == "incomplete":
        response["status"] = "incomplete"
    elif failure == "refusal":
        response["output"].append({"type": "message", "id": "msg_test", "status": "completed", "role": "assistant",
                                   "content": [{"type": "refusal", "refusal": "Cannot comply."}]})
    elif failure == "no_call":
        response["output"] = []
    elif failure == "wrong_call":
        response["output"][0]["name"] = "unexpected_tool"
    elif failure == "two_calls":
        response["output"] *= 2
    elif failure == "non_object":
        response["output"][0]["arguments"] = "[]"
    elif failure == "malformed":
        response["output"][0]["arguments"] = "{"
    elif failure == "other_model":
        response["model"] = "gpt-5.6-luna"
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=response)

    with _install_api(monkeypatch, handler), pytest.raises((RuntimeError, ValueError)):
        _invoke(operation)
    assert len(requests) == 1


@pytest.mark.parametrize("operation", ["synthesis"])
def test_astra_provider_rejection_does_not_retry_change_effort_or_bill_another_source(monkeypatch, operation):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(400, json={"error": {"message": "unsupported parameter", "type": "invalid_request_error"}})

    with _install_api(monkeypatch, handler), pytest.raises(BadRequestError):
        _invoke(operation)
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    assert json.loads(requests[0].content)["model"] == MODEL


@pytest.mark.parametrize("operation", ["synthesis"])
def test_custom_fixed_tasks_use_responses_without_rewriting_model_id(monkeypatch, operation):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/responses"
        assert json.loads(request.content)["model"] == "custom-chat-model"
        return httpx.Response(200, json=_response(operation, model="custom-chat-model"))

    with _install_api(monkeypatch, handler):
        result = _invoke(operation, "custom-chat-model")
    assert len(requests) == 1
    assert all(result[key] == value for key, value in _payload(operation).items())


@pytest.mark.parametrize("operation", ["synthesis"])
def test_astra_oauth_stays_on_subscription_transport(monkeypatch, operation):
    requests = []
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth",
                        lambda _: LiveAuthResolution(provider="openai", source="oauth_driver_unwired", credential_id="local:test"))
    monkeypatch.setattr("src.auth_drivers.live_resolver.live_openai_client",
                        lambda: pytest.fail("Subscription must not construct an API-key client"))
    monkeypatch.setattr("src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
                        lambda **kw: requests.append(kw) or _payload(operation))
    result = _invoke(operation)
    assert len(requests) == 1
    assert requests[0]["model"] == MODEL
    assert requests[0]["auth_mode"] == "chatgpt_oauth"
    assert requests[0]["effort"] == "low"
    assert all(result[key] == value for key, value in _payload(operation).items())


@pytest.mark.parametrize("operation", ["synthesis"])
def test_astra_timeout_uses_fixed_task_error_without_retry(monkeypatch, operation):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("fixture timeout", request=request)

    with _install_api(monkeypatch, handler), pytest.raises(cs.ModelExecutionTimeout) as caught:
        _invoke(operation)
    assert len(requests) == 1
    assert caught.value.model == MODEL
    assert caught.value.effective_seconds == 42


def test_astra_completed_snapshot_with_reasoning_preserves_synthesis(monkeypatch):
    response = _response("synthesis", model="gpt-6-astra-2026-09-08")
    response["output"].insert(0, {"type": "reasoning", "id": "rs_test", "summary": []})
    with _install_api(monkeypatch, lambda _: httpx.Response(200, json=response)):
        result = _invoke("synthesis")
    assert all(result[key] == value for key, value in _payload("synthesis").items())


@pytest.mark.parametrize("auth", ["api_key", "chatgpt_oauth"])
def test_astra_is_selectable_with_correct_efforts_even_with_pre_release_discovery(tmp_path, auth):
    from src.model_discovery_cache import ModelDiscoveryCache
    from src.model_effective import ActiveCredential, effective_model_view_v2

    cache = ModelDiscoveryCache(tmp_path / "profile.db")
    cache.record_run(provider="openai", auth_mode=auth, credential_id="local:test",
                     secret_fingerprint="test", status="ok", models=[{"id": "gpt-5.6-luna", "source": "provider_api"}])
    view = effective_model_view_v2(cache=cache, routes={}, credentials={"openai": ActiveCredential(
        provider="openai", auth_mode=auth, credential_id="local:test", secret_fingerprint="test")})
    for task in ('card_synthesis', 'ai_research', 'lifecycle_investigation'):
        models = view["tasks"][task]["providers"]["openai"]["models"]
        entries = [entry for entry in models if entry["id"] == MODEL]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["eligible"] is True
        assert entry["status"] == "seed"
        assert entry["visible_to_credential"] is None
        assert entry["effort_options"] == ["low", "medium", "high", "xhigh", "max"]


@pytest.mark.parametrize("requested,observed", [
    (MODEL, "gpt-6-astra-unreviewed"),
    (MODEL, "gpt-6-astra-2026-99-99"),
    (MODEL, "2026-09-08"),
    ("gpt-6-astra-2026-09-08", "gpt-6-astra-2026-09-09"),
    ("gpt-6-astra-2026-09-08", MODEL),
])
def test_astra_model_receipt_rejects_variants_and_explicit_snapshot_substitution(monkeypatch, requested, observed):
    response = _response("synthesis", model=observed)
    with _install_api(monkeypatch, lambda _: httpx.Response(200, json=response)), pytest.raises(RuntimeError, match="different model"):
        _invoke("synthesis", requested)


@pytest.mark.parametrize("payload", [
    {}, {"conclusion": 42}, {**_payload("synthesis"), "extra": True},
])
def test_astra_structured_output_must_satisfy_the_requested_schema(monkeypatch, payload):
    response = _response("synthesis")
    response["output"][0]["arguments"] = json.dumps(payload)
    with _install_api(monkeypatch, lambda _: httpx.Response(200, json=response)), pytest.raises(cs.ModelStructuredOutputInvalid, match="structured_output_invalid"):
        _invoke("synthesis")
