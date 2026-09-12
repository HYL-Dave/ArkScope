"""Task2 policy owners; synthetic values only, no tool or DAL execution."""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import fields
from datetime import date, datetime, timezone
from decimal import Decimal
import importlib
import importlib.util
import json
import sqlite3
import traceback
import tracemalloc
from urllib.parse import quote

from pydantic import BaseModel
import pytest

from src.agents.shared.output_boundary import OutputBoundaryError, OutputGuard, output_scope
from src.tools.registry import ToolDefinition, create_default_registry


MODULE = "src.tools.result_policy"
SECRET = 'fixture-only-credential/+?"=Task2'
MAX_BYTES = 32 * 1024**2
TEXT_TOOLS = (
    "check_data_freshness", "scan_alerts", "get_economic_calendar", "get_macro_value",
)
# Independent, source-inventoried names; do not derive expectations from the registry.
JSON_TOOLS = (
    "calculate_compound_growth", "calculate_dcf", "calculate_greeks",
    "calculate_implied_valuation", "calculate_peer_statistics", "calculate_weighted_scenarios",
    "delete_memory", "detect_event_chains", "detect_news_volume_anomaly",
    "get_analyst_consensus", "get_current_quote", "get_detailed_financials",
    "get_earnings_impact", "get_fundamentals_analysis", "get_insider_trades",
    "get_iv_skew_analysis", "get_morning_brief", "get_news_brief", "get_option_chain",
    "get_peer_comparison", "get_portfolio_analysis", "get_portfolio_holdings",
    "get_price_change", "get_report", "get_sa_alpha_picks", "get_sa_article_detail",
    "get_sa_articles", "get_sa_comment_focus", "get_sa_digest", "get_sa_feed",
    "get_sa_market_news", "get_sa_pick_detail", "get_sec_filings", "get_sector_performance",
    "get_security_lifecycle_review", "get_ticker_data_coverage", "get_ticker_news",
    "get_ticker_prices", "get_watchlist_overview", "list_high_value_comments",
    "list_memories", "list_reports", "list_security_lifecycle_reviews", "recall_memories",
    "refresh_sa_alpha_picks", "save_memory", "save_report", "search_news_advanced",
    "search_news_by_keyword", "web_browse",
)


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Task2 policy tests must not open a database")

    monkeypatch.setattr(sqlite3, "connect", forbidden)


def policy_api():
    assert importlib.util.find_spec(MODULE) is not None, "missing Task2 result policy admission"
    return importlib.import_module(MODULE)


def reject(api, value, *, policy, guard=None, code="invalid_value"):
    with pytest.raises(OutputBoundaryError) as caught:
        api.admit_tool_result(value, policy=policy, guard=guard)
    error = caught.value
    assert error.code == code
    assert error.args == (code,)
    assert str(error) == code
    assert SECRET not in repr(error)
    return error


class PublicRow(BaseModel):
    value: Decimal
    observed: date
    published: datetime


class ForeignValue:
    def __init__(self):
        self.calls = []

    def __str__(self):
        self.calls.append("str")
        return SECRET

    def __repr__(self):
        self.calls.append("repr")
        return SECRET


class DuckModel(ForeignValue):
    def model_dump(self, *args, **kwargs):
        self.calls.append("model_dump")
        return {"value": "apparently public"}


def nested(depth):
    value = 0
    for _ in range(depth):
        value = [value]
    return value


def test_result_policy_admission_exists():
    api = policy_api()
    assert callable(api.admit_tool_result)
    assert callable(api.serialize_tool_result)


def test_new_registration_has_explicit_none_default_and_is_not_admitted():
    metadata = {field.name: field for field in fields(ToolDefinition)}
    assert "result_policy" in metadata, "ToolDefinition has no trusted result_policy metadata"
    assert metadata["result_policy"].default is None
    tool = ToolDefinition("new_public_tool", "Synthetic tool", lambda: {"value": 1})
    assert tool.result_policy is None
    api = policy_api()
    reject(api, {"value": 1}, policy=tool.result_policy)


