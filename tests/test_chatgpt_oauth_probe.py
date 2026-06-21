"""S3: P1/P2 probe — OpenAI ChatGPT/Codex-backend OAuth (chatgpt_oauth).

Falsifiable proof of the A≠B distinction + the ChatGPT-backend capability floor
(LLM_AUTH_DRIVER_PLAN.md §9, grounded in Novelloom's proven probe):
  P1  : the OAuth access_token is REJECTED by api.openai.com (standard host) but
        STREAMS against https://chatgpt.com/backend-api/codex — proves it is not an
        sk- API key for the public API.
  P2a : the ChatGPT backend 400s `max_output_tokens` (Unsupported parameter).
  P2b : a single inline custom function call returns a `*_call` output item.
  P2c : model discovery needs a Codex-style `client_version` via extra_query, and
        ids come back in a nonstandard `models` field.

Every probe body is dependency-injected AND the OpenAI client is built behind a
monkeypatchable seam (`_openai_client`), so these tests use a FAKE token + FAKE
transport and make NO network call. Results flow through the redacted harness — a
token can never leak into a ProbeResult, even from an exception.
"""

from __future__ import annotations

import json

import pytest

import src.auth_drivers.chatgpt_oauth_probe as mod
from src.auth_drivers.chatgpt_oauth_probe import (
    CHATGPT_BACKEND_BASE_URL,
    STANDARD_BASE_URL,
    run_chatgpt_oauth_probe,
)

_TOK = "chatgpt-oauth-FAKEtok-AbCdEf0123456789ZyXwVu"


# --- fake transport -----------------------------------------------------------
class _Boom(Exception):
    pass


class _ApiErr(Exception):
    """A fake OpenAI-SDK-style error carrying an HTTP status_code (for P1a auth classification)."""

    def __init__(self, status_code, msg=""):
        super().__init__(msg or f"HTTP {status_code}")
        self.status_code = status_code


class _Timeout(Exception):
    """A fake network/timeout error — no status_code (must NOT count as a P1a pass)."""


class _FakePage:
    """A models.list page that exposes the NONSTANDARD `models` field (no `data`)."""

    def __init__(self, models):
        self.models = models


class _Resp:
    def __init__(self, on_create):
        self._on_create = on_create

    def create(self, **kwargs):
        return self._on_create(kwargs)


class _Models:
    def __init__(self, on_list):
        self._on_list = on_list

    def list(self, **kwargs):
        return self._on_list(kwargs)


class _FakeClient:
    def __init__(self, on_create=None, on_list=None):
        self.responses = _Resp(on_create or (lambda kw: []))
        self.models = _Models(on_list or (lambda kw: _FakePage([])))


def _raise(exc):
    raise exc


# --- runner orchestration (injected sync fns; no transport) -------------------
def test_runner_all_pass_with_injected_fns():
    res = run_chatgpt_oauth_probe(
        _TOK,
        p1_fn=lambda: (True, "standard host rejected; codex backend streamed 12 chars"),
        p2a_fn=lambda: (True, "400 Unsupported parameter: max_output_tokens"),
        p2b_fn=lambda: (True, "harvested a function_call output item"),
        p2c_fn=lambda: (True, "plain models.list 400'd; extra_query returned 6 ids"),
    )
    assert res["passed"] is True
    names = [p["name"] for p in res["probes"]]
    assert any("P1" in n for n in names)
    assert any("P2a" in n for n in names)
    assert any("P2b" in n for n in names)
    assert any("P2c" in n for n in names)
    assert all(p["passed"] for p in res["probes"])
    assert _TOK not in json.dumps(res)  # token never in the result


def test_runner_fails_if_any_probe_fails():
    res = run_chatgpt_oauth_probe(
        _TOK,
        p1_fn=lambda: (True, "ok"),
        p2a_fn=lambda: (False, "backend ACCEPTED max_output_tokens"),
        p2b_fn=lambda: (True, "ok"),
        p2c_fn=lambda: (True, "ok"),
    )
    assert res["passed"] is False
    p2a = next(p for p in res["probes"] if "P2a" in p["name"])
    assert p2a["passed"] is False


def test_runner_never_raises_even_if_all_fail():
    boom = lambda: _raise(RuntimeError("boom"))  # noqa: E731
    res = run_chatgpt_oauth_probe(_TOK, p1_fn=boom, p2a_fn=boom, p2b_fn=boom, p2c_fn=boom)
    assert res["passed"] is False and len(res["probes"]) == 4


def test_runner_redacts_token_from_exception():
    res = run_chatgpt_oauth_probe(
        _TOK,
        p1_fn=lambda: _raise(RuntimeError(f"leaky error mentioning {_TOK}")),
        p2a_fn=lambda: (True, "ok"),
        p2b_fn=lambda: (True, "ok"),
        p2c_fn=lambda: (True, "ok"),
    )
    assert res["passed"] is False
    assert _TOK not in json.dumps(res)  # token in the exception must be redacted


