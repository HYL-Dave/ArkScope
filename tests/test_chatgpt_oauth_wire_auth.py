"""Actual SDK serialization, synthetic credentials, no external transport."""

import asyncio
import json

import httpx
import openai
import pytest

from src.auth_drivers import chatgpt_oauth_driver as research
from src.auth_drivers import chatgpt_oauth_probe as probe
from src.auth_drivers import subscription_structured_output as fixed


@pytest.mark.parametrize("consumer", ["fixed_output", "research", "probe", "probe_api"])
@pytest.mark.parametrize("ambient", ["absent", "canonical", "lowercase", "mixed"])
@pytest.mark.parametrize("status", [200, 401])
def test_chatgpt_wire_uses_only_selected_bearer_even_with_ambient_auth(
    monkeypatch, consumer, ambient, status,
):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-ambient-api-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.invalid/v1")
    headers = {
        "absent": "X-Fixture: retained",
        "canonical": "Authorization: Bearer synthetic-stale\nX-Api-Key: synthetic-other-key",
        "lowercase": "authorization: Bearer synthetic-stale\nx-api-key: synthetic-other-key",
        "mixed": "Authorization: Bearer synthetic-stale\naUtHoRiZaTiOn: Bearer synthetic-other\n"
                 "X-Api-Key: synthetic-other-key\nx-api-KEY: synthetic-another-key",
    }
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", headers[ambient] + "\nX-Fixture: retained")
    requests = []

    def handle(request):
        requests.append(request)
        if status == 401:
            return httpx.Response(401, json={"error": {
                "message": "Provided access token is expired.", "type": "authentication_error",
            }})
        return httpx.Response(200, json={
            "id": "resp_fixture", "object": "response", "created_at": 1,
            "model": "gpt-5.6-luna", "status": "completed", "error": None, "output": [],
        })

    sync_cls, async_cls = openai.OpenAI, openai.AsyncOpenAI
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: sync_cls(
        **kw, http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ))
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kw: async_cls(
        **kw, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    ))
    base_url = "https://api.openai.com/v1" if consumer == "probe_api" else probe.CHATGPT_BACKEND_BASE_URL
    kwargs = {"model": "gpt-5.6-luna", "input": "Synthetic check.",
              "reasoning": {"effort": "max"}, "store": False}

    async def invoke_async():
        client = (fixed._openai_client("synthetic-selected", base_url, 10)
                  if consumer == "fixed_output" else research._execution_client("synthetic-selected"))
        async with client:
            await client.responses.create(**kwargs)

    def invoke():
        if consumer in {"fixed_output", "research"}:
            asyncio.run(invoke_async())
        else:
            with probe._openai_client("synthetic-selected", base_url) as client:
                client.responses.create(**kwargs)

    if status == 401:
        with pytest.raises(openai.AuthenticationError):
            invoke()
    else:
        invoke()
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == base_url + "/responses"
    assert request.headers.get_list("authorization") == ["Bearer synthetic-selected"]
    assert "x-api-key" not in request.headers
    assert request.headers["x-fixture"] == "retained"
    assert json.loads(request.content) == kwargs
