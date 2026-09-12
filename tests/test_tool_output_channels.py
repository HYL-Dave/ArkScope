"""Task2 real adapter owners, with only provider/data acquisition replaced."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import importlib
import importlib.util
import json
import logging
import socket
import sqlite3

from pydantic import BaseModel
import pytest

from src.agents.shared.output_boundary import OutputBoundaryError, output_scope
from src.auth_drivers.runtime_binding import RuntimeAuthBinding, activate_runtime_auth
from src.tools import registry as registry_module


CHANNELS = ("openai", "anthropic", "chatgpt", "claude")
OAUTH_CHANNELS = ("chatgpt", "claude")
MACRO_CHANNELS = (
    ("openai", "get_economic_calendar"), ("anthropic", "get_economic_calendar"),
    ("chatgpt", "get_economic_calendar"), ("claude", "get_economic_calendar"),
    ("openai", "get_macro_value"), ("anthropic", "get_macro_value"),
)
SECRET = "b4~q9!"
UNKNOWN_ANT_KEY = "sk-ant-api03-" + "a" * 40
UNSET = object()
SOURCES = {
    "get_news_brief": ("src.tools.news_tools", {"tickers": ["BOUNDARY"], "days": 7}),
    "get_economic_calendar": ("src.tools.macro_calendar_tools", {
        "country": "US", "importance": "high", "days_back": 7,
        "days_forward": 14, "as_of": "2026-09-12", "limit": 50,
    }),
    "get_macro_value": ("src.tools.macro_calendar_tools", {
        "series_id": "GDP", "observation_date": "2026-09-01", "as_of": "2026-09-12",
    }),
}


def public_data():
    return {
        "institutionalization": "internationalization counterrevolutionaries",
        "value": "1234567890123456789.123",
        "exponent": "-1.234567890123456789E+123",
        "amount": 123456789012345678901234567890,
        "accession": "0000320193-26-000123",
        "url": "https://example.test/reports/0000320193-26-000123?offset=1234567890123456789",
        "hash": "0123456789abcdef" * 4,
        "cursor": "eyJvZmZzZXQiOjEyMzQ1Njc4OTB9.public_PageCursor1234567890" * 4 + "==",
        "contact": "investor.relations@example.test",
        "token_usage": {"token_count": 1234567890123456},
        "optional": [None, True, False, 1.25, [], {}],
    }


def public_text():
    return (
        "internationalization counterrevolutionaries\n"
        "GDP 1234567890123456789.123; exponent -1.234567890123456789E+123\n"
        "https://example.test/report?cursor=eyJvZmZzZXQiOjEyMzQ1Njc4OTB9\n"
    )


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def policy_api():
    assert importlib.util.find_spec("src.tools.result_policy") is not None, "missing Task2 result policy admission"
    return importlib.import_module("src.tools.result_policy")


@dataclass
class Observation:
    success: bool
    body: str


def observe_native(raw, name):
    assert type(raw) is str
    prefix = f'<tool_output tool="{name}">\n'
    suffix = "\n</tool_output>"
    if raw.startswith(prefix) and raw.endswith(suffix):
        return Observation(True, raw[len(prefix):-len(suffix)])
    return Observation(False, raw)


class ForbiddenDAL:
    def __getattr__(self, name):
        pytest.fail("Task2 adapter test attempted DAL acquisition")


@pytest.fixture
def invoke(monkeypatch):
    # Keep real policy resolution, SDK decoration, dispatch, serialization and reducers.
    # The synthetic function replaces acquisition, never an admission or error boundary.
    default_registry = registry_module.create_default_registry

    def forbidden(*args, **kwargs):
        pytest.fail("Task2 adapter tests must not use a database or network")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    def call(channel, result=None, *, name="get_news_brief", policy=UNSET, error=None, token=None):
        module_name, args = SOURCES[name]
        source = importlib.import_module(module_name)
        dal = ForbiddenDAL()

        def handler(received_dal, **received_args):
            assert received_dal is dal
            assert received_args == args
            if error is not None:
                raise error
            return result

        monkeypatch.setattr(source, name, handler)
        registry = default_registry()
        definition = registry.get(name)
        assert definition is not None
        definition.function = handler
        if policy is not UNSET:
            definition.result_policy = policy
        monkeypatch.setattr(registry_module, "create_default_registry", lambda: registry)

        if channel == "chatgpt":
            from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver

            driver = OpenAIChatGPTOAuthDriver(registry=registry, dal=dal)
            ok, body = asyncio.run(driver._invoke_tool(name=name, args=args, token=token))
            return Observation(ok, body)
        if channel == "claude":
            from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool

            raw = asyncio.run(_invoke_bridged_tool(
                name=name, registry=registry, dal=dal, token=token,
                per_tool_timeout_s=5, args=args,
            ))
            assert set(raw) == {"content", "is_error"}
            assert len(raw["content"]) == 1
            assert raw["content"][0]["type"] == "text"
            return Observation(not raw["is_error"], raw["content"][0]["text"])

        try:
            if channel == "openai":
                from agents.tool_context import ToolContext
                from src.agents.openai_agent.tools import create_openai_tools

                tool = next(tool for tool in create_openai_tools(dal) if tool.name == f"tool_{name}")
                arguments = json.dumps(args)
                context = ToolContext(
                    context=None, tool_name=tool.name, tool_call_id="task2-fixture-call",
                    tool_arguments=arguments,
                )
                raw = asyncio.run(tool.on_invoke_tool(context, arguments))
            else:
                assert channel == "anthropic"
                from src.agents.anthropic_agent.tools import execute_tool

                raw = execute_tool(name, args, dal)
        except OutputBoundaryError as exc:
            return Observation(False, str(exc))
        return observe_native(raw, name)

    return call


def assert_rejected(observed, code, *forbidden_values):
    assert observed.success is False, "adapter admitted a rejected result as successful data"
    assert code in observed.body, "adapter did not return the bounded output-boundary failure"
    assert len(observed.body) <= 600
    assert "[REDACTED]" not in observed.body, "structured rejection must not become successful rewriting"
    for value in forbidden_values:
        assert value not in observed.body


def test_four_real_adapters_have_equal_unmodified_business_data(invoke):
    expected = public_data()
    with output_scope(SECRET):
        observations = {channel: invoke(channel, deepcopy(expected)) for channel in CHANNELS}
    for channel, observed in observations.items():
        assert observed.success, (channel, observed.body)
        assert "[REDACTED]" not in observed.body, f"{channel} rewrote public business data"
    decoded = {channel: json.loads(observed.body) for channel, observed in observations.items()}
    assert (
        canonical(decoded["openai"]) == canonical(decoded["anthropic"])
        == canonical(decoded["chatgpt"]) == canonical(decoded["claude"])
        == canonical(expected)
    )
    for result in decoded.values():
        assert result["value"] == "1234567890123456789.123"
        assert result["cursor"] == expected["cursor"]


@pytest.mark.parametrize("channel", CHANNELS)
def test_each_adapter_preserves_full_public_payload_without_lossy_diagnostics(channel, invoke):
    expected = public_data()
    value = deepcopy(expected)
    with output_scope(SECRET):
        observed = invoke(channel, value)
    assert observed.success
    assert "[REDACTED]" not in observed.body
    assert json.loads(observed.body) == expected
    assert value == expected


@pytest.mark.parametrize("channel", CHANNELS)
def test_result_list_is_canonical_json_not_python_list_repr(channel, invoke):
    expected = [{"value": "1234567890123456789.123", "ok": True}, {"value": None, "rows": []}]
    with output_scope():
        observed = invoke(channel, deepcopy(expected))
    assert observed.success
    assert '"value"' in observed.body, "list[dict] was stringified using Python repr"
    assert json.loads(observed.body) == expected


class PublicRow(BaseModel):
    value: Decimal
    observed: date
    published: datetime


@pytest.mark.parametrize("channel", CHANNELS)
def test_nested_native_models_dates_and_decimal_text_cross_each_adapter(channel, invoke):
    row = PublicRow(
        value=Decimal("1234567890123456789.123"), observed=date(2026, 9, 12),
        published=datetime(2026, 9, 12, 3, 4, 5, tzinfo=timezone.utc),
    )
    with output_scope():
        observed = invoke(channel, {"rows": [row]})
    assert observed.success
    assert json.loads(observed.body) == {"rows": [{
        "value": "1234567890123456789.123", "observed": "2026-09-12",
        "published": "2026-09-12T03:04:05+00:00",
    }]}


class ForeignValue:
    def __init__(self):
        self.calls = []

    def __str__(self):
        self.calls.append("str")
        return "rejected-object-repr"

    def __repr__(self):
        self.calls.append("repr")
        return "rejected-object-repr"


def bad_value(case):
    if case == "malformed-json":
        return '{"value": not-json}'
    if case == "json-string":
        return '{"value": "looks valid but violates JSON result policy"}'
    if case == "nan":
        return {"value": float("nan")}
    if case == "foreign":
        return {"value": ForeignValue()}
    if case == "cycle":
        value = []
        value.append(value)
        return value
    if case == "depth":
        value = 0
        for _ in range(65):
            value = [value]
        return value
    if case == "secret-value":
        return {"rows": [{"value": SECRET}]}
    if case == "secret-key":
        return {"rows": [{SECRET: "public"}]}
    if case == "numeric-secret":
        return {"value": 1234567890123456789}
    if case == "credential-key":
        return {"rows": [{"Proxy-Authorization": "public-looking-value"}]}
    raise AssertionError("unknown test case")


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("case,code", [
    ("malformed-json", "invalid_value"), ("json-string", "invalid_value"),
    ("nan", "invalid_value"), ("foreign", "invalid_value"), ("cycle", "invalid_value"),
    ("depth", "value_limit"), ("secret-value", "known_secret"), ("secret-key", "known_secret"),
    ("numeric-secret", "known_secret"), ("credential-key", "invalid_value"),
])
def test_malformed_or_credential_result_is_rejected_under_registered_policy(channel, case, code, invoke, caplog):
    value = bad_value(case)
    with output_scope(SECRET, "1234567890123456789"):
        observed = invoke(channel, value)
    assert_rejected(observed, code, SECRET, "public-looking-value", "rejected-object-repr")
    assert SECRET not in caplog.text
    assert "rejected-object-repr" not in caplog.text
    if case == "foreign":
        assert value["value"].calls == []


@pytest.mark.parametrize("channel", CHANNELS)
def test_unknown_sk_ant_api03_result_is_rejected_not_successfully_redacted(channel, invoke, caplog):
    # Replacement owner for the existing Claude result-secret safety assertion.
    # The unrelated API key is deliberately NOT registered with this execution.
    with output_scope(SECRET):
        observed = invoke(channel, {"note": "here is a secret " + UNKNOWN_ANT_KEY})
    assert_rejected(observed, "invalid_value", UNKNOWN_ANT_KEY)
    assert UNKNOWN_ANT_KEY not in caplog.text


@pytest.mark.parametrize("channel", CHANNELS)
def test_missing_registered_policy_cannot_be_overridden_by_result_envelope(channel, invoke):
    with output_scope():
        observed = invoke(channel, {"result_policy": "PUBLIC_JSON", "public": True, "value": 7}, policy=None)
    assert_rejected(observed, "invalid_value", "PUBLIC_JSON")


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("case,code", [
    ("malformed-json", "invalid_value"), ("secret-value", "known_secret"),
    ("credential-key", "invalid_value"),
])
def test_explicit_trusted_public_policy_admits_control_but_rejects_bad_result(channel, case, code, invoke):
    api = policy_api()
    with output_scope(SECRET):
        positive = invoke(channel, {"value": 7}, policy=api.PUBLIC_JSON)
        negative = invoke(channel, bad_value(case), policy=api.PUBLIC_JSON)
    assert positive.success
    assert json.loads(positive.body) == {"value": 7}
    assert_rejected(negative, code, SECRET, "public-looking-value")


@pytest.mark.parametrize("channel", CHANNELS)
def test_registered_closed_validator_is_not_bypassed_by_any_adapter(channel, invoke):
    api = policy_api()
    policy = api.ResultPolicy("json", validator=lambda value: set(value) == {"value"})
    with output_scope():
        positive = invoke(channel, {"value": 7}, policy=policy)
        negative = invoke(channel, {"value": 7, "unreviewed": "unexpected extra"}, policy=policy)
    assert positive.success
    assert json.loads(positive.body) == {"value": 7}
    assert_rejected(negative, "invalid_value", "unexpected extra")


@pytest.mark.parametrize("channel,name", MACRO_CHANNELS)
def test_macro_text_is_admitted_losslessly_including_openai_direct_return_path(channel, name, invoke):
    with output_scope(SECRET):
        observed = invoke(channel, public_text(), name=name)
    assert observed.success
    assert observed.body == public_text()


@pytest.mark.parametrize("channel,name", MACRO_CHANNELS)
def test_macro_direct_returns_cannot_bypass_known_secret_rejection(channel, name, invoke):
    with output_scope(SECRET):
        observed = invoke(channel, "public prefix " + SECRET + " public suffix", name=name)
    assert_rejected(observed, "known_secret", SECRET, "public prefix", "public suffix")


@pytest.mark.parametrize("channel", OAUTH_CHANNELS)
def test_macro_value_remains_vetoed_by_existing_oauth_allowlists(channel, invoke):
    observed = invoke(
        channel, name="get_macro_value",
        error=RuntimeError("off-allowlist handler was executed " + SECRET),
    )
    assert observed.success is False
    assert "allowlist veto" in observed.body
    assert SECRET not in observed.body


@pytest.mark.parametrize("channel", CHANNELS)
def test_tool_api_errors_are_sanitized_before_sdk_return_and_logging(channel, invoke, caplog):
    provider = "openai" if channel in ("openai", "chatgpt") else "anthropic"
    binding = RuntimeAuthBinding(provider=provider, source="fixture", auth_mode="api_key", _api_key=SECRET)
    with output_scope(SECRET), activate_runtime_auth(binding):
        observed = invoke(channel, error=RuntimeError("upstream failed " + SECRET + " " + "w" * 2000), token=SECRET)
    assert observed.success is False
    assert SECRET not in observed.body
    assert SECRET not in caplog.text
    assert len(observed.body) <= 600


@pytest.mark.parametrize("channel", OAUTH_CHANNELS)
def test_oauth_callback_checks_its_captured_bearer_even_without_an_outer_scope(channel, invoke):
    observed = invoke(channel, {"value": SECRET}, token=SECRET)
    assert_rejected(observed, "known_secret", SECRET)


def capture_real_reducer(monkeypatch, channel):
    path = (
        "src.auth_drivers.chatgpt_oauth_driver" if channel == "chatgpt"
        else "src.auth_drivers.claude_code_sdk_driver"
    )
    module = importlib.import_module(path)
    get_reducer = module.get_reducer
    seen = []

    def select(name):
        reducer = get_reducer(name)

        def record(payload, *, budget):
            seen.append((payload, budget))
            return reducer(payload, budget=budget)

        return record

    monkeypatch.setattr(module, "get_reducer", select)
    return seen


@pytest.mark.parametrize("channel", OAUTH_CHANNELS)
@pytest.mark.parametrize("case", ["secret-value", "secret-key", "credential-key", "nan"])
def test_admission_rejects_hidden_middle_before_any_reducer_or_preview(channel, case, invoke, monkeypatch):
    seen = capture_real_reducer(monkeypatch, channel)
    value = {"head": "public " * 4000, "middle": bad_value(case), "tail": "public " * 4000}
    with output_scope(SECRET):
        observed = invoke(channel, value)
    code = "known_secret" if case in ("secret-value", "secret-key") else "invalid_value"
    assert_rejected(observed, code, SECRET)
    assert seen == [], "rejected data crossed the admission boundary into a reducer"


@pytest.mark.parametrize("channel", OAUTH_CHANNELS)
def test_lossless_admission_precedes_unchanged_12000_character_channel_budget(channel, invoke, monkeypatch):
    seen = capture_real_reducer(monkeypatch, channel)
    value = {"rows": [public_data() for _ in range(80)]}
    with output_scope(SECRET):
        observed = invoke(channel, deepcopy(value))
    assert observed.success
    assert len(seen) == 1
    admitted, budget = seen[0]
    assert json.loads(admitted) == value
    assert budget == 12_000
    assert len(observed.body) <= 12_000
    assert "chars dropped" in observed.body
    assert "[REDACTED]" not in observed.body


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_direct_api_serializers_raise_typed_failure_before_tool_output_wrapping(channel):
    module = importlib.import_module(f"src.agents.{channel}_agent.tools")
    with output_scope(SECRET):
        for value, code in (
            ({"value": SECRET}, "known_secret"), ({"password": "public"}, "invalid_value"),
            ("{bad-json", "invalid_value"),
        ):
            with pytest.raises(OutputBoundaryError) as caught:
                module._serialize_result(value, tool_name="get_news_brief")
            assert caught.value.code == code
            assert str(caught.value) == code


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
@pytest.mark.parametrize("name", ["", "unregistered_public_tool"])
def test_direct_api_serializer_does_not_admit_unnamed_or_unknown_result_policy(channel, name):
    module = importlib.import_module(f"src.agents.{channel}_agent.tools")
    with output_scope():
        with pytest.raises(OutputBoundaryError, match="^invalid_value$"):
            module._serialize_result({"value": 7}, tool_name=name)


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_bridge_only_delegation_json_is_admitted_and_secret_checked(channel):
    module = importlib.import_module(f"src.agents.{channel}_agent.tools")
    with output_scope(SECRET):
        raw = module._serialize_result({"answer": "public", "ok": True}, tool_name="delegate_to_subagent")
        good = observe_native(raw, "delegate_to_subagent")
        assert good.success
        assert json.loads(good.body) == {"answer": "public", "ok": True}
        with pytest.raises(OutputBoundaryError, match="^known_secret$"):
            module._serialize_result({"answer": SECRET}, tool_name="delegate_to_subagent")


@pytest.mark.parametrize("case", ["holdings-json", "sdk-arguments"])
def test_openai_parse_errors_are_sanitized_before_sdk_failure_logging(case, monkeypatch, caplog):
    from agents import _debug
    from agents.tool_context import ToolContext
    from src.agents.openai_agent.tools import create_openai_tools

    monkeypatch.setattr(_debug, "DONT_LOG_TOOL_DATA", False)
    caplog.set_level(logging.ERROR)
    name = "tool_get_portfolio_analysis" if case == "holdings-json" else "tool_get_news_brief"
    tool = next(tool for tool in create_openai_tools(ForbiddenDAL()) if tool.name == name)
    arguments = json.dumps({"holdings_json": "{invalid " + SECRET}) if case == "holdings-json" else "{invalid " + SECRET
    context = ToolContext(context=None, tool_name=name, tool_call_id="parse-error", tool_arguments=arguments)
    with output_scope(SECRET):
        result = asyncio.run(tool.on_invoke_tool(context, arguments))
    assert SECRET not in result
    assert SECRET not in caplog.text
    assert len(result) <= 600


@pytest.mark.parametrize("channel", ["anthropic", "chatgpt", "claude"])
def test_unknown_tool_rejection_cannot_echo_an_untrusted_name(channel):
    name = SECRET * 1000
    registry = registry_module.ToolRegistry()
    with output_scope(SECRET):
        if channel == "anthropic":
            from src.agents.anthropic_agent.tools import execute_tool

            body = execute_tool(name, {}, ForbiddenDAL())
        elif channel == "chatgpt":
            from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver

            driver = OpenAIChatGPTOAuthDriver(registry=registry, dal=ForbiddenDAL())
            ok, body = asyncio.run(driver._invoke_tool(name=name, args={}, token=None))
            assert ok is False
        else:
            from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool

            result = asyncio.run(_invoke_bridged_tool(
                name=name, registry=registry, dal=ForbiddenDAL(), token=None,
                args={}, per_tool_timeout_s=5,
            ))
            assert result["is_error"] is True
            body = result["content"][0]["text"]
    assert SECRET not in body
    assert len(body) <= 600
    assert "invalid_value" in body