# --- P1 default body (host distinctness) via fake transport -------------------
def test_default_p1_pass_when_standard_rejects_and_codex_streams(monkeypatch):
    def factory(token, base_url):
        if base_url == STANDARD_BASE_URL:
            return _FakeClient(on_create=lambda kw: _raise(_ApiErr(401, "invalid_api_key")))
        return _FakeClient(on_create=lambda kw: [
            {"type": "response.output_text.delta", "delta": "OK"},
            {"type": "response.completed", "response": {"output": [], "output_text": "OK"}},
        ])

    monkeypatch.setattr(mod, "_openai_client", factory)
    passed, observed = mod._default_p1_host_distinctness(_TOK)
    assert passed is True and "codex" in observed.lower()


def test_default_p1_fail_when_standard_host_accepts(monkeypatch):
    # If api.openai.com ACCEPTS the OAuth token, the A/B invariant is violated → FAIL.
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=lambda kw: []))
    passed, observed = mod._default_p1_host_distinctness(_TOK)
    assert passed is False and ("invariant" in observed.lower() or "accepted" in observed.lower())


def test_default_p1_fail_when_codex_stream_errors(monkeypatch):
    def factory(token, base_url):
        if base_url == STANDARD_BASE_URL:
            return _FakeClient(on_create=lambda kw: _raise(_ApiErr(401)))
        return _FakeClient(on_create=lambda kw: [{"type": "response.failed"}])

    monkeypatch.setattr(mod, "_openai_client", factory)
    passed, observed = mod._default_p1_host_distinctness(_TOK)
    assert passed is False and "response.failed" in observed


def test_default_p1_pass_on_403_auth_rejection(monkeypatch):
    def factory(token, base_url):
        if base_url == STANDARD_BASE_URL:
            return _FakeClient(on_create=lambda kw: _raise(_ApiErr(403, "unauthorized")))
        return _FakeClient(on_create=lambda kw: [
            {"type": "response.output_text.delta", "delta": "OK"},
            {"type": "response.completed", "response": {"output": []}},
        ])

    monkeypatch.setattr(mod, "_openai_client", factory)
    passed, observed = mod._default_p1_host_distinctness(_TOK)
    assert passed is True


@pytest.mark.parametrize("exc", [
    _ApiErr(404, "model_not_found"),
    _ApiErr(400, "Unsupported parameter"),
    _ApiErr(429, "rate_limit_exceeded"),
    _Timeout("connection timed out"),
])
def test_default_p1_fail_when_standard_host_error_is_not_auth(monkeypatch, exc):
    # A non-auth error from api.openai.com (network/404/400/429) is INCONCLUSIVE —
    # it must NOT be counted as proof the OAuth token was rejected by the standard API.
    def factory(token, base_url):
        if base_url == STANDARD_BASE_URL:
            return _FakeClient(on_create=lambda kw: _raise(exc))
        return _FakeClient(on_create=lambda kw: [{"type": "response.completed", "response": {"output": []}}])

    monkeypatch.setattr(mod, "_openai_client", factory)
    passed, observed = mod._default_p1_host_distinctness(_TOK)
    assert passed is False
    assert "inconclusive" in observed.lower() or "not a pass" in observed.lower()


def test_default_p1_auth_error_message_with_token_is_redacted(monkeypatch):
    # If the standard-host auth error message embeds the token, the runner's
    # ProbeResult must not leak it (P1a labels by type+status, not the message).
    def factory(token, base_url):
        if base_url == STANDARD_BASE_URL:
            return _FakeClient(on_create=lambda kw: _raise(_ApiErr(401, f"invalid key {token}")))
        return _FakeClient(on_create=lambda kw: [
            {"type": "response.output_text.delta", "delta": "OK"},
            {"type": "response.completed", "response": {"output": []}},
        ])

    monkeypatch.setattr(mod, "_openai_client", factory)
    res = run_chatgpt_oauth_probe(
        _TOK, p2a_fn=lambda: (True, "ok"), p2b_fn=lambda: (True, "ok"), p2c_fn=lambda: (True, "ok"),
    )
    p1 = next(p for p in res["probes"] if "P1" in p["name"])
    assert p1["passed"] is True
    assert _TOK not in json.dumps(res)


# --- P2a default body (max_output_tokens → 400) -------------------------------
def test_default_p2a_pass_on_400_max_output_tokens(monkeypatch):
    def on_create(kw):
        if "max_output_tokens" in kw:
            raise _Boom("Error code: 400 - Unsupported parameter: max_output_tokens")
        return []

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=on_create))
    passed, observed = mod._default_p2a_max_output_tokens(_TOK)
    assert passed is True and "max_output_tokens" in observed


def test_default_p2a_fail_when_backend_accepts(monkeypatch):
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(
        on_create=lambda kw: [{"type": "response.completed", "response": {"output": []}}]))
    passed, observed = mod._default_p2a_max_output_tokens(_TOK)
    assert passed is False and "accept" in observed.lower()


def test_default_p2a_sends_max_output_tokens_raw(monkeypatch):
    # The strip is the DRIVER's job; the probe must send max_output_tokens RAW to
    # measure the backend's real behavior.
    seen = {}

    def on_create(kw):
        seen.update(kw)
        raise _Boom("400 Unsupported parameter: max_output_tokens")

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=on_create))
    mod._default_p2a_max_output_tokens(_TOK)
    assert "max_output_tokens" in seen  # not stripped by the probe