def test_registry_matches_the_complete_54_tool_source_inventory():
    registry = create_default_registry()
    assert len(registry.list_all()) == 54
    assert set(registry.list_names()) == set(JSON_TOOLS) | set(TEXT_TOOLS)
    assert registry.get("delegate_to_subagent") is None


@pytest.mark.parametrize("name", JSON_TOOLS + TEXT_TOOLS)
def test_every_builtin_declares_and_uses_its_reviewed_policy(name):
    tool = create_default_registry().get(name)
    assert getattr(tool, "result_policy", None) is not None, f"unclassified result policy: {name}"
    api = policy_api()
    if name in TEXT_TOOLS:
        assert tool.result_policy == api.PUBLIC_TEXT
        text = '{"value": "JSON-looking public prose"}\nnot a JSON document'
        assert api.admit_tool_result(text, policy=tool.result_policy) == text
        reject(api, {"value": 1}, policy=tool.result_policy)
    else:
        assert tool.result_policy == api.PUBLIC_JSON
        admitted = api.admit_tool_result({"value": "1234567890123456789.123"}, policy=tool.result_policy)
        assert json.loads(admitted) == {"value": "1234567890123456789.123"}
        reject(api, '{"value": 1}', policy=tool.result_policy)


def test_bridge_only_delegation_has_json_policy_but_unknown_names_do_not():
    api = policy_api()
    with output_scope():
        admitted = api.serialize_tool_result({"answer": "public", "ok": True}, tool_name="delegate_to_subagent")
        assert json.loads(admitted) == {"answer": "public", "ok": True}
        for name in ("", "unknown_public_tool", "delegate_to_subagent_extra"):
            with pytest.raises(OutputBoundaryError, match="^invalid_value$"):
                api.serialize_tool_result({"result_policy": "PUBLIC_JSON", "value": 1}, tool_name=name)


def test_public_json_preserves_words_numbers_urls_hashes_and_full_cursor():
    api = policy_api()
    value = {
        "institutionalization": "internationalization counterrevolutionaries",
        "value": "1234567890123456789.123",
        "exponent": "-1.234567890123456789E+123",
        "amount": 123456789012345678901234567890,
        "accession": "0000320193-26-000123",
        "hash": "0123456789abcdef" * 4,
        "url": "https://example.test/annual-report/0000320193-26-000123?offset=1234567890123456789",
        "cursor": "eyJvZmZzZXQiOjEyMzQ1Njc4OTB9.public_PaginationCursor1234567890==",
        "contact": "investor.relations@example.test",
        "token_usage": {"token_count": 1234567890123456},
        "authorization_status": "public",
        "optional": [True, False, None, 1.25, [], {}],
    }
    expected = deepcopy(value)
    admitted = api.admit_tool_result(value, policy=api.PUBLIC_JSON, guard=OutputGuard([SECRET]))
    assert json.loads(admitted) == expected
    assert value == expected
    assert "[REDACTED]" not in admitted


def test_equivalent_maps_have_one_canonical_json_serialization():
    api = policy_api()
    left = api.admit_tool_result({"z": [{"b": 2, "a": 1}], "a": []}, policy=api.PUBLIC_JSON)
    right = api.admit_tool_result({"a": [], "z": [{"a": 1, "b": 2}]}, policy=api.PUBLIC_JSON)
    assert left == right
    assert json.loads(left) == {"a": [], "z": [{"a": 1, "b": 2}]}


