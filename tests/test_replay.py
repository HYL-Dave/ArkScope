"""Tests for the replay harness (P0.1 minimal-spike).

Coverage:
  - schema helpers (hash, digest, shape, normalize)
  - ReplayCapture lifecycle + on-disk fixture round-trip
  - load_trace input validation
  - validate_trace_against_registry: pass / unknown-tool / unknown-arg / missing-required
  - env-flag gating (capture is no-op when disabled)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agents.shared.replay import (
    DIGEST_LEN,
    ENV_FLAG,
    SCHEMA_VERSION,
    CapturedToolCall,
    ReplayCapture,
    ValidationResult,
    _SERVER_TOOL_KINDS_BY_PROVIDER,
    _canonical_tool_name,
    _currently_wired_server_tools,
    compute_shape,
    digest_json,
    hash_text,
    is_capture_enabled,
    load_trace,
    normalize_args,
    validate_trace_against_registry,
)

FIXTURE_DIR = Path(__file__).parent / "replay_fixtures"
NO_TOOL_FIXTURE = FIXTURE_DIR / "no_tool_turn.json"
ONE_TOOL_FIXTURE = FIXTURE_DIR / "one_tool_turn.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_hash_text_stable_and_short():
    h1 = hash_text("hello")
    h2 = hash_text("hello")
    h3 = hash_text("world")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == DIGEST_LEN


def test_digest_json_sort_invariance():
    # Same logical dict, different insertion order → same digest.
    a = {"ticker": "NVDA", "days": 7}
    b = {"days": 7, "ticker": "NVDA"}
    assert digest_json(a) == digest_json(b)


def test_digest_json_handles_non_serializable():
    # default=str fallback should not crash on, e.g., a set
    d = digest_json({"x": {1, 2, 3}})
    assert isinstance(d, str) and len(d) == DIGEST_LEN


def test_compute_shape_basic_types():
    assert compute_shape("hello") == "str"
    assert compute_shape(42) == "int"
    assert compute_shape(3.14) == "float"
    assert compute_shape(True) == "bool"
    assert compute_shape(None) == "NoneType"


def test_compute_shape_dict_and_list():
    shape = compute_shape({"ticker": "NVDA", "count": 3, "items": [{"a": 1}]})
    assert shape == {
        "ticker": "str",
        "count": "int",
        "items": [{"a": "int"}],
    }


def test_compute_shape_empty_list():
    assert compute_shape([]) == []


def test_compute_shape_depth_capped():
    deep = {"a": {"b": {"c": {"d": {"e": "leaf"}}}}}
    shape = compute_shape(deep)
    # At max depth (4) anything deeper collapses to "..."
    assert shape["a"]["b"]["c"]["d"] == "..."


def test_normalize_args_sorts_keys():
    a = normalize_args({"b": 2, "a": 1, "c": 3})
    assert list(a.keys()) == ["a", "b", "c"]


def test_normalize_args_wraps_non_dict():
    assert normalize_args("raw_string") == {"_raw": "raw_string"}
    assert normalize_args(None) == {"_raw": None}


# ---------------------------------------------------------------------------
# Env flag gating
# ---------------------------------------------------------------------------


def test_is_capture_enabled_default_false(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    assert is_capture_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "ON", "True"])
def test_is_capture_enabled_truthy(monkeypatch, val):
    monkeypatch.setenv(ENV_FLAG, val)
    assert is_capture_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "off"])
def test_is_capture_enabled_falsy(monkeypatch, val):
    monkeypatch.setenv(ENV_FLAG, val)
    assert is_capture_enabled() is False


# ---------------------------------------------------------------------------
# Capture lifecycle + round-trip
# ---------------------------------------------------------------------------


def test_capture_save_and_reload(tmp_path):
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial(
        question="What is 2+2?",
        system_prompt="You are a helpful assistant.",
        tools_available=["get_ticker_news", "get_news_brief"],
    )
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA", "days": 7},
        result='{"ticker": "NVDA", "articles": [], "count": 0}',
    )
    cap.record_final("Four.", {"input_tokens": 10, "output_tokens": 1})

    path = cap.save()
    assert path.exists()
    assert path.parent.parent == tmp_path  # nested under session_id dir

    trace = load_trace(path)
    assert trace.schema_version == SCHEMA_VERSION
    assert trace.user_input == "What is 2+2?"
    assert trace.provider == "anthropic"
    assert trace.tools_available == ["get_news_brief", "get_ticker_news"]  # sorted
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "get_ticker_news"
    assert call.arguments == {"days": 7, "ticker": "NVDA"}  # sorted
    assert call.result_shape == {"ticker": "str", "articles": [], "count": "int"}


def test_capture_records_no_tool_turns(tmp_path):
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial("hi", "system prompt", ["get_ticker_news"])
    cap.record_final("hello", {})
    path = cap.save()
    trace = load_trace(path)
    assert trace.tool_calls == []


# ---------------------------------------------------------------------------
# load_trace validation
# ---------------------------------------------------------------------------


def test_load_trace_rejects_unknown_schema_version(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        load_trace(bad)


def test_load_trace_rejects_missing_fields(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 1}))
    with pytest.raises(ValueError, match="missing required fields"):
        load_trace(bad)


def test_load_trace_rejects_non_object(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_trace(bad)


def test_load_trace_loads_real_fixtures():
    no_tool = load_trace(NO_TOOL_FIXTURE)
    assert no_tool.tool_calls == []
    assert no_tool.user_input.startswith("What is")

    one_tool = load_trace(ONE_TOOL_FIXTURE)
    assert len(one_tool.tool_calls) == 1
    assert one_tool.tool_calls[0].name == "get_ticker_news"


# ---------------------------------------------------------------------------
# Validation against registry
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_registry():
    from src.tools.registry import create_default_registry
    return create_default_registry()


def test_validate_no_tool_fixture_passes(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert isinstance(result, ValidationResult)
    assert result.passed is True
    assert result.errors == []


def test_validate_one_tool_fixture_passes(real_registry):
    trace = load_trace(ONE_TOOL_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is True, result.render()


def test_validate_flags_unknown_tool(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="this_tool_does_not_exist",
            arguments={"x": 1},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("this_tool_does_not_exist" in e for e in result.errors)


def test_validate_flags_unknown_argument(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="get_ticker_news",
            arguments={"ticker": "NVDA", "obsolete_arg": True},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("obsolete_arg" in e for e in result.errors)


def test_validate_flags_missing_required_argument(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    # ticker is required for get_ticker_news; omit it
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="get_ticker_news",
            arguments={"days": 7},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("ticker" in e for e in result.errors)


def test_validate_warns_on_prompt_drift(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    result = validate_trace_against_registry(
        trace, real_registry, current_system_prompt="totally different prompt text"
    )
    # Hash will not match the fixture's placeholder zeros
    assert any("system_prompt_hash drift" in w for w in result.warnings)
    # Drift is a warning only, not a failure
    assert result.passed is True


def test_validate_warns_on_registry_diff(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    # Capture claimed only 2 tools; current registry has many more → "added"
    result = validate_trace_against_registry(trace, real_registry)
    assert any("newly registered" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 1: tool-name canonicalization
# ---------------------------------------------------------------------------


def test_canonical_tool_name_strips_openai_bridge_prefix():
    # OpenAI bridge functions are registered as ``tool_<canonical>``.
    assert _canonical_tool_name("tool_get_ticker_news") == "get_ticker_news"
    assert _canonical_tool_name("tool_get_news_brief") == "get_news_brief"


def test_canonical_tool_name_idempotent_and_safe():
    # Anthropic / canonical names are pass-through.
    assert _canonical_tool_name("get_ticker_news") == "get_ticker_news"
    # Idempotent — applying twice yields the same result.
    once = _canonical_tool_name("tool_foo")
    assert _canonical_tool_name(once) == once
    # Non-string input must not raise.
    assert _canonical_tool_name(None) == ""  # type: ignore[arg-type]
    assert _canonical_tool_name(123) == ""  # type: ignore[arg-type]
    # Empty string stays empty (no spurious prefix strip).
    assert _canonical_tool_name("") == ""


def test_provider_tool_name_round_trips_through_save_and_load(tmp_path):
    cap = ReplayCapture(
        provider="openai",
        model="gpt-5.4",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial(
        question="news on NVDA",
        system_prompt="You are an assistant.",
        tools_available=["get_ticker_news"],
    )
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA"},
        result='{"ticker": "NVDA", "articles": []}',
        provider_tool_name="tool_get_ticker_news",
    )
    cap.record_final("done", {})
    path = cap.save()

    trace = load_trace(path)
    call = trace.tool_calls[0]
    assert call.name == "get_ticker_news"  # canonical persisted as primary name
    assert call.provider_tool_name == "tool_get_ticker_news"  # bridge name preserved


def test_provider_tool_name_optional_for_anthropic_path(tmp_path):
    # Anthropic regular tools never set ``provider_tool_name`` — confirm
    # the field stays ``None`` (forward-compat through load_trace).
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial("q", "sys", ["get_ticker_news"])
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA"},
        result="{}",
    )
    cap.record_final("ok", {})
    trace = load_trace(cap.save())
    assert trace.tool_calls[0].provider_tool_name is None


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 1: server-tool namespacing + introspection
# ---------------------------------------------------------------------------


def _make_server_trace(provider: str, kinds: list) -> Any:
    """Helper: synthesize a minimal trace claiming the given server tools."""
    base = load_trace(NO_TOOL_FIXTURE)
    base.provider = provider
    base.tools_available = kinds + ["get_ticker_news"]  # mix server + registry
    base.tool_calls = []
    return base


def test_validate_accepts_server_web_search_for_anthropic(real_registry):
    trace = _make_server_trace("anthropic", ["server:web_search"])
    result = validate_trace_against_registry(trace, real_registry)
    # Anthropic agent module currently wires _CLAUDE_WEB_SEARCH_TOOL → passes.
    assert result.passed is True, result.render()
    # No "server tool no longer wired" error.
    assert not any("server tool" in e for e in result.errors)


def test_validate_rejects_server_when_anthropic_not_wired(real_registry, monkeypatch):
    # Drop the ``type`` key on the live Anthropic web-search constant —
    # the introspective helper falls through to empty, so the captured
    # ``server:web_search`` claim fails validation.
    from src.agents.anthropic_agent import agent as a_mod
    monkeypatch.setattr(a_mod, "_CLAUDE_WEB_SEARCH_TOOL", {"name": "web_search"})

    trace = _make_server_trace("anthropic", ["server:web_search"])
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("server tool" in e and "web_search" in e for e in result.errors)


def test_currently_wired_server_tools_unknown_provider_empty():
    # Defensive: unknown provider name must return empty set (no crash).
    assert _currently_wired_server_tools("vertex") == set()
    assert _currently_wired_server_tools("") == set()


def test_server_tool_mapping_forward_anthropic_constant_in_mapping():
    """Forward safeguard: the live Anthropic web-search constant's
    ``type`` value must be a key in the static mapping. Catches version
    bumps (e.g. ``web_search_20260209`` → ``web_search_20270101``) that
    forget to update the mapping — without this, every existing fixture
    claiming ``server:web_search`` would silently fail validation."""
    from src.agents.anthropic_agent.agent import _CLAUDE_WEB_SEARCH_TOOL
    raw_type = _CLAUDE_WEB_SEARCH_TOOL.get("type")
    assert raw_type, "_CLAUDE_WEB_SEARCH_TOOL must declare a 'type' key"
    assert raw_type in _SERVER_TOOL_KINDS_BY_PROVIDER["anthropic"], (
        f"Anthropic _CLAUDE_WEB_SEARCH_TOOL['type']={raw_type!r} drifted "
        f"out of sync with _SERVER_TOOL_KINDS_BY_PROVIDER['anthropic']"
    )


def test_server_tool_mapping_forward_openai_websearchtool_class_name():
    """Forward safeguard: the OpenAI mapping must use the actual class
    name of ``WebSearchTool``. Catches SDK renames before validation
    silently breaks."""
    pytest.importorskip("agents")
    from agents import WebSearchTool
    cls_name = WebSearchTool.__name__
    assert cls_name in _SERVER_TOOL_KINDS_BY_PROVIDER["openai"], (
        f"agents.WebSearchTool.__name__={cls_name!r} drifted out of sync "
        f"with _SERVER_TOOL_KINDS_BY_PROVIDER['openai']"
    )


def test_server_tool_mapping_reverse_helper_resolves_known_kinds(monkeypatch):
    """Reverse safeguard: every kind the static mapping CAN produce must
    be reachable through ``_currently_wired_server_tools`` when the live
    module's symbol matches a mapping key. Stops mappings from accreting
    orphan entries that don't correspond to any live wiring path."""
    from src.agents.anthropic_agent import agent as a_mod
    for raw_type, kind in _SERVER_TOOL_KINDS_BY_PROVIDER["anthropic"].items():
        # Synthesize live state matching this mapping key.
        monkeypatch.setattr(
            a_mod, "_CLAUDE_WEB_SEARCH_TOOL", {"type": raw_type}, raising=False,
        )
        wired = _currently_wired_server_tools("anthropic")
        assert kind in wired, (
            f"Mapping entry {raw_type!r} → {kind!r} did not resolve via "
            f"_currently_wired_server_tools — helper is broken or mapping "
            f"references a key the helper does not consult."
        )