def test_default_p2a_sends_instructions_and_low_reasoning(monkeypatch):
    # The ChatGPT backend validates required request fields before it reaches the
    # unsupported-parameter check. Keep this aligned with the Novelloom smoke
    # shape so the probe actually measures max_output_tokens, not a missing field.
    seen = {}

    def on_create(kw):
        seen.update(kw)
        raise _Boom("400 Unsupported parameter: max_output_tokens")

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=on_create))
    mod._default_p2a_max_output_tokens(_TOK)
    assert seen["instructions"]
    assert seen["reasoning"] == {"effort": "low"}


# --- P2b default body (function-call output item) -----------------------------
def test_default_p2b_pass_harvests_function_call(monkeypatch):
    stream = [
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "lookup_fact", "arguments": "{\"key\": \"x\"}", "call_id": "c1"},
        ]}},
    ]
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=lambda kw: stream))
    passed, observed = mod._default_p2b_function_call(_TOK)
    assert passed is True and "call" in observed.lower()


def test_default_p2b_passes_when_stream_emits_function_call_arguments(monkeypatch):
    # Live 2026-06-21 shape: the backend streamed function-call argument events,
    # but response.completed did not include a response.output list. That still
    # proves tool-call support; the probe must not look only at terminal output.
    stream = [
        {"type": "response.created"},
        {"type": "response.output_item.added", "item": {"type": "function_call", "name": "lookup_fact"}},
        {"type": "response.function_call_arguments.delta", "delta": "{\"key\""},
        {"type": "response.function_call_arguments.done", "arguments": "{\"key\":\"x\"}"},
        {"type": "response.output_item.done", "item": {"type": "function_call", "name": "lookup_fact"}},
        {"type": "response.completed"},
    ]
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=lambda kw: stream))
    passed, observed = mod._default_p2b_function_call(_TOK)
    assert passed is True
    assert "stream" in observed.lower() or "function_call_arguments" in observed


def test_default_p2b_sends_flat_function_tool(monkeypatch):
    # Responses-API tool shape is FLAT: {type:function, name, ...} NOT nested under 'function'.
    seen = {}

    def on_create(kw):
        seen.update(kw)
        return [{"type": "response.completed", "response": {"output": [{"type": "function_call", "name": "lookup_fact"}]}}]

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=on_create))
    mod._default_p2b_function_call(_TOK)
    tools = seen.get("tools")
    assert tools and tools[0]["type"] == "function" and "name" in tools[0] and "function" not in tools[0]
    assert seen["reasoning"] == {"effort": "low"}


def test_default_p2b_fail_when_no_call_item(monkeypatch):
    stream = [{"type": "response.completed", "response": {"output": [{"type": "message", "content": []}]}}]
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_create=lambda kw: stream))
    passed, observed = mod._default_p2b_function_call(_TOK)
    assert passed is False
    assert "message" in observed


# --- P2c default body (model discovery: client_version via extra_query) --------
def test_default_p2c_pass_plain_400_then_extra_query_ids(monkeypatch):
    seen = {}

    def on_list(kw):
        eq = kw.get("extra_query") or {}
        if "client_version" not in eq:
            raise _Boom("400 - missing client_version")
        seen["client_version"] = eq["client_version"]
        return _FakePage([{"id": "gpt-5.4-mini"}, {"id": "gpt-5.5"}])  # nonstandard 'models' field

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_list=on_list))
    passed, observed = mod._default_p2c_model_discovery(_TOK)
    assert passed is True and "id" in observed.lower()
    assert "gpt-5.4-mini" in observed and "gpt-5.5" in observed
    assert seen.get("client_version")  # extra_query client_version was actually sent


def test_default_p2c_observed_caps_long_model_lists(monkeypatch):
    models = [{"id": f"gpt-test-{i}"} for i in range(25)]

    def on_list(kw):
        eq = kw.get("extra_query") or {}
        if "client_version" not in eq:
            raise _Boom("400 - missing client_version")
        return _FakePage(models)

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_list=on_list))
    passed, observed = mod._default_p2c_model_discovery(_TOK)
    assert passed is True
    assert "gpt-test-0" in observed and "gpt-test-19" in observed
    assert "gpt-test-20" not in observed
    assert "+5 more" in observed


def test_default_p2c_fail_when_no_ids(monkeypatch):
    def on_list(kw):
        eq = kw.get("extra_query") or {}
        if "client_version" not in eq:
            raise _Boom("400 missing client_version")
        return _FakePage([])  # extra_query accepted but empty inventory

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(on_list=on_list))
    passed, observed = mod._default_p2c_model_discovery(_TOK)
    assert passed is False


def test_default_p2c_fail_when_plain_list_does_not_400(monkeypatch):
    # If the bare models.list() does NOT 400, that's a deviation from the proven
    # shape — record it, don't silently pass.
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url: _FakeClient(
        on_list=lambda kw: _FakePage([{"id": "gpt-5.4-mini"}])))
    passed, observed = mod._default_p2c_model_discovery(_TOK)
    assert passed is False