@pytest.mark.parametrize("as_list", [False, True], ids=["model", "nested-model"])
def test_native_pydantic_dates_and_finite_decimals_normalize_losslessly(as_list):
    api = policy_api()
    row = PublicRow(
        value=Decimal("1234567890123456789.123"), observed=date(2026, 9, 12),
        published=datetime(2026, 9, 12, 3, 4, 5, tzinfo=timezone.utc),
    )
    expected = {"value": "1234567890123456789.123", "observed": "2026-09-12", "published": "2026-09-12T03:04:05+00:00"}
    result = {"rows": [row], "exponent": Decimal("-1.234567890123456789E+123")} if as_list else row
    wanted = {"rows": [expected], "exponent": "-1.234567890123456789E+123"} if as_list else expected
    assert json.loads(api.admit_tool_result(result, policy=api.PUBLIC_JSON)) == wanted


@pytest.mark.parametrize("text", ["internationalization 1234567890123456789.123", '{"value": 12}', "{not-json", "NaN"])
def test_declared_text_is_never_autoparsed_or_heuristically_rewritten(text):
    api = policy_api()
    assert api.admit_tool_result(text, policy=api.PUBLIC_TEXT) == text


@pytest.mark.parametrize("raw", ["{not-json", '{"value": 1}', "[1, 2]", "NaN", "ordinary text"])
def test_json_policy_rejects_all_raw_strings_instead_of_falling_back_to_text(raw):
    api = policy_api()
    reject(api, raw, policy=api.PUBLIC_JSON)


@pytest.mark.parametrize("value", [None, 1, {"text": "public"}, ["public"]])
def test_text_policy_rejects_non_text_values(value):
    api = policy_api()
    reject(api, value, policy=api.PUBLIC_TEXT)


@pytest.mark.parametrize("policy", [None, "PUBLIC_JSON", {"kind": "json"}], ids=["none", "string", "self-declared-map"])
def test_untrusted_or_missing_policy_cannot_be_selected_by_result_content(policy):
    api = policy_api()
    reject(api, {"result_policy": "PUBLIC_JSON", "public": True, "value": 1}, policy=policy)


@pytest.mark.parametrize("factory", [ForeignValue, DuckModel], ids=["foreign-object", "duck-model"])
@pytest.mark.parametrize("location", ["root", "value", "key"])
def test_arbitrary_coercion_and_model_dump_duck_typing_are_never_invoked(factory, location):
    api = policy_api()
    foreign = factory()
    value = foreign if location == "root" else {"rows": [foreign]} if location == "value" else {foreign: "public"}
    reject(api, value, policy=api.PUBLIC_JSON)
    assert foreign.calls == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), Decimal("NaN"), Decimal("Infinity")],
                         ids=["nan", "positive-infinity", "negative-infinity", "decimal-nan", "decimal-infinity"])
def test_nonfinite_numbers_are_invalid_json_not_stringified_success(value):
    api = policy_api()
    reject(api, {"rows": [{"value": value}]}, policy=api.PUBLIC_JSON)


@pytest.mark.parametrize(
    "value",
    [{1: "public"}, {"raw": b"public"}, {"raw": {1, 2}}, {"raw": (1, 2)}, {"raw": "\ud800"}],
    ids=["nonstring-key", "bytes", "set", "tuple", "invalid-unicode"],
)
def test_non_json_types_and_invalid_unicode_are_typed_failures(value):
    api = policy_api()
    reject(api, value, policy=api.PUBLIC_JSON)


@pytest.mark.parametrize("kind", ["list", "dict"])
def test_cycles_reject_but_shared_acyclic_children_are_public(kind):
    api = policy_api()
    cycle = [] if kind == "list" else {}
    if kind == "list":
        cycle.append(cycle)
    else:
        cycle["self"] = cycle
    reject(api, cycle, policy=api.PUBLIC_JSON)
    child = {"value": 7}
    assert json.loads(api.admit_tool_result([child, child], policy=api.PUBLIC_JSON)) == [{"value": 7}, {"value": 7}]


@pytest.mark.parametrize("key", [
    "Authorization", "authorization", "AUTHORIZATION", "Proxy-Authorization", "proxy_authorization",
    "X-Api-Key", "x_api_key", "X API KEY", "api_key", "API-KEY", "access_token", "ACCESS-TOKEN",
    "refresh_token", "Refresh Token", "id_token", "client_secret", "CLIENT-SECRET",
    "password", "Password", "private_key", "PRIVATE-KEY",
])
def test_recursive_explicit_credential_keys_reject_even_without_known_secret(key):
    api = policy_api()
    reject(api, {"rows": [{key: "not-a-secret"}]}, policy=api.PUBLIC_JSON)


@pytest.mark.parametrize("literal", [
    "Bearer fixture.auth-value_1234567890", "bearer fixture.auth-value_1234567890",
    "sk-ant-api03-" + "a" * 40, "sk-ant-oat01-" + "b" * 40,
    "sk-proj-" + "C2d" * 20, "sk-" + "E3f" * 16, "ghp_" + "a" * 36,
], ids=["bearer", "lowercase-bearer", "anthropic-key", "anthropic-oauth", "openai-project", "openai-key", "github-key"])
@pytest.mark.parametrize("location", ["text", "value", "key"])
def test_narrow_known_auth_syntax_rejects_whole_result_without_rewriting(literal, location):
    api = policy_api()
    if location == "text":
        value = f"public start {literal} public end"
    elif location == "value":
        value = {"rows": [{"note": literal}]}
    else:
        value = {literal: "public"}
    reject(api, value, policy=api.PUBLIC_TEXT if location == "text" else api.PUBLIC_JSON)


@pytest.mark.parametrize("encode", [
    lambda value: value, lambda value: quote(value, safe=""),
    lambda value: base64.b64encode(value.encode()).decode(),
    lambda value: base64.urlsafe_b64encode(value.encode()).decode().rstrip("="),
    lambda value: json.dumps(value)[1:-1],
], ids=["raw", "url", "base64", "base64url-unpadded", "json-escaped"])
@pytest.mark.parametrize("location", ["text", "value", "key"])
def test_captured_secret_representations_reject_values_and_mapping_keys(encode, location):
    api = policy_api()
    encoded = encode(SECRET)
    if location == "text":
        value = encoded
    elif location == "value":
        value = {"rows": [{"value": encoded}]}
    else:
        value = {"rows": [{encoded: "public"}]}
    reject(api, value, policy=api.PUBLIC_TEXT if location == "text" else api.PUBLIC_JSON,
           guard=OutputGuard([SECRET]), code="known_secret")


@pytest.mark.parametrize("value,secret", [
    (1234567890123456789, "1234567890123456789"), (1.25, "1.25"),
    (Decimal("1.234E+25"), "1.234E+25"),
], ids=["integer", "float", "decimal-exponent"])
def test_implicit_active_guard_and_final_numeric_representation_are_checked(value, secret):
    api = policy_api()
    with output_scope(secret):
        reject(api, {"value": value}, policy=api.PUBLIC_JSON, code="known_secret")
    admitted = api.admit_tool_result({"value": value}, policy=api.PUBLIC_JSON)
    assert json.loads(admitted) == {"value": secret if isinstance(value, Decimal) else value}


def test_closed_validator_executes_and_rejects_an_unknown_extra_field():
    api = policy_api()
    policy = api.ResultPolicy("json", validator=lambda value: type(value) is dict and set(value) == {"value"})
    assert json.loads(api.admit_tool_result({"value": 7}, policy=policy)) == {"value": 7}
    reject(api, {"value": 7, "unreviewed": "public but not in the contract"}, policy=policy)


@pytest.mark.parametrize(
    "outcome", [False, None, 1, "true", {"valid": True}],
    ids=["false", "none", "truthy-int", "truthy-string", "truthy-dict"],
)
def test_validator_requires_literal_true_not_truthiness(outcome):
    api = policy_api()
    policy = api.ResultPolicy("json", validator=lambda value: outcome)
    reject(api, {"value": 7}, policy=policy)


def test_validator_return_does_not_invoke_arbitrary_truthiness_or_repr():
    api = policy_api()

    class TruthyValue(ForeignValue):
        def __bool__(self):
            self.calls.append("bool")
            return True

    outcome = TruthyValue()
    policy = api.ResultPolicy("json", validator=lambda value: outcome)
    reject(api, {"value": 7}, policy=policy)
    assert outcome.calls == []


def test_validator_exceptions_do_not_escape_as_raw_error_or_traceback_context():
    api = policy_api()

    def invalid(value):
        raise RuntimeError(SECRET)

    error = reject(api, {"value": 7}, policy=api.ResultPolicy("json", validator=invalid))
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert SECRET not in rendered


def test_validator_cannot_select_an_unrelated_core_error_code():
    api = policy_api()

    def invalid(value):
        raise OutputBoundaryError("secret_limit")

    reject(api, {"value": 7}, policy=api.ResultPolicy("json", validator=invalid))


@pytest.mark.parametrize("mutation", ["public", "credential", "cycle", "foreign"])
def test_validator_mutation_cannot_change_admitted_data_or_bypass_revalidation(mutation):
    api = policy_api()

    def mutate(value):
        if mutation == "public":
            value["rows"][0]["value"] = "altered public value"
        elif mutation == "credential":
            value["rows"][0]["password"] = SECRET
        elif mutation == "cycle":
            value["rows"].append(value)
        else:
            value["rows"].append(ForeignValue())
        return True

    reject(api, {"rows": [{"value": "original"}]}, policy=api.ResultPolicy("json", validator=mutate))


def test_depth_64_is_admitted_and_65_is_a_typed_limit_failure():
    api = policy_api()
    assert json.loads(api.admit_tool_result(nested(64), policy=api.PUBLIC_JSON)) == nested(64)
    reject(api, nested(65), policy=api.PUBLIC_JSON, code="value_limit")


def test_one_million_node_limit_counts_mapping_keys_and_container_nodes():
    api = policy_api()
    value = {"rows": [0] * (1_000_000 - 3)}
    admitted = json.loads(api.admit_tool_result(value, policy=api.PUBLIC_JSON))
    assert len(admitted["rows"]) == 999_997
    value["rows"].append(0)
    reject(api, value, policy=api.PUBLIC_JSON, code="value_limit")


def test_node_budget_stops_before_coercing_an_over_budget_foreign_value():
    api = policy_api()
    foreign = ForeignValue()
    value = [0] * 999_999 + [foreign]
    reject(api, value, policy=api.PUBLIC_JSON, code="value_limit")
    assert foreign.calls == []


def test_text_32_mib_limit_counts_encoded_bytes_not_unicode_characters():
    api = policy_api()
    text = "\U0001f4c8" * (MAX_BYTES // 4)
    assert api.admit_tool_result(text, policy=api.PUBLIC_TEXT) == text
    reject(api, text + "x", policy=api.PUBLIC_TEXT, code="value_limit")


def test_json_32_mib_limit_counts_container_and_escape_encoding_overhead():
    api = policy_api()
    value = ["x" * (MAX_BYTES - 4)]
    admitted = api.admit_tool_result(value, policy=api.PUBLIC_JSON)
    assert len(admitted.encode("utf-8")) == MAX_BYTES
    assert json.loads(admitted) == value
    reject(api, ["x" * (MAX_BYTES - 3)], policy=api.PUBLIC_JSON, code="value_limit")
    reject(api, ["\\" * (MAX_BYTES // 2)], policy=api.PUBLIC_JSON, code="value_limit")


def test_oversized_key_is_bounded_before_allocating_canonicalized_key_copies():
    api = policy_api()
    value = {"A" * (MAX_BYTES + 1): 0}
    tracemalloc.start()
    try:
        reject(api, value, policy=api.PUBLIC_JSON, code="value_limit")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8 * 1024**2, "rejected key was copied wholesale before its byte bound"
